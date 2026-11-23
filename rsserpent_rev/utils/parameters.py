from typing import Any

from pydantic import ValidationError
from starlette.routing import Route

from ..models import FeedRoute
from .provider import ProviderInputError, provider_signature

_SCALAR_LABELS = {"boolean": "boolean", "integer": "integer", "number": "number", "string": "string"}


def _scalar_schemas(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return [branch for branch in schema.get("anyOf", [schema]) if branch.get("type") != "null"]


def _literal_values(schema: dict[str, Any]) -> list[object]:
    if "const" in schema:
        return [schema["const"]]
    return list(schema.get("enum", []))


def _url_literal(value: object) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


class RouteParameters:
    """Compile a URL parameter model once for binding and documentation."""

    def __init__(self, declaration: FeedRoute, route: Route, *, uses_format_query: bool) -> None:
        self.model = declaration.parameters
        fields = self.model.model_fields
        if unknown := set(route.param_convertors) - fields.keys():
            message = f"Path parameters missing from model: {', '.join(sorted(unknown))}."
            raise ValueError(message)
        if uses_format_query and "format" in fields:
            message = "The format query parameter is reserved on catch-all routes."
            raise ValueError(message)
        provider_signature(declaration.provider).bind(**dict.fromkeys(fields))
        properties = self.model.model_json_schema(by_alias=False).get("properties", {})
        self.schemas: dict[str, dict[str, Any]] = {}
        self.literals: dict[str, dict[str, object]] = {}
        for name in fields:
            field_schema = properties.get(name, {})
            branches = _scalar_schemas(field_schema)
            if not branches or any(
                branch.get("type") not in _SCALAR_LABELS
                and (
                    not _literal_values(branch)
                    or not all(type(value) in (str, int, float, bool) for value in _literal_values(branch))
                )
                for branch in branches
            ):
                message = f"Parameter {name!r} must declare a URL scalar or Literal."
                raise ValueError(message)
            self.schemas[name] = field_schema
            values = [value for branch in branches for value in _literal_values(branch)]
            if values:
                # If strings and numbers share a spelling, pass the literal string.
                self.literals[name] = {
                    _url_literal(value): value for value in sorted(values, key=lambda value: isinstance(value, str))
                }

    def bind(self, path: dict[str, Any], query: dict[str, str]) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        for name in self.schemas:
            if name in path:
                value = path[name]
            elif name in query:
                value = query[name]
            else:
                continue
            if isinstance(value, str) and name in self.literals:
                value = self.literals[name].get(value, value)
            raw[name] = value
        try:
            model = self.model.model_validate(raw, by_alias=False, by_name=True)
        except ValidationError as exception:
            error = exception.errors(include_input=False, include_context=False, include_url=False)[0]
            name = str(error["loc"][0]) if error["loc"] else "query"
            raise ProviderInputError(name, missing=error["type"] == "missing") from None
        return {name: getattr(model, name) for name in self.schemas}

    def type_label(self, name: str) -> str:
        labels = []
        for schema in _scalar_schemas(self.schemas[name]):
            if values := _literal_values(schema):
                labels.append(" / ".join(_url_literal(value) for value in values))
            else:
                labels.append(schema.get("format") or _SCALAR_LABELS[schema["type"]])
            for key, operator in (
                ("minimum", ">="),
                ("exclusiveMinimum", ">"),
                ("maximum", "<="),
                ("exclusiveMaximum", "<"),
            ):
                if key in schema:
                    labels.append(f"{operator} {schema[key]}")
        return ", ".join(labels)
