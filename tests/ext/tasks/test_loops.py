# SPDX-License-Identifier: MIT

import datetime
from typing import Any, Tuple

import pytest

from disnake.ext import commands
from disnake.ext.tasks import LF, Loop, loop


class TestLoops:
    def test_decorator(self) -> None:
        class Cog(commands.Cog):
            @loop(seconds=30, minutes=0, hours=0)
            async def task(self) -> None:
                ...

        for c in (Cog, Cog()):
            assert c.task.seconds == 30

        with pytest.raises(TypeError, match="must be a coroutine"):

            @loop()  # type: ignore
            def task() -> None:
                ...

    def test_mixing_time(self) -> None:
        async def callback() -> None:
            pass

        with pytest.raises(TypeError):
            Loop(callback, seconds=30, time=datetime.time())

        with pytest.raises(TypeError):

            @loop(seconds=30, time=datetime.time())
            async def task() -> None:
                ...

    def test_inheritance(self) -> None:
        class HyperLoop(Loop[LF]):
            def __init__(self, coro: LF, time_tup: Tuple[float, float, float]) -> None:
                s, m, h = time_tup
                super().__init__(coro, seconds=s, minutes=m, hours=h)

            def clone(self):
                instance = type(self)(self.coro, (self._seconds, self._minutes, self._hours))
                instance._time = self._time
                instance.count = self.count
                instance.reconnect = self.reconnect
                instance._before_loop = self._before_loop
                instance._after_loop = self._after_loop
                instance._error = self._error
                instance._injected = self._injected
                return instance

        class WhileTrueLoop:
            def __init__(self, coro: Any) -> None:
                ...

        async def callback() -> None:
            pass

        HyperLoop(callback, (1, 2, 3))

        class Cog(commands.Cog):
            @loop(cls=HyperLoop[Any], time_tup=(1, 2, 3))
            async def task(self) -> None:
                ...

        for c in (Cog, Cog()):
            assert (c.task.seconds, c.task.minutes, c.task.hours) == (1, 2, 3)

        with pytest.raises(TypeError, match="subclass of Loop"):

            @loop(cls=WhileTrueLoop)  # type: ignore
            async def task() -> None:
                ...
