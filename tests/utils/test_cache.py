import asyncio
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    DataObject,
    booleans,
    data,
    dictionaries,
    floats,
    integers,
    lists,
    text,
)

import rsserpent_rev.utils.cache as cache_module
from rsserpent_rev.utils.cache import CacheKey, cached, get_cache
from tests.conftest import Times

primitive = booleans() | floats() | integers() | text()


class TestCacheKey:
    """Test the `CacheKey` class."""

    @settings(max_examples=Times.THOROUGH)
    @given(
        args=lists(primitive).map(tuple),
        kwds=dictionaries(text(), primitive),
    )
    def test(self, args: tuple[Any, ...], kwds: dict[str, Any]) -> None:
        """Test if the `CacheKey` class works properly.

        * `make`, `__eq__`, `__hash__`, `__init__`
        """
        key1 = CacheKey.make(args, kwds)
        key2 = CacheKey.make(args, kwds)
        key3 = CacheKey.make(args + (0,), kwds)
        assert key1 == key2
        assert key1 != key3
        with pytest.raises(NotImplementedError):
            assert key1 == object()


@settings(max_examples=Times.SOME)
@given(n=integers(min_value=2, max_value=100))
async def test_cached(n: int) -> None:
    """Test if `@cached` decorator works properly."""

    @cached
    async def fib(n: int) -> int:
        return n if n < 2 else await fib(n - 1) + await fib(n - 2)

    assert await fib(n) == await fib(n - 1) + await fib(n - 2)

    cache = get_cache(fib)
    assert cache is not None
    assert cache.hits == n
    assert cache.size == n + 1
    assert cache.misses == n + 1


def test_cache_key_keeps_keyword_names_and_values() -> None:
    assert CacheKey.make((), {"first": 1}) != CacheKey.make((), {"second": 1})
    assert CacheKey.make((-1,), {}) != CacheKey.make((-2,), {})


async def test_default_capacity_and_expiration(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 0.0
    monkeypatch.setattr(cache_module, "time", type("Clock", (), {"monotonic": lambda: now}))

    @cached
    async def load(i: int) -> int:
        return i

    for i in range(300):
        await load(i)
    cache = get_cache(load)
    assert cache is not None
    assert cache.size == 256
    now = 3601
    await load(300)
    assert cache.size == 1


async def test_concurrent_waiter_cancellation() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    @cached
    async def load(value: str) -> str:
        nonlocal calls
        if value == "same":
            calls += 1
            entered.set()
            await release.wait()
        return value

    first = asyncio.create_task(load("same"))
    await entered.wait()
    second = asyncio.create_task(load("same"))
    assert await load("other") == "other"
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    release.set()
    assert await second == "same"
    assert calls == 1


async def test_failed_load_can_retry() -> None:
    calls = 0

    @cached
    async def load() -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError
        return calls

    with pytest.raises(ValueError):
        await load()
    assert await load() == 2


@settings(max_examples=Times.ONCE)
@given(n=integers(min_value=2, max_value=10), expire=integers(max_value=-1))
async def test_cached_with_expire(n: int, expire: int) -> None:
    """Test if `@cached` decorator works properly, given parameter `expire`."""

    @cached(expire=expire)
    async def fib(n: int) -> int:
        return n if n < 2 else await fib(n - 1) + await fib(n - 2)

    assert await fib(n) == await fib(n - 1) + await fib(n - 2)

    cache = get_cache(fib)
    assert cache is not None
    assert cache.hits == 0


@settings(max_examples=Times.SOME)
@given(data())
async def test_cached_with_maxsize(data: DataObject) -> None:
    """Test if `@cached` decorator works properly, given parameter `maxsize`."""
    n = data.draw(integers(min_value=2, max_value=10))

    # cache size too small
    maxsize = data.draw(integers(min_value=1, max_value=n))

    @cached(maxsize=maxsize)
    async def fib1(n: int) -> int:
        return n if n < 2 else await fib1(n - 1) + await fib1(n - 2)

    assert await fib1(n) == await fib1(n - 1) + await fib1(n - 2)

    cache = get_cache(fib1)
    assert cache is not None
    assert cache.size == maxsize

    # cache size suffice
    maxsize = data.draw(integers(max_value=0) | integers(min_value=n + 1))

    @cached(maxsize=maxsize)
    async def fib2(n: int) -> int:
        return n if n < 2 else await fib2(n - 1) + await fib2(n - 2)

    assert await fib2(n) == await fib2(n - 1) + await fib2(n - 2)

    cache = get_cache(fib2)
    assert cache is not None
    assert cache.size == n + 1
