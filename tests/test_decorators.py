import asyncio
from typing import Any

import pytest
from aiolimiter import AsyncLimiter
from cachetools import TTLCache

from akeylimiter import rate_limited, rate_limited_method


class TestRateLimited:
    async def test_calls(self):
        store = {}

        @rate_limited(max_rate=10, time_period=1, store=store)
        async def fetch(value: str) -> str:
            return value

        assert await fetch("hello") == "hello"

    async def test_reuses_limiter(self):
        store = {}

        @rate_limited(max_rate=10, time_period=1, store=store)
        async def fetch(key: str) -> str:
            return key

        await fetch("key-1")
        limiter = store[("key-1",)]
        await fetch("key-1")

        assert len(store) == 1
        assert store[("key-1",)] is limiter

    async def test_separates_keys(self):
        store = {}

        @rate_limited(max_rate=10, time_period=1, store=store)
        async def fetch(key: str) -> str:
            return key

        await fetch("key-1")
        await fetch("key-2")

        assert len(store) == 2
        assert store[("key-1",)] is not store[("key-2",)]

    async def test_custom_key(self):
        store = {}

        @rate_limited(
            max_rate=10,
            time_period=1,
            store=store,
            key=lambda user_id, value: user_id,
        )
        async def fetch(user_id: str, value: str) -> str:
            return value

        await fetch("user-1", "hello")
        await fetch("user-1", "world")
        await fetch("user-2", "hello")

        assert len(store) == 2
        assert "user-1" in store
        assert "user-2" in store

    async def test_custom_store(self):
        store = TTLCache(maxsize=100, ttl=60)

        @rate_limited(max_rate=10, time_period=1, store=store, key=lambda key: key)
        async def fetch(key: str) -> str:
            return key

        await fetch("key-1")

        assert "key-1" in store
        assert isinstance(store["key-1"], AsyncLimiter)

    async def test_metadata(self):
        store = {}

        @rate_limited(max_rate=10, time_period=1, store=store)
        async def fetch(value: str) -> str:
            """Fetch a value."""
            return value

        assert fetch.__name__ == "fetch"
        assert fetch.__doc__ == "Fetch a value."

    def test_invalid_max_rate(self):
        with pytest.raises(
            ValueError,
            match="max_rate and time_period must be greater than 0",
        ):
            rate_limited(max_rate=0, time_period=1, store={})

    def test_invalid_time_period(self):
        with pytest.raises(
            ValueError,
            match="max_rate and time_period must be greater than 0",
        ):
            rate_limited(max_rate=1, time_period=0, store={})

    def test_sync_function(self):
        store = {}
        decorator = rate_limited(10, 1, store)

        def fetch() -> int:
            return 1

        with pytest.raises(TypeError, match="Expected coroutine function"):
            decorator(fetch)  # type: ignore[arg-type]

    async def test_rate_limits(self):
        store = {}

        @rate_limited(max_rate=2, time_period=1, store=store)
        async def fetch(key: str) -> str:
            return key

        await fetch("key-1")
        await fetch("key-1")
        start = asyncio.get_running_loop().time()
        await fetch("key-1")
        elapsed = asyncio.get_running_loop().time() - start

        assert elapsed >= 0.45

    async def test_separate_limits(self):
        store = {}

        @rate_limited(max_rate=1, time_period=1, store=store)
        async def fetch(key: str) -> str:
            return key

        await fetch("key-1")
        start = asyncio.get_running_loop().time()
        await fetch("key-2")
        elapsed = asyncio.get_running_loop().time() - start

        assert elapsed < 0.5

    async def test_concurrent_calls(self):
        store = {}

        @rate_limited(max_rate=1, time_period=1, store=store)
        async def fetch(key: str) -> str:
            return key

        start = asyncio.get_running_loop().time()
        await asyncio.gather(
            fetch("key-1"),
            fetch("key-1"),
        )
        elapsed = asyncio.get_running_loop().time() - start

        assert elapsed >= 0.9


class TestRateLimitedMethod:
    async def test_calls(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

            @rate_limited_method(
                max_rate=10,
                time_period=1,
                store_factory=lambda self: self.limiters,
            )
            async def generate(self, key: str) -> str:
                return key

        service = Service()

        assert await service.generate("key-1") == "key-1"

    async def test_reuses_limiter(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

            @rate_limited_method(
                max_rate=10,
                time_period=1,
                store_factory=lambda self: self.limiters,
            )
            async def generate(self, key: str) -> str:
                return key

        service = Service()

        await service.generate("key-1")
        limiter = service.limiters[("key-1",)]
        await service.generate("key-1")

        assert len(service.limiters) == 1
        assert service.limiters[("key-1",)] is limiter

    async def test_separates_keys(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

            @rate_limited_method(
                max_rate=10,
                time_period=1,
                store_factory=lambda self: self.limiters,
            )
            async def generate(self, key: str) -> str:
                return key

        service = Service()

        await service.generate("key-1")
        await service.generate("key-2")

        assert len(service.limiters) == 2
        assert ("key-1",) in service.limiters
        assert ("key-2",) in service.limiters
        assert service.limiters[("key-1",)] is not service.limiters[("key-2",)]

    async def test_separates_instances(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

            @rate_limited_method(
                max_rate=10,
                time_period=1,
                store_factory=lambda self: self.limiters,
            )
            async def generate(self, key: str) -> str:
                return key

        service1 = Service()
        service2 = Service()
        await service1.generate("key-1")
        await service2.generate("key-1")

        assert service1.limiters[("key-1",)] is not service2.limiters[("key-1",)]

    async def test_custom_key(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

            @rate_limited_method(
                max_rate=10,
                time_period=1,
                store_factory=lambda self: self.limiters,
                key=lambda self, key, value: key,
            )
            async def generate(self, key: str, value: str) -> str:
                return value

        service = Service()
        await service.generate("key-1", "hello")
        await service.generate("key-1", "world")
        await service.generate("key-2", "hello")

        assert len(service.limiters) == 2
        assert "key-1" in service.limiters
        assert "key-2" in service.limiters

    async def test_custom_key_kwargs(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

            @rate_limited_method(
                max_rate=10,
                time_period=1,
                store_factory=lambda self: self.limiters,
                key=lambda self, key, **_: key,
            )
            async def generate(self, key: str, *, value: str) -> str:
                return value

        service = Service()
        await service.generate("key-1", value="hello")
        await service.generate("key-1", value="world")

        assert len(service.limiters) == 1
        assert "key-1" in service.limiters

    async def test_metadata(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

            @rate_limited_method(
                max_rate=10,
                time_period=1,
                store_factory=lambda self: self.limiters,
            )
            async def generate(self, key: str) -> str:
                """Generate a value."""
                return key

        assert Service.generate.__name__ == "generate"
        assert Service.generate.__doc__ == "Generate a value."

    def test_sync_method(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

        def generate(self: Any, key: str) -> int:
            return 1

        decorator = rate_limited_method(
            max_rate=10,
            time_period=1,
            store_factory=lambda self: self.limiters,
        )

        with pytest.raises(TypeError, match="Expected coroutine function"):
            decorator(generate)  # type: ignore[arg-type]

    def test_invalid_max_rate(self):
        with pytest.raises(
            ValueError,
            match="max_rate and time_period must be greater than 0",
        ):
            rate_limited_method(
                max_rate=0,
                time_period=1,
                store_factory=lambda self: self.limiters,
            )

    def test_invalid_time_period(self):
        with pytest.raises(
            ValueError,
            match="max_rate and time_period must be greater than 0",
        ):
            rate_limited_method(
                max_rate=1,
                time_period=0,
                store_factory=lambda self: self.limiters,
            )

    async def test_rate_limits(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

            @rate_limited_method(
                max_rate=2,
                time_period=1,
                store_factory=lambda self: self.limiters,
            )
            async def generate(self, key: str) -> str:
                return key

        service = Service()
        await service.generate("key-1")
        await service.generate("key-1")
        start = asyncio.get_running_loop().time()
        await service.generate("key-1")
        elapsed = asyncio.get_running_loop().time() - start

        assert elapsed >= 0.45

    async def test_separate_limits(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

            @rate_limited_method(
                max_rate=1,
                time_period=1,
                store_factory=lambda self: self.limiters,
            )
            async def generate(self, key: str) -> str:
                return key

        service = Service()
        await service.generate("key-1")
        start = asyncio.get_running_loop().time()
        await service.generate("key-2")
        elapsed = asyncio.get_running_loop().time() - start

        assert elapsed < 0.5

    async def test_concurrent_calls(self):
        class Service:
            def __init__(self) -> None:
                self.limiters = {}

            @rate_limited_method(
                max_rate=1,
                time_period=1,
                store_factory=lambda self: self.limiters,
            )
            async def generate(self, key: str) -> str:
                return key

        service = Service()
        start = asyncio.get_running_loop().time()
        await asyncio.gather(
            service.generate("key-1"),
            service.generate("key-1"),
        )
        elapsed = asyncio.get_running_loop().time() - start

        assert elapsed >= 0.9
