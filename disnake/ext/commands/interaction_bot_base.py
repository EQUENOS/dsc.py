# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import logging
import sys
import traceback
import warnings
from types import MappingProxyType
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
    cast,
)

import disnake
from disnake.app_commands import ApplicationCommand, Option
from disnake.custom_warnings import SyncWarning
from disnake.enums import ApplicationCommandType
from disnake.utils import deprecated, warn_deprecated

from . import errors
from .base_core import AppCmdIndex, InvokableApplicationCommand
from .common_bot_base import CommonBotBase
from .ctx_menus_core import (
    InvokableMessageCommand,
    InvokableUserCommand,
    message_command,
    user_command,
)
from .errors import ApplicationCommandRegistrationError
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


def _match_subcommand_chain(
    command: InvokableSlashCommand, chain: List[str]
) -> Union[InvokableSlashCommand, SubCommand, SubCommandGroup, None]:
    """An internal function that returns a subcommand with a route matching the chain.
    If there's no match then ``None`` is returned.
    """
    if command.name != chain[0]:
        return None
    if len(chain) == 1:
        return command
    if len(chain) == 2:
        return command.children.get(chain[1])
    if len(chain) == 3:
        group = command.children.get(chain[1])
        if isinstance(group, SubCommandGroup):
            return group.children.get(chain[2])


class InteractionBotBase(CommonBotBase):
    def __init__(
        self,
        *,
        command_sync_flags: Optional[CommandSyncFlags] = None,
        sync_commands: bool = MISSING,
        sync_commands_debug: bool = MISSING,
        sync_commands_on_cog_unload: bool = MISSING,
        test_guilds: Optional[Sequence[int]] = None,
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

        self._all_app_commands: Dict[AppCmdIndex, InvokableApplicationCommand] = {}

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

    @property
    def all_app_commands(self) -> MappingProxyType[AppCmdIndex, InvokableApplicationCommand]:
        """Mapping[:class:`AppCmdIndex`, :class:`InvokableApplicationCommand`]:
        A read-only mapping with all application commands the bot has.
        """
        return MappingProxyType(self._all_app_commands)

    @property
    def application_commands(self) -> Set[InvokableApplicationCommand]:
        """Set[:class:`InvokableApplicationCommand`]: A set of all application commands the bot has."""
        return set(self._all_app_commands.values())

    @property
    def slash_commands(self) -> Set[InvokableSlashCommand]:
        """Set[:class:`InvokableSlashCommand`]: A set of all slash commands the bot has."""
        return {
            cmd for cmd in self._all_app_commands.values() if isinstance(cmd, InvokableSlashCommand)
        }

    @property
    def user_commands(self) -> Set[InvokableUserCommand]:
        """Set[:class:`InvokableUserCommand`]: A set of all user commands the bot has."""
        return {
            cmd for cmd in self._all_app_commands.values() if isinstance(cmd, InvokableUserCommand)
        }

    @property
    def message_commands(self) -> Set[InvokableMessageCommand]:
        """Set[:class:`InvokableMessageCommand`]: A set of all message commands the bot has."""
        return {
            cmd
            for cmd in self._all_app_commands.values()
            if isinstance(cmd, InvokableMessageCommand)
        }

    @property
    @deprecated("slash_commands")
    def all_slash_commands(self) -> Dict[str, InvokableSlashCommand]:
        # no docstring because it was an attribute and now it's deprecated
        return {
            cmd.name: cmd
            for cmd in self._all_app_commands.values()
            if isinstance(cmd, InvokableSlashCommand)
        }

    @property
    @deprecated("user_commands")
    def all_user_commands(self) -> Dict[str, InvokableUserCommand]:
        # no docstring because it was an attribute and now it's deprecated
        return {
            cmd.name: cmd
            for cmd in self._all_app_commands.values()
            if isinstance(cmd, InvokableUserCommand)
        }

    @property
    @deprecated("message_commands")
    def all_message_commands(self) -> Dict[str, InvokableMessageCommand]:
        # no docstring because it was an attribute and now it's deprecated
        return {
            cmd.name: cmd
            for cmd in self._all_app_commands.values()
            if isinstance(cmd, InvokableMessageCommand)
        }

    def add_app_command(self, app_command: InvokableApplicationCommand) -> None:
        """Adds an :class:`InvokableApplicationCommand` into the internal list of app commands.

        This is usually not called, instead shortcut decorators are used, such as
        :meth:`.slash_command`, :meth:`.user_command` or :meth:`.message_command`.

        The app command is registered to guilds specified in the ``guild_ids`` attribute.
        If this attribute is ``None`` then the command is registered globally, unless
        parameter ``test_guilds`` is specified in the bot constructor, in which case
        this command is registered to those guilds.

        .. versionadded:: 2.10

        Parameters
        ----------
        app_command: :class:`InvokableApplicationCommand`
            The app command to add.

        Raises
        ------
        ApplicationCommandRegistrationError
            The app command is already registered.
        TypeError
            The app command passed is not an instance of :class:`InvokableApplicationCommand`.
        """
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("This method is only usable in disnake.Client subclasses")

        if not isinstance(app_command, InvokableApplicationCommand):
            raise TypeError(
                "The app_command passed must be an instance of InvokableApplicationCommand"
            )
        if isinstance(app_command, (SubCommand, SubCommandGroup)):
            raise TypeError(
                "The app_command passed must be a top level command, "
                "not an instance of SubCommand or SubCommandGroup"
            )

        test_guilds = (None,) if self._test_guilds is None else self._test_guilds
        guild_ids = app_command.guild_ids or test_guilds

        for guild_id in guild_ids:
            cmd_index = AppCmdIndex(
                type=app_command.body.type, name=app_command.name, guild_id=guild_id
            )
            if cmd_index in self._all_app_commands:
                raise ApplicationCommandRegistrationError(
                    cmd_index.type, cmd_index.name, cmd_index.guild_id
                )

            # localization may be called multiple times for the same command but it's harmless
            app_command.body.localize(self.i18n)
            # note that we're adding the same command object for each guild_id
            # this ensures that any changes that happen to app_command after add_app_command
            # (such as hook attachments or permission modifications) apply properly
            self._all_app_commands[cmd_index] = app_command

    @deprecated("add_app_command")
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
        self.add_app_command(slash_command)

    @deprecated("add_app_command")
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
        self.add_app_command(user_command)

    @deprecated("add_app_command")
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
        self.add_app_command(message_command)

    def remove_app_command(
        self, cmd_type: ApplicationCommandType, name: str, *, guild_id: Optional[int]
    ) -> Optional[InvokableApplicationCommand]:
        """Removes an :class:`InvokableApplicationCommand` from the internal list of app commands.

        .. versionadded:: 2.10

        Parameters
        ----------
        cmd_type: :class:`disnake.ApplicationCommandType`
            The type of the app command to remove.
        name: :class:`str`
            The name of the app command to remove.
        guild_id: Optional[:class:`int`]
            The ID of the guild from which this command should be removed,
            or ``None`` if it's global.

        Returns
        -------
        Optional[:class:`InvokableApplicationCommand`]
            The app command that was removed. If no matching command was found, then ``None`` is returned instead.
        """
        if guild_id is not None or self._test_guilds is None:
            cmd_index = AppCmdIndex(type=cmd_type, name=name, guild_id=guild_id)
            return self._all_app_commands.pop(cmd_index, None)

        result = None
        for guild_id in self._test_guilds:
            cmd_index = AppCmdIndex(type=cmd_type, name=name, guild_id=guild_id)
            cmd = self._all_app_commands.pop(cmd_index, None)
            if result is None:
                result = cmd

        return result

    def _remove_app_commands(
        self, cmd_type: ApplicationCommandType, name: str, *, guild_ids: Optional[Sequence[int]]
    ) -> None:
        test_guilds = (None,) if self._test_guilds is None else self._test_guilds
        # this is consistent with the behavior of command synchronisation
        final_guild_ids = guild_ids or test_guilds

        for guild_id in final_guild_ids:
            cmd_index = AppCmdIndex(type=cmd_type, name=name, guild_id=guild_id)
            self._all_app_commands.pop(cmd_index, None)

    def _emulate_old_app_command_remove(self, cmd_type: ApplicationCommandType, name: str) -> Any:
        type_info = "slash" if cmd_type is ApplicationCommandType.chat_input else cmd_type.name
        warn_deprecated(
            f"remove_{type_info}_command is deprecated and will be removed in a future version. "
            "Use remove_app_command instead.",
            stacklevel=3,
        )
        bad_keys: List[AppCmdIndex] = []
        for key in self._all_app_commands.keys():
            if key.type is cmd_type and key.name == name:
                bad_keys.append(key)

        result: Optional[InvokableApplicationCommand] = None
        for key in bad_keys:
            cmd = self._all_app_commands.pop(key, None)
            if result is None:
                result = cmd

        return result

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
        return self._emulate_old_app_command_remove(ApplicationCommandType.chat_input, name)

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
        return self._emulate_old_app_command_remove(ApplicationCommandType.user, name)

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
        return self._emulate_old_app_command_remove(ApplicationCommandType.message, name)

    def get_slash_command(
        self, name: str, guild_id: Optional[int] = MISSING
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
        guild_id: Optional[:class:`int`]
            The guild ID corresponding to the slash command or ``None`` if it's a global command.
            If this is not specified then the first match is returned instead.

        Raises
        ------
        TypeError
            The name is not a string.
        ValueError
            Parameter ``guild_id`` was not provided in a case where different slash commands
            have the same name but different guild_ids.

        Returns
        -------
        Optional[Union[:class:`InvokableSlashCommand`, :class:`SubCommandGroup`, :class:`SubCommand`]]
            The slash command that was requested. If not found, returns ``None``.
        """
        if not isinstance(name, str):
            raise TypeError(f"Expected name to be str, not {name.__class__}")

        chain = name.split()
        if guild_id is not MISSING:
            cmd_index = AppCmdIndex(
                type=ApplicationCommandType.chat_input, name=chain[0], guild_id=guild_id
            )
            command = self._all_app_commands.get(cmd_index)
            if command is None:
                return None
            return _match_subcommand_chain(command, chain)  # type: ignore

        # this is mostly for backwards compatibility, as previously guild_id arg didn't exist
        result = None
        for command in self._all_app_commands.values():
            if not isinstance(command, InvokableSlashCommand):
                continue
            chain_match = _match_subcommand_chain(command, chain)
            if chain_match is None:
                continue
            if result is None:
                result = chain_match
            # we should check whether there's an ambiguity in command search
            elif chain_match is not result:
                raise ValueError(
                    "Argument guild_id must be provided if there're different slash commands "
                    "with the same name but different guilds or one of them is global."
                )

        return result

    def get_user_command(
        self, name: str, guild_id: Optional[int] = MISSING
    ) -> Optional[InvokableUserCommand]:
        """Gets an :class:`InvokableUserCommand` from the internal list
        of user commands.

        Parameters
        ----------
        name: :class:`str`
            The name of the user command to get.
        guild_id: Optional[:class:`int`]
            The guild ID corresponding to the user command or ``None`` if it's a global command.
            If this is not specified then the first match is returned instead.

        Raises
        ------
        ValueError
            Parameter ``guild_id`` was not provided in a case where different user commands
            have the same name but different guild_ids.

        Returns
        -------
        Optional[:class:`InvokableUserCommand`]
            The user command that was requested. If not found, returns ``None``.
        """
        if guild_id is not MISSING:
            cmd_index = AppCmdIndex(type=ApplicationCommandType.user, name=name, guild_id=guild_id)
            command = self._all_app_commands.get(cmd_index)
            if command is None:
                return None
            return command  # type: ignore
        # this is mostly for backwards compatibility, as previously guild_id arg didn't exist
        result = None
        for command in self._all_app_commands.values():
            if not isinstance(command, InvokableUserCommand) or command.name != name:
                continue
            if result is None:
                result = command
            # we should check whether there's an ambiguity in command search
            elif command is not result:
                raise ValueError(
                    "Argument guild_id must be provided if there're different user commands "
                    "with the same name but different guilds or one of them is global."
                )

        return result

    def get_message_command(
        self, name: str, guild_id: Optional[int] = MISSING
    ) -> Optional[InvokableMessageCommand]:
        """Gets an :class:`InvokableMessageCommand` from the internal list
        of message commands.

        Parameters
        ----------
        name: :class:`str`
            The name of the message command to get.
        guild_id: Optional[:class:`int`]
            The guild ID corresponding to the message command or ``None`` if it's a global command.
            If this is not specified then the first match is returned instead.

        Raises
        ------
        ValueError
            Parameter ``guild_id`` was not provided in a case where different message commands
            have the same name but different guild_ids.

        Returns
        -------
        Optional[:class:`InvokableMessageCommand`]
            The message command that was requested. If not found, returns ``None``.
        """
        if guild_id is not MISSING:
            cmd_index = AppCmdIndex(
                type=ApplicationCommandType.message, name=name, guild_id=guild_id
            )
            command = self._all_app_commands.get(cmd_index)
            if command is None:
                return None
            return command  # type: ignore
        # this is mostly for backwards compatibility, as previously guild_id arg didn't exist
        result = None
        for command in self._all_app_commands.values():
            if not isinstance(command, InvokableMessageCommand) or command.name != name:
                continue
            if result is None:
                result = command
            # we should check whether there's an ambiguity in command search
            elif command is not result:
                raise ValueError(
                    "Argument guild_id must be provided if there're different message commands "
                    "with the same name but different guilds or one of them is global."
                )

        return result

    def slash_command(
        self,
        *,
        name: LocalizedOptional = None,
        description: LocalizedOptional = None,
        dm_permission: Optional[bool] = None,
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
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
        default_member_permissions: Optional[Union[:class:`.Permissions`, :class:`int`]]
            The default required permissions for this command.
            See :attr:`.ApplicationCommand.default_member_permissions` for details.

            .. versionadded:: 2.5

        nsfw: :class:`bool`
            Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
            Defaults to ``False``.

            .. versionadded:: 2.8

        auto_sync: :class:`bool`
            Whether to automatically register the command. Defaults to ``True``
        guild_ids: Optional[Sequence[:class:`int`]]
            If specified, the client will register the command to these guilds.
            Otherwise the command will be registered globally, unless
            parameter ``test_guilds`` is specified in the bot constructor, in which case
            this command will be registered to those guilds.
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
                guild_ids=guild_ids,
                connectors=connectors,
                auto_sync=auto_sync,
                extras=extras,
                **kwargs,
            )(func)
            self.add_app_command(result)
            return result

        return decorator

    def user_command(
        self,
        *,
        name: LocalizedOptional = None,
        dm_permission: Optional[bool] = None,
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
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
        default_member_permissions: Optional[Union[:class:`.Permissions`, :class:`int`]]
            The default required permissions for this command.
            See :attr:`.ApplicationCommand.default_member_permissions` for details.

            .. versionadded:: 2.5

        nsfw: :class:`bool`
            Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
            Defaults to ``False``.

            .. versionadded:: 2.8

        auto_sync: :class:`bool`
            Whether to automatically register the command. Defaults to ``True``.
        guild_ids: Optional[Sequence[:class:`int`]]
            If specified, the client will register the command to these guilds.
            Otherwise the command will be registered globally, unless
            parameter ``test_guilds`` is specified in the bot constructor, in which case
            this command will be registered to those guilds.
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
            func: InteractionCommandCallback[CogT, UserCommandInteraction, P]
        ) -> InvokableUserCommand:
            result = user_command(
                name=name,
                dm_permission=dm_permission,
                default_member_permissions=default_member_permissions,
                nsfw=nsfw,
                guild_ids=guild_ids,
                auto_sync=auto_sync,
                extras=extras,
                **kwargs,
            )(func)
            self.add_app_command(result)
            return result

        return decorator

    def message_command(
        self,
        *,
        name: LocalizedOptional = None,
        dm_permission: Optional[bool] = None,
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
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
        default_member_permissions: Optional[Union[:class:`.Permissions`, :class:`int`]]
            The default required permissions for this command.
            See :attr:`.ApplicationCommand.default_member_permissions` for details.

            .. versionadded:: 2.5

        nsfw: :class:`bool`
            Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
            Defaults to ``False``.

            .. versionadded:: 2.8

        auto_sync: :class:`bool`
            Whether to automatically register the command. Defaults to ``True``
        guild_ids: Optional[Sequence[:class:`int`]]
            If specified, the client will register the command to these guilds.
            Otherwise the command will be registered globally, unless
            parameter ``test_guilds`` is specified in the bot constructor, in which case
            this command will be registered to those guilds.
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
            func: InteractionCommandCallback[CogT, MessageCommandInteraction, P]
        ) -> InvokableMessageCommand:
            result = message_command(
                name=name,
                dm_permission=dm_permission,
                default_member_permissions=default_member_permissions,
                nsfw=nsfw,
                guild_ids=guild_ids,
                auto_sync=auto_sync,
                extras=extras,
                **kwargs,
            )(func)
            self.add_app_command(result)
            return result

        return decorator

    # command synchronisation

    def _ordered_unsynced_commands(
        self,
    ) -> Tuple[List[ApplicationCommand], Dict[int, List[ApplicationCommand]]]:
        global_cmds: List[ApplicationCommand] = []
        guilds: Dict[int, List[ApplicationCommand]] = {}

        for key, cmd in self._all_app_commands.items():
            if not cmd.auto_sync:
                cmd.body._always_synced = True

            guild_id = key.guild_id

            if guild_id is None:
                global_cmds.append(cmd.body)
            elif guild_id not in guilds:
                guilds[guild_id] = [cmd.body]
            else:
                guilds[guild_id].append(cmd.body)

        return global_cmds, guilds

    async def _cache_application_commands(self) -> None:
        if not isinstance(self, disnake.Client):
            raise NotImplementedError("This method is only usable in disnake.Client subclasses")

        _, guilds = self._ordered_unsynced_commands()

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
        # Group all invokable commands by guild IDs:
        global_cmds, guild_cmds = self._ordered_unsynced_commands()

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
        if self._command_sync_flags.sync_guild_commands:
            for guild_id, cmds in guild_cmds.items():
                current_guild_cmds = self._connection._guild_application_commands.get(guild_id, {})
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
            func: Callable[[ApplicationCommandInteraction], Any]
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
        # `inter.data.guild_id` is the guild ID the command is registered to,
        # so this is correct even when a global command is called from a guild
        cmd_index = AppCmdIndex(
            type=inter.data.type, name=inter.data.name, guild_id=inter.data.guild_id
        )
        # this happens to always be a slash command
        slash_command = self._all_app_commands.get(cmd_index)

        if slash_command is None:
            return

        slash_command = cast(InvokableSlashCommand, slash_command)

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
            and interaction.data.guild_id
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
        event_name = None
        # `inter.data.guild_id` is the guild ID the command is registered to,
        # so this is correct even when a global command is called from a guild
        cmd_index = AppCmdIndex(
            type=command_type, name=interaction.data.name, guild_id=interaction.data.guild_id
        )
        app_command = self._all_app_commands.get(cmd_index)

        if command_type is ApplicationCommandType.chat_input:
            event_name = "slash_command"
        elif command_type is ApplicationCommandType.user:
            event_name = "user_command"
        elif command_type is ApplicationCommandType.message:
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
