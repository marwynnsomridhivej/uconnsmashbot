from operator import attrgetter
from typing import Any, Iterable, List, Union


__all__ = (
    "extract",
    "extract_attr",
    "extract_all_attr",
)


def extract(iterable: Iterable, iter_in: List, *args,
            func: str = None, default: Any = None, **kwargs) -> Union[str, None]:
    for item in iterable:
        if not func:
            if item in iter_in:
                return item
        else:
            modif_func = getattr(item, func)
            if modif_func(*args, **kwargs) in iter_in:
                return item
    return default


def extract_attr(iterable: Iterable, mode: str = "all", **attrs) -> Union[Any, None]:
    allattrs = [(attrgetter(k), v) for k, v in attrs.items()]
    for item in iterable:
        if mode == "all":
            if all(func(item) == value for func, value in allattrs):
                return item
        else:
            if any(func(item) == value for func, value in allattrs):
                return item
    return None


def extract_all_attr(iterable: Iterable, mode: str = "all", **attrs) -> Union[List[Any], None]:
    allattrs = [(attrgetter(k), v) for k, v in attrs.items()]
    if mode == "all":
        return [item for item in iterable if all(func(item) == value for func, value in allattrs)]
    else:
        return [item for item in iterable if any(func(item) == value for func, value in allattrs)]
