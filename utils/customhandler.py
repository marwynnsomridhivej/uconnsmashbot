import functools
from typing import Tuple
from inspect import iscoroutine, iscoroutinefunction


__all__ = (
    "handle",
)


def handle(*exceptions: Tuple[Exception], to_raise: Exception = None):
    def actual_deco(func):
        @functools.wraps(func)
        async def handler(*args, **kwargs):
            if not (iscoroutine(func) or iscoroutinefunction(func)):
                raise TypeError("Function must be an async function defined using the async def syntax")
            try:
                return await func(*args, **kwargs)
            except (exceptions):
                if to_raise:
                    raise to_raise
        return handler
    return actual_deco