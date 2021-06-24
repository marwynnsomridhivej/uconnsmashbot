from typing import Any


class AttrDict(dict):
    def __init__(self, *args, **kwargs) -> None:
        super(AttrDict, self).__init__(*args, **kwargs)

    def __getattr__(self, attr) -> Any:
        try:
            return self.__dict__[attr]
        except KeyError as e:
            raise AttributeError() from e

    def __setattr__(self, name: str, value: Any) -> None:
        self.__setitem__(name, value)

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self.__dict__.update({key: value})

    def __delattr__(self, name: str) -> None:
        self.__delitem__(name)

    def __delitem__(self, key: Any) -> None:
        super().__delitem__(key)
        del self.__dict__[key]
