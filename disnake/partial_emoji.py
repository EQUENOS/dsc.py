# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

from . import utils
from .asset import Asset, AssetMixin

__all__ = ("PartialEmoji",)

if TYPE_CHECKING:
    from datetime import datetime

    from typing_extensions import Self

    from .emoji import Emoji
    from .state import ConnectionState
    from .types.activity import ActivityEmoji as ActivityEmojiPayload
    from .types.emoji import Emoji as EmojiPayload, PartialEmoji as PartialEmojiPayload


class _EmojiTag:
    __slots__ = ()

    id: int

    def _to_partial(self) -> PartialEmoji:
        raise NotImplementedError


class PartialEmoji(_EmojiTag, AssetMixin):
    """Represents a "partial" emoji.

    This model will be given in two scenarios:

    - "Raw" data events such as :func:`on_raw_reaction_add`
    - Custom emoji that the bot cannot see from e.g. :attr:`Message.reactions`

    .. container:: operations

        .. describe:: x == y

            Checks if two emoji are the same.

        .. describe:: x != y

            Checks if two emoji are not the same.

        .. describe:: hash(x)

            Return the emoji's hash.

        .. describe:: str(x)

            Returns the emoji rendered for Discord.

    Attributes
    ----------
    name: Optional[:class:`str`]
        The custom emoji name, if applicable, or the unicode codepoint
        of the non-custom emoji. This can be ``None`` if the emoji
        got deleted (e.g. removing a reaction with a deleted emoji).
    animated: :class:`bool`
        Whether the emoji is animated or not.
    id: Optional[:class:`int`]
        The ID of the custom emoji, if applicable.
    """

    __slots__ = ("animated", "name", "id")

    _CUSTOM_EMOJI_RE = re.compile(
        r"<?(?P<animated>a)?:?(?P<name>[A-Za-z0-9\_]+):(?P<id>[0-9]{17,19})>?"
    )

    if TYPE_CHECKING:
        id: Optional[int]

    def __init__(self, *, name: str, animated: bool = False, id: Optional[int] = None) -> None:
        self.animated = animated
        self.name = name
        self.id = id
        self._state = None

    @classmethod
    def from_dict(
        cls, data: Union[PartialEmojiPayload, ActivityEmojiPayload, Dict[str, Any]]
    ) -> Self:
        return cls(
            animated=data.get("animated", False),
            id=utils._get_as_snowflake(data, "id"),
            name=data.get("name") or "",
        )

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Converts a Discord string representation of an emoji to a :class:`PartialEmoji`.

        The formats accepted are:

        - ``a:name:id``
        - ``<a:name:id>``
        - ``name:id``
        - ``<:name:id>``

        If the format does not match then it is assumed to be a unicode emoji.

        .. versionadded:: 2.0

        Parameters
        ----------
        value: :class:`str`
            The string representation of an emoji.

        Returns
        -------
        :class:`PartialEmoji`
            The partial emoji from this string.
        """
        match = cls._CUSTOM_EMOJI_RE.match(value)
        if match is not None:
            groups = match.groupdict()
            animated = bool(groups["animated"])
            emoji_id = int(groups["id"])
            name = groups["name"]
            return cls(name=name, animated=animated, id=emoji_id)

        return cls(name=value, id=None, animated=False)

    def to_dict(self) -> EmojiPayload:
        o: EmojiPayload = {
            "name": self.name,
            "id": self.id,
        }
        if self.animated:
            o["animated"] = self.animated
        return o

    def _to_partial(self) -> PartialEmoji:
        return self

    @classmethod
    def with_state(
        cls,
        state: ConnectionState,
        *,
        name: str,
        animated: bool = False,
        id: Optional[int] = None,
    ) -> Self:
        self = cls(name=name, animated=animated, id=id)
        self._state = state
        return self

    def __str__(self) -> str:
        if self.id is None:
            return self.name
        if self.animated:
            return f"<a:{self.name}:{self.id}>"
        return f"<:{self.name}:{self.id}>"

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} animated={self.animated} name={self.name!r} id={self.id}>"
        )

    def __eq__(self, other: Any) -> bool:
        if self.is_unicode_emoji():
            return isinstance(other, PartialEmoji) and self.name == other.name

        if isinstance(other, _EmojiTag):
            return self.id == other.id
        return False

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.id, self.name))

    def is_custom_emoji(self) -> bool:
        """Whether the partial emoji is a custom non-Unicode emoji.

        :return type: :class:`bool`
        """
        return self.id is not None

    def is_unicode_emoji(self) -> bool:
        """Whether the partial emoji is a Unicode emoji.

        :return type: :class:`bool`
        """
        return self.id is None

    def _as_reaction(self) -> str:
        if self.id is None:
            return self.name
        return f"{self.name}:{self.id}"

    @property
    def created_at(self) -> Optional[datetime]:
        """Optional[:class:`datetime.datetime`]: Returns the emoji's creation time in UTC, or None if it's a Unicode emoji.

        .. versionadded:: 1.6
        """
        if self.id is None:
            return None

        return utils.snowflake_time(self.id)

    @property
    def url(self) -> str:
        """:class:`str`: Returns the URL of the emoji, if it is custom.

        If this isn't a custom emoji then an empty string is returned
        """
        if self.is_unicode_emoji():
            return ""

        fmt = "gif" if self.animated else "png"
        return f"{Asset.BASE}/emojis/{self.id}.{fmt}"

    async def read(self) -> bytes:
        """|coro|

        Retrieves the data of this emoji as a :class:`bytes` object.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Raises
        ------
        TypeError
            The emoji is not a custom emoji.
        DiscordException
            There was no internal connection state.
        HTTPException
            Downloading the asset failed.
        NotFound
            The asset was deleted.

        Returns
        -------
        :class:`bytes`
            The content of the asset.
        """
        if self.is_unicode_emoji():
            raise TypeError("PartialEmoji is not a custom emoji")

        return await super().read()

    # utility method for unusual emoji model in forums
    # (e.g. default reaction, tag emoji)
    @staticmethod
    def _emoji_to_name_id(
        emoji: Optional[Union[str, Emoji, PartialEmoji]]
    ) -> Tuple[Optional[str], Optional[int]]:
        if emoji is None:
            return None, None

        if isinstance(emoji, str):
            emoji = PartialEmoji.from_str(emoji)

        # note: API only supports exactly one of `name` and `id` being set
        if emoji.id:
            return None, emoji.id
        return emoji.name, None
