# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import collections.abc
import importlib.util
import logging
import os
import sys
import time
import types
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Mapping,
    Optional,
    Set,
    TypeVar,
    Union,
)

import disnake
import disnake.utils
from disnake.enums import Event

from . import errors
from .cog import Cog

if TYPE_CHECKING:
    import importlib.machinery

    from ._types import CoroFunc
    from .bot import AutoShardedBot, AutoShardedInteractionBot, Bot, InteractionBot
    from .help import HelpCommand

    AnyBot = Union[Bot, AutoShardedBot, InteractionBot, AutoShardedInteractionBot]

__all__ = ("CommonBotBase",)
_log = logging.getLogger(__name__)

CogT = TypeVar("CogT", bound="Cog")
CFT = TypeVar("CFT", bound="CoroFunc")

MISSING: Any = disnake.utils.MISSING


def _is_submodule(parent: str, child: str) -> bool:
    return parent == child or child.startswith(parent + ".")


class CommonBotBase(Generic[CogT]):
    def __init__(
        self,
        *args: Any,
        owner_id: Optional[int] = None,
        owner_ids: Optional[Set[int]] = None,
        reload: bool = False,
        **kwargs: Any,
    ) -> None:
        self.__cogs: Dict[str, Cog] = {}
        self.__extensions: Dict[str, types.ModuleType] = {}
        self.extra_events: Dict[str, List[CoroFunc]] = {}
        self._is_closed: bool = False

        self.owner_id: Optional[int] = owner_id
        self.owner_ids: Set[int] = owner_ids or set()
        self.owner: Optional[disnake.User] = None
        self.owners: Set[disnake.TeamMember] = set()

        if self.owner_id and self.owner_ids:
            raise TypeError("Both owner_id and owner_ids are set.")

        if self.owner_ids and not isinstance(self.owner_ids, collections.abc.Collection):
            raise TypeError(f"owner_ids must be a collection not {self.owner_ids.__class__!r}")

        self.reload: bool = reload

        super().__init__(*args, **kwargs)

    def dispatch(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        # super() will resolve to Client
        super().dispatch(event_name, *args, **kwargs)  # type: ignore
        ev = "on_" + event_name
        for event in self.extra_events.get(ev, []):
            self._schedule_event(event, ev, *args, **kwargs)  # type: ignore

    async def _fill_owners(self) -> None:
        if self.owner_id or self.owner_ids:
            return

        await self.wait_until_first_connect()  # type: ignore

        app = await self.application_info()  # type: ignore
        if app.team:
            self.owners = set(app.team.members)
            self.owner_ids = {m.id for m in app.team.members}
        else:
            self.owner = app.owner
            self.owner_id = app.owner.id

    async def close(self) -> None:
        self._is_closed = True

        for extension in tuple(self.__extensions):
            try:
                self.unload_extension(extension)
            except Exception as error:
                error.__suppress_context__ = True
                _log.error("Failed to unload extension %r", extension, exc_info=error)

        for cog in tuple(self.__cogs):
            try:
                self.remove_cog(cog)
            except Exception as error:
                error.__suppress_context__ = True
                _log.exception("Failed to remove cog %r", cog, exc_info=error)

        await super().close()  # type: ignore

    @disnake.utils.copy_doc(disnake.Client.login)
    async def login(self, token: str) -> None:
        self.loop.create_task(self._fill_owners())  # type: ignore

        if self.reload:
            self.loop.create_task(self._watchdog())  # type: ignore
        await super().login(token=token)  # type: ignore

    async def is_owner(self, user: Union[disnake.User, disnake.Member]) -> bool:
        """|coro|

        Checks if a :class:`~disnake.User` or :class:`~disnake.Member` is the owner of
        this bot.

        If an :attr:`owner_id` is not set, it is fetched automatically
        through the use of :meth:`~.Bot.application_info`.

        .. versionchanged:: 1.3
            The function also checks if the application is team-owned if
            :attr:`owner_ids` is not set.

        Parameters
        ----------
        user: :class:`.abc.User`
            The user to check for.

        Returns
        -------
        :class:`bool`
            Whether the user is the owner.
        """
        if self.owner_id:
            return user.id == self.owner_id
        if self.owner_ids:
            return user.id in self.owner_ids
        app = await self.application_info()  # type: ignore
        if app.team:
            self.owners = set(app.team.members)
            self.owner_ids = ids = {m.id for m in app.team.members}
            return user.id in ids
        self.owner = app.owner
        self.owner_id = owner_id = app.owner.id
        return user.id == owner_id

    # listener registration

    def add_listener(self, func: CoroFunc, name: Union[str, Event] = MISSING) -> None:
        """The non decorator alternative to :meth:`.listen`.

        Parameters
        ----------
        func: :ref:`coroutine <coroutine>`
            The function to call.
        name: Union[:class:`str`, :class:`.Event`]
            The name of the event to listen for. Defaults to ``func.__name__``.

        Example
        --------

        .. code-block:: python

            async def on_ready(): pass
            async def my_message(message): pass
            async def another_message(message): pass

            bot.add_listener(on_ready)
            bot.add_listener(my_message, 'on_message')
            bot.add_listener(another_message, Event.message)

        Raises
        ------
        TypeError
            The function is not a coroutine or a string or an :class:`.Event` was not passed
            as the name.
        """
        if name is not MISSING and not isinstance(name, (str, Event)):
            raise TypeError(
                f"Bot.add_listener expected str or Enum but received {name.__class__.__name__!r} instead."
            )

        name_ = (
            func.__name__
            if name is MISSING
            else (name if isinstance(name, str) else f"on_{name.value}")
        )

        if not asyncio.iscoroutinefunction(func):
            raise TypeError("Listeners must be coroutines")

        if name_ in self.extra_events:
            self.extra_events[name_].append(func)
        else:
            self.extra_events[name_] = [func]

    def remove_listener(self, func: CoroFunc, name: Union[str, Event] = MISSING) -> None:
        """Removes a listener from the pool of listeners.

        Parameters
        ----------
        func
            The function that was used as a listener to remove.
        name: Union[:class:`str`, :class:`.Event`]
            The name of the event we want to remove. Defaults to
            ``func.__name__``.

        Raises
        ------
        TypeError
            The name passed was not a string or an :class:`.Event`.
        """
        if name is not MISSING and not isinstance(name, (str, Event)):
            raise TypeError(
                f"Bot.remove_listener expected str or Enum but received {name.__class__.__name__!r} instead."
            )
        name = (
            func.__name__
            if name is MISSING
            else (name if isinstance(name, str) else f"on_{name.value}")
        )

        if name in self.extra_events:
            try:
                self.extra_events[name].remove(func)
            except ValueError:
                pass

    def listen(self, name: Union[str, Event] = MISSING) -> Callable[[CFT], CFT]:
        """A decorator that registers another function as an external
        event listener. Basically this allows you to listen to multiple
        events from different places e.g. such as :func:`.on_ready`

        The functions being listened to must be a :ref:`coroutine <coroutine>`.

        Example
        -------
        .. code-block:: python3

            @bot.listen()
            async def on_message(message):
                print('one')

            # in some other file...

            @bot.listen('on_message')
            async def my_message(message):
                print('two')

            # in yet another file
            @bot.listen(Event.message)
            async def another_message(message):
                print('three')

        Would print one, two and three in an unspecified order.

        Raises
        ------
        TypeError
            The function being listened to is not a coroutine or a string or an :class:`.Event` was not passed
            as the name.
        """
        if name is not MISSING and not isinstance(name, (str, Event)):
            raise TypeError(
                f"Bot.listen expected str or Enum but received {name.__class__.__name__!r} instead."
            )

        def decorator(func: CFT) -> CFT:
            self.add_listener(func, name)
            return func

        return decorator

    # cogs

    def add_cog(self, cog: Cog, *, override: bool = False) -> None:
        """Adds a "cog" to the bot.

        A cog is a class that has its own event listeners and commands.

        .. versionchanged:: 2.0

            :exc:`.ClientException` is raised when a cog with the same name
            is already loaded.

        Parameters
        ----------
        cog: :class:`.Cog`
            The cog to register to the bot.
        override: :class:`bool`
            If a previously loaded cog with the same name should be ejected
            instead of raising an error.

            .. versionadded:: 2.0

        Raises
        ------
        TypeError
            The cog does not inherit from :class:`.Cog`.
        CommandError
            An error happened during loading.
        ClientException
            A cog with the same name is already loaded.
        """
        if not isinstance(cog, Cog):
            raise TypeError("cogs must derive from Cog")

        cog_name = cog.__cog_name__
        existing = self.__cogs.get(cog_name)

        if existing is not None:
            if not override:
                raise disnake.ClientException(f"Cog named {cog_name!r} already loaded")
            self.remove_cog(cog_name)

        # NOTE: Should be covariant
        cog = cog._inject(self)  # type: ignore
        self.__cogs[cog_name] = cog

    def get_cog(self, name: str) -> Optional[Cog]:
        """Gets the cog instance requested.

        If the cog is not found, ``None`` is returned instead.

        Parameters
        ----------
        name: :class:`str`
            The name of the cog you are requesting.
            This is equivalent to the name passed via keyword
            argument in class creation or the class name if unspecified.

        Returns
        -------
        Optional[:class:`Cog`]
            The cog that was requested. If not found, returns ``None``.
        """
        return self.__cogs.get(name)

    def remove_cog(self, name: str) -> Optional[Cog]:
        """Removes a cog from the bot and returns it.

        All registered commands and event listeners that the
        cog has registered will be removed as well.

        If no cog is found then this method has no effect.

        Parameters
        ----------
        name: :class:`str`
            The name of the cog to remove.

        Returns
        -------
        Optional[:class:`.Cog`]
            The cog that was removed. Returns ``None`` if not found.
        """
        cog = self.__cogs.pop(name, None)
        if cog is None:
            return None

        help_command: Optional[HelpCommand] = getattr(self, "_help_command", None)
        if help_command and help_command.cog is cog:
            help_command.cog = None
        # NOTE: Should be covariant
        cog._eject(self)  # type: ignore

        return cog

    @property
    def cogs(self) -> Mapping[str, Cog]:
        """Mapping[:class:`str`, :class:`Cog`]: A read-only mapping of cog name to cog."""
        return types.MappingProxyType(self.__cogs)

    def get_listeners(self) -> Mapping[str, List[CoroFunc]]:
        """Mapping[:class:`str`, List[Callable]]: A read-only mapping of event names to listeners.

        .. note::
            To add or remove a listener you should use :meth:`.add_listener` and
            :meth:`.remove_listener`.

        .. versionadded:: 2.9
        """
        return types.MappingProxyType(self.extra_events)

    # extensions

    def _remove_module_references(self, name: str) -> None:
        # find all references to the module
        # remove the cogs registered from the module
        for cogname, cog in self.__cogs.copy().items():
            if _is_submodule(name, cog.__module__):
                self.remove_cog(cogname)
        # remove all the listeners from the module
        for event_list in self.extra_events.copy().values():
            remove = [
                index
                for index, event in enumerate(event_list)
                if event.__module__ and _is_submodule(name, event.__module__)
            ]

            for index in reversed(remove):
                del event_list[index]

    def _call_module_finalizers(self, lib: types.ModuleType, key: str) -> None:
        try:
            func = lib.teardown
        except AttributeError:
            pass
        else:
            try:
                func(self)
            except Exception as error:
                error.__suppress_context__ = True
                _log.error("Exception in extension finalizer %r", key, exc_info=error)
        finally:
            self.__extensions.pop(key, None)
            sys.modules.pop(key, None)
            name = lib.__name__
            for module in list(sys.modules.keys()):
                if _is_submodule(name, module):
                    del sys.modules[module]

    def _load_from_module_spec(self, spec: importlib.machinery.ModuleSpec, key: str) -> None:
        # precondition: key not in self.__extensions
        lib = importlib.util.module_from_spec(spec)
        sys.modules[key] = lib
        try:
            spec.loader.exec_module(lib)  # type: ignore
        except Exception as e:
            del sys.modules[key]
            raise errors.ExtensionFailed(key, e) from e

        try:
            setup = lib.setup
        except AttributeError:
            del sys.modules[key]
            raise errors.NoEntryPointError(key) from None

        try:
            setup(self)
        except Exception as e:
            del sys.modules[key]
            self._remove_module_references(lib.__name__)
            self._call_module_finalizers(lib, key)
            raise errors.ExtensionFailed(key, e) from e
        else:
            self.__extensions[key] = lib

    def _resolve_name(self, name: str, package: Optional[str]) -> str:
        try:
            return importlib.util.resolve_name(name, package)
        except ImportError as e:
            raise errors.ExtensionNotFound(name) from e

    def load_extension(self, name: str, *, package: Optional[str] = None) -> None:
        """Loads an extension.

        An extension is a python module that contains commands, cogs, or
        listeners.

        An extension must have a global function, ``setup`` defined as
        the entry point on what to do when the extension is loaded. This entry
        point must have a single argument, the ``bot``.

        Parameters
        ----------
        name: :class:`str`
            The extension name to load. It must be dot separated like
            regular Python imports if accessing a sub-module. e.g.
            ``foo.test`` if you want to import ``foo/test.py``.
        package: Optional[:class:`str`]
            The package name to resolve relative imports with.
            This is required when loading an extension using a relative path, e.g ``.foo.test``.
            Defaults to ``None``.

            .. versionadded:: 1.7

        Raises
        ------
        ExtensionNotFound
            The extension could not be imported.
            This is also raised if the name of the extension could not
            be resolved using the provided ``package`` parameter.
        ExtensionAlreadyLoaded
            The extension is already loaded.
        NoEntryPointError
            The extension does not have a setup function.
        ExtensionFailed
            The extension or its setup function had an execution error.
        """
        name = self._resolve_name(name, package)
        if name in self.__extensions:
            raise errors.ExtensionAlreadyLoaded(name)

        spec = importlib.util.find_spec(name)
        if spec is None:
            raise errors.ExtensionNotFound(name)

        self._load_from_module_spec(spec, name)

    def unload_extension(self, name: str, *, package: Optional[str] = None) -> None:
        """Unloads an extension.

        When the extension is unloaded, all commands, listeners, and cogs are
        removed from the bot and the module is un-imported.

        The extension can provide an optional global function, ``teardown``,
        to do miscellaneous clean-up if necessary. This function takes a single
        parameter, the ``bot``, similar to ``setup`` from
        :meth:`~.Bot.load_extension`.

        Parameters
        ----------
        name: :class:`str`
            The extension name to unload. It must be dot separated like
            regular Python imports if accessing a sub-module. e.g.
            ``foo.test`` if you want to import ``foo/test.py``.
        package: Optional[:class:`str`]
            The package name to resolve relative imports with.
            This is required when unloading an extension using a relative path, e.g ``.foo.test``.
            Defaults to ``None``.

            .. versionadded:: 1.7

        Raises
        ------
        ExtensionNotFound
            The name of the extension could not
            be resolved using the provided ``package`` parameter.
        ExtensionNotLoaded
            The extension was not loaded.
        """
        name = self._resolve_name(name, package)
        lib = self.__extensions.get(name)
        if lib is None:
            raise errors.ExtensionNotLoaded(name)

        self._remove_module_references(lib.__name__)
        self._call_module_finalizers(lib, name)

    def reload_extension(self, name: str, *, package: Optional[str] = None) -> None:
        """Atomically reloads an extension.

        This replaces the extension with the same extension, only refreshed. This is
        equivalent to a :meth:`unload_extension` followed by a :meth:`load_extension`
        except done in an atomic way. That is, if an operation fails mid-reload then
        the bot will roll-back to the prior working state.

        Parameters
        ----------
        name: :class:`str`
            The extension name to reload. It must be dot separated like
            regular Python imports if accessing a sub-module. e.g.
            ``foo.test`` if you want to import ``foo/test.py``.
        package: Optional[:class:`str`]
            The package name to resolve relative imports with.
            This is required when reloading an extension using a relative path, e.g ``.foo.test``.
            Defaults to ``None``.

            .. versionadded:: 1.7

        Raises
        ------
        ExtensionNotLoaded
            The extension was not loaded.
        ExtensionNotFound
            The extension could not be imported.
            This is also raised if the name of the extension could not
            be resolved using the provided ``package`` parameter.
        NoEntryPointError
            The extension does not have a setup function.
        ExtensionFailed
            The extension setup function had an execution error.
        """
        name = self._resolve_name(name, package)
        lib = self.__extensions.get(name)
        if lib is None:
            raise errors.ExtensionNotLoaded(name)

        # get the previous module states from sys modules
        modules = {
            name: module
            for name, module in sys.modules.items()
            if _is_submodule(lib.__name__, name)
        }

        try:
            # Unload and then load the module...
            self._remove_module_references(lib.__name__)
            self._call_module_finalizers(lib, name)
            self.load_extension(name)
        except Exception:
            # if the load failed, the remnants should have been
            # cleaned from the load_extension function call
            # so let's load it from our old compiled library.
            lib.setup(self)
            self.__extensions[name] = lib

            # revert sys.modules back to normal and raise back to caller
            sys.modules.update(modules)
            raise

    def load_extensions(self, path: str) -> None:
        """Loads all extensions in a directory.

        .. versionadded:: 2.4

        Parameters
        ----------
        path: :class:`str`
            The path to search for extensions
        """
        for extension in disnake.utils.search_directory(path):
            self.load_extension(extension)

    @property
    def extensions(self) -> Mapping[str, types.ModuleType]:
        """Mapping[:class:`str`, :class:`py:types.ModuleType`]: A read-only mapping of extension name to extension."""
        return types.MappingProxyType(self.__extensions)

    async def _watchdog(self) -> None:
        """|coro|

        Starts the bot watchdog which will watch currently loaded extensions
        and reload them when they're modified.
        """
        if isinstance(self, disnake.Client):
            await self.wait_until_ready()

        reload_log = logging.getLogger(__name__)

        if isinstance(self, disnake.Client):
            is_closed = self.is_closed
        else:
            is_closed = lambda: False

        reload_log.info("WATCHDOG: Watching extensions")

        last = time.time()
        while not is_closed():
            t = time.time()

            extensions = set()
            for name, module in self.extensions.items():
                file = module.__file__
                if file and os.stat(file).st_mtime > last:
                    extensions.add(name)

            if extensions:
                try:
                    self.i18n.reload()  # type: ignore
                except Exception as e:
                    reload_log.exception(e)

            for name in extensions:
                try:
                    self.reload_extension(name)
                except errors.ExtensionError as e:
                    reload_log.exception(e)
                else:
                    reload_log.info(f"WATCHDOG: Reloaded '{name}'")

            await asyncio.sleep(1)
            last = t
