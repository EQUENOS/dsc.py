# SPDX-License-Identifier: MIT

"""Repsonsible for handling Params for slash commands"""

from __future__ import annotations

import asyncio
import collections.abc
import copy
import inspect
import itertools
import math
import sys
import types
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, EnumMeta
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Final,
    FrozenSet,
    Generic,
    List,
    Literal,
    NoReturn,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_origin,
)

import disnake
from disnake.app_commands import Option, OptionChoice
from disnake.channel import _channel_type_factory
from disnake.enums import ChannelType, OptionType, try_enum_to_int
from disnake.ext import commands
from disnake.i18n import Localized
from disnake.interactions import ApplicationCommandInteraction
from disnake.utils import (
    get_signature_parameters,
    get_signature_return,
    maybe_coroutine,
    signature_has_self_param,
)

from . import errors
from .converter import CONVERTER_MAPPING

T_ = TypeVar("T_")

if TYPE_CHECKING:
    from typing_extensions import Concatenate, ParamSpec, Self, TypeGuard

    from disnake.app_commands import Choices
    from disnake.i18n import LocalizationValue, LocalizedOptional
    from disnake.types.interactions import ApplicationCommandOptionChoiceValue

    from .base_core import CogT
    from .cog import Cog
    from .slash_core import InvokableSlashCommand, SubCommand

    AnySlashCommand = Union[InvokableSlashCommand, SubCommand]

    P = ParamSpec("P")

    InjectionCallback = Union[
        Callable[Concatenate[CogT, P], T_],
        Callable[P, T_],
    ]
    AnyAutocompleter = Union[
        Sequence[Any],
        Callable[Concatenate[ApplicationCommandInteraction, str, P], Any],
        Callable[Concatenate[CogT, ApplicationCommandInteraction, str, P], Any],
    ]

    TChoice = TypeVar("TChoice", bound=ApplicationCommandOptionChoiceValue)
else:
    P = TypeVar("P")

if sys.version_info >= (3, 10):
    from types import UnionType
else:
    UnionType = object()

T = TypeVar("T", bound=Any)
TypeT = TypeVar("TypeT", bound=Type[Any])
CallableT = TypeVar("CallableT", bound=Callable[..., Any])
BotT = TypeVar("BotT", bound="disnake.Client", covariant=True)

__all__ = (
    "Range",
    "String",
    "LargeInt",
    "ParamInfo",
    "Param",
    "param",
    "inject",
    "injection",
    "Injection",
    "option_enum",
    "register_injection",
    "converter_method",
)


def issubclass_(obj: Any, tp: Union[TypeT, Tuple[TypeT, ...]]) -> TypeGuard[TypeT]:
    """Similar to the builtin `issubclass`, but more lenient.
    Can also handle unions (`issubclass(Union[int, str], int)`) and
    generic types (`issubclass(X[T], X)`) in the first argument.
    """
    if not isinstance(tp, (type, tuple)):
        return False
    elif isinstance(obj, type):
        # common case
        return issubclass(obj, tp)

    # At this point, `obj` is likely a generic type hint
    if (origin := get_origin(obj)) is None:
        return False

    if origin in (Union, UnionType):
        # If we have a Union, try matching any of its args
        # (recursively, to handle possibly generic types inside this union)
        return any(issubclass_(o, tp) for o in obj.__args__)
    else:
        return isinstance(origin, type) and issubclass(origin, tp)


def remove_optionals(annotation: Any) -> Any:
    """Remove unwanted optionals from an annotation."""
    if get_origin(annotation) in (Union, UnionType):
        args = tuple(i for i in annotation.__args__ if i not in (None, type(None)))
        if len(args) == 1:
            annotation = args[0]
        else:
            annotation = Union[args]  # type: ignore

    return annotation


def _xt_to_xe(xe: Optional[float], xt: Optional[float], direction: float = 1) -> Optional[float]:
    """Function for combining xt and xe

    * x > xt && x >= xe ; x >= f(xt, xe, 1)
    * x < xt && x <= xe ; x <= f(xt, xe, -1)
    """
    if xe is not None:
        if xt is not None:
            raise TypeError("Cannot combine lt and le or gt and le")
        return xe
    elif xt is not None:
        epsilon = math.ldexp(1.0, -1024)
        return xt + (epsilon * direction)
    else:
        return None


def _int_to_str_len(number: int) -> int:
    """Returns `len(str(number))`, i.e. character count of base 10 signed repr of `number`."""
    # Desmos equivalent: floor(log(max(abs(x), 1))) + 1 + max(-sign(x), 0)
    return (
        int(math.log10(abs(number) or 1))
        # 0 -> 0, 1 -> 0, 9 -> 0, 10 -> 1
        + 1
        + (number < 0)
    )


def _range_to_str_len(min_value: int, max_value: int) -> Tuple[int, int]:
    min_ = _int_to_str_len(min_value)
    max_ = _int_to_str_len(max_value)
    opposite_sign = (min_value < 0) ^ (max_value < 0)
    # both bounds positive: len(str(min_value)) <= len(str(max_value))
    # smaller bound negative: the range includes 0, which sets the minimum length to 1
    # both bounds negative: len(str(min_value)) >= len(str(max_value))
    if opposite_sign:
        return 1, max(min_, max_)
    return min(min_, max_), max(min_, max_)


class Injection(Generic[P, T_]):
    """Represents a slash command injection.

    .. versionadded:: 2.3

    .. versionchanged:: 2.6
        Added keyword-only argument ``autocompleters``.

    Attributes
    ----------
    function: Callable
        The underlying injection function.
    autocompleters: Dict[:class:`str`, Callable]
        A mapping of injection's option names to their respective autocompleters.

        .. versionadded:: 2.6
    """

    _registered: ClassVar[Dict[Any, Injection]] = {}

    def __init__(
        self,
        function: InjectionCallback[CogT, P, T_],
        *,
        autocompleters: Optional[Dict[str, Callable]] = None,
    ) -> None:
        if autocompleters is not None:
            for autocomp in autocompleters.values():
                classify_autocompleter(autocomp)

        self.function: InjectionCallback[CogT, P, T_] = function
        self.autocompleters: Dict[str, Callable] = autocompleters or {}
        self._injected: Optional[Cog] = None

    def __get__(self, obj: Optional[Any], _: Type[Any]) -> Self:
        if obj is None:
            return self

        copy = type(self)(function=self.function, autocompleters=self.autocompleters)
        copy._injected = obj
        setattr(obj, self.function.__name__, copy)

        return copy

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T_:
        """Calls the underlying function that the injection holds.

        .. versionadded:: 2.6
        """
        if self._injected is not None:
            return self.function(self._injected, *args, **kwargs)  # type: ignore
        else:
            return self.function(*args, **kwargs)  # type: ignore

    @classmethod
    def register(
        cls,
        function: InjectionCallback[CogT, P, T_],
        annotation: Any,
        *,
        autocompleters: Optional[Dict[str, Callable]] = None,
    ) -> Injection[P, T_]:
        self = cls(function, autocompleters=autocompleters)
        cls._registered[annotation] = self
        return self

    def autocomplete(self, option_name: str) -> Callable[[CallableT], CallableT]:
        """A decorator that registers an autocomplete function for the specified option.

        .. versionadded:: 2.6

        Parameters
        ----------
        option_name: :class:`str`
            The name of the option.

        Raises
        ------
        ValueError
            This injection already has an autocompleter set for the given option
        TypeError
            ``option_name`` is not :class:`str`
        """
        if not isinstance(option_name, str):
            raise TypeError("option_name must be a type of str")

        if option_name in self.autocompleters:
            raise ValueError(
                f"This injection already has an autocompleter set for option '{option_name}'"
            )

        def decorator(func: CallableT) -> CallableT:
            classify_autocompleter(func)
            self.autocompleters[option_name] = func
            return func

        return decorator


NumberT = TypeVar("NumberT", bound=Union[int, float])


@dataclass(frozen=True)
class _BaseRange(ABC, Generic[NumberT]):
    """Internal base type for supporting ``Range[...]`` and ``String[...]``."""

    _allowed_types: ClassVar[Tuple[type, ...]]

    underlying_type: type
    min_value: Optional[NumberT]
    max_value: Optional[NumberT]

    def __class_getitem__(cls, params: Tuple[Any, ...]) -> Self:
        if cls is _BaseRange:
            # needed since made generic
            return super().__class_getitem__(params)  # pyright: ignore

        # deconstruct type arguments
        if not isinstance(params, tuple):
            params = (params,)

        name = cls.__name__

        if len(params) == 2:
            # backwards compatibility for `Range[1, 2]`

            # FIXME: the warning context is incorrect when used with stringified annotations,
            # and points to the eval frame instead of user code
            disnake.utils.warn_deprecated(
                f"Using `{name}` without an explicit type argument is deprecated, "
                "as this form does not work well with modern type-checkers. "
                f"Use `{name}[<type>, <min>, <max>]` instead.",
                stacklevel=2,
            )
            # infer type from min/max values
            params = (cls._infer_type(params),) + params

        if len(params) != 3:
            raise TypeError(
                f"`{name}` expects 3 arguments ({name}[<type>, <min>, <max>]), got {len(params)}"
            )

        underlying_type, min_value, max_value = params

        # validate type (argument 1)
        if not isinstance(underlying_type, type):
            raise TypeError(f"First `{name}` argument must be a type, not `{underlying_type!r}`")

        if not issubclass_(underlying_type, cls._allowed_types):
            allowed = "/".join(t.__name__ for t in cls._allowed_types)
            raise TypeError(f"First `{name}` argument must be {allowed}, not `{underlying_type!r}`")

        # validate min/max (arguments 2/3)
        min_value = cls._coerce_bound(min_value, "min")
        max_value = cls._coerce_bound(max_value, "max")

        if min_value is None and max_value is None:
            raise ValueError(f"`{name}` bounds cannot both be empty")

        # n.b. this allows bounds to be equal, which doesn't really serve a purpose with numbers,
        # but is still accepted by the api
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError(
                f"`{name}` minimum ({min_value}) must be less than or equal to maximum ({max_value})"
            )

        return cls(underlying_type=underlying_type, min_value=min_value, max_value=max_value)

    @staticmethod
    def _coerce_bound(value: Optional[NumberT], name: str) -> Optional[NumberT]:
        if value is None or value is ...:
            return None
        elif isinstance(value, (int, float)):
            if not math.isfinite(value):
                raise ValueError(f"{name} value may not be NaN, inf, or -inf")
            return value
        else:
            raise TypeError(f"{name} value must be int, float, None, or `...`, not `{type(value)}`")

    def __repr__(self) -> str:
        a = "..." if self.min_value is None else self.min_value
        b = "..." if self.max_value is None else self.max_value
        return f"{type(self).__name__}[{self.underlying_type.__name__}, {a}, {b}]"

    @staticmethod
    @abstractmethod
    def _infer_type(params: Tuple[Any, ...]) -> Type[Any]:
        raise NotImplementedError

    # hack to get `typing._type_check` to pass, e.g. when using `Range` as a generic parameter
    def __call__(self) -> NoReturn:
        raise NotImplementedError

    # support new union syntax for `Range[int, 1, 2] | None`
    if sys.version_info >= (3, 10):

        def __or__(self, other: type) -> UnionType:
            return Union[self, other]  # pyright: ignore


if TYPE_CHECKING:
    # aliased import since mypy doesn't understand `Range = Annotated`
    from typing_extensions import Annotated as Range, Annotated as String
else:

    @dataclass(frozen=True, repr=False)
    class Range(_BaseRange[Union[int, float]]):
        """Type representing a number with a limited range of allowed values.

        See :ref:`param_ranges` for more information.

        .. versionadded:: 2.4

        .. versionchanged:: 2.9
            Syntax changed from ``Range[5, 10]`` to ``Range[int, 5, 10]``;
            the type (:class:`int` or :class:`float`) must now be specified explicitly.
        """

        _allowed_types = (int, float)

        def __post_init__(self) -> None:
            for value in (self.min_value, self.max_value):
                if value is None:
                    continue

                if self.underlying_type is not float and not isinstance(value, int):
                    raise TypeError("Range[int, ...] bounds must be int, not float")

                if self.underlying_type is int and abs(value) >= 2**53:
                    raise ValueError(
                        "Discord has upper input limit on integer input type of +/-2**53.\n"
                        " For larger values, use Range[commands.LargeInt, ...], which will use"
                        " string input type with length limited to the minimum and maximum string"
                        " representations of the range bounds."
                    )

        @staticmethod
        def _infer_type(params: Tuple[Any, ...]) -> Type[Any]:
            if any(isinstance(p, float) for p in params):
                return float
            return int

    @dataclass(frozen=True, repr=False)
    class String(_BaseRange[int]):
        """Type representing a string option with a limited length.

        See :ref:`string_lengths` for more information.

        .. versionadded:: 2.6

        .. versionchanged:: 2.9
            Syntax changed from ``String[5, 10]`` to ``String[str, 5, 10]``;
            the type (:class:`str`) must now be specified explicitly.
        """

        _allowed_types = (str,)

        def __post_init__(self) -> None:
            for value in (self.min_value, self.max_value):
                if value is None:
                    continue

                if not isinstance(value, int):
                    raise TypeError("String bounds must be int, not float")
                if value < 0:
                    raise ValueError("String bounds may not be negative")

        @staticmethod
        def _infer_type(params: Tuple[Any, ...]) -> Type[Any]:
            return str


class LargeInt(int):
    """Type representing integers `<=-2**53`, `>=2**53` in slash commands."""


# option types that require additional handling in verify_type
_VERIFY_TYPES: Final[FrozenSet[OptionType]] = frozenset((OptionType.user, OptionType.mentionable))


class ParamInfo:
    """A class that basically connects function params with slash command options.
    The instances of this class are not created manually, but via the functional interface instead.
    See :func:`Param`.

    Parameters
    ----------
    default: Union[Any, Callable[[:class:`.ApplicationCommandInteraction`], Any]]
        The actual default value for the corresponding function param.
        Can be a sync/async callable taking an interaction and returning a dynamic default value,
        if the user didn't pass a value for this parameter.
    name: Optional[Union[:class:`str`, :class:`.Localized`]]
        The name of this slash command option.

        .. versionchanged:: 2.5
            Added support for localizations.

    description: Optional[Union[:class:`str`, :class:`.Localized`]]
        The description of this slash command option.

        .. versionchanged:: 2.5
            Added support for localizations.

    choices: Union[Sequence[:class:`.OptionChoice`], Sequence[Union[:class:`str`, :class:`int`, :class:`float`]], Mapping[:class:`str`, Union[:class:`str`, :class:`int`, :class:`float`]]]
        The pre-defined choices for this option.
    ge: :class:`float`
        The lowest allowed value for this option.
    le: :class:`float`
        The greatest allowed value for this option.
    type: Any
        The type of the parameter.
    channel_types: List[:class:`.ChannelType`]
        The list of channel types supported by this slash command option.
    autocomplete: Callable[[:class:`.ApplicationCommandInteraction`, :class:`str`], Any]
        The function that will suggest possible autocomplete options while typing.
    converter: Callable[[:class:`.ApplicationCommandInteraction`, Any], Any]
        The function that will convert the original input to a desired format.
    min_length: :class:`int`
        The minimum length for this option, if it is a string option.

        .. versionadded:: 2.6

    max_length: :class:`int`
        The maximum length for this option, if it is a string option.

        .. versionadded:: 2.6
    """

    TYPES: ClassVar[Dict[type, int]] = {
        str:                                               OptionType.string.value,
        int:                                               OptionType.integer.value,
        bool:                                              OptionType.boolean.value,
        float:                                             OptionType.number.value,
        disnake.abc.User:                                  OptionType.user.value,
        disnake.User:                                      OptionType.user.value,
        disnake.Member:                                    OptionType.user.value,
        Union[disnake.User, disnake.Member]:               OptionType.user.value,
        disnake.Role:                                      OptionType.role.value,
        disnake.abc.Snowflake:                             OptionType.mentionable.value,
        Union[disnake.Member, disnake.Role]:               OptionType.mentionable.value,
        Union[disnake.User, disnake.Role]:                 OptionType.mentionable.value,
        Union[disnake.User, disnake.Member, disnake.Role]: OptionType.mentionable.value,
        disnake.Attachment:                                OptionType.attachment.value,
        # channels handled separately
        disnake.abc.GuildChannel:                          OptionType.channel.value,
    }  # fmt: skip
    _registered_converters: ClassVar[Dict[type, Callable]] = {}

    def __init__(
        self,
        default: Union[Any, Callable[[ApplicationCommandInteraction[BotT]], Any]] = ...,
        *,
        name: LocalizedOptional = None,
        description: LocalizedOptional = None,
        converter: Optional[Callable[[ApplicationCommandInteraction[BotT], Any], Any]] = None,
        convert_default: bool = False,
        autocomplete: Optional[AnyAutocompleter] = None,
        choices: Optional[Choices] = None,
        type: Optional[type] = None,
        channel_types: Optional[List[ChannelType]] = None,
        lt: Union[int, float, None] = None,
        le: Union[int, float, None] = None,
        gt: Union[int, float, None] = None,
        ge: Union[int, float, None] = None,
        large: bool = False,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
    ) -> None:
        name_loc = Localized._cast(name, False)
        self.name: str = name_loc.string or ""
        self.name_localizations: LocalizationValue = name_loc.localizations

        desc_loc = Localized._cast(description, False)
        self.description: Optional[str] = desc_loc.string
        self.description_localizations: LocalizationValue = desc_loc.localizations

        self.default = default
        self.param_name: str = self.name
        self.converter = converter
        self.convert_default = convert_default
        self.autocomplete = autocomplete
        self.choices = choices or []
        self.type = type or str
        self.channel_types = channel_types or []
        self.min_value: Union[int, float, None] = _xt_to_xe(ge, gt, 1)
        self.max_value: Union[int, float, None] = _xt_to_xe(le, lt, -1)
        self.min_length: Optional[int] = min_length
        self.max_length: Optional[int] = max_length
        self.large = large

    def copy(self) -> Self:
        # n. b. this method needs to be manually updated when a new attribute is added.
        cls = self.__class__
        ins = cls.__new__(cls)

        ins.name = self.name
        ins.name_localizations = self.name_localizations._copy()
        ins.description = self.description
        ins.description_localizations = self.description_localizations._copy()
        ins.default = self.default
        ins.param_name = self.param_name
        ins.converter = self.converter
        ins.convert_default = self.convert_default
        ins.autocomplete = self.autocomplete
        ins.choices = copy.copy(self.choices)
        ins.type = self.type
        ins.channel_types = self.channel_types.copy()
        ins.max_value = self.max_value
        ins.min_value = self.min_value
        ins.min_length = self.min_length
        ins.max_length = self.max_length
        ins.large = self.large

        return ins

    @property
    def required(self) -> bool:
        return self.default is Ellipsis

    @property
    def discord_type(self) -> OptionType:
        return OptionType(self.TYPES.get(self.type, OptionType.string.value))

    @discord_type.setter
    def discord_type(self, discord_type: OptionType) -> None:
        value = try_enum_to_int(discord_type)
        for t, v in self.TYPES.items():
            if value == v:
                self.type = t
                return

        raise TypeError(f"Type {discord_type} is not a valid Param type")

    @classmethod
    def from_param(
        cls,
        param: inspect.Parameter,
        type_hints: Dict[str, Any],
        parsed_docstring: Optional[Dict[str, disnake.utils._DocstringParam]] = None,
    ) -> Self:
        # hopefully repeated parsing won't cause any problems
        parsed_docstring = parsed_docstring or {}

        if isinstance(param.default, cls):
            # we copy this ParamInfo instance because it can be used in multiple signatures
            self = param.default.copy()
        else:
            default = param.default if param.default is not inspect.Parameter.empty else ...
            self = cls(default)

        self.parse_parameter(param)
        doc = parsed_docstring.get(param.name)
        if doc:
            self.parse_doc(doc)
        self.parse_annotation(type_hints.get(param.name, param.annotation))

        return self

    @classmethod
    def register_converter(cls, annotation: Any, converter: CallableT) -> CallableT:
        cls._registered_converters[annotation] = converter
        return converter

    def __repr__(self) -> str:
        args = ", ".join(f"{k}={'...' if v is ... else repr(v)}" for k, v in vars(self).items())
        return f"{type(self).__name__}({args})"

    async def get_default(self, inter: ApplicationCommandInteraction) -> Any:
        """Gets the default for an interaction."""
        default = self.default
        if callable(self.default):
            default = self.default(inter)

            if inspect.isawaitable(default):
                default = await default

        if self.convert_default:
            default = await self.convert_argument(inter, default)

        return default

    async def verify_type(self, inter: ApplicationCommandInteraction, argument: Any) -> Any:
        """Check if the type of an argument is correct and possibly raise if it's not."""
        if self.discord_type not in _VERIFY_TYPES:
            return argument

        # The API may return a `User` for options annotated with `Member`,
        # including `Member` (user option), `Union[User, Member]` (user option) and
        # `Union[Member, Role]` (mentionable option).
        # If we received a `User` but didn't expect one, raise.
        if (
            isinstance(argument, disnake.User)
            and issubclass_(self.type, disnake.Member)
            and not issubclass_(self.type, disnake.User)
        ):
            raise errors.MemberNotFound(str(argument.id))

        return argument

    async def convert_argument(self, inter: ApplicationCommandInteraction, argument: Any) -> Any:
        """Convert a value if a converter is given."""
        if self.large:
            try:
                argument = int(argument)
            except ValueError:
                raise errors.LargeIntConversionFailure(argument) from None

            min_value = -math.inf if self.min_value is None else self.min_value
            max_value = math.inf if self.max_value is None else self.max_value

            if not min_value <= argument <= max_value:
                raise errors.LargeIntOutOfRange(argument, self.min_value, self.max_value) from None

        if self.converter is None:
            # TODO: Custom validators
            return await self.verify_type(inter, argument)

        try:
            argument = self.converter(inter, argument)
            if inspect.isawaitable(argument):
                return await argument

            return argument
        except errors.CommandError:
            raise
        except Exception as e:
            raise errors.ConversionError(self.converter, e) from e

    def _parse_enum(self, annotation: Any) -> None:
        if isinstance(annotation, (EnumMeta, disnake.enums.EnumMeta)):
            self.choices = [OptionChoice(name, value.value) for name, value in annotation.__members__.items()]  # type: ignore
        else:
            self.choices = [OptionChoice(str(i), i) for i in annotation.__args__]

        self.type = type(self.choices[0].value)

    def _parse_guild_channel(
        self, *channels: Union[Type[disnake.abc.GuildChannel], Type[disnake.Thread]]
    ) -> None:
        # this variable continues to be GuildChannel because the type is still
        # determined from the TYPE mapping in the class definition
        self.type = disnake.abc.GuildChannel

        if not self.channel_types:
            channel_types = set()
            for channel in channels:
                channel_types.update(_channel_type_factory(channel))
            self.channel_types = list(channel_types)

    def parse_annotation(self, annotation: Any, converter_mode: bool = False) -> bool:
        """Parse an annotation"""
        annotation = remove_optionals(annotation)

        if not converter_mode:
            self.converter = (
                self.converter
                or getattr(annotation, "__discord_converter__", None)
                or self._registered_converters.get(annotation)
            )
            if self.converter:
                self.parse_converter_annotation(self.converter, annotation)
                return True

        # short circuit if user forgot to provide annotations
        if annotation is inspect.Parameter.empty or annotation is Any:
            return False

        # resolve type aliases and special types
        if isinstance(annotation, Range):
            self.min_value = annotation.min_value
            self.max_value = annotation.max_value
            annotation = annotation.underlying_type

        elif isinstance(annotation, String):
            self.min_length = annotation.min_value
            self.max_length = annotation.max_value
            annotation = annotation.underlying_type

        if issubclass_(annotation, LargeInt):
            self.large = True
            annotation = int

        if self.large:
            if annotation is not int:
                raise TypeError("Large integers must be annotated with int or LargeInt")
            self.type = str

            if self.min_value is not None and self.max_value is not None:
                # honestly would rather assert than type ignore these
                self.min_length, self.max_length = _range_to_str_len(
                    self.min_value,  # pyright: ignore
                    self.max_value,  # pyright: ignore
                )

            elif self.min_value is not None and self.min_value > 0:
                # 0 < min_value <= max_value == inf
                self.min_length = _int_to_str_len(self.min_value)  # pyright: ignore

            elif self.max_value is not None and self.max_value < 0:
                # -inf == max_value <= min_value < 0
                self.max_length = _int_to_str_len(self.max_value)  # pyright: ignore

        elif annotation in self.TYPES:
            self.type = annotation
        elif (
            isinstance(annotation, (EnumMeta, disnake.enums.EnumMeta))
            or get_origin(annotation) is Literal
        ):
            self._parse_enum(annotation)
        elif get_origin(annotation) in (Union, UnionType):
            args = annotation.__args__
            if all(
                issubclass_(channel, (disnake.abc.GuildChannel, disnake.Thread)) for channel in args
            ):
                self._parse_guild_channel(*args)
            else:
                raise TypeError(
                    "Unions for anything else other than channels or a mentionable are not supported"
                )
        elif issubclass_(annotation, (disnake.abc.GuildChannel, disnake.Thread)):
            self._parse_guild_channel(annotation)
        elif issubclass_(get_origin(annotation), collections.abc.Sequence):
            raise TypeError(
                f"List arguments have not been implemented yet and therefore {annotation!r} is invalid"
            )

        elif annotation in CONVERTER_MAPPING:
            if converter_mode:
                raise TypeError(
                    f"{annotation!r} implies the usage of a converter but those cannot be nested"
                )
            self.converter = CONVERTER_MAPPING[annotation]().convert
        elif converter_mode:
            raise TypeError(f"{annotation!r} is not a valid converter annotation")
        else:
            raise TypeError(f"{annotation!r} is not a valid parameter annotation")

        return True

    def parse_converter_annotation(self, converter: Callable, fallback_annotation: Any) -> None:
        if isinstance(converter, (types.FunctionType, types.MethodType)):
            converter_func = converter
        else:
            # if converter isn't a function/method, assume it's a callable object/type
            # (we need `__call__` here to get the correct global namespace later, since
            # classes do not have `__globals__`)
            converter_func = converter.__call__
        _, parameters = isolate_self(converter_func)

        if len(parameters) != 1:
            raise TypeError(
                "Converters must take precisely two arguments: the interaction and the argument"
            )

        _, parameter = parameters.popitem()
        annotation = parameter.annotation

        if parameter.default is not inspect.Parameter.empty and self.required:
            self.default = parameter.default
            self.convert_default = True

        success = self.parse_annotation(annotation, converter_mode=True)
        if success:
            return
        success = self.parse_annotation(fallback_annotation, converter_mode=True)
        if success:
            return

        raise TypeError(
            f"Both the converter annotation {annotation!r} and the option annotation {fallback_annotation!r} are invalid"
        )

    def parse_parameter(self, param: inspect.Parameter) -> None:
        self.name = self.name or param.name
        self.param_name = param.name

    def parse_doc(self, doc: disnake.utils._DocstringParam) -> None:
        if self.type == str and doc["type"] is not None:
            self.parse_annotation(doc["type"])

        self.description = self.description or doc["description"]

        self.name_localizations._upgrade(doc["localization_key_name"])
        self.description_localizations._upgrade(doc["localization_key_desc"])

    def to_option(self) -> Option:
        if not self.name:
            raise TypeError("Param must be parsed first")

        name = Localized(self.name, data=self.name_localizations)
        desc = Localized(self.description, data=self.description_localizations)

        return Option(
            name=name,
            description=desc,
            type=self.discord_type,
            required=self.required,
            choices=self.choices or None,
            channel_types=self.channel_types,
            autocomplete=self.autocomplete is not None,
            min_value=None if self.large else self.min_value,
            max_value=None if self.large else self.max_value,
            min_length=self.min_length,
            max_length=self.max_length,
        )


def safe_call(function: Callable[..., T], /, *possible_args: Any, **possible_kwargs: Any) -> T:
    """Calls a function without providing any extra unexpected arguments"""
    MISSING: Any = object()
    parameters = get_signature_parameters(function)

    kinds = {p.kind for p in parameters.values()}
    arb = {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
    if arb.issubset(kinds):
        raise TypeError(
            "Cannot safely call a function with both *args and **kwargs. "
            "If this is a wrapper please use functools.wraps to keep the signature correct"
        )

    parsed_pos = False
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}

    for index, parameter, posarg in itertools.zip_longest(
        itertools.count(),
        parameters.values(),
        possible_args,
        fillvalue=MISSING,
    ):
        if parameter is MISSING:
            break
        if posarg is MISSING:
            parsed_pos = True

        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            args = list(possible_args)
            parsed_pos = True
        elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
            kwargs = possible_kwargs
            break
        elif parameter.kind is inspect.Parameter.KEYWORD_ONLY:
            parsed_pos = True

        if not parsed_pos:
            args.append(possible_args[index])
        elif parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
            break  # guaranteed error since not enough positional arguments
        elif parameter.name in possible_kwargs:
            kwargs[parameter.name] = possible_kwargs[parameter.name]

    return function(*args, **kwargs)


def isolate_self(
    function: Callable,
    parameters: Optional[Dict[str, inspect.Parameter]] = None,
) -> Tuple[Tuple[Optional[inspect.Parameter], ...], Dict[str, inspect.Parameter]]:
    """Create parameters without self and the first interaction.

    Optionally accepts a `{str: inspect.Parameter}` dict as an optimization,
    calls `get_signature_parameters(function)` if not provided.
    """
    if parameters is None:
        parameters = get_signature_parameters(function)
    if not parameters:
        return (None, None), {}

    parameters = dict(parameters)  # shallow copy
    parametersl = list(parameters.values())

    cog_param: Optional[inspect.Parameter] = None
    inter_param: Optional[inspect.Parameter] = None

    if signature_has_self_param(function):
        cog_param = parameters.pop(parametersl[0].name)
        parametersl.pop(0)
    if parametersl:
        annot = parametersl[0].annotation
        if issubclass_(annot, ApplicationCommandInteraction) or annot is inspect.Parameter.empty:
            inter_param = parameters.pop(parametersl[0].name)

    return (cog_param, inter_param), parameters


def classify_autocompleter(autocompleter: AnyAutocompleter) -> None:
    """Detects whether an autocomplete function can take a cog as the first argument.
    The result is then saved as a boolean value in `func.__has_cog_param__`
    """
    if not callable(autocompleter):
        return

    sig = inspect.signature(autocompleter)
    positional_param_count = 0

    for param in sig.parameters.values():
        if (
            param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD)
        ) and param.default is param.empty:
            positional_param_count += 1
        else:
            break

    if positional_param_count < 2:
        raise ValueError(
            "An autocomplete function should have 2 or 3 non-optional positional arguments. "
            "For example, foo(inter, string) or foo(cog, inter, string)"
        )

    if positional_param_count > 3:
        raise ValueError(
            "Any additional arguments of an autocomplete function "
            "(apart from the first 3) should be keyword-only"
        )

    autocompleter.__has_cog_param__ = positional_param_count == 3


def collect_params(
    function: Callable,
    parameters: Optional[Dict[str, inspect.Parameter]] = None,
) -> Tuple[Optional[str], Optional[str], List[ParamInfo], Dict[str, Injection]]:
    """Collect all parameters in a function.

    Optionally accepts a `{str: inspect.Parameter}` dict as an optimization.

    Returns: (`cog parameter`, `interaction parameter`, `param infos`, `injections`)
    """
    (cog_param, inter_param), parameters = isolate_self(function, parameters)

    doc = disnake.utils.parse_docstring(function)["params"]

    paraminfos: List[ParamInfo] = []
    injections: Dict[str, Injection] = {}

    for parameter in parameters.values():
        if parameter.kind in [parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD]:
            continue
        if parameter.kind is parameter.POSITIONAL_ONLY:
            raise TypeError("Positional-only parameters cannot be used in commands")

        default = parameter.default
        if isinstance(default, Injection):
            injections[parameter.name] = default
        elif parameter.annotation in Injection._registered:
            injections[parameter.name] = Injection._registered[parameter.annotation]
        elif issubclass_(parameter.annotation, ApplicationCommandInteraction):
            if inter_param is None:
                inter_param = parameter
            else:
                raise TypeError(
                    f"Found two candidates for the interaction parameter in {function!r}: {inter_param.name} and {parameter.name}"
                )
        elif issubclass_(parameter.annotation, commands.Cog):
            if cog_param is None:
                cog_param = parameter
            else:
                raise TypeError(
                    f"Found two candidates for the cog parameter in {function!r}: {cog_param.name} and {parameter.name}"
                )
        else:
            paraminfo = ParamInfo.from_param(parameter, {}, doc)
            paraminfos.append(paraminfo)

    return (
        cog_param.name if cog_param else None,
        inter_param.name if inter_param else None,
        paraminfos,
        injections,
    )


def collect_nested_params(function: Callable) -> List[ParamInfo]:
    """Collect all options from a function"""
    # TODO: Have these be actually sorted properly and not have injections always at the end
    _, _, paraminfos, injections = collect_params(function)

    for injection in injections.values():
        paraminfos += collect_nested_params(injection.function)

    return sorted(paraminfos, key=lambda param: not param.required)


def format_kwargs(
    interaction: ApplicationCommandInteraction,
    cog_param: Optional[str] = None,
    inter_param: Optional[str] = None,
    /,
    *args: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Create kwargs from appropriate information"""
    first = args[0] if args else None

    if len(args) > 1:
        raise TypeError(
            "When calling a slash command only self and the interaction should be positional"
        )
    elif first and not isinstance(first, commands.Cog):
        raise TypeError("Method slash commands may be created only in cog subclasses")

    cog: Optional[commands.Cog] = first

    if cog_param:
        kwargs[cog_param] = cog
    if inter_param:
        kwargs[inter_param] = interaction

    return kwargs


async def run_injections(
    injections: Dict[str, Injection],
    interaction: ApplicationCommandInteraction,
    /,
    *args: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Run and resolve a list of injections"""

    async def _helper(name: str, injection: Injection) -> Tuple[str, Any]:
        return name, await call_param_func(injection.function, interaction, *args, **kwargs)

    resolved = await asyncio.gather(*(_helper(name, i) for name, i in injections.items()))
    return dict(resolved)


async def call_param_func(
    function: Callable, interaction: ApplicationCommandInteraction, /, *args: Any, **kwargs: Any
) -> Any:
    """Call a function utilizing ParamInfo"""
    cog_param, inter_param, paraminfos, injections = collect_params(function)
    formatted_kwargs = format_kwargs(interaction, cog_param, inter_param, *args, **kwargs)
    formatted_kwargs.update(await run_injections(injections, interaction, *args, **kwargs))
    kwargs = formatted_kwargs

    for param in paraminfos:
        if param.param_name in kwargs:
            kwargs[param.param_name] = await param.convert_argument(
                interaction, kwargs[param.param_name]
            )
        elif param.default is not ...:
            kwargs[param.param_name] = await param.get_default(interaction)

    return await maybe_coroutine(safe_call, function, **kwargs)


def expand_params(command: AnySlashCommand) -> List[Option]:
    """Update an option with its params *in-place*

    Returns the created options
    """
    parameters = get_signature_parameters(command.callback)
    # pass `parameters` down to avoid having to call `get_signature_parameters(func)` another time,
    # which may cause side effects with deferred annotations and warnings
    _, inter_param, params, injections = collect_params(command.callback, parameters)

    if inter_param is None:
        raise TypeError(f"Couldn't find an interaction parameter in {command.callback}")

    for injection in injections.values():
        collected = collect_nested_params(injection.function)
        if injection.autocompleters:
            lookup = {p.name: p for p in collected}
            for name, func in injection.autocompleters.items():
                param = lookup.get(name)
                if param is None:
                    raise ValueError(f"Option '{name}' doesn't exist in '{command.qualified_name}'")
                param.autocomplete = func
        params += collected

    params = sorted(params, key=lambda param: not param.required)

    # update connectors and autocompleters
    for param in params:
        if param.name != param.param_name:
            command.connectors[param.name] = param.param_name
        if param.autocomplete:
            command.autocompleters[param.name] = param.autocomplete

    if issubclass_(parameters[inter_param].annotation, disnake.GuildCommandInteraction):
        command._guild_only = True

    return [param.to_option() for param in params]


def Param(
    default: Union[Any, Callable[[ApplicationCommandInteraction[BotT]], Any]] = ...,
    *,
    name: LocalizedOptional = None,
    description: LocalizedOptional = None,
    choices: Optional[Choices] = None,
    converter: Optional[Callable[[ApplicationCommandInteraction[BotT], Any], Any]] = None,
    convert_defaults: bool = False,
    autocomplete: Optional[Callable[[ApplicationCommandInteraction[BotT], str], Any]] = None,
    channel_types: Optional[List[ChannelType]] = None,
    lt: Optional[float] = None,
    le: Optional[float] = None,
    gt: Optional[float] = None,
    ge: Optional[float] = None,
    large: bool = False,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    **kwargs: Any,
) -> Any:
    """A special function that creates an instance of :class:`ParamInfo` that contains some information about a
    slash command option. This instance should be assigned to a parameter of a function representing your slash command.

    See :ref:`param_syntax` for more info.

    Parameters
    ----------
    default: Union[Any, Callable[[:class:`.ApplicationCommandInteraction`], Any]]
        The actual default value of the function parameter that should be passed instead of the :class:`ParamInfo` instance.
        Can be a sync/async callable taking an interaction and returning a dynamic default value,
        if the user didn't pass a value for this parameter.
    name: Optional[Union[:class:`str`, :class:`.Localized`]]
        The name of the option. By default, the option name is the parameter name.

        .. versionchanged:: 2.5
            Added support for localizations.

    description: Optional[Union[:class:`str`, :class:`.Localized`]]
        The description of the option. You can skip this kwarg and use docstrings. See :ref:`param_syntax`.
        Kwarg aliases: ``desc``.

        .. versionchanged:: 2.5
            Added support for localizations.

    choices: Union[Sequence[:class:`.OptionChoice`], Sequence[Union[:class:`str`, :class:`int`, :class:`float`]], Mapping[:class:`str`, Union[:class:`str`, :class:`int`, :class:`float`]]]
        The pre-defined choices for this slash command option.
    converter: Callable[[:class:`.ApplicationCommandInteraction`, Any], Any]
        A function that will convert the original input to a desired format.
        Kwarg aliases: ``conv``.
    convert_defaults: :class:`bool`
        Whether to also apply the converter to the provided default value.
        Defaults to ``False``.

        .. versionadded:: 2.3
    autocomplete: Callable[[:class:`.ApplicationCommandInteraction`, :class:`str`], Any]
        A function that will suggest possible autocomplete options while typing.
        See :ref:`param_syntax`. Kwarg aliases: ``autocomp``.
    channel_types: Iterable[:class:`.ChannelType`]
        A list of channel types that should be allowed.
        By default these are discerned from the annotation.
    lt: :class:`float`
        The (exclusive) upper bound of values for this option (less-than).
    le: :class:`float`
        The (inclusive) upper bound of values for this option (less-than-or-equal). Kwarg aliases: ``max_value``.
    gt: :class:`float`
        The (exclusive) lower bound of values for this option (greater-than).
    ge: :class:`float`
        The (inclusive) lower bound of values for this option (greater-than-or-equal). Kwarg aliases: ``min_value``.
    large: :class:`bool`
        Whether to accept large :class:`int` values (if this is ``False``, only
        values in the range ``(-2^53, 2^53)`` would be accepted due to an API limitation).

        .. versionadded:: 2.3

    min_length: :class:`int`
        The minimum length for this option if this is a string option.

        .. versionadded:: 2.6

    max_length: :class:`int`
        The maximum length for this option if this is a string option.

        .. versionadded:: 2.6

    Raises
    ------
    TypeError
        Unexpected keyword arguments were provided.

    Returns
    -------
    :class:`ParamInfo`
        An instance with the option info.

        .. note::

            In terms of typing, this returns ``Any`` to avoid typing issues,
            but at runtime this is always a :class:`ParamInfo` instance.
            You can find a more in-depth explanation :ref:`here <why_params_and_injections_return_any>`.
    """
    description = kwargs.pop("desc", description)
    converter = kwargs.pop("conv", converter)
    autocomplete = kwargs.pop("autocomp", autocomplete)
    le = kwargs.pop("max_value", le)
    ge = kwargs.pop("min_value", ge)

    if kwargs:
        a = ", ".join(map(repr, kwargs))
        raise TypeError(f"Param() got unexpected keyword arguments: {a}")

    return ParamInfo(
        default,
        name=name,
        description=description,
        choices=choices,
        converter=converter,
        convert_default=convert_defaults,
        autocomplete=autocomplete,
        channel_types=channel_types,
        lt=lt,
        le=le,
        gt=gt,
        ge=ge,
        large=large,
        min_length=min_length,
        max_length=max_length,
    )


param = Param


def inject(
    function: Callable[..., Any],
    *,
    autocompleters: Optional[Dict[str, Callable]] = None,
) -> Any:
    """A special function to use the provided function for injections.
    This should be assigned to a parameter of a function representing your slash command.

    .. versionadded:: 2.3

    .. versionchanged:: 2.6
        Added ``autocompleters`` keyword-only argument.

    Parameters
    ----------
    function: Callable
        The injection function.
    autocompleters: Dict[:class:`str`, Callable]
        A mapping of the injection's option names to their respective autocompleters.

        See also :func:`Injection.autocomplete`.

        .. versionadded:: 2.6

    Returns
    -------
    :class:`Injection`
        The resulting injection

        .. note::

            The return type is annotated with ``Any`` to avoid typing issues caused by how this
            extension works, but at runtime this is always an :class:`Injection` instance.
            You can find more in-depth explanation :ref:`here <why_params_and_injections_return_any>`.
    """
    return Injection(function, autocompleters=autocompleters)


def injection(
    *,
    autocompleters: Optional[Dict[str, Callable]] = None,
) -> Callable[[Callable[..., Any]], Any]:
    """Decorator interface for :func:`inject`.
    You can then assign this value to your slash commands' parameters.

    .. versionadded:: 2.6

    Parameters
    ----------
    autocompleters: Dict[:class:`str`, Callable]
        A mapping of the injection's option names to their respective autocompleters.

        See also :func:`Injection.autocomplete`.

    Returns
    -------
    Callable[[Callable[..., Any]], :class:`Injection`]
        Decorator which turns your injection function into actual :class:`Injection`.

        .. note::

            The decorator return type is annotated with ``Any`` to avoid typing issues caused by how this
            extension works, but at runtime this is always an :class:`Injection` instance.
            You can find more in-depth explanation :ref:`here <why_params_and_injections_return_any>`.
    """

    def decorator(function: Callable[..., Any]) -> Injection:
        return inject(function, autocompleters=autocompleters)

    return decorator


def option_enum(
    choices: Union[Dict[str, TChoice], List[TChoice]], **kwargs: TChoice
) -> Type[TChoice]:
    """A utility function to create an enum type.
    Returns a new :class:`~enum.Enum` based on the provided parameters.

    .. versionadded:: 2.1

    Parameters
    ----------
    choices: Union[Dict[:class:`str`, :class:`Any`], List[:class:`Any`]]
        A name/value mapping of choices, or a list of values whose stringified representations
        will be used as the names.
    **kwargs
        Name/value pairs to use instead of the ``choices`` parameter.
    """
    if isinstance(choices, list):
        choices = {str(i): i for i in choices}

    choices = choices or kwargs
    first, *_ = choices.values()
    return Enum("", choices, type=type(first))  # type: ignore


class ConverterMethod(classmethod):
    """A class to help register a method as a converter method."""

    def __set_name__(self, owner: Any, name: str) -> None:
        # this feels wrong
        function = self.__get__(None, owner)
        ParamInfo._registered_converters[owner] = function
        owner.__discord_converter__ = function


# due to a bug in pylance classmethod subclasses do not actually work properly
if TYPE_CHECKING:
    converter_method = classmethod
else:

    def converter_method(function: Any) -> ConverterMethod:
        """A decorator to register a method as the converter method.

        .. versionadded:: 2.3
        """
        return ConverterMethod(function)


def register_injection(
    function: InjectionCallback[CogT, P, T_],
    *,
    autocompleters: Optional[Dict[str, Callable]] = None,
) -> Injection[P, T_]:
    """A decorator to register a global injection.

    .. versionadded:: 2.3

    .. versionchanged:: 2.6
        Now returns :class:`.Injection`.

    .. versionchanged:: 2.6
        Added ``autocompleters`` keyword-only argument.

    Raises
    ------
    TypeError
        Injection doesn't have a return annotation,
        or tries to overwrite builtin types.

    Returns
    -------
    :class:`Injection`
        The injection being registered.
    """
    tp = get_signature_return(function)

    if tp is inspect.Parameter.empty:
        raise TypeError("Injection must have a return annotation")
    if tp in ParamInfo.TYPES:
        raise TypeError("Injection cannot overwrite builtin types")

    return Injection.register(function, tp, autocompleters=autocompleters)
