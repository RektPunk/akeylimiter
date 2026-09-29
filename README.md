<div style="text-align: center;">
  <img src="https://capsule-render.vercel.app/api?type=transparent&fontColor=0047AB&text=akeylimiter&height=120&fontSize=90">
</div>

**akeylimiter** provides key-based async rate limiting built on [`aiolimiter`](https://github.com/mjpieters/aiolimiter). Each key gets its own limiter, allowing independent rate limits for different users, API keys, or other identifiers.

## Installation

```bash
pip install akeylimiter
```

## Usage

### `rate_limited`

Use `rate_limited` to apply an independent rate limit for each key. By default, all function arguments determine the rate limit key. Use `key` to select which arguments determine the rate limit.

```python
from akeylimiter import rate_limited
from cachetools import TTLCache

store = TTLCache(maxsize=1024, ttl=600)


@rate_limited(
    max_rate=10,
    time_period=1,
    store=store,
    key=lambda user_id, prompt: user_id,
)
async def generate(user_id: str, prompt: str): ...
```

Here, all requests from the same `user_id` share a limiter, while different users get independent limiters.

```text
generate("user-1", "hello")  ─┐
generate("user-1", "world")  ─┼─ same limiter
generate("user-1", "python") ─┘

generate("user-2", "hello")  ─── different limiter
```

The limiter store can be any `MutableMapping`, such as a regular dictionary or a `cachetools` cache like `TTLCache` or `LRUCache`.

Using a [`cachetools`](https://github.com/tkem/cachetools) cache is useful when the number of keys can grow over time. Since each key creates a limiter, a regular dictionary keeps every limiter until it is explicitly removed. Caches such as `TTLCache` and `LRUCache` can automatically evict limiters based on expiration or cache capacity.

### `rate_limited_method`

Use `rate_limited_method` when the limiter store belongs to a class instance.

```python
from akeylimiter import rate_limited_method
from cachetools import LRUCache


class APIClient:
    def __init__(self):
        self.limiters = LRUCache(maxsize=1024)

    @rate_limited_method(
        max_rate=10,
        time_period=1,
        store_factory=lambda self: self.limiters,
        key=lambda self, api_key, endpoint, params: api_key,
    )
    async def fetch(
        self,
        api_key: str,
        endpoint: str,
        params: dict[str, object],
    ): ...
```

Each instance maintains its own limiter store.

```text
client.fetch("key-1", "/users", ...)    ─┐
client.fetch("key-1", "/posts", ...)    ─┼─ same limiter
client.fetch("key-1", "/comments", ...) ─┘

client.fetch("key-2", "/users", ...)  ───── different limiter
```

The two clients have independent rate limits, even when they use the same `api_key`.
