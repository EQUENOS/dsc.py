# SPDX-License-Identifier: MIT

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type

from .enums import ExpireBehaviour, try_enum
from .user import User
from .utils import MISSING, _get_as_snowflake, deprecated, parse_time, warn_deprecated

__all__ = (
    "IntegrationAccount",
    "IntegrationApplication",
    "PartialIntegration",
    "Integration",
    "StreamIntegration",
    "BotIntegration",
)

if TYPE_CHECKING:
    from .guild import Guild
    from .role import Role
    from .types.integration import (
        BotIntegration as BotIntegrationPayload,
        Integration as IntegrationPayload,
        IntegrationAccount as IntegrationAccountPayload,
        IntegrationApplication as IntegrationApplicationPayload,
        IntegrationType,
        PartialIntegration as PartialIntegrationPayload,
        StreamIntegration as StreamIntegrationPayload,
    )


class IntegrationAccount:
    """Represents an integration account.

    .. versionadded:: 1.4

    Attributes
    ----------
    id: :class:`str`
        The account ID.
    name: :class:`str`
        The account name.
    """

    __slots__ = ("id", "name")

    def __init__(self, data: IntegrationAccountPayload) -> None:
        self.id: str = data["id"]
        self.name: str = data["name"]

    def __repr__(self) -> str:
        return f"<IntegrationAccount id={self.id} name={self.name!r}>"


class PartialIntegration:
    """Represents a partial guild integration.

    .. versionadded:: 2.6

    Attributes
    ----------
    id: :class:`int`
        The integration ID.
    name: :class:`str`
        The integration name.
    guild: :class:`Guild`
        The guild of the integration.
    type: :class:`str`
        The integration type (i.e. ``twitch``).
    account: :class:`IntegrationAccount`
        The account linked to this integration.
    application_id: Optional[:class:`int`]
        The ID of the application tied to this integration.
    """

    __slots__ = (
        "guild",
        "id",
        "name",
        "type",
        "account",
        "application_id",
    )

    def __init__(self, *, data: PartialIntegrationPayload, guild: Guild) -> None:
        self.guild = guild
        self._from_data(data)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id} name={self.name!r}>"

    def _from_data(self, data: PartialIntegrationPayload) -> None:
        self.id: int = int(data["id"])
        self.type: IntegrationType = data["type"]
        self.name: str = data["name"]
        self.account: IntegrationAccount = IntegrationAccount(data["account"])
        self.application_id: Optional[int] = _get_as_snowflake(data, "application_id")


class Integration(PartialIntegration):
    """Represents a guild integration.

    .. versionadded:: 1.4

    Attributes
    ----------
    id: :class:`int`
        The integration ID.
    name: :class:`str`
        The integration name.
    guild: :class:`Guild`
        The guild of the integration.
    type: :class:`str`
        The integration type (i.e. Twitch).
    enabled: :class:`bool`
        Whether the integration is currently enabled.
    account: :class:`IntegrationAccount`
        The account linked to this integration.
    user: Optional[:class:`User`]
        The user that added this integration.
    """

    __slots__ = (
        "_state",
        "user",
        "enabled",
    )

    def _from_data(self, data: IntegrationPayload) -> None:
        super()._from_data(data)
        self._state = self.guild._state

        user = data.get("user")
        self.user = User(state=self._state, data=user) if user else None
        self.enabled: bool = data["enabled"]

    @deprecated("Guild.leave")
    async def delete(self, *, reason: Optional[str] = None) -> None:
        """|coro|

        .. deprecated:: 2.5
            Can only be used on the application's own integration and is therefore
            equivalent to leaving the guild.

        Deletes the integration.

        You must have :attr:`~Permissions.manage_guild` permission to
        use this.

        Parameters
        ----------
        reason: Optional[:class:`str`]
            The reason the integration was deleted. Shows up on the audit log.

            .. versionadded:: 2.0

        Raises
        ------
        Forbidden
            You do not have permission to delete the integration.
        HTTPException
            Deleting the integration failed.
        """
        await self._state.http.delete_integration(self.guild.id, self.id, reason=reason)


class StreamIntegration(Integration):
    """Represents a stream integration for Twitch or YouTube.

    .. versionadded:: 2.0

    Attributes
    ----------
    id: :class:`int`
        The integration ID.
    name: :class:`str`
        The integration name.
    guild: :class:`Guild`
        The guild of the integration.
    type: :class:`str`
        The integration type (i.e. Twitch).
    enabled: :class:`bool`
        Whether the integration is currently enabled.
    syncing: :class:`bool`
        Whether the integration is currently syncing.
    enable_emoticons: Optional[:class:`bool`]
        Whether emoticons should be synced for this integration (currently twitch only).
    expire_behaviour: :class:`ExpireBehaviour`
        The behaviour of expiring subscribers. Aliased to ``expire_behavior`` as well.
    expire_grace_period: :class:`int`
        The grace period (in days) for expiring subscribers.
    user: :class:`User`
        The user for the integration.
    account: :class:`IntegrationAccount`
        The integration account information.
    synced_at: :class:`datetime.datetime`
        An aware UTC datetime representing when the integration was last synced.
    """

    __slots__ = (
        "revoked",
        "expire_behaviour",
        "expire_grace_period",
        "synced_at",
        "_role_id",
        "syncing",
        "enable_emoticons",
        "subscriber_count",
    )

    def _from_data(self, data: StreamIntegrationPayload) -> None:
        super()._from_data(data)
        self.revoked: bool = data["revoked"]
        self.expire_behaviour: ExpireBehaviour = try_enum(ExpireBehaviour, data["expire_behavior"])
        self.expire_grace_period: int = data["expire_grace_period"]
        self.synced_at: datetime.datetime = parse_time(data["synced_at"])
        self._role_id: Optional[int] = _get_as_snowflake(data, "role_id")
        self.syncing: bool = data["syncing"]
        self.enable_emoticons: bool = data["enable_emoticons"]
        self.subscriber_count: int = data["subscriber_count"]

    @property
    def expire_behavior(self) -> ExpireBehaviour:
        """:class:`ExpireBehaviour`: An alias for :attr:`expire_behaviour`."""
        return self.expire_behaviour

    @property
    def role(self) -> Optional[Role]:
        """Optional[:class:`Role`] The role which the integration uses for subscribers."""
        return self.guild.get_role(self._role_id)  # type: ignore

    @deprecated()
    async def edit(
        self,
        *,
        expire_behaviour: ExpireBehaviour = MISSING,
        expire_grace_period: int = MISSING,
        enable_emoticons: bool = MISSING,
    ) -> None:
        """|coro|

        .. deprecated:: 2.5
            No longer supported, bots cannot use this endpoint anymore.

        Edits the integration.

        You must have :attr:`~Permissions.manage_guild` permission to
        use this.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Parameters
        ----------
        expire_behaviour: :class:`ExpireBehaviour`
            The behaviour when an integration subscription lapses. Aliased to ``expire_behavior`` as well.
        expire_grace_period: :class:`int`
            The period (in days) where the integration will ignore lapsed subscriptions.
        enable_emoticons: :class:`bool`
            Where emoticons should be synced for this integration (currently twitch only).

        Raises
        ------
        Forbidden
            You do not have permission to edit the integration.
        HTTPException
            Editing the guild failed.
        TypeError
            ``expire_behaviour`` did not receive a :class:`ExpireBehaviour`.
        """
        payload: Dict[str, Any] = {}
        if expire_behaviour is not MISSING:
            if not isinstance(expire_behaviour, ExpireBehaviour):
                raise TypeError("expire_behaviour field must be of type ExpireBehaviour")

            payload["expire_behavior"] = expire_behaviour.value

        if expire_grace_period is not MISSING:
            payload["expire_grace_period"] = expire_grace_period

        if enable_emoticons is not MISSING:
            payload["enable_emoticons"] = enable_emoticons

        # This endpoint is undocumented.
        # Unsure if it returns the data or not as a result
        await self._state.http.edit_integration(self.guild.id, self.id, **payload)

    @deprecated()
    async def sync(self) -> None:
        """|coro|

        .. deprecated:: 2.5
            No longer supported, bots cannot use this endpoint anymore.

        Syncs the integration.

        You must have :attr:`~Permissions.manage_guild` permission to
        use this.

        Raises
        ------
        Forbidden
            You do not have permission to sync the integration.
        HTTPException
            Syncing the integration failed.
        """
        await self._state.http.sync_integration(self.guild.id, self.id)
        self.synced_at = datetime.datetime.now(datetime.timezone.utc)


class IntegrationApplication:
    """Represents an application for a bot integration.

    .. versionadded:: 2.0

    Attributes
    ----------
    id: :class:`int`
        The application's ID.
    name: :class:`str`
        The application's name.
    icon: Optional[:class:`str`]
        The application's icon hash.
    description: :class:`str`
        The application's description. Can be an empty string.
    user: Optional[:class:`User`]
        The bot user associated with this application.
    """

    __slots__ = (
        "id",
        "name",
        "icon",
        "description",
        "_summary",
        "user",
    )

    def __init__(self, *, data: IntegrationApplicationPayload, state) -> None:
        self.id: int = int(data["id"])
        self.name: str = data["name"]
        self.icon: Optional[str] = data["icon"]
        self.description: str = data["description"]
        self._summary: str = data.get("summary", "")
        user = data.get("bot")
        self.user: Optional[User] = User(state=state, data=user) if user else None

    @property
    def summary(self) -> str:
        """:class:`str`: The application's summary. Can be an empty string.

        .. deprecated:: 2.5

            This field is deprecated by discord and is now always blank. Consider using :attr:`.description` instead.
        """
        warn_deprecated(
            "summary is deprecated and will be removed in a future version. Consider using description instead.",
            stacklevel=2,
        )
        return self._summary


class BotIntegration(Integration):
    """Represents a bot integration on Discord.

    .. versionadded:: 2.0

    Attributes
    ----------
    id: :class:`int`
        The integration ID.
    name: :class:`str`
        The integration name.
    guild: :class:`Guild`
        The guild of the integration.
    type: :class:`str`
        The integration type (i.e. Twitch).
    enabled: :class:`bool`
        Whether the integration is currently enabled.
    user: :class:`User`
        The user that added this integration.
    account: :class:`IntegrationAccount`
        The integration account information.
    application: :class:`IntegrationApplication`
        The application tied to this integration.
    scopes: List[:class:`str`]
        The OAuth2 scopes the application has been authorized for.

        .. versionadded:: 2.6
    """

    __slots__ = ("application", "scopes")

    def _from_data(self, data: BotIntegrationPayload) -> None:
        super()._from_data(data)
        self.application: IntegrationApplication = IntegrationApplication(
            data=data["application"], state=self._state
        )
        self.scopes: List[str] = data.get("scopes") or []

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} id={self.id}"
            f" name={self.name!r} scopes={self.scopes!r}>"
        )


def _integration_factory(value: str) -> Tuple[Type[Integration], str]:
    if value == "discord":
        return BotIntegration, value
    if value in ("twitch", "youtube"):
        return StreamIntegration, value
    return Integration, value
