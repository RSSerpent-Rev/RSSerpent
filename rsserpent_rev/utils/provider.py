import inspect
from annotationlib import Format
from collections.abc import Callable
from contextvars import ContextVar
from functools import partial
from inspect import Parameter, Signature, getattr_static, signature, unwrap
from types import FunctionType, MethodType
from typing import Any

from ..models import FeedResult, ProviderFn

provider_resource = ContextVar[object | None]("provider_resource", default=None)


class ProviderInputError(ValueError):
    """A required provider parameter is missing or has an invalid value."""

    def __init__(self, name: str, *, missing: bool = False) -> None:
        super().__init__(f"{'Missing' if missing else 'Invalid'} parameter: {name}")


def convert(value: str, type_: type) -> Any:
    """Convert string `value` to type `type_`."""
    if type_ is bool:
        return value.lower() in ("1", "t", "true", "y", "yes")
    return type_(value)


async def fetch_data(provider: ProviderFn, path_params: dict[str, Any], query_params: dict[str, str]) -> FeedResult:
    """Fetch data by using the data provider function.

    We first inspect the signature of the `provider` function to determine what
    parameters it needs. We then find values for these parameters from `path_params` &
    `query_params`. Finally we invoke `provider(**kwds)` and return the fetched data.

    Args:
        provider: The data provider function.
        path_params: `request.path_params`, arguments parsed from the route path.
        query_params: `request.query_params`, arguments parsed from the query string,
            but deduplicated.

    Returns:
        The data fetched by the `provider` function.

    Raises:
        NotImplementedError: do not use positional-only arguments in `provider`.
    """
    kwds = {}
    signature = inspect.signature(provider, eval_str=True, annotation_format=Format.VALUE)
    for parameter in signature.parameters.values():
        # ignore `*args` & `**kwds` arguments
        if parameter.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
            continue
        try:
            parameter_value = look_up_parameter_value(parameter, path_params, query_params)
        except ValueError as exception:
            raise ProviderInputError(parameter.name) from exception
        if parameter_value is None:
            if parameter.default is Parameter.empty:
                raise ProviderInputError(parameter.name, missing=True)
            continue
        # handle positional-or-keyword & keyword-only arguments
        elif parameter.kind in (
            Parameter.POSITIONAL_OR_KEYWORD,
            Parameter.KEYWORD_ONLY,
        ):
            kwds[parameter.name] = parameter_value
        # do not use positional-only arguments
        # TODO: document this behavior
        else:
            raise NotImplementedError()  # pragma: no cover
    return await provider(**kwds)


def look_up_parameter_value(parameter: Parameter, path_params: dict[str, Any], query_params: dict[str, str]) -> Any:
    """Look up value for a specific parameter from `path_params` & `query_params`.

    Args:
        parameter: A parameter of some data provider function (`ProviderFn`).
        path_params: `request.path_params`, arguments parsed from the route.
        query_params: `request.query_params`, arguments parsed from the query string,
            but deduplicated.

    Returns:
        The value for the parameter, `None` if not found.
    """
    value = None
    # look for `parameter.name` in `path_params`
    if parameter.name in path_params:
        value = path_params[parameter.name]
        if isinstance(value, str):
            value = convert(value, parameter.annotation)
    # looking for `parameter.name` in `query_params`
    elif parameter.name in query_params:
        value = convert(query_params[parameter.name], parameter.annotation)
    return value


_NO_SIGNATURE = object()


def _without_annotations(provider: Callable[..., object]) -> Callable[..., object]:
    target = unwrap(
        provider,
        stop=lambda value: (
            isinstance(value, MethodType) or getattr_static(value, "__signature__", _NO_SIGNATURE) is not _NO_SIGNATURE
        ),
    )
    if isinstance(target, MethodType):
        return MethodType(_without_annotations(target.__func__), target.__self__)

    declared = getattr_static(target, "__signature__", _NO_SIGNATURE)
    if isinstance(declared, Signature):

        def placeholder() -> None:
            pass

        placeholder.__dict__["__signature__"] = declared.replace(
            parameters=[parameter.replace(annotation=Parameter.empty) for parameter in declared.parameters.values()],
            return_annotation=Signature.empty,
        )
        return placeholder
    if declared is not _NO_SIGNATURE and declared is not None:
        message = "Provider has no static signature."
        raise TypeError(message)
    if isinstance(target, partial):
        return partial(_without_annotations(target.func), *target.args, **target.keywords)
    if not isinstance(target, FunctionType):
        message = "Provider has no Python function signature."
        raise TypeError(message)

    # Even inspect.signature's string format can execute a delayed annotation.
    function = FunctionType(target.__code__, target.__globals__, None, target.__defaults__, target.__closure__)
    function.__kwdefaults__ = target.__kwdefaults__
    return function


def provider_signature(provider: Callable[..., object]) -> Signature:
    return signature(_without_annotations(provider))
