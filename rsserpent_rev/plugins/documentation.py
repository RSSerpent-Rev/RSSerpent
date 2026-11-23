from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from inspect import Parameter, getdoc, signature, unwrap
from types import FunctionType, MethodType
from urllib.parse import quote, urlencode

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.convertors import FloatConvertor, IntegerConvertor, PathConvertor, UUIDConvertor
from starlette.routing import NoMatchFound, Route

from ..log import logger
from ..models import ProviderFn, QueryString

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


def _without_annotations(provider: Callable[..., object]) -> Callable[..., object]:
    target = unwrap(provider, stop=lambda value: isinstance(value, (partial, MethodType)))
    if isinstance(target, partial):
        return partial(_without_annotations(target.func), *target.args, **target.keywords)
    if isinstance(target, MethodType):
        return MethodType(_without_annotations(target.__func__), target.__self__)
    if not isinstance(target, FunctionType):
        message = "Provider has no Python function signature."
        raise TypeError(message)

    # Even inspect.signature's string format can execute a delayed annotation.
    function = FunctionType(target.__code__, target.__globals__, None, target.__defaults__, target.__closure__)
    function.__kwdefaults__ = target.__kwdefaults__
    return function


def _example_path(route: Route, path: dict[str, str]) -> str:
    # A converter can generate a string that its own route will not match.
    resolved = str(route.url_path_for(route.name, **path))
    if not route.path_regex.fullmatch(resolved) or {".", ".."}.intersection(resolved.split("/")):
        message = "The example does not match the route."
        raise ValueError(message)
    return quote(resolved[1:], safe="/")


def _examples(
    raw_examples: list[object],
    routes: list[Route],
    query_parameters: tuple[ParameterDoc, ...],
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
            logger.warning("Ignoring invalid route documentation example %d for %s", index, routes[-1].path)
            continue
        if not required <= example.query.keys() <= allowed:
            logger.warning(
                "Ignoring route documentation example %d with invalid query fields for %s", index, routes[-1].path
            )
            continue
        try:
            if uses_format_query:
                rss = _example_path(routes[0], example.path)
                atom = f"{rss}?{urlencode({**example.query, 'format': 'atom'})}"
                if example.query:
                    rss = f"{rss}?{urlencode(example.query)}"
            else:
                atom_route, rss_route, _ = routes
                query = f"?{urlencode(example.query)}" if example.query else ""
                rss = _example_path(rss_route, example.path) + query
                atom = _example_path(atom_route, example.path) + query
        except AssertionError, NoMatchFound, TypeError, ValueError:
            logger.warning("Ignoring route documentation example %d for %s", index, routes[-1].path)
            continue
        examples.append(ExampleLinks(example.label, rss, atom))
    return examples


def document_feed(
    routes: list[Route], provider: ProviderFn, metadata: object, uses_format_query: bool
) -> FeedRouteGroup:
    route = routes[-1]
    try:
        spec = RouteDoc.model_validate(metadata) if metadata is not None else None
    except ValidationError:
        logger.warning("Ignoring invalid route documentation for %s", route.path)
        spec = None

    try:
        parameters = {
            name: parameter
            for name, parameter in signature(_without_annotations(provider)).parameters.items()
            if parameter.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
        }
    except TypeError, ValueError:
        logger.warning("Cannot read provider signature for %s", route.path)
        parameters = {}

    descriptions = spec.parameters if spec else {}
    path_parameters = tuple(
        ParameterDoc(
            name,
            True,
            _CONVERTOR_LABELS.get(type(convertor)),
            descriptions.get(name),
        )
        for name, convertor in route.param_convertors.items()
    )
    query_parameters = tuple(
        ParameterDoc(name, parameter.default is Parameter.empty, None, descriptions.get(name))
        for name, parameter in parameters.items()
        if name not in route.param_convertors and not (uses_format_query and name == "format")
    )
    for name in descriptions.keys() - {parameter.name for parameter in (*path_parameters, *query_parameters)}:
        logger.warning("Ignoring documentation for unknown parameter %s in %s", name, route.path)

    examples = _examples(spec.examples, routes, query_parameters, uses_format_query=uses_format_query) if spec else []
    return FeedRouteGroup(
        routes=routes,
        uses_format_query=uses_format_query,
        summary=spec.summary if spec else None,
        description=spec.description if spec else getdoc(provider),
        path_parameters=path_parameters,
        query_parameters=query_parameters,
        examples=examples,
    )
