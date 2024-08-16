# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

from disnake import utils
from disnake.app_commands import Option, SlashCommand
from disnake.enums import OptionType
from disnake.i18n import Localized
from disnake.interactions import ApplicationCommandInteraction
from disnake.permissions import Permissions

from .base_core import InvokableApplicationCommand, _get_overridden_method
from .errors import CommandError, CommandInvokeError
from .params import call_param_func, classify_autocompleter, expand_params

if TYPE_CHECKING:
    from disnake.app_commands import Choices
    from disnake.i18n import LocalizedOptional

    from .base_core import CommandCallback

MISSING = utils.MISSING

__all__ = ("InvokableSlashCommand", "SubCommandGroup", "SubCommand", "slash_command")


SlashCommandT = TypeVar("SlashCommandT", bound="InvokableSlashCommand")


def _autocomplete(
    self: Union[SubCommand, InvokableSlashCommand], option_name: str
) -> Callable[[Callable], Callable]:
    for option in self.body.options:
        if option.name == option_name:
            option.autocomplete = True
            break
    else:  # nobreak
        raise ValueError(f"Option '{option_name}' doesn't exist in '{self.qualified_name}'")

    def decorator(func: Callable) -> Callable:
        classify_autocompleter(func)
        self.autocompleters[option_name] = func
        return func

    return decorator


async def _call_autocompleter(
    self: Union[InvokableSlashCommand, SubCommand],
    param: str,
    inter: ApplicationCommandInteraction,
    user_input: str,
) -> Optional[Choices]:
    autocomp = self.autocompleters.get(param)
    if autocomp is None:
        return None
    if not callable(autocomp):
        return autocomp

    try:
        requires_cog_param = autocomp.__has_cog_param__
    except AttributeError:
        requires_cog_param = False

    cog = self.root_parent.cog if isinstance(self, SubCommand) else self.cog
    filled = inter.filled_options
    del filled[inter.data.focused_option.name]

    try:
        if requires_cog_param:
            choices = autocomp(cog, inter, user_input, **filled)
        else:
            choices = autocomp(inter, user_input, **filled)
    except TypeError:
        if requires_cog_param:
            choices = autocomp(cog, inter, user_input)
        else:
            choices = autocomp(inter, user_input)

    if inspect.isawaitable(choices):
        return await choices
    return choices


class SubCommandGroup(InvokableApplicationCommand):
    """A class that implements the protocol for a bot slash command group.

    These are not created manually, instead they are created via the
    decorator or functional interface.

    Attributes
    ----------
    name: :class:`str`
        The name of the group.
    qualified_name: :class:`str`
        The full command name, including parent names in the case of slash subcommands or groups.
        For example, the qualified name for ``/one two three`` would be ``one two three``.
    parent: :class:`InvokableSlashCommand`
        The parent command this group belongs to.

        .. versionadded:: 2.6
    option: :class:`.Option`
        API representation of this subcommand.
    callback: :ref:`coroutine <coroutine>`
        The coroutine that is executed when the command group is invoked.
    cog: Optional[:class:`Cog`]
        The cog that this group belongs to. ``None`` if there isn't one.
    checks: List[Callable[[:class:`.ApplicationCommandInteraction`], :class:`bool`]]
        A list of predicates that verifies if the group could be executed
        with the given :class:`.ApplicationCommandInteraction` as the sole parameter. If an exception
        is necessary to be thrown to signal failure, then one inherited from
        :exc:`.CommandError` should be used. Note that if the checks fail then
        :exc:`.CheckFailure` exception is raised to the :func:`.on_slash_command_error`
        event.
    extras: Dict[:class:`str`, Any]
        A dict of user provided extras to attach to the subcommand group.

        .. note::
            This object may be copied by the library.

        .. versionadded:: 2.5
    """

    def __init__(
        self,
        func: CommandCallback,
        parent: InvokableSlashCommand,
        *,
        name: LocalizedOptional = None,
        **kwargs: Any,
    ) -> None:
        name_loc = Localized._cast(name, False)
        super().__init__(func, name=name_loc.string, **kwargs)
        self.parent: InvokableSlashCommand = parent
        self.children: Dict[str, SubCommand] = {}
        self.option = Option(
            name=name_loc._upgrade(self.name),
            description="-",
            type=OptionType.sub_command_group,
            options=[],
        )
        self.qualified_name: str = f"{parent.qualified_name} {self.name}"

        if (
            "dm_permission" in kwargs
            or "default_member_permissions" in kwargs
            or hasattr(func, "__default_member_permissions__")
        ):
            raise TypeError(
                "Cannot set `default_member_permissions` or `dm_permission` on subcommand groups"
            )

    @property
    def root_parent(self) -> InvokableSlashCommand:
        """:class:`InvokableSlashCommand`: Returns the slash command containing this group.
        This is mainly for consistency with :class:`SubCommand`, and is equivalent to :attr:`parent`.

        .. versionadded:: 2.6
        """
        return self.parent

    @property
    def parents(self) -> Tuple[InvokableSlashCommand]:
        """Tuple[:class:`InvokableSlashCommand`]: Returns all parents of this group.

        .. versionadded:: 2.6
        """
        return (self.parent,)

    @property
    def body(self) -> Option:
        return self.option

    def sub_command(
        self,
        name: LocalizedOptional = None,
        description: LocalizedOptional = None,
        options: Optional[list] = None,
        connectors: Optional[dict] = None,
        extras: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Callable[[CommandCallback], SubCommand]:
        """A decorator that creates a subcommand in the subcommand group.
        Parameters are the same as in :class:`InvokableSlashCommand.sub_command`

        Returns
        -------
        Callable[..., :class:`SubCommand`]
            A decorator that converts the provided method into a SubCommand, adds it to the bot, then returns it.
        """

        def decorator(func: CommandCallback) -> SubCommand:
            new_func = SubCommand(
                func,
                self,
                name=name,
                description=description,
                options=options,
                connectors=connectors,
                extras=extras,
                **kwargs,
            )
            self.children[new_func.name] = new_func
            self.option.options.append(new_func.option)
            return new_func

        return decorator


class SubCommand(InvokableApplicationCommand):
    """A class that implements the protocol for a bot slash subcommand.

    These are not created manually, instead they are created via the
    decorator or functional interface.

    Attributes
    ----------
    name: :class:`str`
        The name of the subcommand.
    qualified_name: :class:`str`
        The full command name, including parent names in the case of slash subcommands or groups.
        For example, the qualified name for ``/one two three`` would be ``one two three``.
    parent: Union[:class:`InvokableSlashCommand`, :class:`SubCommandGroup`]
        The parent command or group this subcommand belongs to.

        .. versionadded:: 2.6
    option: :class:`.Option`
        API representation of this subcommand.
    callback: :ref:`coroutine <coroutine>`
        The coroutine that is executed when the subcommand is called.
    cog: Optional[:class:`Cog`]
        The cog that this subcommand belongs to. ``None`` if there isn't one.
    checks: List[Callable[[:class:`.ApplicationCommandInteraction`], :class:`bool`]]
        A list of predicates that verifies if the subcommand could be executed
        with the given :class:`.ApplicationCommandInteraction` as the sole parameter. If an exception
        is necessary to be thrown to signal failure, then one inherited from
        :exc:`.CommandError` should be used. Note that if the checks fail then
        :exc:`.CheckFailure` exception is raised to the :func:`.on_slash_command_error`
        event.
    connectors: Dict[:class:`str`, :class:`str`]
        A mapping of option names to function parameter names, mainly for internal processes.
    extras: Dict[:class:`str`, Any]
        A dict of user provided extras to attach to the subcommand.

        .. note::
            This object may be copied by the library.

        .. versionadded:: 2.5
    """

    def __init__(
        self,
        func: CommandCallback,
        parent: Union[InvokableSlashCommand, SubCommandGroup],
        *,
        name: LocalizedOptional = None,
        description: LocalizedOptional = None,
        options: Optional[list] = None,
        connectors: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        name_loc = Localized._cast(name, False)
        super().__init__(func, name=name_loc.string, **kwargs)
        self.parent: Union[InvokableSlashCommand, SubCommandGroup] = parent
        self.connectors: Dict[str, str] = connectors or {}
        self.autocompleters: Dict[str, Any] = kwargs.get("autocompleters", {})

        if options is None:
            options = expand_params(self)

        self.docstring = utils.parse_docstring(func)
        desc_loc = Localized._cast(description, False)

        self.option = Option(
            name=name_loc._upgrade(self.name, key=self.docstring["localization_key_name"]),
            description=desc_loc._upgrade(
                self.docstring["description"] or "-", key=self.docstring["localization_key_desc"]
            ),
            type=OptionType.sub_command,
            options=options,
        )
        self.qualified_name = f"{parent.qualified_name} {self.name}"

        if (
            "dm_permission" in kwargs
            or "default_member_permissions" in kwargs
            or hasattr(func, "__default_member_permissions__")
        ):
            raise TypeError(
                "Cannot set `default_member_permissions` or `dm_permission` on subcommands"
            )

    @property
    def root_parent(self) -> InvokableSlashCommand:
        """:class:`InvokableSlashCommand`: Returns the top-level slash command containing this subcommand,
        even if the parent is a :class:`SubCommandGroup`.

        .. versionadded:: 2.6
        """
        return self.parent.parent if isinstance(self.parent, SubCommandGroup) else self.parent

    @property
    def parents(
        self,
    ) -> Union[Tuple[InvokableSlashCommand], Tuple[SubCommandGroup, InvokableSlashCommand]]:
        """Union[Tuple[:class:`InvokableSlashCommand`], Tuple[:class:`SubCommandGroup`, :class:`InvokableSlashCommand`]]:
        Returns all parents of this subcommand.

        For example, the parents of the ``c`` subcommand in ``/a b c`` are ``(b, a)``.

        .. versionadded:: 2.6
        """
        # here I'm not using 'self.parent.parents + (self.parent,)' because it causes typing issues
        if isinstance(self.parent, SubCommandGroup):
            return (self.parent, self.parent.parent)
        return (self.parent,)

    @property
    def description(self) -> str:
        """:class:`str`: The slash sub command's description. Shorthand for :attr:`self.body.description <.Option.description>`."""
        return self.body.description

    @property
    def body(self) -> Option:
        """:class:`.Option`: The API representation for this slash sub command. Shorthand for :attr:`.SubCommand.option`"""
        return self.option

    async def _call_autocompleter(
        self, param: str, inter: ApplicationCommandInteraction, user_input: str
    ) -> Optional[Choices]:
        return await _call_autocompleter(self, param, inter, user_input)

    async def invoke(self, inter: ApplicationCommandInteraction, *args: Any, **kwargs: Any) -> None:
        for k, v in self.connectors.items():
            if k in kwargs:
                kwargs[v] = kwargs.pop(k)

        await self.prepare(inter)

        try:
            await call_param_func(self.callback, inter, self.cog, **kwargs)
        except CommandError:
            inter.command_failed = True
            raise
        except asyncio.CancelledError:
            inter.command_failed = True
            return
        except Exception as exc:
            inter.command_failed = True
            raise CommandInvokeError(exc) from exc
        finally:
            if self._max_concurrency is not None:
                await self._max_concurrency.release(inter)  # type: ignore

            await self.call_after_hooks(inter)

    def autocomplete(self, option_name: str) -> Callable[[Callable], Callable]:
        """A decorator that registers an autocomplete function for the specified option.

        Parameters
        ----------
        option_name: :class:`str`
            The name of the slash command option.
        """
        return _autocomplete(self, option_name)


class InvokableSlashCommand(InvokableApplicationCommand):
    """A class that implements the protocol for a bot slash command.

    These are not created manually, instead they are created via the
    decorator or functional interface.

    Attributes
    ----------
    name: :class:`str`
        The name of the command.
    qualified_name: :class:`str`
        The full command name, including parent names in the case of slash subcommands or groups.
        For example, the qualified name for ``/one two three`` would be ``one two three``.
    body: :class:`.SlashCommand`
        An object being registered in the API.
    callback: :ref:`coroutine <coroutine>`
        The coroutine that is executed when the command is called.
    cog: Optional[:class:`Cog`]
        The cog that this command belongs to. ``None`` if there isn't one.
    checks: List[Callable[[:class:`.ApplicationCommandInteraction`], :class:`bool`]]
        A list of predicates that verifies if the command could be executed
        with the given :class:`.ApplicationCommandInteraction` as the sole parameter. If an exception
        is necessary to be thrown to signal failure, then one inherited from
        :exc:`.CommandError` should be used. Note that if the checks fail then
        :exc:`.CheckFailure` exception is raised to the :func:`.on_slash_command_error`
        event.
    guild_ids: Optional[Tuple[:class:`int`, ...]]
        The list of IDs of the guilds where the command is synced. ``None`` if this command is global.
    connectors: Dict[:class:`str`, :class:`str`]
        A mapping of option names to function parameter names, mainly for internal processes.
    auto_sync: :class:`bool`
        Whether to automatically register the command.
    extras: Dict[:class:`str`, Any]
        A dict of user provided extras to attach to the command.

        .. note::
            This object may be copied by the library.

        .. versionadded:: 2.5

    parent: ``None``
        This exists for consistency with :class:`SubCommand` and :class:`SubCommandGroup`. Always ``None``.

        .. versionadded:: 2.6
    """

    def __init__(
        self,
        func: CommandCallback,
        *,
        name: LocalizedOptional = None,
        description: LocalizedOptional = None,
        options: Optional[List[Option]] = None,
        dm_permission: Optional[bool] = None,
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
        guild_ids: Optional[Sequence[int]] = None,
        connectors: Optional[Dict[str, str]] = None,
        auto_sync: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        name_loc = Localized._cast(name, False)
        super().__init__(func, name=name_loc.string, **kwargs)
        self.parent = None
        self.connectors: Dict[str, str] = connectors or {}
        self.children: Dict[str, Union[SubCommand, SubCommandGroup]] = {}
        self.auto_sync: bool = True if auto_sync is None else auto_sync
        self.guild_ids: Optional[Tuple[int, ...]] = None if guild_ids is None else tuple(guild_ids)
        self.autocompleters: Dict[str, Any] = kwargs.get("autocompleters", {})

        if options is None:
            options = expand_params(self)

        self.docstring = utils.parse_docstring(func)
        desc_loc = Localized._cast(description, False)

        try:
            default_member_permissions = func.__default_member_permissions__
        except AttributeError:
            pass

        dm_permission = True if dm_permission is None else dm_permission

        self.body: SlashCommand = SlashCommand(
            name=name_loc._upgrade(self.name, key=self.docstring["localization_key_name"]),
            description=desc_loc._upgrade(
                self.docstring["description"] or "-", key=self.docstring["localization_key_desc"]
            ),
            options=options or [],
            dm_permission=dm_permission and not self._guild_only,
            default_member_permissions=default_member_permissions,
            nsfw=nsfw,
        )

    @property
    def root_parent(self) -> None:
        """``None``: This is for consistency with :class:`SubCommand` and :class:`SubCommandGroup`.

        .. versionadded:: 2.6
        """
        return None

    @property
    def parents(self) -> Tuple[()]:
        """Tuple[()]: This is mainly for consistency with :class:`SubCommand`, and is equivalent to an empty tuple.

        .. versionadded:: 2.6
        """
        return ()

    def _ensure_assignment_on_copy(self, other: SlashCommandT) -> SlashCommandT:
        super()._ensure_assignment_on_copy(other)
        if self.connectors != other.connectors:
            other.connectors = self.connectors.copy()
        if self.autocompleters != other.autocompleters:
            other.autocompleters = self.autocompleters.copy()
        if self.children != other.children:
            other.children = self.children.copy()
            # update parents...
            for child in other.children.values():
                child.parent = other
        if self.description != other.description and "description" not in other.__original_kwargs__:
            # Allows overriding the default description cog-wide.
            other.body.description = self.description
        if self.options != other.options:
            other.body.options = self.options
        return other

    @property
    def description(self) -> str:
        """:class:`str`: The slash command's description. Shorthand for :attr:`self.body.description <.SlashCommand.description>`."""
        return self.body.description

    @property
    def options(self) -> List[Option]:
        """List[:class:`.Option`]: The list of options the slash command has. Shorthand for :attr:`self.body.options <.SlashCommand.options>`."""
        return self.body.options

    def sub_command(
        self,
        name: LocalizedOptional = None,
        description: LocalizedOptional = None,
        options: Optional[list] = None,
        connectors: Optional[dict] = None,
        extras: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Callable[[CommandCallback], SubCommand]:
        """A decorator that creates a subcommand under the base command.

        Parameters
        ----------
        name: Optional[Union[:class:`str`, :class:`.Localized`]]
            The name of the subcommand (defaults to function name).

            .. versionchanged:: 2.5
                Added support for localizations.

        description: Optional[Union[:class:`str`, :class:`.Localized`]]
            The description of the subcommand.

            .. versionchanged:: 2.5
                Added support for localizations.

        options: List[:class:`.Option`]
            the options of the subcommand for registration in API
        connectors: Dict[:class:`str`, :class:`str`]
            which function param states for each option. If the name
            of an option already matches the corresponding function param,
            you don't have to specify the connectors. Connectors template:
            ``{"option-name": "param_name", ...}``
        extras: Dict[:class:`str`, Any]
            A dict of user provided extras to attach to the subcommand.

            .. note::
                This object may be copied by the library.

            .. versionadded:: 2.5

        Returns
        -------
        Callable[..., :class:`SubCommand`]
            A decorator that converts the provided method into a :class:`SubCommand`, adds it to the bot, then returns it.
        """

        def decorator(func: CommandCallback) -> SubCommand:
            if len(self.children) == 0 and len(self.body.options) > 0:
                self.body.options = []
            new_func = SubCommand(
                func,
                self,
                name=name,
                description=description,
                options=options,
                connectors=connectors,
                extras=extras,
                **kwargs,
            )
            self.children[new_func.name] = new_func
            self.body.options.append(new_func.option)
            return new_func

        return decorator

    def sub_command_group(
        self,
        name: LocalizedOptional = None,
        extras: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Callable[[CommandCallback], SubCommandGroup]:
        """A decorator that creates a subcommand group under the base command.

        Parameters
        ----------
        name: Optional[Union[:class:`str`, :class:`.Localized`]]
            The name of the subcommand group (defaults to function name).

            .. versionchanged:: 2.5
                Added support for localizations.
        extras: Dict[:class:`str`, Any]
            A dict of user provided extras to attach to the subcommand group.

            .. note::
                This object may be copied by the library.

            .. versionadded:: 2.5

        Returns
        -------
        Callable[..., :class:`SubCommandGroup`]
            A decorator that converts the provided method into a :class:`SubCommandGroup`, adds it to the bot, then returns it.
        """

        def decorator(func: CommandCallback) -> SubCommandGroup:
            if len(self.children) == 0 and len(self.body.options) > 0:
                self.body.options = []
            new_func = SubCommandGroup(
                func,
                self,
                name=name,
                extras=extras,
                **kwargs,
            )
            self.children[new_func.name] = new_func
            self.body.options.append(new_func.option)
            return new_func

        return decorator

    def autocomplete(self, option_name: str) -> Callable[[Callable], Callable]:
        """A decorator that registers an autocomplete function for the specified option.

        Parameters
        ----------
        option_name: :class:`str`
            The name of the slash command option.
        """
        return _autocomplete(self, option_name)

    async def _call_external_error_handlers(
        self, inter: ApplicationCommandInteraction, error: CommandError
    ) -> None:
        stop_propagation = False
        cog = self.cog
        try:
            if cog is not None:
                local = _get_overridden_method(cog.cog_slash_command_error)
                if local is not None:
                    stop_propagation = await local(inter, error)
                    # User has an option to cancel the global error handler by returning True
        finally:
            if stop_propagation:
                return  # noqa: B012
            inter.bot.dispatch("slash_command_error", inter, error)

    async def _call_autocompleter(
        self, param: str, inter: ApplicationCommandInteraction, user_input: str
    ) -> Optional[Choices]:
        return await _call_autocompleter(self, param, inter, user_input)

    async def _call_relevant_autocompleter(self, inter: ApplicationCommandInteraction) -> None:
        chain, _ = inter.data._get_chain_and_kwargs()

        if len(chain) == 0:
            subcmd = None
        elif len(chain) == 1:
            subcmd = self.children.get(chain[0])
        elif len(chain) == 2:
            group = self.children.get(chain[0])
            if not isinstance(group, SubCommandGroup):
                raise AssertionError("the first subcommand is not a SubCommandGroup instance")
            subcmd = group.children.get(chain[1])
        else:
            raise ValueError("Command chain is too long")

        focused_option = inter.data.focused_option

        if subcmd is None or isinstance(subcmd, SubCommandGroup):
            call_autocompleter = self._call_autocompleter
        else:
            call_autocompleter = subcmd._call_autocompleter

        choices = await call_autocompleter(focused_option.name, inter, focused_option.value)

        if choices is not None:
            await inter.response.autocomplete(choices=choices)

    async def invoke_children(self, inter: ApplicationCommandInteraction) -> None:
        chain, kwargs = inter.data._get_chain_and_kwargs()

        if len(chain) == 0:
            group = None
            subcmd = None
        elif len(chain) == 1:
            group = None
            subcmd = self.children.get(chain[0])
        elif len(chain) == 2:
            group = self.children.get(chain[0])
            if not isinstance(group, SubCommandGroup):
                raise AssertionError("the first subcommand is not a SubCommandGroup instance")
            subcmd = group.children.get(chain[1])
        else:
            raise ValueError("Command chain is too long")

        if group is not None:
            try:
                await group.invoke(inter)
            except CommandError as exc:
                if not await group._call_local_error_handler(inter, exc):
                    raise

        if subcmd is not None:
            try:
                await subcmd.invoke(inter, **kwargs)
            except CommandError as exc:
                if not await subcmd._call_local_error_handler(inter, exc):
                    raise

    async def invoke(self, inter: ApplicationCommandInteraction) -> None:
        await self.prepare(inter)

        try:
            if len(self.children) > 0:
                await self(inter)
                await self.invoke_children(inter)
            else:
                kwargs = inter.filled_options
                for k, v in self.connectors.items():
                    if k in kwargs:
                        kwargs[v] = kwargs.pop(k)
                await call_param_func(self.callback, inter, self.cog, **kwargs)
        except CommandError:
            inter.command_failed = True
            raise
        except asyncio.CancelledError:
            inter.command_failed = True
            return
        except Exception as exc:
            inter.command_failed = True
            raise CommandInvokeError(exc) from exc
        finally:
            if self._max_concurrency is not None:
                await self._max_concurrency.release(inter)  # type: ignore

            await self.call_after_hooks(inter)


def slash_command(
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
    """A decorator that builds a slash command.

    Parameters
    ----------
    auto_sync: :class:`bool`
        Whether to automatically register the command. Defaults to ``True``.
    name: Optional[Union[:class:`str`, :class:`.Localized`]]
        The name of the slash command (defaults to function name).

        .. versionchanged:: 2.5
            Added support for localizations.

    description: Optional[Union[:class:`str`, :class:`.Localized`]]
        The description of the slash command. It will be visible in Discord.

        .. versionchanged:: 2.5
            Added support for localizations.

    nsfw: :class:`bool`
        Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
        Defaults to ``False``.

        .. versionadded:: 2.8

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
        A decorator that converts the provided method into an InvokableSlashCommand and returns it.
    """

    def decorator(func: CommandCallback) -> InvokableSlashCommand:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(f"<{func.__qualname__}> must be a coroutine function")
        if hasattr(func, "__command_flag__"):
            raise TypeError("Callback is already a command.")
        if guild_ids and not all(isinstance(guild_id, int) for guild_id in guild_ids):
            raise ValueError("guild_ids must be a sequence of int.")
        return InvokableSlashCommand(
            func,
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
        )

    return decorator
