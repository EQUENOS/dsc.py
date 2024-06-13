# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

import disnake
import disnake.utils
from disnake.enums import Event

from ._types import _BaseCommand
from .base_core import InvokableApplicationCommand
from .ctx_menus_core import InvokableMessageCommand, InvokableUserCommand
from .slash_core import InvokableSlashCommand

if TYPE_CHECKING:
    from typing_extensions import Self

    from disnake.interactions import ApplicationCommandInteraction

    from ._types import FuncT
    from .bot import AutoShardedBot, AutoShardedInteractionBot, Bot, InteractionBot
    from .context import Context
    from .core import Command

    AnyBot = Union[Bot, AutoShardedBot, InteractionBot, AutoShardedInteractionBot]


__all__ = (
    "CogMeta",
    "Cog",
)

MISSING: Any = disnake.utils.MISSING
_log = logging.getLogger(__name__)


def _cog_special_method(func: FuncT) -> FuncT:
    func.__cog_special_method__ = None
    return func


class CogMeta(type):
    """A metaclass for defining a cog.

    Note that you should probably not use this directly. It is exposed
    purely for documentation purposes along with making custom metaclasses to intermix
    with other metaclasses such as the :class:`abc.ABCMeta` metaclass.

    For example, to create an abstract cog mixin class, the following would be done.

    .. code-block:: python3

        import abc

        class CogABCMeta(commands.CogMeta, abc.ABCMeta):
            pass

        class SomeMixin(metaclass=abc.ABCMeta):
            pass

        class SomeCogMixin(SomeMixin, commands.Cog, metaclass=CogABCMeta):
            pass

    .. note::

        When passing an attribute of a metaclass that is documented below, note
        that you must pass it as a keyword-only argument to the class creation
        like the following example:

        .. code-block:: python3

            class MyCog(commands.Cog, name='My Cog'):
                pass

    Attributes
    ----------
    name: :class:`str`
        The cog name. By default, it is the name of the class with no modification.
    description: :class:`str`
        The cog description. By default, it is the cleaned docstring of the class.

        .. versionadded:: 1.6

    command_attrs: Dict[:class:`str`, Any]
        A list of attributes to apply to every command inside this cog. The dictionary
        is passed into the :class:`Command` options at ``__init__``.
        If you specify attributes inside the command attribute in the class, it will
        override the one specified inside this attribute. For example:

        .. code-block:: python3

            class MyCog(commands.Cog, command_attrs=dict(hidden=True)):
                @commands.command()
                async def foo(self, ctx):
                    pass # hidden -> True

                @commands.command(hidden=False)
                async def bar(self, ctx):
                    pass # hidden -> False

    slash_command_attrs: Dict[:class:`str`, Any]
        A list of attributes to apply to every slash command inside this cog. The dictionary
        is passed into the options of every :class:`InvokableSlashCommand` at ``__init__``.
        Usage of this kwarg is otherwise the same as with ``command_attrs``.

        .. note:: This does not apply to instances of :class:`SubCommand` or :class:`SubCommandGroup`.

        .. versionadded:: 2.5

    user_command_attrs: Dict[:class:`str`, Any]
        A list of attributes to apply to every user command inside this cog. The dictionary
        is passed into the options of every :class:`InvokableUserCommand` at ``__init__``.
        Usage of this kwarg is otherwise the same as with ``command_attrs``.

        .. versionadded:: 2.5

    message_command_attrs: Dict[:class:`str`, Any]
        A list of attributes to apply to every message command inside this cog. The dictionary
        is passed into the options of every :class:`InvokableMessageCommand` at ``__init__``.
        Usage of this kwarg is otherwise the same as with ``command_attrs``.

        .. versionadded:: 2.5
    """

    __cog_name__: str
    __cog_settings__: Dict[str, Any]
    __cog_slash_settings__: Dict[str, Any]
    __cog_user_settings__: Dict[str, Any]
    __cog_message_settings__: Dict[str, Any]
    __cog_commands__: List[Command]
    __cog_app_commands__: List[InvokableApplicationCommand]
    __cog_listeners__: List[Tuple[str, str]]

    def __new__(cls: Type[CogMeta], *args: Any, **kwargs: Any) -> CogMeta:
        name, bases, attrs = args
        attrs["__cog_name__"] = kwargs.pop("name", name)
        attrs["__cog_settings__"] = kwargs.pop("command_attrs", {})
        attrs["__cog_slash_settings__"] = kwargs.pop("slash_command_attrs", {})
        attrs["__cog_user_settings__"] = kwargs.pop("user_command_attrs", {})
        attrs["__cog_message_settings__"] = kwargs.pop("message_command_attrs", {})

        description = kwargs.pop("description", None)
        if description is None:
            description = inspect.cleandoc(attrs.get("__doc__", ""))
        attrs["__cog_description__"] = description

        commands = {}
        app_commands = {}
        listeners = {}
        no_bot_cog = (
            "Commands or listeners must not start with cog_ or bot_ (in method {0.__name__}.{1})"
        )

        new_cls = super().__new__(cls, name, bases, attrs, **kwargs)
        for base in reversed(new_cls.__mro__):
            for elem, value in base.__dict__.items():
                if elem in commands:
                    del commands[elem]
                if elem in app_commands:
                    del app_commands[elem]
                if elem in listeners:
                    del listeners[elem]

                is_static_method = isinstance(value, staticmethod)
                if is_static_method:
                    value = value.__func__
                if isinstance(value, _BaseCommand):
                    if is_static_method:
                        raise TypeError(
                            f"Command in method {base}.{elem!r} must not be staticmethod."
                        )
                    if elem.startswith(("cog_", "bot_")):
                        raise TypeError(no_bot_cog.format(base, elem))
                    commands[elem] = value
                elif isinstance(value, InvokableApplicationCommand):
                    if is_static_method:
                        raise TypeError(
                            f"Application command in method {base}.{elem!r} must not be staticmethod."
                        )
                    if elem.startswith(("cog_", "bot_")):
                        raise TypeError(no_bot_cog.format(base, elem))
                    app_commands[elem] = value
                elif asyncio.iscoroutinefunction(value):
                    if hasattr(value, "__cog_listener__"):
                        if elem.startswith(("cog_", "bot_")):
                            raise TypeError(no_bot_cog.format(base, elem))
                        listeners[elem] = value

        new_cls.__cog_commands__ = list(commands.values())  # this will be copied in Cog.__new__
        new_cls.__cog_app_commands__ = list(app_commands.values())

        listeners_as_list = []
        for listener in listeners.values():
            for listener_name in listener.__cog_listener_names__:
                # I use __name__ instead of just storing the value so I can inject
                # the self attribute when the time comes to add them to the bot
                listeners_as_list.append((listener_name, listener.__name__))

        new_cls.__cog_listeners__ = listeners_as_list
        return new_cls

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args)

    @classmethod
    def qualified_name(cls) -> str:
        return cls.__cog_name__


class Cog(metaclass=CogMeta):
    """The base class that all cogs must inherit from.

    A cog is a collection of commands, listeners, and optional state to
    help group commands together. More information on them can be found on
    the :ref:`ext_commands_cogs` page.

    When inheriting from this class, the options shown in :class:`CogMeta`
    are equally valid here.
    """

    __cog_name__: ClassVar[str]
    __cog_settings__: ClassVar[Dict[str, Any]]
    __cog_commands__: ClassVar[List[Command]]
    __cog_app_commands__: ClassVar[List[InvokableApplicationCommand]]
    __cog_listeners__: ClassVar[List[Tuple[str, str]]]

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        # For issue 426, we need to store a copy of the command objects
        # since we modify them to inject `self` to them.
        # To do this, we need to interfere with the Cog creation process.
        self = super().__new__(cls)
        cmd_attrs = cls.__cog_settings__
        slash_cmd_attrs = cls.__cog_slash_settings__
        user_cmd_attrs = cls.__cog_user_settings__
        message_cmd_attrs = cls.__cog_message_settings__

        # Either update the command with the cog provided defaults or copy it.
        cog_app_commands: List[InvokableApplicationCommand] = []
        for c in cls.__cog_app_commands__:
            if isinstance(c, InvokableSlashCommand):
                c = c._update_copy(slash_cmd_attrs)
            elif isinstance(c, InvokableUserCommand):
                c = c._update_copy(user_cmd_attrs)
            elif isinstance(c, InvokableMessageCommand):
                c = c._update_copy(message_cmd_attrs)

            cog_app_commands.append(c)

        self.__cog_app_commands__ = tuple(cog_app_commands)  # type: ignore  # overriding ClassVar
        # Replace the old command objects with the new copies
        for app_command in self.__cog_app_commands__:
            setattr(self, app_command.callback.__name__, app_command)

        self.__cog_commands__ = tuple(c._update_copy(cmd_attrs) for c in cls.__cog_commands__)  # type: ignore  # overriding ClassVar

        lookup = {cmd.qualified_name: cmd for cmd in self.__cog_commands__}
        for command in self.__cog_commands__:
            setattr(self, command.callback.__name__, command)
            parent = command.parent
            if parent is not None:
                # Get the latest parent reference
                parent = lookup[parent.qualified_name]  # type: ignore

                # Update our parent's reference to our self
                parent.remove_command(command.name)  # type: ignore
                parent.add_command(command)  # type: ignore

        return self

    def get_commands(self) -> List[Command]:
        """Returns a list of commands the cog has.

        Returns
        -------
        List[:class:`.Command`]
            A :class:`list` of :class:`.Command`\\s that are
            defined inside this cog.

            .. note::

                This does not include subcommands.
        """
        return [c for c in self.__cog_commands__ if c.parent is None]

    def get_application_commands(self) -> List[InvokableApplicationCommand]:
        """Returns a list of application commands the cog has.

        Returns
        -------
        List[:class:`.InvokableApplicationCommand`]
            A :class:`list` of :class:`.InvokableApplicationCommand`\\s that are
            defined inside this cog.

            .. note::

                This does not include subcommands.
        """
        return list(self.__cog_app_commands__)

    def get_slash_commands(self) -> List[InvokableSlashCommand]:
        """Returns a list of slash commands the cog has.

        Returns
        -------
        List[:class:`.InvokableSlashCommand`]
            A :class:`list` of :class:`.InvokableSlashCommand`\\s that are
            defined inside this cog.

            .. note::

                This does not include subcommands.
        """
        return [c for c in self.__cog_app_commands__ if isinstance(c, InvokableSlashCommand)]

    def get_user_commands(self) -> List[InvokableUserCommand]:
        """Returns a list of user commands the cog has.

        Returns
        -------
        List[:class:`.InvokableUserCommand`]
            A :class:`list` of :class:`.InvokableUserCommand`\\s that are
            defined inside this cog.
        """
        return [c for c in self.__cog_app_commands__ if isinstance(c, InvokableUserCommand)]

    def get_message_commands(self) -> List[InvokableMessageCommand]:
        """Returns a list of message commands the cog has.

        Returns
        -------
        List[:class:`.InvokableMessageCommand`]
            A :class:`list` of :class:`.InvokableMessageCommand`\\s that are
            defined inside this cog.
        """
        return [c for c in self.__cog_app_commands__ if isinstance(c, InvokableMessageCommand)]

    @property
    def qualified_name(self) -> str:
        """:class:`str`: Returns the cog's specified name, not the class name."""
        return self.__cog_name__

    @property
    def description(self) -> str:
        """:class:`str`: Returns the cog's description, typically the cleaned docstring."""
        return self.__cog_description__

    @description.setter
    def description(self, description: str) -> None:
        self.__cog_description__ = description

    def walk_commands(self) -> Generator[Command, None, None]:
        """An iterator that recursively walks through this cog's commands and subcommands.

        Yields
        ------
        Union[:class:`.Command`, :class:`.Group`]
            A command or group from the cog.
        """
        from .core import GroupMixin

        for command in self.__cog_commands__:
            if command.parent is None:
                yield command
                if isinstance(command, GroupMixin):
                    yield from command.walk_commands()

    def get_listeners(self) -> List[Tuple[str, Callable[..., Any]]]:
        """Returns a :class:`list` of (name, function) listener pairs the cog has.

        Returns
        -------
        List[Tuple[:class:`str`, :ref:`coroutine <coroutine>`]]
            The listeners defined in this cog.
        """
        return [(name, getattr(self, method_name)) for name, method_name in self.__cog_listeners__]

    @classmethod
    def _get_overridden_method(cls, method: FuncT) -> Optional[FuncT]:
        """Return None if the method is not overridden. Otherwise returns the overridden method."""
        return getattr(method.__func__, "__cog_special_method__", method)

    @classmethod
    def listener(cls, name: Union[str, Event] = MISSING) -> Callable[[FuncT], FuncT]:
        """A decorator that marks a function as a listener.

        This is the cog equivalent of :meth:`.Bot.listen`.

        Parameters
        ----------
        name: Union[:class:`str`, :class:`.Event`]
            The name of the event being listened to. If not provided, it
            defaults to the function's name.

        Raises
        ------
        TypeError
            The function is not a coroutine function or a string or an :class:`.Event` enum member was not passed as
            the name.
        """
        if name is not MISSING and not isinstance(name, (str, Event)):
            raise TypeError(
                f"Cog.listener expected str or Enum but received {name.__class__.__name__!r} instead."
            )

        def decorator(func: FuncT) -> FuncT:
            actual = func
            if isinstance(actual, staticmethod):
                actual = actual.__func__
            if not asyncio.iscoroutinefunction(actual):
                raise TypeError("Listener function must be a coroutine function.")
            actual.__cog_listener__ = True
            to_assign = (
                actual.__name__
                if name is MISSING
                else (name if isinstance(name, str) else f"on_{name.value}")
            )
            try:
                actual.__cog_listener_names__.append(to_assign)
            except AttributeError:
                actual.__cog_listener_names__ = [to_assign]
            # we have to return `func` instead of `actual` because
            # we need the type to be `staticmethod` for the metaclass
            # to pick it up but the metaclass unfurls the function and
            # thus the assignments need to be on the actual function
            return func

        return decorator

    def has_error_handler(self) -> bool:
        """Whether the cog has an error handler.

        .. versionadded:: 1.7

        :return type: :class:`bool`
        """
        return not hasattr(self.cog_command_error.__func__, "__cog_special_method__")

    def has_slash_error_handler(self) -> bool:
        """Whether the cog has a slash command error handler.

        :return type: :class:`bool`
        """
        return not hasattr(self.cog_slash_command_error.__func__, "__cog_special_method__")

    def has_user_error_handler(self) -> bool:
        """Whether the cog has a user command error handler.

        :return type: :class:`bool`
        """
        return not hasattr(self.cog_user_command_error.__func__, "__cog_special_method__")

    def has_message_error_handler(self) -> bool:
        """Whether the cog has a message command error handler.

        :return type: :class:`bool`
        """
        return not hasattr(self.cog_message_command_error.__func__, "__cog_special_method__")

    @_cog_special_method
    async def cog_load(self) -> None:
        """A special method that is called as a task when the cog is added."""
        pass

    @_cog_special_method
    def cog_unload(self) -> None:
        """A special method that is called when the cog gets removed.

        This function **cannot** be a coroutine. It must be a regular
        function.

        Subclasses must replace this if they want special unloading behaviour.
        """
        pass

    @_cog_special_method
    def bot_check_once(self, ctx: Context) -> bool:
        """A special method that registers as a :meth:`.Bot.check_once`
        check.

        This is for text commands only, and doesn't apply to application commands.

        This function **can** be a coroutine and must take a sole parameter,
        ``ctx``, to represent the :class:`.Context`.
        """
        return True

    @_cog_special_method
    def bot_check(self, ctx: Context) -> bool:
        """A special method that registers as a :meth:`.Bot.check`
        check.

        This is for text commands only, and doesn't apply to application commands.

        This function **can** be a coroutine and must take a sole parameter,
        ``ctx``, to represent the :class:`.Context`.
        """
        return True

    @_cog_special_method
    def bot_slash_command_check_once(self, inter: ApplicationCommandInteraction) -> bool:
        """A special method that registers as a :meth:`.Bot.slash_command_check_once`
        check.

        This function **can** be a coroutine and must take a sole parameter,
        ``inter``, to represent the :class:`.ApplicationCommandInteraction`.
        """
        return True

    @_cog_special_method
    def bot_slash_command_check(self, inter: ApplicationCommandInteraction) -> bool:
        """A special method that registers as a :meth:`.Bot.slash_command_check`
        check.

        This function **can** be a coroutine and must take a sole parameter,
        ``inter``, to represent the :class:`.ApplicationCommandInteraction`.
        """
        return True

    @_cog_special_method
    def bot_user_command_check_once(self, inter: ApplicationCommandInteraction) -> bool:
        """Similar to :meth:`.Bot.slash_command_check_once` but for user commands."""
        return True

    @_cog_special_method
    def bot_user_command_check(self, inter: ApplicationCommandInteraction) -> bool:
        """Similar to :meth:`.Bot.slash_command_check` but for user commands."""
        return True

    @_cog_special_method
    def bot_message_command_check_once(self, inter: ApplicationCommandInteraction) -> bool:
        """Similar to :meth:`.Bot.slash_command_check_once` but for message commands."""
        return True

    @_cog_special_method
    def bot_message_command_check(self, inter: ApplicationCommandInteraction) -> bool:
        """Similar to :meth:`.Bot.slash_command_check` but for message commands."""
        return True

    @_cog_special_method
    def cog_check(self, ctx: Context) -> bool:
        """A special method that registers as a :func:`~.check`
        for every text command and subcommand in this cog.

        This is for text commands only, and doesn't apply to application commands.

        This function **can** be a coroutine and must take a sole parameter,
        ``ctx``, to represent the :class:`.Context`.
        """
        return True

    @_cog_special_method
    def cog_slash_command_check(self, inter: ApplicationCommandInteraction) -> bool:
        """A special method that registers as a :func:`~.check`
        for every slash command and subcommand in this cog.

        This function **can** be a coroutine and must take a sole parameter,
        ``inter``, to represent the :class:`.ApplicationCommandInteraction`.
        """
        return True

    @_cog_special_method
    def cog_user_command_check(self, inter: ApplicationCommandInteraction) -> bool:
        """Similar to :meth:`.Cog.cog_slash_command_check` but for user commands."""
        return True

    @_cog_special_method
    def cog_message_command_check(self, inter: ApplicationCommandInteraction) -> bool:
        """Similar to :meth:`.Cog.cog_slash_command_check` but for message commands."""
        return True

    @_cog_special_method
    async def cog_command_error(self, ctx: Context, error: Exception) -> None:
        """A special method that is called whenever an error
        is dispatched inside this cog.

        This is for text commands only, and doesn't apply to application commands.

        This is similar to :func:`.on_command_error` except only applying
        to the commands inside this cog.

        This **must** be a coroutine.

        Parameters
        ----------
        ctx: :class:`.Context`
            The invocation context where the error happened.
        error: :class:`CommandError`
            The error that was raised.
        """
        pass

    @_cog_special_method
    async def cog_slash_command_error(
        self, inter: ApplicationCommandInteraction, error: Exception
    ) -> None:
        """A special method that is called whenever an error
        is dispatched inside this cog.

        This is similar to :func:`.on_slash_command_error` except only applying
        to the slash commands inside this cog.

        This **must** be a coroutine.

        Parameters
        ----------
        inter: :class:`.ApplicationCommandInteraction`
            The interaction where the error happened.
        error: :class:`CommandError`
            The error that was raised.
        """
        pass

    @_cog_special_method
    async def cog_user_command_error(
        self, inter: ApplicationCommandInteraction, error: Exception
    ) -> None:
        """Similar to :func:`cog_slash_command_error` but for user commands."""
        pass

    @_cog_special_method
    async def cog_message_command_error(
        self, inter: ApplicationCommandInteraction, error: Exception
    ) -> None:
        """Similar to :func:`cog_slash_command_error` but for message commands."""
        pass

    @_cog_special_method
    async def cog_before_invoke(self, ctx: Context) -> None:
        """A special method that acts as a cog local pre-invoke hook,
        similar to :meth:`.Command.before_invoke`.

        This is for text commands only, and doesn't apply to application commands.

        This **must** be a coroutine.

        Parameters
        ----------
        ctx: :class:`.Context`
            The invocation context.
        """
        pass

    @_cog_special_method
    async def cog_after_invoke(self, ctx: Context) -> None:
        """A special method that acts as a cog local post-invoke hook,
        similar to :meth:`.Command.after_invoke`.

        This is for text commands only, and doesn't apply to application commands.

        This **must** be a coroutine.

        Parameters
        ----------
        ctx: :class:`.Context`
            The invocation context.
        """
        pass

    @_cog_special_method
    async def cog_before_slash_command_invoke(self, inter: ApplicationCommandInteraction) -> None:
        """A special method that acts as a cog local pre-invoke hook.

        This is similar to :meth:`.Command.before_invoke` but for slash commands.

        This **must** be a coroutine.

        Parameters
        ----------
        inter: :class:`.ApplicationCommandInteraction`
            The interaction of the slash command.
        """
        pass

    @_cog_special_method
    async def cog_after_slash_command_invoke(self, inter: ApplicationCommandInteraction) -> None:
        """A special method that acts as a cog local post-invoke hook.

        This is similar to :meth:`.Command.after_invoke` but for slash commands.

        This **must** be a coroutine.

        Parameters
        ----------
        inter: :class:`.ApplicationCommandInteraction`
            The interaction of the slash command.
        """
        pass

    @_cog_special_method
    async def cog_before_user_command_invoke(self, inter: ApplicationCommandInteraction) -> None:
        """Similar to :meth:`cog_before_slash_command_invoke` but for user commands."""
        pass

    @_cog_special_method
    async def cog_after_user_command_invoke(self, inter: ApplicationCommandInteraction) -> None:
        """Similar to :meth:`cog_after_slash_command_invoke` but for user commands."""
        pass

    @_cog_special_method
    async def cog_before_message_command_invoke(self, inter: ApplicationCommandInteraction) -> None:
        """Similar to :meth:`cog_before_slash_command_invoke` but for message commands."""
        pass

    @_cog_special_method
    async def cog_after_message_command_invoke(self, inter: ApplicationCommandInteraction) -> None:
        """Similar to :meth:`cog_after_slash_command_invoke` but for message commands."""
        pass

    def _inject(self, bot: AnyBot) -> Self:
        from .bot import AutoShardedInteractionBot, InteractionBot

        cls = self.__class__

        if (
            isinstance(bot, (InteractionBot, AutoShardedInteractionBot))
            and len(self.__cog_commands__) > 0
        ):
            raise TypeError("@commands.command is not supported for interaction bots.")

        # realistically, the only thing that can cause loading errors
        # is essentially just the command loading, which raises if there are
        # duplicates. When this condition is met, we want to undo all what
        # we've added so far for some form of atomic loading.
        for index, command in enumerate(self.__cog_commands__):
            command.cog = self
            if command.parent is None:
                try:
                    bot.add_command(command)  # type: ignore
                except Exception:
                    # undo our additions
                    for to_undo in self.__cog_commands__[:index]:
                        if to_undo.parent is None:
                            bot.remove_command(to_undo.name)  # type: ignore
                    raise

        for index, command in enumerate(self.__cog_app_commands__):
            command.cog = self
            try:
                if isinstance(command, InvokableSlashCommand):
                    bot.add_slash_command(command)
                elif isinstance(command, InvokableUserCommand):
                    bot.add_user_command(command)
                elif isinstance(command, InvokableMessageCommand):
                    bot.add_message_command(command)
            except Exception:
                # undo our additions
                for to_undo in self.__cog_app_commands__[:index]:
                    if isinstance(to_undo, InvokableSlashCommand):
                        bot.remove_slash_command(to_undo.name)
                    elif isinstance(to_undo, InvokableUserCommand):
                        bot.remove_user_command(to_undo.name)
                    elif isinstance(to_undo, InvokableMessageCommand):
                        bot.remove_message_command(to_undo.name)
                raise

        if not hasattr(self.cog_load.__func__, "__cog_special_method__"):
            bot.loop.create_task(disnake.utils.maybe_coroutine(self.cog_load))

        # check if we're overriding the default
        if cls.bot_check is not Cog.bot_check:
            if isinstance(bot, (InteractionBot, AutoShardedInteractionBot)):
                raise TypeError("Cog.bot_check is not supported for interaction bots.")

            bot.add_check(self.bot_check)

        if cls.bot_check_once is not Cog.bot_check_once:
            if isinstance(bot, (InteractionBot, AutoShardedInteractionBot)):
                raise TypeError("Cog.bot_check_once is not supported for interaction bots.")

            bot.add_check(self.bot_check_once, call_once=True)

        # Add application command checks
        if cls.bot_slash_command_check is not Cog.bot_slash_command_check:
            bot.add_app_command_check(self.bot_slash_command_check, slash_commands=True)

        if cls.bot_user_command_check is not Cog.bot_user_command_check:
            bot.add_app_command_check(self.bot_user_command_check, user_commands=True)

        if cls.bot_message_command_check is not Cog.bot_message_command_check:
            bot.add_app_command_check(self.bot_message_command_check, message_commands=True)

        # Add app command one-off checks
        if cls.bot_slash_command_check_once is not Cog.bot_slash_command_check_once:
            bot.add_app_command_check(
                self.bot_slash_command_check_once,
                call_once=True,
                slash_commands=True,
            )

        if cls.bot_user_command_check_once is not Cog.bot_user_command_check_once:
            bot.add_app_command_check(
                self.bot_user_command_check_once, call_once=True, user_commands=True
            )

        if cls.bot_message_command_check_once is not Cog.bot_message_command_check_once:
            bot.add_app_command_check(
                self.bot_message_command_check_once,
                call_once=True,
                message_commands=True,
            )

        # while Bot.add_listener can raise if it's not a coroutine,
        # this precondition is already met by the listener decorator
        # already, thus this should never raise.
        # Outside of, memory errors and the like...
        for name, method_name in self.__cog_listeners__:
            bot.add_listener(getattr(self, method_name), name)

        try:
            if bot._command_sync_flags.sync_on_cog_actions:
                bot._schedule_delayed_command_sync()
        except NotImplementedError:
            pass

        return self

    def _eject(self, bot: AnyBot) -> None:
        cls = self.__class__

        try:
            for command in self.__cog_commands__:
                if command.parent is None:
                    bot.remove_command(command.name)  # type: ignore

            for app_command in self.__cog_app_commands__:
                if isinstance(app_command, InvokableSlashCommand):
                    bot.remove_slash_command(app_command.name)
                elif isinstance(app_command, InvokableUserCommand):
                    bot.remove_user_command(app_command.name)
                elif isinstance(app_command, InvokableMessageCommand):
                    bot.remove_message_command(app_command.name)

            for name, method_name in self.__cog_listeners__:
                bot.remove_listener(getattr(self, method_name), name)

            if cls.bot_check is not Cog.bot_check:
                bot.remove_check(self.bot_check)  # type: ignore

            if cls.bot_check_once is not Cog.bot_check_once:
                bot.remove_check(self.bot_check_once, call_once=True)  # type: ignore

            # Remove application command checks
            if cls.bot_slash_command_check is not Cog.bot_slash_command_check:
                bot.remove_app_command_check(self.bot_slash_command_check, slash_commands=True)

            if cls.bot_user_command_check is not Cog.bot_user_command_check:
                bot.remove_app_command_check(self.bot_user_command_check, user_commands=True)

            if cls.bot_message_command_check is not Cog.bot_message_command_check:
                bot.remove_app_command_check(self.bot_message_command_check, message_commands=True)

            # Remove app command one-off checks
            if cls.bot_slash_command_check_once is not Cog.bot_slash_command_check_once:
                bot.remove_app_command_check(
                    self.bot_slash_command_check_once,
                    call_once=True,
                    slash_commands=True,
                )

            if cls.bot_user_command_check_once is not Cog.bot_user_command_check_once:
                bot.remove_app_command_check(
                    self.bot_user_command_check_once,
                    call_once=True,
                    user_commands=True,
                )

            if cls.bot_message_command_check_once is not Cog.bot_message_command_check_once:
                bot.remove_app_command_check(
                    self.bot_message_command_check_once,
                    call_once=True,
                    message_commands=True,
                )

        finally:
            try:
                if bot._command_sync_flags.sync_on_cog_actions:
                    bot._schedule_delayed_command_sync()
            except NotImplementedError:
                pass
            try:
                self.cog_unload()
            except Exception as e:
                _log.error(
                    "An error occurred while unloading the %s cog.", self.qualified_name, exc_info=e
                )
