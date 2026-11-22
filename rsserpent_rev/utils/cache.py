import asyncio
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial, wraps
from typing import (
    Any,
    TypeVar,
    cast,
    overload,
)

__all__ = ("cached",)

CACHE_EXPIRE = int(os.environ.get("CACHE_EXPIRE", 60 * 60))
DEFAULT_CACHE_SIZE = 256

AsyncFn = TypeVar("AsyncFn", bound=Callable[..., Awaitable[Any]])


class CacheKey:
    """Hashed function parameters that could be used as dictionary keys.

    This module provides `@cached` & `@cached_with` decorators for caching function
    results. Cache exists as key-value pairs. The parameters of each function
    invocation are converted to a tuple and then hashed, so that results of different
    function invocations (e.g. `fn(1)` & `fn(2)`) could be differentiated and
    separately cached.

    Attributes:
        hashvalue: The hashed value of function parameters.
    """

    __sentinel__ = object()
    __slots__ = ("arguments", "hashvalue")

    def __init__(self, key: tuple[Any, ...]) -> None:
        self.arguments = key
        self.hashvalue = hash(key)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CacheKey):
            raise NotImplementedError()
        return self.arguments == other.arguments

    def __hash__(self) -> int:
        return self.hashvalue

    @classmethod
    def make(cls, args: tuple[Any, ...], kwds: dict[str, Any]) -> CacheKey:
        """Create a `CacheKey` instance from any function parameters.

        Args:
            args: Positional arguments in function parameters.
            kwds: Keyword arguments in function parameters.

        Returns:
            The created `CacheKey` instance.
        """
        key = []
        # positional arguments
        for argument in args:
            key.append(argument)
            key.append(type(argument))
        # keyword arguments
        if kwds:
            key.append(cls.__sentinel__)
            for name, argument in sorted(kwds.items()):
                key.append(name)
                key.append(argument)
                key.append(type(argument))
        return CacheKey(tuple(key))


@dataclass
class CacheValue:
    """Cached function results with a expiring timestamp."""

    expired: float
    data: Any


class LRUCache(OrderedDict):  # type: ignore[type-arg]
    """Least Recently Used (LRU) cache.

    Attributes:
        hits: The number of cache hits.
        maxsize: The maximum capacity of the LRU cache.
        misses: The number of cache misses.
    """

    def __init__(self, maxsize: int) -> None:
        self.maxsize = maxsize if maxsize > 0 else float("inf")
        self.hits, self.misses = 0, 0
        self.lock = threading.RLock()
        super().__init__()

    def __getitem__(self, key: CacheKey) -> CacheValue | None:
        """Get cache value by key.

        In case of cache miss / expire, `None` is returned. Otherwise the cached value
        is returned and moved to the end of the list.
        """
        with self.lock:
            if key not in self:
                return None
            value: CacheValue = super().__getitem__(key)
            if value.expired <= time.monotonic():
                del self[key]
                return None
            self.move_to_end(key)
            self.hits += 1
            return value

    def __setitem__(self, key: CacheKey, value: CacheValue) -> None:
        """Set a cache (key, value) pair.

        The `__setitem__` is called only when a cache miss / expire happens. In case of
        cache expire, the existing `key` must be moved to the end of the list. In case
        cache maximum capacity is reached, the first (thus least recently used) cache
        item is deleted.
        """
        with self.lock:
            now = time.monotonic()
            self.misses += 1
            if value.expired <= now:
                return
            if len(self) >= self.maxsize:
                for old_key in [old_key for old_key, old_value in self.items() if old_value.expired <= now]:
                    del self[old_key]
            if key in self:
                self.move_to_end(key)
            super().__setitem__(key, value)
            if len(self) > self.maxsize:
                # do not use `self.popitem`
                del self[next(iter(self))]

    def clear(self) -> None:
        with self.lock:
            super().clear()

    @property
    def size(self) -> int:
        """Return the current size of the cache."""
        return super().__len__()


def decorator[AsyncFn: Callable[..., Awaitable[Any]]](fn: AsyncFn, *, expire: int, maxsize: int) -> AsyncFn:
    """Cache decorator."""
    cache = LRUCache(maxsize=maxsize)
    pending: dict[tuple[asyncio.AbstractEventLoop, CacheKey], asyncio.Task[Any]] = {}

    async def load(key: CacheKey, args: tuple[Any, ...], kwds: dict[str, Any]) -> Any:
        result = await fn(*args, **kwds)
        cache[key] = CacheValue(expired=time.monotonic() + expire, data=result)
        return result

    @wraps(fn)
    async def wrapper(*args: Any, **kwds: Any) -> Any:
        """Wrap the original async `fn`.

        Cached results will be returned if cache hit, otherwise
        (missing/expired) `fn` will be invoked and its result will be cached.

        Args:
            args: Positional arguments in function parameters.
            kwds: Keyword arguments in function parameters.

        Returns:
            The (maybe cached) result of `fn(*args, **kwds)`.
        """
        key = CacheKey.make(args, kwds)
        pending_key = (asyncio.get_running_loop(), key)

        def discard(task: asyncio.Task[Any]) -> None:
            with cache.lock:
                if pending.get(pending_key) is task:
                    del pending[pending_key]
            if not task.cancelled():
                task.exception()

        with cache.lock:
            value = cache[key]
            if value is not None:
                return value.data
            task = pending.get(pending_key)
            if task is None or task.done():
                task = asyncio.create_task(load(key, args, kwds))
                pending[pending_key] = task
                task.add_done_callback(discard)
        return await asyncio.shield(task)

    wrapper.__dict__["cache"] = cache
    wrapper.__dict__["expire"] = expire
    return cast(AsyncFn, wrapper)


@overload
def cached[AsyncFn: Callable[..., Awaitable[Any]]](fn: AsyncFn) -> AsyncFn: ...  # pragma: no cover


@overload
def cached(
    *, expire: int = CACHE_EXPIRE, maxsize: int = DEFAULT_CACHE_SIZE
) -> Callable[[AsyncFn], AsyncFn]: ...  # pragma: no cover


def cached[AsyncFn: Callable[..., Awaitable[Any]]](
    fn: AsyncFn | None = None, *, expire: int = CACHE_EXPIRE, maxsize: int = DEFAULT_CACHE_SIZE
) -> AsyncFn | Callable[[AsyncFn], AsyncFn]:
    """Cache function results."""
    if fn is not None:
        return decorator(fn, expire=expire, maxsize=maxsize)
    return partial(decorator, expire=expire, maxsize=maxsize)


def get_cache[AsyncFn: Callable[..., Awaitable[Any]]](fn: AsyncFn) -> LRUCache | None:
    return fn.__dict__.get("cache")
