# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import copy
import datetime
import inspect
import itertools
import logging
import os
import weakref
from collections import OrderedDict, deque
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Deque,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)

from . import utils
from .activity import BaseActivity
from .app_commands import GuildApplicationCommandPermissions, application_command_factory
from .audit_logs import AuditLogEntry
from .automod import AutoModActionExecution, AutoModRule
from .channel import (
    DMChannel,
    ForumChannel,
    GroupChannel,
    PartialMessageable,
    StageChannel,
    TextChannel,
    VoiceChannel,
    _guild_channel_factory,
)
from .emoji import Emoji
from .enums import ApplicationCommandType, ChannelType, ComponentType, MessageType, Status, try_enum
from .flags import ApplicationFlags, Intents, MemberCacheFlags
from .guild import Guild
from .guild_scheduled_event import GuildScheduledEvent
from .integrations import _integration_factory
from .interactions import (
    ApplicationCommandInteraction,
    Interaction,
    MessageInteraction,
    ModalInteraction,
)
from .invite import Invite
from .member import Member
from .mentions import AllowedMentions
from .message import Message
from .object import Object
from .partial_emoji import PartialEmoji
from .raw_models import (
    RawBulkMessageDeleteEvent,
    RawGuildMemberRemoveEvent,
    RawGuildScheduledEventUserActionEvent,
    RawIntegrationDeleteEvent,
    RawMessageDeleteEvent,
    RawMessageUpdateEvent,
    RawReactionActionEvent,
    RawReactionClearEmojiEvent,
    RawReactionClearEvent,
    RawThreadDeleteEvent,
    RawThreadMemberRemoveEvent,
    RawTypingEvent,
)
from .role import Role
from .stage_instance import StageInstance
from .sticker import GuildSticker
from .threads import Thread, ThreadMember
from .ui.modal import Modal, ModalStore
from .ui.view import View, ViewStore
from .user import ClientUser, User
from .utils import MISSING
from .webhook import Webhook

if TYPE_CHECKING:
    from .abc import MessageableChannel, PrivateChannel
    from .app_commands import APIApplicationCommand, ApplicationCommand
    from .client import Client
    from .gateway import DiscordWebSocket
    from .guild import GuildChannel, VocalGuildChannel
    from .http import HTTPClient
    from .types import gateway
    from .types.activity import Activity as ActivityPayload
    from .types.channel import DMChannel as DMChannelPayload
    from .types.emoji import Emoji as EmojiPayload, PartialEmoji as PartialEmojiPayload
    from .types.guild import Guild as GuildPayload, UnavailableGuild as UnavailableGuildPayload
    from .types.message import Message as MessagePayload
    from .types.sticker import GuildSticker as GuildStickerPayload
    from .types.user import User as UserPayload
    from .types.webhook import Webhook as WebhookPayload
    from .voice_client import VoiceProtocol

    T = TypeVar("T")
    Channel = Union[GuildChannel, VocalGuildChannel, PrivateChannel]
    PartialChannel = Union[Channel, PartialMessageable]


class ChunkRequest:
    def __init__(
        self,
        guild_id: int,
        loop: asyncio.AbstractEventLoop,
        resolver: Callable[[int], Any],
        *,
        cache: bool = True,
    ) -> None:
        self.guild_id: int = guild_id
        self.resolver: Callable[[int], Any] = resolver
        self.loop: asyncio.AbstractEventLoop = loop
        self.cache: bool = cache
        self.nonce: str = os.urandom(16).hex()
        self.buffer: List[Member] = []
        self.waiters: List[asyncio.Future[List[Member]]] = []

    def add_members(self, members: List[Member]) -> None:
        self.buffer.extend(members)
        if self.cache:
            guild = self.resolver(self.guild_id)
            if guild is None:
                return

            for member in members:
                existing = guild.get_member(member.id)
                if existing is None or existing.joined_at is None:
                    guild._add_member(member)

    async def wait(self) -> List[Member]:
        future = self.loop.create_future()
        self.waiters.append(future)
        try:
            return await future
        finally:
            self.waiters.remove(future)

    def get_future(self) -> asyncio.Future[List[Member]]:
        future = self.loop.create_future()
        self.waiters.append(future)
        return future

    def done(self) -> None:
        for future in self.waiters:
            if not future.done():
                future.set_result(self.buffer)


_log = logging.getLogger(__name__)


async def logging_coroutine(coroutine: Coroutine[Any, Any, T], *, info: str) -> Optional[T]:
    try:
        await coroutine
    except Exception:
        _log.exception("Exception occurred during %s", info)


_SELECT_COMPONENT_TYPES = frozenset(
    (
        ComponentType.string_select,
        ComponentType.user_select,
        ComponentType.role_select,
        ComponentType.mentionable_select,
        ComponentType.channel_select,
    )
)


class ConnectionState:
    if TYPE_CHECKING:
        _get_websocket: Callable[..., DiscordWebSocket]
        _get_client: Callable[..., Client]
        _parsers: Dict[str, Callable[[Dict[str, Any]], None]]

    def __init__(
        self,
        *,
        dispatch: Callable,
        handlers: Dict[str, Callable],
        hooks: Dict[str, Callable],
        http: HTTPClient,
        loop: asyncio.AbstractEventLoop,
        max_messages: Optional[int] = 1000,
        application_id: Optional[int] = None,
        heartbeat_timeout: float = 60.0,
        guild_ready_timeout: float = 2.0,
        allowed_mentions: Optional[AllowedMentions] = None,
        activity: Optional[BaseActivity] = None,
        status: Optional[Union[str, Status]] = None,
        intents: Optional[Intents] = None,
        chunk_guilds_at_startup: Optional[bool] = None,
        member_cache_flags: Optional[MemberCacheFlags] = None,
    ) -> None:
        self.loop: asyncio.AbstractEventLoop = loop
        self.http: HTTPClient = http
        self.max_messages: Optional[int] = max_messages
        if self.max_messages is not None and self.max_messages <= 0:
            self.max_messages = 1000

        self.dispatch: Callable = dispatch
        self.handlers: Dict[str, Callable] = handlers
        self.hooks: Dict[str, Callable] = hooks
        self.shard_count: Optional[int] = None
        self._ready_task: Optional[asyncio.Task] = None
        self.application_id: Optional[int] = None if application_id is None else int(application_id)
        self.heartbeat_timeout: float = heartbeat_timeout
        self.guild_ready_timeout: float = guild_ready_timeout
        if self.guild_ready_timeout < 0:
            raise ValueError("guild_ready_timeout cannot be negative.")

        if allowed_mentions is not None and not isinstance(allowed_mentions, AllowedMentions):
            raise TypeError("allowed_mentions parameter must be AllowedMentions.")

        self.allowed_mentions: Optional[AllowedMentions] = allowed_mentions
        self._chunk_requests: Dict[Union[int, str], ChunkRequest] = {}

        if activity:
            if not isinstance(activity, BaseActivity):
                raise TypeError("activity parameter must derive from BaseActivity.")

            self._activity: Optional[ActivityPayload] = activity.to_dict()
        else:
            self._activity: Optional[ActivityPayload] = None

        self._status: Optional[str] = None
        if status:
            self._status = "invisible" if status is Status.offline else str(status)

        if intents is not None:
            if not isinstance(intents, Intents):
                raise TypeError(f"intents parameter must be Intents, not {type(intents)!r}.")

            if not intents.guilds:
                _log.warning(
                    "Guilds intent seems to be disabled. This may cause state related issues."
                )

            self._intents: Intents = intents
        else:
            self._intents: Intents = Intents.default()

        self._chunk_guilds: bool = (
            self._intents.members if chunk_guilds_at_startup is None else chunk_guilds_at_startup
        )

        # Ensure these two are set properly
        if not self._intents.members and self._chunk_guilds:
            raise ValueError("Intents.members must be enabled to chunk guilds at startup.")

        if member_cache_flags is None:
            member_cache_flags = MemberCacheFlags.from_intents(self._intents)
        else:
            if not isinstance(member_cache_flags, MemberCacheFlags):
                raise TypeError(
                    "member_cache_flags parameter must be MemberCacheFlags, "
                    f"not {type(member_cache_flags)!r}"
                )

            member_cache_flags._verify_intents(self._intents)

        self.member_cache_flags: MemberCacheFlags = member_cache_flags

        if not self._intents.members or member_cache_flags._empty:
            self.store_user = self.create_user

        self.parsers = parsers = {}
        for attr, func in inspect.getmembers(self):
            if attr.startswith("parse_"):
                parsers[attr[6:].upper()] = func

        self.clear()

    def clear(
        self, *, views: bool = True, application_commands: bool = True, modals: bool = True
    ) -> None:
        self.user: ClientUser = MISSING
        # NOTE: without weakrefs, these user objects would otherwise be kept in memory indefinitely.
        # However, using weakrefs here unfortunately has a few drawbacks:
        # - the weakref slot + object in user objects likely results in a small increase in memory usage
        # - accesses on `_users` are slower, e.g. `__getitem__` takes ~1us with weakrefs and ~0.2us without
        self._users: weakref.WeakValueDictionary[int, User] = weakref.WeakValueDictionary()
        self._emojis: Dict[int, Emoji] = {}
        self._stickers: Dict[int, GuildSticker] = {}
        self._guilds: Dict[int, Guild] = {}

        if application_commands:
            self._global_application_commands: Dict[int, APIApplicationCommand] = {}
            self._guild_application_commands: Dict[int, Dict[int, APIApplicationCommand]] = {}

        if views:
            self._view_store: ViewStore = ViewStore(self)

        if modals:
            self._modal_store: ModalStore = ModalStore(self)

        self._voice_clients: Dict[int, VoiceProtocol] = {}

        # LRU of max size 128
        self._private_channels: OrderedDict[int, PrivateChannel] = OrderedDict()
        # extra dict to look up private channels by user id
        self._private_channels_by_user: Dict[int, DMChannel] = {}
        if self.max_messages is not None:
            self._messages: Optional[Deque[Message]] = deque(maxlen=self.max_messages)
        else:
            self._messages: Optional[Deque[Message]] = None

    def process_chunk_requests(
        self, guild_id: int, nonce: Optional[str], members: List[Member], complete: bool
    ) -> None:
        removed = []
        for key, request in self._chunk_requests.items():
            if request.guild_id == guild_id and request.nonce == nonce:
                request.add_members(members)
                if complete:
                    request.done()
                    removed.append(key)

        for key in removed:
            del self._chunk_requests[key]

    def call_handlers(self, key: str, *args: Any, **kwargs: Any) -> None:
        try:
            func = self.handlers[key]
        except KeyError:
            pass
        else:
            func(*args, **kwargs)

    async def call_hooks(self, key: str, *args: Any, **kwargs: Any) -> None:
        try:
            coro = self.hooks[key]
        except KeyError:
            pass
        else:
            await coro(*args, **kwargs)

    @property
    def self_id(self) -> Optional[int]:
        u = self.user
        return u.id if u else None

    @property
    def intents(self) -> Intents:
        ret = Intents.none()
        ret.value = self._intents.value
        return ret

    @property
    def voice_clients(self) -> List[VoiceProtocol]:
        return list(self._voice_clients.values())

    def _get_voice_client(self, guild_id: Optional[int]) -> Optional[VoiceProtocol]:
        # the keys of self._voice_clients are ints
        return self._voice_clients.get(guild_id)  # type: ignore

    def _add_voice_client(self, guild_id: int, voice: VoiceProtocol) -> None:
        self._voice_clients[guild_id] = voice

    def _remove_voice_client(self, guild_id: int) -> None:
        self._voice_clients.pop(guild_id, None)

    def _update_references(self, ws: DiscordWebSocket) -> None:
        for vc in self.voice_clients:
            vc.main_ws = ws  # type: ignore

    def store_user(self, data: UserPayload) -> User:
        user_id = int(data["id"])
        try:
            return self._users[user_id]
        except KeyError:
            user = User(state=self, data=data)
            if user.discriminator != "0000":
                self._users[user_id] = user
            return user

    def create_user(self, data: UserPayload) -> User:
        return User(state=self, data=data)

    def get_user(self, id: Optional[int]) -> Optional[User]:
        # the keys of self._users are ints
        return self._users.get(id)  # type: ignore

    def store_emoji(self, guild: Guild, data: EmojiPayload) -> Emoji:
        # the id will be present here
        emoji_id = int(data["id"])  # type: ignore
        self._emojis[emoji_id] = emoji = Emoji(guild=guild, state=self, data=data)
        return emoji

    def store_sticker(self, guild: Guild, data: GuildStickerPayload) -> GuildSticker:
        sticker_id = int(data["id"])
        self._stickers[sticker_id] = sticker = GuildSticker(state=self, data=data)
        return sticker

    def store_view(self, view: View, message_id: Optional[int] = None) -> None:
        self._view_store.add_view(view, message_id)

    def store_modal(self, user_id: int, modal: Modal) -> None:
        self._modal_store.add_modal(user_id, modal)

    def prevent_view_updates_for(self, message_id: int) -> Optional[View]:
        return self._view_store.remove_message_tracking(message_id)

    @property
    def persistent_views(self) -> Sequence[View]:
        return self._view_store.persistent_views

    @property
    def guilds(self) -> List[Guild]:
        return list(self._guilds.values())

    def _get_guild(self, guild_id: Optional[int]) -> Optional[Guild]:
        # the keys of self._guilds are ints
        if guild_id is None:
            return None
        return self._guilds.get(guild_id)

    def _add_guild(self, guild: Guild) -> None:
        self._guilds[guild.id] = guild

    def _remove_guild(self, guild: Guild) -> None:
        self._guilds.pop(guild.id, None)

        for emoji in guild.emojis:
            self._emojis.pop(emoji.id, None)

        for sticker in guild.stickers:
            self._stickers.pop(sticker.id, None)

        del guild

    def _get_global_application_command(
        self, application_command_id: int
    ) -> Optional[APIApplicationCommand]:
        return self._global_application_commands.get(application_command_id)

    def _add_global_application_command(
        self,
        application_command: APIApplicationCommand,
        /,
    ) -> None:
        if not application_command.id:
            AssertionError("The provided application command does not have an ID")
        self._global_application_commands[application_command.id] = application_command

    def _remove_global_application_command(self, application_command_id: int, /) -> None:
        self._global_application_commands.pop(application_command_id, None)

    def _clear_global_application_commands(self) -> None:
        self._global_application_commands.clear()

    def _get_guild_application_command(
        self, guild_id: int, application_command_id: int
    ) -> Optional[APIApplicationCommand]:
        granula = self._guild_application_commands.get(guild_id)
        if granula is not None:
            return granula.get(application_command_id)
        return None

    def _add_guild_application_command(
        self, guild_id: int, application_command: APIApplicationCommand
    ) -> None:
        if not application_command.id:
            AssertionError("The provided application command does not have an ID")
        try:
            granula = self._guild_application_commands[guild_id]
            granula[application_command.id] = application_command
        except KeyError:
            self._guild_application_commands[guild_id] = {
                application_command.id: application_command
            }

    def _remove_guild_application_command(self, guild_id: int, application_command_id: int) -> None:
        try:
            granula = self._guild_application_commands[guild_id]
            granula.pop(application_command_id, None)
        except KeyError:
            pass

    def _clear_guild_application_commands(self, guild_id: int) -> None:
        self._guild_application_commands.pop(guild_id, None)

    def _get_global_command_named(
        self, name: str, cmd_type: Optional[ApplicationCommandType] = None
    ) -> Optional[APIApplicationCommand]:
        for cmd in self._global_application_commands.values():
            if cmd.name == name and (cmd_type is None or cmd.type is cmd_type):
                return cmd
        return None

    def _get_guild_command_named(
        self, guild_id: int, name: str, cmd_type: Optional[ApplicationCommandType] = None
    ) -> Optional[APIApplicationCommand]:
        granula = self._guild_application_commands.get(guild_id, {})
        for cmd in granula.values():
            if cmd.name == name and (cmd_type is None or cmd.type is cmd_type):
                return cmd
        return None

    @property
    def emojis(self) -> List[Emoji]:
        return list(self._emojis.values())

    @property
    def stickers(self) -> List[GuildSticker]:
        return list(self._stickers.values())

    def get_emoji(self, emoji_id: Optional[int]) -> Optional[Emoji]:
        # the keys of self._emojis are ints
        return self._emojis.get(emoji_id)  # type: ignore

    def get_sticker(self, sticker_id: Optional[int]) -> Optional[GuildSticker]:
        # the keys of self._stickers are ints
        return self._stickers.get(sticker_id)  # type: ignore

    @property
    def private_channels(self) -> List[PrivateChannel]:
        return list(self._private_channels.values())

    def _get_private_channel(self, channel_id: Optional[int]) -> Optional[PrivateChannel]:
        try:
            # the keys of self._private_channels are ints
            value = self._private_channels[channel_id]  # type: ignore
        except KeyError:
            return None
        else:
            self._private_channels.move_to_end(channel_id)  # type: ignore
            return value

    def _get_private_channel_by_user(self, user_id: Optional[int]) -> Optional[DMChannel]:
        # the keys of self._private_channels are ints
        return self._private_channels_by_user.get(user_id)  # type: ignore

    def _add_private_channel(self, channel: PrivateChannel) -> None:
        channel_id = channel.id
        self._private_channels[channel_id] = channel

        if len(self._private_channels) > 128:
            _, to_remove = self._private_channels.popitem(last=False)
            if isinstance(to_remove, DMChannel) and to_remove.recipient:
                self._private_channels_by_user.pop(to_remove.recipient.id, None)

        if isinstance(channel, DMChannel) and channel.recipient:
            self._private_channels_by_user[channel.recipient.id] = channel

    def add_dm_channel(self, data: DMChannelPayload) -> DMChannel:
        # self.user is *always* cached when this is called
        channel = DMChannel(me=self.user, state=self, data=data)
        self._add_private_channel(channel)
        return channel

    def _remove_private_channel(self, channel: PrivateChannel) -> None:
        self._private_channels.pop(channel.id, None)
        if isinstance(channel, DMChannel):
            recipient = channel.recipient
            if recipient is not None:
                self._private_channels_by_user.pop(recipient.id, None)

    def _get_message(self, msg_id: Optional[int]) -> Optional[Message]:
        return (
            utils.find(lambda m: m.id == msg_id, reversed(self._messages))
            if self._messages
            else None
        )

    def _add_guild_from_data(self, data: Union[GuildPayload, UnavailableGuildPayload]) -> Guild:
        guild = Guild(
            data=data,  # type: ignore  # may be unavailable guild
            state=self,
        )
        self._add_guild(guild)
        return guild

    def _guild_needs_chunking(self, guild: Guild) -> bool:
        # If presences are enabled then we get back the old guild.large behaviour
        return (
            self._chunk_guilds
            and not guild.chunked
            and not (self._intents.presences and not guild.large)
        )

    def _get_guild_channel(
        self,
        data: Union[MessagePayload, gateway.TypingStartEvent],
    ) -> Tuple[Union[PartialChannel, Thread], Optional[Guild]]:
        channel_id = int(data["channel_id"])
        try:
            guild = self._get_guild(int(data["guild_id"]))
        except KeyError:
            # if we're here, this is a DM channel or an ephemeral message in a guild
            channel = self.get_channel(channel_id)
            if channel is None:
                if "author" in data:
                    # MessagePayload
                    data = cast("MessagePayload", data)
                    user_id = int(data["author"]["id"])
                else:
                    # TypingStartEvent
                    user_id = int(data["user_id"])
                channel = DMChannel._from_message(self, channel_id, user_id)
            guild = None
        else:
            channel = guild and guild._resolve_channel(channel_id)

        return channel or PartialMessageable(state=self, id=channel_id), guild

    async def chunker(
        self,
        guild_id: int,
        query: str = "",
        limit: int = 0,
        presences: bool = False,
        *,
        nonce: Optional[str] = None,
    ) -> None:
        ws = self._get_websocket(guild_id)  # This is ignored upstream
        await ws.request_chunks(
            guild_id, query=query, limit=limit, presences=presences, nonce=nonce
        )

    async def query_members(
        self,
        guild: Guild,
        query: Optional[str],
        limit: int,
        user_ids: Optional[List[int]],
        cache: bool,
        presences: bool,
    ):
        guild_id = guild.id
        ws = self._get_websocket(guild_id)
        if ws is None:
            raise RuntimeError("Somehow do not have a websocket for this guild_id")

        request = ChunkRequest(guild.id, self.loop, self._get_guild, cache=cache)
        self._chunk_requests[request.nonce] = request

        try:
            # start the query operation
            await ws.request_chunks(
                guild_id,
                query=query,
                limit=limit,
                user_ids=user_ids,
                presences=presences,
                nonce=request.nonce,
            )
            return await asyncio.wait_for(request.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            _log.warning(
                "Timed out waiting for chunks with query %r and limit %d for guild_id %d",
                query,
                limit,
                guild_id,
            )
            raise

    async def _delay_ready(self) -> None:
        try:
            states = []
            while True:
                # this snippet of code is basically waiting N seconds
                # until the last GUILD_CREATE was sent
                try:
                    guild = await asyncio.wait_for(
                        self._ready_state.get(), timeout=self.guild_ready_timeout
                    )
                except asyncio.TimeoutError:
                    break
                else:
                    if self._guild_needs_chunking(guild):
                        future = await self.chunk_guild(guild, wait=False)
                        states.append((guild, future))
                    else:
                        if guild.unavailable is False:
                            self.dispatch("guild_available", guild)
                        else:
                            self.dispatch("guild_join", guild)

            for guild, future in states:
                try:
                    await asyncio.wait_for(future, timeout=5.0)
                except asyncio.TimeoutError:
                    _log.warning(
                        "Shard ID %s timed out waiting for chunks for guild_id %s.",
                        guild.shard_id,
                        guild.id,
                    )

                if guild.unavailable is False:
                    self.dispatch("guild_available", guild)
                else:
                    self.dispatch("guild_join", guild)

            # remove the state
            try:
                del self._ready_state
            except AttributeError:
                pass  # already been deleted somehow

        except asyncio.CancelledError:
            pass
        else:
            # dispatch the event
            self.call_handlers("ready")
            self.dispatch("ready")
        finally:
            self._ready_task = None

    def parse_ready(self, data: gateway.ReadyEvent) -> None:
        if self._ready_task is not None:
            self._ready_task.cancel()

        self._ready_state: asyncio.Queue[Guild] = asyncio.Queue()
        self.clear(views=False, application_commands=False, modals=False)
        self.user = ClientUser(state=self, data=data["user"])
        # self._users is a list of Users, we're setting a ClientUser
        self._users[self.user.id] = self.user  # type: ignore

        try:
            application = data["application"]
        except KeyError:
            pass
        else:
            if self.application_id is None:
                self.application_id = utils._get_as_snowflake(application, "id")
            self.application_flags = ApplicationFlags._from_value(application["flags"])

        for guild_data in data["guilds"]:
            self._add_guild_from_data(guild_data)

        self.dispatch("connect")
        self.call_handlers("connect_internal")
        self._ready_task = asyncio.create_task(self._delay_ready())

    def parse_resumed(self, data: gateway.ResumedEvent) -> None:
        self.dispatch("resumed")

    def parse_application_command_permissions_update(
        self, data: gateway.ApplicationCommandPermissionsUpdateEvent
    ) -> None:
        app_command_perms = GuildApplicationCommandPermissions(data=data, state=self)
        self.dispatch("application_command_permissions_update", app_command_perms)

    def parse_message_create(self, data: gateway.MessageCreateEvent) -> None:
        channel, _ = self._get_guild_channel(data)
        # channel would be the correct type here
        message = Message(channel=channel, data=data, state=self)  # type: ignore
        self.dispatch("message", message)
        if self._messages is not None:
            self._messages.append(message)

        if channel:
            # we ensure that the channel is a type that implements last_message_id
            if channel.__class__ in (TextChannel, Thread, VoiceChannel, StageChannel):
                channel.last_message_id = message.id  # type: ignore
            # Essentially, messages *don't* count towards message_count, if:
            # - they're the thread starter message
            # - or, they're the initial message of a forum channel thread (which uses MessageType.default)
            # This mirrors the current client and API behavior.
            if channel.__class__ is Thread and not (
                message.type is MessageType.thread_starter_message
                or (
                    type(channel.parent) is ForumChannel  # type: ignore
                    and channel.id == message.id
                )
            ):
                channel.total_message_sent += 1  # type: ignore
                channel.message_count += 1  # type: ignore

    def parse_message_delete(self, data: gateway.MessageDeleteEvent) -> None:
        raw = RawMessageDeleteEvent(data)
        found = self._get_message(raw.message_id)
        raw.cached_message = found
        self.dispatch("raw_message_delete", raw)

        # the initial message isn't counted, and hence shouldn't be subtracted from the count either
        if raw.message_id != raw.channel_id:
            guild = self._get_guild(raw.guild_id)
            thread = guild and guild.get_thread(raw.channel_id)
            if thread:
                thread.message_count = max(0, thread.message_count - 1)

        if self._messages is not None and found is not None:
            self.dispatch("message_delete", found)
            self._messages.remove(found)

    def parse_message_delete_bulk(self, data: gateway.MessageDeleteBulkEvent) -> None:
        raw = RawBulkMessageDeleteEvent(data)
        if self._messages:
            found_messages = [
                message for message in self._messages if message.id in raw.message_ids
            ]
        else:
            found_messages = []
        raw.cached_messages = found_messages
        self.dispatch("raw_bulk_message_delete", raw)
        guild = self._get_guild(raw.guild_id)
        thread = guild and guild.get_thread(raw.channel_id)
        if thread:
            to_subtract = len(raw.message_ids)
            # the initial message isn't counted, and hence shouldn't be subtracted from the count either
            if raw.channel_id in raw.message_ids:
                to_subtract -= 1
            thread.message_count = max(0, thread.message_count - to_subtract)
        if found_messages:
            self.dispatch("bulk_message_delete", found_messages)
            for msg in found_messages:
                # self._messages won't be None here
                self._messages.remove(msg)  # type: ignore

    def parse_message_update(self, data: gateway.MessageUpdateEvent) -> None:
        raw = RawMessageUpdateEvent(data)
        message = self._get_message(raw.message_id)
        if message is not None:
            older_message = copy.copy(message)
            raw.cached_message = older_message
            self.dispatch("raw_message_edit", raw)
            message._update(data)
            # Coerce the `after` parameter to take the new updated Member
            # ref: #5999
            older_message.author = message.author
            self.dispatch("message_edit", older_message, message)
        else:
            self.dispatch("raw_message_edit", raw)

        if "components" in data and self._view_store.is_message_tracked(raw.message_id):
            self._view_store.update_from_message(raw.message_id, data["components"])

    def parse_message_reaction_add(self, data: gateway.MessageReactionAddEvent) -> None:
        emoji = data["emoji"]
        emoji_id = utils._get_as_snowflake(emoji, "id")
        emoji = PartialEmoji.with_state(
            self,
            id=emoji_id,
            animated=emoji.get("animated", False),
            name=emoji["name"],  # type: ignore
        )
        raw = RawReactionActionEvent(data, emoji, "REACTION_ADD")

        member_data = data.get("member")
        if member_data:
            guild = self._get_guild(raw.guild_id)
            if guild is not None:
                raw.member = Member(data=member_data, guild=guild, state=self)
            else:
                raw.member = None
        else:
            raw.member = None
        self.dispatch("raw_reaction_add", raw)

        # rich interface here
        message = self._get_message(raw.message_id)
        if message is not None:
            emoji = self._upgrade_partial_emoji(emoji)
            reaction = message._add_reaction(data, emoji, raw.user_id)
            user = raw.member or self._get_reaction_user(message.channel, raw.user_id)

            if user:
                self.dispatch("reaction_add", reaction, user)

    def parse_message_reaction_remove_all(
        self, data: gateway.MessageReactionRemoveAllEvent
    ) -> None:
        raw = RawReactionClearEvent(data)
        self.dispatch("raw_reaction_clear", raw)

        message = self._get_message(raw.message_id)
        if message is not None:
            old_reactions = message.reactions.copy()
            message.reactions.clear()
            self.dispatch("reaction_clear", message, old_reactions)

    def parse_message_reaction_remove(self, data: gateway.MessageReactionRemoveEvent) -> None:
        emoji = data["emoji"]
        emoji_id = utils._get_as_snowflake(emoji, "id")
        emoji = PartialEmoji.with_state(
            self,
            id=emoji_id,
            # may be `None` in gateway events if custom emoji data isn't available anymore
            # https://discord.com/developers/docs/resources/emoji#emoji-object-custom-emoji-examples
            name=emoji["name"],  # type: ignore
        )
        raw = RawReactionActionEvent(data, emoji, "REACTION_REMOVE")
        self.dispatch("raw_reaction_remove", raw)

        message = self._get_message(raw.message_id)
        if message is not None:
            emoji = self._upgrade_partial_emoji(emoji)
            try:
                reaction = message._remove_reaction(data, emoji, raw.user_id)
            except (AttributeError, ValueError):  # eventual consistency lol
                pass
            else:
                user = self._get_reaction_user(message.channel, raw.user_id)
                if user:
                    self.dispatch("reaction_remove", reaction, user)

    def parse_message_reaction_remove_emoji(
        self, data: gateway.MessageReactionRemoveEmojiEvent
    ) -> None:
        emoji = data["emoji"]
        emoji_id = utils._get_as_snowflake(emoji, "id")
        emoji = PartialEmoji.with_state(
            self,
            id=emoji_id,
            # may be `None` in gateway events if custom emoji data isn't available anymore
            # https://discord.com/developers/docs/resources/emoji#emoji-object-custom-emoji-examples
            name=emoji["name"],  # type: ignore
        )
        raw = RawReactionClearEmojiEvent(data, emoji)
        self.dispatch("raw_reaction_clear_emoji", raw)

        message = self._get_message(raw.message_id)
        if message is not None:
            try:
                reaction = message._clear_emoji(emoji)
            except (AttributeError, ValueError):  # eventual consistency lol
                pass
            else:
                if reaction:
                    self.dispatch("reaction_clear_emoji", reaction)

    def parse_interaction_create(self, data: gateway.InteractionCreateEvent) -> None:
        # note: this does not use an intermediate variable for `data["type"]` since
        # it wouldn't allow automatically narrowing the `data` union type based
        # on the `["type"]` field

        interaction: Interaction

        if data["type"] == 1:
            # PING interaction should never be received
            return

        if data["type"] == 2:
            interaction = ApplicationCommandInteraction(data=data, state=self)
            self.dispatch("application_command", interaction)

        elif data["type"] == 3:
            interaction = MessageInteraction(data=data, state=self)
            self._view_store.dispatch(interaction)
            self.dispatch("message_interaction", interaction)
            if interaction.data.component_type is ComponentType.button:
                self.dispatch("button_click", interaction)
            elif interaction.data.component_type in _SELECT_COMPONENT_TYPES:
                self.dispatch("dropdown", interaction)

        elif data["type"] == 4:
            interaction = ApplicationCommandInteraction(data=data, state=self)
            self.dispatch("application_command_autocomplete", interaction)

        elif data["type"] == 5:
            interaction = ModalInteraction(data=data, state=self)
            self._modal_store.dispatch(interaction)
            self.dispatch("modal_submit", interaction)

        else:
            return

        self.dispatch("interaction", interaction)

    def parse_presence_update(self, data: gateway.PresenceUpdateEvent) -> None:
        guild_id = utils._get_as_snowflake(data, "guild_id")
        guild = self._get_guild(guild_id)
        if guild is None:
            _log.debug("PRESENCE_UPDATE referencing an unknown guild ID: %s. Discarding.", guild_id)
            return

        user = data["user"]
        member_id = int(user["id"])
        member = guild.get_member(member_id)
        if member is None:
            _log.debug(
                "PRESENCE_UPDATE referencing an unknown member ID: %s. Discarding", member_id
            )
            return

        old_member = Member._copy(member)
        user_update = member._presence_update(data=data, user=user)
        if user_update:
            self.dispatch("user_update", user_update[0], user_update[1])

        self.dispatch("presence_update", old_member, member)

    def parse_user_update(self, data: gateway.UserUpdateEvent) -> None:
        if user := self.user:
            user._update(data)

    def parse_invite_create(self, data: gateway.InviteCreateEvent) -> None:
        invite = Invite.from_gateway(state=self, data=data)
        self.dispatch("invite_create", invite)

    def parse_invite_delete(self, data: gateway.InviteDeleteEvent) -> None:
        invite = Invite.from_gateway(state=self, data=data)
        self.dispatch("invite_delete", invite)

    def parse_channel_delete(self, data: gateway.ChannelDeleteEvent) -> None:
        guild = self._get_guild(utils._get_as_snowflake(data, "guild_id"))
        if guild is None:
            return

        channel_id = int(data["id"])
        channel = guild.get_channel(channel_id)
        if channel is None:
            return

        guild._remove_channel(channel)
        self.dispatch("guild_channel_delete", channel)

        if channel.type in (ChannelType.voice, ChannelType.stage_voice):
            for event_id, scheduled_event in list(guild._scheduled_events.items()):
                if scheduled_event.channel_id == channel_id:
                    guild._scheduled_events.pop(event_id)
                    self.dispatch("guild_scheduled_event_delete", scheduled_event)

    def parse_channel_update(self, data: gateway.ChannelUpdateEvent) -> None:
        channel_type = try_enum(ChannelType, data.get("type"))
        channel_id = int(data["id"])
        if channel_type is ChannelType.group:
            channel = self._get_private_channel(channel_id)
            old_channel = copy.copy(channel)
            # the channel is a GroupChannel
            channel._update_group(data)  # type: ignore
            self.dispatch("private_channel_update", old_channel, channel)
            return

        guild_id = utils._get_as_snowflake(data, "guild_id")
        guild = self._get_guild(guild_id)
        if guild is not None:
            channel = guild.get_channel(channel_id)
            if channel is not None:
                old_channel = copy.copy(channel)
                channel._update(
                    guild,
                    data,  # type: ignore  # data type will always match channel type
                )
                self.dispatch("guild_channel_update", old_channel, channel)
            else:
                _log.debug(
                    "CHANNEL_UPDATE referencing an unknown channel ID: %s. Discarding.", channel_id
                )
        else:
            _log.debug("CHANNEL_UPDATE referencing an unknown guild ID: %s. Discarding.", guild_id)

    def parse_channel_create(self, data: gateway.ChannelCreateEvent) -> None:
        factory, _ = _guild_channel_factory(data["type"])
        if factory is None:
            _log.debug(
                "CHANNEL_CREATE referencing an unknown channel type %s. Discarding.", data["type"]
            )
            return

        guild_id = utils._get_as_snowflake(data, "guild_id")
        guild = self._get_guild(guild_id)
        if guild is not None:
            channel = factory(
                guild=guild,
                state=self,
                data=data,  # type: ignore  # data type will always match channel type
            )
            guild._add_channel(channel)
            self.dispatch("guild_channel_create", channel)
        else:
            _log.debug("CHANNEL_CREATE referencing an unknown guild ID: %s. Discarding.", guild_id)
            return

    def parse_channel_pins_update(self, data: gateway.ChannelPinsUpdateEvent) -> None:
        channel_id = int(data["channel_id"])
        try:
            guild = self._get_guild(int(data["guild_id"]))
        except KeyError:
            guild = None
            channel = self._get_private_channel(channel_id)
        else:
            channel = guild and guild._resolve_channel(channel_id)

        if channel is None:
            _log.debug(
                "CHANNEL_PINS_UPDATE referencing an unknown channel ID: %s. Discarding.", channel_id
            )
            return

        last_pin = None
        if "last_pin_timestamp" in data:
            last_pin = utils.parse_time(data["last_pin_timestamp"])

        if isinstance(channel, (DMChannel, TextChannel, Thread)):
            channel.last_pin_timestamp = last_pin

        if guild is None:
            self.dispatch("private_channel_pins_update", channel, last_pin)
        else:
            self.dispatch("guild_channel_pins_update", channel, last_pin)

    def parse_thread_create(self, data: gateway.ThreadCreateEvent) -> None:
        guild_id = int(data["guild_id"])
        guild: Optional[Guild] = self._get_guild(guild_id)
        if guild is None:
            _log.debug("THREAD_CREATE referencing an unknown guild ID: %s. Discarding", guild_id)
            return

        thread = Thread(guild=guild, state=guild._state, data=data)
        has_thread = guild.get_thread(thread.id)
        guild._add_thread(thread)
        if not has_thread:
            if data.get("newly_created"):
                if isinstance(thread.parent, ForumChannel):
                    thread.parent.last_thread_id = thread.id

                self.dispatch("thread_create", thread)
            else:
                self.dispatch("thread_join", thread)

    def parse_thread_update(self, data: gateway.ThreadUpdateEvent) -> None:
        guild_id = int(data["guild_id"])
        guild = self._get_guild(guild_id)
        if guild is None:
            _log.debug("THREAD_UPDATE referencing an unknown guild ID: %s. Discarding", guild_id)
            return

        thread_id = int(data["id"])
        thread = guild.get_thread(thread_id)
        if thread is not None:
            old = copy.copy(thread)
            thread._update(data)
            self.dispatch("thread_update", old, thread)
        else:
            thread = Thread(guild=guild, state=guild._state, data=data)
            guild._add_thread(thread)
            self.dispatch("thread_join", thread)

        self.dispatch("raw_thread_update", thread)

    def parse_thread_delete(self, data: gateway.ThreadDeleteEvent) -> None:
        guild_id = int(data["guild_id"])
        guild = self._get_guild(guild_id)
        if guild is None:
            _log.debug("THREAD_DELETE referencing an unknown guild ID: %s. Discarding", guild_id)
            return

        thread_id = int(data["id"])
        thread = guild.get_thread(thread_id)
        raw = RawThreadDeleteEvent(data)
        if thread is not None:
            raw.thread = thread
            guild._remove_thread(thread)
            self.dispatch("thread_delete", thread)
        self.dispatch("raw_thread_delete", raw)

    def parse_thread_list_sync(self, data: gateway.ThreadListSyncEvent) -> None:
        guild_id = int(data["guild_id"])
        guild: Optional[Guild] = self._get_guild(guild_id)
        if guild is None:
            _log.debug("THREAD_LIST_SYNC referencing an unknown guild ID: %s. Discarding", guild_id)
            return

        try:
            channel_ids = set(map(int, data["channel_ids"]))
        except KeyError:
            # If not provided, then the entire guild is being synced
            # So all previous thread data should be overwritten
            previous_threads = guild._threads.copy()
            guild._clear_threads()
        else:
            previous_threads = guild._filter_threads(channel_ids)

        threads = {d["id"]: guild._store_thread(d) for d in data.get("threads", [])}

        for member in data.get("members", []):
            try:
                # note: member["id"] is the thread_id
                thread = threads[member["id"]]
            except KeyError:
                continue
            else:
                thread._add_member(ThreadMember(thread, member))

        for thread in threads.values():
            old = previous_threads.pop(thread.id, None)
            if old is None:
                self.dispatch("thread_join", thread)

        for thread in previous_threads.values():
            self.dispatch("thread_remove", thread)

    def parse_thread_member_update(self, data: gateway.ThreadMemberUpdateEvent) -> None:
        guild_id = int(data["guild_id"])
        guild: Optional[Guild] = self._get_guild(guild_id)
        if guild is None:
            _log.debug(
                "THREAD_MEMBER_UPDATE referencing an unknown guild ID: %s. Discarding", guild_id
            )
            return

        thread_id = int(data["id"])
        thread: Optional[Thread] = guild.get_thread(thread_id)
        if thread is None:
            _log.debug(
                "THREAD_MEMBER_UPDATE referencing an unknown thread ID: %s. Discarding", thread_id
            )
            return

        member = ThreadMember(thread, data)
        thread.me = member

    def parse_thread_members_update(self, data: gateway.ThreadMembersUpdateEvent) -> None:
        guild_id = int(data["guild_id"])
        guild: Optional[Guild] = self._get_guild(guild_id)
        if guild is None:
            _log.debug(
                "THREAD_MEMBERS_UPDATE referencing an unknown guild ID: %s. Discarding", guild_id
            )
            return

        thread_id = int(data["id"])
        thread: Optional[Thread] = guild.get_thread(thread_id)
        if thread is None:
            _log.debug(
                "THREAD_MEMBERS_UPDATE referencing an unknown thread ID: %s. Discarding", thread_id
            )
            return

        added_members = [ThreadMember(thread, d) for d in data.get("added_members", [])]
        removed_member_ids = [int(x) for x in data.get("removed_member_ids", [])]
        self_id = self.self_id
        for member in added_members:
            if member.id != self_id:
                thread._add_member(member)
                self.dispatch("thread_member_join", member)
            else:
                thread.me = member
                self.dispatch("thread_join", thread)

        for member_id in removed_member_ids:
            if member_id != self_id:
                raw = RawThreadMemberRemoveEvent(thread, member_id)
                member = thread._pop_member(member_id)
                if member is not None:
                    raw.cached_member = member
                    self.dispatch("thread_member_remove", member)
                self.dispatch("raw_thread_member_remove", raw)
            else:
                self.dispatch("thread_remove", thread)

    def parse_guild_member_add(self, data: gateway.GuildMemberAddEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is None:
            _log.debug(
                "GUILD_MEMBER_ADD referencing an unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        member = Member(guild=guild, data=data, state=self)
        if self.member_cache_flags.joined:
            guild._add_member(member)

        try:
            guild._member_count += 1
        except AttributeError:
            pass

        self.dispatch("member_join", member)

    def parse_guild_member_remove(self, data: gateway.GuildMemberRemoveEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is not None:
            try:
                guild._member_count -= 1
            except AttributeError:
                pass

            user_id = int(data["user"]["id"])
            member = guild.get_member(user_id)
            if member is not None:
                guild._remove_member(member)
                self.dispatch("member_remove", member)
                user = member
            else:
                user = self.store_user(data["user"])
            raw = RawGuildMemberRemoveEvent(user, guild.id)
            self.dispatch("raw_member_remove", raw)
        else:
            _log.debug(
                "GUILD_MEMBER_REMOVE referencing an unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )

    def parse_guild_member_update(self, data: gateway.GuildMemberUpdateEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        user_id = int(data["user"]["id"])
        if guild is None:
            _log.debug(
                "GUILD_MEMBER_UPDATE referencing an unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        member = guild.get_member(user_id)
        if member is not None:
            old_member = Member._copy(member)
            member._update(data)
            user_update = member._update_inner_user(data["user"])
            if user_update:
                self.dispatch("user_update", user_update[0], user_update[1])

            self.dispatch("member_update", old_member, member)
        else:
            member = Member(data=data, guild=guild, state=self)

            # Force an update on the inner user if necessary
            user_update = member._update_inner_user(data["user"])
            if user_update:
                self.dispatch("user_update", user_update[0], user_update[1])

            if self.member_cache_flags.joined:
                guild._add_member(member)

        self.dispatch("raw_member_update", member)

    def parse_guild_emojis_update(self, data: gateway.GuildEmojisUpdateEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is None:
            _log.debug(
                "GUILD_EMOJIS_UPDATE referencing an unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        before_emojis = guild.emojis
        for emoji in before_emojis:
            self._emojis.pop(emoji.id, None)
        guild.emojis = tuple(self.store_emoji(guild, d) for d in data["emojis"])
        self.dispatch("guild_emojis_update", guild, before_emojis, guild.emojis)

    def parse_guild_stickers_update(self, data: gateway.GuildStickersUpdateEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is None:
            _log.debug(
                "GUILD_STICKERS_UPDATE referencing an unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        before_stickers = guild.stickers
        for emoji in before_stickers:
            self._stickers.pop(emoji.id, None)
        guild.stickers = tuple(self.store_sticker(guild, d) for d in data["stickers"])
        self.dispatch("guild_stickers_update", guild, before_stickers, guild.stickers)

    def _get_create_guild(self, data: gateway.GuildCreateEvent) -> Guild:
        if data.get("unavailable") is False:
            # GUILD_CREATE with unavailable in the response
            # usually means that the guild has become available
            # and is therefore in the cache
            guild = self._get_guild(int(data["id"]))
            if guild is not None:
                guild.unavailable = False
                guild._from_data(data)  # type: ignore  # data type not narrowed correctly to full guild
                return guild

        return self._add_guild_from_data(data)

    def is_guild_evicted(self, guild) -> bool:
        return guild.id not in self._guilds

    @overload
    async def chunk_guild(
        self, guild: Guild, *, wait: Literal[False], cache: Optional[bool] = None
    ) -> asyncio.Future[List[Member]]:
        ...

    @overload
    async def chunk_guild(
        self, guild: Guild, *, wait: Literal[True] = True, cache: Optional[bool] = None
    ) -> List[Member]:
        ...

    async def chunk_guild(
        self, guild: Guild, *, wait: bool = True, cache: Optional[bool] = None
    ) -> Union[List[Member], asyncio.Future[List[Member]]]:
        cache = cache or self.member_cache_flags.joined
        request = self._chunk_requests.get(guild.id)
        if request is None:
            self._chunk_requests[guild.id] = request = ChunkRequest(
                guild.id, self.loop, self._get_guild, cache=cache
            )
            await self.chunker(guild.id, nonce=request.nonce)

        if wait:
            return await request.wait()
        return request.get_future()

    async def _chunk_and_dispatch(self, guild, unavailable) -> None:
        try:
            await asyncio.wait_for(self.chunk_guild(guild), timeout=60.0)
        except asyncio.TimeoutError:
            _log.info("Somehow timed out waiting for chunks.")

        if unavailable is False:
            self.dispatch("guild_available", guild)
        else:
            self.dispatch("guild_join", guild)

    def parse_guild_create(self, data: gateway.GuildCreateEvent) -> None:
        unavailable = data.get("unavailable")
        if unavailable is True:
            # joined a guild with unavailable == True so..
            return

        guild = self._get_create_guild(data)

        try:
            # Notify the on_ready state, if any, that this guild is complete.
            self._ready_state.put_nowait(guild)
        except AttributeError:
            pass
        else:
            # If we're waiting for the event, put the rest on hold
            return

        # check if it requires chunking
        if self._guild_needs_chunking(guild):
            asyncio.create_task(self._chunk_and_dispatch(guild, unavailable))
            return

        # Dispatch available if newly available
        if unavailable is False:
            self.dispatch("guild_available", guild)
        else:
            self.dispatch("guild_join", guild)

    def parse_guild_update(self, data: gateway.GuildUpdateEvent) -> None:
        guild = self._get_guild(int(data["id"]))
        if guild is not None:
            old_guild = copy.copy(guild)
            guild._from_data(data)
            self.dispatch("guild_update", old_guild, guild)
        else:
            _log.debug("GUILD_UPDATE referencing an unknown guild ID: %s. Discarding.", data["id"])

    def parse_guild_delete(self, data: gateway.GuildDeleteEvent) -> None:
        guild = self._get_guild(int(data["id"]))
        if guild is None:
            _log.debug("GUILD_DELETE referencing an unknown guild ID: %s. Discarding.", data["id"])
            return

        if data.get("unavailable", False):
            # GUILD_DELETE with unavailable being True means that the
            # guild that was available is now currently unavailable
            guild.unavailable = True
            self.dispatch("guild_unavailable", guild)
            return

        # do a cleanup of the messages cache
        if self._messages is not None:
            self._messages: Optional[Deque[Message]] = deque(
                (msg for msg in self._messages if msg.guild != guild), maxlen=self.max_messages
            )

        self._remove_guild(guild)
        self.dispatch("guild_remove", guild)

    def parse_guild_ban_add(self, data: gateway.GuildBanAddEvent) -> None:
        # we make the assumption that GUILD_BAN_ADD is done
        # before GUILD_MEMBER_REMOVE is called
        # hence we don't remove it from cache or do anything
        # strange with it, the main purpose of this event
        # is mainly to dispatch to another event worth listening to for logging
        guild = self._get_guild(int(data["guild_id"]))
        if guild is not None:
            try:
                user = User(data=data["user"], state=self)
            except KeyError:
                pass
            else:
                member = guild.get_member(user.id) or user
                self.dispatch("member_ban", guild, member)

    def parse_guild_ban_remove(self, data: gateway.GuildBanRemoveEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is not None and "user" in data:
            user = self.store_user(data["user"])
            self.dispatch("member_unban", guild, user)

    def parse_guild_role_create(self, data: gateway.GuildRoleCreateEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is None:
            _log.debug(
                "GUILD_ROLE_CREATE referencing an unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        role_data = data["role"]
        role = Role(guild=guild, data=role_data, state=self)
        guild._add_role(role)
        self.dispatch("guild_role_create", role)

    def parse_guild_role_delete(self, data: gateway.GuildRoleDeleteEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is not None:
            role_id = int(data["role_id"])
            try:
                role = guild._remove_role(role_id)
            except KeyError:
                return
            else:
                self.dispatch("guild_role_delete", role)
        else:
            _log.debug(
                "GUILD_ROLE_DELETE referencing an unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )

    def parse_guild_role_update(self, data: gateway.GuildRoleUpdateEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is not None:
            role_data = data["role"]
            role_id = int(role_data["id"])
            role = guild.get_role(role_id)
            if role is not None:
                old_role = copy.copy(role)
                role._update(role_data)
                self.dispatch("guild_role_update", old_role, role)
        else:
            _log.debug(
                "GUILD_ROLE_UPDATE referencing an unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )

    def parse_guild_scheduled_event_create(
        self, data: gateway.GuildScheduledEventCreateEvent
    ) -> None:
        scheduled_event = GuildScheduledEvent(state=self, data=data)
        guild = scheduled_event.guild
        if guild is not None:
            guild._scheduled_events[scheduled_event.id] = scheduled_event
        self.dispatch("guild_scheduled_event_create", scheduled_event)

    def parse_guild_scheduled_event_update(
        self, data: gateway.GuildScheduledEventUpdateEvent
    ) -> None:
        guild = self._get_guild(int(data["guild_id"]))

        if guild is None:
            _log.debug(
                "GUILD_SCHEDULED_EVENT_UPDATE referencing unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        scheduled_event = guild._scheduled_events.get(int(data["id"]))
        if scheduled_event is not None:
            old_scheduled_event = copy.copy(scheduled_event)
            scheduled_event._update(data)
            self.dispatch("guild_scheduled_event_update", old_scheduled_event, scheduled_event)

        else:
            _log.debug(
                "GUILD_SCHEDULED_EVENT_UPDATE referencing "
                "unknown scheduled event ID: %s. Discarding.",
                data["id"],
            )

    def parse_guild_scheduled_event_delete(
        self, data: gateway.GuildScheduledEventDeleteEvent
    ) -> None:
        scheduled_event = GuildScheduledEvent(state=self, data=data)
        guild = scheduled_event.guild
        if guild is not None:
            guild._scheduled_events.pop(scheduled_event.id, None)
        self.dispatch("guild_scheduled_event_delete", scheduled_event)

    def parse_guild_scheduled_event_user_add(
        self, data: gateway.GuildScheduledEventUserAddEvent
    ) -> None:
        payload = RawGuildScheduledEventUserActionEvent(data)
        self.dispatch("raw_guild_scheduled_event_subscribe", payload)
        guild = self._get_guild(payload.guild_id)
        if guild is None:
            return

        event = guild.get_scheduled_event(payload.event_id)
        user = guild.get_member(payload.user_id)
        if user is None:
            user = self.get_user(payload.user_id)

        if event is not None and user is not None:
            self.dispatch("guild_scheduled_event_subscribe", event, user)

    def parse_guild_scheduled_event_user_remove(
        self, data: gateway.GuildScheduledEventUserRemoveEvent
    ) -> None:
        payload = RawGuildScheduledEventUserActionEvent(data)
        self.dispatch("raw_guild_scheduled_event_unsubscribe", payload)
        guild = self._get_guild(payload.guild_id)
        if guild is None:
            return

        event = guild.get_scheduled_event(payload.event_id)
        user = guild.get_member(payload.user_id)
        if user is None:
            user = self.get_user(payload.user_id)

        if event is not None and user is not None:
            self.dispatch("guild_scheduled_event_unsubscribe", event, user)

    def parse_guild_members_chunk(self, data: gateway.GuildMembersChunkEvent) -> None:
        guild_id = int(data["guild_id"])
        guild = self._get_guild(guild_id)
        # This should never happen, but it's handled just in case
        if guild is None:
            _log.debug(
                "GUILD_MEMBERS_CHUNK referencing unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        presences = data.get("presences", [])

        members = [
            Member(guild=guild, data=member, state=self) for member in data.get("members", [])
        ]
        _log.debug("Processed a chunk for %s members in guild ID %s.", len(members), guild_id)

        if presences:
            member_dict = {member.id: member for member in members}
            for presence in presences:
                user = presence["user"]
                member_id = int(user["id"])
                member = member_dict.get(member_id)
                if member is not None:
                    member._presence_update(presence, user)

        complete = data.get("chunk_index", 0) + 1 == data.get("chunk_count")
        self.process_chunk_requests(guild_id, data.get("nonce"), members, complete)

    def parse_guild_integrations_update(self, data: gateway.GuildIntegrationsUpdateEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is not None:
            self.dispatch("guild_integrations_update", guild)
        else:
            _log.debug(
                "GUILD_INTEGRATIONS_UPDATE referencing an unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )

    def parse_integration_create(self, data: gateway.IntegrationCreateEvent) -> None:
        guild_id = int(data["guild_id"])
        guild = self._get_guild(guild_id)
        if guild is not None:
            cls, _ = _integration_factory(data["type"])
            integration = cls(data=data, guild=guild)
            self.dispatch("integration_create", integration)
        else:
            _log.debug(
                "INTEGRATION_CREATE referencing an unknown guild ID: %s. Discarding.", guild_id
            )

    def parse_integration_update(self, data: gateway.IntegrationUpdateEvent) -> None:
        guild_id = int(data["guild_id"])
        guild = self._get_guild(guild_id)
        if guild is not None:
            cls, _ = _integration_factory(data["type"])
            integration = cls(data=data, guild=guild)
            self.dispatch("integration_update", integration)
        else:
            _log.debug(
                "INTEGRATION_UPDATE referencing an unknown guild ID: %s. Discarding.", guild_id
            )

    def parse_integration_delete(self, data: gateway.IntegrationDeleteEvent) -> None:
        guild_id = int(data["guild_id"])
        guild = self._get_guild(guild_id)
        if guild is not None:
            raw = RawIntegrationDeleteEvent(data)
            self.dispatch("raw_integration_delete", raw)
        else:
            _log.debug(
                "INTEGRATION_DELETE referencing an unknown guild ID: %s. Discarding.", guild_id
            )

    def parse_webhooks_update(self, data: gateway.WebhooksUpdateEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is None:
            _log.debug(
                "WEBHOOKS_UPDATE referencing an unknown guild ID: %s. Discarding", data["guild_id"]
            )
            return

        channel = guild.get_channel(int(data["channel_id"]))
        if channel is not None:
            self.dispatch("webhooks_update", channel)
        else:
            _log.debug(
                "WEBHOOKS_UPDATE referencing an unknown channel ID: %s. Discarding.",
                data["channel_id"],
            )

    def parse_stage_instance_create(self, data: gateway.StageInstanceCreateEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is not None:
            stage_instance = StageInstance(guild=guild, state=self, data=data)
            guild._stage_instances[stage_instance.id] = stage_instance
            self.dispatch("stage_instance_create", stage_instance)
        else:
            _log.debug(
                "STAGE_INSTANCE_CREATE referencing unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )

    def parse_stage_instance_update(self, data: gateway.StageInstanceUpdateEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is not None:
            stage_instance = guild._stage_instances.get(int(data["id"]))
            if stage_instance is not None:
                old_stage_instance = copy.copy(stage_instance)
                stage_instance._update(data)
                self.dispatch("stage_instance_update", old_stage_instance, stage_instance)
            else:
                _log.debug(
                    "STAGE_INSTANCE_UPDATE referencing unknown stage instance ID: %s. Discarding.",
                    data["id"],
                )
        else:
            _log.debug(
                "STAGE_INSTANCE_UPDATE referencing unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )

    def parse_stage_instance_delete(self, data: gateway.StageInstanceDeleteEvent) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is not None:
            try:
                stage_instance = guild._stage_instances.pop(int(data["id"]))
            except KeyError:
                pass
            else:
                self.dispatch("stage_instance_delete", stage_instance)
        else:
            _log.debug(
                "STAGE_INSTANCE_DELETE referencing unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )

    def parse_voice_state_update(self, data: gateway.VoiceStateUpdateEvent) -> None:
        guild = self._get_guild(utils._get_as_snowflake(data, "guild_id"))
        channel_id = utils._get_as_snowflake(data, "channel_id")
        flags = self.member_cache_flags
        # self.user is *always* cached when this is called
        self_id = self.user.id
        if guild is not None:
            if int(data["user_id"]) == self_id:
                voice = self._get_voice_client(guild.id)
                if voice is not None:
                    coro = voice.on_voice_state_update(data)
                    asyncio.create_task(
                        logging_coroutine(coro, info="Voice Protocol voice state update handler")
                    )

            member, before, after = guild._update_voice_state(data, channel_id)
            if member is not None:
                if flags.voice:
                    if channel_id is None and flags._voice_only and member.id != self_id:
                        # Only remove from cache if we only have the voice flag enabled
                        # Member doesn't meet the Snowflake protocol currently
                        guild._remove_member(member)
                    elif channel_id is not None:
                        guild._add_member(member)

                self.dispatch("voice_state_update", member, before, after)
            else:
                _log.debug(
                    "VOICE_STATE_UPDATE referencing an unknown member ID: %s. Discarding.",
                    data["user_id"],
                )

    def parse_voice_server_update(self, data: gateway.VoiceServerUpdateEvent) -> None:
        key_id = int(data["guild_id"])

        vc = self._get_voice_client(key_id)
        if vc is not None:
            coro = vc.on_voice_server_update(data)
            asyncio.create_task(
                logging_coroutine(coro, info="Voice Protocol voice server update handler")
            )

    def parse_typing_start(self, data: gateway.TypingStartEvent) -> None:
        channel, guild = self._get_guild_channel(data)
        raw = RawTypingEvent(data)

        user_id = int(data["user_id"])
        member_data = data.get("member")
        if member_data and guild is not None:
            # try member cache first
            raw.member = guild.get_member(user_id) or Member(
                data=member_data, guild=guild, state=self
            )

        self.dispatch("raw_typing", raw)

        if channel is not None:
            member = None
            if raw.member is not None:
                member = raw.member

            elif isinstance(channel, DMChannel):
                member = channel.recipient

            elif isinstance(channel, GroupChannel):
                member = utils.find(lambda x: x.id == user_id, channel.recipients)

            if member is not None:
                timestamp = datetime.datetime.fromtimestamp(
                    data["timestamp"], tz=datetime.timezone.utc
                )
                self.dispatch("typing", channel, member, timestamp)

    def parse_auto_moderation_rule_create(
        self, data: gateway.AutoModerationRuleCreateEvent
    ) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is None:
            _log.debug(
                "AUTO_MODERATION_RULE_CREATE referencing unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        rule = AutoModRule(data=data, guild=guild)
        self.dispatch("automod_rule_create", rule)

    def parse_auto_moderation_rule_update(
        self, data: gateway.AutoModerationRuleUpdateEvent
    ) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is None:
            _log.debug(
                "AUTO_MODERATION_RULE_UPDATE referencing unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        rule = AutoModRule(data=data, guild=guild)
        self.dispatch("automod_rule_update", rule)

    def parse_auto_moderation_rule_delete(
        self, data: gateway.AutoModerationRuleDeleteEvent
    ) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is None:
            _log.debug(
                "AUTO_MODERATION_RULE_DELETE referencing unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        rule = AutoModRule(data=data, guild=guild)
        self.dispatch("automod_rule_delete", rule)

    def parse_auto_moderation_action_execution(
        self, data: gateway.AutoModerationActionExecutionEvent
    ) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is None:
            _log.debug(
                "AUTO_MODERATION_ACTION_EXECUTION referencing unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        event = AutoModActionExecution(data=data, guild=guild)
        self.dispatch("automod_action_execution", event)

    def parse_guild_audit_log_entry_create(self, data: gateway.AuditLogEntryCreate) -> None:
        guild = self._get_guild(int(data["guild_id"]))
        if guild is None:
            _log.debug(
                "GUILD_AUDIT_LOG_ENTRY_CREATE referencing unknown guild ID: %s. Discarding.",
                data["guild_id"],
            )
            return

        entry = AuditLogEntry(
            data=data,
            guild=guild,
            application_commands={},
            automod_rules={},
            guild_scheduled_events=guild._scheduled_events,
            integrations={},
            threads=guild._threads,
            users=self._users,
            webhooks={},
        )
        self.dispatch("audit_log_entry_create", entry)

    def _get_reaction_user(
        self, channel: MessageableChannel, user_id: int
    ) -> Optional[Union[User, Member]]:
        if isinstance(channel, (TextChannel, VoiceChannel, Thread, StageChannel)):
            return channel.guild.get_member(user_id)
        return self.get_user(user_id)

    # methods to handle all sorts of different emoji formats

    def _get_emoji_from_data(
        self, data: PartialEmojiPayload
    ) -> Optional[Union[str, Emoji, PartialEmoji]]:
        """Convert partial emoji data to proper emoji.
        Returns unicode emojis as strings.

        Primarily used to handle reaction emojis.
        """
        emoji_id = utils._get_as_snowflake(data, "id")
        if not emoji_id:
            return data["name"]

        if (emoji := self._emojis.get(emoji_id)) is not None:
            return emoji

        return PartialEmoji.with_state(
            self,
            # This may be `None` when custom emoji data in reactions isn't available.
            # Should generally be fine, since we have an id at this point.
            name=data["name"],  # type: ignore
            id=emoji_id,
            animated=data.get("animated", False),
        )

    # deprecated
    get_reaction_emoji = _get_emoji_from_data

    def _get_emoji_from_fields(
        self,
        *,
        name: Optional[str],
        id: Optional[int],
        animated: Optional[bool] = False,
    ) -> Optional[Union[Emoji, PartialEmoji]]:
        """Convert partial emoji fields to proper emoji, if possible.
        If both `id` and `name` are nullish, returns `None`.

        Unlike _get_emoji_from_data, this returns `PartialEmoji`s instead of strings
        for unicode emojis, and falls back to "" for the emoji name.

        Primarily used for structures with nonstandard top-level `emoji_name` and `emoji_id` fields,
        like forum channels/tags or welcome screens.
        """
        if not (name or id):
            return None

        if id and (emoji := self._emojis.get(id)) is not None:
            return emoji

        return PartialEmoji.with_state(
            self,
            # Note: this does not render correctly if it's a custom emoji, there's just no name information here sometimes.
            # This may change in a future API version, but for now we'll just have to accept it.
            name=name or "",
            # Coerce `0` to `None`, occasional API inconsistency
            id=id or None,
            animated=animated or False,
        )

    def _upgrade_partial_emoji(self, emoji: PartialEmoji) -> Union[Emoji, PartialEmoji, str]:
        emoji_id = emoji.id
        if not emoji_id:
            return emoji.name
        try:
            return self._emojis[emoji_id]
        except KeyError:
            return emoji

    def get_channel(self, id: Optional[int]) -> Optional[Union[Channel, Thread]]:
        if id is None:
            return None

        pm = self._get_private_channel(id)
        if pm is not None:
            return pm

        for guild in self.guilds:
            channel = guild._resolve_channel(id)
            if channel is not None:
                return channel
        return None

    def create_message(
        self,
        *,
        channel: MessageableChannel,
        data: MessagePayload,
    ) -> Message:
        return Message(state=self, channel=channel, data=data)

    def create_webhook(self, data: WebhookPayload) -> Webhook:
        return Webhook.from_state(data=data, state=self)

    # Application commands (global)
    # All these methods (except fetchers) update the application command cache as well,
    # since there're no events related to application command updates

    async def fetch_global_commands(
        self,
        *,
        with_localizations: bool = True,
    ) -> List[APIApplicationCommand]:
        results = await self.http.get_global_commands(self.application_id, with_localizations=with_localizations)  # type: ignore
        return [application_command_factory(data) for data in results]

    async def fetch_global_command(self, command_id: int) -> APIApplicationCommand:
        result = await self.http.get_global_command(self.application_id, command_id)  # type: ignore
        return application_command_factory(result)

    async def create_global_command(
        self, application_command: ApplicationCommand
    ) -> APIApplicationCommand:
        result = await self.http.upsert_global_command(
            self.application_id, application_command.to_dict()  # type: ignore
        )
        cmd = application_command_factory(result)
        self._add_global_application_command(cmd)
        return cmd

    async def edit_global_command(
        self, command_id: int, new_command: ApplicationCommand
    ) -> APIApplicationCommand:
        result = await self.http.edit_global_command(
            self.application_id, command_id, new_command.to_dict()  # type: ignore
        )
        cmd = application_command_factory(result)
        self._add_global_application_command(cmd)
        return cmd

    async def delete_global_command(self, command_id: int) -> None:
        await self.http.delete_global_command(self.application_id, command_id)  # type: ignore
        self._remove_global_application_command(command_id)

    async def bulk_overwrite_global_commands(
        self, application_commands: List[ApplicationCommand]
    ) -> List[APIApplicationCommand]:
        payload = [cmd.to_dict() for cmd in application_commands]
        results = await self.http.bulk_upsert_global_commands(self.application_id, payload)  # type: ignore
        commands = [application_command_factory(data) for data in results]
        self._global_application_commands = {cmd.id: cmd for cmd in commands}
        return commands

    # Application commands (guild)

    async def fetch_guild_commands(
        self,
        guild_id: int,
        *,
        with_localizations: bool = True,
    ) -> List[APIApplicationCommand]:
        results = await self.http.get_guild_commands(self.application_id, guild_id, with_localizations=with_localizations)  # type: ignore
        return [application_command_factory(data) for data in results]

    async def fetch_guild_command(self, guild_id: int, command_id: int) -> APIApplicationCommand:
        result = await self.http.get_guild_command(self.application_id, guild_id, command_id)  # type: ignore
        return application_command_factory(result)

    async def create_guild_command(
        self, guild_id: int, application_command: ApplicationCommand
    ) -> APIApplicationCommand:
        result = await self.http.upsert_guild_command(
            self.application_id, guild_id, application_command.to_dict()  # type: ignore
        )
        cmd = application_command_factory(result)
        self._add_guild_application_command(guild_id, cmd)
        return cmd

    async def edit_guild_command(
        self, guild_id: int, command_id: int, new_command: ApplicationCommand
    ) -> APIApplicationCommand:
        result = await self.http.edit_guild_command(
            self.application_id, guild_id, command_id, new_command.to_dict()  # type: ignore
        )
        cmd = application_command_factory(result)
        self._add_guild_application_command(guild_id, cmd)
        return cmd

    async def delete_guild_command(self, guild_id: int, command_id: int) -> None:
        await self.http.delete_guild_command(
            self.application_id, guild_id, command_id  # type: ignore
        )
        self._remove_guild_application_command(guild_id, command_id)

    async def bulk_overwrite_guild_commands(
        self, guild_id: int, application_commands: List[ApplicationCommand]
    ) -> List[APIApplicationCommand]:
        payload = [cmd.to_dict() for cmd in application_commands]
        results = await self.http.bulk_upsert_guild_commands(
            self.application_id, guild_id, payload  # type: ignore
        )
        commands = [application_command_factory(data) for data in results]
        self._guild_application_commands[guild_id] = {cmd.id: cmd for cmd in commands}
        return commands

    # Application command permissions

    async def bulk_fetch_command_permissions(
        self, guild_id: int
    ) -> List[GuildApplicationCommandPermissions]:
        array = await self.http.get_guild_application_command_permissions(
            self.application_id, guild_id  # type: ignore
        )
        return [GuildApplicationCommandPermissions(state=self, data=obj) for obj in array]

    async def fetch_command_permissions(
        self, guild_id: int, command_id: int
    ) -> GuildApplicationCommandPermissions:
        data = await self.http.get_application_command_permissions(
            self.application_id, guild_id, command_id  # type: ignore
        )
        return GuildApplicationCommandPermissions(state=self, data=data)


class AutoShardedConnectionState(ConnectionState):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.shard_ids: Union[List[int], range] = []
        self.shards_launched: asyncio.Event = asyncio.Event()

    def _update_guild_channel_references(self) -> None:
        if not self._messages:
            return
        for msg in self._messages:
            if not msg.guild:
                continue

            new_guild = self._get_guild(msg.guild.id)
            if new_guild is not None and new_guild is not msg.guild:
                channel_id = msg.channel.id
                channel = new_guild._resolve_channel(channel_id) or Object(id=channel_id)
                # channel will either be a TextChannel, VoiceChannel, Thread, StageChannel, or Object
                msg._rebind_cached_references(new_guild, channel)  # type: ignore

        # these generally get deallocated once the voice reconnect times out
        # (it never succeeds after gateway reconnects)
        # but we rebind the channel reference just in case
        for vc in self._voice_clients.values():
            if not getattr(vc.channel, "guild", None):
                continue

            new_guild = self._get_guild(vc.channel.guild.id)
            if new_guild is None:
                continue

            new_channel = new_guild._resolve_channel(vc.channel.id) or Object(id=vc.channel.id)
            if new_channel is not vc.channel:
                vc.channel = new_channel  # type: ignore

    def _update_member_references(self) -> None:
        messages: Sequence[Message] = self._messages or []
        for msg in messages:
            if not msg.guild:
                continue

            # note that unlike with channels, this doesn't fall back to `Object` in case
            # guild chunking is disabled, but still shouldn't lead to old references being
            # kept as `msg.author.guild` was already rebound (see above) at this point.
            new_author = msg.guild.get_member(msg.author.id)
            if new_author is not None and new_author is not msg.author:
                msg.author = new_author

    async def chunker(
        self,
        guild_id: int,
        query: str = "",
        limit: int = 0,
        presences: bool = False,
        *,
        shard_id: Optional[int] = None,
        nonce: Optional[str] = None,
    ) -> None:
        ws = self._get_websocket(guild_id, shard_id=shard_id)
        await ws.request_chunks(
            guild_id, query=query, limit=limit, presences=presences, nonce=nonce
        )

    async def _delay_ready(self) -> None:
        await self.shards_launched.wait()
        processed: List[Tuple[Guild, asyncio.Future[List[Member]]]] = []
        max_concurrency = len(self.shard_ids) * 2
        current_bucket = []
        while True:
            # this snippet of code is basically waiting N seconds
            # until the last GUILD_CREATE was sent
            try:
                guild = await asyncio.wait_for(
                    self._ready_state.get(), timeout=self.guild_ready_timeout
                )
            except asyncio.TimeoutError:
                break
            else:
                future: asyncio.Future[List[Member]]
                if self._guild_needs_chunking(guild):
                    _log.debug(
                        "Guild ID %d requires chunking, will be done in the background.", guild.id
                    )
                    if len(current_bucket) >= max_concurrency:
                        try:
                            await utils.sane_wait_for(
                                current_bucket, timeout=max_concurrency * 70.0
                            )
                        except asyncio.TimeoutError:
                            fmt = "Shard ID %s failed to wait for chunks from a sub-bucket with length %d"
                            _log.warning(fmt, guild.shard_id, len(current_bucket))
                        finally:
                            current_bucket = []

                    # Chunk the guild in the background while we wait for GUILD_CREATE streaming
                    future = asyncio.ensure_future(self.chunk_guild(guild))
                    current_bucket.append(future)
                else:
                    future = self.loop.create_future()
                    future.set_result([])

                processed.append((guild, future))

        # update references once the guild cache is repopulated
        self._update_guild_channel_references()

        guilds = sorted(processed, key=lambda g: g[0].shard_id)
        for shard_id, info in itertools.groupby(guilds, key=lambda g: g[0].shard_id):
            # this is equivalent to `children, futures = zip(*info)`, but typed properly
            children: List[Guild] = []
            futures: List[asyncio.Future[List[Member]]] = []
            for c, f in info:
                children.append(c)
                futures.append(f)

            # 110 reqs/minute w/ 1 req/guild plus some buffer
            timeout = 61 * (len(children) / 110)
            try:
                await utils.sane_wait_for(futures, timeout=timeout)
            except asyncio.TimeoutError:
                _log.warning(
                    "Shard ID %s failed to wait for chunks (timeout=%.2f) for %d guilds",
                    shard_id,
                    timeout,
                    len(guilds),
                )
            for guild in children:
                if guild.unavailable is False:
                    self.dispatch("guild_available", guild)
                else:
                    self.dispatch("guild_join", guild)

            self.dispatch("shard_ready", shard_id)

        # remove the state
        try:
            del self._ready_state
        except AttributeError:
            pass  # already been deleted somehow

        # clear the current task
        self._ready_task = None

        # update member references once guilds are chunked
        # note: this is always called regardless of whether chunking/caching is enabled;
        #       the bot member is always cached, so if any of the bot's own messages are
        #       cached, their `author` should be rebound to the new member object
        self._update_member_references()

        # dispatch the event
        self.call_handlers("ready")
        self.dispatch("ready")

    def parse_ready(self, data: gateway.ReadyEvent) -> None:
        if not hasattr(self, "_ready_state"):
            self._ready_state = asyncio.Queue()

        self.user = user = ClientUser(state=self, data=data["user"])
        # self._users is a list of Users, we're setting a ClientUser
        self._users[user.id] = user  # type: ignore

        try:
            application = data["application"]
        except KeyError:
            pass
        else:
            if self.application_id is None:
                self.application_id = utils._get_as_snowflake(application, "id")
            self.application_flags = ApplicationFlags._from_value(application["flags"])

        for guild_data in data["guilds"]:
            self._add_guild_from_data(guild_data)

        self.dispatch("connect")
        self.dispatch("shard_connect", data["__shard_id__"])  # type: ignore  # set in websocket receive
        self.call_handlers("connect_internal")

        if self._ready_task is None:
            self._ready_task = asyncio.create_task(self._delay_ready())

    def parse_resumed(self, data: gateway.ResumedEvent) -> None:
        self.dispatch("resumed")
        self.dispatch("shard_resumed", data["__shard_id__"])  # type: ignore  # set in websocket receive
