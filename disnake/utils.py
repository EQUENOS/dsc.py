# SPDX-License-Identifier: MIT

from __future__ import annotations

import array
import asyncio
import datetime
import functools
import json
import os
import pkgutil
import re
import sys
import unicodedata
import warnings
from base64 import b64encode
from bisect import bisect_left
from inspect import getdoc as _getdoc, isawaitable as _isawaitable, signature as _signature
from operator import attrgetter
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    ForwardRef,
    Generic,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    NoReturn,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
    get_origin,
    overload,
)
from urllib.parse import parse_qs, urlencode

from .enums import Locale

try:
    import orjson
except ModuleNotFoundError:
    HAS_ORJSON = False
else:
    HAS_ORJSON = True


__all__ = (
    "oauth_url",
    "snowflake_time",
    "time_snowflake",
    "find",
    "get",
    "sleep_until",
    "utcnow",
    "remove_markdown",
    "escape_markdown",
    "escape_mentions",
    "as_chunks",
    "format_dt",
    "search_directory",
    "as_valid_locale",
)

DISCORD_EPOCH = 1420070400000


class _MissingSentinel:
    def __eq__(self, other: Any) -> bool:
        return False

    def __hash__(self) -> int:
        return 0

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "..."


MISSING: Any = _MissingSentinel()


class _cached_property:
    def __init__(self, function) -> None:
        self.function = function
        self.__doc__: Optional[str] = function.__doc__

    def __get__(self, instance, owner):
        if instance is None:
            return self

        value = self.function(instance)
        setattr(instance, self.function.__name__, value)

        return value


if TYPE_CHECKING:
    from functools import cached_property as cached_property

    from typing_extensions import Never, ParamSpec, Self

    from .abc import Snowflake
    from .asset import AssetBytes
    from .invite import Invite
    from .permissions import Permissions
    from .template import Template

    class _RequestLike(Protocol):
        headers: Mapping[str, Any]

    P = ParamSpec("P")

else:
    cached_property = _cached_property


T = TypeVar("T")
V = TypeVar("V")
T_co = TypeVar("T_co", covariant=True)
_Iter = Union[Iterator[T], AsyncIterator[T]]


class CachedSlotProperty(Generic[T, T_co]):
    def __init__(self, name: str, function: Callable[[T], T_co]) -> None:
        self.name = name
        self.function = function
        self.__doc__ = function.__doc__

    @overload
    def __get__(self, instance: None, owner: Type[T]) -> Self:
        ...

    @overload
    def __get__(self, instance: T, owner: Type[T]) -> T_co:
        ...

    def __get__(self, instance: Optional[T], owner: Type[T]) -> Any:
        if instance is None:
            return self

        try:
            return getattr(instance, self.name)
        except AttributeError:
            value = self.function(instance)
            setattr(instance, self.name, value)
            return value


class classproperty(Generic[T_co]):
    def __init__(self, fget: Callable[[Any], T_co]) -> None:
        self.fget = fget

    def __get__(self, instance: Optional[Any], owner: Type[Any]) -> T_co:
        return self.fget(owner)

    def __set__(self, instance, value) -> NoReturn:
        raise AttributeError("cannot set attribute")


def cached_slot_property(name: str) -> Callable[[Callable[[T], T_co]], CachedSlotProperty[T, T_co]]:
    def decorator(func: Callable[[T], T_co]) -> CachedSlotProperty[T, T_co]:
        return CachedSlotProperty(name, func)

    return decorator


class SequenceProxy(Sequence[T_co]):
    """Read-only proxy of a Sequence."""

    def __init__(self, proxied: Sequence[T_co]) -> None:
        self.__proxied = proxied

    def __getitem__(self, idx: int) -> T_co:
        return self.__proxied[idx]

    def __len__(self) -> int:
        return len(self.__proxied)

    def __contains__(self, item: Any) -> bool:
        return item in self.__proxied

    def __iter__(self) -> Iterator[T_co]:
        return iter(self.__proxied)

    def __reversed__(self) -> Iterator[T_co]:
        return reversed(self.__proxied)

    def index(self, value: Any, *args, **kwargs) -> int:
        return self.__proxied.index(value, *args, **kwargs)

    def count(self, value: Any) -> int:
        return self.__proxied.count(value)


@overload
def parse_time(timestamp: None) -> None:
    ...


@overload
def parse_time(timestamp: str) -> datetime.datetime:
    ...


@overload
def parse_time(timestamp: Optional[str]) -> Optional[datetime.datetime]:
    ...


def parse_time(timestamp: Optional[str]) -> Optional[datetime.datetime]:
    if timestamp:
        return datetime.datetime.fromisoformat(timestamp)
    return None


@overload
def isoformat_utc(dt: datetime.datetime) -> str:
    ...


@overload
def isoformat_utc(dt: Optional[datetime.datetime]) -> Optional[str]:
    ...


def isoformat_utc(dt: Optional[datetime.datetime]) -> Optional[str]:
    if dt:
        return dt.astimezone(datetime.timezone.utc).isoformat()
    return None


def copy_doc(original: Callable) -> Callable[[T], T]:
    def decorator(overriden: T) -> T:
        overriden.__doc__ = original.__doc__
        overriden.__signature__ = _signature(original)  # type: ignore
        return overriden

    return decorator


def deprecated(instead: Optional[str] = None) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def actual_decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def decorated(*args: P.args, **kwargs: P.kwargs) -> T:
            if instead:
                msg = f"{func.__name__} is deprecated, use {instead} instead."
            else:
                msg = f"{func.__name__} is deprecated."

            warn_deprecated(msg, stacklevel=2)
            return func(*args, **kwargs)

        return decorated

    return actual_decorator


def warn_deprecated(*args: Any, stacklevel: int = 1, **kwargs: Any) -> None:
    old_filters = warnings.filters[:]
    try:
        warnings.simplefilter("always", DeprecationWarning)
        warnings.warn(*args, stacklevel=stacklevel + 1, category=DeprecationWarning, **kwargs)
    finally:
        warnings.filters[:] = old_filters  # type: ignore


def oauth_url(
    client_id: Union[int, str],
    *,
    permissions: Permissions = MISSING,
    guild: Snowflake = MISSING,
    redirect_uri: str = MISSING,
    scopes: Iterable[str] = MISSING,
    disable_guild_select: bool = False,
) -> str:
    """A helper function that returns the OAuth2 URL for inviting the bot
    into guilds.

    Parameters
    ----------
    client_id: Union[:class:`int`, :class:`str`]
        The client ID for your bot.
    permissions: :class:`~disnake.Permissions`
        The permissions you're requesting. If not given then you won't be requesting any
        permissions.
    guild: :class:`~disnake.abc.Snowflake`
        The guild to pre-select in the authorization screen, if available.
    redirect_uri: :class:`str`
        An optional valid redirect URI.
    scopes: Iterable[:class:`str`]
        An optional valid list of scopes. Defaults to ``('bot',)``.

        .. versionadded:: 1.7

    disable_guild_select: :class:`bool`
        Whether to disallow the user from changing the guild dropdown.

        .. versionadded:: 2.0

    Returns
    -------
    :class:`str`
        The OAuth2 URL for inviting the bot into guilds.
    """
    url = f"https://discord.com/oauth2/authorize?client_id={client_id}"
    url += "&scope=" + "+".join(scopes or ("bot",))
    if permissions is not MISSING:
        url += f"&permissions={permissions.value}"
    if guild is not MISSING:
        url += f"&guild_id={guild.id}"
    if redirect_uri is not MISSING:
        url += "&response_type=code&" + urlencode({"redirect_uri": redirect_uri})
    if disable_guild_select:
        url += "&disable_guild_select=true"
    return url


def snowflake_time(id: int) -> datetime.datetime:
    """Parameters
    ----------
    id: :class:`int`
        The snowflake ID.

    Returns
    -------
    :class:`datetime.datetime`
        An aware datetime in UTC representing the creation time of the snowflake.
    """
    timestamp = ((id >> 22) + DISCORD_EPOCH) / 1000
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)


def time_snowflake(dt: datetime.datetime, high: bool = False) -> int:
    """Returns a numeric snowflake pretending to be created at the given date.

    When using as the lower end of a range, use ``time_snowflake(high=False) - 1``
    to be inclusive, ``high=True`` to be exclusive.

    When using as the higher end of a range, use ``time_snowflake(high=True) + 1``
    to be inclusive, ``high=False`` to be exclusive

    Parameters
    ----------
    dt: :class:`datetime.datetime`
        A datetime object to convert to a snowflake.
        If naive, the timezone is assumed to be local time.
    high: :class:`bool`
        Whether or not to set the lower 22 bit to high or low.

    Returns
    -------
    :class:`int`
        The snowflake representing the time given.
    """
    discord_millis = int(dt.timestamp() * 1000 - DISCORD_EPOCH)
    return (discord_millis << 22) + (2**22 - 1 if high else 0)


def find(predicate: Callable[[T], Any], seq: Iterable[T]) -> Optional[T]:
    """A helper to return the first element found in the sequence
    that meets the predicate. For example: ::

        member = disnake.utils.find(lambda m: m.name == 'Mighty', channel.guild.members)

    would find the first :class:`~disnake.Member` whose name is 'Mighty' and return it.
    If an entry is not found, then ``None`` is returned.

    This is different from :func:`py:filter` due to the fact it stops the moment it finds
    a valid entry.

    Parameters
    ----------
    predicate
        A function that returns a boolean-like result.
    seq: :class:`collections.abc.Iterable`
        The iterable to search through.
    """
    for element in seq:
        if predicate(element):
            return element
    return None


def get(iterable: Iterable[T], **attrs: Any) -> Optional[T]:
    """A helper that returns the first element in the iterable that meets
    all the traits passed in ``attrs``. This is an alternative for
    :func:`~disnake.utils.find`.

    When multiple attributes are specified, they are checked using
    logical AND, not logical OR. Meaning they have to meet every
    attribute passed in and not one of them.

    To have a nested attribute search (i.e. search by ``x.y``) then
    pass in ``x__y`` as the keyword argument.

    If nothing is found that matches the attributes passed, then
    ``None`` is returned.

    Examples
    --------
    Basic usage:

    .. code-block:: python3

        member = disnake.utils.get(message.guild.members, name='Foo')

    Multiple attribute matching:

    .. code-block:: python3

        channel = disnake.utils.get(guild.voice_channels, name='Foo', bitrate=64000)

    Nested attribute matching:

    .. code-block:: python3

        channel = disnake.utils.get(client.get_all_channels(), guild__name='Cool', name='general')

    Parameters
    ----------
    iterable
        An iterable to search through.
    **attrs
        Keyword arguments that denote attributes to search with.
    """
    # global -> local
    _all = all
    attrget = attrgetter

    # Special case the single element call
    if len(attrs) == 1:
        k, v = attrs.popitem()
        pred = attrget(k.replace("__", "."))
        for elem in iterable:
            if pred(elem) == v:
                return elem
        return None

    converted = [(attrget(attr.replace("__", ".")), value) for attr, value in attrs.items()]

    for elem in iterable:
        if _all(pred(elem) == value for pred, value in converted):
            return elem
    return None


def _unique(iterable: Iterable[T]) -> List[T]:
    return list(dict.fromkeys(iterable))


def _get_as_snowflake(data: Any, key: str) -> Optional[int]:
    try:
        value = data[key]
    except KeyError:
        return None
    else:
        return value and int(value)


def _maybe_cast(value: V, converter: Callable[[V], T], default: T = None) -> Optional[T]:
    if value is MISSING:
        return default
    return converter(value)


# stdlib mimetypes doesn't know webp in <3.11, so we ship
# our own map with the needed types
_mime_type_extensions = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def _get_mime_type_for_image(data: bytes) -> str:
    if data[0:8] == b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A":
        return "image/png"
    if data[0:3] == b"\xff\xd8\xff" or data[6:10] in (b"JFIF", b"Exif"):
        return "image/jpeg"
    if data[0:6] in (b"\x47\x49\x46\x38\x37\x61", b"\x47\x49\x46\x38\x39\x61"):
        return "image/gif"
    if data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("Unsupported image type given")


def _bytes_to_base64_data(data: bytes) -> str:
    fmt = "data:{mime};base64,{data}"
    mime = _get_mime_type_for_image(data)
    b64 = b64encode(data).decode("ascii")
    return fmt.format(mime=mime, data=b64)


def _get_extension_for_image(data: bytes) -> Optional[str]:
    try:
        mime_type = _get_mime_type_for_image(data)
    except ValueError:
        return None
    return _mime_type_extensions.get(mime_type)


@overload
async def _assetbytes_to_base64_data(data: None) -> None:
    ...


@overload
async def _assetbytes_to_base64_data(data: AssetBytes) -> str:
    ...


async def _assetbytes_to_base64_data(data: Optional[AssetBytes]) -> Optional[str]:
    if data is None:
        return None
    if not isinstance(data, (bytes, bytearray, memoryview)):
        data = await data.read()
    return _bytes_to_base64_data(data)


if HAS_ORJSON:

    def _to_json(obj: Any) -> str:
        return orjson.dumps(obj).decode("utf-8")

    _from_json = orjson.loads  # type: ignore

else:

    def _to_json(obj: Any) -> str:
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=True)

    _from_json = json.loads


def _parse_ratelimit_header(request: Any, *, use_clock: bool = False) -> float:
    reset_after: Optional[str] = request.headers.get("X-Ratelimit-Reset-After")
    if use_clock or not reset_after:
        utc = datetime.timezone.utc
        now = datetime.datetime.now(utc)
        reset = datetime.datetime.fromtimestamp(float(request.headers["X-Ratelimit-Reset"]), utc)
        return (reset - now).total_seconds()
    return float(reset_after)


async def maybe_coroutine(
    f: Callable[P, Union[Awaitable[T], T]], /, *args: P.args, **kwargs: P.kwargs
) -> T:
    value = f(*args, **kwargs)
    if _isawaitable(value):
        return await value
    return value  # type: ignore  # typeguard doesn't narrow in the negative case


async def async_all(gen: Iterable[Union[Awaitable[bool], bool]], *, check=_isawaitable) -> bool:
    for elem in gen:
        if check(elem):
            elem = await elem
        if not elem:
            return False
    return True


async def sane_wait_for(futures: Iterable[Awaitable[T]], *, timeout: float) -> Set[asyncio.Task[T]]:
    ensured = [asyncio.ensure_future(fut) for fut in futures]
    done, pending = await asyncio.wait(ensured, timeout=timeout, return_when=asyncio.ALL_COMPLETED)

    if len(pending) != 0:
        raise asyncio.TimeoutError

    return done


def get_slots(cls: Type[Any]) -> Iterator[str]:
    for mro in reversed(cls.__mro__):
        slots = getattr(mro, "__slots__", [])
        if isinstance(slots, str):
            yield slots
        else:
            yield from slots


def compute_timedelta(dt: datetime.datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.astimezone()
    now = utcnow()
    return max((dt - now).total_seconds(), 0)


async def sleep_until(when: datetime.datetime, result: Optional[T] = None) -> Optional[T]:
    """|coro|

    Sleep until a specified time.

    If the time supplied is in the past this function will yield instantly.

    .. versionadded:: 1.3

    Parameters
    ----------
    when: :class:`datetime.datetime`
        The timestamp in which to sleep until. If the datetime is naive then
        it is assumed to be local time.
    result: Any
        If provided, is returned to the caller when the coroutine completes.
    """
    delta = compute_timedelta(when)
    return await asyncio.sleep(delta, result)


def utcnow() -> datetime.datetime:
    """A helper function to return an aware UTC datetime representing the current time.

    This should be preferred to :meth:`datetime.datetime.utcnow` since it is an aware
    datetime, compared to the naive datetime in the standard library.

    .. versionadded:: 2.0

    Returns
    -------
    :class:`datetime.datetime`
        The current aware datetime in UTC.
    """
    return datetime.datetime.now(datetime.timezone.utc)


def valid_icon_size(size: int) -> bool:
    """Icons must be power of 2 within [16, 4096]."""
    return not size & (size - 1) and 4096 >= size >= 16


class SnowflakeList(array.array):
    """Internal data storage class to efficiently store a list of snowflakes.

    This should have the following characteristics:

    - Low memory usage
    - O(n) iteration (obviously)
    - O(n log n) initial creation if data is unsorted
    - O(log n) search and indexing
    - O(n) insertion
    """

    __slots__ = ()

    if TYPE_CHECKING:

        def __init__(self, data: Iterable[int], *, is_sorted: bool = False) -> None:
            ...

    def __new__(cls, data: Iterable[int], *, is_sorted: bool = False):
        return array.array.__new__(cls, "Q", data if is_sorted else sorted(data))  # type: ignore

    def add(self, element: int) -> None:
        i = bisect_left(self, element)
        self.insert(i, element)

    def get(self, element: int) -> Optional[int]:
        i = bisect_left(self, element)
        return self[i] if i != len(self) and self[i] == element else None

    def has(self, element: int) -> bool:
        i = bisect_left(self, element)
        return i != len(self) and self[i] == element


_IS_ASCII = re.compile(r"^[\x00-\x7f]+$")


def _string_width(string: str, *, _IS_ASCII=_IS_ASCII) -> int:
    """Returns string's width."""
    match = _IS_ASCII.match(string)
    if match:
        return match.endpos

    UNICODE_WIDE_CHAR_TYPE = "WFA"
    func = unicodedata.east_asian_width
    return sum(2 if func(char) in UNICODE_WIDE_CHAR_TYPE else 1 for char in string)


@overload
def resolve_invite(invite: Union[Invite, str], *, with_params: Literal[False] = False) -> str:
    ...


@overload
def resolve_invite(
    invite: Union[Invite, str], *, with_params: Literal[True]
) -> Tuple[str, Dict[str, str]]:
    ...


def resolve_invite(
    invite: Union[Invite, str], *, with_params: bool = False
) -> Union[str, Tuple[str, Dict[str, str]]]:
    """Resolves an invite from a :class:`~disnake.Invite`, URL or code.

    Parameters
    ----------
    invite: Union[:class:`~disnake.Invite`, :class:`str`]
        The invite to resolve.
    with_params: :class:`bool`
        Whether to also return the query parameters of the invite, if it's a url.

        .. versionadded:: 2.3

    Returns
    -------
    Union[:class:`str`, Tuple[:class:`str`, Dict[:class:`str`, :class:`str`]]]
        The invite code if ``with_params`` is ``False``, otherwise a tuple containing the
        invite code and the url's query parameters, if applicable.
    """
    from .invite import Invite  # circular import

    code = None
    params = {}
    if isinstance(invite, Invite):
        code = invite.code
    else:
        rx = r"(?:https?\:\/\/)?discord(?:\.gg|(?:app)?\.com\/invite)\/([^?]+)(?:\?(.+))?"
        m = re.match(rx, invite)
        if m:
            code, p = m.groups()
            if with_params:
                params = {k: v[0] for k, v in parse_qs(p or "").items()}
        else:
            code = invite
    return (code, params) if with_params else code


def resolve_template(code: Union[Template, str]) -> str:
    """Resolves a template code from a :class:`~disnake.Template`, URL or code.

    .. versionadded:: 1.4

    Parameters
    ----------
    code: Union[:class:`~disnake.Template`, :class:`str`]
        The code.

    Returns
    -------
    :class:`str`
        The template code.
    """
    from .template import Template  # circular import

    if isinstance(code, Template):
        return code.code
    rx = r"(?:https?\:\/\/)?discord(?:\.new|(?:app)?\.com\/template)\/(.+)"
    m = re.match(rx, code)
    if m:
        return m.group(1)
    return code


_MARKDOWN_ESCAPE_SUBREGEX = "|".join(
    r"\{0}(?=([\s\S]*((?<!\{0})\{0})))".format(c) for c in ("*", "`", "_", "~", "|")
)

_MARKDOWN_ESCAPE_COMMON = r"^>(?:>>)?\s|\[.+\]\(.+\)"

_MARKDOWN_ESCAPE_REGEX = re.compile(
    rf"(?P<markdown>{_MARKDOWN_ESCAPE_SUBREGEX}|{_MARKDOWN_ESCAPE_COMMON})", re.MULTILINE
)

_URL_REGEX = r"(?P<url><[^: >]+:\/[^ >]+>|(?:https?|steam):\/\/[^\s<]+[^<.,:;\"\'\]\s])"

_MARKDOWN_STOCK_REGEX = rf"(?P<markdown>[_\\~|\*`]|{_MARKDOWN_ESCAPE_COMMON})"


def remove_markdown(text: str, *, ignore_links: bool = True) -> str:
    """A helper function that removes markdown characters.

    .. versionadded:: 1.7

    .. note::
            This function is not markdown aware and may remove meaning from the original text. For example,
            if the input contains ``10 * 5`` then it will be converted into ``10  5``.

    Parameters
    ----------
    text: :class:`str`
        The text to remove markdown from.
    ignore_links: :class:`bool`
        Whether to leave links alone when removing markdown. For example,
        if a URL in the text contains characters such as ``_`` then it will
        be left alone. Defaults to ``True``.

    Returns
    -------
    :class:`str`
        The text with the markdown special characters removed.
    """

    def replacement(match):
        groupdict = match.groupdict()
        return groupdict.get("url", "")

    regex = _MARKDOWN_STOCK_REGEX
    if ignore_links:
        regex = f"(?:{_URL_REGEX}|{regex})"
    return re.sub(regex, replacement, text, 0, re.MULTILINE)


def escape_markdown(text: str, *, as_needed: bool = False, ignore_links: bool = True) -> str:
    """A helper function that escapes Discord's markdown.

    Parameters
    ----------
    text: :class:`str`
        The text to escape markdown from.
    as_needed: :class:`bool`
        Whether to escape the markdown characters as needed. This
        means that it does not escape extraneous characters if it's
        not necessary, e.g. ``**hello**`` is escaped into ``\\*\\*hello**``
        instead of ``\\*\\*hello\\*\\*``. Note however that this can open
        you up to some clever syntax abuse. Defaults to ``False``.
    ignore_links: :class:`bool`
        Whether to leave links alone when escaping markdown. For example,
        if a URL in the text contains characters such as ``_`` then it will
        be left alone. This option is not supported with ``as_needed``.
        Defaults to ``True``.

    Returns
    -------
    :class:`str`
        The text with the markdown special characters escaped with a slash.
    """
    if not as_needed:

        def replacement(match):
            groupdict = match.groupdict()
            is_url = groupdict.get("url")
            if is_url:
                return is_url
            return "\\" + groupdict["markdown"]

        regex = _MARKDOWN_STOCK_REGEX
        if ignore_links:
            regex = f"(?:{_URL_REGEX}|{regex})"
        return re.sub(regex, replacement, text, 0, re.MULTILINE)

    text = re.sub(r"\\", r"\\\\", text)
    return _MARKDOWN_ESCAPE_REGEX.sub(r"\\\1", text)


def escape_mentions(text: str) -> str:
    """A helper function that escapes everyone, here, role, and user mentions.

    .. note::

        This does not include channel mentions.

    .. note::

        For more granular control over what mentions should be escaped
        within messages, refer to the :class:`~disnake.AllowedMentions`
        class.

    Parameters
    ----------
    text: :class:`str`
        The text to escape mentions from.

    Returns
    -------
    :class:`str`
        The text with the mentions removed.
    """
    return re.sub(r"@(everyone|here|[!&]?[0-9]{17,19})", "@\u200b\\1", text)


# Custom docstring parser


class _DocstringLocalizationsMixin(TypedDict):
    localization_key_name: Optional[str]
    localization_key_desc: Optional[str]


class _DocstringParam(_DocstringLocalizationsMixin):
    name: str
    type: None
    description: str


class _ParsedDocstring(_DocstringLocalizationsMixin):
    description: str
    params: Dict[str, _DocstringParam]


def _count_left_spaces(string: str) -> int:
    res = 0
    for s in string:
        if not s.isspace():
            return res
        res += 1
    return res


def _get_header_line(lines: List[str], header: str, underline: str) -> int:
    underlining = len(header) * underline
    for i, line in enumerate(lines):
        if line.rstrip() == header and i + 1 < len(lines) and lines[i + 1].startswith(underlining):
            return i
    return len(lines)


def _get_next_header_line(lines: List[str], underline: str, start: int = 0) -> int:
    for idx, line in enumerate(lines[start:]):
        i = start + idx
        clean_line = line.rstrip()
        if (
            i > 0
            and len(clean_line) > 0
            and clean_line.count(underline) == len(clean_line)
            and _count_left_spaces(lines[i - 1]) == 0
            and len(lines[i - 1].rstrip()) <= len(clean_line)
        ):
            return i - 1
    return len(lines)


def _get_description(lines: List[str]) -> str:
    end = _get_next_header_line(lines, "-")
    return "\n".join(lines[:end]).strip()


def _extract_localization_key(desc: str) -> Tuple[str, Tuple[Optional[str], Optional[str]]]:
    match = re.search(r"\{\{(.*?)\}\}", desc)
    if match:
        desc = desc.replace(match.group(0), "").strip()
        loc_key = match.group(1).strip()
        return desc, (f"{loc_key}_NAME", f"{loc_key}_DESCRIPTION")
    return desc, (None, None)


def _get_option_desc(lines: List[str]) -> Dict[str, _DocstringParam]:
    start = _get_header_line(lines, "Parameters", "-") + 2
    end = _get_next_header_line(lines, "-", start)
    if start >= len(lines):
        return {}
    # Read option descriptions
    options: Dict[str, _DocstringParam] = {}

    def add_param(param: Optional[str], desc_lines: List[str], maybe_type: Optional[str]) -> None:
        if param is None:
            return
        desc: Optional[str] = None
        if desc_lines:
            desc = "\n".join(desc_lines)
        elif maybe_type:
            desc = maybe_type
        if desc is not None:
            desc, (loc_key_name, loc_key_desc) = _extract_localization_key(desc)
            # TODO: maybe parse types in the future
            options[param] = {
                "name": param,
                "type": None,
                "description": desc,
                "localization_key_name": loc_key_name,
                "localization_key_desc": loc_key_desc,
            }

    desc_lines: List[str] = []
    param: Optional[str] = None
    maybe_type: Optional[str] = None
    for line in lines[start:end]:
        spaces = _count_left_spaces(line)
        if spaces == 0:
            # Add previous param desc
            add_param(param, desc_lines, maybe_type)
            # Prepare new param desc
            if ":" in line:
                param, maybe_type = line.split(":", 1)
                param = param.strip()
                maybe_type = maybe_type.strip()
            else:
                param = line.strip()
                maybe_type = None
            desc_lines = []
        else:
            desc_lines.append(line.strip())
    # After the last iteration
    add_param(param, desc_lines, maybe_type)
    return options


def parse_docstring(func: Callable) -> _ParsedDocstring:
    doc = _getdoc(func)
    if doc is None:
        return {
            "description": "",
            "params": {},
            "localization_key_name": None,
            "localization_key_desc": None,
        }
    lines = doc.splitlines()
    desc, (loc_key_name, loc_key_desc) = _extract_localization_key(_get_description(lines))
    return {
        "description": desc,
        "localization_key_name": loc_key_name,
        "localization_key_desc": loc_key_desc,
        "params": _get_option_desc(lines),
    }


# Chunkers


def _chunk(iterator: Iterator[T], max_size: int) -> Iterator[List[T]]:
    ret = []
    n = 0
    for item in iterator:
        ret.append(item)
        n += 1
        if n == max_size:
            yield ret
            ret = []
            n = 0
    if ret:
        yield ret


async def _achunk(iterator: AsyncIterator[T], max_size: int) -> AsyncIterator[List[T]]:
    ret = []
    n = 0
    async for item in iterator:
        ret.append(item)
        n += 1
        if n == max_size:
            yield ret
            ret = []
            n = 0
    if ret:
        yield ret


@overload
def as_chunks(iterator: Iterator[T], max_size: int) -> Iterator[List[T]]:
    ...


@overload
def as_chunks(iterator: AsyncIterator[T], max_size: int) -> AsyncIterator[List[T]]:
    ...


def as_chunks(iterator: _Iter[T], max_size: int) -> _Iter[List[T]]:
    """A helper function that collects an iterator into chunks of a given size.

    .. versionadded:: 2.0

    Parameters
    ----------
    iterator: Union[:class:`collections.abc.Iterator`, :class:`collections.abc.AsyncIterator`]
        The iterator to chunk, can be sync or async.
    max_size: :class:`int`
        The maximum chunk size.


    .. warning::

        The last chunk collected may not be as large as ``max_size``.

    Returns
    -------
    Union[:class:`Iterator`, :class:`AsyncIterator`]
        A new iterator which yields chunks of a given size.
    """
    if max_size <= 0:
        raise ValueError("Chunk sizes must be greater than 0.")

    if isinstance(iterator, AsyncIterator):
        return _achunk(iterator, max_size)
    return _chunk(iterator, max_size)


if sys.version_info >= (3, 10):
    PY_310 = True
    from types import UnionType
else:
    PY_310 = False
    UnionType = object()


def flatten_literal_params(parameters: Iterable[Any]) -> Tuple[Any, ...]:
    params = []
    for p in parameters:
        if get_origin(p) is Literal:
            params.extend(_unique(flatten_literal_params(p.__args__)))
        else:
            params.append(p)
    return tuple(params)


def normalise_optional_params(parameters: Iterable[Any]) -> Tuple[Any, ...]:
    none_cls = type(None)
    return tuple(p for p in parameters if p is not none_cls) + (none_cls,)


def evaluate_annotation(
    tp: Any,
    globals: Dict[str, Any],
    locals: Dict[str, Any],
    cache: Dict[str, Any],
    *,
    implicit_str: bool = True,
):
    if isinstance(tp, ForwardRef):
        tp = tp.__forward_arg__
        # ForwardRefs always evaluate their internals
        implicit_str = True

    if implicit_str and isinstance(tp, str):
        if tp in cache:
            return cache[tp]
        evaluated = eval(  # noqa: PGH001 # this is how annotations are supposed to be unstringifed
            tp, globals, locals
        )
        cache[tp] = evaluated
        return evaluate_annotation(evaluated, globals, locals, cache)

    if hasattr(tp, "__args__"):
        implicit_str = True
        is_literal = False
        orig_args = args = tp.__args__
        if not hasattr(tp, "__origin__"):
            if tp.__class__ is UnionType:
                converted = Union[args]  # type: ignore
                return evaluate_annotation(converted, globals, locals, cache)

            return tp
        if tp.__origin__ is Union:
            try:
                if args.index(type(None)) != len(args) - 1:
                    args = normalise_optional_params(tp.__args__)
            except ValueError:
                pass
        if tp.__origin__ is Literal:
            if not PY_310:
                args = flatten_literal_params(tp.__args__)
            implicit_str = False
            is_literal = True

        evaluated_args = tuple(
            evaluate_annotation(arg, globals, locals, cache, implicit_str=implicit_str)
            for arg in args
        )

        if is_literal and not all(
            isinstance(x, (str, int, bool, type(None))) for x in evaluated_args
        ):
            raise TypeError("Literal arguments must be of type str, int, bool, or NoneType.")

        if evaluated_args == orig_args:
            return tp

        try:
            return tp.copy_with(evaluated_args)
        except AttributeError:
            return tp.__origin__[evaluated_args]

    return tp


def resolve_annotation(
    annotation: Any,
    globalns: Dict[str, Any],
    localns: Optional[Dict[str, Any]],
    cache: Optional[Dict[str, Any]],
) -> Any:
    if annotation is None:
        return type(None)
    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)

    locals = globalns if localns is None else localns
    if cache is None:
        cache = {}
    return evaluate_annotation(annotation, globalns, locals, cache)


TimestampStyle = Literal["f", "F", "d", "D", "t", "T", "R"]


def format_dt(dt: Union[datetime.datetime, float], /, style: TimestampStyle = "f") -> str:
    """A helper function to format a :class:`datetime.datetime`, :class:`int` or :class:`float` for presentation within Discord.

    This allows for a locale-independent way of presenting data using Discord specific Markdown.

    +-------------+----------------------------+-----------------+
    |    Style    |       Example Output       |   Description   |
    +=============+============================+=================+
    | t           | 22:57                      | Short Time      |
    +-------------+----------------------------+-----------------+
    | T           | 22:57:58                   | Long Time       |
    +-------------+----------------------------+-----------------+
    | d           | 17/05/2016                 | Short Date      |
    +-------------+----------------------------+-----------------+
    | D           | 17 May 2016                | Long Date       |
    +-------------+----------------------------+-----------------+
    | f (default) | 17 May 2016 22:57          | Short Date Time |
    +-------------+----------------------------+-----------------+
    | F           | Tuesday, 17 May 2016 22:57 | Long Date Time  |
    +-------------+----------------------------+-----------------+
    | R           | 5 years ago                | Relative Time   |
    +-------------+----------------------------+-----------------+

    Note that the exact output depends on the user's locale setting in the client. The example output
    presented is using the ``en-GB`` locale.

    .. versionadded:: 2.0

    Parameters
    ----------
    dt: Union[:class:`datetime.datetime`, :class:`int`, :class:`float`]
        The datetime to format.
        If this is a naive datetime, it is assumed to be local time.
    style: :class:`str`
        The style to format the datetime with. Defaults to ``f``

    Returns
    -------
    :class:`str`
        The formatted string.
    """
    if isinstance(dt, datetime.datetime):
        dt = dt.timestamp()
    return f"<t:{int(dt)}:{style}>"


def search_directory(path: str) -> Iterator[str]:
    """Walk through a directory and yield all modules.

    Parameters
    ----------
    path: :class:`str`
        The path to search for modules

    Yields
    ------
    :class:`str`
        The name of the found module. (usable in load_extension)
    """
    relpath = os.path.relpath(path)  # relative and normalized
    if ".." in relpath:
        raise ValueError("Modules outside the cwd require a package to be specified")

    abspath = os.path.abspath(path)
    if not os.path.exists(relpath):
        raise ValueError(f"Provided path '{abspath}' does not exist")
    if not os.path.isdir(relpath):
        raise ValueError(f"Provided path '{abspath}' is not a directory")

    prefix = relpath.replace(os.sep, ".")
    if prefix in ("", "."):
        prefix = ""
    else:
        prefix += "."

    for _, name, ispkg in pkgutil.iter_modules([path]):
        if ispkg:
            yield from search_directory(os.path.join(path, name))
        else:
            yield prefix + name


def as_valid_locale(locale: str) -> Optional[str]:
    """Converts the provided locale name to a name that is valid for use with the API,
    for example by returning ``en-US`` for ``en_US``.
    Returns ``None`` for invalid names.

    .. versionadded:: 2.5

    Parameters
    ----------
    locale: :class:`str`
        The input locale name.
    """
    # check for key first (e.g. `en_US`)
    if locale_type := Locale.__members__.get(locale):
        return locale_type.value

    # check for value (e.g. `en-US`)
    try:
        Locale(locale)
    except ValueError:
        pass
    else:
        return locale

    # didn't match, try language without country code (e.g. `en` instead of `en-US`)
    language = re.split(r"[-_]", locale)[0]
    if language != locale:
        return as_valid_locale(language)
    return None


def humanize_list(values: List[str], combine: str) -> str:
    if len(values) > 2:
        return f"{', '.join(values[:-1])}, {combine} {values[-1]}"
    if len(values) == 0:
        return "<none>"
    return f" {combine} ".join(values)


# Similar to typing.assert_never, but returns instead of raising (i.e. has no runtime effect).
# This is only to avoid "unreachable code", which pyright doesn't type-check.
def assert_never(arg: Never, /) -> None:
    pass


# n.b. This must be imported and used as @ _overload_with_permissions (without the space)
# this is used by the libcst parser and has no runtime purpose
# it is merely a marker not unlike pytest.mark
def _overload_with_permissions(func: T) -> T:
    return func


# this is used as a marker for functions or classes that were created by codemodding
def _generated(func: T) -> T:
    return func
