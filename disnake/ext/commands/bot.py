# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, List, Optional, Sequence, Set, Union

import disnake

from .bot_base import BotBase, when_mentioned, when_mentioned_or
from .interaction_bot_base import InteractionBotBase

if TYPE_CHECKING:
    import aiohttp
    from typing_extensions import Self

    from disnake.activity import BaseActivity
    from disnake.client import GatewayParams
    from disnake.enums import Status
    from disnake.flags import Intents, MemberCacheFlags
    from disnake.i18n import LocalizationProtocol
    from disnake.mentions import AllowedMentions
    from disnake.message import Message

    from ._types import MaybeCoro
    from .bot_base import PrefixType
    from .flags import CommandSyncFlags
    from .help import HelpCommand


__all__ = (
    "when_mentioned",
    "when_mentioned_or",
    "BotBase",
    "Bot",
    "InteractionBot",
    "AutoShardedBot",
    "AutoShardedInteractionBot",
)

MISSING: Any = disnake.utils.MISSING


class Bot(BotBase, InteractionBotBase, disnake.Client):
    """Represents a discord bot.

    This class is a subclass of :class:`disnake.Client` and as a result
    anything that you can do with a :class:`disnake.Client` you can do with
    this bot.

    This class also subclasses :class:`.GroupMixin` to provide the functionality
    to manage commands.

    Parameters
    ----------
    test_guilds: List[:class:`int`]
        The list of IDs of the guilds where you're going to test your application commands.
        Defaults to ``None``, which means global registration of commands across
        all guilds.

        .. versionadded:: 2.1

    command_sync_flags: :class:`.CommandSyncFlags`
        The command sync flags for the session. This is a way of
        controlling when and how application commands will be synced with the Discord API.
        If not given, defaults to :func:`CommandSyncFlags.default`.

        .. versionadded:: 2.7

    sync_commands: :class:`bool`
        Whether to enable automatic synchronization of application commands in your code.
        Defaults to ``True``, which means that commands in API are automatically synced
        with the commands in your code.

        .. versionadded:: 2.1

        .. deprecated:: 2.7
            Replaced with ``command_sync_flags``.

    sync_commands_on_cog_unload: :class:`bool`
        Whether to sync the application commands on cog unload / reload. Defaults to ``True``.

        .. versionadded:: 2.1

        .. deprecated:: 2.7
            Replaced with ``command_sync_flags``.

    sync_commands_debug: :class:`bool`
        Whether to always show sync debug logs (uses ``INFO`` log level if it's enabled, prints otherwise).
        If disabled, uses the default ``DEBUG`` log level which isn't shown unless the log level is changed manually.
        Useful for tracking the commands being registered in the API.
        Defaults to ``False``.

        .. versionadded:: 2.1

        .. versionchanged:: 2.4
            Changes the log level of corresponding messages from ``DEBUG`` to ``INFO`` or ``print``\\s them,
            instead of controlling whether they are enabled at all.

        .. deprecated:: 2.7
            Replaced with ``command_sync_flags``.

    localization_provider: :class:`.LocalizationProtocol`
        An implementation of :class:`.LocalizationProtocol` to use for localization of
        application commands.
        If not provided, the default :class:`.LocalizationStore` implementation is used.

        .. versionadded:: 2.5

    strict_localization: :class:`bool`
        Whether to raise an exception when localizations for a specific key couldn't be found.
        This is mainly useful for testing/debugging, consider disabling this eventually
        as missing localized names will automatically fall back to the default/base name without it.
        Only applicable if the ``localization_provider`` parameter is not provided.
        Defaults to ``False``.

        .. versionadded:: 2.5

    Attributes
    ----------
    command_prefix
        The command prefix is what the message content must contain initially
        to have a command invoked. This prefix could either be a string to
        indicate what the prefix should be, or a callable that takes in the bot
        as its first parameter and :class:`disnake.Message` as its second
        parameter and returns the prefix. This is to facilitate "dynamic"
        command prefixes. This callable can be either a regular function or
        a coroutine.

        An empty string as the prefix always matches, enabling prefix-less
        command invocation. While this may be useful in DMs it should be avoided
        in servers, as it's likely to cause performance issues and unintended
        command invocations.

        The command prefix could also be an iterable of strings indicating that
        multiple checks for the prefix should be used and the first one to
        match will be the invocation prefix. You can get this prefix via
        :attr:`.Context.prefix`. To avoid confusion empty iterables are not
        allowed.

        If the prefix is ``None``, the bot won't listen to any prefixes, and prefix
        commands will not be processed. If you don't need prefix commands, consider
        using :class:`InteractionBot` or :class:`AutoShardedInteractionBot` instead,
        which are drop-in replacements, just without prefix command support.

        This can be provided as a parameter at creation.

        .. note::

            When passing multiple prefixes be careful to not pass a prefix
            that matches a longer prefix occurring later in the sequence.  For
            example, if the command prefix is ``('!', '!?')``  the ``'!?'``
            prefix will never be matched to any message as the previous one
            matches messages starting with ``!?``. This is especially important
            when passing an empty string, it should always be last as no prefix
            after it will be matched.
    case_insensitive: :class:`bool`
        Whether the commands should be case insensitive. Defaults to ``False``. This
        attribute does not carry over to groups. You must set it to every group if
        you require group commands to be case insensitive as well.

        This can be provided as a parameter at creation.

    description: :class:`str`
        The content prefixed into the default help message.

        This can be provided as a parameter at creation.

    help_command: Optional[:class:`.HelpCommand`]
        The help command implementation to use. This can be dynamically
        set at runtime. To remove the help command pass ``None``. For more
        information on implementing a help command, see :ref:`ext_commands_api_help_commands`.

        This can be provided as a parameter at creation.

    owner_id: Optional[:class:`int`]
        The ID of the user that owns the bot. If this is not set and is then queried via
        :meth:`.is_owner` then it is fetched automatically using
        :meth:`~.Bot.application_info`.

        This can be provided as a parameter at creation.

    owner_ids: Optional[Collection[:class:`int`]]
        The IDs of the users that own the bot. This is similar to :attr:`owner_id`.
        If this is not set and the application is team based, then it is
        fetched automatically using :meth:`~.Bot.application_info` (taking team roles into account).
        For performance reasons it is recommended to use a :class:`set`
        for the collection. You cannot set both ``owner_id`` and ``owner_ids``.

        This can be provided as a parameter at creation.

        .. versionadded:: 1.3

    strip_after_prefix: :class:`bool`
        Whether to strip whitespace characters after encountering the command
        prefix. This allows for ``!   hello`` and ``!hello`` to both work if
        the ``command_prefix`` is set to ``!``. Defaults to ``False``.

        This can be provided as a parameter at creation.

        .. versionadded:: 1.7

    reload: :class:`bool`
        Whether to enable automatic extension reloading on file modification for debugging.
        Whenever you save an extension with reloading enabled the file will be automatically
        reloaded for you so you do not have to reload the extension manually. Defaults to ``False``

        This can be provided as a parameter at creation.

        .. versionadded:: 2.1

    i18n: :class:`.LocalizationProtocol`
        An implementation of :class:`.LocalizationProtocol` used for localization of
        application commands.

        .. versionadded:: 2.5
    """

    if TYPE_CHECKING:

        def __init__(
            self,
            command_prefix: Optional[
                Union[PrefixType, Callable[[Self, Message], MaybeCoro[PrefixType]]]
            ] = None,
            help_command: Optional[HelpCommand] = ...,
            description: Optional[str] = None,
            *,
            strip_after_prefix: bool = False,
            owner_id: Optional[int] = None,
            owner_ids: Optional[Set[int]] = None,
            reload: bool = False,
            case_insensitive: bool = False,
            command_sync_flags: CommandSyncFlags = ...,
            test_guilds: Optional[Sequence[int]] = None,
            sync_commands: bool = ...,
            sync_commands_debug: bool = ...,
            sync_commands_on_cog_unload: bool = ...,
            shard_id: Optional[int] = None,
            shard_count: Optional[int] = None,
            enable_debug_events: bool = False,
            enable_gateway_error_handler: bool = True,
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
            localization_provider: Optional[LocalizationProtocol] = None,
            strict_localization: bool = False,
        ) -> None:
            ...


class AutoShardedBot(BotBase, InteractionBotBase, disnake.AutoShardedClient):
    """Similar to :class:`.Bot`, except that it is inherited from
    :class:`disnake.AutoShardedClient` instead.
    """

    if TYPE_CHECKING:

        def __init__(
            self,
            command_prefix: Optional[
                Union[PrefixType, Callable[[Self, Message], MaybeCoro[PrefixType]]]
            ] = None,
            help_command: Optional[HelpCommand] = ...,
            description: Optional[str] = None,
            *,
            strip_after_prefix: bool = False,
            owner_id: Optional[int] = None,
            owner_ids: Optional[Set[int]] = None,
            reload: bool = False,
            case_insensitive: bool = False,
            command_sync_flags: CommandSyncFlags = ...,
            test_guilds: Optional[Sequence[int]] = None,
            sync_commands: bool = ...,
            sync_commands_debug: bool = ...,
            sync_commands_on_cog_unload: bool = ...,
            shard_ids: Optional[List[int]] = None,  # instead of shard_id
            shard_count: Optional[int] = None,
            enable_debug_events: bool = False,
            enable_gateway_error_handler: bool = True,
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
            localization_provider: Optional[LocalizationProtocol] = None,
            strict_localization: bool = False,
        ) -> None:
            ...


class InteractionBot(InteractionBotBase, disnake.Client):
    """Represents a discord bot for application commands only.

    This class is a subclass of :class:`disnake.Client` and as a result
    anything that you can do with a :class:`disnake.Client` you can do with
    this bot.

    This class also subclasses InteractionBotBase to provide the functionality
    to manage application commands.

    Parameters
    ----------
    test_guilds: List[:class:`int`]
        The list of IDs of the guilds where you're going to test your application commands.
        Defaults to ``None``, which means global registration of commands across
        all guilds.

        .. versionadded:: 2.1

    command_sync_flags: :class:`.CommandSyncFlags`
        The command sync flags for the session. This is a way of
        controlling when and how application commands will be synced with the Discord API.
        If not given, defaults to :func:`CommandSyncFlags.default`.

        .. versionadded:: 2.7

    sync_commands: :class:`bool`
        Whether to enable automatic synchronization of application commands in your code.
        Defaults to ``True``, which means that commands in API are automatically synced
        with the commands in your code.

        .. versionadded:: 2.1

        .. deprecated:: 2.7
            Replaced with ``command_sync_flags``.

    sync_commands_on_cog_unload: :class:`bool`
        Whether to sync the application commands on cog unload / reload. Defaults to ``True``.

        .. versionadded:: 2.1

        .. deprecated:: 2.7
            Replaced with ``command_sync_flags``.

    sync_commands_debug: :class:`bool`
        Whether to always show sync debug logs (uses ``INFO`` log level if it's enabled, prints otherwise).
        If disabled, uses the default ``DEBUG`` log level which isn't shown unless the log level is changed manually.
        Useful for tracking the commands being registered in the API.
        Defaults to ``False``.

        .. versionadded:: 2.1

        .. versionchanged:: 2.4
            Changes the log level of corresponding messages from ``DEBUG`` to ``INFO`` or ``print``\\s them,
            instead of controlling whether they are enabled at all.

        .. deprecated:: 2.7
            Replaced with ``command_sync_flags``.

    localization_provider: :class:`.LocalizationProtocol`
        An implementation of :class:`.LocalizationProtocol` to use for localization of
        application commands.
        If not provided, the default :class:`.LocalizationStore` implementation is used.

        .. versionadded:: 2.5

    strict_localization: :class:`bool`
        Whether to raise an exception when localizations for a specific key couldn't be found.
        This is mainly useful for testing/debugging, consider disabling this eventually
        as missing localized names will automatically fall back to the default/base name without it.
        Only applicable if the ``localization_provider`` parameter is not provided.
        Defaults to ``False``.

        .. versionadded:: 2.5

    Attributes
    ----------
    owner_id: Optional[:class:`int`]
        The ID of the user that owns the bot. If this is not set and is then queried via
        :meth:`.is_owner` then it is fetched automatically using
        :meth:`~.Bot.application_info`.

        This can be provided as a parameter at creation.

    owner_ids: Optional[Collection[:class:`int`]]
        The IDs of the users that own the bot. This is similar to :attr:`owner_id`.
        If this is not set and the application is team based, then it is
        fetched automatically using :meth:`~.Bot.application_info` (taking team roles into account).
        For performance reasons it is recommended to use a :class:`set`
        for the collection. You cannot set both ``owner_id`` and ``owner_ids``.

        This can be provided as a parameter at creation.

    reload: :class:`bool`
        Whether to enable automatic extension reloading on file modification for debugging.
        Whenever you save an extension with reloading enabled the file will be automatically
        reloaded for you so you do not have to reload the extension manually. Defaults to ``False``

        This can be provided as a parameter at creation.

        .. versionadded:: 2.1

    i18n: :class:`.LocalizationProtocol`
        An implementation of :class:`.LocalizationProtocol` used for localization of
        application commands.

        .. versionadded:: 2.5
    """

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            owner_id: Optional[int] = None,
            owner_ids: Optional[Set[int]] = None,
            reload: bool = False,
            command_sync_flags: CommandSyncFlags = ...,
            test_guilds: Optional[Sequence[int]] = None,
            sync_commands: bool = ...,
            sync_commands_debug: bool = ...,
            sync_commands_on_cog_unload: bool = ...,
            shard_id: Optional[int] = None,
            shard_count: Optional[int] = None,
            enable_debug_events: bool = False,
            enable_gateway_error_handler: bool = True,
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
            localization_provider: Optional[LocalizationProtocol] = None,
            strict_localization: bool = False,
        ) -> None:
            ...


class AutoShardedInteractionBot(InteractionBotBase, disnake.AutoShardedClient):
    """Similar to :class:`.InteractionBot`, except that it is inherited from
    :class:`disnake.AutoShardedClient` instead.
    """

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            owner_id: Optional[int] = None,
            owner_ids: Optional[Set[int]] = None,
            reload: bool = False,
            command_sync_flags: CommandSyncFlags = ...,
            test_guilds: Optional[Sequence[int]] = None,
            sync_commands: bool = ...,
            sync_commands_debug: bool = ...,
            sync_commands_on_cog_unload: bool = ...,
            shard_ids: Optional[List[int]] = None,  # instead of shard_id
            shard_count: Optional[int] = None,
            enable_debug_events: bool = False,
            enable_gateway_error_handler: bool = True,
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
            localization_provider: Optional[LocalizationProtocol] = None,
            strict_localization: bool = False,
        ) -> None:
            ...
