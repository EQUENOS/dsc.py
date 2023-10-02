# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
)

from .app_commands import application_command_factory
from .audit_logs import AuditLogEntry
from .automod import AutoModRule
from .bans import BanEntry
from .errors import NoMoreItems
from .guild_scheduled_event import GuildScheduledEvent
from .integrations import PartialIntegration
from .object import Object
from .threads import Thread
from .utils import maybe_coroutine, snowflake_time, time_snowflake

__all__ = (
    "ReactionIterator",
    "HistoryIterator",
    "BanIterator",
    "AuditLogIterator",
    "GuildIterator",
    "MemberIterator",
    "GuildScheduledEventUserIterator",
)

if TYPE_CHECKING:
    from .abc import Messageable, Snowflake
    from .app_commands import APIApplicationCommand
    from .guild import Guild
    from .member import Member
    from .message import Message
    from .state import ConnectionState
    from .types.audit_log import (
        AuditLog as AuditLogPayload,
        AuditLogEntry as AuditLogEntryPayload,
        AuditLogEvent,
    )
    from .types.guild import Ban as BanPayload, Guild as GuildPayload
    from .types.guild_scheduled_event import (
        GuildScheduledEventUser as GuildScheduledEventUserPayload,
    )
    from .types.message import Message as MessagePayload
    from .types.threads import Thread as ThreadPayload
    from .types.user import PartialUser as PartialUserPayload
    from .user import User

T = TypeVar("T")
OT = TypeVar("OT")
_Func = Callable[[T], Union[OT, Awaitable[OT]]]

OLDEST_OBJECT = Object(id=0)


class _AsyncIterator(AsyncIterator[T]):
    __slots__ = ()

    async def next(self) -> T:
        raise NotImplementedError

    def get(self, **attrs: Any) -> Awaitable[Optional[T]]:
        def predicate(elem: T) -> bool:
            for attr, val in attrs.items():
                nested = attr.split("__")
                obj = elem
                for attribute in nested:
                    obj = getattr(obj, attribute)

                if obj != val:
                    return False
            return True

        return self.find(predicate)

    async def find(self, predicate: _Func[T, bool]) -> Optional[T]:
        while True:
            try:
                elem = await self.next()
            except NoMoreItems:
                return None

            ret = await maybe_coroutine(predicate, elem)
            if ret:
                return elem

    def chunk(self, max_size: int) -> _ChunkedAsyncIterator[T]:
        if max_size <= 0:
            raise ValueError("async iterator chunk sizes must be greater than 0.")
        return _ChunkedAsyncIterator(self, max_size)

    def map(self, func: _Func[T, OT]) -> _MappedAsyncIterator[OT]:
        return _MappedAsyncIterator(self, func)

    def filter(self, predicate: _Func[T, bool]) -> _FilteredAsyncIterator[T]:
        return _FilteredAsyncIterator(self, predicate)

    async def flatten(self) -> List[T]:
        return [element async for element in self]

    async def __anext__(self) -> T:
        try:
            return await self.next()
        except NoMoreItems:
            raise StopAsyncIteration from None


class _ChunkedAsyncIterator(_AsyncIterator[List[T]]):
    def __init__(self, iterator: _AsyncIterator[T], max_size: int) -> None:
        self.iterator = iterator
        self.max_size = max_size

    async def next(self) -> List[T]:
        ret: List[T] = []
        n = 0
        while n < self.max_size:
            try:
                item = await self.iterator.next()
            except NoMoreItems:
                if ret:
                    return ret
                raise
            else:
                ret.append(item)
                n += 1
        return ret


class _MappedAsyncIterator(_AsyncIterator[OT]):
    def __init__(self, iterator: _AsyncIterator[T], func: _Func[T, OT]) -> None:
        self.iterator = iterator
        self.func = func

    async def next(self) -> OT:
        # this raises NoMoreItems and will propagate appropriately
        item = await self.iterator.next()
        return await maybe_coroutine(self.func, item)


class _FilteredAsyncIterator(_AsyncIterator[T]):
    def __init__(self, iterator: _AsyncIterator[T], predicate: _Func[T, bool]) -> None:
        self.iterator = iterator

        if predicate is None:
            predicate = lambda x: bool(x)

        self.predicate: _Func[T, bool] = predicate

    async def next(self) -> T:
        getter = self.iterator.next
        pred = self.predicate
        while True:
            # propagate NoMoreItems similar to _MappedAsyncIterator
            item = await getter()
            ret = await maybe_coroutine(pred, item)
            if ret:
                return item


class ReactionIterator(_AsyncIterator[Union["User", "Member"]]):
    def __init__(self, message, emoji, limit: int = 100, after=None, type: int = 0) -> None:
        self.message = message
        self.limit = limit
        self.after = after
        state = message._state
        self.getter = state.http.get_reaction_users
        self.state = state
        self.emoji = emoji
        self.guild = message.guild
        self.channel_id = message.channel.id
        self.users = asyncio.Queue()
        self.type = type

    async def next(self) -> Union[User, Member]:
        if self.users.empty():
            await self.fill_users()

        try:
            return self.users.get_nowait()
        except asyncio.QueueEmpty:
            raise NoMoreItems from None

    async def fill_users(self) -> None:
        if self.limit > 0:
            retrieve = min(self.limit, 100)

            after = self.after.id if self.after else None
            data: List[PartialUserPayload] = await self.getter(
                self.channel_id, self.message.id, self.emoji, retrieve, after=after, type=self.type
            )

            if data:
                self.limit -= retrieve
                self.after = Object(id=int(data[-1]["id"]))

            for element in reversed(data):
                if self.guild is None or isinstance(self.guild, Object):
                    await self.users.put(self.state.create_user(data=element))
                else:
                    member_id = int(element["id"])
                    member = self.guild.get_member(member_id)
                    if member is not None:
                        await self.users.put(member)
                    else:
                        await self.users.put(self.state.create_user(data=element))


class HistoryIterator(_AsyncIterator["Message"]):
    """Iterator for receiving a channel's message history.

    The messages endpoint has two behaviours we care about here:
    If ``before`` is specified, the messages endpoint returns the `limit`
    newest messages before ``before``, sorted with newest first. For filling over
    100 messages, update the ``before`` parameter to the oldest message received.
    Messages will be returned in order by time.
    If ``after`` is specified, it returns the ``limit`` oldest messages after
    ``after``, sorted with newest first. For filling over 100 messages, update the
    ``after`` parameter to the newest message received. If messages are not
    reversed, they will be out of order (99-0, 199-100, so on)

    A note that if both ``before`` and ``after`` are specified, ``before`` is ignored by the
    messages endpoint.

    Parameters
    ----------
    messageable: :class:`abc.Messageable`
        Messageable class to retrieve message history from.
    limit: :class:`int`
        Maximum number of messages to retrieve
    before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
        Message before which all messages must be.
    after: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
        Message after which all messages must be.
    around: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
        Message around which all messages must be. Limit max 101. Note that if
        limit is an even number, this will return at most limit+1 messages.
    oldest_first: Optional[:class:`bool`]
        If set to ``True``, return messages in oldest->newest order. Defaults to
        ``True`` if `after` is specified, otherwise ``False``.
    """

    def __init__(
        self,
        messageable: Messageable,
        limit: Optional[int] = 100,
        before: Optional[Union[Snowflake, datetime.datetime]] = None,
        after: Optional[Union[Snowflake, datetime.datetime]] = None,
        around: Optional[Union[Snowflake, datetime.datetime]] = None,
        oldest_first: Optional[bool] = None,
    ) -> None:
        if isinstance(before, datetime.datetime):
            before = Object(id=time_snowflake(before, high=False))
        if isinstance(after, datetime.datetime):
            after = Object(id=time_snowflake(after, high=True))
        if isinstance(around, datetime.datetime):
            around = Object(id=time_snowflake(around))

        if oldest_first is None:
            self.reverse = after is not None
        else:
            self.reverse = oldest_first

        self.messageable = messageable
        self.limit = limit
        self.before = before
        self.after = after or OLDEST_OBJECT
        self.around = around

        self._filter: Optional[Callable[[MessagePayload], bool]] = None

        self.state = self.messageable._state
        self.logs_from = self.state.http.logs_from
        self.messages = asyncio.Queue()

        if self.around:
            if self.limit is None:
                raise ValueError("history does not support around with limit=None")
            if self.limit > 101:
                raise ValueError("history max limit 101 when specifying around parameter")
            elif self.limit == 101:
                self.limit = 100  # Thanks Discord

            self._retrieve_messages = self._retrieve_messages_around_strategy
            if self.before and self.after:
                self._filter = lambda m: self.after.id < int(m["id"]) < self.before.id  # type: ignore
            elif self.before:
                self._filter = lambda m: int(m["id"]) < self.before.id  # type: ignore
            elif self.after:
                self._filter = lambda m: self.after.id < int(m["id"])
        else:
            if self.reverse:
                self._retrieve_messages = self._retrieve_messages_after_strategy
                if self.before:
                    self._filter = lambda m: int(m["id"]) < self.before.id  # type: ignore
            else:
                self._retrieve_messages = self._retrieve_messages_before_strategy
                if self.after and self.after != OLDEST_OBJECT:
                    self._filter = lambda m: int(m["id"]) > self.after.id

    async def next(self) -> Message:
        if self.messages.empty():
            await self.fill_messages()

        try:
            return self.messages.get_nowait()
        except asyncio.QueueEmpty:
            raise NoMoreItems from None

    def _get_retrieve(self):
        limit = self.limit
        if limit is None or limit > 100:
            retrieve = 100
        else:
            retrieve = limit
        self.retrieve = retrieve
        return retrieve > 0

    async def fill_messages(self) -> None:
        if not hasattr(self, "channel"):
            # do the required set up
            channel = await self.messageable._get_channel()
            self.channel = channel

        if self._get_retrieve():
            data = await self._retrieve_messages(self.retrieve)
            if len(data) < 100:
                self.limit = 0  # terminate the infinite loop

            if self.reverse:
                data = reversed(data)
            if self._filter:
                data = filter(self._filter, data)

            channel = self.channel
            for element in data:
                await self.messages.put(self.state.create_message(channel=channel, data=element))

    async def _retrieve_messages(self, retrieve) -> List[MessagePayload]:
        """Retrieve messages and update next parameters."""
        raise NotImplementedError

    async def _retrieve_messages_before_strategy(self, retrieve):
        """Retrieve messages using before parameter."""
        before = self.before.id if self.before else None
        data: List[MessagePayload] = await self.logs_from(self.channel.id, retrieve, before=before)
        if len(data):
            if self.limit is not None:
                self.limit -= retrieve
            self.before = Object(id=int(data[-1]["id"]))
        return data

    async def _retrieve_messages_after_strategy(self, retrieve):
        """Retrieve messages using after parameter."""
        after = self.after.id if self.after else None
        data: List[MessagePayload] = await self.logs_from(self.channel.id, retrieve, after=after)
        if len(data):
            if self.limit is not None:
                self.limit -= retrieve
            self.after = Object(id=int(data[0]["id"]))
        return data

    async def _retrieve_messages_around_strategy(self, retrieve):
        """Retrieve messages using around parameter."""
        if self.around:
            around = self.around.id if self.around else None
            data: List[MessagePayload] = await self.logs_from(
                self.channel.id, retrieve, around=around
            )
            self.around = None
            return data
        return []


class BanIterator(_AsyncIterator["BanEntry"]):
    """Iterator for receiving a guild's bans.

    The bans endpoint has two behaviours we care about here:
    If ``before`` is specified, the bans endpoint returns the ``limit``
    bans with user ids before ``before``, sorted with the oldest first. For filling over
    1000 bans, update the ``before`` parameter to the newest user received.
    If ``after`` is specified, it returns the ``limit`` bans with user ids after
    ``after``, sorted with the oldest first. For filling over 1000 bans, update the
    ``after`` parameter to the oldest user received.

    A note that if both ``before`` and ``after`` are specified, ``after`` is ignored by the
    bans endpoint.

    Parameters
    ----------
    guild: :class:`~disnake.Guild`
        The guild to get bans from.
    limit: Optional[:class:`int`]
        Maximum number of bans to retrieve.
    before: Optional[:class:`abc.Snowflake`]
        Object before which all bans must be.
    after: Optional[:class:`abc.Snowflake`]
        Object after which all bans must be.
    """

    def __init__(
        self,
        guild: Guild,
        limit: Optional[int] = None,
        before: Optional[Snowflake] = None,
        after: Optional[Snowflake] = None,
    ) -> None:
        self.guild = guild
        self.limit = limit
        self.before = before
        self.after = after or OLDEST_OBJECT

        self.state = self.guild._state
        self.get_bans = self.state.http.get_bans
        self.bans = asyncio.Queue()

        self._filter: Optional[Callable[[BanPayload], bool]] = None

        if self.before:
            self._retrieve_bans = self._retrieve_bans_before_strategy
            if self.after != OLDEST_OBJECT:
                self._filter = lambda b: int(b["user"]["id"]) > self.after.id
        else:
            self._retrieve_bans = self._retrieve_bans_after_strategy

    async def next(self) -> BanEntry:
        if self.bans.empty():
            await self.fill_bans()

        try:
            return self.bans.get_nowait()
        except asyncio.QueueEmpty:
            raise NoMoreItems from None

    def _get_retrieve(self) -> bool:
        self.retrieve = min(self.limit, 1000) if self.limit is not None else 1000
        return self.retrieve > 0

    async def fill_bans(self) -> None:
        if self._get_retrieve():
            data = await self._retrieve_bans(self.retrieve)
            if len(data) < 1000:
                self.limit = 0  # terminate the infinite loop

            if self._filter:
                data = filter(self._filter, data)

            for element in data:
                await self.bans.put(
                    BanEntry(
                        user=self.state.create_user(data=element["user"]),
                        reason=element["reason"],
                    )
                )

    async def _retrieve_bans_before_strategy(self, retrieve: int) -> List[BanPayload]:
        """Retrieve bans using before parameter."""
        before = self.before.id if self.before else None
        data: List[BanPayload] = await self.get_bans(self.guild.id, retrieve, before=before)
        if len(data):
            if self.limit is not None:
                self.limit -= len(data)
            self.before = Object(id=int(data[0]["user"]["id"]))
        return data

    async def _retrieve_bans_after_strategy(self, retrieve: int) -> List[BanPayload]:
        """Retrieve bans using after parameter."""
        after = self.after.id if self.after else None
        data: List[BanPayload] = await self.get_bans(self.guild.id, retrieve, after=after)
        if len(data):
            if self.limit is not None:
                self.limit -= len(data)
            self.after = Object(id=int(data[-1]["user"]["id"]))
        return data


class AuditLogIterator(_AsyncIterator["AuditLogEntry"]):
    def __init__(
        self,
        guild: Guild,
        limit: Optional[int] = None,
        before: Optional[Union[Snowflake, datetime.datetime]] = None,
        after: Optional[Union[Snowflake, datetime.datetime]] = None,
        user_id: Optional[int] = None,
        action_type: Optional[AuditLogEvent] = None,
        oldest_first: bool = False,
    ) -> None:
        if isinstance(before, datetime.datetime):
            before = Object(id=time_snowflake(before, high=False))
        if isinstance(after, datetime.datetime):
            after = Object(id=time_snowflake(after, high=True))

        self.limit: Optional[int] = limit
        self.before: Optional[Snowflake] = before
        self.after: Snowflake = after or OLDEST_OBJECT
        self.user_id: Optional[int] = user_id
        self.action_type: Optional[AuditLogEvent] = action_type

        self.guild = guild
        self._state = guild._state
        self.request = guild._state.http.get_audit_logs

        self.entries: asyncio.Queue[AuditLogEntry] = asyncio.Queue()

        self._filter: Optional[Callable[[AuditLogEntryPayload], bool]] = None
        if oldest_first:
            self._strategy = self._after_strategy
            if self.before:
                self._filter = lambda m: int(m["id"]) < self.before.id  # type: ignore
        else:
            self._strategy = self._before_strategy
            if self.after and self.after != OLDEST_OBJECT:
                self._filter = lambda m: int(m["id"]) > self.after.id

    async def _before_strategy(self, retrieve: int) -> AuditLogPayload:
        before = self.before.id if self.before else None
        data: AuditLogPayload = await self.request(
            self.guild.id,
            limit=retrieve,
            user_id=self.user_id,
            action_type=self.action_type,
            before=before,
        )

        entries = data.get("audit_log_entries", [])
        if entries:
            if self.limit is not None:
                self.limit -= retrieve
            self.before = Object(id=int(entries[-1]["id"]))
        return data

    async def _after_strategy(self, retrieve: int) -> AuditLogPayload:
        after = self.after.id
        data: AuditLogPayload = await self.request(
            self.guild.id,
            limit=retrieve,
            user_id=self.user_id,
            action_type=self.action_type,
            after=after,
        )

        entries = data.get("audit_log_entries", [])
        if entries:
            if self.limit is not None:
                self.limit -= retrieve
            # note: unlike other paginated endpoints, this one returns entries in ascending
            # order when using `after`; hence `-1` (instead of `0`) is correct here.
            self.after = Object(id=int(entries[-1]["id"]))
        return data

    async def next(self) -> AuditLogEntry:
        if self.entries.empty():
            await self._fill()

        try:
            return self.entries.get_nowait()
        except asyncio.QueueEmpty:
            raise NoMoreItems from None

    def _get_retrieve(self):
        limit = self.limit
        if limit is None or limit > 100:
            retrieve = 100
        else:
            retrieve = limit
        self.retrieve = retrieve
        return retrieve > 0

    async def _fill(self) -> None:
        if self._get_retrieve():
            log_data = await self._strategy(self.retrieve)
            entries = log_data.get("audit_log_entries")
            if len(entries) < 100:
                self.limit = 0  # terminate the infinite loop

            if self._filter:
                entries = filter(self._filter, entries)

            state = self._state

            appcmds: Dict[int, APIApplicationCommand] = {}
            for data in log_data.get("application_commands", []):
                try:
                    cmd = application_command_factory(data)
                except TypeError:
                    pass
                else:
                    appcmds[int(data["id"])] = cmd

            automod_rules = {
                int(data["id"]): AutoModRule(guild=self.guild, data=data)
                for data in log_data.get("auto_moderation_rules", [])
            }

            events = {
                int(data["id"]): GuildScheduledEvent(state=state, data=data)
                for data in log_data.get("guild_scheduled_events", [])
            }

            integrations = {
                int(data["id"]): PartialIntegration(guild=self.guild, data=data)
                for data in log_data.get("integrations", [])
            }

            threads = {
                int(data["id"]): Thread(guild=self.guild, state=state, data=data)
                for data in log_data.get("threads", [])
            }

            users = {int(data["id"]): state.create_user(data) for data in log_data.get("users", [])}

            webhooks = {
                int(data["id"]): state.create_webhook(data) for data in log_data.get("webhooks", [])
            }

            for element in entries:
                # TODO: remove this if statement later
                if element["action_type"] is None:
                    continue

                await self.entries.put(
                    AuditLogEntry(
                        data=element,
                        guild=self.guild,
                        application_commands=appcmds,
                        automod_rules=automod_rules,
                        guild_scheduled_events=events,
                        integrations=integrations,
                        threads=threads,
                        users=users,
                        webhooks=webhooks,
                    )
                )


class GuildIterator(_AsyncIterator["Guild"]):
    """Iterator for receiving the client's guilds.

    The guilds endpoint has the same two behaviours as described
    in :class:`HistoryIterator`:
    If ``before`` is specified, the guilds endpoint returns the ``limit``
    newest guilds before ``before``, sorted with newest first. For filling over
    100 guilds, update the ``before`` parameter to the oldest guild received.
    Guilds will be returned in order by time.
    If `after` is specified, it returns the ``limit`` oldest guilds after ``after``,
    sorted with newest first. For filling over 100 guilds, update the ``after``
    parameter to the newest guild received, If guilds are not reversed, they
    will be out of order (99-0, 199-100, so on)

    Not that if both ``before`` and ``after`` are specified, ``before`` is ignored by the
    guilds endpoint.

    Parameters
    ----------
    bot: :class:`disnake.Client`
        The client to retrieve the guilds from.
    limit: :class:`int`
        Maximum number of guilds to retrieve.
    before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
        Object before which all guilds must be.
    after: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
        Object after which all guilds must be.
    """

    def __init__(
        self, bot, limit: Optional[int], before=None, after=None, with_counts: bool = True
    ) -> None:
        if isinstance(before, datetime.datetime):
            before = Object(id=time_snowflake(before, high=False))
        if isinstance(after, datetime.datetime):
            after = Object(id=time_snowflake(after, high=True))

        self.bot = bot
        self.limit = limit
        self.before = before
        self.after = after
        self.with_counts = with_counts

        self._filter = None

        self.state = self.bot._connection
        self.get_guilds = self.bot.http.get_guilds
        self.guilds = asyncio.Queue()

        if self.before:
            self.reverse = True
            self._retrieve_guilds = self._retrieve_guilds_before_strategy  # type: ignore
            if self.after:
                self._filter = lambda m: int(m["id"]) > self.after.id  # type: ignore
        else:
            self.reverse = False
            self._retrieve_guilds = self._retrieve_guilds_after_strategy  # type: ignore

    async def next(self) -> Guild:
        if self.guilds.empty():
            await self.fill_guilds()

        try:
            return self.guilds.get_nowait()
        except asyncio.QueueEmpty:
            raise NoMoreItems from None

    def _get_retrieve(self):
        limit = self.limit
        if limit is None or limit > 200:
            retrieve = 200
        else:
            retrieve = limit
        self.retrieve = retrieve
        return retrieve > 0

    def create_guild(self, data):
        from .guild import Guild

        return Guild(state=self.state, data=data)

    async def fill_guilds(self) -> None:
        if self._get_retrieve():
            data = await self._retrieve_guilds(self.retrieve)
            if len(data) < 200:
                self.limit = 0

            if self.reverse:
                data = reversed(data)
            if self._filter:
                data = filter(self._filter, data)

            for element in data:
                await self.guilds.put(self.create_guild(element))

    async def _retrieve_guilds(self, retrieve) -> List[Guild]:
        """Retrieve guilds and update next parameters."""
        raise NotImplementedError

    async def _retrieve_guilds_before_strategy(self, retrieve):
        """Retrieve guilds using before parameter."""
        before = self.before.id if self.before else None
        data: List[GuildPayload] = await self.get_guilds(
            retrieve, before=before, with_counts=self.with_counts
        )
        if len(data):
            if self.limit is not None:
                self.limit -= retrieve
            self.before = Object(id=int(data[0]["id"]))
        return data

    async def _retrieve_guilds_after_strategy(self, retrieve):
        """Retrieve guilds using after parameter."""
        after = self.after.id if self.after else None
        data: List[GuildPayload] = await self.get_guilds(
            retrieve, after=after, with_counts=self.with_counts
        )
        if len(data):
            if self.limit is not None:
                self.limit -= retrieve
            self.after = Object(id=int(data[-1]["id"]))
        return data


class MemberIterator(_AsyncIterator["Member"]):
    def __init__(self, guild, limit: Optional[int] = 1000, after=None) -> None:
        if isinstance(after, datetime.datetime):
            after = Object(id=time_snowflake(after, high=True))

        self.guild = guild
        self.limit = limit
        self.after = after or OLDEST_OBJECT

        self.state = self.guild._state
        self.get_members = self.state.http.get_members
        self.members = asyncio.Queue()

    async def next(self) -> Member:
        if self.members.empty():
            await self.fill_members()

        try:
            return self.members.get_nowait()
        except asyncio.QueueEmpty:
            raise NoMoreItems from None

    def _get_retrieve(self):
        limit = self.limit
        if limit is None or limit > 1000:
            retrieve = 1000
        else:
            retrieve = limit
        self.retrieve = retrieve
        return retrieve > 0

    async def fill_members(self) -> None:
        if self._get_retrieve():
            after = self.after.id if self.after else None
            data = await self.get_members(self.guild.id, self.retrieve, after)
            if not data:
                # no data, terminate
                return

            if len(data) < 1000:
                self.limit = 0  # terminate loop

            self.after = Object(id=int(data[-1]["user"]["id"]))

            for element in reversed(data):
                await self.members.put(self.create_member(element))

    def create_member(self, data):
        from .member import Member

        return Member(data=data, guild=self.guild, state=self.state)


class ArchivedThreadIterator(_AsyncIterator["Thread"]):
    def __init__(
        self,
        channel_id: int,
        guild: Guild,
        limit: Optional[int],
        joined: bool,
        private: bool,
        before: Optional[Union[Snowflake, datetime.datetime]] = None,
    ) -> None:
        self.channel_id = channel_id
        self.guild = guild
        self.limit = limit
        self.joined = joined
        self.private = private
        self.http = guild._state.http

        if joined and not private:
            raise ValueError("Cannot iterate over joined public archived threads")

        self.before: Optional[str]
        if before is None:
            self.before = None
        elif isinstance(before, datetime.datetime):
            if joined:
                self.before = str(time_snowflake(before, high=False))
            else:
                self.before = before.isoformat()
        else:
            if joined:
                self.before = str(before.id)
            else:
                self.before = snowflake_time(before.id).isoformat()

        self.update_before: Callable[[ThreadPayload], str] = self.get_archive_timestamp

        if joined:
            self.endpoint = self.http.get_joined_private_archived_threads
            self.update_before = self.get_thread_id
        elif private:
            self.endpoint = self.http.get_private_archived_threads
        else:
            self.endpoint = self.http.get_public_archived_threads

        self.queue: asyncio.Queue[Thread] = asyncio.Queue()
        self.has_more: bool = True

    async def next(self) -> Thread:
        if self.queue.empty():
            await self.fill_queue()

        try:
            return self.queue.get_nowait()
        except asyncio.QueueEmpty:
            raise NoMoreItems from None

    @staticmethod
    def get_archive_timestamp(data: ThreadPayload) -> str:
        return data["thread_metadata"]["archive_timestamp"]

    @staticmethod
    def get_thread_id(data: ThreadPayload) -> str:
        return data["id"]  # type: ignore

    async def fill_queue(self) -> None:
        if not self.has_more:
            raise NoMoreItems

        limit = 50 if self.limit is None else max(self.limit, 50)
        data = await self.endpoint(self.channel_id, before=self.before, limit=limit)

        # This stuff is obviously WIP because 'members' is always empty
        threads: List[ThreadPayload] = data.get("threads", [])
        for d in reversed(threads):
            self.queue.put_nowait(self.create_thread(d))

        self.has_more = data.get("has_more", False)
        if self.limit is not None:
            self.limit -= len(threads)
            if self.limit <= 0:
                self.has_more = False

        if self.has_more:
            self.before = self.update_before(threads[-1])

    def create_thread(self, data: ThreadPayload) -> Thread:
        from .threads import Thread

        return Thread(guild=self.guild, state=self.guild._state, data=data)


class GuildScheduledEventUserIterator(_AsyncIterator[Union["User", "Member"]]):
    def __init__(
        self,
        event: GuildScheduledEvent,
        limit: Optional[int],
        with_members: bool,
        before: Optional[Snowflake],
        after: Optional[Snowflake],
    ) -> None:
        self.event: GuildScheduledEvent = event
        self.limit: Optional[int] = limit
        self.with_members: bool = with_members
        self.before: Optional[Snowflake] = before
        self.after: Optional[Snowflake] = after

        self.state: ConnectionState = event._state
        self.get_event_users = self.state.http.get_guild_scheduled_event_users
        self.users = asyncio.Queue()

        self._filter: Optional[Callable[[GuildScheduledEventUserPayload], bool]] = None
        if self.before is not None:
            self._strategy = self._before_strategy
            if self.after is not None:
                self._filter = lambda u: int(u["user"]["id"]) > cast("Snowflake", self.after).id
            # reverse if using `before` strategy, since chunks are always received in
            # ascending order (200-299, 100-199, 0-99) regardless of before/after
            self.reverse = True
        else:
            self._strategy = self._after_strategy
            self.reverse = False

    async def next(self) -> Message:
        if self.users.empty():
            await self.fill_users()

        try:
            return self.users.get_nowait()
        except asyncio.QueueEmpty:
            raise NoMoreItems from None

    def _get_retrieve(self) -> bool:
        limit = self.limit
        if limit is None or limit > 100:
            retrieve = 100
        else:
            retrieve = limit
        self.retrieve: int = retrieve
        return retrieve > 0

    def create_user(self, data: GuildScheduledEventUserPayload) -> Union[User, Member]:
        from .member import Member

        user_data = data["user"]
        member_data = data.get("member")
        if member_data is not None and (guild := self.event.guild) is not None:
            return guild.get_member(int(user_data["id"])) or Member(
                data=member_data, user_data=user_data, guild=guild, state=self.state
            )
        else:
            return self.state.store_user(data["user"])

    async def fill_users(self) -> None:
        if not self._get_retrieve():
            return

        data = await self._strategy(self.retrieve)
        if len(data) < 100:
            self.limit = 0  # terminate loop

        if self.reverse:
            data = reversed(data)
        if self._filter:
            data = filter(self._filter, data)

        for user in data:
            await self.users.put(self.create_user(user))

    async def _before_strategy(self, retrieve: int) -> List[GuildScheduledEventUserPayload]:
        before = self.before.id if self.before else None
        data = await self.get_event_users(
            self.event.guild_id,
            self.event.id,
            limit=retrieve,
            with_member=self.with_members,
            before=before,
        )

        if len(data):
            if self.limit is not None:
                self.limit -= retrieve
            # users are always returned in ascending order
            self.before = Object(id=int(data[0]["user"]["id"]))
        return data

    async def _after_strategy(self, retrieve: int) -> List[GuildScheduledEventUserPayload]:
        after = self.after.id if self.after else None
        data = await self.get_event_users(
            self.event.guild_id,
            self.event.id,
            limit=retrieve,
            with_member=self.with_members,
            after=after,
        )

        if len(data):
            if self.limit is not None:
                self.limit -= retrieve
            self.after = Object(id=int(data[-1]["user"]["id"]))
        return data
