# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import collections
import collections.abc
import inspect
import logging
import sys
import traceback
import warnings
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
)

import disnake

from . import errors
from .common_bot_base import CommonBotBase
from .context import Context
from .core import GroupMixin
from .custom_warnings import MessageContentPrefixWarning
from .help import DefaultHelpCommand, HelpCommand
from .view import StringView

if TYPE_CHECKING:
    from typing_extensions import Self

    from disnake.message import Message

    from ._types import Check, CoroFunc, MaybeCoro

__all__ = (
    "when_mentioned",
    "when_mentioned_or",
    "BotBase",
)

MISSING: Any = disnake.utils.MISSING

T = TypeVar("T")
CFT = TypeVar("CFT", bound="CoroFunc")
CXT = TypeVar("CXT", bound="Context")

PrefixType = Union[str, Iterable[str]]

_log = logging.getLogger(__name__)


def when_mentioned(bot: BotBase, msg: Message) -> List[str]:
    """A callable that implements a command prefix equivalent to being mentioned.

    These are meant to be passed into the :attr:`.Bot.command_prefix` attribute.
    """
    # bot.user will never be None when this is called
    return [f"<@{bot.user.id}> ", f"<@!{bot.user.id}> "]  # type: ignore


def when_mentioned_or(*prefixes: str) -> Callable[[BotBase, Message], List[str]]:
    """A callable that implements when mentioned or other prefixes provided.

    These are meant to be passed into the :attr:`.Bot.command_prefix` attribute.

    Example
    -------
    .. code-block:: python3

        bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'))


    .. note::

        This callable returns another callable, so if this is done inside a custom
        callable, you must call the returned callable, for example:

        .. code-block:: python3

            async def get_prefix(bot, message):
                extras = await prefixes_for(message.guild) # returns a list
                return commands.when_mentioned_or(*extras)(bot, message)


    See Also
    --------
    :func:`.when_mentioned`
    """

    def inner(bot, msg):
        r = list(prefixes)
        r = when_mentioned(bot, msg) + r
        return r

    return inner


def _is_submodule(parent: str, child: str) -> bool:
    return parent == child or child.startswith(parent + ".")


class _DefaultRepr:
    def __repr__(self) -> str:
        return "<default-help-command>"


_default: Any = _DefaultRepr()


class BotBase(CommonBotBase, GroupMixin):
    def __init__(
        self,
        command_prefix: Optional[
            Union[PrefixType, Callable[[Self, Message], MaybeCoro[PrefixType]]]
        ] = None,
        help_command: Optional[HelpCommand] = _default,
        description: Optional[str] = None,
        *,
        strip_after_prefix: bool = False,
        **options: Any,
    ) -> None:
        super().__init__(**options)

        if not isinstance(self, disnake.Client):
            raise RuntimeError("BotBase mixin must be used with disnake.Client")  # noqa: TRY004

        alternative = (
            "AutoShardedInteractionBot"
            if isinstance(self, disnake.AutoShardedClient)
            else "InteractionBot"
        )
        if command_prefix is None:
            disnake.utils.warn_deprecated(
                "Using `command_prefix=None` is deprecated and will result in "
                "an error in future versions. "
                f"If you don't need any prefix functionality, consider using {alternative}.",
                stacklevel=2,
            )
        elif (
            # note: no need to check for empty iterables,
            # as they won't be allowed by `get_prefix`
            command_prefix is not when_mentioned
            and not self.intents.message_content
        ):
            warnings.warn(
                "Message Content intent is not enabled and a prefix is configured. "
                "This may cause limited functionality for prefix commands. "
                "If you want prefix commands, pass an intents object with message_content set to True. "
                f"If you don't need any prefix functionality, consider using {alternative}. "
                "Alternatively, set prefix to disnake.ext.commands.when_mentioned to silence this warning.",
                MessageContentPrefixWarning,
                stacklevel=2,
            )

        self.command_prefix = command_prefix

        self._checks: List[Check] = []
        self._check_once: List[Check] = []

        self._before_invoke: Optional[CoroFunc] = None
        self._after_invoke: Optional[CoroFunc] = None

        self._help_command: Optional[HelpCommand] = None
        self.description: str = inspect.cleandoc(description) if description else ""
        self.strip_after_prefix: bool = strip_after_prefix

        if help_command is _default:
            self.help_command = DefaultHelpCommand()
        else:
            self.help_command = help_command

    # internal helpers

    async def on_command_error(self, context: Context, exception: errors.CommandError) -> None:
        """|coro|

        The default command error handler provided by the bot.

        This is for text commands only, and doesn't apply to application commands.

        By default this prints to :data:`sys.stderr` however it could be
        overridden to have a different implementation.

        This only fires if you do not specify any listeners for command error.
        """
        if self.extra_events.get("on_command_error", None):
            return

        command = context.command
        if command and command.has_error_handler():
            return

        cog = context.cog
        if cog and cog.has_error_handler():
            return

        print(f"Ignoring exception in command {context.command}:", file=sys.stderr)
        traceback.print_exception(
            type(exception), exception, exception.__traceback__, file=sys.stderr
        )

    # global check registration

    def add_check(
        self,
        func: Check,
        *,
        call_once: bool = False,
    ) -> None:
        """Adds a global check to the bot.

        This is for text commands only, and doesn't apply to application commands.

        This is the non-decorator interface to :meth:`.check` and :meth:`.check_once`.

        Parameters
        ----------
        func
            The function that was used as a global check.
        call_once: :class:`bool`
            If the function should only be called once per
            :meth:`.invoke` call.
        """
        if call_once:
            self._check_once.append(func)
        else:
            self._checks.append(func)

    def remove_check(
        self,
        func: Check,
        *,
        call_once: bool = False,
    ) -> None:
        """Removes a global check from the bot.

        This is for text commands only, and doesn't apply to application commands.

        This function is idempotent and will not raise an exception
        if the function is not in the global checks.

        Parameters
        ----------
        func
            The function to remove from the global checks.
        call_once: :class:`bool`
            If the function was added with ``call_once=True`` in
            the :meth:`.Bot.add_check` call or using :meth:`.check_once`.
        """
        check_list = self._check_once if call_once else self._checks
        try:
            check_list.remove(func)
        except ValueError:
            pass

    def check(self, func: T) -> T:
        """A decorator that adds a global check to the bot.

        This is for text commands only, and doesn't apply to application commands.

        A global check is similar to a :func:`.check` that is applied
        on a per command basis except it is run before any command checks
        have been verified and applies to every command the bot has.

        .. note::

            This function can either be a regular function or a coroutine.

        Similar to a command :func:`.check`\\, this takes a single parameter
        of type :class:`.Context` and can only raise exceptions inherited from
        :exc:`.CommandError`.

        Example
        -------
        .. code-block:: python3

            @bot.check
            def check_commands(ctx):
                return ctx.command.qualified_name in allowed_commands

        """
        # T was used instead of Check to ensure the type matches on return
        self.add_check(func)  # type: ignore
        return func

    def check_once(self, func: CFT) -> CFT:
        """A decorator that adds a "call once" global check to the bot.

        This is for text commands only, and doesn't apply to application commands.

        Unlike regular global checks, this one is called only once
        per :meth:`.invoke` call.

        Regular global checks are called whenever a command is called
        or :meth:`.Command.can_run` is called. This type of check
        bypasses that and ensures that it's called only once, even inside
        the default help command.

        .. note::

            When using this function the :class:`.Context` sent to a group subcommand
            may only parse the parent command and not the subcommands due to it
            being invoked once per :meth:`.Bot.invoke` call.

        .. note::

            This function can either be a regular function or a coroutine.

        Similar to a command :func:`.check`\\, this takes a single parameter
        of type :class:`.Context` and can only raise exceptions inherited from
        :exc:`.CommandError`.

        Example
        -------
        .. code-block:: python3

            @bot.check_once
            def whitelist(ctx):
                return ctx.message.author.id in my_whitelist

        """
        self.add_check(func, call_once=True)
        return func

    async def can_run(self, ctx: Context, *, call_once: bool = False) -> bool:
        data = self._check_once if call_once else self._checks

        if len(data) == 0:
            return True

        # type-checker doesn't distinguish between functions and methods
        return await disnake.utils.async_all(f(ctx) for f in data)  # type: ignore

    def before_invoke(self, coro: CFT) -> CFT:
        """A decorator that registers a coroutine as a pre-invoke hook.

        This is for text commands only, and doesn't apply to application commands.

        A pre-invoke hook is called directly before the command is
        called. This makes it a useful function to set up database
        connections or any type of set up required.

        This pre-invoke hook takes a sole parameter, a :class:`.Context`.

        .. note::

            The :meth:`~.Bot.before_invoke` and :meth:`~.Bot.after_invoke` hooks are
            only called if all checks and argument parsing procedures pass
            without error. If any check or argument parsing procedures fail
            then the hooks are not called.

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

    def after_invoke(self, coro: CFT) -> CFT:
        """A decorator that registers a coroutine as a post-invoke hook.

        This is for text commands only, and doesn't apply to application commands.

        A post-invoke hook is called directly after the command is
        called. This makes it a useful function to clean-up database
        connections or any type of clean up required.

        This post-invoke hook takes a sole parameter, a :class:`.Context`.

        .. note::

            Similar to :meth:`~.Bot.before_invoke`\\, this is not called unless
            checks and argument parsing procedures succeed. This hook is,
            however, **always** called regardless of the internal command
            callback raising an error (i.e. :exc:`.CommandInvokeError`\\).
            This makes it ideal for clean-up scenarios.

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

    # extensions

    def _remove_module_references(self, name: str) -> None:
        super()._remove_module_references(name)
        # remove all the commands from the module
        for cmd in self.all_commands.copy().values():
            if cmd.module is not None and _is_submodule(name, cmd.module):
                if isinstance(cmd, GroupMixin):
                    cmd.recursively_remove_all_commands()
                self.remove_command(cmd.name)

    # help command stuff

    @property
    def help_command(self) -> Optional[HelpCommand]:
        return self._help_command

    @help_command.setter
    def help_command(self, value: Optional[HelpCommand]) -> None:
        if value is not None and not isinstance(value, HelpCommand):
            raise TypeError("help_command must be a subclass of HelpCommand or None")

        if self._help_command is not None:
            self._help_command._remove_from_bot(self)

        self._help_command = value

        if value is not None:
            value._add_to_bot(self)

    # command processing

    async def get_prefix(self, message: Message) -> Optional[Union[List[str], str]]:
        """|coro|

        Retrieves the prefix the bot is listening to
        with the message as a context.

        Parameters
        ----------
        message: :class:`disnake.Message`
            The message context to get the prefix of.

        Returns
        -------
        Optional[Union[List[:class:`str`], :class:`str`]]
            A list of prefixes or a single prefix that the bot is
            listening for. None if the bot isn't listening for prefixes.
        """
        ret = self.command_prefix
        if callable(ret):
            ret = await disnake.utils.maybe_coroutine(ret, self, message)

        if ret is None:
            return None

        if not isinstance(ret, str):
            try:
                ret = list(ret)
            except TypeError:
                # It's possible that a generator raised this exception.  Don't
                # replace it with our own error if that's the case.
                if isinstance(ret, collections.abc.Iterable):
                    raise

                raise TypeError(
                    "command_prefix must be plain string, iterable of strings, or callable "
                    f"returning either of these, not {ret.__class__.__name__}"
                ) from None

            if not ret:
                raise ValueError("Iterable command_prefix must contain at least one prefix")

        return ret

    async def get_context(self, message: Message, *, cls: Type[CXT] = Context) -> CXT:
        """|coro|

        Returns the invocation context from the message.

        This is a more low-level counter-part for :meth:`.process_commands`
        to allow users more fine grained control over the processing.

        The returned context is not guaranteed to be a valid invocation
        context, :attr:`.Context.valid` must be checked to make sure it is.
        If the context is not valid then it is not a valid candidate to be
        invoked under :meth:`~.Bot.invoke`.

        Parameters
        ----------
        message: :class:`disnake.Message`
            The message to get the invocation context from.
        cls
            The factory class that will be used to create the context.
            By default, this is :class:`.Context`. Should a custom
            class be provided, it must be similar enough to :class:`.Context`\'s
            interface.

        Returns
        -------
        :class:`.Context`
            The invocation context. The type of this can change via the
            ``cls`` parameter.
        """
        view = StringView(message.content)
        ctx = cast("CXT", cls(prefix=None, view=view, bot=self, message=message))

        if message.author.id == self.user.id:  # type: ignore
            return ctx

        prefix = await self.get_prefix(message)
        invoked_prefix = prefix

        if prefix is None:
            return ctx
        if isinstance(prefix, str):
            if not view.skip_string(prefix):
                return ctx
        else:
            try:
                # if the context class' __init__ consumes something from the view this
                # will be wrong.  That seems unreasonable though.
                if message.content.startswith(tuple(prefix)):
                    invoked_prefix = disnake.utils.find(view.skip_string, prefix)
                else:
                    return ctx

            except TypeError:
                if not isinstance(prefix, list):
                    raise TypeError(
                        "get_prefix must return either a string or a list of string, "
                        f"not {prefix.__class__.__name__}"
                    ) from None

                # It's possible a bad command_prefix got us here.
                for value in prefix:
                    if not isinstance(value, str):
                        raise TypeError(
                            "Iterable command_prefix or list returned from get_prefix must "
                            f"contain only strings, not {value.__class__.__name__}"
                        ) from None

                # Getting here shouldn't happen
                raise

        if self.strip_after_prefix:
            view.skip_ws()

        invoker = view.get_word()
        ctx.invoked_with = invoker
        # type-checker fails to narrow invoked_prefix type.
        ctx.prefix = invoked_prefix  # type: ignore
        ctx.command = self.all_commands.get(invoker)
        return ctx

    async def invoke(self, ctx: Context) -> None:
        """|coro|

        Invokes the command given under the invocation context and
        handles all the internal event dispatch mechanisms.

        Parameters
        ----------
        ctx: :class:`.Context`
            The invocation context to invoke.
        """
        if ctx.command is not None:
            self.dispatch("command", ctx)
            try:
                if await self.can_run(ctx, call_once=True):
                    await ctx.command.invoke(ctx)
                else:
                    raise errors.CheckFailure("The global check once functions failed.")
            except errors.CommandError as exc:
                await ctx.command.dispatch_error(ctx, exc)
            else:
                self.dispatch("command_completion", ctx)
        elif ctx.invoked_with:
            exc = errors.CommandNotFound(f'Command "{ctx.invoked_with}" is not found')
            self.dispatch("command_error", ctx, exc)

    async def process_commands(self, message: Message) -> None:
        """|coro|

        This function processes the commands that have been registered
        to the bot and other groups. Without this coroutine, none of the
        commands will be triggered.

        By default, this coroutine is called inside the :func:`.on_message`
        event. If you choose to override the :func:`.on_message` event, then
        you should invoke this coroutine as well.

        This is built using other low level tools, and is equivalent to a
        call to :meth:`~.Bot.get_context` followed by a call to :meth:`~.Bot.invoke`.

        This also checks if the message's author is a bot and doesn't
        call :meth:`~.Bot.get_context` or :meth:`~.Bot.invoke` if so.

        Parameters
        ----------
        message: :class:`disnake.Message`
            The message to process commands for.
        """
        if message.author.bot:
            return

        ctx = await self.get_context(message)
        await self.invoke(ctx)

    async def on_message(self, message) -> None:
        await self.process_commands(message)
