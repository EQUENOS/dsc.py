# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import traceback
import types
import warnings
from datetime import datetime, timedelta
from errno import ECONNRESET
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    Generator,
    List,
    Literal,
    Mapping,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
    overload,
)

import aiohttp

from . import abc, utils
from .activity import ActivityTypes, BaseActivity, create_activity
from .app_commands import (
    APIMessageCommand,
    APISlashCommand,
    APIUserCommand,
    ApplicationCommand,
    GuildApplicationCommandPermissions,
)
from .appinfo import AppInfo, InstallParams
from .application_role_connection import ApplicationRoleConnectionMetadata
from .backoff import ExponentialBackoff
from .channel import PartialMessageable, _threaded_channel_factory
from .emoji import Emoji
from .entitlement import Entitlement
from .enums import ApplicationCommandType, ChannelType, Event, Status
from .errors import (
    ConnectionClosed,
    GatewayNotFound,
    HTTPException,
    InvalidData,
    PrivilegedIntentsRequired,
    SessionStartLimitReached,
)
from .flags import ApplicationFlags, Intents, MemberCacheFlags
from .gateway import DiscordWebSocket, ReconnectWebSocket
from .guild import Guild, GuildBuilder
from .guild_preview import GuildPreview
from .http import HTTPClient
from .i18n import LocalizationProtocol, LocalizationStore
from .invite import Invite
from .iterators import EntitlementIterator, GuildIterator
from .mentions import AllowedMentions
from .object import Object
from .sku import SKU
from .stage_instance import StageInstance
from .state import ConnectionState
from .sticker import GuildSticker, StandardSticker, StickerPack, _sticker_factory
from .template import Template
from .threads import Thread
from .ui.view import View
from .user import ClientUser, User
from .utils import MISSING, deprecated
from .voice_client import VoiceClient
from .voice_region import VoiceRegion
from .webhook import Webhook
from .widget import Widget

if TYPE_CHECKING:
    from typing_extensions import NotRequired

    from .abc import GuildChannel, PrivateChannel, Snowflake, SnowflakeTime
    from .app_commands import APIApplicationCommand, MessageCommand, SlashCommand, UserCommand
    from .asset import AssetBytes
    from .channel import DMChannel
    from .member import Member
    from .message import Message
    from .types.application_role_connection import (
        ApplicationRoleConnectionMetadata as ApplicationRoleConnectionMetadataPayload,
    )
    from .types.gateway import SessionStartLimit as SessionStartLimitPayload
    from .voice_client import VoiceProtocol


__all__ = (
    "Client",
    "SessionStartLimit",
    "GatewayParams",
)

T = TypeVar("T")

Coro = Coroutine[Any, Any, T]
CoroFunc = Callable[..., Coro[Any]]

CoroT = TypeVar("CoroT", bound=Callable[..., Coroutine[Any, Any, Any]])

_log = logging.getLogger(__name__)


def _cancel_tasks(loop: asyncio.AbstractEventLoop) -> None:
    tasks = {t for t in asyncio.all_tasks(loop=loop) if not t.done()}

    if not tasks:
        return

    _log.info("Cleaning up after %d tasks.", len(tasks))
    for task in tasks:
        task.cancel()

    loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
    _log.info("All tasks finished cancelling.")

    for task in tasks:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler(
                {
                    "message": "Unhandled exception during Client.run shutdown.",
                    "exception": task.exception(),
                    "task": task,
                }
            )


def _cleanup_loop(loop: asyncio.AbstractEventLoop) -> None:
    try:
        _cancel_tasks(loop)
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        _log.info("Closing the event loop.")
        loop.close()


class SessionStartLimit:
    """A class that contains information about the current session start limit,
    at the time when the client connected for the first time.

    .. versionadded:: 2.5

    Attributes
    ----------
    total: :class:`int`
        The total number of allowed session starts.
    remaining: :class:`int`
        The remaining number of allowed session starts.
    reset_after: :class:`int`
        The number of milliseconds after which the :attr:`.remaining` limit resets,
        relative to when the client connected.
        See also :attr:`reset_time`.
    max_concurrency: :class:`int`
        The number of allowed ``IDENTIFY`` requests per 5 seconds.
    reset_time: :class:`datetime.datetime`
        The approximate time at which which the :attr:`.remaining` limit resets.
    """

    __slots__: Tuple[str, ...] = (
        "total",
        "remaining",
        "reset_after",
        "max_concurrency",
        "reset_time",
    )

    def __init__(self, data: SessionStartLimitPayload) -> None:
        self.total: int = data["total"]
        self.remaining: int = data["remaining"]
        self.reset_after: int = data["reset_after"]
        self.max_concurrency: int = data["max_concurrency"]

        self.reset_time: datetime = utils.utcnow() + timedelta(milliseconds=self.reset_after)

    def __repr__(self) -> str:
        return (
            f"<SessionStartLimit total={self.total!r} remaining={self.remaining!r} "
            f"reset_after={self.reset_after!r} max_concurrency={self.max_concurrency!r} reset_time={self.reset_time!s}>"
        )


class GatewayParams(NamedTuple):
    """Container type for configuring gateway connections.

    .. versionadded:: 2.6

    Parameters
    ----------
    encoding: :class:`str`
        The payload encoding (``json`` is currently the only supported encoding).
        Defaults to ``"json"``.
    zlib: :class:`bool`
        Whether to enable transport compression.
        Defaults to ``True``.
    """

    encoding: Literal["json"] = "json"
    zlib: bool = True


# used for typing the ws parameter dict in the connect() loop
class _WebSocketParams(TypedDict):
    initial: bool
    shard_id: Optional[int]
    gateway: Optional[str]

    sequence: NotRequired[Optional[int]]
    resume: NotRequired[bool]
    session: NotRequired[Optional[str]]


class Client:
    """Represents a client connection that connects to Discord.
    This class is used to interact with the Discord WebSocket and API.

    A number of options can be passed to the :class:`Client`.

    Parameters
    ----------
    max_messages: Optional[:class:`int`]
        The maximum number of messages to store in the internal message cache.
        This defaults to ``1000``. Passing in ``None`` disables the message cache.

        .. versionchanged:: 1.3
            Allow disabling the message cache and change the default size to ``1000``.
    loop: Optional[:class:`asyncio.AbstractEventLoop`]
        The :class:`asyncio.AbstractEventLoop` to use for asynchronous operations.
        Defaults to ``None``, in which case the default event loop is used via
        :func:`asyncio.get_event_loop()`.
    asyncio_debug: :class:`bool`
        Whether to enable asyncio debugging when the client starts.
        Defaults to False.
    connector: Optional[:class:`aiohttp.BaseConnector`]
        The connector to use for connection pooling.
    proxy: Optional[:class:`str`]
        Proxy URL.
    proxy_auth: Optional[:class:`aiohttp.BasicAuth`]
        An object that represents proxy HTTP Basic Authorization.
    shard_id: Optional[:class:`int`]
        Integer starting at ``0`` and less than :attr:`.shard_count`.
    shard_count: Optional[:class:`int`]
        The total number of shards.
    application_id: :class:`int`
        The client's application ID.
    intents: Optional[:class:`Intents`]
        The intents that you want to enable for the session. This is a way of
        disabling and enabling certain gateway events from triggering and being sent.
        If not given, defaults to a regularly constructed :class:`Intents` class.

        .. versionadded:: 1.5

    member_cache_flags: :class:`MemberCacheFlags`
        Allows for finer control over how the library caches members.
        If not given, defaults to cache as much as possible with the
        currently selected intents.

        .. versionadded:: 1.5

    chunk_guilds_at_startup: :class:`bool`
        Indicates if :func:`.on_ready` should be delayed to chunk all guilds
        at start-up if necessary. This operation is incredibly slow for large
        amounts of guilds. The default is ``True`` if :attr:`Intents.members`
        is ``True``.

        .. versionadded:: 1.5

    status: Optional[Union[class:`str`, :class:`.Status`]]
        A status to start your presence with upon logging on to Discord.
    activity: Optional[:class:`.BaseActivity`]
        An activity to start your presence with upon logging on to Discord.
    allowed_mentions: Optional[:class:`AllowedMentions`]
        Control how the client handles mentions by default on every message sent.

        .. versionadded:: 1.4

    heartbeat_timeout: :class:`float`
        The maximum numbers of seconds before timing out and restarting the
        WebSocket in the case of not receiving a HEARTBEAT_ACK. Useful if
        processing the initial packets take too long to the point of disconnecting
        you. The default timeout is 60 seconds.
    guild_ready_timeout: :class:`float`
        The maximum number of seconds to wait for the GUILD_CREATE stream to end before
        preparing the member cache and firing READY. The default timeout is 2 seconds.

        .. versionadded:: 1.4

    assume_unsync_clock: :class:`bool`
        Whether to assume the system clock is unsynced. This applies to the ratelimit handling
        code. If this is set to ``True``, the default, then the library uses the time to reset
        a rate limit bucket given by Discord. If this is ``False`` then your system clock is
        used to calculate how long to sleep for. If this is set to ``False`` it is recommended to
        sync your system clock to Google's NTP server.

        .. versionadded:: 1.3

    enable_debug_events: :class:`bool`
        Whether to enable events that are useful only for debugging gateway related information.

        Right now this involves :func:`on_socket_raw_receive` and :func:`on_socket_raw_send`. If
        this is ``False`` then those events will not be dispatched (due to performance considerations).
        To enable these events, this must be set to ``True``. Defaults to ``False``.

        .. versionadded:: 2.0

    enable_gateway_error_handler: :class:`bool`
        Whether to enable the :func:`disnake.on_gateway_error` event.
        Defaults to ``True``.

        If this is disabled, exceptions that occur while parsing (known) gateway events
        won't be handled and the pre-v2.6 behavior of letting the exception propagate up to
        the :func:`connect`/:func:`start`/:func:`run` call is used instead.

        .. versionadded:: 2.6

    localization_provider: :class:`.LocalizationProtocol`
        An implementation of :class:`.LocalizationProtocol` to use for localization of
        application commands.
        If not provided, the default :class:`.LocalizationStore` implementation is used.

        .. versionadded:: 2.5

        .. versionchanged:: 2.6
            Can no longer be provided together with ``strict_localization``, as it does
            not apply to the custom localization provider entered in this parameter.

    strict_localization: :class:`bool`
        Whether to raise an exception when localizations for a specific key couldn't be found.
        This is mainly useful for testing/debugging, consider disabling this eventually
        as missing localized names will automatically fall back to the default/base name without it.
        Only applicable if the ``localization_provider`` parameter is not provided.
        Defaults to ``False``.

        .. versionadded:: 2.5

        .. versionchanged:: 2.6
            Can no longer be provided together with ``localization_provider``, as this parameter is
            ignored for custom localization providers.

    gateway_params: :class:`.GatewayParams`
        Allows configuring parameters used for establishing gateway connections,
        notably enabling/disabling compression (enabled by default).
        Encodings other than JSON are not supported.

        .. versionadded:: 2.6

    Attributes
    ----------
    ws
        The websocket gateway the client is currently connected to. Could be ``None``.
    loop: :class:`asyncio.AbstractEventLoop`
        The event loop that the client uses for asynchronous operations.
    session_start_limit: Optional[:class:`SessionStartLimit`]
        Information about the current session start limit.
        Only available after initiating the connection.

        .. versionadded:: 2.5
    i18n: :class:`.LocalizationProtocol`
        An implementation of :class:`.LocalizationProtocol` used for localization of
        application commands.

        .. versionadded:: 2.5
    """

    def __init__(
        self,
        *,
        asyncio_debug: bool = False,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        shard_id: Optional[int] = None,
        shard_count: Optional[int] = None,
        enable_debug_events: bool = False,
        enable_gateway_error_handler: bool = True,
        localization_provider: Optional[LocalizationProtocol] = None,
        strict_localization: bool = False,
        gateway_params: Optional[GatewayParams] = None,
        connector: Optional[aiohttp.BaseConnector] = None,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        assume_unsync_clock: bool = True,
        max_messages: Optional[int] = 1000,
        application_id: Optional[int] = None,
        heartbeat_timeout: float = 60.0,
        guild_ready_timeout: float = 2.0,
        allowed_mentions: Optional[AllowedMentions] = None,
        activity: Optional[BaseActivity] = None,
        status: Optional[Union[Status, str]] = None,
        intents: Optional[Intents] = None,
        chunk_guilds_at_startup: Optional[bool] = None,
        member_cache_flags: Optional[MemberCacheFlags] = None,
    ) -> None:
        # self.ws is set in the connect method
        self.ws: DiscordWebSocket = None  # type: ignore

        if loop is None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        else:
            self.loop: asyncio.AbstractEventLoop = loop

        self.loop.set_debug(asyncio_debug)
        self._listeners: Dict[str, List[Tuple[asyncio.Future, Callable[..., bool]]]] = {}
        self.session_start_limit: Optional[SessionStartLimit] = None

        self.http: HTTPClient = HTTPClient(
            connector,
            proxy=proxy,
            proxy_auth=proxy_auth,
            unsync_clock=assume_unsync_clock,
            loop=self.loop,
        )

        self._handlers: Dict[str, Callable] = {
            "ready": self._handle_ready,
            "connect_internal": self._handle_first_connect,
        }

        self._hooks: Dict[str, Callable] = {"before_identify": self._call_before_identify_hook}

        self._enable_debug_events: bool = enable_debug_events
        self._enable_gateway_error_handler: bool = enable_gateway_error_handler
        self._connection: ConnectionState = self._get_state(
            max_messages=max_messages,
            application_id=application_id,
            heartbeat_timeout=heartbeat_timeout,
            guild_ready_timeout=guild_ready_timeout,
            allowed_mentions=allowed_mentions,
            activity=activity,
            status=status,
            intents=intents,
            chunk_guilds_at_startup=chunk_guilds_at_startup,
            member_cache_flags=member_cache_flags,
        )
        self.shard_id: Optional[int] = shard_id
        self.shard_count: Optional[int] = shard_count
        self._connection.shard_count = shard_count

        self._closed: bool = False
        self._ready: asyncio.Event = asyncio.Event()
        self._first_connect: asyncio.Event = asyncio.Event()
        self._connection._get_websocket = self._get_websocket
        self._connection._get_client = lambda: self

        if VoiceClient.warn_nacl:
            VoiceClient.warn_nacl = False
            _log.warning("PyNaCl is not installed, voice will NOT be supported")

        if strict_localization and localization_provider is not None:
            raise ValueError(
                "Providing both `localization_provider` and `strict_localization` is not supported."
                " If strict localization is desired for a customized localization provider, this"
                " should be implemented by that custom provider."
            )

        self.i18n: LocalizationProtocol = (
            LocalizationStore(strict=strict_localization)
            if localization_provider is None
            else localization_provider
        )

        self.gateway_params: GatewayParams = gateway_params or GatewayParams()
        if self.gateway_params.encoding != "json":
            raise ValueError("Gateway encodings other than `json` are currently not supported.")

        self.extra_events: Dict[str, List[CoroFunc]] = {}

    # internals

    def _get_websocket(
        self, guild_id: Optional[int] = None, *, shard_id: Optional[int] = None
    ) -> DiscordWebSocket:
        return self.ws

    def _get_state(
        self,
        *,
        max_messages: Optional[int],
        application_id: Optional[int],
        heartbeat_timeout: float,
        guild_ready_timeout: float,
        allowed_mentions: Optional[AllowedMentions],
        activity: Optional[BaseActivity],
        status: Optional[Union[str, Status]],
        intents: Optional[Intents],
        chunk_guilds_at_startup: Optional[bool],
        member_cache_flags: Optional[MemberCacheFlags],
    ) -> ConnectionState:
        return ConnectionState(
            dispatch=self.dispatch,
            handlers=self._handlers,
            hooks=self._hooks,
            http=self.http,
            loop=self.loop,
            max_messages=max_messages,
            application_id=application_id,
            heartbeat_timeout=heartbeat_timeout,
            guild_ready_timeout=guild_ready_timeout,
            allowed_mentions=allowed_mentions,
            activity=activity,
            status=status,
            intents=intents,
            chunk_guilds_at_startup=chunk_guilds_at_startup,
            member_cache_flags=member_cache_flags,
        )

    def _handle_ready(self) -> None:
        self._ready.set()

    def _handle_first_connect(self) -> None:
        if self._first_connect.is_set():
            return
        self._first_connect.set()

    @property
    def latency(self) -> float:
        """:class:`float`: Measures latency between a HEARTBEAT and a HEARTBEAT_ACK in seconds.

        This could be referred to as the Discord WebSocket protocol latency.
        """
        ws = self.ws
        return float("nan") if not ws else ws.latency

    def is_ws_ratelimited(self) -> bool:
        """Whether the websocket is currently rate limited.

        This can be useful to know when deciding whether you should query members
        using HTTP or via the gateway.

        .. versionadded:: 1.6

        :return type: :class:`bool`
        """
        if self.ws:
            return self.ws.is_ratelimited()
        return False

    @property
    def user(self) -> ClientUser:
        """Optional[:class:`.ClientUser`]: Represents the connected client. ``None`` if not logged in."""
        return self._connection.user

    @property
    def guilds(self) -> List[Guild]:
        """List[:class:`.Guild`]: The guilds that the connected client is a member of."""
        return self._connection.guilds

    @property
    def emojis(self) -> List[Emoji]:
        """List[:class:`.Emoji`]: The emojis that the connected client has."""
        return self._connection.emojis

    @property
    def stickers(self) -> List[GuildSticker]:
        """List[:class:`.GuildSticker`]: The stickers that the connected client has.

        .. versionadded:: 2.0
        """
        return self._connection.stickers

    @property
    def cached_messages(self) -> Sequence[Message]:
        """Sequence[:class:`.Message`]: Read-only list of messages the connected client has cached.

        .. versionadded:: 1.1
        """
        return utils.SequenceProxy(self._connection._messages or [])

    @property
    def private_channels(self) -> List[PrivateChannel]:
        """List[:class:`.abc.PrivateChannel`]: The private channels that the connected client is participating on.

        .. note::

            This returns only up to 128 most recent private channels due to an internal working
            on how Discord deals with private channels.
        """
        return self._connection.private_channels

    @property
    def voice_clients(self) -> List[VoiceProtocol]:
        """List[:class:`.VoiceProtocol`]: Represents a list of voice connections.

        These are usually :class:`.VoiceClient` instances.
        """
        return self._connection.voice_clients

    @property
    def application_id(self) -> int:
        """Optional[:class:`int`]: The client's application ID.

        If this is not passed via ``__init__`` then this is retrieved
        through the gateway when an event contains the data. Usually
        after :func:`~disnake.on_connect` is called.

        .. versionadded:: 2.0
        """
        return self._connection.application_id  # type: ignore

    @property
    def application_flags(self) -> ApplicationFlags:
        """:class:`~disnake.ApplicationFlags`: The client's application flags.

        .. versionadded:: 2.0
        """
        return self._connection.application_flags

    @property
    def global_application_commands(self) -> List[APIApplicationCommand]:
        """List[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]: The client's global application commands."""
        return list(self._connection._global_application_commands.values())

    @property
    def global_slash_commands(self) -> List[APISlashCommand]:
        """List[:class:`.APISlashCommand`]: The client's global slash commands."""
        return [
            cmd
            for cmd in self._connection._global_application_commands.values()
            if isinstance(cmd, APISlashCommand)
        ]

    @property
    def global_user_commands(self) -> List[APIUserCommand]:
        """List[:class:`.APIUserCommand`]: The client's global user commands."""
        return [
            cmd
            for cmd in self._connection._global_application_commands.values()
            if isinstance(cmd, APIUserCommand)
        ]

    @property
    def global_message_commands(self) -> List[APIMessageCommand]:
        """List[:class:`.APIMessageCommand`]: The client's global message commands."""
        return [
            cmd
            for cmd in self._connection._global_application_commands.values()
            if isinstance(cmd, APIMessageCommand)
        ]

    def get_message(self, id: int) -> Optional[Message]:
        """Gets the message with the given ID from the bot's message cache.

        Parameters
        ----------
        id: :class:`int`
            The ID of the message to look for.

        Returns
        -------
        Optional[:class:`.Message`]
            The corresponding message.
        """
        return utils.get(self.cached_messages, id=id)

    @overload
    async def get_or_fetch_user(
        self, user_id: int, *, strict: Literal[False] = ...
    ) -> Optional[User]:
        ...

    @overload
    async def get_or_fetch_user(self, user_id: int, *, strict: Literal[True]) -> User:
        ...

    async def get_or_fetch_user(self, user_id: int, *, strict: bool = False) -> Optional[User]:
        """|coro|

        Tries to get the user from the cache. If it fails,
        fetches the user from the API.

        This only propagates exceptions when the ``strict`` parameter is enabled.

        Parameters
        ----------
        user_id: :class:`int`
            The ID to search for.
        strict: :class:`bool`
            Whether to propagate exceptions from :func:`fetch_user`
            instead of returning ``None`` in case of failure
            (e.g. if the user wasn't found).
            Defaults to ``False``.

        Returns
        -------
        Optional[:class:`~disnake.User`]
            The user with the given ID, or ``None`` if not found and ``strict`` is set to ``False``.
        """
        user = self.get_user(user_id)
        if user is not None:
            return user
        try:
            user = await self.fetch_user(user_id)
        except Exception:
            if strict:
                raise
            return None
        return user

    getch_user = get_or_fetch_user

    def is_ready(self) -> bool:
        """Whether the client's internal cache is ready for use.

        :return type: :class:`bool`
        """
        return self._ready.is_set()

    async def _run_event(
        self,
        coro: Callable[..., Coroutine[Any, Any, Any]],
        event_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        try:
            await coro(*args, **kwargs)
        except asyncio.CancelledError:
            pass
        except Exception:
            try:
                await self.on_error(event_name, *args, **kwargs)
            except asyncio.CancelledError:
                pass

    def _schedule_event(
        self,
        coro: Callable[..., Coroutine[Any, Any, Any]],
        event_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> asyncio.Task:
        wrapped = self._run_event(coro, event_name, *args, **kwargs)
        # Schedules the task
        return asyncio.create_task(wrapped, name=f"disnake: {event_name}")

    def dispatch(self, event: str, *args: Any, **kwargs: Any) -> None:
        _log.debug("Dispatching event %s", event)
        method = "on_" + event

        listeners = self._listeners.get(event)
        if listeners:
            removed = []
            for i, (future, condition) in enumerate(listeners):
                if future.cancelled():
                    removed.append(i)
                    continue

                try:
                    result = condition(*args)
                except Exception as exc:
                    future.set_exception(exc)
                    removed.append(i)
                else:
                    if result:
                        if len(args) == 0:
                            future.set_result(None)
                        elif len(args) == 1:
                            future.set_result(args[0])
                        else:
                            future.set_result(args)
                        removed.append(i)

            if len(removed) == len(listeners):
                self._listeners.pop(event)
            else:
                for idx in reversed(removed):
                    del listeners[idx]

        try:
            coro = getattr(self, method)
        except AttributeError:
            pass
        else:
            self._schedule_event(coro, method, *args, **kwargs)

        for event_ in self.extra_events.get(method, []):
            self._schedule_event(event_, method, *args, **kwargs)

    def add_listener(self, func: CoroFunc, name: Union[str, Event] = MISSING) -> None:
        """The non decorator alternative to :meth:`.listen`.

        .. versionchanged:: 2.10
            The definition of this method was moved from :class:`.ext.commands.Bot`
            to the :class:`.Client` class.

        Parameters
        ----------
        func: :ref:`coroutine <coroutine>`
            The function to call.
        name: Union[:class:`str`, :class:`.Event`]
            The name of the event to listen for. Defaults to ``func.__name__``.

        Example
        --------

        .. code-block:: python

            async def on_ready(): pass
            async def my_message(message): pass
            async def another_message(message): pass

            client.add_listener(on_ready)
            client.add_listener(my_message, 'on_message')
            client.add_listener(another_message, Event.message)

        Raises
        ------
        TypeError
            The function is not a coroutine or a string or an :class:`.Event` was not passed
            as the name.
        """
        if name is not MISSING and not isinstance(name, (str, Event)):
            raise TypeError(
                f"add_listener expected str or Enum but received {name.__class__.__name__!r} instead."
            )

        name_ = (
            func.__name__
            if name is MISSING
            else (name if isinstance(name, str) else f"on_{name.value}")
        )

        if not asyncio.iscoroutinefunction(func):
            raise TypeError("Listeners must be coroutines")

        if name_ in self.extra_events:
            self.extra_events[name_].append(func)
        else:
            self.extra_events[name_] = [func]

    def remove_listener(self, func: CoroFunc, name: Union[str, Event] = MISSING) -> None:
        """Removes a listener from the pool of listeners.

        .. versionchanged:: 2.10
            The definition of this method was moved from :class:`.ext.commands.Bot`
            to the :class:`.Client` class.

        Parameters
        ----------
        func
            The function that was used as a listener to remove.
        name: Union[:class:`str`, :class:`.Event`]
            The name of the event we want to remove. Defaults to
            ``func.__name__``.

        Raises
        ------
        TypeError
            The name passed was not a string or an :class:`.Event`.
        """
        if name is not MISSING and not isinstance(name, (str, Event)):
            raise TypeError(
                f"remove_listener expected str or Enum but received {name.__class__.__name__!r} instead."
            )
        name = (
            func.__name__
            if name is MISSING
            else (name if isinstance(name, str) else f"on_{name.value}")
        )

        if name in self.extra_events:
            try:
                self.extra_events[name].remove(func)
            except ValueError:
                pass

    def listen(self, name: Union[str, Event] = MISSING) -> Callable[[CoroT], CoroT]:
        """A decorator that registers another function as an external
        event listener. Basically this allows you to listen to multiple
        events from different places e.g. such as :func:`.on_ready`

        The functions being listened to must be a :ref:`coroutine <coroutine>`.

        .. versionchanged:: 2.10
            The definition of this method was moved from :class:`.ext.commands.Bot`
            to the :class:`.Client` class.

        Example
        -------
        .. code-block:: python3

            @client.listen()
            async def on_message(message):
                print('one')

            # in some other file...

            @client.listen('on_message')
            async def my_message(message):
                print('two')

            # in yet another file
            @client.listen(Event.message)
            async def another_message(message):
                print('three')

        Would print one, two and three in an unspecified order.

        Raises
        ------
        TypeError
            The function being listened to is not a coroutine or a string or an :class:`.Event` was not passed
            as the name.
        """
        if name is not MISSING and not isinstance(name, (str, Event)):
            raise TypeError(
                f"listen expected str or Enum but received {name.__class__.__name__!r} instead."
            )

        def decorator(func: CoroT) -> CoroT:
            self.add_listener(func, name)
            return func

        return decorator

    def get_listeners(self) -> Mapping[str, List[CoroFunc]]:
        """Mapping[:class:`str`, List[Callable]]: A read-only mapping of event names to listeners.

        .. note::
            To add or remove a listener you should use :meth:`.add_listener` and
            :meth:`.remove_listener`.

        .. versionchanged:: 2.10
            The definition of this method was moved from :class:`.ext.commands.Bot`
            to the :class:`.Client` class.
        """
        return types.MappingProxyType(self.extra_events)

    async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
        """|coro|

        The default error handler provided by the client.

        By default this prints to :data:`sys.stderr` however it could be
        overridden to have a different implementation.
        Check :func:`~disnake.on_error` for more details.
        """
        print(f"Ignoring exception in {event_method}", file=sys.stderr)
        traceback.print_exc()

    async def _dispatch_gateway_error(
        self, event: str, data: Any, shard_id: Optional[int], exc: Exception, /
    ) -> None:
        # This is an internal hook that calls the public one,
        # enabling additional handling while still allowing users to
        # overwrite `on_gateway_error`.
        # Even though this is always meant to be an async func, we use `maybe_coroutine`
        # just in case the client gets subclassed and the method is overwritten with a sync one.
        await utils.maybe_coroutine(self.on_gateway_error, event, data, shard_id, exc)

    async def on_gateway_error(
        self, event: str, data: Any, shard_id: Optional[int], exc: Exception, /
    ) -> None:
        """|coro|

        The default gateway error handler provided by the client.

        By default this prints to :data:`sys.stderr` however it could be
        overridden to have a different implementation.
        Check :func:`~disnake.on_gateway_error` for more details.

        .. versionadded:: 2.6

        .. note::
            Unlike :func:`on_error`, the exception is available as the ``exc``
            parameter and cannot be obtained through :func:`sys.exc_info`.
        """
        print(
            f"Ignoring exception in {event} gateway event handler (shard ID {shard_id})",
            file=sys.stderr,
        )
        traceback.print_exception(type(exc), exc, exc.__traceback__)

    # hooks

    async def _call_before_identify_hook(
        self, shard_id: Optional[int], *, initial: bool = False
    ) -> None:
        # This hook is an internal hook that actually calls the public one.
        # It allows the library to have its own hook without stepping on the
        # toes of those who need to override their own hook.
        await self.before_identify_hook(shard_id, initial=initial)

    async def before_identify_hook(self, shard_id: Optional[int], *, initial: bool = False) -> None:
        """|coro|

        A hook that is called before IDENTIFYing a session. This is useful
        if you wish to have more control over the synchronization of multiple
        IDENTIFYing clients.

        The default implementation sleeps for 5 seconds.

        .. versionadded:: 1.4

        Parameters
        ----------
        shard_id: :class:`int`
            The shard ID that requested being IDENTIFY'd
        initial: :class:`bool`
            Whether this IDENTIFY is the first initial IDENTIFY.
        """
        if not initial:
            await asyncio.sleep(5.0)

    # login state management

    async def login(self, token: str) -> None:
        """|coro|

        Logs in the client with the specified credentials.

        Parameters
        ----------
        token: :class:`str`
            The authentication token. Do not prefix this token with
            anything as the library will do it for you.

        Raises
        ------
        LoginFailure
            The wrong credentials are passed.
        HTTPException
            An unknown HTTP related error occurred,
            usually when it isn't 200 or the known incorrect credentials
            passing status code.
        """
        _log.info("logging in using static token")
        if not isinstance(token, str):
            raise TypeError(f"token must be of type str, got {type(token).__name__} instead")

        data = await self.http.static_login(token.strip())
        self._connection.user = ClientUser(state=self._connection, data=data)

    async def connect(
        self, *, reconnect: bool = True, ignore_session_start_limit: bool = False
    ) -> None:
        """|coro|

        Creates a websocket connection and lets the websocket listen
        to messages from Discord. This is a loop that runs the entire
        event system and miscellaneous aspects of the library. Control
        is not resumed until the WebSocket connection is terminated.

        .. versionchanged:: 2.6
            Added usage of :class:`.SessionStartLimit` when connecting to the API.
            Added the ``ignore_session_start_limit`` parameter.


        Parameters
        ----------
        reconnect: :class:`bool`
            Whether reconnecting should be attempted, either due to internet
            failure or a specific failure on Discord's part. Certain
            disconnects that lead to bad state will not be handled (such as
            invalid sharding payloads or bad tokens).

        ignore_session_start_limit: :class:`bool`
            Whether the API provided session start limit should be ignored when
            connecting to the API.

            .. versionadded:: 2.6

        Raises
        ------
        GatewayNotFound
            If the gateway to connect to Discord is not found. Usually if this
            is thrown then there is a Discord API outage.
        ConnectionClosed
            The websocket connection has been terminated.
        SessionStartLimitReached
            If the client doesn't have enough connects remaining in the current 24-hour window
            and ``ignore_session_start_limit`` is ``False`` this will be raised rather than
            connecting to the gateawy and Discord resetting the token.
            However, if ``ignore_session_start_limit`` is ``True``, the client will connect regardless
            and this exception will not be raised.
        """
        _, initial_gateway, session_start_limit = await self.http.get_bot_gateway(
            encoding=self.gateway_params.encoding,
            zlib=self.gateway_params.zlib,
        )
        self.session_start_limit = SessionStartLimit(session_start_limit)

        if not ignore_session_start_limit and self.session_start_limit.remaining == 0:
            raise SessionStartLimitReached(self.session_start_limit)

        ws_params: _WebSocketParams = {
            "initial": True,
            "shard_id": self.shard_id,
            "gateway": initial_gateway,
        }

        backoff = ExponentialBackoff()
        while not self.is_closed():
            # "connecting" in this case means "waiting for HELLO"
            connecting = True

            try:
                coro = DiscordWebSocket.from_client(self, **ws_params)
                self.ws = await asyncio.wait_for(coro, timeout=60.0)

                # If we got to this point:
                # - connection was established
                # - received a HELLO
                # - and sent an IDENTIFY or RESUME
                connecting = False
                ws_params["initial"] = False

                while True:
                    await self.ws.poll_event()

            except ReconnectWebSocket as e:
                _log.info("Got a request to %s the websocket.", e.op)
                self.dispatch("disconnect")
                ws_params.update(
                    sequence=self.ws.sequence,
                    resume=e.resume,
                    session=self.ws.session_id,
                    # use current (possibly new) gateway if resuming,
                    # reset to default if not
                    gateway=self.ws.resume_gateway if e.resume else initial_gateway,
                )
                continue

            except (
                OSError,
                HTTPException,
                GatewayNotFound,
                ConnectionClosed,
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as exc:
                self.dispatch("disconnect")
                if not reconnect:
                    await self.close()
                    if isinstance(exc, ConnectionClosed) and exc.code == 1000:
                        # clean close, don't re-raise this
                        return
                    raise

                if self.is_closed():
                    return

                # If we get connection reset by peer then try to RESUME
                if isinstance(exc, OSError) and exc.errno == ECONNRESET:
                    ws_params.update(
                        sequence=self.ws.sequence,
                        initial=False,
                        resume=True,
                        session=self.ws.session_id,
                        gateway=self.ws.resume_gateway,
                    )
                    continue

                # We should only get this when an unhandled close code happens,
                # such as a clean disconnect (1000) or a bad state (bad token, no sharding, etc)
                # sometimes, Discord sends us 1000 for unknown reasons so we should reconnect
                # regardless and rely on is_closed instead
                if isinstance(exc, ConnectionClosed):
                    if exc.code == 4014:
                        raise PrivilegedIntentsRequired(exc.shard_id) from None
                    if exc.code != 1000:
                        await self.close()
                        raise

                retry = backoff.delay()
                _log.exception("Attempting a reconnect in %.2fs", retry)
                await asyncio.sleep(retry)

                if connecting:
                    # Always identify back to the initial gateway if we failed while connecting.
                    # This is in case we fail to connect to the resume_gateway instance.
                    ws_params.update(
                        resume=False,
                        gateway=initial_gateway,
                    )
                else:
                    # Just try to resume the session.
                    # If it's not RESUME-able then the gateway will invalidate the session.
                    # This is apparently what the official Discord client does.
                    ws_params.update(
                        sequence=self.ws.sequence,
                        resume=True,
                        session=self.ws.session_id,
                        gateway=self.ws.resume_gateway,
                    )

    async def close(self) -> None:
        """|coro|

        Closes the connection to Discord.
        """
        if self._closed:
            return

        self._closed = True

        for voice in self.voice_clients:
            try:
                await voice.disconnect(force=True)
            except Exception:
                # if an error happens during disconnects, disregard it.
                pass

        # can be None if not connected
        if self.ws is not None and self.ws.open:  # pyright: ignore[reportUnnecessaryComparison]
            await self.ws.close(code=1000)

        await self.http.close()
        self._ready.clear()

    def clear(self) -> None:
        """Clears the internal state of the bot.

        After this, the bot can be considered "re-opened", i.e. :meth:`is_closed`
        and :meth:`is_ready` both return ``False`` along with the bot's internal
        cache cleared.
        """
        self._closed = False
        self._ready.clear()
        self._connection.clear()
        self.http.recreate()

    async def start(
        self, token: str, *, reconnect: bool = True, ignore_session_start_limit: bool = False
    ) -> None:
        """|coro|

        A shorthand coroutine for :meth:`login` + :meth:`connect`.

        Raises
        ------
        TypeError
            An unexpected keyword argument was received.
        """
        await self.login(token)
        await self.connect(
            reconnect=reconnect, ignore_session_start_limit=ignore_session_start_limit
        )

    def run(self, *args: Any, **kwargs: Any) -> None:
        """A blocking call that abstracts away the event loop
        initialisation from you.

        If you want more control over the event loop then this
        function should not be used. Use :meth:`start` coroutine
        or :meth:`connect` + :meth:`login`.

        Roughly Equivalent to: ::

            try:
                loop.run_until_complete(start(*args, **kwargs))
            except KeyboardInterrupt:
                loop.run_until_complete(close())
                # cancel all tasks lingering
            finally:
                loop.close()

        .. warning::

            This function must be the last function to call due to the fact that it
            is blocking. That means that registration of events or anything being
            called after this function call will not execute until it returns

        Parameters
        ----------
        token: :class:`str`
            The discord token of the bot that is being ran.
        """
        loop = self.loop

        try:
            loop.add_signal_handler(signal.SIGINT, lambda: loop.stop())
            loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
        except NotImplementedError:
            pass

        async def runner() -> None:
            try:
                await self.start(*args, **kwargs)
            finally:
                if not self.is_closed():
                    await self.close()

        def stop_loop_on_completion(f) -> None:
            loop.stop()

        future = asyncio.ensure_future(runner(), loop=loop)
        future.add_done_callback(stop_loop_on_completion)
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            _log.info("Received signal to terminate bot and event loop.")
        finally:
            future.remove_done_callback(stop_loop_on_completion)
            _log.info("Cleaning up tasks.")
            _cleanup_loop(loop)

        if not future.cancelled():
            try:
                return future.result()
            except KeyboardInterrupt:
                # I am unsure why this gets raised here but suppress it anyway
                return None

    # properties

    def is_closed(self) -> bool:
        """Whether the websocket connection is closed.

        :return type: :class:`bool`
        """
        return self._closed

    @property
    def activity(self) -> Optional[ActivityTypes]:
        """Optional[:class:`.BaseActivity`]: The activity being used upon logging in."""
        return create_activity(self._connection._activity, state=self._connection)

    @activity.setter
    def activity(self, value: Optional[ActivityTypes]) -> None:
        if value is None:
            self._connection._activity = None
        elif isinstance(value, BaseActivity):
            # ConnectionState._activity is typehinted as ActivityPayload, we're passing Dict[str, Any]
            self._connection._activity = value.to_dict()  # type: ignore
        else:
            raise TypeError("activity must derive from BaseActivity.")

    @property
    def status(self):
        """:class:`.Status`: The status being used upon logging on to Discord.

        .. versionadded:: 2.0
        """
        if self._connection._status in {state.value for state in Status}:
            return Status(self._connection._status)
        return Status.online

    @status.setter
    def status(self, value) -> None:
        if value is Status.offline:
            self._connection._status = "invisible"
        elif isinstance(value, Status):
            self._connection._status = str(value)
        else:
            raise TypeError("status must derive from Status.")

    @property
    def allowed_mentions(self) -> Optional[AllowedMentions]:
        """Optional[:class:`~disnake.AllowedMentions`]: The allowed mention configuration.

        .. versionadded:: 1.4
        """
        return self._connection.allowed_mentions

    @allowed_mentions.setter
    def allowed_mentions(self, value: Optional[AllowedMentions]) -> None:
        if value is None or isinstance(value, AllowedMentions):
            self._connection.allowed_mentions = value
        else:
            raise TypeError(f"allowed_mentions must be AllowedMentions not {value.__class__!r}")

    @property
    def intents(self) -> Intents:
        """:class:`~disnake.Intents`: The intents configured for this connection.

        .. versionadded:: 1.5
        """
        return self._connection.intents

    # helpers/getters

    @property
    def users(self) -> List[User]:
        """List[:class:`~disnake.User`]: Returns a list of all the users the bot can see."""
        return list(self._connection._users.values())

    def get_channel(self, id: int, /) -> Optional[Union[GuildChannel, Thread, PrivateChannel]]:
        """Returns a channel or thread with the given ID.

        Parameters
        ----------
        id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[Union[:class:`.abc.GuildChannel`, :class:`.Thread`, :class:`.abc.PrivateChannel`]]
            The returned channel or ``None`` if not found.
        """
        return self._connection.get_channel(id)

    def get_partial_messageable(
        self, id: int, *, type: Optional[ChannelType] = None
    ) -> PartialMessageable:
        """Returns a partial messageable with the given channel ID.

        This is useful if you have a channel_id but don't want to do an API call
        to send messages to it.

        .. versionadded:: 2.0

        Parameters
        ----------
        id: :class:`int`
            The channel ID to create a partial messageable for.
        type: Optional[:class:`.ChannelType`]
            The underlying channel type for the partial messageable.

        Returns
        -------
        :class:`.PartialMessageable`
            The partial messageable
        """
        return PartialMessageable(state=self._connection, id=id, type=type)

    def get_stage_instance(self, id: int, /) -> Optional[StageInstance]:
        """Returns a stage instance with the given stage channel ID.

        .. versionadded:: 2.0

        Parameters
        ----------
        id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`.StageInstance`]
            The returns stage instance or ``None`` if not found.
        """
        from .channel import StageChannel

        channel = self._connection.get_channel(id)

        if isinstance(channel, StageChannel):
            return channel.instance

    def get_guild(self, id: int, /) -> Optional[Guild]:
        """Returns a guild with the given ID.

        Parameters
        ----------
        id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`.Guild`]
            The guild or ``None`` if not found.
        """
        return self._connection._get_guild(id)

    def get_user(self, id: int, /) -> Optional[User]:
        """Returns a user with the given ID.

        Parameters
        ----------
        id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`~disnake.User`]
            The user or ``None`` if not found.
        """
        return self._connection.get_user(id)

    def get_emoji(self, id: int, /) -> Optional[Emoji]:
        """Returns an emoji with the given ID.

        Parameters
        ----------
        id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`.Emoji`]
            The custom emoji or ``None`` if not found.
        """
        return self._connection.get_emoji(id)

    def get_sticker(self, id: int, /) -> Optional[GuildSticker]:
        """Returns a guild sticker with the given ID.

        .. versionadded:: 2.0

        .. note::

            To retrieve standard stickers, use :meth:`.fetch_sticker`.
            or :meth:`.fetch_sticker_packs`.

        Returns
        -------
        Optional[:class:`.GuildSticker`]
            The sticker or ``None`` if not found.
        """
        return self._connection.get_sticker(id)

    def get_all_channels(self) -> Generator[GuildChannel, None, None]:
        """A generator that retrieves every :class:`.abc.GuildChannel` the client can 'access'.

        This is equivalent to: ::

            for guild in client.guilds:
                for channel in guild.channels:
                    yield channel

        .. note::

            Just because you receive a :class:`.abc.GuildChannel` does not mean that
            you can communicate in said channel. :meth:`.abc.GuildChannel.permissions_for` should
            be used for that.

        Yields
        ------
        :class:`.abc.GuildChannel`
            A channel the client can 'access'.
        """
        for guild in self.guilds:
            yield from guild.channels

    def get_all_members(self) -> Generator[Member, None, None]:
        """Returns a generator with every :class:`.Member` the client can see.

        This is equivalent to: ::

            for guild in client.guilds:
                for member in guild.members:
                    yield member

        Yields
        ------
        :class:`.Member`
            A member the client can see.
        """
        for guild in self.guilds:
            yield from guild.members

    def get_guild_application_commands(self, guild_id: int) -> List[APIApplicationCommand]:
        """Returns a list of all application commands in the guild with the given ID.

        Parameters
        ----------
        guild_id: :class:`int`
            The ID to search for.

        Returns
        -------
        List[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            The list of application commands.
        """
        data = self._connection._guild_application_commands.get(guild_id, {})
        return list(data.values())

    def get_guild_slash_commands(self, guild_id: int) -> List[APISlashCommand]:
        """Returns a list of all slash commands in the guild with the given ID.

        Parameters
        ----------
        guild_id: :class:`int`
            The ID to search for.

        Returns
        -------
        List[:class:`.APISlashCommand`]
            The list of slash commands.
        """
        data = self._connection._guild_application_commands.get(guild_id, {})
        return [cmd for cmd in data.values() if isinstance(cmd, APISlashCommand)]

    def get_guild_user_commands(self, guild_id: int) -> List[APIUserCommand]:
        """Returns a list of all user commands in the guild with the given ID.

        Parameters
        ----------
        guild_id: :class:`int`
            The ID to search for.

        Returns
        -------
        List[:class:`.APIUserCommand`]
            The list of user commands.
        """
        data = self._connection._guild_application_commands.get(guild_id, {})
        return [cmd for cmd in data.values() if isinstance(cmd, APIUserCommand)]

    def get_guild_message_commands(self, guild_id: int) -> List[APIMessageCommand]:
        """Returns a list of all message commands in the guild with the given ID.

        Parameters
        ----------
        guild_id: :class:`int`
            The ID to search for.

        Returns
        -------
        List[:class:`.APIMessageCommand`]
            The list of message commands.
        """
        data = self._connection._guild_application_commands.get(guild_id, {})
        return [cmd for cmd in data.values() if isinstance(cmd, APIMessageCommand)]

    def get_global_command(self, id: int) -> Optional[APIApplicationCommand]:
        """Returns a global application command with the given ID.

        Parameters
        ----------
        id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            The application command.
        """
        return self._connection._get_global_application_command(id)

    def get_guild_command(self, guild_id: int, id: int) -> Optional[APIApplicationCommand]:
        """Returns a guild application command with the given guild ID and application command ID.

        Parameters
        ----------
        guild_id: :class:`int`
            The guild ID to search for.
        id: :class:`int`
            The command ID to search for.

        Returns
        -------
        Optional[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            The application command.
        """
        return self._connection._get_guild_application_command(guild_id, id)

    def get_global_command_named(
        self, name: str, cmd_type: Optional[ApplicationCommandType] = None
    ) -> Optional[APIApplicationCommand]:
        """Returns a global application command matching the given name.

        Parameters
        ----------
        name: :class:`str`
            The name to look for.
        cmd_type: :class:`.ApplicationCommandType`
            The type to look for. By default, no types are checked.

        Returns
        -------
        Optional[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            The application command.
        """
        return self._connection._get_global_command_named(name, cmd_type)

    def get_guild_command_named(
        self, guild_id: int, name: str, cmd_type: Optional[ApplicationCommandType] = None
    ) -> Optional[APIApplicationCommand]:
        """Returns a guild application command matching the given name.

        Parameters
        ----------
        guild_id: :class:`int`
            The guild ID to search for.
        name: :class:`str`
            The command name to search for.
        cmd_type: :class:`.ApplicationCommandType`
            The type to look for. By default, no types are checked.

        Returns
        -------
        Optional[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            The application command.
        """
        return self._connection._get_guild_command_named(guild_id, name, cmd_type)

    # listeners/waiters

    async def wait_until_ready(self) -> None:
        """|coro|

        Waits until the client's internal cache is all ready.
        """
        await self._ready.wait()

    async def wait_until_first_connect(self) -> None:
        """|coro|

        Waits until the first connect.
        """
        await self._first_connect.wait()

    def wait_for(
        self,
        event: Union[str, Event],
        *,
        check: Optional[Callable[..., bool]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """|coro|

        Waits for a WebSocket event to be dispatched.

        This could be used to wait for a user to reply to a message,
        or to react to a message, or to edit a message in a self-contained
        way.

        The ``timeout`` parameter is passed onto :func:`asyncio.wait_for`. By default,
        it does not timeout. Note that this does propagate the
        :exc:`asyncio.TimeoutError` for you in case of timeout and is provided for
        ease of use.

        In case the event returns multiple arguments, a :class:`tuple` containing those
        arguments is returned instead. Please check the
        :ref:`documentation <disnake_api_events>` for a list of events and their
        parameters.

        This function returns the **first event that meets the requirements**.

        Examples
        --------
        Waiting for a user reply: ::

            @client.event
            async def on_message(message):
                if message.content.startswith('$greet'):
                    channel = message.channel
                    await channel.send('Say hello!')

                    def check(m):
                        return m.content == 'hello' and m.channel == channel

                    msg = await client.wait_for('message', check=check)
                    await channel.send(f'Hello {msg.author}!')

            # using events enums:
            @client.event
            async def on_message(message):
                if message.content.startswith('$greet'):
                    channel = message.channel
                    await channel.send('Say hello!')

                    def check(m):
                        return m.content == 'hello' and m.channel == channel

                    msg = await client.wait_for(Event.message, check=check)
                    await channel.send(f'Hello {msg.author}!')

        Waiting for a thumbs up reaction from the message author: ::

            @client.event
            async def on_message(message):
                if message.content.startswith('$thumb'):
                    channel = message.channel
                    await channel.send('Send me that \N{THUMBS UP SIGN} reaction, mate')

                    def check(reaction, user):
                        return user == message.author and str(reaction.emoji) == '\N{THUMBS UP SIGN}'

                    try:
                        reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check)
                    except asyncio.TimeoutError:
                        await channel.send('\N{THUMBS DOWN SIGN}')
                    else:
                        await channel.send('\N{THUMBS UP SIGN}')


        Parameters
        ----------
        event: Union[:class:`str`, :class:`.Event`]
            The event name, similar to the :ref:`event reference <disnake_api_events>`,
            but without the ``on_`` prefix, to wait for. It's recommended
            to use :class:`.Event`.
        check: Optional[Callable[..., :class:`bool`]]
            A predicate to check what to wait for. The arguments must meet the
            parameters of the event being waited for.
        timeout: Optional[:class:`float`]
            The number of seconds to wait before timing out and raising
            :exc:`asyncio.TimeoutError`.

        Raises
        ------
        asyncio.TimeoutError
            If a timeout is provided and it was reached.

        Returns
        -------
        Any
            Returns no arguments, a single argument, or a :class:`tuple` of multiple
            arguments that mirrors the parameters passed in the
            :ref:`event <disnake_api_events>`.
        """
        future = self.loop.create_future()
        if check is None:

            def _check(*args) -> bool:
                return True

            check = _check

        ev = event.lower() if isinstance(event, str) else event.value
        try:
            listeners = self._listeners[ev]
        except KeyError:
            listeners = []
            self._listeners[ev] = listeners

        listeners.append((future, check))
        return asyncio.wait_for(future, timeout)

    # event registration

    def event(self, coro: CoroT) -> CoroT:
        """A decorator that registers an event to listen to.

        You can find more info about the events in the :ref:`documentation <disnake_api_events>`.

        The events must be a :ref:`coroutine <coroutine>`, if not, :exc:`TypeError` is raised.

        Example
        -------
        .. code-block:: python3

            @client.event
            async def on_ready():
                print('Ready!')

        Raises
        ------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError("event registered must be a coroutine function")

        setattr(self, coro.__name__, coro)
        _log.debug("%s has successfully been registered as an event", coro.__name__)
        return coro

    async def change_presence(
        self,
        *,
        activity: Optional[BaseActivity] = None,
        status: Optional[Status] = None,
    ) -> None:
        """|coro|

        Changes the client's presence.

        .. versionchanged:: 2.0
            Removed the ``afk`` keyword-only parameter.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Example
        ---------

        .. code-block:: python3

            game = disnake.Game("with the API")
            await client.change_presence(status=disnake.Status.idle, activity=game)

        Parameters
        ----------
        activity: Optional[:class:`.BaseActivity`]
            The activity being done. ``None`` if no currently active activity is done.
        status: Optional[:class:`.Status`]
            Indicates what status to change to. If ``None``, then
            :attr:`.Status.online` is used.

        Raises
        ------
        TypeError
            If the ``activity`` parameter is not the proper type.
        """
        if status is None:
            status_str = "online"
            status = Status.online
        elif status is Status.offline:
            status_str = "invisible"
            status = Status.offline
        else:
            status_str = str(status)

        await self.ws.change_presence(activity=activity, status=status_str)

        activities = () if activity is None else (activity,)
        for guild in self._connection.guilds:
            me = guild.me
            if me is None:  # pyright: ignore[reportUnnecessaryComparison]
                # may happen if guild is unavailable
                continue

            # Member.activities is typehinted as Tuple[ActivityType, ...], we may be setting it as Tuple[BaseActivity, ...]
            me.activities = activities  # type: ignore
            me.status = status

    # Guild stuff

    def fetch_guilds(
        self,
        *,
        limit: Optional[int] = 100,
        before: Optional[SnowflakeTime] = None,
        after: Optional[SnowflakeTime] = None,
        with_counts: bool = True,
    ) -> GuildIterator:
        """Retrieves an :class:`.AsyncIterator` that enables receiving your guilds.

        .. note::

            Using this, you will only receive :attr:`.Guild.id`, :attr:`.Guild.name`,
            :attr:`.Guild.features`, :attr:`.Guild.icon`, and :attr:`.Guild.banner` per :class:`.Guild`.

        .. note::

            This method is an API call. For general usage, consider :attr:`guilds` instead.

        Examples
        --------
        Usage ::

            async for guild in client.fetch_guilds(limit=150):
                print(guild.name)

        Flattening into a list ::

            guilds = await client.fetch_guilds(limit=150).flatten()
            # guilds is now a list of Guild...

        All parameters are optional.

        Parameters
        ----------
        limit: Optional[:class:`int`]
            The number of guilds to retrieve.
            If ``None``, it retrieves every guild you have access to. Note, however,
            that this would make it a slow operation.
            Defaults to ``100``.
        before: Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]
            Retrieves guilds before this date or object.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        after: Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]
            Retrieve guilds after this date or object.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        with_counts: :class:`bool`
            Whether to include approximate member and presence counts for the guilds.
            Defaults to ``True``.

            .. versionadded:: 2.10

        Raises
        ------
        HTTPException
            Retrieving the guilds failed.

        Yields
        ------
        :class:`.Guild`
            The guild with the guild data parsed.
        """
        return GuildIterator(self, limit=limit, before=before, after=after, with_counts=with_counts)

    async def fetch_template(self, code: Union[Template, str]) -> Template:
        """|coro|

        Retrieves a :class:`.Template` from a discord.new URL or code.

        Parameters
        ----------
        code: Union[:class:`.Template`, :class:`str`]
            The Discord Template Code or URL (must be a discord.new URL).

        Raises
        ------
        NotFound
            The template is invalid.
        HTTPException
            Retrieving the template failed.

        Returns
        -------
        :class:`.Template`
            The template from the URL/code.
        """
        code = utils.resolve_template(code)
        data = await self.http.get_template(code)
        return Template(data=data, state=self._connection)

    async def fetch_guild(self, guild_id: int, /, *, with_counts: bool = True) -> Guild:
        """|coro|

        Retrieves a :class:`.Guild` from the given ID.

        .. note::

            Using this, you will **not** receive :attr:`.Guild.channels`, :attr:`.Guild.members`,
            :attr:`.Member.activity` and :attr:`.Member.voice` per :class:`.Member`.

        .. note::

            This method is an API call. For general usage, consider :meth:`get_guild` instead.

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild to retrieve.
        with_counts: :class:`bool`
            Whether to include approximate member and presence counts for the guild.
            Defaults to ``True``.

            .. versionadded:: 2.10

        Raises
        ------
        Forbidden
            You do not have access to the guild.
        HTTPException
            Retrieving the guild failed.

        Returns
        -------
        :class:`.Guild`
            The guild from the given ID.
        """
        data = await self.http.get_guild(guild_id, with_counts=with_counts)
        return Guild(data=data, state=self._connection)

    async def fetch_guild_preview(
        self,
        guild_id: int,
        /,
    ) -> GuildPreview:
        """|coro|

         Retrieves a :class:`.GuildPreview` from the given ID. Your bot does not have to be in this guild.

        .. note::

            This method may fetch any guild that has ``DISCOVERABLE`` in :attr:`.Guild.features`,
            but this information can not be known ahead of time.

            This will work for any guild that you are in.

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild to to retrieve a preview object.

        Raises
        ------
        NotFound
            Retrieving the guild preview failed.

        Returns
        -------
        :class:`.GuildPreview`
            The guild preview from the given ID.
        """
        data = await self.http.get_guild_preview(guild_id)
        return GuildPreview(data=data, state=self._connection)

    async def create_guild(
        self,
        *,
        name: str,
        icon: AssetBytes = MISSING,
        code: str = MISSING,
    ) -> Guild:
        """|coro|

        Creates a :class:`.Guild`.

        See :func:`guild_builder` for a more comprehensive alternative.

        Bot accounts in 10 or more guilds are not allowed to create guilds.

        .. note::

            Using this, you will **not** receive :attr:`.Guild.channels`, :attr:`.Guild.members`,
            :attr:`.Member.activity` and :attr:`.Member.voice` per :class:`.Member`.

        .. versionchanged:: 2.5
            Removed the ``region`` parameter.

        .. versionchanged:: 2.6
            Raises :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The name of the guild.
        icon: |resource_type|
            The icon of the guild.
            See :meth:`.ClientUser.edit` for more details on what is expected.

            .. versionchanged:: 2.5
                Now accepts various resource types in addition to :class:`bytes`.

        code: :class:`str`
            The code for a template to create the guild with.

            .. versionadded:: 1.4

        Raises
        ------
        NotFound
            The ``icon`` asset couldn't be found.
        HTTPException
            Guild creation failed.
        ValueError
            Invalid icon image format given. Must be PNG or JPG.
        TypeError
            The ``icon`` asset is a lottie sticker (see :func:`Sticker.read <disnake.Sticker.read>`).

        Returns
        -------
        :class:`.Guild`
            The created guild. This is not the same guild that is added to cache.
        """
        if icon is not MISSING:
            icon_base64 = await utils._assetbytes_to_base64_data(icon)
        else:
            icon_base64 = None

        if code:
            data = await self.http.create_from_template(code, name, icon_base64)
        else:
            data = await self.http.create_guild(name, icon_base64)
        return Guild(data=data, state=self._connection)

    def guild_builder(self, name: str) -> GuildBuilder:
        """Creates a builder object that can be used to create more complex guilds.

        This is a more comprehensive alternative to :func:`create_guild`.
        See :class:`.GuildBuilder` for details and examples.

        Bot accounts in 10 or more guilds are not allowed to create guilds.

        .. note::

            Using this, you will **not** receive :attr:`.Guild.channels`, :attr:`.Guild.members`,
            :attr:`.Member.activity` and :attr:`.Member.voice` per :class:`.Member`.

        .. versionadded:: 2.8

        Parameters
        ----------
        name: :class:`str`
            The name of the guild.

        Returns
        -------
        :class:`.GuildBuilder`
            The guild builder object for configuring and creating a new guild.
        """
        return GuildBuilder(name=name, state=self._connection)

    async def fetch_stage_instance(self, channel_id: int, /) -> StageInstance:
        """|coro|

        Retrieves a :class:`.StageInstance` with the given ID.

        .. note::

            This method is an API call. For general usage, consider :meth:`get_stage_instance` instead.

        .. versionadded:: 2.0

        Parameters
        ----------
        channel_id: :class:`int`
            The stage channel ID.

        Raises
        ------
        NotFound
            The stage instance or channel could not be found.
        HTTPException
            Retrieving the stage instance failed.

        Returns
        -------
        :class:`.StageInstance`
            The stage instance from the given ID.
        """
        data = await self.http.get_stage_instance(channel_id)
        guild = self.get_guild(int(data["guild_id"]))
        return StageInstance(guild=guild, state=self._connection, data=data)  # type: ignore

    # Invite management

    async def fetch_invite(
        self,
        url: Union[Invite, str],
        *,
        with_counts: bool = True,
        with_expiration: bool = True,
        guild_scheduled_event_id: Optional[int] = None,
    ) -> Invite:
        """|coro|

        Retrieves an :class:`.Invite` from a discord.gg URL or ID.

        .. note::

            If the invite is for a guild you have not joined, the guild and channel
            attributes of the returned :class:`.Invite` will be :class:`.PartialInviteGuild` and
            :class:`.PartialInviteChannel` respectively.

        Parameters
        ----------
        url: Union[:class:`.Invite`, :class:`str`]
            The Discord invite ID or URL (must be a discord.gg URL).
        with_counts: :class:`bool`
            Whether to include count information in the invite. This fills the
            :attr:`.Invite.approximate_member_count` and :attr:`.Invite.approximate_presence_count`
            fields.
        with_expiration: :class:`bool`
            Whether to include the expiration date of the invite. This fills the
            :attr:`.Invite.expires_at` field.

            .. versionadded:: 2.0

        guild_scheduled_event_id: :class:`int`
            The ID of the scheduled event to include in the invite.
            If not provided, defaults to the ``event`` parameter in the URL if it exists,
            or the ID of the scheduled event contained in the provided invite object.

            .. versionadded:: 2.3

        Raises
        ------
        NotFound
            The invite has expired or is invalid.
        HTTPException
            Retrieving the invite failed.

        Returns
        -------
        :class:`.Invite`
            The invite from the URL/ID.
        """
        invite_id, params = utils.resolve_invite(url, with_params=True)

        if not guild_scheduled_event_id:
            # keep scheduled event ID from invite url/object
            if "event" in params:
                guild_scheduled_event_id = int(params["event"])
            elif isinstance(url, Invite) and url.guild_scheduled_event:
                guild_scheduled_event_id = url.guild_scheduled_event.id

        data = await self.http.get_invite(
            invite_id,
            with_counts=with_counts,
            with_expiration=with_expiration,
            guild_scheduled_event_id=guild_scheduled_event_id,
        )
        return Invite.from_incomplete(state=self._connection, data=data)

    async def delete_invite(self, invite: Union[Invite, str]) -> None:
        """|coro|

        Revokes an :class:`.Invite`, URL, or ID to an invite.

        You must have :attr:`~.Permissions.manage_channels` permission in
        the associated guild to do this.

        Parameters
        ----------
        invite: Union[:class:`.Invite`, :class:`str`]
            The invite to revoke.

        Raises
        ------
        Forbidden
            You do not have permissions to revoke invites.
        NotFound
            The invite is invalid or expired.
        HTTPException
            Revoking the invite failed.
        """
        invite_id = utils.resolve_invite(invite)
        await self.http.delete_invite(invite_id)

    # Voice region stuff

    async def fetch_voice_regions(self, guild_id: Optional[int] = None) -> List[VoiceRegion]:
        """Retrieves a list of :class:`.VoiceRegion`\\s.

        Retrieves voice regions for the user, or a guild if provided.

        .. versionadded:: 2.5

        Parameters
        ----------
        guild_id: Optional[:class:`int`]
            The guild to get regions for, if provided.

        Raises
        ------
        HTTPException
            Retrieving voice regions failed.
        NotFound
            The provided ``guild_id`` could not be found.
        """
        if guild_id:
            regions = await self.http.get_guild_voice_regions(guild_id)
        else:
            regions = await self.http.get_voice_regions()
        return [VoiceRegion(data=data) for data in regions]

    # Miscellaneous stuff

    async def fetch_widget(self, guild_id: int, /) -> Widget:
        """|coro|

        Retrieves a :class:`.Widget` for the given guild ID.

        .. note::

            The guild must have the widget enabled to get this information.

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild.

        Raises
        ------
        Forbidden
            The widget for this guild is disabled.
        HTTPException
            Retrieving the widget failed.

        Returns
        -------
        :class:`.Widget`
            The guild's widget.
        """
        data = await self.http.get_widget(guild_id)
        return Widget(state=self._connection, data=data)

    async def application_info(self) -> AppInfo:
        """|coro|

        Retrieves the bot's application information.

        Raises
        ------
        HTTPException
            Retrieving the information failed somehow.

        Returns
        -------
        :class:`.AppInfo`
            The bot's application information.
        """
        data = await self.http.application_info()
        if "rpc_origins" not in data:
            data["rpc_origins"] = None
        return AppInfo(self._connection, data)

    async def edit_application_info(
        self,
        *,
        description: Optional[str] = MISSING,
        flags: ApplicationFlags = MISSING,
        icon: Optional[AssetBytes] = MISSING,
        cover_image: Optional[AssetBytes] = MISSING,
        custom_install_url: Optional[str] = MISSING,
        install_params: Optional[InstallParams] = MISSING,
        role_connections_verification_url: Optional[str] = MISSING,
        interactions_endpoint_url: Optional[str] = MISSING,
        tags: Optional[List[str]] = MISSING,
    ) -> AppInfo:
        """|coro|

        Edit's the application's information.

        All parameters are optional.

        .. versionadded:: 2.10

        Parameters
        ----------
        description: Optional[:class:`str`]
            The application's description.
        flags: Optional[:class:`.ApplicationFlags`]
            The application's public flags.
        tags: Optional[List[:class:`str`]]
            The application's tags.
        install_params: Optional[:class:`.InstallParams`]
            The installation parameters for this application.
        custom_install_url: Optional[:class:`str`]
            The custom installation url for this application.
        role_connections_verification_url: Optional[:class:`str`]
            The application's role connection verification entry point,
            which when configured will render the app as a verification method
            in the guild role verification configuration.
        icon: |resource_type|
            Update the application's icon asset, if any.
        cover_image: |resource_type|
            Retrieves the cover image on a store embed, if any.

        Raises
        ------
        HTTPException
            Editing the information failed somehow.

        Returns
        -------
        :class:`.AppInfo`
            The bot's application information.
        """
        fields: Dict[str, Any] = {}

        if install_params is not MISSING:
            fields["install_params"] = None if install_params is None else install_params.to_dict()

        if icon is not MISSING:
            fields["icon"] = await utils._assetbytes_to_base64_data(icon)

        if cover_image is not MISSING:
            fields["cover_image"] = await utils._assetbytes_to_base64_data(cover_image)

        if flags is not MISSING:
            fields["flags"] = flags.value

        if description is not MISSING:
            fields["description"] = description

        if custom_install_url is not MISSING:
            fields["custom_install_url"] = custom_install_url

        if role_connections_verification_url is not MISSING:
            fields["role_connections_verification_url"] = role_connections_verification_url

        if interactions_endpoint_url is not MISSING:
            fields["interactions_endpoint_url"] = interactions_endpoint_url

        if tags is not MISSING:
            fields["tags"] = tags

        data = await self.http.edit_application_info(**fields)

        if "rpc_origins" not in data:
            data["rpc_origins"] = None
        return AppInfo(self._connection, data)

    async def fetch_user(self, user_id: int, /) -> User:
        """|coro|

        Retrieves a :class:`~disnake.User` based on their ID.
        You do not have to share any guilds with the user to get this information,
        however many operations do require that you do.

        .. note::

            This method is an API call. If you have :attr:`disnake.Intents.members` and member cache enabled, consider :meth:`get_user` instead.

        Parameters
        ----------
        user_id: :class:`int`
            The ID of the user to retrieve.

        Raises
        ------
        NotFound
            A user with this ID does not exist.
        HTTPException
            Retrieving the user failed.

        Returns
        -------
        :class:`~disnake.User`
            The user you requested.
        """
        data = await self.http.get_user(user_id)
        return User(state=self._connection, data=data)

    async def fetch_channel(
        self,
        channel_id: int,
        /,
    ) -> Union[GuildChannel, PrivateChannel, Thread]:
        """|coro|

        Retrieves a :class:`.abc.GuildChannel`, :class:`.abc.PrivateChannel`, or :class:`.Thread` with the specified ID.

        .. note::

            This method is an API call. For general usage, consider :meth:`get_channel` instead.

        .. versionadded:: 1.2

        Parameters
        ----------
        channel_id: :class:`int`
            The ID of the channel to retrieve.

        Raises
        ------
        InvalidData
            An unknown channel type was received from Discord.
        HTTPException
            Retrieving the channel failed.
        NotFound
            Invalid Channel ID.
        Forbidden
            You do not have permission to fetch this channel.

        Returns
        -------
        Union[:class:`.abc.GuildChannel`, :class:`.abc.PrivateChannel`, :class:`.Thread`]
            The channel from the ID.
        """
        data = await self.http.get_channel(channel_id)

        factory, ch_type = _threaded_channel_factory(data["type"])
        if factory is None:
            raise InvalidData("Unknown channel type {type} for channel ID {id}.".format_map(data))

        if ch_type in (ChannelType.group, ChannelType.private):
            # the factory will be a DMChannel or GroupChannel here
            channel = factory(me=self.user, data=data, state=self._connection)  # type: ignore
        else:
            # the factory can't be a DMChannel or GroupChannel here
            guild_id = int(data["guild_id"])  # type: ignore
            guild = self.get_guild(guild_id) or Object(id=guild_id)
            # GuildChannels expect a Guild, we may be passing an Object
            channel = factory(guild=guild, state=self._connection, data=data)  # type: ignore

        return channel

    async def fetch_webhook(self, webhook_id: int, /) -> Webhook:
        """|coro|

        Retrieves a :class:`.Webhook` with the given ID.

        Parameters
        ----------
        webhook_id: :class:`int`
            The ID of the webhook to retrieve.

        Raises
        ------
        HTTPException
            Retrieving the webhook failed.
        NotFound
            Invalid webhook ID.
        Forbidden
            You do not have permission to fetch this webhook.

        Returns
        -------
        :class:`.Webhook`
            The webhook you requested.
        """
        data = await self.http.get_webhook(webhook_id)
        return Webhook.from_state(data, state=self._connection)

    async def fetch_sticker(self, sticker_id: int, /) -> Union[StandardSticker, GuildSticker]:
        """|coro|

        Retrieves a :class:`.Sticker` with the given ID.

        .. versionadded:: 2.0

        Parameters
        ----------
        sticker_id: :class:`int`
            The ID of the sticker to retrieve.

        Raises
        ------
        HTTPException
            Retrieving the sticker failed.
        NotFound
            Invalid sticker ID.

        Returns
        -------
        Union[:class:`.StandardSticker`, :class:`.GuildSticker`]
            The sticker you requested.
        """
        data = await self.http.get_sticker(sticker_id)
        cls, _ = _sticker_factory(data["type"])  # type: ignore
        return cls(state=self._connection, data=data)  # type: ignore

    async def fetch_sticker_pack(self, pack_id: int, /) -> StickerPack:
        """|coro|

        Retrieves a :class:`.StickerPack` with the given ID.

        .. versionadded:: 2.10

        Parameters
        ----------
        pack_id: :class:`int`
            The ID of the sticker pack to retrieve.

        Raises
        ------
        HTTPException
            Retrieving the sticker pack failed.
        NotFound
            Invalid sticker pack ID.

        Returns
        -------
        :class:`.StickerPack`
            The sticker pack you requested.
        """
        data = await self.http.get_sticker_pack(pack_id)
        return StickerPack(state=self._connection, data=data)

    async def fetch_sticker_packs(self) -> List[StickerPack]:
        """|coro|

        Retrieves all available sticker packs.

        .. versionadded:: 2.0

        .. versionchanged:: 2.10
            Renamed from ``fetch_premium_sticker_packs``.

        Raises
        ------
        HTTPException
            Retrieving the sticker packs failed.

        Returns
        -------
        List[:class:`.StickerPack`]
            All available sticker packs.
        """
        data = await self.http.list_sticker_packs()
        return [StickerPack(state=self._connection, data=pack) for pack in data["sticker_packs"]]

    @deprecated("fetch_sticker_packs")
    async def fetch_premium_sticker_packs(self) -> List[StickerPack]:
        """An alias of :meth:`fetch_sticker_packs`.

        .. deprecated:: 2.10
        """
        return await self.fetch_sticker_packs()

    async def create_dm(self, user: Snowflake) -> DMChannel:
        """|coro|

        Creates a :class:`.DMChannel` with the given user.

        This should be rarely called, as this is done transparently for most
        people.

        .. versionadded:: 2.0

        Parameters
        ----------
        user: :class:`~disnake.abc.Snowflake`
            The user to create a DM with.

        Returns
        -------
        :class:`.DMChannel`
            The channel that was created.
        """
        state = self._connection
        found = state._get_private_channel_by_user(user.id)
        if found:
            return found

        data = await state.http.start_private_message(user.id)
        return state.add_dm_channel(data)

    def add_view(self, view: View, *, message_id: Optional[int] = None) -> None:
        """Registers a :class:`~disnake.ui.View` for persistent listening.

        This method should be used for when a view is comprised of components
        that last longer than the lifecycle of the program.

        .. versionadded:: 2.0

        Parameters
        ----------
        view: :class:`disnake.ui.View`
            The view to register for dispatching.
        message_id: Optional[:class:`int`]
            The message ID that the view is attached to. This is currently used to
            refresh the view's state during message update events. If not given
            then message update events are not propagated for the view.

        Raises
        ------
        TypeError
            A view was not passed.
        ValueError
            The view is not persistent. A persistent view has no timeout
            and all their components have an explicitly provided custom_id.
        """
        if not isinstance(view, View):
            raise TypeError(f"expected an instance of View not {view.__class__!r}")

        if not view.is_persistent():
            raise ValueError(
                "View is not persistent. Items need to have a custom_id set and View must have no timeout"
            )

        self._connection.store_view(view, message_id)

    @property
    def persistent_views(self) -> Sequence[View]:
        """Sequence[:class:`.View`]: A sequence of persistent views added to the client.

        .. versionadded:: 2.0
        """
        return self._connection.persistent_views

    # Application commands (global)

    async def fetch_global_commands(
        self,
        *,
        with_localizations: bool = True,
    ) -> List[APIApplicationCommand]:
        """|coro|

        Retrieves a list of global application commands.

        .. versionadded:: 2.1

        Parameters
        ----------
        with_localizations: :class:`bool`
            Whether to include localizations in the response. Defaults to ``True``.

            .. versionadded:: 2.5

        Returns
        -------
        List[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            A list of application commands.
        """
        return await self._connection.fetch_global_commands(with_localizations=with_localizations)

    async def fetch_global_command(self, command_id: int) -> APIApplicationCommand:
        """|coro|

        Retrieves a global application command.

        .. versionadded:: 2.1

        Parameters
        ----------
        command_id: :class:`int`
            The ID of the command to retrieve.

        Returns
        -------
        Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]
            The requested application command.
        """
        return await self._connection.fetch_global_command(command_id)

    @overload
    async def create_global_command(self, application_command: SlashCommand) -> APISlashCommand:
        ...

    @overload
    async def create_global_command(self, application_command: UserCommand) -> APIUserCommand:
        ...

    @overload
    async def create_global_command(self, application_command: MessageCommand) -> APIMessageCommand:
        ...

    @overload
    async def create_global_command(
        self, application_command: ApplicationCommand
    ) -> APIApplicationCommand:
        ...

    async def create_global_command(
        self, application_command: ApplicationCommand
    ) -> APIApplicationCommand:
        """|coro|

        Creates a global application command.

        .. versionadded:: 2.1

        Parameters
        ----------
        application_command: :class:`.ApplicationCommand`
            An object representing the application command to create.

        Returns
        -------
        Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]
            The application command that was created.
        """
        application_command.localize(self.i18n)
        return await self._connection.create_global_command(application_command)

    @overload
    async def edit_global_command(
        self, command_id: int, new_command: SlashCommand
    ) -> APISlashCommand:
        ...

    @overload
    async def edit_global_command(
        self, command_id: int, new_command: UserCommand
    ) -> APIUserCommand:
        ...

    @overload
    async def edit_global_command(
        self, command_id: int, new_command: MessageCommand
    ) -> APIMessageCommand:
        ...

    @overload
    async def edit_global_command(
        self, command_id: int, new_command: ApplicationCommand
    ) -> APIApplicationCommand:
        ...

    async def edit_global_command(
        self, command_id: int, new_command: ApplicationCommand
    ) -> APIApplicationCommand:
        """|coro|

        Edits a global application command.

        .. versionadded:: 2.1

        Parameters
        ----------
        command_id: :class:`int`
            The ID of the application command to edit.
        new_command: :class:`.ApplicationCommand`
            An object representing the edited application command.

        Returns
        -------
        Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]
            The edited application command.
        """
        new_command.localize(self.i18n)
        return await self._connection.edit_global_command(command_id, new_command)

    async def delete_global_command(self, command_id: int) -> None:
        """|coro|

        Deletes a global application command.

        .. versionadded:: 2.1

        Parameters
        ----------
        command_id: :class:`int`
            The ID of the application command to delete.
        """
        await self._connection.delete_global_command(command_id)

    async def bulk_overwrite_global_commands(
        self, application_commands: List[ApplicationCommand]
    ) -> List[APIApplicationCommand]:
        """|coro|

        Overwrites several global application commands in one API request.

        .. versionadded:: 2.1

        Parameters
        ----------
        application_commands: List[:class:`.ApplicationCommand`]
            A list of application commands to insert instead of the existing commands.

        Returns
        -------
        List[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            A list of registered application commands.
        """
        for cmd in application_commands:
            cmd.localize(self.i18n)
        return await self._connection.bulk_overwrite_global_commands(application_commands)

    # Application commands (guild)

    async def fetch_guild_commands(
        self,
        guild_id: int,
        *,
        with_localizations: bool = True,
    ) -> List[APIApplicationCommand]:
        """|coro|

        Retrieves a list of guild application commands.

        .. versionadded:: 2.1

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild to fetch commands from.
        with_localizations: :class:`bool`
            Whether to include localizations in the response. Defaults to ``True``.

            .. versionadded:: 2.5

        Returns
        -------
        List[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            A list of application commands.
        """
        return await self._connection.fetch_guild_commands(
            guild_id, with_localizations=with_localizations
        )

    async def fetch_guild_command(self, guild_id: int, command_id: int) -> APIApplicationCommand:
        """|coro|

        Retrieves a guild application command.

        .. versionadded:: 2.1

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild to fetch command from.
        command_id: :class:`int`
            The ID of the application command to retrieve.

        Returns
        -------
        Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]
            The requested application command.
        """
        return await self._connection.fetch_guild_command(guild_id, command_id)

    @overload
    async def create_guild_command(
        self, guild_id: int, application_command: SlashCommand
    ) -> APISlashCommand:
        ...

    @overload
    async def create_guild_command(
        self, guild_id: int, application_command: UserCommand
    ) -> APIUserCommand:
        ...

    @overload
    async def create_guild_command(
        self, guild_id: int, application_command: MessageCommand
    ) -> APIMessageCommand:
        ...

    @overload
    async def create_guild_command(
        self, guild_id: int, application_command: ApplicationCommand
    ) -> APIApplicationCommand:
        ...

    async def create_guild_command(
        self, guild_id: int, application_command: ApplicationCommand
    ) -> APIApplicationCommand:
        """|coro|

        Creates a guild application command.

        .. versionadded:: 2.1

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild where the application command should be created.
        application_command: :class:`.ApplicationCommand`
            The application command.

        Returns
        -------
        Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]
            The newly created application command.
        """
        application_command.localize(self.i18n)
        return await self._connection.create_guild_command(guild_id, application_command)

    @overload
    async def edit_guild_command(
        self, guild_id: int, command_id: int, new_command: SlashCommand
    ) -> APISlashCommand:
        ...

    @overload
    async def edit_guild_command(
        self, guild_id: int, command_id: int, new_command: UserCommand
    ) -> APIUserCommand:
        ...

    @overload
    async def edit_guild_command(
        self, guild_id: int, command_id: int, new_command: MessageCommand
    ) -> APIMessageCommand:
        ...

    @overload
    async def edit_guild_command(
        self, guild_id: int, command_id: int, new_command: ApplicationCommand
    ) -> APIApplicationCommand:
        ...

    async def edit_guild_command(
        self, guild_id: int, command_id: int, new_command: ApplicationCommand
    ) -> APIApplicationCommand:
        """|coro|

        Edits a guild application command.

        .. versionadded:: 2.1

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild where the application command should be edited.
        command_id: :class:`int`
            The ID of the application command to edit.
        new_command: :class:`.ApplicationCommand`
            An object representing the edited application command.

        Returns
        -------
        Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]
            The newly edited application command.
        """
        new_command.localize(self.i18n)
        return await self._connection.edit_guild_command(guild_id, command_id, new_command)

    async def delete_guild_command(self, guild_id: int, command_id: int) -> None:
        """|coro|

        Deletes a guild application command.

        .. versionadded:: 2.1

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild where the applcation command should be deleted.
        command_id: :class:`int`
            The ID of the application command to delete.
        """
        await self._connection.delete_guild_command(guild_id, command_id)

    async def bulk_overwrite_guild_commands(
        self, guild_id: int, application_commands: List[ApplicationCommand]
    ) -> List[APIApplicationCommand]:
        """|coro|

        Overwrites several guild application commands in one API request.

        .. versionadded:: 2.1

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild where the application commands should be overwritten.
        application_commands: List[:class:`.ApplicationCommand`]
            A list of application commands to insert instead of the existing commands.

        Returns
        -------
        List[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            A list of registered application commands.
        """
        for cmd in application_commands:
            cmd.localize(self.i18n)
        return await self._connection.bulk_overwrite_guild_commands(guild_id, application_commands)

    # Application command permissions

    async def bulk_fetch_command_permissions(
        self, guild_id: int
    ) -> List[GuildApplicationCommandPermissions]:
        """|coro|

        Retrieves a list of :class:`.GuildApplicationCommandPermissions` configured for the guild with the given ID.

        .. versionadded:: 2.1

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild to inspect.
        """
        return await self._connection.bulk_fetch_command_permissions(guild_id)

    async def fetch_command_permissions(
        self, guild_id: int, command_id: int
    ) -> GuildApplicationCommandPermissions:
        """|coro|

        Retrieves :class:`.GuildApplicationCommandPermissions` for a specific application command in the guild with the given ID.

        .. versionadded:: 2.1

        Parameters
        ----------
        guild_id: :class:`int`
            The ID of the guild to inspect.
        command_id: :class:`int`
            The ID of the application command, or the application ID to fetch application-wide permissions.

            .. versionchanged:: 2.5
                Can now also fetch application-wide permissions.

        Returns
        -------
        :class:`.GuildApplicationCommandPermissions`
            The permissions configured for the specified application command.
        """
        return await self._connection.fetch_command_permissions(guild_id, command_id)

    async def fetch_role_connection_metadata(self) -> List[ApplicationRoleConnectionMetadata]:
        """|coro|

        Retrieves the :class:`.ApplicationRoleConnectionMetadata` records for the application.

        .. versionadded:: 2.8

        Raises
        ------
        HTTPException
            Retrieving the metadata records failed.

        Returns
        -------
        List[:class:`.ApplicationRoleConnectionMetadata`]
            The list of metadata records.
        """
        data = await self.http.get_application_role_connection_metadata_records(self.application_id)
        return [ApplicationRoleConnectionMetadata._from_data(record) for record in data]

    async def edit_role_connection_metadata(
        self, records: Sequence[ApplicationRoleConnectionMetadata]
    ) -> List[ApplicationRoleConnectionMetadata]:
        """|coro|

        Edits the :class:`.ApplicationRoleConnectionMetadata` records for the application.

        An application can have up to 5 metadata records.

        .. warning::
            This will overwrite all existing metadata records.
            Consider :meth:`fetching <fetch_role_connection_metadata>` them first,
            and constructing the new list of metadata records based off of the returned list.

        .. versionadded:: 2.8

        Parameters
        ----------
        records: Sequence[:class:`.ApplicationRoleConnectionMetadata`]
            The new metadata records.

        Raises
        ------
        HTTPException
            Editing the metadata records failed.

        Returns
        -------
        List[:class:`.ApplicationRoleConnectionMetadata`]
            The list of newly edited metadata records.
        """
        payload: List[ApplicationRoleConnectionMetadataPayload] = []
        for record in records:
            record._localize(self.i18n)
            payload.append(record.to_dict())

        data = await self.http.edit_application_role_connection_metadata_records(
            self.application_id, payload
        )
        return [ApplicationRoleConnectionMetadata._from_data(record) for record in data]

    async def skus(self) -> List[SKU]:
        """|coro|

        Retrieves the :class:`.SKU`\\s for the application.

        To manage application subscription entitlements, you should use the SKU
        with :attr:`.SKUType.subscription` (not the :attr:`~.SKUType.subscription_group` one).

        .. versionadded:: 2.10

        Raises
        ------
        HTTPException
            Retrieving the SKUs failed.

        Returns
        -------
        List[:class:`.SKU`]
            The list of SKUs.
        """
        data = await self.http.get_skus(self.application_id)
        return [SKU(data=d) for d in data]

    def entitlements(
        self,
        *,
        limit: Optional[int] = 100,
        before: Optional[SnowflakeTime] = None,
        after: Optional[SnowflakeTime] = None,
        user: Optional[Snowflake] = None,
        guild: Optional[Snowflake] = None,
        skus: Optional[Sequence[Snowflake]] = None,
        exclude_ended: bool = False,
        exclude_deleted: bool = True,
        oldest_first: bool = False,
    ) -> EntitlementIterator:
        """Retrieves an :class:`.AsyncIterator` that enables receiving entitlements for the application.

        .. note::

            This method is an API call. To get the entitlements of the invoking user/guild
            in interactions, consider using :attr:`.Interaction.entitlements`.

        Entries are returned in order from newest to oldest by default;
        pass ``oldest_first=True`` to reverse the iteration order.

        All parameters are optional.

        .. versionadded:: 2.10

        Parameters
        ----------
        limit: Optional[:class:`int`]
            The number of entitlements to retrieve.
            If ``None``, retrieves every entitlement.
            Note, however, that this would make it a slow operation.
            Defaults to ``100``.
        before: Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]
            Retrieves entitlements created before this date or object.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        after: Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]
            Retrieve entitlements created after this date or object.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        user: Optional[:class:`.abc.Snowflake`]
            The user to retrieve entitlements for.
        guild: Optional[:class:`.abc.Snowflake`]
            The guild to retrieve entitlements for.
        skus: Optional[Sequence[:class:`.abc.Snowflake`]]
            The SKUs for which entitlements are retrieved.
        exclude_ended: :class:`bool`
            Whether to exclude ended/expired entitlements. Defaults to ``False``.
        exclude_deleted: :class:`bool`
            Whether to exclude deleted entitlements. Defaults to ``True``.
        oldest_first: :class:`bool`
            If set to ``True``, return entries in oldest->newest order. Defaults to ``False``.

        Raises
        ------
        HTTPException
            Retrieving the entitlements failed.

        Yields
        ------
        :class:`.Entitlement`
            The entitlements for the given parameters.
        """
        return EntitlementIterator(
            self.application_id,
            state=self._connection,
            limit=limit,
            before=before,
            after=after,
            user_id=user.id if user is not None else None,
            guild_id=guild.id if guild is not None else None,
            sku_ids=[sku.id for sku in skus] if skus else None,
            exclude_ended=exclude_ended,
            exclude_deleted=exclude_deleted,
            oldest_first=oldest_first,
        )

    async def fetch_entitlement(self, entitlement_id: int, /) -> Entitlement:
        """|coro|

        Retrieves a :class:`.Entitlement` for the given ID.

        .. note::

            This method is an API call. To get the entitlements of the invoking user/guild
            in interactions, consider using :attr:`.Interaction.entitlements`.

        .. versionadded:: 2.10

        Parameters
        ----------
        entitlement_id: :class:`int`
            The ID of the entitlement to retrieve.

        Raises
        ------
        HTTPException
            Retrieving the entitlement failed.

        Returns
        -------
        :class:`.Entitlement`
            The retrieved entitlement.
        """
        data = await self.http.get_entitlement(self.application_id, entitlement_id=entitlement_id)
        return Entitlement(data=data, state=self._connection)

    async def create_entitlement(
        self, sku: Snowflake, owner: Union[abc.User, Guild]
    ) -> Entitlement:
        """|coro|

        Creates a new test :class:`.Entitlement` for the given user or guild, with no expiry.

        Parameters
        ----------
        sku: :class:`.abc.Snowflake`
            The :class:`.SKU` to grant the entitlement for.
        owner: Union[:class:`.abc.User`, :class:`.Guild`]
            The user or guild to grant the entitlement to.

        Raises
        ------
        HTTPException
            Creating the entitlement failed.

        Returns
        -------
        :class:`.Entitlement`
            The newly created entitlement.
        """
        data = await self.http.create_test_entitlement(
            self.application_id,
            sku_id=sku.id,
            owner_id=owner.id,
            owner_type=2 if isinstance(owner, abc.User) else 1,
        )
        return Entitlement(data=data, state=self._connection)
