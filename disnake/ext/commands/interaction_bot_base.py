# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import logging
import sys
import traceback
import warnings
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
)

import disnake
from disnake.app_commands import ApplicationCommand, Option
from disnake.custom_warnings import SyncWarning
from disnake.enums import ApplicationCommandType
from disnake.flags import ApplicationInstallTypes, InteractionContextTypes
from disnake.utils import warn_deprecated

from . import errors
from .base_core import InvokableApplicationCommand
from .common_bot_base import CommonBotBase
from .ctx_menus_core import (
    InvokableMessageCommand,
    InvokableUserCommand,
    message_command,
    user_command,
)
from .errors import CommandRegistrationError
from .flags import CommandSyncFlags
from .slash_core import InvokableSlashCommand, SubCommand, SubCommandGroup, slash_command

if TYPE_CHECKING:
    from typing_extensions import NotRequired, ParamSpec

    from disnake.i18n import LocalizedOptional
    from disnake.interactions import (
        ApplicationCommandInteraction,
        MessageCommandInteraction,
        UserCommandInteraction,
    )
    from disnake.permissions import Permissions

    from ._types import AppCheck, CoroFunc
    from .base_core import CogT, CommandCallback, InteractionCommandCallback

    P = ParamSpec("P")


__all__ = ("InteractionBotBase",)

MISSING: Any = disnake.utils.MISSING

T = TypeVar("T")
CFT = TypeVar("CFT", bound="CoroFunc")


_log = logging.getLogger(__name__)


class _Diff(TypedDict):
    no_changes: List[ApplicationCommand]
    upsert: List[ApplicationCommand]
    edit: List[ApplicationCommand]
    delete: List[ApplicationCommand]
    delete_ignored: NotRequired[List[ApplicationCommand]]


def _get_to_send_from_diff(diff: _Diff):
    return diff["no_changes"] + diff["upsert"] + diff["edit"] + diff.get("delete_ignored", [])


def _app_commands_diff(
    new_commands: Iterable[ApplicationCommand],
    old_commands: Iterable[ApplicationCommand],
) -> _Diff:
    new_cmds = {(cmd.name, cmd.type): cmd for cmd in new_commands}
    old_cmds = {(cmd.name, cmd.type): cmd for cmd in old_commands}

    diff: _Diff = {
        "no_changes": [],
        "upsert": [],
        "edit": [],
        "delete": [],
    }

    for name_and_type, new_cmd in new_cmds.items():
        old_cmd = old_cmds.get(name_and_type)
        if old_cmd is None:
            diff["upsert"].append(new_cmd)
        elif new_cmd._always_synced:
            diff["no_changes"].append(old_cmd)
            continue
        elif new_cmd != old_cmd:
            diff["edit"].append(new_cmd)
        else:
            diff["no_changes"].append(new_cmd)

    for name_and_type, old_cmd in old_cmds.items():
        if name_and_type not in new_cmds:
            diff["delete"].append(old_cmd)

    return diff


_diff_map = {
    "upsert": "To upsert:",
    "edit": "To edit:",
    "delete": "To delete:",
    "no_changes": "No changes:",
    "delete_ignored": "Ignored due to delete flags:",
}


def _format_diff(diff: _Diff) -> str:
    lines: List[str] = []
    for key, label in _diff_map.items():
        if key not in diff:
            continue
        lines.append(label)
        if changes := diff[key]:
            lines.extend(f"    <{type(cmd).__name__} name={cmd.name!r}>" for cmd in changes)
        else:
            lines.append("    -")

    return "\n".join(f"| {line}" for line in lines)


class InteractionBotBase(CommonBotBase):
    def __init__(
        self,
        *,
        command_sync_flags: Optional[CommandSyncFlags] = None,
        sync_commands: bool = MISSING,
        sync_commands_debug: bool = MISSING,
        sync_commands_on_cog_unload: bool = MISSING,
        test_guilds: Optional[Sequence[int]] = None,
        default_install_types: Optional[ApplicationInstallTypes] = None,
        default_contexts: Optional[InteractionContextTypes] = None,
        **options: Any,
    ) -> None:
        if test_guilds and not all(isinstance(guild_id, int) for guild_id in test_guilds):
            raise ValueError("test_guilds must be a sequence of int.")

        super().__init__(**options)

        test_guilds = None if test_guilds is None else tuple(test_guilds)
        self._test_guilds: Optional[Tuple[int, ...]] = test_guilds

        if command_sync_flags is not None and (
            sync_commands is not MISSING
            or sync_commands_debug is not MISSING
            or sync_commands_on_cog_unload is not MISSING
        ):
            raise TypeError(
                "cannot set 'command_sync_flags' and any of 'sync_commands', 'sync_commands_debug', 'sync_commands_on_cog_unload' at the same time."
            )

        if command_sync_flags is not None:
            # this makes a copy so it cannot be changed after setting
            command_sync_flags = CommandSyncFlags._from_value(command_sync_flags.value)
        if command_sync_flags is None:
            command_sync_flags = CommandSyncFlags.default()

            if sync_commands is not MISSING:
                warn_deprecated(
                    "sync_commands is deprecated and will be removed in a future version. "
                    "Use `command_sync_flags` with an `CommandSyncFlags` instance as a replacement.",
                    stacklevel=3,
                )
                command_sync_flags.sync_commands = sync_commands
            if sync_commands_debug is not MISSING:
                warn_deprecated(
                    "sync_commands_debug is deprecated and will be removed in a future version. "
                    "Use `command_sync_flags` with an `CommandSyncFlags` instance as a replacement.",
                    stacklevel=3,
                )
                command_sync_flags.sync_commands_debug = sync_commands_debug

            if sync_commands_on_cog_unload is not MISSING:
                warn_deprecated(
                    "sync_commands_on_cog_unload is deprecated and will be removed in a future version. "
                    "Use `command_sync_flags` with an `CommandSyncFlags` instance as a replacement.",
                    stacklevel=3,
                )
                command_sync_flags.sync_on_cog_actions = sync_commands_on_cog_unload

        self._command_sync_flags = command_sync_flags
        self._sync_queued: asyncio.Lock = asyncio.Lock()

        self._default_install_types = default_install_types
        self._default_contexts = default_contexts

        self._slash_command_checks = []
        self._slash_command_check_once = []
        self._user_command_checks = []
        self._user_command_check_once = []
        self._message_command_checks = []
        self._message_command_check_once = []

        self._before_slash_command_invoke = None
        self._after_slash_command_invoke = None
        self._before_user_command_invoke = None
        self._after_user_command_invoke = None
        self._before_message_command_invoke = None
        self._after_message_command_invoke = None

        self.all_slash_commands: Dict[str, InvokableSlashCommand] = {}
        self.all_user_commands: Dict[str, InvokableUserCommand] = {}
        self.all_message_commands: Dict[str, InvokableMessageCommand] = {}

    @disnake.utils.copy_doc(disnake.Client.login)
    async def login(self, token: str) -> None:
        self._schedule_app_command_preparation()

        await super().login(token)

    @property
    def command_sync_flags(self) -> CommandSyncFlags:
        """:class:`~.CommandSyncFlags`: The command sync flags configured for this bot.

        .. versionadded:: 2.7
        """
        return CommandSyncFlags._from_value(self._command_sync_flags.value)

    def application_commands_iterator(self) -> Iterable[InvokableApplicationCommand]:
        return chain(
            self.all_slash_commands.values(),
            self.all_user_commands.values(),
            self.all_message_commands.values(),
        )

    @property
    def application_commands(self) -> Set[InvokableApplicationCommand]:
        """Set[:class:`InvokableApplicationCommand`]: A set of all application commands the bot has."""
        return set(self.application_commands_iterator())

    @property
    def slash_commands(self) -> Set[InvokableSlashCommand]:
        """Set[:class:`InvokableSlashCommand`]: A set of all slash commands the bot has."""
        return set(self.all_slash_commands.values())

    @property
    def user_commands(self) -> Set[InvokableUserCommand]:
        """Set[:class:`InvokableUserCommand`]: A set of all user commands the bot has."""
        return set(self.all_user_commands.values())

    @property
    def message_commands(self) -> Set[InvokableMessageCommand]:
        """Set[:class:`InvokableMessageCommand`]: A set of all message commands the bot has."""
        return set(self.all_message_commands.values())

    def add_slash_command(self, slash_command: InvokableSlashCommand) -> None:
        """Adds an :class:`InvokableSlashCommand` into the internal list of slash commands.

        This is usually not called, instead the :meth:`.slash_command` or
        shortcut decorators are used.

        Parameters
        ----------
        slash_command: :class:`InvokableSlashCommand`
            The slash command to add.

        Raises
        ------
        CommandRegistrationError
            The slash command is already registered.
        TypeError
            The slash command passed is not an instance of :class:`InvokableSlashCommand`.
        """
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("This method is only usable in disnake.Client subclasses")

        if not isinstance(slash_command, InvokableSlashCommand):
            raise TypeError("The slash_command passed must be an instance of InvokableSlashCommand")

        if slash_command.name in self.all_slash_commands:
            raise CommandRegistrationError(slash_command.name)

        slash_command._apply_defaults(self)
        slash_command.body.localize(self.i18n)
        self.all_slash_commands[slash_command.name] = slash_command

    def add_user_command(self, user_command: InvokableUserCommand) -> None:
        """Adds an :class:`InvokableUserCommand` into the internal list of user commands.

        This is usually not called, instead the :meth:`.user_command` or
        shortcut decorators are used.

        Parameters
        ----------
        user_command: :class:`InvokableUserCommand`
            The user command to add.

        Raises
        ------
        CommandRegistrationError
            The user command is already registered.
        TypeError
            The user command passed is not an instance of :class:`InvokableUserCommand`.
        """
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("This method is only usable in disnake.Client subclasses")

        if not isinstance(user_command, InvokableUserCommand):
            raise TypeError("The user_command passed must be an instance of InvokableUserCommand")

        if user_command.name in self.all_user_commands:
            raise CommandRegistrationError(user_command.name)

        user_command._apply_defaults(self)
        user_command.body.localize(self.i18n)
        self.all_user_commands[user_command.name] = user_command

    def add_message_command(self, message_command: InvokableMessageCommand) -> None:
        """Adds an :class:`InvokableMessageCommand` into the internal list of message commands.

        This is usually not called, instead the :meth:`.message_command` or
        shortcut decorators are used.

        Parameters
        ----------
        message_command: :class:`InvokableMessageCommand`
            The message command to add.

        Raises
        ------
        CommandRegistrationError
            The message command is already registered.
        TypeError
            The message command passed is not an instance of :class:`InvokableMessageCommand`.
        """
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("This method is only usable in disnake.Client subclasses")

        if not isinstance(message_command, InvokableMessageCommand):
            raise TypeError(
                "The message_command passed must be an instance of InvokableMessageCommand"
            )

        if message_command.name in self.all_message_commands:
            raise CommandRegistrationError(message_command.name)

        message_command._apply_defaults(self)
        message_command.body.localize(self.i18n)
        self.all_message_commands[message_command.name] = message_command

    def remove_slash_command(self, name: str) -> Optional[InvokableSlashCommand]:
        """Removes an :class:`InvokableSlashCommand` from the internal list
        of slash commands.

        Parameters
        ----------
        name: :class:`str`
            The name of the slash command to remove.

        Returns
        -------
        Optional[:class:`InvokableSlashCommand`]
            The slash command that was removed. If the name is not valid then ``None`` is returned instead.
        """
        command = self.all_slash_commands.pop(name, None)
        if command is None:
            return None
        return command

    def remove_user_command(self, name: str) -> Optional[InvokableUserCommand]:
        """Removes an :class:`InvokableUserCommand` from the internal list
        of user commands.

        Parameters
        ----------
        name: :class:`str`
            The name of the user command to remove.

        Returns
        -------
        Optional[:class:`InvokableUserCommand`]
            The user command that was removed. If the name is not valid then ``None`` is returned instead.
        """
        command = self.all_user_commands.pop(name, None)
        if command is None:
            return None
        return command

    def remove_message_command(self, name: str) -> Optional[InvokableMessageCommand]:
        """Removes an :class:`InvokableMessageCommand` from the internal list
        of message commands.

        Parameters
        ----------
        name: :class:`str`
            The name of the message command to remove.

        Returns
        -------
        Optional[:class:`InvokableMessageCommand`]
            The message command that was removed. If the name is not valid then ``None`` is returned instead.
        """
        command = self.all_message_commands.pop(name, None)
        if command is None:
            return None
        return command

    def get_slash_command(
        self, name: str
    ) -> Optional[Union[InvokableSlashCommand, SubCommandGroup, SubCommand]]:
        """Works like ``Bot.get_command``, but for slash commands.

        If the name contains spaces, then it will assume that you are looking for a :class:`SubCommand` or
        a :class:`SubCommandGroup`.
        e.g: ``'foo bar'`` will get the sub command group, or the sub command ``bar`` of the top-level slash command
        ``foo`` if found, otherwise ``None``.

        Parameters
        ----------
        name: :class:`str`
            The name of the slash command to get.

        Raises
        ------
        TypeError
            The name is not a string.

        Returns
        -------
        Optional[Union[:class:`InvokableSlashCommand`, :class:`SubCommandGroup`, :class:`SubCommand`]]
            The slash command that was requested. If not found, returns ``None``.
        """
        if not isinstance(name, str):
            raise TypeError(f"Expected name to be str, not {name.__class__}")

        chain = name.split()
        slash = self.all_slash_commands.get(chain[0])
        if slash is None:
            return None

        if len(chain) == 1:
            return slash
        elif len(chain) == 2:
            return slash.children.get(chain[1])
        elif len(chain) == 3:
            group = slash.children.get(chain[1])
            if isinstance(group, SubCommandGroup):
                return group.children.get(chain[2])

    def get_user_command(self, name: str) -> Optional[InvokableUserCommand]:
        """Gets an :class:`InvokableUserCommand` from the internal list
        of user commands.

        Parameters
        ----------
        name: :class:`str`
            The name of the user command to get.

        Returns
        -------
        Optional[:class:`InvokableUserCommand`]
            The user command that was requested. If not found, returns ``None``.
        """
        return self.all_user_commands.get(name)

    def get_message_command(self, name: str) -> Optional[InvokableMessageCommand]:
        """Gets an :class:`InvokableMessageCommand` from the internal list
        of message commands.

        Parameters
        ----------
        name: :class:`str`
            The name of the message command to get.

        Returns
        -------
        Optional[:class:`InvokableMessageCommand`]
            The message command that was requested. If not found, returns ``None``.
        """
        return self.all_message_commands.get(name)

    def slash_command(
        self,
        *,
        name: LocalizedOptional = None,
        description: LocalizedOptional = None,
        dm_permission: Optional[bool] = None,  # deprecated
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
        install_types: Optional[ApplicationInstallTypes] = None,
        contexts: Optional[InteractionContextTypes] = None,
        options: Optional[List[Option]] = None,
        guild_ids: Optional[Sequence[int]] = None,
        connectors: Optional[Dict[str, str]] = None,
        auto_sync: Optional[bool] = None,
        extras: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Callable[[CommandCallback], InvokableSlashCommand]:
        """A shortcut decorator that invokes :func:`~disnake.ext.commands.slash_command` and adds it to
        the internal command list.

        Parameters
        ----------
        name: Optional[Union[:class:`str`, :class:`.Localized`]]
            The name of the slash command (defaults to function name).

            .. versionchanged:: 2.5
                Added support for localizations.

        description: Optional[Union[:class:`str`, :class:`.Localized`]]
            The description of the slash command. It will be visible in Discord.

            .. versionchanged:: 2.5
                Added support for localizations.

        options: List[:class:`.Option`]
            The list of slash command options. The options will be visible in Discord.
            This is the old way of specifying options. Consider using :ref:`param_syntax` instead.
        dm_permission: :class:`bool`
            Whether this command can be used in DMs.
            Defaults to ``True``.

            .. deprecated:: 2.10
                Use ``contexts`` instead.
                This is equivalent to the :attr:`.InteractionContextTypes.bot_dm` flag.

        default_member_permissions: Optional[Union[:class:`.Permissions`, :class:`int`]]
            The default required permissions for this command.
            See :attr:`.ApplicationCommand.default_member_permissions` for details.

            .. versionadded:: 2.5

        nsfw: :class:`bool`
            Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
            Defaults to ``False``.

            .. versionadded:: 2.8

        install_types: Optional[:class:`.ApplicationInstallTypes`]
            The installation types where the command is available.
            Defaults to :attr:`.ApplicationInstallTypes.guild` only.
            Only available for global commands.

            See :ref:`app_command_contexts` for details.

            .. versionadded:: 2.10

        contexts: Optional[:class:`.InteractionContextTypes`]
            The interaction contexts where the command can be used.
            Only available for global commands.

            See :ref:`app_command_contexts` for details.

            .. versionadded:: 2.10

        auto_sync: :class:`bool`
            Whether to automatically register the command. Defaults to ``True``
        guild_ids: Sequence[:class:`int`]
            If specified, the client will register the command in these guilds.
            Otherwise, this command will be registered globally.
        connectors: Dict[:class:`str`, :class:`str`]
            Binds function names to option names. If the name
            of an option already matches the corresponding function param,
            you don't have to specify the connectors. Connectors template:
            ``{"option-name": "param_name", ...}``.
            If you're using :ref:`param_syntax`, you don't need to specify this.
        extras: Dict[:class:`str`, Any]
            A dict of user provided extras to attach to the command.

            .. note::
                This object may be copied by the library.

            .. versionadded:: 2.5

        Returns
        -------
        Callable[..., :class:`InvokableSlashCommand`]
            A decorator that converts the provided method into an InvokableSlashCommand, adds it to the bot, then returns it.
        """

        def decorator(func: CommandCallback) -> InvokableSlashCommand:
            result = slash_command(
                name=name,
                description=description,
                options=options,
                dm_permission=dm_permission,
                default_member_permissions=default_member_permissions,
                nsfw=nsfw,
                install_types=install_types,
                contexts=contexts,
                guild_ids=guild_ids,
                connectors=connectors,
                auto_sync=auto_sync,
                extras=extras,
                **kwargs,
            )(func)
            self.add_slash_command(result)
            return result

        return decorator

    def user_command(
        self,
        *,
        name: LocalizedOptional = None,
        dm_permission: Optional[bool] = None,  # deprecated
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
        install_types: Optional[ApplicationInstallTypes] = None,
        contexts: Optional[InteractionContextTypes] = None,
        guild_ids: Optional[Sequence[int]] = None,
        auto_sync: Optional[bool] = None,
        extras: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Callable[
        [InteractionCommandCallback[CogT, UserCommandInteraction, P]], InvokableUserCommand
    ]:
        """A shortcut decorator that invokes :func:`~disnake.ext.commands.user_command` and adds it to
        the internal command list.

        Parameters
        ----------
        name: Optional[Union[:class:`str`, :class:`.Localized`]]
            The name of the user command (defaults to function name).

            .. versionchanged:: 2.5
                Added support for localizations.

        dm_permission: :class:`bool`
            Whether this command can be used in DMs.
            Defaults to ``True``.

            .. deprecated:: 2.10
                Use ``contexts`` instead.
                This is equivalent to the :attr:`.InteractionContextTypes.bot_dm` flag.

        default_member_permissions: Optional[Union[:class:`.Permissions`, :class:`int`]]
            The default required permissions for this command.
            See :attr:`.ApplicationCommand.default_member_permissions` for details.

            .. versionadded:: 2.5

        nsfw: :class:`bool`
            Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
            Defaults to ``False``.

            .. versionadded:: 2.8

        install_types: Optional[:class:`.ApplicationInstallTypes`]
            The installation types where the command is available.
            Defaults to :attr:`.ApplicationInstallTypes.guild` only.
            Only available for global commands.

            See :ref:`app_command_contexts` for details.

            .. versionadded:: 2.10

        contexts: Optional[:class:`.InteractionContextTypes`]
            The interaction contexts where the command can be used.
            Only available for global commands.

            See :ref:`app_command_contexts` for details.

            .. versionadded:: 2.10

        auto_sync: :class:`bool`
            Whether to automatically register the command. Defaults to ``True``.
        guild_ids: Sequence[:class:`int`]
            If specified, the client will register the command in these guilds.
            Otherwise, this command will be registered globally.
        extras: Dict[:class:`str`, Any]
            A dict of user provided extras to attach to the command.

            .. note::
                This object may be copied by the library.

            .. versionadded:: 2.5

        Returns
        -------
        Callable[..., :class:`InvokableUserCommand`]
            A decorator that converts the provided method into an InvokableUserCommand, adds it to the bot, then returns it.
        """

        def decorator(
            func: InteractionCommandCallback[CogT, UserCommandInteraction, P],
        ) -> InvokableUserCommand:
            result = user_command(
                name=name,
                dm_permission=dm_permission,
                default_member_permissions=default_member_permissions,
                nsfw=nsfw,
                install_types=install_types,
                contexts=contexts,
                guild_ids=guild_ids,
                auto_sync=auto_sync,
                extras=extras,
                **kwargs,
            )(func)
            self.add_user_command(result)
            return result

        return decorator

    def message_command(
        self,
        *,
        name: LocalizedOptional = None,
        dm_permission: Optional[bool] = None,  # deprecated
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
        install_types: Optional[ApplicationInstallTypes] = None,
        contexts: Optional[InteractionContextTypes] = None,
        guild_ids: Optional[Sequence[int]] = None,
        auto_sync: Optional[bool] = None,
        extras: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Callable[
        [InteractionCommandCallback[CogT, MessageCommandInteraction, P]], InvokableMessageCommand
    ]:
        """A shortcut decorator that invokes :func:`~disnake.ext.commands.message_command` and adds it to
        the internal command list.

        Parameters
        ----------
        name: Optional[Union[:class:`str`, :class:`.Localized`]]
            The name of the message command (defaults to function name).

            .. versionchanged:: 2.5
                Added support for localizations.

        dm_permission: :class:`bool`
            Whether this command can be used in DMs.
            Defaults to ``True``.

            .. deprecated:: 2.10
                Use ``contexts`` instead.
                This is equivalent to the :attr:`.InteractionContextTypes.bot_dm` flag.

        default_member_permissions: Optional[Union[:class:`.Permissions`, :class:`int`]]
            The default required permissions for this command.
            See :attr:`.ApplicationCommand.default_member_permissions` for details.

            .. versionadded:: 2.5

        nsfw: :class:`bool`
            Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
            Defaults to ``False``.

            .. versionadded:: 2.8

        install_types: Optional[:class:`.ApplicationInstallTypes`]
            The installation types where the command is available.
            Defaults to :attr:`.ApplicationInstallTypes.guild` only.
            Only available for global commands.

            See :ref:`app_command_contexts` for details.

            .. versionadded:: 2.10

        contexts: Optional[:class:`.InteractionContextTypes`]
            The interaction contexts where the command can be used.
            Only available for global commands.

            See :ref:`app_command_contexts` for details.

            .. versionadded:: 2.10

        auto_sync: :class:`bool`
            Whether to automatically register the command. Defaults to ``True``
        guild_ids: Sequence[:class:`int`]
            If specified, the client will register the command in these guilds.
            Otherwise, this command will be registered globally.
        extras: Dict[:class:`str`, Any]
            A dict of user provided extras to attach to the command.

            .. note::
                This object may be copied by the library.

            .. versionadded:: 2.5

        Returns
        -------
        Callable[..., :class:`InvokableMessageCommand`]
            A decorator that converts the provided method into an InvokableMessageCommand, adds it to the bot, then returns it.
        """

        def decorator(
            func: InteractionCommandCallback[CogT, MessageCommandInteraction, P],
        ) -> InvokableMessageCommand:
            result = message_command(
                name=name,
                dm_permission=dm_permission,
                default_member_permissions=default_member_permissions,
                nsfw=nsfw,
                install_types=install_types,
                contexts=contexts,
                guild_ids=guild_ids,
                auto_sync=auto_sync,
                extras=extras,
                **kwargs,
            )(func)
            self.add_message_command(result)
            return result

        return decorator

    # command synchronisation

    def _ordered_unsynced_commands(
        self, test_guilds: Optional[Sequence[int]] = None
    ) -> Tuple[List[ApplicationCommand], Dict[int, List[ApplicationCommand]]]:
        global_cmds = []
        guilds = {}

        for cmd in self.application_commands_iterator():
            if not cmd.auto_sync:
                cmd.body._always_synced = True

            guild_ids = cmd.guild_ids or test_guilds

            if guild_ids is None:
                global_cmds.append(cmd.body)
                continue

            for guild_id in guild_ids:
                if guild_id not in guilds:
                    guilds[guild_id] = [cmd.body]
                else:
                    guilds[guild_id].append(cmd.body)

        return global_cmds, guilds

    async def _cache_application_commands(self) -> None:
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("This method is only usable in disnake.Client subclasses")

        _, guilds = self._ordered_unsynced_commands(self._test_guilds)

        # Here we only cache global commands and commands from guilds that are specified in the code.
        # They're collected from the "test_guilds" kwarg of commands.InteractionBotBase
        # and the "guild_ids" kwarg of the decorators. This is the only way to avoid rate limits.
        # If we cache guild commands from everywhere, the limit of invalid requests gets exhausted.
        # This is because we don't know the scopes of the app in all guilds in advance, so we'll have to
        # catch a lot of "Forbidden" errors, exceeding the limit of 10k invalid requests in 10 minutes (for large bots).
        # However, our approach has blind spots. We deal with them in :meth:`process_application_commands`.

        try:
            commands = await self.fetch_global_commands(with_localizations=True)
            self._connection._global_application_commands = {
                command.id: command for command in commands
            }
        except (disnake.HTTPException, TypeError):
            pass
        for guild_id in guilds:
            try:
                commands = await self.fetch_guild_commands(guild_id, with_localizations=True)
                if commands:
                    self._connection._guild_application_commands[guild_id] = {
                        command.id: command for command in commands
                    }
            except (disnake.HTTPException, TypeError):
                pass

    async def _sync_application_commands(self) -> None:
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("This method is only usable in disnake.Client subclasses")

        if not self._command_sync_flags._sync_enabled or self._is_closed or self.loop.is_closed():
            return

        # We assume that all commands are already cached.
        # Sort all invokable commands between guild IDs:
        global_cmds, guild_cmds = self._ordered_unsynced_commands(self._test_guilds)

        if self._command_sync_flags.sync_global_commands:
            # Update global commands first
            diff = _app_commands_diff(
                global_cmds, self._connection._global_application_commands.values()
            )
            if not self._command_sync_flags.allow_command_deletion:
                # because allow_command_deletion is disabled, we want to never automatically delete a command
                # so we move the delete commands to delete_ignored
                diff["delete_ignored"] = diff["delete"]
                diff["delete"] = []
            update_required = bool(diff["upsert"] or diff["edit"] or diff["delete"])

            # Show the difference
            self._log_sync_debug(
                "Application command synchronization:\n"
                "GLOBAL COMMANDS\n"
                "===============\n"
                f"| Update is required: {update_required}\n{_format_diff(diff)}"
            )

            if update_required:
                # Notice that we don't do any API requests if there're no changes.
                to_send = _get_to_send_from_diff(diff)
                try:
                    await self.bulk_overwrite_global_commands(to_send)
                except Exception as e:
                    warnings.warn(
                        f"Failed to overwrite global commands due to {e}", SyncWarning, stacklevel=1
                    )

        # Same process but for each specified guild individually.
        # Notice that we're not doing this for every single guild for optimisation purposes.
        # See the note in :meth:`_cache_application_commands` about guild app commands.
        guild_ids_to_check = set(guild_cmds.keys())
        for guild_id in self._connection._guild_application_commands.keys():
            guild_ids_to_check.add(guild_id)
        if self._command_sync_flags.sync_guild_commands:
            for guild_id in guild_ids_to_check:
                current_guild_cmds = self._connection._guild_application_commands.get(guild_id, {})
                cmds = guild_cmds.get(guild_id, {})
                diff = _app_commands_diff(cmds, current_guild_cmds.values())
                if not self._command_sync_flags.allow_command_deletion:
                    # because allow_command_deletion is disabled, we want to never automatically delete a command
                    # so we move the delete commands to delete_ignored
                    diff["delete_ignored"] = diff["delete"]
                    diff["delete"] = []
                update_required = bool(diff["upsert"] or diff["edit"] or diff["delete"])

                # Show diff
                self._log_sync_debug(
                    "Application command synchronization:\n"
                    f"COMMANDS IN {guild_id}\n"
                    "===============================\n"
                    f"| Update is required: {update_required}\n{_format_diff(diff)}"
                )

                # Do API requests and cache
                if update_required:
                    to_send = _get_to_send_from_diff(diff)
                    try:
                        await self.bulk_overwrite_guild_commands(guild_id, to_send)
                    except Exception as e:
                        warnings.warn(
                            f"Failed to overwrite commands in <Guild id={guild_id}> due to {e}",
                            SyncWarning,
                            stacklevel=1,
                        )
        # Last debug message
        self._log_sync_debug("Command synchronization task has finished")

    def _log_sync_debug(self, text: str) -> None:
        if self._command_sync_flags.sync_commands_debug:
            # if sync debugging is enabled, *always* output logs
            if _log.isEnabledFor(logging.INFO):
                # if the log level is `INFO` or higher, use that
                _log.info(text)
            else:
                # if not, nothing would be logged, so just print instead
                print(text)
        else:
            # if debugging is not explicitly enabled, always use the debug log level
            _log.debug(text)

    async def _prepare_application_commands(self) -> None:
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("Command sync is only possible in disnake.Client subclasses")

        async with self._sync_queued:
            await self.wait_until_first_connect()
            await self._cache_application_commands()
            await self._sync_application_commands()

    async def _delayed_command_sync(self) -> None:
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("This method is only usable in disnake.Client subclasses")

        if (
            not self._command_sync_flags._sync_enabled
            or self._sync_queued.locked()
            or not self.is_ready()
            or self._is_closed
            or self.loop.is_closed()
        ):
            return
        # We don't do this task on login or in parallel with a similar task
        # Wait a little bit, maybe other cogs are loading
        async with self._sync_queued:
            await asyncio.sleep(2)
            await self._sync_application_commands()

    def _schedule_app_command_preparation(self) -> None:
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("Command sync is only possible in disnake.Client subclasses")

        self.loop.create_task(
            self._prepare_application_commands(), name="disnake: app_command_preparation"
        )

    def _schedule_delayed_command_sync(self) -> None:
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("This method is only usable in disnake.Client subclasses")

        self.loop.create_task(self._delayed_command_sync(), name="disnake: delayed_command_sync")

    # Error handlers

    async def on_slash_command_error(
        self, interaction: ApplicationCommandInteraction, exception: errors.CommandError
    ) -> None:
        """|coro|

        The default slash command error handler provided by the bot.

        By default this prints to :data:`sys.stderr` however it could be
        overridden to have a different implementation.

        This only fires if you do not specify any listeners for slash command error.
        """
        if self.extra_events.get("on_slash_command_error", None):
            return

        command = interaction.application_command
        if command and command.has_error_handler():
            return

        cog = command.cog
        if cog and cog.has_slash_error_handler():
            return

        print(f"Ignoring exception in slash command {command.name!r}:", file=sys.stderr)
        traceback.print_exception(
            type(exception), exception, exception.__traceback__, file=sys.stderr
        )

    async def on_user_command_error(
        self, interaction: ApplicationCommandInteraction, exception: errors.CommandError
    ) -> None:
        """|coro|

        Similar to :meth:`on_slash_command_error() <Bot.on_slash_command_error>` but for user commands.
        """
        if self.extra_events.get("on_user_command_error", None):
            return
        command = interaction.application_command
        if command and command.has_error_handler():
            return
        cog = command.cog
        if cog and cog.has_user_error_handler():
            return
        print(f"Ignoring exception in user command {command.name!r}:", file=sys.stderr)
        traceback.print_exception(
            type(exception), exception, exception.__traceback__, file=sys.stderr
        )

    async def on_message_command_error(
        self, interaction: ApplicationCommandInteraction, exception: errors.CommandError
    ) -> None:
        """|coro|

        Similar to :meth:`on_slash_command_error() <Bot.on_slash_command_error>` but for message commands.
        """
        if self.extra_events.get("on_message_command_error", None):
            return
        command = interaction.application_command
        if command and command.has_error_handler():
            return
        cog = command.cog
        if cog and cog.has_message_error_handler():
            return
        print(f"Ignoring exception in message command {command.name!r}:", file=sys.stderr)
        traceback.print_exception(
            type(exception), exception, exception.__traceback__, file=sys.stderr
        )

    # global check registration

    def add_app_command_check(
        self,
        func: AppCheck,
        *,
        call_once: bool = False,
        slash_commands: bool = False,
        user_commands: bool = False,
        message_commands: bool = False,
    ) -> None:
        """Adds a global application command check to the bot.

        This is the non-decorator interface to :func:`.app_check`,
        :meth:`.slash_command_check` and etc.

        You must specify at least one of the bool parameters, otherwise
        the check won't be added.

        Parameters
        ----------
        func
            The function that will be used as a global check.
        call_once: :class:`bool`
            Whether the function should only be called once per invoke call.
        slash_commands: :class:`bool`
            Whether this check is for slash commands.
        user_commands: :class:`bool`
            Whether this check is for user commands.
        message_commands: :class:`bool`
            Whether this check is for message commands.
        """
        if slash_commands:
            if call_once:
                self._slash_command_check_once.append(func)
            else:
                self._slash_command_checks.append(func)

        if user_commands:
            if call_once:
                self._user_command_check_once.append(func)
            else:
                self._user_command_checks.append(func)

        if message_commands:
            if call_once:
                self._message_command_check_once.append(func)
            else:
                self._message_command_checks.append(func)

    def remove_app_command_check(
        self,
        func: AppCheck,
        *,
        call_once: bool = False,
        slash_commands: bool = False,
        user_commands: bool = False,
        message_commands: bool = False,
    ) -> None:
        """Removes a global application command check from the bot.

        This function is idempotent and will not raise an exception
        if the function is not in the global checks.

        You must specify at least one of the bool parameters, otherwise
        the check won't be removed.

        Parameters
        ----------
        func
            The function to remove from the global checks.
        call_once: :class:`bool`
            Whether the function was added with ``call_once=True`` in
            the :meth:`.Bot.add_app_command_check` call.
        slash_commands: :class:`bool`
            Whether this check was for slash commands.
        user_commands: :class:`bool`
            Whether this check was for user commands.
        message_commands: :class:`bool`
            Whether this check was for message commands.
        """
        if slash_commands:
            check_list = self._slash_command_check_once if call_once else self._slash_command_checks
            try:
                check_list.remove(func)
            except ValueError:
                pass

        if user_commands:
            check_list = self._user_command_check_once if call_once else self._user_command_checks
            try:
                check_list.remove(func)
            except ValueError:
                pass

        if message_commands:
            check_list = (
                self._message_command_check_once if call_once else self._message_command_checks
            )
            try:
                check_list.remove(func)
            except ValueError:
                pass

    def slash_command_check(self, func: T) -> T:
        """Similar to :meth:`.check` but for slash commands."""
        # T was used instead of Check to ensure the type matches on return
        self.add_app_command_check(func, slash_commands=True)  # type: ignore
        return func

    def slash_command_check_once(self, func: CFT) -> CFT:
        """Similar to :meth:`.check_once` but for slash commands."""
        self.add_app_command_check(func, call_once=True, slash_commands=True)
        return func

    def user_command_check(self, func: T) -> T:
        """Similar to :meth:`.check` but for user commands."""
        # T was used instead of Check to ensure the type matches on return
        self.add_app_command_check(func, user_commands=True)  # type: ignore
        return func

    def user_command_check_once(self, func: CFT) -> CFT:
        """Similar to :meth:`.check_once` but for user commands."""
        self.add_app_command_check(func, call_once=True, user_commands=True)
        return func

    def message_command_check(self, func: T) -> T:
        """Similar to :meth:`.check` but for message commands."""
        # T was used instead of Check to ensure the type matches on return
        self.add_app_command_check(func, message_commands=True)  # type: ignore
        return func

    def message_command_check_once(self, func: CFT) -> CFT:
        """Similar to :meth:`.check_once` but for message commands."""
        self.add_app_command_check(func, call_once=True, message_commands=True)
        return func

    def application_command_check(
        self,
        *,
        call_once: bool = False,
        slash_commands: bool = False,
        user_commands: bool = False,
        message_commands: bool = False,
    ) -> Callable[
        [Callable[[ApplicationCommandInteraction], Any]],
        Callable[[ApplicationCommandInteraction], Any],
    ]:
        """A decorator that adds a global application command check to the bot.

        A global check is similar to a :func:`check` that is applied
        on a per command basis except it is run before any application command checks
        have been verified and applies to every application command the bot has.

        .. note::

            This function can either be a regular function or a coroutine.

        Similar to a command :func:`check`\\, this takes a single parameter
        of type :class:`.ApplicationCommandInteraction` and can only raise exceptions inherited from
        :exc:`CommandError`.

        Example
        -------

        .. code-block:: python3

            @bot.application_command_check()
            def check_app_commands(inter):
                return inter.channel_id in whitelisted_channels

        Parameters
        ----------
        call_once: :class:`bool`
            Whether the function should only be called once per invoke call.
        slash_commands: :class:`bool`
            Whether this check is for slash commands.
        user_commands: :class:`bool`
            Whether this check is for user commands.
        message_commands: :class:`bool`
            Whether this check is for message commands.
        """
        if not (slash_commands or user_commands or message_commands):
            slash_commands = True
            user_commands = True
            message_commands = True

        def decorator(
            func: Callable[[ApplicationCommandInteraction], Any],
        ) -> Callable[[ApplicationCommandInteraction], Any]:
            # T was used instead of Check to ensure the type matches on return
            self.add_app_command_check(
                func,
                call_once=call_once,
                slash_commands=slash_commands,
                user_commands=user_commands,
                message_commands=message_commands,
            )
            return func

        return decorator

    async def application_command_can_run(
        self, inter: ApplicationCommandInteraction, *, call_once: bool = False
    ) -> bool:
        if inter.data.type is ApplicationCommandType.chat_input:
            checks = self._slash_command_check_once if call_once else self._slash_command_checks

        elif inter.data.type is ApplicationCommandType.user:
            checks = self._user_command_check_once if call_once else self._user_command_checks

        elif inter.data.type is ApplicationCommandType.message:
            checks = self._message_command_check_once if call_once else self._message_command_checks

        else:
            return True

        if len(checks) == 0:
            return True

        return await disnake.utils.async_all(f(inter) for f in checks)

    def before_slash_command_invoke(self, coro: CFT) -> CFT:
        """Similar to :meth:`Bot.before_invoke` but for slash commands,
        and it takes an :class:`.ApplicationCommandInteraction` as its only parameter.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError("The pre-invoke hook must be a coroutine.")

        self._before_slash_command_invoke = coro
        return coro

    def after_slash_command_invoke(self, coro: CFT) -> CFT:
        """Similar to :meth:`Bot.after_invoke` but for slash commands,
        and it takes an :class:`.ApplicationCommandInteraction` as its only parameter.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError("The post-invoke hook must be a coroutine.")

        self._after_slash_command_invoke = coro
        return coro

    def before_user_command_invoke(self, coro: CFT) -> CFT:
        """Similar to :meth:`Bot.before_slash_command_invoke` but for user commands."""
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError("The pre-invoke hook must be a coroutine.")

        self._before_user_command_invoke = coro
        return coro

    def after_user_command_invoke(self, coro: CFT) -> CFT:
        """Similar to :meth:`Bot.after_slash_command_invoke` but for user commands."""
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError("The post-invoke hook must be a coroutine.")

        self._after_user_command_invoke = coro
        return coro

    def before_message_command_invoke(self, coro: CFT) -> CFT:
        """Similar to :meth:`Bot.before_slash_command_invoke` but for message commands."""
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError("The pre-invoke hook must be a coroutine.")

        self._before_message_command_invoke = coro
        return coro

    def after_message_command_invoke(self, coro: CFT) -> CFT:
        """Similar to :meth:`Bot.after_slash_command_invoke` but for message commands."""
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError("The post-invoke hook must be a coroutine.")

        self._after_message_command_invoke = coro
        return coro

    # command processing

    async def process_app_command_autocompletion(
        self, inter: ApplicationCommandInteraction
    ) -> None:
        """|coro|

        This function processes the application command autocompletions.
        Without this coroutine, none of the autocompletions will be performed.

        By default, this coroutine is called inside the :func:`.on_application_command_autocomplete`
        event. If you choose to override the :func:`.on_application_command_autocomplete` event, then
        you should invoke this coroutine as well.

        Parameters
        ----------
        inter: :class:`disnake.ApplicationCommandInteraction`
            The interaction to process.
        """
        slash_command = self.all_slash_commands.get(inter.data.name)

        if slash_command is None:
            return

        inter.application_command = slash_command
        if slash_command.guild_ids is None or inter.guild_id in slash_command.guild_ids:
            await slash_command._call_relevant_autocompleter(inter)

    async def process_application_commands(
        self, interaction: ApplicationCommandInteraction
    ) -> None:
        """|coro|

        This function processes the application commands that have been registered
        to the bot and other groups. Without this coroutine, none of the
        application commands will be triggered.

        By default, this coroutine is called inside the :func:`.on_application_command`
        event. If you choose to override the :func:`.on_application_command` event, then
        you should invoke this coroutine as well.

        Parameters
        ----------
        interaction: :class:`disnake.ApplicationCommandInteraction`
            The interaction to process commands for.
        """
        # This usually comes from the blind spots of the sync algorithm.
        # Since not all guild commands are cached, it is possible to experience such issues.
        # In this case, the blind spot is the interaction guild, let's fix it:
        if (
            # if we're not currently syncing,
            not self._sync_queued.locked()
            # and we're instructed to sync guild commands
            and self._command_sync_flags.sync_guild_commands
            # and the current command was registered to a guild
            and interaction.data.get("guild_id")
            # and we don't know the command
            and not self.get_guild_command(interaction.guild_id, interaction.data.id)  # type: ignore
        ):
            # don't do anything if we aren't allowed to disable them
            if self._command_sync_flags.allow_command_deletion:
                try:
                    await self.bulk_overwrite_guild_commands(interaction.guild_id, [])  # type: ignore
                except disnake.HTTPException:
                    # for some reason we were unable to sync the command
                    # either malformed API request, or some other error
                    # in theory this will never error: if a command exists the bot has authorisation
                    # in practice this is not the case, the API could change valid requests at any time
                    message = "This command could not be processed. Additionally, an error occured when trying to sync commands."
                else:
                    message = "This command has just been synced."
            else:
                # this block is responsible for responding to guild commands that we don't delete
                # this could be changed to not respond but that behavior is undecided
                message = "This command could not be processed."
            try:
                # This part is in a separate try-except because we still should respond to the interaction
                message += (
                    " More information about this: "
                    "https://docs.disnake.dev/page/ext/commands/additional_info.html#unknown-commands."
                )
                await interaction.response.send_message(
                    message,
                    ephemeral=True,
                )
            except (disnake.HTTPException, disnake.InteractionTimedOut):
                pass
            return

        command_type = interaction.data.type
        command_name = interaction.data.name
        app_command = None
        event_name = None

        if command_type is ApplicationCommandType.chat_input:
            app_command = self.all_slash_commands.get(command_name)
            event_name = "slash_command"

        elif command_type is ApplicationCommandType.user:
            app_command = self.all_user_commands.get(command_name)
            event_name = "user_command"

        elif command_type is ApplicationCommandType.message:
            app_command = self.all_message_commands.get(command_name)
            event_name = "message_command"

        if event_name is None or app_command is None:
            # If we are here, the command being invoked is either unknown or has an unknonw type.
            # This usually happens if the auto sync is disabled, so let's just ignore this.
            return

        self.dispatch(event_name, interaction)
        try:
            if await self.application_command_can_run(interaction, call_once=True):
                await app_command.invoke(interaction)
                self.dispatch(f"{event_name}_completion", interaction)
            else:
                raise errors.CheckFailure("The global check_once functions failed.")
        except errors.CommandError as exc:
            await app_command.dispatch_error(interaction, exc)

    async def on_application_command(self, interaction: ApplicationCommandInteraction) -> None:
        await self.process_application_commands(interaction)

    async def on_application_command_autocomplete(
        self, interaction: ApplicationCommandInteraction
    ) -> None:
        await self.process_app_command_autocompletion(interaction)
