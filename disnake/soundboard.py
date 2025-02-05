# SPDX-License-Identifier: MIT

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from .asset import Asset, AssetMixin
from .mixins import Hashable
from .partial_emoji import PartialEmoji
from .utils import MISSING, _get_as_snowflake, snowflake_time

if TYPE_CHECKING:
    from .emoji import Emoji
    from .guild import Guild
    from .state import ConnectionState
    from .types.soundboard import (
        GuildSoundboardSound as GuildSoundboardSoundPayload,
        PartialSoundboardSound as PartialSoundboardSoundPayload,
        SoundboardSound as SoundboardSoundPayload,
    )
    from .user import User


__all__ = (
    "PartialSoundboardSound",
    "SoundboardSound",
    "GuildSoundboardSound",
)


class PartialSoundboardSound(Hashable, AssetMixin):
    """Represents a partial soundboard sound.

    Used for sounds in :class:`VoiceChannelEffect`\\s,
    and as the base for full :class:`SoundboardSound`/:class:`GuildSoundboardSound` objects.

    .. versionadded:: 2.10

    .. collapse:: operations

        .. describe:: x == y

            Checks if two soundboard sounds are equal.

        .. describe:: x != y

            Checks if two soundboard sounds are not equal.

        .. describe:: hash(x)

            Returns the soundboard sounds' hash.

    Attributes
    ----------
    id: :class:`int`
        The sound's ID.
    volume: :class:`float`
        The sound's volume (from ``0.0`` to ``1.0``).
    """

    __slots__ = (
        "id",
        "volume",
    )

    def __init__(
        self,
        *,
        data: PartialSoundboardSoundPayload,
        state: Optional[ConnectionState] = None,
    ) -> None:
        self._state = state
        self.id: int = int(data["sound_id"])
        self.volume: float = data["volume"]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id!r}>"

    @property
    def created_at(self) -> Optional[datetime.datetime]:
        """Optional[:class:`datetime.datetime`]: Returns the sound's creation time in UTC.
        Can be ``None`` if this is a default sound.
        """
        if self.is_default():
            return None
        return snowflake_time(self.id)

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a string that allows you to mention the given soundboard sound.

        .. versionadded:: 2.11
        """
        return f"<sound:0:{self.id}>"

    @property
    def url(self) -> str:
        """:class:`str`: The url for the sound file."""
        return f"{Asset.BASE}/soundboard-sounds/{self.id}"

    def is_default(self) -> bool:
        """Whether the sound is a default sound provided by Discord.

        :return type: :class:`bool`
        """
        # default sounds have IDs starting from 1, i.e. tiny numbers compared to real snowflakes.
        # assume any "snowflake" with a zero timestamp is for a default sound
        return (self.id >> 22) == 0


class SoundboardSound(PartialSoundboardSound):
    """Represents a soundboard sound.

    .. versionadded:: 2.10

    .. collapse:: operations

        .. describe:: x == y

            Checks if two soundboard sounds are equal.

        .. describe:: x != y

            Checks if two soundboard sounds are not equal.

        .. describe:: hash(x)

            Returns the soundboard sounds' hash.

    Attributes
    ----------
    id: :class:`int`
        The sound's ID.
    volume: :class:`float`
        The sound's volume (from ``0.0`` to ``1.0``).
    name: :class:`str`
        The sound's name.
    emoji: Optional[Union[:class:`Emoji`, :class:`PartialEmoji`]]
        The sound's emoji, if any.
        Due to a Discord limitation, this will have an empty
        :attr:`~PartialEmoji.name` if it is a custom :class:`PartialEmoji`.
    available: :class:`bool`
        Whether this sound is available for use.
    """

    __slots__ = ("name", "emoji", "available")

    _state: ConnectionState

    def __init__(
        self,
        *,
        data: SoundboardSoundPayload,
        state: ConnectionState,
    ) -> None:
        super().__init__(data=data, state=state)

        self.name: str = data["name"]
        self.emoji: Optional[Union[Emoji, PartialEmoji]] = self._state._get_emoji_from_fields(
            name=data.get("emoji_name"),
            id=_get_as_snowflake(data, "emoji_id"),
        )
        self.available: bool = data.get("available", True)

    def __repr__(self) -> str:
        return f"<SoundboardSound id={self.id!r} name={self.name!r}>"


class GuildSoundboardSound(SoundboardSound):
    """Represents a soundboard sound that belongs to a guild.

    .. versionadded:: 2.10

    .. collapse:: operations

        .. describe:: x == y

            Checks if two soundboard sounds are equal.

        .. describe:: x != y

            Checks if two soundboard sounds are not equal.

        .. describe:: hash(x)

            Returns the soundboard sounds' hash.

    Attributes
    ----------
    id: :class:`int`
        The sound's ID.
    volume: :class:`float`
        The sound's volume (from ``0.0`` to ``1.0``).
    name: :class:`str`
        The sound's name.
    emoji: Optional[Union[:class:`Emoji`, :class:`PartialEmoji`]]
        The sound's emoji, if any.
        Due to a Discord limitation, this will have an empty
        :attr:`~PartialEmoji.name` if it is a custom :class:`PartialEmoji`.
    guild_id: :class:`int`
        The ID of the guild this sound belongs to.
    available: :class:`bool`
        Whether this sound is available for use.
    user: Optional[:class:`User`]
        The user that created this sound. This can only be retrieved using
        :meth:`Guild.fetch_soundboard_sound`/:meth:`Guild.fetch_soundboard_sounds` while
        having the :attr:`~Permissions.create_guild_expressions` or
        :attr:`~Permissions.manage_guild_expressions` permission.
    """

    __slots__ = ("guild_id", "user")

    def __init__(
        self,
        *,
        data: GuildSoundboardSoundPayload,
        state: ConnectionState,
        # `guild_id` isn't sent over REST, so we manually keep track of it
        guild_id: int,
    ) -> None:
        super().__init__(data=data, state=state)

        self.guild_id: int = guild_id
        self.user: Optional[User] = (
            state.store_user(user_data) if (user_data := data.get("user")) is not None else None
        )

    def __repr__(self) -> str:
        return (
            f"<GuildSoundboardSound id={self.id!r} name={self.name!r}"
            f" guild_id={self.guild_id!r} user={self.user!r}>"
        )

    @property
    def guild(self) -> Guild:
        """:class:`Guild`: The guild that this sound is from."""
        # this will most likely never return None
        return self._state._get_guild(self.guild_id)  # type: ignore

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a string that allows you to mention the given soundboard sound.

        .. versionadded:: 2.11
        """
        if self.is_default():
            return super().mention
        return f"<sound:{self.guild_id}:{self.id}>"

    async def edit(
        self,
        *,
        name: str = MISSING,
        volume: float = MISSING,
        emoji: Optional[Union[str, Emoji, PartialEmoji]] = MISSING,
        reason: Optional[str] = None,
    ) -> GuildSoundboardSound:
        """|coro|

        Edits a :class:`GuildSoundboardSound` for the guild.

        You must have :attr:`~Permissions.manage_guild_expressions` permission to
        do this.
        If this sound was created by you, :attr:`~Permissions.create_guild_expressions`
        permission is also sufficient.

        All fields are optional.

        Parameters
        ----------
        name: :class:`str`
            The sounds's new name. Must be at least 2 characters.
        volume: :class:`float`
            The sound's new volume (from ``0.0`` to ``1.0``).
        emoji: Optional[Union[:class:`str`, :class:`Emoji`, :class:`PartialEmoji`]]
            The sound's new emoji. Can be ``None``.
        reason: Optional[:class:`str`]
            The reason for editing this sound. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You are not allowed to edit this soundboard sound.
        HTTPException
            An error occurred editing the soundboard sound.

        Returns
        -------
        :class:`GuildSoundboardSound`
            The newly modified soundboard sound.
        """
        payload: Dict[str, Any] = {}

        if name is not MISSING:
            payload["name"] = name
        if volume is not MISSING:
            payload["volume"] = volume
        if emoji is not MISSING:
            emoji_name, emoji_id = PartialEmoji._emoji_to_name_id(emoji)
            payload["emoji_name"] = emoji_name
            payload["emoji_id"] = emoji_id

        data = await self._state.http.edit_guild_soundboard_sound(
            self.guild_id, self.id, reason=reason, **payload
        )
        return GuildSoundboardSound(data=data, state=self._state, guild_id=self.guild_id)

    async def delete(self, *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes the :class:`GuildSoundboardSound` from the guild.

        You must have :attr:`~Permissions.manage_guild_expressions` permission to
        do this.
        If this sound was created by you, :attr:`~Permissions.create_guild_expressions`
        permission is also sufficient.

        Parameters
        ----------
        reason: Optional[:class:`str`]
            The reason for deleting this sound. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You are not allowed to delete this soundboard sound.
        HTTPException
            An error occurred deleting the soundboard sound.
        """
        await self._state.http.delete_guild_soundboard_sound(self.guild_id, self.id, reason=reason)
