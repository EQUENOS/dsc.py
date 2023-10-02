# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Union

from .colour import Colour
from .iterators import ReactionIterator

__all__ = (
    "Reaction",
    "BurstReaction",
)

if TYPE_CHECKING:
    from .abc import Snowflake
    from .emoji import Emoji
    from .message import Message
    from .partial_emoji import PartialEmoji
    from .types.message import Reaction as ReactionPayload


class Reaction:
    """Represents a reaction to a message.

    Depending on the way this object was created, some of the attributes can
    have a value of ``None``.

    .. container:: operations

        .. describe:: x == y

            Checks if two reactions are equal. This works by checking if the emoji
            is the same. So two messages with the same reaction will be considered
            "equal".

        .. describe:: x != y

            Checks if two reactions are not equal.

        .. describe:: hash(x)

            Returns the reaction's hash.

        .. describe:: str(x)

            Returns the string form of the reaction's emoji.

    Attributes
    ----------
    emoji: Union[:class:`Emoji`, :class:`PartialEmoji`, :class:`str`]
        The reaction emoji. May be a custom emoji, or a unicode emoji.
    count: :class:`int`
        Number of times this reaction was made.
    me: :class:`bool`
        If the user sent this reaction.
    message: :class:`Message`
        The message this reaction belongs to.
    """

    __slots__ = ("message", "count", "emoji", "me")

    def __init__(
        self,
        *,
        message: Message,
        data: ReactionPayload,
        emoji: Optional[Union[PartialEmoji, Emoji, str]] = None,
    ) -> None:
        self.message: Message = message
        # _get_emoji_from_data won't return None
        self.emoji: Union[PartialEmoji, Emoji, str] = emoji or message._state._get_emoji_from_data(  # type: ignore
            data["emoji"]
        )
        self.count: int = data["count_details"].get("normal", 1)
        self.me: bool = data["me"]

    # TODO: typeguard
    def is_custom_emoji(self) -> bool:
        """Whether the emoji is a custom emoji.

        :return type: :class:`bool`
        """
        return not isinstance(self.emoji, str)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, self.__class__) and other.emoji == self.emoji

    def __ne__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return other.emoji != self.emoji
        return True

    def __hash__(self) -> int:
        return hash(self.emoji)

    def __str__(self) -> str:
        return str(self.emoji)

    def __repr__(self) -> str:
        return f"<Reaction emoji={self.emoji!r} me={self.me} count={self.count}>"

    async def remove(self, user: Snowflake) -> None:
        """|coro|

        Removes the reaction by the provided :class:`User` from the message.

        If the reaction is not your own (i.e. ``user`` parameter is not you) then
        the :attr:`~Permissions.manage_messages` permission is needed.

        The ``user`` parameter must represent a user or member and meet
        the :class:`abc.Snowflake` abc.

        Parameters
        ----------
        user: :class:`abc.Snowflake`
            The user or member from which to remove the reaction.

        Raises
        ------
        HTTPException
            Removing the reaction failed.
        Forbidden
            You do not have the proper permissions to remove the reaction.
        NotFound
            The user you specified, or the reaction's message was not found.
        """
        await self.message.remove_reaction(self.emoji, user)

    async def clear(self) -> None:
        """|coro|

        Clears this reaction from the message.

        You need the :attr:`~Permissions.manage_messages` permission to use this.

        .. versionadded:: 1.3

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Raises
        ------
        HTTPException
            Clearing the reaction failed.
        Forbidden
            You do not have the proper permissions to clear the reaction.
        NotFound
            The emoji you specified was not found.
        TypeError
            The emoji parameter is invalid.
        """
        await self.message.clear_reaction(self.emoji)

    def users(
        self, *, limit: Optional[int] = None, after: Optional[Snowflake] = None
    ) -> ReactionIterator:
        """Returns an :class:`AsyncIterator` representing the users that have reacted to the message.

        The ``after`` parameter must represent a member
        and meet the :class:`abc.Snowflake` abc.

        Examples
        --------
        Usage ::

            # We do not actually recommend doing this.
            async for user in reaction.users():
                await channel.send(f'{user} has reacted with {reaction.emoji}!')

        Flattening into a list: ::

            users = await reaction.users().flatten()
            # users is now a list of User...
            winner = random.choice(users)
            await channel.send(f'{winner} has won the raffle.')

        Parameters
        ----------
        limit: Optional[:class:`int`]
            The maximum number of results to return.
            If not provided, returns all the users who
            reacted to the message.
        after: Optional[:class:`abc.Snowflake`]
            For pagination, reactions are sorted by member.

        Raises
        ------
        HTTPException
            Getting the users for the reaction failed.

        Yields
        ------
        Union[:class:`User`, :class:`Member`]
            The member (if retrievable) or the user that has reacted
            to this message. The case where it can be a :class:`Member` is
            in a guild message context. Sometimes it can be a :class:`User`
            if the member has left the guild.
        """
        if not isinstance(self.emoji, str):
            emoji = f"{self.emoji.name}:{self.emoji.id}"
        else:
            emoji = self.emoji

        if limit is None:
            limit = self.count

        return ReactionIterator(
            self.message, emoji, limit, after, type=1 if isinstance(self, BurstReaction) else 0
        )


class BurstReaction(Reaction):
    """Represents a Super reaction to a message.

    .. versionadded:: 2.10

    This class is a subclass of :class:`.Reaction`.

    Depending on the way this object was created, some of the attributes can
    have a value of ``None``.

    .. container:: operations

        .. describe:: x == y

            Checks if two Super reactions are equal. This works by checking if the
            emoji is the same. So two messages with the same reaction will be
            considered "equal".

        .. describe:: x != y

            Checks if two Super reactions are not equal.

        .. describe:: hash(x)

            Returns the Super reaction's hash.

        .. describe:: str(x)

            Returns the string form of the Super reaction's emoji.

    Attributes
    ----------
    emoji: Union[:class:`Emoji`, :class:`PartialEmoji`, :class:`str`]
        The Super reaction emoji. May be a custom emoji, or a unicode emoji.
    count: :class:`int`
        Number of times this Super reaction was made.
    me: :class:`bool`
        If the user sent this Super reaction.
    message: :class:`Message`
        The message this Super reaction belongs to.
    colors: List[:class:`Colour`]
        The list of :class:`Colour` used for Super reaction.
    """

    __slots__ = (
        "_raw_colors",
        "burst_colors",
    )

    def __init__(
        self,
        *,
        message: Message,
        data: ReactionPayload,
        emoji: Optional[Union[PartialEmoji, Emoji, str]] = None,
    ) -> None:
        super().__init__(message=message, data=data, emoji=emoji)
        self.count: int = data["count_details"].get("burst", 1)
        self.me: bool = data["me_burst"]
        self._raw_colors: List[str] = data.get("burst_colors", [])

    def __repr__(self) -> str:
        return f"<BurstReaction emoji={self.emoji!r} me={self.me} count={self.count}>"

    @property
    def colors(self) -> List[Colour]:
        return [Colour(int(c.lstrip("#"), base=16)) for c in self._raw_colors]
