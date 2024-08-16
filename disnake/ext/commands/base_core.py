# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import datetime
import functools
from abc import ABC
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    NamedTuple,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)

from disnake.app_commands import ApplicationCommand
from disnake.enums import ApplicationCommandType
from disnake.permissions import Permissions
from disnake.utils import _generated, _overload_with_permissions, async_all, maybe_coroutine

from .cooldowns import BucketType, CooldownMapping, MaxConcurrency
from .errors import CheckFailure, CommandError, CommandInvokeError, CommandOnCooldown

if TYPE_CHECKING:
    from typing_extensions import Concatenate, ParamSpec, Self

    from disnake.interactions import ApplicationCommandInteraction

    from ._types import AppCheck, Coro, Error, Hook
    from .cog import Cog

    ApplicationCommandInteractionT = TypeVar(
        "ApplicationCommandInteractionT", bound=ApplicationCommandInteraction, covariant=True
    )

    P = ParamSpec("P")

    CommandCallback = Callable[..., Coro[Any]]
    InteractionCommandCallback = Union[
        Callable[Concatenate["CogT", ApplicationCommandInteractionT, P], Coro[Any]],
        Callable[Concatenate[ApplicationCommandInteractionT, P], Coro[Any]],
    ]


__all__ = ("AppCmdIndex", "InvokableApplicationCommand", "default_member_permissions")


T = TypeVar("T")
AppCommandT = TypeVar("AppCommandT", bound="InvokableApplicationCommand")
CogT = TypeVar("CogT", bound="Cog")
HookT = TypeVar("HookT", bound="Hook")
ErrorT = TypeVar("ErrorT", bound="Error")


def _get_overridden_method(method):
    return getattr(method.__func__, "__cog_special_method__", method)


def wrap_callback(coro):
    @functools.wraps(coro)
    async def wrapped(*args, **kwargs):
        try:
            ret = await coro(*args, **kwargs)
        except CommandError:
            raise
        except asyncio.CancelledError:
            return
        except Exception as exc:
            raise CommandInvokeError(exc) from exc
        return ret

    return wrapped


class AppCmdIndex(NamedTuple):
    """A named tuple used for indexation of :class:`InvokableApplicationCommand`
    objects stored in bot's cache.

    Attributes
    ----------
    type: :class:`disnake.ApplicationCommandType`
        The type of the application command being stored.
    name: :class:`str`
        The name of the application command being stored.
    guild_id: Optional[:class:`int`]
        One of the guild IDs this command should be registered to,
        or ``None`` if it's a global command.
    """

    type: ApplicationCommandType
    name: str
    guild_id: Optional[int]


class InvokableApplicationCommand(ABC):
    """A base class that implements the protocol for a bot application command.

    These are not created manually, instead they are created via the
    decorator or functional interface.

    The following classes implement this ABC:

    - :class:`~.InvokableSlashCommand`
    - :class:`~.InvokableMessageCommand`
    - :class:`~.InvokableUserCommand`

    Attributes
    ----------
    name: :class:`str`
        The name of the command.
    qualified_name: :class:`str`
        The full command name, including parent names in the case of slash subcommands or groups.
        For example, the qualified name for ``/one two three`` would be ``one two three``.
    body: :class:`.ApplicationCommand`
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
    auto_sync: :class:`bool`
        Whether to automatically register the command.
    extras: Dict[:class:`str`, Any]
        A dict of user provided extras to attach to the command.

        .. versionadded:: 2.5
    """

    __original_kwargs__: Dict[str, Any]
    body: ApplicationCommand

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        self = super().__new__(cls)
        # todo: refactor to not require None and change this to be based on the presence of a kwarg
        self.__original_kwargs__ = {k: v for k, v in kwargs.items() if v is not None}
        return self

    def __init__(self, func: CommandCallback, *, name: Optional[str] = None, **kwargs: Any) -> None:
        self.__command_flag__ = None
        self._callback: CommandCallback = func
        self.name: str = name or func.__name__
        self.qualified_name: str = self.name
        # Annotation parser needs this attribute because body doesn't exist at this moment.
        # We will use this attribute later in order to set the dm_permission.
        self._guild_only: bool = kwargs.get("guild_only", False)
        self.extras: Dict[str, Any] = kwargs.get("extras") or {}

        if not isinstance(self.name, str):
            raise TypeError("Name of a command must be a string.")

        if "default_permission" in kwargs:
            raise TypeError(
                "`default_permission` is deprecated and will always be set to `True`. "
                "See `default_member_permissions` and `dm_permission` instead."
            )

        try:
            checks = func.__commands_checks__
            checks.reverse()
        except AttributeError:
            checks = kwargs.get("checks", [])

        self.checks: List[AppCheck] = checks

        try:
            cooldown = func.__commands_cooldown__
        except AttributeError:
            cooldown = kwargs.get("cooldown")

        # TODO: Figure out how cooldowns even work with interactions
        if cooldown is None:
            buckets = CooldownMapping(cooldown, BucketType.default)
        elif isinstance(cooldown, CooldownMapping):
            buckets = cooldown
        else:
            raise TypeError("Cooldown must be a an instance of CooldownMapping or None.")
        self._buckets: CooldownMapping = buckets

        try:
            max_concurrency = func.__commands_max_concurrency__
        except AttributeError:
            max_concurrency = kwargs.get("max_concurrency")
        self._max_concurrency: Optional[MaxConcurrency] = max_concurrency

        self.cog: Optional[Cog] = None
        self.guild_ids: Optional[Tuple[int, ...]] = None
        self.auto_sync: bool = True

        self._before_invoke: Optional[Hook] = None
        self._after_invoke: Optional[Hook] = None

    def _ensure_assignment_on_copy(self, other: AppCommandT) -> AppCommandT:
        other._before_invoke = self._before_invoke
        other._after_invoke = self._after_invoke
        if self.checks != other.checks:
            other.checks = self.checks.copy()
        if self._buckets.valid and not other._buckets.valid:
            other._buckets = self._buckets.copy()
        if self._max_concurrency != other._max_concurrency:
            # _max_concurrency won't be None at this point
            other._max_concurrency = cast(MaxConcurrency, self._max_concurrency).copy()

        if self.body._default_member_permissions != other.body._default_member_permissions and (
            "default_member_permissions" not in other.__original_kwargs__
            or self.body._default_member_permissions is not None
        ):
            other.body._default_member_permissions = self.body._default_member_permissions

        try:
            other.on_error = self.on_error
        except AttributeError:
            pass

        return other

    def copy(self: AppCommandT) -> AppCommandT:
        """Create a copy of this application command.

        Returns
        -------
        :class:`InvokableApplicationCommand`
            A new instance of this application command.
        """
        copy = type(self)(self.callback, **self.__original_kwargs__)
        return self._ensure_assignment_on_copy(copy)

    def _update_copy(self: AppCommandT, kwargs: Dict[str, Any]) -> AppCommandT:
        if kwargs:
            kw = kwargs.copy()
            kw.update(self.__original_kwargs__)
            copy = type(self)(self.callback, **kw)
            return self._ensure_assignment_on_copy(copy)
        else:
            return self.copy()

    @property
    def dm_permission(self) -> bool:
        """:class:`bool`: Whether this command can be used in DMs."""
        return self.body.dm_permission

    @property
    def default_member_permissions(self) -> Optional[Permissions]:
        """Optional[:class:`.Permissions`]: The default required member permissions for this command.
        A member must have *all* these permissions to be able to invoke the command in a guild.

        This is a default value, the set of users/roles that may invoke this command can be
        overridden by moderators on a guild-specific basis, disregarding this setting.

        If ``None`` is returned, it means everyone can use the command by default.
        If an empty :class:`.Permissions` object is returned (that is, all permissions set to ``False``),
        this means no one can use the command.

        .. versionadded:: 2.5
        """
        return self.body.default_member_permissions

    @property
    def callback(self) -> CommandCallback:
        return self._callback

    def add_check(self, func: AppCheck) -> None:
        """Adds a check to the application command.

        This is the non-decorator interface to :func:`.app_check`.

        Parameters
        ----------
        func
            The function that will be used as a check.
        """
        self.checks.append(func)

    def remove_check(self, func: AppCheck) -> None:
        """Removes a check from the application command.

        This function is idempotent and will not raise an exception
        if the function is not in the command's checks.

        Parameters
        ----------
        func
            The function to remove from the checks.
        """
        try:
            self.checks.remove(func)
        except ValueError:
            pass

    async def __call__(
        self, interaction: ApplicationCommandInteraction, *args: Any, **kwargs: Any
    ) -> Any:
        """|coro|

        Calls the internal callback that the application command holds.

        .. note::

            This bypasses all mechanisms -- including checks, converters,
            invoke hooks, cooldowns, etc. You must take care to pass
            the proper arguments and types to this function.

        """
        if self.cog is not None:
            return await self.callback(self.cog, interaction, *args, **kwargs)
        else:
            return await self.callback(interaction, *args, **kwargs)

    def _prepare_cooldowns(self, inter: ApplicationCommandInteraction) -> None:
        if self._buckets.valid:
            dt = inter.created_at
            current = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
            bucket = self._buckets.get_bucket(inter, current)  # type: ignore
            if bucket is not None:  # pyright: ignore[reportUnnecessaryComparison]
                retry_after = bucket.update_rate_limit(current)
                if retry_after:
                    raise CommandOnCooldown(bucket, retry_after, self._buckets.type)  # type: ignore

    async def prepare(self, inter: ApplicationCommandInteraction) -> None:
        inter.application_command = self

        if not await self.can_run(inter):
            raise CheckFailure(f"The check functions for command {self.qualified_name!r} failed.")

        if self._max_concurrency is not None:
            await self._max_concurrency.acquire(inter)  # type: ignore

        try:
            self._prepare_cooldowns(inter)
            await self.call_before_hooks(inter)
        except Exception:
            if self._max_concurrency is not None:
                await self._max_concurrency.release(inter)  # type: ignore
            raise

    def is_on_cooldown(self, inter: ApplicationCommandInteraction) -> bool:
        """Checks whether the application command is currently on cooldown.

        Parameters
        ----------
        inter: :class:`.ApplicationCommandInteraction`
            The interaction with the application command currently being invoked.

        Returns
        -------
        :class:`bool`
            A boolean indicating if the application command is on cooldown.
        """
        if not self._buckets.valid:
            return False

        bucket = self._buckets.get_bucket(inter)  # type: ignore
        dt = inter.created_at
        current = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
        return bucket.get_tokens(current) == 0

    def reset_cooldown(self, inter: ApplicationCommandInteraction) -> None:
        """Resets the cooldown on this application command.

        Parameters
        ----------
        inter: :class:`.ApplicationCommandInteraction`
            The interaction with this application command
        """
        if self._buckets.valid:
            bucket = self._buckets.get_bucket(inter)  # type: ignore
            bucket.reset()

    def get_cooldown_retry_after(self, inter: ApplicationCommandInteraction) -> float:
        """Retrieves the amount of seconds before this application command can be tried again.

        Parameters
        ----------
        inter: :class:`.ApplicationCommandInteraction`
            The interaction with this application command.

        Returns
        -------
        :class:`float`
            The amount of time left on this command's cooldown in seconds.
            If this is ``0.0`` then the command isn't on cooldown.
        """
        if self._buckets.valid:
            bucket = self._buckets.get_bucket(inter)  # type: ignore
            dt = inter.created_at
            current = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
            return bucket.get_retry_after(current)

        return 0.0

    # This method isn't really usable in this class, but it's usable in subclasses.
    async def invoke(self, inter: ApplicationCommandInteraction, *args: Any, **kwargs: Any) -> None:
        await self.prepare(inter)

        try:
            await self(inter, *args, **kwargs)
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

    def error(self, coro: ErrorT) -> ErrorT:
        """A decorator that registers a coroutine as a local error handler.

        A local error handler is an error event limited to a single application command.

        Parameters
        ----------
        coro: :ref:`coroutine <coroutine>`
            The coroutine to register as the local error handler.

        Raises
        ------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError("The error handler must be a coroutine.")

        self.on_error: Error = coro
        return coro

    def has_error_handler(self) -> bool:
        """Checks whether the application command has an error handler registered."""
        return hasattr(self, "on_error")

    async def _call_local_error_handler(
        self, inter: ApplicationCommandInteraction, error: CommandError
    ) -> Any:
        if not self.has_error_handler():
            return

        injected = wrap_callback(self.on_error)
        if self.cog is not None:
            return await injected(self.cog, inter, error)
        else:
            return await injected(inter, error)

    async def _call_external_error_handlers(
        self, inter: ApplicationCommandInteraction, error: CommandError
    ) -> None:
        """Overridden in subclasses"""
        raise error

    async def dispatch_error(
        self, inter: ApplicationCommandInteraction, error: CommandError
    ) -> None:
        if not await self._call_local_error_handler(inter, error):
            await self._call_external_error_handlers(inter, error)

    async def call_before_hooks(self, inter: ApplicationCommandInteraction) -> None:
        # now that we're done preparing we can call the pre-command hooks
        # first, call the command local hook:
        cog = self.cog
        if self._before_invoke is not None:
            # should be cog if @commands.before_invoke is used
            instance = getattr(self._before_invoke, "__self__", cog)
            # __self__ only exists for methods, not functions
            # however, if @command.before_invoke is used, it will be a function
            if instance:
                await self._before_invoke(instance, inter)  # type: ignore
            else:
                await self._before_invoke(inter)  # type: ignore

        if inter.data.type is ApplicationCommandType.chat_input:
            partial_attr_name = "slash_command"
        elif inter.data.type is ApplicationCommandType.user:
            partial_attr_name = "user_command"
        elif inter.data.type is ApplicationCommandType.message:
            partial_attr_name = "message_command"
        else:
            return

        # call the cog local hook if applicable:
        if cog is not None:
            meth = getattr(cog, f"cog_before_{partial_attr_name}_invoke", None)
            hook = _get_overridden_method(meth)
            if hook is not None:
                await hook(inter)

        # call the bot global hook if necessary
        hook = getattr(inter.bot, f"_before_{partial_attr_name}_invoke", None)
        if hook is not None:
            await hook(inter)

    async def call_after_hooks(self, inter: ApplicationCommandInteraction) -> None:
        cog = self.cog
        if self._after_invoke is not None:
            instance = getattr(self._after_invoke, "__self__", cog)
            if instance:
                await self._after_invoke(instance, inter)  # type: ignore
            else:
                await self._after_invoke(inter)  # type: ignore

        if inter.data.type is ApplicationCommandType.chat_input:
            partial_attr_name = "slash_command"
        elif inter.data.type is ApplicationCommandType.user:
            partial_attr_name = "user_command"
        elif inter.data.type is ApplicationCommandType.message:
            partial_attr_name = "message_command"
        else:
            return

        # call the cog local hook if applicable:
        if cog is not None:
            meth = getattr(cog, f"cog_after_{partial_attr_name}_invoke", None)
            hook = _get_overridden_method(meth)
            if hook is not None:
                await hook(inter)

        # call the bot global hook if necessary
        hook = getattr(inter.bot, f"_after_{partial_attr_name}_invoke", None)
        if hook is not None:
            await hook(inter)

    def before_invoke(self, coro: HookT) -> HookT:
        """A decorator that registers a coroutine as a pre-invoke hook.

        A pre-invoke hook is called directly before the command is called.

        This pre-invoke hook takes a sole parameter, a :class:`.ApplicationCommandInteraction`.

        Parameters
        ----------
        coro: :ref:`coroutine <coroutine>`
            The coroutine to register as the pre-invoke hook.

        Raises
        ------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError("The pre-invoke hook must be a coroutine.")

        self._before_invoke = coro
        return coro

    def after_invoke(self, coro: HookT) -> HookT:
        """A decorator that registers a coroutine as a post-invoke hook.

        A post-invoke hook is called directly after the command is called.

        This post-invoke hook takes a sole parameter, a :class:`.ApplicationCommandInteraction`.

        Parameters
        ----------
        coro: :ref:`coroutine <coroutine>`
            The coroutine to register as the post-invoke hook.

        Raises
        ------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError("The post-invoke hook must be a coroutine.")

        self._after_invoke = coro
        return coro

    @property
    def cog_name(self) -> Optional[str]:
        """Optional[:class:`str`]: The name of the cog this application command belongs to, if any."""
        return type(self.cog).__cog_name__ if self.cog is not None else None

    async def can_run(self, inter: ApplicationCommandInteraction) -> bool:
        """|coro|

        Checks if the command can be executed by checking all the predicates
        inside the :attr:`~Command.checks` attribute.

        Parameters
        ----------
        inter: :class:`.ApplicationCommandInteraction`
            The interaction with the application command currently being invoked.

        Raises
        ------
        :class:`CommandError`
            Any application command error that was raised during a check call will be propagated
            by this function.

        Returns
        -------
        :class:`bool`
            A boolean indicating if the application command can be invoked.
        """
        original = inter.application_command
        inter.application_command = self

        if inter.data.type is ApplicationCommandType.chat_input:
            partial_attr_name = "slash_command"
        elif inter.data.type is ApplicationCommandType.user:
            partial_attr_name = "user_command"
        elif inter.data.type is ApplicationCommandType.message:
            partial_attr_name = "message_command"
        else:
            return True

        try:
            if inter.bot and not await inter.bot.application_command_can_run(inter):
                raise CheckFailure(
                    f"The global check functions for command {self.qualified_name} failed."
                )

            cog = self.cog
            if cog is not None:
                meth = getattr(cog, f"cog_{partial_attr_name}_check", None)
                local_check = _get_overridden_method(meth)
                if local_check is not None:
                    ret = await maybe_coroutine(local_check, inter)
                    if not ret:
                        return False

            predicates = self.checks
            if not predicates:
                # since we have no checks, then we just return True.
                return True

            return await async_all(predicate(inter) for predicate in predicates)  # type: ignore
        finally:
            inter.application_command = original


@overload
@_generated
def default_member_permissions(
    value: int = 0,
    *,
    add_reactions: bool = ...,
    administrator: bool = ...,
    attach_files: bool = ...,
    ban_members: bool = ...,
    change_nickname: bool = ...,
    connect: bool = ...,
    create_events: bool = ...,
    create_forum_threads: bool = ...,
    create_guild_expressions: bool = ...,
    create_instant_invite: bool = ...,
    create_private_threads: bool = ...,
    create_public_threads: bool = ...,
    deafen_members: bool = ...,
    embed_links: bool = ...,
    external_emojis: bool = ...,
    external_stickers: bool = ...,
    kick_members: bool = ...,
    manage_channels: bool = ...,
    manage_emojis: bool = ...,
    manage_emojis_and_stickers: bool = ...,
    manage_events: bool = ...,
    manage_guild: bool = ...,
    manage_guild_expressions: bool = ...,
    manage_messages: bool = ...,
    manage_nicknames: bool = ...,
    manage_permissions: bool = ...,
    manage_roles: bool = ...,
    manage_threads: bool = ...,
    manage_webhooks: bool = ...,
    mention_everyone: bool = ...,
    moderate_members: bool = ...,
    move_members: bool = ...,
    mute_members: bool = ...,
    priority_speaker: bool = ...,
    read_message_history: bool = ...,
    read_messages: bool = ...,
    request_to_speak: bool = ...,
    send_messages: bool = ...,
    send_messages_in_threads: bool = ...,
    send_tts_messages: bool = ...,
    send_voice_messages: bool = ...,
    speak: bool = ...,
    start_embedded_activities: bool = ...,
    stream: bool = ...,
    use_application_commands: bool = ...,
    use_embedded_activities: bool = ...,
    use_external_apps: bool = ...,
    use_external_emojis: bool = ...,
    use_external_sounds: bool = ...,
    use_external_stickers: bool = ...,
    use_slash_commands: bool = ...,
    use_soundboard: bool = ...,
    use_voice_activation: bool = ...,
    view_audit_log: bool = ...,
    view_channel: bool = ...,
    view_creator_monetization_analytics: bool = ...,
    view_guild_insights: bool = ...,
) -> Callable[[T], T]:
    ...


@overload
@_generated
def default_member_permissions(
    value: int = 0,
) -> Callable[[T], T]:
    ...


@_overload_with_permissions
def default_member_permissions(value: int = 0, **permissions: bool) -> Callable[[T], T]:
    """A decorator that sets default required member permissions for the command.
    Unlike :func:`~.has_permissions`, this decorator does not add any checks.
    Instead, it prevents the command from being run by members without *all* required permissions,
    if not overridden by moderators on a guild-specific basis.

    See also the ``default_member_permissions`` parameter for application command decorators.

    .. note::
        This does not work with slash subcommands/groups.

    Example
    -------

    This would only allow members with :attr:`~.Permissions.manage_messages` *and*
    :attr:`~.Permissions.view_audit_log` permissions to use the command by default,
    however moderators can override this and allow/disallow specific users and
    roles to use the command in their guilds regardless of this setting.

    .. code-block:: python3

        @bot.slash_command()
        @commands.default_member_permissions(manage_messages=True, view_audit_log=True)
        async def purge(inter, num: int):
            ...

    Parameters
    ----------
    value: :class:`int`
        A raw permission bitfield of an integer representing the required permissions.
        May be used instead of specifying kwargs.
    **permissions: bool
        The required permissions for a command. A member must have *all* these
        permissions to be able to invoke the command.
        Setting a permission to ``False`` does not affect the result.
    """
    if isinstance(value, bool):
        raise TypeError("`value` cannot be a bool value")
    perms_value = Permissions(value, **permissions).value

    def decorator(func: T) -> T:
        from .slash_core import SubCommand, SubCommandGroup

        if isinstance(func, InvokableApplicationCommand):
            if isinstance(func, (SubCommand, SubCommandGroup)):
                raise TypeError(
                    "Cannot set `default_member_permissions` on subcommands or subcommand groups"
                )
            if func.body._default_member_permissions is not None:
                raise ValueError(
                    "Cannot set `default_member_permissions` in both parameter and decorator"
                )
            func.body._default_member_permissions = perms_value
        else:
            func.__default_member_permissions__ = perms_value  # type: ignore
        return func

    return decorator
