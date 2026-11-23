from dataclasses import dataclass
from inspect import Parameter, getdoc
from json import dumps
from urllib.parse import quote, urlencode

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.convertors import FloatConvertor, IntegerConvertor, PathConvertor, UUIDConvertor
from starlette.routing import NoMatchFound, Route

from ..models import ProviderFn, QueryString
from ..utils.feed import compile_filters
from ..utils.parameters import RouteParameters
from ..utils.provider import ProviderInputError, provider_signature

_CONVERTOR_LABELS = {
    FloatConvertor: "number",
    IntegerConvertor: "integer",
    PathConvertor: "path",
    UUIDConvertor: "UUID",
}


class RouteDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    description: str | None = None
    parameters: dict[str, str] = Field(default_factory=dict)
    examples: list[object] = Field(default_factory=list)


class RouteExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    path: dict[str, str] = Field(default_factory=dict)
    query: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParameterDoc:
    name: str
    required: bool
    type_label: str | None
    description: str | None
    default: str | None = None


@dataclass(frozen=True, slots=True)
class ExampleLinks:
    label: str
    rss: str
    atom: str


@dataclass(frozen=True, slots=True)
class FeedRouteGroup:
    routes: list[Route]
    uses_format_query: bool
    summary: str | None
    description: str | None
    path_parameters: tuple[ParameterDoc, ...]
    query_parameters: tuple[ParameterDoc, ...]
    examples: list[ExampleLinks]
    diagnostics: list[str]


def _example_path(route: Route, path: dict[str, str]) -> str:
    # A converter can generate a string that its own route will not match.
    resolved = str(route.url_path_for(route.name, **path))
    if not route.path_regex.fullmatch(resolved) or {".", ".."}.intersection(resolved.split("/")):
        message = "The example does not match the route."
        raise ValueError(message)
    return resolved


def _examples(
    raw_examples: list[object],
    routes: list[Route],
    query_parameters: tuple[ParameterDoc, ...],
    parameters: RouteParameters | None,
    diagnostics: list[str],
    *,
    uses_format_query: bool,
) -> list[ExampleLinks]:
    required = {parameter.name for parameter in query_parameters if parameter.required}
    allowed = {parameter.name for parameter in query_parameters} | QueryString.model_fields.keys()
    examples = []
    for index, raw in enumerate(raw_examples, start=1):
        try:
            example = RouteExample.model_validate(raw)
        except ValidationError:
            diagnostics.append(f"Invalid route documentation example {index}.")
            continue
        if not required <= example.query.keys() <= allowed:
            diagnostics.append(f"route documentation example {index} has invalid query fields.")
            continue
        try:
            path = _example_path(routes[-1], example.path)
            _, scope = routes[-1].matches({"type": "http", "path": path, "method": "GET"})
            if parameters is not None:
                parameters.bind(scope["path_params"], example.query)
            compile_filters(QueryString.model_validate(example.query))
            if uses_format_query:
                rss = quote(path[1:], safe="/")
                atom = f"{rss}?{urlencode({**example.query, 'format': 'atom'})}"
                if example.query:
                    rss = f"{rss}?{urlencode(example.query)}"
            else:
                atom_route, rss_route, _ = routes
                query = f"?{urlencode(example.query)}" if example.query else ""
                rss = quote(_example_path(rss_route, example.path)[1:], safe="/") + query
                atom = quote(_example_path(atom_route, example.path)[1:], safe="/") + query
        except ProviderInputError as exception:
            diagnostics.append(f"route documentation example {index}: {exception}.")
            continue
        except AssertionError, NoMatchFound, TypeError, ValueError:
            diagnostics.append(f"route documentation example {index} does not match the route or its filters.")
            continue
        examples.append(ExampleLinks(example.label, rss, atom))
    return examples


def document_feed(
    routes: list[Route],
    provider: ProviderFn,
    metadata: object,
    uses_format_query: bool,
    typed: RouteParameters | None = None,
) -> FeedRouteGroup:
    route = routes[-1]
    diagnostics: list[str] = []
    try:
        spec = RouteDoc.model_validate(metadata) if metadata is not None else None
    except ValidationError:
        diagnostics.append("Invalid route documentation.")
        spec = None

    descriptions = spec.parameters if spec else {}
    if typed is None:
        try:
            parameters = dict(provider_signature(provider).parameters)
        except TypeError, ValueError:
            diagnostics.append("Cannot read provider signature.")
            parameters = {}
        for name, parameter in parameters.items():
            if parameter.kind is Parameter.POSITIONAL_ONLY:
                diagnostics.append(f"Positional-only provider parameter {name!r} cannot be bound.")
            if (
                uses_format_query
                and name == "format"
                and name not in route.param_convertors
                and parameter.default is Parameter.empty
            ):
                diagnostics.append("Required provider parameter 'format' is reserved on this route.")
        path_parameters = tuple(
            ParameterDoc(name, True, _CONVERTOR_LABELS.get(type(convertor)), descriptions.get(name))
            for name, convertor in route.param_convertors.items()
        )
        query_parameters = tuple(
            ParameterDoc(name, parameter.default is Parameter.empty, None, descriptions.get(name))
            for name, parameter in parameters.items()
            if parameter.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
            and name not in route.param_convertors
            and not (uses_format_query and name == "format")
        )
    else:
        typed_docs = {}
        for name, field in typed.model.model_fields.items():
            schema = typed.schemas[name]
            default = (
                dumps(schema["default"], ensure_ascii=False)
                if (schema.get("document_default") is True and "default" in schema)
                else None
            )
            typed_docs[name] = ParameterDoc(
                name,
                name in route.param_convertors or field.is_required(),
                typed.type_label(name),
                descriptions.get(name, field.description),
                default,
            )
        path_parameters = tuple(typed_docs[name] for name in route.param_convertors)
        query_parameters = tuple(doc for name, doc in typed_docs.items() if name not in route.param_convertors)
    for name in sorted(descriptions.keys() - {parameter.name for parameter in (*path_parameters, *query_parameters)}):
        diagnostics.append(f"Unknown documented parameter {name!r}.")

    examples = (
        _examples(spec.examples, routes, query_parameters, typed, diagnostics, uses_format_query=uses_format_query)
        if spec
        else []
    )
    return FeedRouteGroup(
        routes=routes,
        uses_format_query=uses_format_query,
        summary=spec.summary if spec else None,
        description=spec.description if spec else getdoc(provider),
        path_parameters=path_parameters,
        query_parameters=query_parameters,
        examples=examples,
        diagnostics=diagnostics,
    )
