# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING, Any, Callable, Coroutine, TypeVar, Union

if TYPE_CHECKING:
    from disnake import ApplicationCommandInteraction

    from .cog import Cog
    from .context import Context
    from .errors import CommandError

T = TypeVar("T")

FuncT = TypeVar("FuncT", bound=Callable[..., Any])

Coro = Coroutine[Any, Any, T]
MaybeCoro = Union[T, Coro[T]]
CoroFunc = Callable[..., Coro[Any]]

Check = Union[
    Callable[["Cog", "Context[Any]"], MaybeCoro[bool]], Callable[["Context[Any]"], MaybeCoro[bool]]
]
AppCheck = Union[
    Callable[["Cog", "ApplicationCommandInteraction"], MaybeCoro[bool]],
    Callable[["ApplicationCommandInteraction"], MaybeCoro[bool]],
]
Hook = Union[Callable[["Cog", "Context[Any]"], Coro[Any]], Callable[["Context[Any]"], Coro[Any]]]
Error = Union[
    Callable[["Cog", "Context[Any]", "CommandError"], Coro[Any]],
    Callable[["Context[Any]", "CommandError"], Coro[Any]],
]


# This is merely a tag type to avoid circular import issues.
# Yes, this is a terrible solution but ultimately it is the only solution.
class _BaseCommand:
    __slots__ = ()
