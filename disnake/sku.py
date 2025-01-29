# SPDX-License-Identifier: MIT

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from .enums import SKUType, try_enum
from .flags import SKUFlags
from .iterators import SubscriptionIterator
from .mixins import Hashable
from .subscription import Subscription
from .utils import snowflake_time

if TYPE_CHECKING:
    from .abc import Snowflake, SnowflakeTime
    from .state import ConnectionState
    from .types.sku import SKU as SKUPayload


__all__ = ("SKU",)


class SKU(Hashable):
    """Represents an SKU.

    This can be retrieved using :meth:`Client.skus`.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two :class:`SKU`\\s are equal.

        .. describe:: x != y

            Checks if two :class:`SKU`\\s are not equal.

        .. describe:: hash(x)

            Returns the SKU's hash.

        .. describe:: str(x)

            Returns the SKU's name.

    .. versionadded:: 2.10

    Attributes
    ----------
    id: :class:`int`
        The SKU's ID.
    type: :class:`SKUType`
        The SKU's type.
    application_id: :class:`int`
        The parent application's ID.
    name: :class:`str`
        The SKU's name.
    slug: :class:`str`
        The SKU's URL slug, system-generated based on :attr:`name`.
    """

    __slots__ = ("_state", "id", "type", "application_id", "name", "slug", "_flags")

    def __init__(self, *, data: SKUPayload, state: ConnectionState) -> None:
        self._state: ConnectionState = state
        self.id: int = int(data["id"])
        self.type: SKUType = try_enum(SKUType, data["type"])
        self.application_id: int = int(data["application_id"])
        self.name: str = data["name"]
        self.slug: str = data["slug"]
        self._flags: int = data.get("flags", 0)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<SKU id={self.id!r} type={self.type!r} name={self.name!r}>"

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the SKU's creation time in UTC."""
        return snowflake_time(self.id)

    @property
    def flags(self) -> SKUFlags:
        """:class:`SKUFlags`: Returns the SKU's flags."""
        return SKUFlags._from_value(self._flags)

    def subscriptions(
        self,
        user: Snowflake,
        *,
        limit: Optional[int] = 50,
        before: Optional[SnowflakeTime] = None,
        after: Optional[SnowflakeTime] = None,
    ) -> SubscriptionIterator:
        """Retrieves an :class:`.AsyncIterator` that enables receiving subscriptions for the SKU.

        All parameters, except ``user``, are optional.

        Parameters
        ----------
        user: :class:`abc.Snowflake`
            The user to retrieve subscriptions for.
        limit: Optional[:class:`int`]
            The number of subscriptions to retrieve.
            If ``None``, retrieves every subscription.
            Note, however, that this would make it a slow operation.
            Defaults to ``50``.
        before: Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]
            Retrieves subscriptions created before this date or object.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        after: Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]
            Retrieve subscriptions created after this date or object.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.

        Raises
        ------
        HTTPException
            Retrieving the subscriptions failed.

        Yields
        ------
        :class:`.Subscription`
            The subscriptions for the given parameters.
        """
        return SubscriptionIterator(
            self.id,
            state=self._state,
            user_id=user.id,
            limit=limit,
            before=before,
            after=after,
        )

    async def fetch_subscription(self, subscription_id: int, /) -> Subscription:
        """|coro|

        Retrieve a subscription for this SKU given its ID.

        Raises
        ------
        NotFound
            The subscription does not exist.
        HTTPException
            Retrieving the subscription failed.
        """
        data = await self._state.http.get_subscription(self.id, subscription_id)
        return Subscription(data=data, state=self._state)
