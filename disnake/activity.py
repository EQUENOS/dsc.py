# SPDX-License-Identifier: MIT

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Union, overload

from .asset import Asset
from .colour import Colour
from .enums import ActivityType, try_enum
from .partial_emoji import PartialEmoji

__all__ = (
    "BaseActivity",
    "Activity",
    "Streaming",
    "Game",
    "Spotify",
    "CustomActivity",
)

"""If curious, this is the current schema for an activity.

It's fairly long so I will document it here:

All keys are optional.

state: str (max: 128),
details: str (max: 128)
timestamps: dict
    start: int (min: 1)
    end: int (min: 1)
assets: dict
    large_image: str (max: 32)
    large_text: str (max: 128)
    small_image: str (max: 32)
    small_text: str (max: 128)
party: dict
    id: str (max: 128),
    size: List[int] (max-length: 2)
        elem: int (min: 1)
secrets: dict
    match: str (max: 128)
    join: str (max: 128)
    spectate: str (max: 128)
instance: bool
application_id: str
name: str (max: 128)
url: str
type: int
sync_id: str
session_id: str
flags: int
buttons: list[str (max: 32)]

There are also activity flags which are mostly uninteresting for the library atm.

t.ActivityFlags = {
    INSTANCE: 1,
    JOIN: 2,
    SPECTATE: 4,
    JOIN_REQUEST: 8,
    SYNC: 16,
    PLAY: 32
}
"""

if TYPE_CHECKING:
    from .state import ConnectionState
    from .types.activity import (
        Activity as ActivityPayload,
        ActivityAssets,
        ActivityEmoji as ActivityEmojiPayload,
        ActivityParty,
        ActivityTimestamps,
    )
    from .types.emoji import PartialEmoji as PartialEmojiPayload
    from .types.widget import WidgetActivity as WidgetActivityPayload


class _BaseActivity:
    __slots__ = ("_created_at", "_timestamps", "assets")

    def __init__(
        self,
        *,
        created_at: Optional[float] = None,
        timestamps: Optional[ActivityTimestamps] = None,
        assets: Optional[ActivityAssets] = None,
        **kwargs: Any,  # discarded
    ) -> None:
        self._created_at: Optional[float] = created_at
        self._timestamps: ActivityTimestamps = timestamps or {}
        self.assets: ActivityAssets = assets or {}

    @property
    def created_at(self) -> Optional[datetime.datetime]:
        """Optional[:class:`datetime.datetime`]: When the user started doing this activity in UTC.

        .. versionadded:: 1.3
        """
        if self._created_at is not None:
            return datetime.datetime.fromtimestamp(
                self._created_at / 1000, tz=datetime.timezone.utc
            )
        return None

    @property
    def start(self) -> Optional[datetime.datetime]:
        """Optional[:class:`datetime.datetime`]: When the user started doing this activity in UTC, if applicable.

        .. versionchanged:: 2.6
            This attribute can now be ``None``.
        """
        try:
            timestamp = self._timestamps["start"] / 1000
        except KeyError:
            return None
        else:
            return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)

    @property
    def end(self) -> Optional[datetime.datetime]:
        """Optional[:class:`datetime.datetime`]: When the user will stop doing this activity in UTC, if applicable.

        .. versionchanged:: 2.6
            This attribute can now be ``None``.
        """
        try:
            timestamp = self._timestamps["end"] / 1000
        except KeyError:
            return None
        else:
            return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)

    def to_dict(self) -> ActivityPayload:
        raise NotImplementedError


# tag type for user-settable activities
class BaseActivity(_BaseActivity):
    """The base activity that all user-settable activities inherit from.

    A user-settable activity is one that can be used in :meth:`Client.change_presence`.

    The following types currently count as user-settable:

    - :class:`Activity`
    - :class:`Game`
    - :class:`Streaming`
    - :class:`CustomActivity`

    Note that although these types are considered user-settable by the library,
    Discord typically ignores certain combinations of activity depending on
    what is currently set. This behaviour may change in the future so there are
    no guarantees on whether Discord will actually let you set these types.

    .. versionadded:: 1.3
    """

    __slots__ = ()


class Activity(BaseActivity):
    """Represents an activity in Discord.

    This could be an activity such as streaming, playing, listening
    or watching.

    For memory optimisation purposes, some activities are offered in slimmed
    down versions:

    - :class:`Game`
    - :class:`Streaming`

    Parameters
    ----------
    name: Optional[:class:`str`]
        The name of the activity.
    url: Optional[:class:`str`]
        A stream URL that the activity could be doing.
    type: :class:`ActivityType`
        The type of activity currently being done.

    Attributes
    ----------
    application_id: Optional[:class:`int`]
        The application ID of the game.
    name: Optional[:class:`str`]
        The name of the activity.
    url: Optional[:class:`str`]
        A stream URL that the activity could be doing.
    type: :class:`ActivityType`
        The type of activity currently being done.
    state: Optional[:class:`str`]
        The user's current state. For example, "In Game".
    details: Optional[:class:`str`]
        The detail of the user's current activity.
    assets: :class:`dict`
        A dictionary representing the images and their hover text of an activity.
        It contains the following optional keys:

        - ``large_image``: A string representing the ID for the large image asset.
        - ``large_text``: A string representing the text when hovering over the large image asset.
        - ``small_image``: A string representing the ID for the small image asset.
        - ``small_text``: A string representing the text when hovering over the small image asset.
    party: :class:`dict`
        A dictionary representing the activity party. It contains the following optional keys:

        - ``id``: A string representing the party ID.
        - ``size``: A list of two integers denoting (current_size, maximum_size).
    buttons: List[str]
        A list of strings representing the labels of custom buttons shown in a rich presence.

        .. versionadded:: 2.0

        .. versionchanged:: 2.6
            Changed type to ``List[str]`` to match API types.

    emoji: Optional[:class:`PartialEmoji`]
        The emoji that belongs to this activity.
    """

    __slots__ = (
        "state",
        "details",
        "party",
        "flags",
        "type",
        "name",
        "url",
        "application_id",
        "emoji",
        "buttons",
        "id",
        "platform",
        "sync_id",
        "session_id",
    )

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        url: Optional[str] = None,
        type: Optional[Union[ActivityType, int]] = None,
        state: Optional[str] = None,
        details: Optional[str] = None,
        party: Optional[ActivityParty] = None,
        application_id: Optional[Union[str, int]] = None,
        flags: Optional[int] = None,
        buttons: Optional[List[str]] = None,
        emoji: Optional[Union[PartialEmojiPayload, ActivityEmojiPayload]] = None,
        id: Optional[str] = None,
        platform: Optional[str] = None,
        sync_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.state: Optional[str] = state
        self.details: Optional[str] = details
        self.party: ActivityParty = party or {}
        self.application_id: Optional[int] = (
            int(application_id) if application_id is not None else None
        )
        self.name: Optional[str] = name
        self.url: Optional[str] = url
        self.flags: int = flags or 0
        self.buttons: List[str] = buttons or []

        # undocumented fields:
        self.id: Optional[str] = id
        self.platform: Optional[str] = platform
        self.sync_id: Optional[str] = sync_id
        self.session_id: Optional[str] = session_id

        activity_type = type if type is not None else 0
        self.type: ActivityType = (
            activity_type
            if isinstance(activity_type, ActivityType)
            else try_enum(ActivityType, activity_type)
        )

        self.emoji: Optional[PartialEmoji] = (
            PartialEmoji.from_dict(emoji) if emoji is not None else None
        )

    def __repr__(self) -> str:
        attrs = (
            ("type", self.type),
            ("name", self.name),
            ("url", self.url),
            ("details", self.details),
            ("application_id", self.application_id),
            ("session_id", self.session_id),
            ("emoji", self.emoji),
        )
        inner = " ".join(f"{k!s}={v!r}" for k, v in attrs)
        return f"<Activity {inner}>"

    def to_dict(self) -> Dict[str, Any]:
        ret: Dict[str, Any] = {}
        for attr in self.__slots__:
            value = getattr(self, attr, None)
            if value is None:
                continue

            if isinstance(value, dict) and len(value) == 0:
                continue

            ret[attr] = value

        # fix type field
        ret["type"] = int(self.type)

        if self.emoji:
            ret["emoji"] = self.emoji.to_dict()
        # defined in base class slots
        if self._timestamps:
            ret["timestamps"] = self._timestamps
        return ret

    @property
    def large_image_url(self) -> Optional[str]:
        """Optional[:class:`str`]: Returns a URL pointing to the large image asset of this activity, if applicable."""
        if self.application_id is None:
            return None

        try:
            large_image = self.assets["large_image"]
        except KeyError:
            return None
        else:
            return f"{Asset.BASE}/app-assets/{self.application_id}/{large_image}.png"

    @property
    def small_image_url(self) -> Optional[str]:
        """Optional[:class:`str`]: Returns a URL pointing to the small image asset of this activity, if applicable."""
        if self.application_id is None:
            return None

        try:
            small_image = self.assets["small_image"]
        except KeyError:
            return None
        else:
            return f"{Asset.BASE}/app-assets/{self.application_id}/{small_image}.png"

    @property
    def large_image_text(self) -> Optional[str]:
        """Optional[:class:`str`]: Returns the large image asset hover text of this activity, if applicable."""
        return self.assets.get("large_text", None)

    @property
    def small_image_text(self) -> Optional[str]:
        """Optional[:class:`str`]: Returns the small image asset hover text of this activity, if applicable."""
        return self.assets.get("small_text", None)


class Game(BaseActivity):
    """A slimmed down version of :class:`Activity` that represents a Discord game.

    This is typically displayed via **Playing** on the official Discord client.

    .. container:: operations

        .. describe:: x == y

            Checks if two games are equal.

        .. describe:: x != y

            Checks if two games are not equal.

        .. describe:: hash(x)

            Returns the game's hash.

        .. describe:: str(x)

            Returns the game's name.

    Parameters
    ----------
    name: :class:`str`
        The game's name.

    Attributes
    ----------
    name: :class:`str`
        The game's name.
    assets: :class:`dict`
        A dictionary with the same structure as :attr:`Activity.assets`.
    """

    __slots__ = ("name", "platform")

    def __init__(
        self,
        name: str,
        *,
        platform: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.name: str = name

        # undocumented
        self.platform: Optional[str] = platform

    @property
    def type(self) -> Literal[ActivityType.playing]:
        """:class:`ActivityType`: Returns the game's type. This is for compatibility with :class:`Activity`.

        It always returns :attr:`ActivityType.playing`.
        """
        return ActivityType.playing

    def __str__(self) -> str:
        return str(self.name)

    def __repr__(self) -> str:
        return f"<Game name={self.name!r}>"

    def to_dict(self) -> ActivityPayload:
        return {
            "type": ActivityType.playing.value,
            "name": str(self.name),
            "timestamps": self._timestamps,
            "assets": self.assets,
        }

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Game) and other.name == self.name

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self.name)


class Streaming(BaseActivity):
    """A slimmed down version of :class:`Activity` that represents a Discord streaming status.

    This is typically displayed via **Streaming** on the official Discord client.

    .. container:: operations

        .. describe:: x == y

            Checks if two streams are equal.

        .. describe:: x != y

            Checks if two streams are not equal.

        .. describe:: hash(x)

            Returns the stream's hash.

        .. describe:: str(x)

            Returns the stream's name.

    Attributes
    ----------
    platform: Optional[:class:`str`]
        Where the user is streaming from (ie. YouTube, Twitch).

        .. versionadded:: 1.3

    name: Optional[:class:`str`]
        The stream's name.
    details: Optional[:class:`str`]
        An alias for :attr:`name`
    game: Optional[:class:`str`]
        The game being streamed.

        .. versionadded:: 1.3

    url: :class:`str`
        The stream's URL.
    assets: :class:`dict`
        A dictionary with the same structure as :attr:`Activity.assets`.
    """

    __slots__ = ("platform", "name", "game", "url", "details")

    def __init__(
        self,
        *,
        name: Optional[str],
        url: str,
        details: Optional[str] = None,
        state: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.platform: Optional[str] = name
        self.name: Optional[str] = details or name
        self.details: Optional[str] = self.name  # compatibility
        self.url: str = url
        self.game: Optional[str] = state

    @property
    def type(self) -> Literal[ActivityType.streaming]:
        """:class:`ActivityType`: Returns the game's type. This is for compatibility with :class:`Activity`.

        It always returns :attr:`ActivityType.streaming`.
        """
        return ActivityType.streaming

    def __str__(self) -> str:
        return str(self.name)

    def __repr__(self) -> str:
        return f"<Streaming name={self.name!r}>"

    @property
    def twitch_name(self):
        """Optional[:class:`str`]: If provided, the twitch name of the user streaming.

        This corresponds to the ``large_image`` key of the :attr:`Streaming.assets`
        dictionary if it starts with ``twitch:``. Typically set by the Discord client.
        """
        try:
            name = self.assets["large_image"]
        except KeyError:
            return None
        else:
            return name[7:] if name[:7] == "twitch:" else None

    def to_dict(self) -> Dict[str, Any]:
        ret: Dict[str, Any] = {
            "type": ActivityType.streaming.value,
            "name": str(self.name),
            "url": str(self.url),
            "assets": self.assets,
        }
        if self.details:
            ret["details"] = self.details
        return ret

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Streaming) and other.name == self.name and other.url == self.url

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self.name)


class Spotify(_BaseActivity):
    """Represents a Spotify listening activity from Discord.

    .. container:: operations

        .. describe:: x == y

            Checks if two activities are equal.

        .. describe:: x != y

            Checks if two activities are not equal.

        .. describe:: hash(x)

            Returns the activity's hash.

        .. describe:: str(x)

            Returns the string 'Spotify'.
    """

    __slots__ = (
        "_state",
        "_details",
        "_party",
        "_sync_id",
        "_session_id",
    )

    def __init__(
        self,
        *,
        state: Optional[str] = None,
        details: Optional[str] = None,
        party: Optional[ActivityParty] = None,
        sync_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._state: str = state or ""
        self._details: str = details or ""
        self._party: ActivityParty = party or {}
        self._sync_id: str = sync_id or ""
        self._session_id: Optional[str] = session_id

    @property
    def type(self) -> Literal[ActivityType.listening]:
        """:class:`ActivityType`: Returns the activity's type. This is for compatibility with :class:`Activity`.

        It always returns :attr:`ActivityType.listening`.
        """
        return ActivityType.listening

    @property
    def colour(self) -> Colour:
        """:class:`Colour`: Returns the Spotify integration colour, as a :class:`Colour`.

        There is an alias for this named :attr:`color`
        """
        return Colour(0x1DB954)

    @property
    def color(self) -> Colour:
        """:class:`Colour`: Returns the Spotify integration colour, as a :class:`Colour`.

        There is an alias for this named :attr:`colour`
        """
        return self.colour

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flags": 48,  # SYNC | PLAY
            "name": "Spotify",
            "assets": self.assets,
            "party": self._party,
            "sync_id": self._sync_id,
            "session_id": self._session_id,
            "timestamps": self._timestamps,
            "details": self._details,
            "state": self._state,
        }

    @property
    def name(self) -> str:
        """:class:`str`: The activity's name. This will always return "Spotify"."""
        return "Spotify"

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, Spotify)
            and other._session_id == self._session_id
            and other._sync_id == self._sync_id
            and other.start == self.start
        )

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self._session_id)

    def __str__(self) -> str:
        return "Spotify"

    def __repr__(self) -> str:
        return f"<Spotify title={self.title!r} artist={self.artist!r} track_id={self.track_id!r}>"

    @property
    def title(self) -> str:
        """:class:`str`: The title of the song being played."""
        return self._details

    @property
    def artists(self) -> List[str]:
        """List[:class:`str`]: The artists of the song being played."""
        return self._state.split("; ")

    @property
    def artist(self) -> str:
        """:class:`str`: The artist of the song being played.

        This does not attempt to split the artist information into
        multiple artists. Useful if there's only a single artist.
        """
        return self._state

    @property
    def album(self) -> str:
        """:class:`str`: The album that the song being played belongs to."""
        return self.assets.get("large_text", "")

    @property
    def album_cover_url(self) -> str:
        """:class:`str`: The album cover image URL from Spotify's CDN."""
        large_image = self.assets.get("large_image", "")
        if large_image[:8] != "spotify:":
            return ""
        album_image_id = large_image[8:]
        return f"https://i.scdn.co/image/{album_image_id}"

    @property
    def track_id(self) -> str:
        """:class:`str`: The track ID used by Spotify to identify this song."""
        return self._sync_id

    @property
    def track_url(self) -> str:
        """:class:`str`: The track URL to listen on Spotify.

        .. versionadded:: 2.0
        """
        return f"https://open.spotify.com/track/{self.track_id}"

    @property
    def duration(self) -> Optional[datetime.timedelta]:
        """Optional[:class:`datetime.timedelta`]: The duration of the song being played, if applicable.

        .. versionchanged:: 2.6
            This attribute can now be ``None``.
        """
        start, end = self.start, self.end
        if start and end:
            return end - start
        return None

    @property
    def party_id(self) -> str:
        """:class:`str`: The party ID of the listening party."""
        return self._party.get("id", "")


class CustomActivity(BaseActivity):
    """Represents a Custom activity from Discord.

    .. container:: operations

        .. describe:: x == y

            Checks if two activities are equal.

        .. describe:: x != y

            Checks if two activities are not equal.

        .. describe:: hash(x)

            Returns the activity's hash.

        .. describe:: str(x)

            Returns the custom status text.

    .. versionadded:: 1.3

    Attributes
    ----------
    name: Optional[:class:`str`]
        The custom activity's name.
    emoji: Optional[:class:`PartialEmoji`]
        The emoji to pass to the activity, if any.
    """

    __slots__ = ("name", "emoji", "state")

    def __init__(
        self,
        name: Optional[str],
        *,
        emoji: Optional[Union[ActivityEmojiPayload, str, PartialEmoji]] = None,
        state: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.name: Optional[str] = name
        self.state: Optional[str] = state
        if self.name == "Custom Status":
            self.name = self.state

        self.emoji: Optional[PartialEmoji]
        if emoji is None:
            self.emoji = emoji
        elif isinstance(emoji, dict):
            self.emoji = PartialEmoji.from_dict(emoji)
        elif isinstance(emoji, str):
            self.emoji = PartialEmoji(name=emoji)
        elif isinstance(emoji, PartialEmoji):
            self.emoji = emoji
        else:
            raise TypeError(
                f"Expected str, PartialEmoji, or None, received {type(emoji)!r} instead."
            )

    @property
    def type(self) -> Literal[ActivityType.custom]:
        """:class:`ActivityType`: Returns the activity's type. This is for compatibility with :class:`Activity`.

        It always returns :attr:`ActivityType.custom`.
        """
        return ActivityType.custom

    def to_dict(self) -> ActivityPayload:
        o: ActivityPayload
        if self.name == self.state:
            o = {
                "type": ActivityType.custom.value,
                "state": self.name,
                "name": "Custom Status",
            }
        else:
            o = {
                "type": ActivityType.custom.value,
                "name": self.name or "",
            }

        if self.emoji:
            o["emoji"] = self.emoji.to_dict()  # type: ignore
        return o

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, CustomActivity)
            and other.name == self.name
            and other.emoji == self.emoji
        )

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.name, str(self.emoji)))

    def __str__(self) -> str:
        if self.emoji:
            if self.name:
                return f"{self.emoji} {self.name}"
            return str(self.emoji)
        return str(self.name)

    def __repr__(self) -> str:
        return f"<CustomActivity name={self.name!r} emoji={self.emoji!r}>"


ActivityTypes = Union[Activity, Game, CustomActivity, Streaming, Spotify]


@overload
def create_activity(
    data: Union[ActivityPayload, WidgetActivityPayload], *, state: Optional[ConnectionState] = None
) -> ActivityTypes:
    ...


@overload
def create_activity(data: None, *, state: Optional[ConnectionState] = None) -> None:
    ...


def create_activity(
    data: Optional[Union[ActivityPayload, WidgetActivityPayload]],
    *,
    state: Optional[ConnectionState] = None,
) -> Optional[ActivityTypes]:
    if not data:
        return None

    activity: ActivityTypes
    game_type = try_enum(ActivityType, data.get("type", -1))
    if game_type is ActivityType.playing and not ("application_id" in data or "session_id" in data):
        activity = Game(**data)  # type: ignore  # pyright bug(?)
    elif game_type is ActivityType.custom and "name" in data:
        activity = CustomActivity(**data)  # type: ignore
    elif game_type is ActivityType.streaming and "url" in data:
        # url won't be None here
        activity = Streaming(**data)  # type: ignore
    elif game_type is ActivityType.listening and "sync_id" in data and "session_id" in data:
        activity = Spotify(**data)
    else:
        activity = Activity(**data)

    if isinstance(activity, (Activity, CustomActivity)) and activity.emoji and state:
        activity.emoji._state = state

    return activity
