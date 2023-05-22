# SPDX-License-Identifier: MIT

import asyncio
import datetime
import functools
import types
from typing import TYPE_CHECKING, Callable, ContextManager, Optional, Type, TypeVar
from unittest import mock

if TYPE_CHECKING:
    # for pyright
    from typing_extensions import reveal_type as reveal_type
else:
    # to avoid flake8 noqas
    def reveal_type(*args, **kwargs) -> None:
        raise RuntimeError


CallableT = TypeVar("CallableT", bound=Callable)


class freeze_time(ContextManager):
    """Helper class that freezes time at the given datetime by patching `datetime.now`.
    If no datetime is provided, defaults to the current time.
    Can be used as a sync context manager or decorator for sync/async functions.
    """

    # i know `freezegun` exists, but it's rather complex and does much more than
    # we really need here, and I'm unsure if it would interfere with `looptime`

    def __init__(self, dt: Optional[datetime.datetime] = None) -> None:
        dt = dt or datetime.datetime.now(datetime.timezone.utc)
        assert dt.tzinfo

        def fake_now(tz=None):
            return dt.astimezone(tz).replace(tzinfo=tz)

        self.mock_datetime = mock.MagicMock(wraps=datetime.datetime)
        self.mock_datetime.now = fake_now

    def __enter__(self) -> mock.MagicMock:
        self._mock = mock.patch.object(datetime, "datetime", self.mock_datetime)
        return type(self._mock).__enter__(self._mock)

    def __exit__(
        self,
        typ: Optional[Type[BaseException]],
        value: Optional[BaseException],
        tb: Optional[types.TracebackType],
    ) -> Optional[bool]:
        return type(self._mock).__exit__(self._mock, typ, value, tb)

    def __call__(self, func: CallableT) -> CallableT:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrap_async(*args, **kwargs):
                with self:
                    return await func(*args, **kwargs)

            return wrap_async  # type: ignore

        else:  # noqa: RET505

            @functools.wraps(func)
            def wrap_sync(*args, **kwargs):
                with self:
                    return func(*args, **kwargs)

            return wrap_sync  # type: ignore
