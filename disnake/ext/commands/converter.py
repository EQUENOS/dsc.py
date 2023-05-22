# SPDX-License-Identifier: MIT

from __future__ import annotations

import functools
import inspect
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Literal,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)

import disnake

from .context import AnyContext, Context
from .errors import (
    BadArgument,
    BadBoolArgument,
    BadColourArgument,
    BadInviteArgument,
    BadLiteralArgument,
    BadUnionArgument,
    ChannelNotFound,
    ChannelNotReadable,
    CommandError,
    ConversionError,
    EmojiNotFound,
    GuildNotFound,
    GuildScheduledEventNotFound,
    GuildStickerNotFound,
    MemberNotFound,
    MessageNotFound,
    NoPrivateMessage,
    ObjectNotFound,
    PartialEmojiConversionFailure,
    RoleNotFound,
    ThreadNotFound,
    UserNotFound,
)

if TYPE_CHECKING:
    from disnake.abc import MessageableChannel


# TODO: USE ACTUAL FUNCTIONS INSTEAD OF USELESS CLASSES

__all__ = (
    "Converter",
    "IDConverter",
    "ObjectConverter",
    "MemberConverter",
    "UserConverter",
    "PartialMessageConverter",
    "MessageConverter",
    "GuildChannelConverter",
    "TextChannelConverter",
    "VoiceChannelConverter",
    "StageChannelConverter",
    "CategoryChannelConverter",
    "ForumChannelConverter",
    "ThreadConverter",
    "ColourConverter",
    "ColorConverter",
    "RoleConverter",
    "GameConverter",
    "InviteConverter",
    "GuildConverter",
    "EmojiConverter",
    "PartialEmojiConverter",
    "GuildStickerConverter",
    "PermissionsConverter",
    "GuildScheduledEventConverter",
    "clean_content",
    "Greedy",
    "run_converters",
)


_utils_get = disnake.utils.get
T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
CT = TypeVar("CT", bound=disnake.abc.GuildChannel)
TT = TypeVar("TT", bound=disnake.Thread)


def _get_from_guilds(
    client: disnake.Client, func: Callable[[disnake.Guild], Optional[T]]
) -> Optional[T]:
    for guild in client.guilds:
        if result := func(guild):
            return result
    return None


@runtime_checkable
class Converter(Protocol[T_co]):
    """The base class of custom converters that require the :class:`.Context`
    or :class:`.ApplicationCommandInteraction` to be passed to be useful.

    This allows you to implement converters that function similar to the
    special cased ``disnake`` classes.

    Classes that derive from this should override the :meth:`~.Converter.convert`
    method to do its conversion logic. This method must be a :ref:`coroutine <coroutine>`.
    """

    async def convert(self, ctx: AnyContext, argument: str) -> T_co:
        """|coro|

        The method to override to do conversion logic.

        If an error is found while converting, it is recommended to
        raise a :exc:`.CommandError` derived exception as it will
        properly propagate to the error handlers.

        Parameters
        ----------
        ctx: Union[:class:`.Context`, :class:`.ApplicationCommandInteraction`]
            The invocation context that the argument is being used in.
        argument: :class:`str`
            The argument that is being converted.

        Raises
        ------
        CommandError
            A generic exception occurred when converting the argument.
        BadArgument
            The converter failed to convert the argument.
        """
        raise NotImplementedError("Derived classes need to implement this.")


_ID_REGEX = re.compile(r"([0-9]{17,19})$")


class IDConverter(Converter[T_co]):
    @staticmethod
    def _get_id_match(argument: str) -> Optional[re.Match[str]]:
        return _ID_REGEX.match(argument)


class ObjectConverter(IDConverter[disnake.Object]):
    """Converts to a :class:`~disnake.Object`.

    The argument must follow the valid ID or mention formats (e.g. `<@80088516616269824>`).

    .. versionadded:: 2.0

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by member, role, or channel mention.
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Object:
        match = self._get_id_match(argument) or re.match(
            r"<(?:@(?:!|&)?|#)([0-9]{17,19})>$", argument
        )

        if match is None:
            raise ObjectNotFound(argument)

        result = int(match.group(1))

        return disnake.Object(id=result)


class MemberConverter(IDConverter[disnake.Member]):
    """Converts to a :class:`~disnake.Member`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name#discrim
    4. Lookup by name
    5. Lookup by nickname

    .. versionchanged:: 1.5
        Raise :exc:`.MemberNotFound` instead of generic :exc:`.BadArgument`

    .. versionchanged:: 1.5.1
        This converter now lazily fetches members from the gateway and HTTP APIs,
        optionally caching the result if :attr:`.MemberCacheFlags.joined` is enabled.
    """

    async def query_member_named(
        self, guild: disnake.Guild, argument: str
    ) -> Optional[disnake.Member]:
        cache = guild._state.member_cache_flags.joined
        if len(argument) > 5 and argument[-5] == "#":
            username, _, discriminator = argument.rpartition("#")
            members = await guild.query_members(username, limit=100, cache=cache)
            return _utils_get(members, name=username, discriminator=discriminator)

        members = await guild.query_members(argument, limit=100, cache=cache)
        return disnake.utils.find(lambda m: m.name == argument or m.nick == argument, members)

    async def query_member_by_id(
        self, bot: disnake.Client, guild: disnake.Guild, user_id: int
    ) -> Optional[disnake.Member]:
        ws = bot._get_websocket(shard_id=guild.shard_id)
        cache = guild._state.member_cache_flags.joined
        if ws.is_ratelimited():
            # If we're being rate limited on the WS, then fall back to using the HTTP API
            # So we don't have to wait ~60 seconds for the query to finish
            try:
                member = await guild.fetch_member(user_id)
            except disnake.HTTPException:
                return None

            if cache:
                guild._add_member(member)
            return member

        # If we're not being rate limited then we can use the websocket to actually query
        members = await guild.query_members(limit=1, user_ids=[user_id], cache=cache)
        if not members:
            return None
        return members[0]

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Member:
        bot: disnake.Client = ctx.bot
        match = self._get_id_match(argument) or re.match(r"<@!?([0-9]{17,19})>$", argument)
        guild = ctx.guild
        result: Optional[disnake.Member] = None
        user_id: Optional[int] = None

        if match is None:
            # not a mention...
            if guild:
                result = guild.get_member_named(argument)
            else:
                result = _get_from_guilds(bot, lambda g: g.get_member_named(argument))
        else:
            user_id = int(match.group(1))
            if guild:
                mentions: Iterable[disnake.Member]
                if isinstance(ctx, Context):
                    mentions = (
                        user for user in ctx.message.mentions if isinstance(user, disnake.Member)
                    )
                else:
                    mentions = []
                result = guild.get_member(user_id) or _utils_get(mentions, id=user_id)
            else:
                result = _get_from_guilds(bot, lambda g: g.get_member(user_id))

        if result is None:
            if guild is None:
                raise MemberNotFound(argument)

            if user_id is not None:
                result = await self.query_member_by_id(bot, guild, user_id)
            else:
                result = await self.query_member_named(guild, argument)

            if not result:
                raise MemberNotFound(argument)

        return result


class UserConverter(IDConverter[disnake.User]):
    """Converts to a :class:`~disnake.User`.

    All lookups are via the global user cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name#discrim
    4. Lookup by name

    .. versionchanged:: 1.5
        Raise :exc:`.UserNotFound` instead of generic :exc:`.BadArgument`

    .. versionchanged:: 1.6
        This converter now lazily fetches users from the HTTP APIs if an ID is passed
        and it's not available in cache.
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.User:
        match = self._get_id_match(argument) or re.match(r"<@!?([0-9]{17,19})>$", argument)
        state = ctx._state
        bot: disnake.Client = ctx.bot
        result: Optional[Union[disnake.User, disnake.Member]] = None

        if match is not None:
            user_id = int(match.group(1))

            mentions: Iterable[Union[disnake.User, disnake.Member]]
            if isinstance(ctx, Context):
                mentions = ctx.message.mentions
            else:
                mentions = []
            result = bot.get_user(user_id) or _utils_get(mentions, id=user_id)

            if result is None:
                try:
                    result = await bot.fetch_user(user_id)
                except disnake.HTTPException:
                    raise UserNotFound(argument) from None

            if isinstance(result, disnake.Member):
                return result._user
            return result

        arg = argument

        # Remove the '@' character if this is the first character from the argument
        if arg[0] == "@":
            # Remove first character
            arg = arg[1:]

        # check for discriminator if it exists,
        if len(arg) > 5 and arg[-5] == "#":
            discrim = arg[-4:]
            name = arg[:-5]
            result = disnake.utils.find(
                lambda u: u.name == name and u.discriminator == discrim, state._users.values()
            )
            if result is not None:
                return result

        result = disnake.utils.find(lambda u: u.name == arg, state._users.values())

        if result is None:
            raise UserNotFound(argument)

        return result


class PartialMessageConverter(Converter[disnake.PartialMessage]):
    """Converts to a :class:`~disnake.PartialMessage`.

    .. versionadded:: 1.7

    The creation strategy is as follows (in order):

    1. By "{channel ID}-{message ID}" (retrieved by shift-clicking on "Copy ID")
    2. By message ID (The message is assumed to be in the context channel.)
    3. By message URL
    """

    @staticmethod
    def _get_id_matches(ctx: AnyContext, argument: str) -> Tuple[Optional[int], int, int]:
        id_regex = re.compile(r"(?:(?P<channel_id>[0-9]{17,19})-)?(?P<message_id>[0-9]{17,19})$")
        link_regex = re.compile(
            r"https?://(?:(ptb|canary|www)\.)?discord(?:app)?\.com/channels/"
            r"(?P<guild_id>[0-9]{17,19}|@me)"
            r"/(?P<channel_id>[0-9]{17,19})/(?P<message_id>[0-9]{17,19})/?$"
        )
        match = id_regex.match(argument) or link_regex.match(argument)
        if not match:
            raise MessageNotFound(argument)
        data = match.groupdict()
        channel_id = disnake.utils._get_as_snowflake(data, "channel_id") or ctx.channel.id
        message_id = int(data["message_id"])
        guild_id_str: Optional[str] = data.get("guild_id")
        if guild_id_str is None:
            guild_id = ctx.guild and ctx.guild.id
        elif guild_id_str == "@me":
            guild_id = None
        else:
            guild_id = int(guild_id_str)
        return guild_id, message_id, channel_id

    @staticmethod
    def _resolve_channel(
        ctx: AnyContext, guild_id: Optional[int], channel_id: int
    ) -> Optional[MessageableChannel]:
        bot: disnake.Client = ctx.bot
        if guild_id is None:
            return bot.get_channel(channel_id) if channel_id else ctx.channel  # type: ignore

        guild = bot.get_guild(guild_id)
        if guild is not None:
            return guild._resolve_channel(channel_id)  # type: ignore
        return None

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.PartialMessage:
        guild_id, message_id, channel_id = self._get_id_matches(ctx, argument)
        channel = self._resolve_channel(ctx, guild_id, channel_id)
        if not channel:
            raise ChannelNotFound(str(channel_id))
        return disnake.PartialMessage(channel=channel, id=message_id)


class MessageConverter(IDConverter[disnake.Message]):
    """Converts to a :class:`~disnake.Message`.

    .. versionadded:: 1.1

    The lookup strategy is as follows (in order):

    1. Lookup by "{channel ID}-{message ID}" (retrieved by shift-clicking on "Copy ID")
    2. Lookup by message ID (the message **must** be in the context channel)
    3. Lookup by message URL

    .. versionchanged:: 1.5
        Raise :exc:`.ChannelNotFound`, :exc:`.MessageNotFound` or :exc:`.ChannelNotReadable` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Message:
        guild_id, message_id, channel_id = PartialMessageConverter._get_id_matches(ctx, argument)
        bot: disnake.Client = ctx.bot
        message = bot._connection._get_message(message_id)
        if message:
            return message
        channel = PartialMessageConverter._resolve_channel(ctx, guild_id, channel_id)
        if not channel:
            raise ChannelNotFound(str(channel_id))
        try:
            return await channel.fetch_message(message_id)
        except disnake.NotFound:
            raise MessageNotFound(argument) from None
        except disnake.Forbidden:
            raise ChannelNotReadable(channel) from None  # type: ignore


class GuildChannelConverter(IDConverter[disnake.abc.GuildChannel]):
    """Converts to a :class:`.abc.GuildChannel`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name.

    .. versionadded:: 2.0
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.abc.GuildChannel:
        return self._resolve_channel(ctx, argument, "channels", disnake.abc.GuildChannel)

    @staticmethod
    def _resolve_channel(ctx: AnyContext, argument: str, attribute: str, type: Type[CT]) -> CT:
        bot: disnake.Client = ctx.bot

        match = IDConverter._get_id_match(argument) or re.match(r"<#([0-9]{17,19})>$", argument)
        result: Optional[disnake.abc.GuildChannel] = None
        guild = ctx.guild

        if match is None:
            # not a mention
            if guild:
                iterable: Iterable[CT] = getattr(guild, attribute)
                result = _utils_get(iterable, name=argument)
            else:
                result = disnake.utils.find(
                    lambda c: isinstance(c, type) and c.name == argument, bot.get_all_channels()
                )
        else:
            channel_id = int(match.group(1))
            if guild:
                result = guild.get_channel(channel_id)
            else:
                result = _get_from_guilds(bot, lambda g: g.get_channel(channel_id))

        if not isinstance(result, type):
            raise ChannelNotFound(argument)

        return result

    @staticmethod
    def _resolve_thread(ctx: AnyContext, argument: str, attribute: str, type: Type[TT]) -> TT:
        match = IDConverter._get_id_match(argument) or re.match(r"<#([0-9]{17,19})>$", argument)
        result: Optional[disnake.Thread] = None
        guild = ctx.guild

        if match is None:
            # not a mention
            if guild:
                iterable: Iterable[TT] = getattr(guild, attribute)
                result = _utils_get(iterable, name=argument)
        else:
            thread_id = int(match.group(1))
            if guild:
                result = guild.get_thread(thread_id)

        if not isinstance(result, type):
            raise ThreadNotFound(argument)

        return result


class TextChannelConverter(IDConverter[disnake.TextChannel]):
    """Converts to a :class:`~disnake.TextChannel`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name

    .. versionchanged:: 1.5
        Raise :exc:`.ChannelNotFound` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.TextChannel:
        return GuildChannelConverter._resolve_channel(
            ctx, argument, "text_channels", disnake.TextChannel
        )


class VoiceChannelConverter(IDConverter[disnake.VoiceChannel]):
    """Converts to a :class:`~disnake.VoiceChannel`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name

    .. versionchanged:: 1.5
        Raise :exc:`.ChannelNotFound` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.VoiceChannel:
        return GuildChannelConverter._resolve_channel(
            ctx, argument, "voice_channels", disnake.VoiceChannel
        )


class StageChannelConverter(IDConverter[disnake.StageChannel]):
    """Converts to a :class:`~disnake.StageChannel`.

    .. versionadded:: 1.7

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.StageChannel:
        return GuildChannelConverter._resolve_channel(
            ctx, argument, "stage_channels", disnake.StageChannel
        )


class CategoryChannelConverter(IDConverter[disnake.CategoryChannel]):
    """Converts to a :class:`~disnake.CategoryChannel`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name

    .. versionchanged:: 1.5
        Raise :exc:`.ChannelNotFound` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.CategoryChannel:
        return GuildChannelConverter._resolve_channel(
            ctx, argument, "categories", disnake.CategoryChannel
        )


class ForumChannelConverter(IDConverter[disnake.ForumChannel]):
    """Converts to a :class:`~disnake.ForumChannel`.

    .. versionadded:: 2.5

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.ForumChannel:
        return GuildChannelConverter._resolve_channel(
            ctx, argument, "forum_channels", disnake.ForumChannel
        )


class ThreadConverter(IDConverter[disnake.Thread]):
    """Coverts to a :class:`~disnake.Thread`.

    All lookups are via the local guild.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name.

    .. versionadded:: 2.0
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Thread:
        return GuildChannelConverter._resolve_thread(ctx, argument, "threads", disnake.Thread)


class ColourConverter(Converter[disnake.Colour]):
    """Converts to a :class:`~disnake.Colour`.

    .. versionchanged:: 1.5
        Add an alias named ColorConverter

    The following formats are accepted:

    - ``0x<hex>``
    - ``#<hex>``
    - ``0x#<hex>``
    - ``rgb(<number>, <number>, <number>)``
    - Any of the ``classmethod`` in :class:`~disnake.Colour`

        - The ``_`` in the name can be optionally replaced with spaces.

    Like CSS, ``<number>`` can be either 0-255 or 0-100% and ``<hex>`` can be
    either a 6 digit hex number or a 3 digit hex shortcut (e.g. #fff).

    .. versionchanged:: 1.5
        Raise :exc:`.BadColourArgument` instead of generic :exc:`.BadArgument`

    .. versionchanged:: 1.7
        Added support for ``rgb`` function and 3-digit hex shortcuts
    """

    RGB_REGEX = re.compile(
        r"rgb\s*\((?P<r>[0-9]{1,3}%?)\s*,\s*(?P<g>[0-9]{1,3}%?)\s*,\s*(?P<b>[0-9]{1,3}%?)\s*\)"
    )

    def parse_hex_number(self, argument: str) -> disnake.Color:
        arg = "".join(i * 2 for i in argument) if len(argument) == 3 else argument
        try:
            value = int(arg, base=16)
            if not (0 <= value <= 0xFFFFFF):
                raise BadColourArgument(argument)
        except ValueError:
            raise BadColourArgument(argument) from None
        else:
            return disnake.Color(value=value)

    def parse_rgb_number(self, argument: str, number: str) -> int:
        if number[-1] == "%":
            value = int(number[:-1])
            if not (0 <= value <= 100):
                raise BadColourArgument(argument)
            return round(255 * (value / 100))

        value = int(number)
        if not (0 <= value <= 255):
            raise BadColourArgument(argument)
        return value

    def parse_rgb(self, argument: str, *, regex: re.Pattern[str] = RGB_REGEX) -> disnake.Color:
        match = regex.match(argument)
        if match is None:
            raise BadColourArgument(argument)

        red = self.parse_rgb_number(argument, match.group("r"))
        green = self.parse_rgb_number(argument, match.group("g"))
        blue = self.parse_rgb_number(argument, match.group("b"))
        return disnake.Color.from_rgb(red, green, blue)

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Color:
        if argument[0] == "#":
            return self.parse_hex_number(argument[1:])

        if argument[0:2] == "0x":
            rest = argument[2:]
            # Legacy backwards compatible syntax
            if rest.startswith("#"):
                return self.parse_hex_number(rest[1:])
            return self.parse_hex_number(rest)

        arg = argument.lower()
        if arg[0:3] == "rgb":
            return self.parse_rgb(arg)

        arg = arg.replace(" ", "_")
        method = getattr(disnake.Colour, arg, None)
        if arg.startswith("from_") or method is None or not inspect.ismethod(method):
            raise BadColourArgument(arg)
        return method()


ColorConverter = ColourConverter


class RoleConverter(IDConverter[disnake.Role]):
    """Converts to a :class:`~disnake.Role`.

    All lookups are via the local guild. If in a DM context, the converter raises
    :exc:`.NoPrivateMessage` exception.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name

    .. versionchanged:: 1.5
        Raise :exc:`.RoleNotFound` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Role:
        guild = ctx.guild
        if not guild:
            raise NoPrivateMessage

        match = self._get_id_match(argument) or re.match(r"<@&([0-9]{17,19})>$", argument)
        if match:
            result = guild.get_role(int(match.group(1)))
        else:
            result = _utils_get(guild._roles.values(), name=argument)

        if result is None:
            raise RoleNotFound(argument)
        return result


class GameConverter(Converter[disnake.Game]):
    """Converts to :class:`~disnake.Game`."""

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Game:
        return disnake.Game(name=argument)


class InviteConverter(Converter[disnake.Invite]):
    """Converts to a :class:`~disnake.Invite`.

    This is done via an HTTP request using :meth:`.Bot.fetch_invite`.

    .. versionchanged:: 1.5
        Raise :exc:`.BadInviteArgument` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Invite:
        try:
            return await ctx.bot.fetch_invite(argument)
        except Exception as exc:
            raise BadInviteArgument(argument) from exc


class GuildConverter(IDConverter[disnake.Guild]):
    """Converts to a :class:`~disnake.Guild`.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by name. (There is no disambiguation for Guilds with multiple matching names).

    .. versionadded:: 1.7
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Guild:
        match = self._get_id_match(argument)
        bot: disnake.Client = ctx.bot
        result: Optional[disnake.Guild] = None

        if match is not None:
            guild_id = int(match.group(1))
            result = bot.get_guild(guild_id)

        if result is None:
            result = _utils_get(bot.guilds, name=argument)

            if result is None:
                raise GuildNotFound(argument)
        return result


class EmojiConverter(IDConverter[disnake.Emoji]):
    """Converts to a :class:`~disnake.Emoji`.

    All lookups are done for the local guild first, if available. If that lookup
    fails, then it checks the client's global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by extracting ID from the emoji.
    3. Lookup by name

    .. versionchanged:: 1.5
        Raise :exc:`.EmojiNotFound` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Emoji:
        match = self._get_id_match(argument) or re.match(
            r"<a?:[a-zA-Z0-9\_]{1,32}:([0-9]{17,19})>$", argument
        )
        result: Optional[disnake.Emoji] = None
        bot = ctx.bot
        guild = ctx.guild

        if match is None:
            # Try to get the emoji by name. Try local guild first.
            if guild:
                result = _utils_get(guild.emojis, name=argument)

            if result is None:
                result = _utils_get(bot.emojis, name=argument)
        else:
            # Try to look up emoji by id.
            result = bot.get_emoji(int(match.group(1)))

        if result is None:
            raise EmojiNotFound(argument)

        return result


class PartialEmojiConverter(Converter[disnake.PartialEmoji]):
    """Converts to a :class:`~disnake.PartialEmoji`.

    This is done by extracting the animated flag, name and ID from the emoji.

    .. versionchanged:: 1.5
        Raise :exc:`.PartialEmojiConversionFailure` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.PartialEmoji:
        match = re.match(r"<(a?):([a-zA-Z0-9\_]{1,32}):([0-9]{17,19})>$", argument)

        if match:
            emoji_animated = bool(match.group(1))
            emoji_name: str = match.group(2)
            emoji_id = int(match.group(3))

            return disnake.PartialEmoji.with_state(
                ctx.bot._connection, animated=emoji_animated, name=emoji_name, id=emoji_id
            )

        raise PartialEmojiConversionFailure(argument)


class GuildStickerConverter(IDConverter[disnake.GuildSticker]):
    """Converts to a :class:`~disnake.GuildSticker`.

    All lookups are done for the local guild first, if available. If that lookup
    fails, then it checks the client's global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID
    2. Lookup by name

    .. versionadded:: 2.0
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.GuildSticker:
        match = self._get_id_match(argument)
        result = None
        bot: disnake.Client = ctx.bot
        guild = ctx.guild

        if match is None:
            # Try to get the sticker by name. Try local guild first.
            if guild:
                result = _utils_get(guild.stickers, name=argument)

            if result is None:
                result = _utils_get(bot.stickers, name=argument)
        else:
            # Try to look up sticker by id.
            result = bot.get_sticker(int(match.group(1)))

        if result is None:
            raise GuildStickerNotFound(argument)

        return result


class PermissionsConverter(Converter[disnake.Permissions]):
    """Converts to a :class:`~disnake.Permissions`.

    Accepts an integer or a string of space-separated permission names (or just a single one) as input.

    .. versionadded:: 2.3
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.Permissions:
        # try the permission bit value
        try:
            value = int(argument)
        except ValueError:
            pass
        else:
            return disnake.Permissions(value)

        argument = argument.replace("server", "guild")

        # try multiple attributes, then a single one
        perms: List[disnake.Permissions] = []
        for name in argument.split():
            attr = getattr(disnake.Permissions, name, None)
            if attr is None:
                break

            if callable(attr):
                perms.append(attr())
            else:
                perms.append(disnake.Permissions(**{name: True}))
        else:
            return functools.reduce(lambda a, b: disnake.Permissions(a.value | b.value), perms)

        name = argument.replace(" ", "_")

        attr = getattr(disnake.Permissions, name, None)
        if attr is None:
            raise BadArgument(f"Invalid Permissions: {name!r}")

        if callable(attr):
            return attr()
        return disnake.Permissions(**{name: True})


class GuildScheduledEventConverter(IDConverter[disnake.GuildScheduledEvent]):
    """Converts to a :class:`~disnake.GuildScheduledEvent`.

    The lookup strategy is as follows (in order):

    1. Lookup by ID (in current guild)
    2. Lookup as event URL
    3. Lookup by name (in current guild; there is no disambiguation for scheduled events with multiple matching names)

    .. versionadded:: 2.5
    """

    async def convert(self, ctx: AnyContext, argument: str) -> disnake.GuildScheduledEvent:
        event_regex = re.compile(
            r"https?://(?:(?:ptb|canary|www)\.)?discord(?:app)?\.com/events/"
            r"([0-9]{17,19})/([0-9]{17,19})/?$"
        )
        bot: disnake.Client = ctx.bot
        result: Optional[disnake.GuildScheduledEvent] = None
        guild = ctx.guild

        # 1.
        if guild and (match := self._get_id_match(argument)):
            result = guild.get_scheduled_event(int(match.group(1)))

        # 2.
        if not result and (match := event_regex.match(argument)):
            event_guild = bot.get_guild(int(match.group(1)))
            if event_guild:
                result = event_guild.get_scheduled_event(int(match.group(2)))

        # 3.
        if not result and guild:
            result = _utils_get(guild.scheduled_events, name=argument)

        if not result:
            raise GuildScheduledEventNotFound(argument)
        return result


class clean_content(Converter[str]):
    """Converts the argument to mention scrubbed version of
    said content.

    This behaves similarly to :attr:`~disnake.Message.clean_content`.

    Attributes
    ----------
    fix_channel_mentions: :class:`bool`
        Whether to clean channel mentions.
    use_nicknames: :class:`bool`
        Whether to use nicknames when transforming mentions.
    escape_markdown: :class:`bool`
        Whether to also escape special markdown characters.
    remove_markdown: :class:`bool`
        Whether to also remove special markdown characters. This option is not supported with ``escape_markdown``

        .. versionadded:: 1.7
    """

    def __init__(
        self,
        *,
        fix_channel_mentions: bool = False,
        use_nicknames: bool = True,
        escape_markdown: bool = False,
        remove_markdown: bool = False,
    ) -> None:
        self.fix_channel_mentions = fix_channel_mentions
        self.use_nicknames = use_nicknames
        self.escape_markdown = escape_markdown
        self.remove_markdown = remove_markdown

    async def convert(self, ctx: AnyContext, argument: str) -> str:
        msg = ctx.message if isinstance(ctx, Context) else None
        bot: disnake.Client = ctx.bot

        def resolve_user(id: int) -> str:
            m = (msg and _utils_get(msg.mentions, id=id)) or bot.get_user(id)
            if m is None and ctx.guild:
                m = ctx.guild.get_member(id)
            return f"@{m.display_name if self.use_nicknames else m.name}" if m else "@deleted-user"

        def resolve_role(id: int) -> str:
            if ctx.guild is None:
                return "@deleted-role"
            r = (msg and _utils_get(msg.role_mentions, id=id)) or ctx.guild.get_role(id)
            return f"@{r.name}" if r else "@deleted-role"

        def resolve_channel(id: int) -> str:
            if ctx.guild and self.fix_channel_mentions:
                c = ctx.guild.get_channel(id)
                return f"#{c.name}" if c else "#deleted-channel"

            return f"<#{id}>"

        transforms: Dict[str, Callable[[int], str]] = {
            "@": resolve_user,
            "@!": resolve_user,
            "#": resolve_channel,
            "@&": resolve_role,
        }

        def repl(match: re.Match) -> str:
            type = match[1]
            id = int(match[2])
            return transforms[type](id)

        result = re.sub(r"<(@[!&]?|#)([0-9]{17,19})>", repl, argument)
        if self.escape_markdown:
            result = disnake.utils.escape_markdown(result)
        elif self.remove_markdown:
            result = disnake.utils.remove_markdown(result)

        # Completely ensure no mentions escape:
        return disnake.utils.escape_mentions(result)


class Greedy(List[T]):
    """A special converter that greedily consumes arguments until it can't.
    As a consequence of this behaviour, most input errors are silently discarded,
    since it is used as an indicator of when to stop parsing.

    When a parser error is met the greedy converter stops converting, undoes the
    internal string parsing routine, and continues parsing regularly.

    For example, in the following code:

    .. code-block:: python3

        @commands.command()
        async def test(ctx, numbers: Greedy[int], reason: str):
            await ctx.send("numbers: {0}, reason: {1}".format(numbers, reason))

    An invocation of ``[p]test 1 2 3 4 5 6 hello`` would pass ``numbers`` with
    ``[1, 2, 3, 4, 5, 6]`` and ``reason`` with ``hello``.

    For more information, check :ref:`ext_commands_special_converters`.
    """

    __slots__ = ("converter",)

    def __init__(self, *, converter: T) -> None:
        self.converter = converter

    def __repr__(self) -> str:
        converter = getattr(self.converter, "__name__", repr(self.converter))
        return f"Greedy[{converter}]"

    def __class_getitem__(cls, params: Union[Tuple[T], T]) -> Greedy[T]:
        if not isinstance(params, tuple):
            params = (params,)
        if len(params) != 1:
            raise TypeError("Greedy[...] only takes a single argument")
        converter = params[0]

        origin = getattr(converter, "__origin__", None)
        args = getattr(converter, "__args__", ())

        if not (callable(converter) or isinstance(converter, Converter) or origin is not None):
            raise TypeError("Greedy[...] expects a type or a Converter instance.")

        if converter in (str, type(None)) or origin is Greedy:
            raise TypeError(f"Greedy[{converter.__name__}] is invalid.")  # type: ignore

        if origin is Union and type(None) in args:
            raise TypeError(f"Greedy[{converter!r}] is invalid.")

        return cls(converter=converter)


def _convert_to_bool(argument: str) -> bool:
    lowered = argument.lower()
    if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
        return True
    if lowered in ("no", "n", "false", "f", "0", "disable", "off"):
        return False
    raise BadBoolArgument(lowered)


def get_converter(param: inspect.Parameter) -> Any:
    converter = param.annotation
    if converter is param.empty:
        if param.default is not param.empty:
            converter = str if param.default is None else type(param.default)
        else:
            converter = str
    return converter


_GenericAlias = type(List[T])


def is_generic_type(tp: Any, *, _GenericAlias: Type = _GenericAlias) -> bool:
    return isinstance(tp, type) and issubclass(tp, Generic) or isinstance(tp, _GenericAlias)


CONVERTER_MAPPING: Dict[Type[Any], Type[Converter]] = {
    disnake.Object: ObjectConverter,
    disnake.Member: MemberConverter,
    disnake.User: UserConverter,
    disnake.Message: MessageConverter,
    disnake.PartialMessage: PartialMessageConverter,
    disnake.TextChannel: TextChannelConverter,
    disnake.Invite: InviteConverter,
    disnake.Guild: GuildConverter,
    disnake.Role: RoleConverter,
    disnake.Game: GameConverter,
    disnake.Colour: ColourConverter,
    disnake.VoiceChannel: VoiceChannelConverter,
    disnake.StageChannel: StageChannelConverter,
    disnake.Emoji: EmojiConverter,
    disnake.PartialEmoji: PartialEmojiConverter,
    disnake.CategoryChannel: CategoryChannelConverter,
    disnake.ForumChannel: ForumChannelConverter,
    disnake.Thread: ThreadConverter,
    disnake.abc.GuildChannel: GuildChannelConverter,
    disnake.GuildSticker: GuildStickerConverter,
    disnake.Permissions: PermissionsConverter,
    disnake.GuildScheduledEvent: GuildScheduledEventConverter,
}


async def _actual_conversion(
    ctx: Context,
    converter: Union[Type[T], Type[Converter[T]], Converter[T], Callable[[str], T]],
    argument: str,
    param: inspect.Parameter,
) -> T:
    if converter is bool:
        return _convert_to_bool(argument)  # type: ignore

    if isinstance(converter, type):
        module = converter.__module__
        if module.startswith("disnake.") and not module.endswith("converter"):
            converter = CONVERTER_MAPPING.get(converter, converter)

    try:
        if isinstance(converter, type) and issubclass(converter, Converter):
            if inspect.ismethod(converter.convert):
                return await converter.convert(ctx, argument)
            return await converter().convert(ctx, argument)
        if isinstance(converter, Converter):
            return await converter.convert(ctx, argument)  # type: ignore
    except CommandError:
        raise
    except Exception as exc:
        raise ConversionError(converter, exc) from exc

    try:
        return converter(argument)
    except CommandError:
        raise
    except Exception as exc:
        try:
            name = converter.__name__
        except AttributeError:
            name = converter.__class__.__name__

        raise BadArgument(f'Converting to "{name}" failed for parameter "{param.name}".') from exc


async def run_converters(ctx: Context, converter, argument: str, param: inspect.Parameter):
    """|coro|

    Runs converters for a given converter, argument, and parameter.

    This function does the same work that the library does under the hood.

    .. versionadded:: 2.0

    Parameters
    ----------
    ctx: :class:`Context`
        The invocation context to run the converters under.
    converter: Any
        The converter to run, this corresponds to the annotation in the function.
    argument: :class:`str`
        The argument to convert to.
    param: :class:`inspect.Parameter`
        The parameter being converted. This is mainly for error reporting.

    Raises
    ------
    CommandError
        The converter failed to convert.

    Returns
    -------
    Any
        The resulting conversion.
    """
    origin = getattr(converter, "__origin__", None)

    if origin is Union:
        errors = []
        _NoneType = type(None)
        union_args = converter.__args__
        for conv in union_args:
            # if we got to this part in the code, then the previous conversions have failed
            # so we should just undo the view, return the default, and allow parsing to continue
            # with the other parameters
            if conv is _NoneType and param.kind != param.VAR_POSITIONAL:
                ctx.view.undo()
                return None if param.default is param.empty else param.default

            try:
                value = await run_converters(ctx, conv, argument, param)
            except CommandError as exc:
                errors.append(exc)
            else:
                return value

        # if we're here, then we failed all the converters
        raise BadUnionArgument(param, union_args, errors)

    if origin is Literal:
        errors = []
        conversions = {}
        literal_args = converter.__args__
        for literal in literal_args:
            literal_type = type(literal)
            try:
                value = conversions[literal_type]
            except KeyError:
                try:
                    value = await _actual_conversion(ctx, literal_type, argument, param)
                except CommandError as exc:
                    errors.append(exc)
                    conversions[literal_type] = object()
                    continue
                else:
                    conversions[literal_type] = value

            if value == literal:
                return value

        # if we're here, then we failed to match all the literals
        raise BadLiteralArgument(param, literal_args, errors)

    # This must be the last if-clause in the chain of origin checking
    # Nearly every type is a generic type within the typing library
    # So care must be taken to make sure a more specialised origin handle
    # isn't overwritten by the widest if clause
    if origin is not None and is_generic_type(converter):
        converter = origin

    return await _actual_conversion(ctx, converter, argument, param)
