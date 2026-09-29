from collections.abc import Callable, Coroutine, MutableMapping
from functools import update_wrapper
from inspect import iscoroutinefunction
from typing import Any, Concatenate, ParamSpec, TypeVar

from aiolimiter import AsyncLimiter
from cachetools.keys import hashkey, methodkey

P = ParamSpec("P")
R = TypeVar("R")


def _get_limiter(
    store: MutableMapping[Any, Any],
    key: Any,
    max_rate: float,
    time_period: float,
) -> AsyncLimiter:
    limiter = store.get(key)

    if limiter is None:
        limiter = AsyncLimiter(max_rate, time_period)
        store[key] = limiter

    return limiter


def rate_limited(
    max_rate: float,
    time_period: float,
    store: MutableMapping[Any, Any],
    *,
    key: Callable[..., Any] = hashkey,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]],
    Callable[P, Coroutine[Any, Any, R]],
]:
    """Rate-limit an async function independently per key using aiolimiter."""
    if max_rate <= 0 or time_period <= 0:
        raise ValueError("max_rate and time_period must be greater than 0")

    def decorator(
        fn: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        if not iscoroutinefunction(fn):
            raise TypeError(f"Expected coroutine function, got {fn!r}")

        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            limiter_key = key(*args, **kwargs)
            limiter = _get_limiter(store, limiter_key, max_rate, time_period)
            async with limiter:
                return await fn(*args, **kwargs)

        return update_wrapper(wrapper, fn)

    return decorator


def rate_limited_method(
    max_rate: float,
    time_period: float,
    store_factory: Callable[[Any], MutableMapping[Any, Any]],
    *,
    key: Callable[..., Any] = methodkey,
) -> Callable[
    [Callable[Concatenate[Any, P], Coroutine[Any, Any, R]]],
    Callable[Concatenate[Any, P], Coroutine[Any, Any, R]],
]:
    """Rate-limit an async class method independently per instance/key."""
    if max_rate <= 0 or time_period <= 0:
        raise ValueError("max_rate and time_period must be greater than 0")

    def decorator(
        method: Callable[Concatenate[Any, P], Coroutine[Any, Any, R]],
    ) -> Callable[Concatenate[Any, P], Coroutine[Any, Any, R]]:
        if not iscoroutinefunction(method):
            raise TypeError(f"Expected coroutine function, got {method!r}")

        async def wrapper(self: Any, *args: P.args, **kwargs: P.kwargs) -> R:
            store = store_factory(self)
            limiter_key = key(self, *args, **kwargs)
            limiter = _get_limiter(store, limiter_key, max_rate, time_period)

            async with limiter:
                return await method(self, *args, **kwargs)

        return update_wrapper(wrapper, method)

    return decorator
