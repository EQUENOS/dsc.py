# SPDX-License-Identifier: MIT

from __future__ import annotations

import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sized,
    Union,
    cast,
    overload,
)

from . import utils
from .colour import Colour
from .file import File
from .utils import MISSING, classproperty, warn_deprecated

__all__ = ("Embed",)


# backwards compatibility, hidden from type-checkers to have them show errors when accessed
if not TYPE_CHECKING:

    def __getattr__(name: str) -> None:
        if name == "EmptyEmbed":
            warn_deprecated(
                "`EmptyEmbed` is deprecated and will be removed in a future version. Use `None` instead.",
                stacklevel=2,
            )
            return None
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


class EmbedProxy:
    def __init__(self, layer: Optional[Mapping[str, Any]]) -> None:
        if layer is not None:
            self.__dict__.update(layer)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __repr__(self) -> str:
        inner = ", ".join((f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_")))
        return f"EmbedProxy({inner})"

    def __getattr__(self, attr: str) -> None:
        return None

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, EmbedProxy) and self.__dict__ == other.__dict__


if TYPE_CHECKING:
    from typing_extensions import Self

    from disnake.types.embed import (
        Embed as EmbedData,
        EmbedAuthor as EmbedAuthorPayload,
        EmbedField as EmbedFieldPayload,
        EmbedFooter as EmbedFooterPayload,
        EmbedImage as EmbedImagePayload,
        EmbedProvider as EmbedProviderPayload,
        EmbedThumbnail as EmbedThumbnailPayload,
        EmbedType,
        EmbedVideo as EmbedVideoPayload,
    )

    class _EmbedFooterProxy(Sized, Protocol):
        text: Optional[str]
        icon_url: Optional[str]
        proxy_icon_url: Optional[str]

    class _EmbedFieldProxy(Sized, Protocol):
        name: Optional[str]
        value: Optional[str]
        inline: Optional[bool]

    class _EmbedMediaProxy(Sized, Protocol):
        url: Optional[str]
        proxy_url: Optional[str]
        height: Optional[int]
        width: Optional[int]

    class _EmbedVideoProxy(Sized, Protocol):
        url: Optional[str]
        proxy_url: Optional[str]
        height: Optional[int]
        width: Optional[int]

    class _EmbedProviderProxy(Sized, Protocol):
        name: Optional[str]
        url: Optional[str]

    class _EmbedAuthorProxy(Sized, Protocol):
        name: Optional[str]
        url: Optional[str]
        icon_url: Optional[str]
        proxy_icon_url: Optional[str]

    _FileKey = Literal["image", "thumbnail"]


class Embed:
    """Represents a Discord embed.

    .. container:: operations

        .. describe:: x == y

            Checks if two embeds are equal.

            .. versionadded:: 2.6

        .. describe:: x != y

            Checks if two embeds are not equal.

            .. versionadded:: 2.6

        .. describe:: len(x)

            Returns the total size of the embed.
            Useful for checking if it's within the 6000 character limit.
            Check if all aspects of the embed are within the limits with :func:`Embed.check_limits`.

        .. describe:: bool(b)

            Returns whether the embed has any data set.

            .. versionadded:: 2.0

    Certain properties return an ``EmbedProxy``, a type
    that acts similar to a regular :class:`dict` except using dotted access,
    e.g. ``embed.author.icon_url``.

    For ease of use, all parameters that expect a :class:`str` are implicitly
    cast to :class:`str` for you.

    Attributes
    ----------
    title: Optional[:class:`str`]
        The title of the embed.
    type: Optional[:class:`str`]
        The type of embed. Usually "rich".
        Possible strings for embed types can be found on Discord's
        :ddocs:`api-docs <resources/channel#embed-object-embed-types>`.
    description: Optional[:class:`str`]
        The description of the embed.
    url: Optional[:class:`str`]
        The URL of the embed.
    timestamp: Optional[:class:`datetime.datetime`]
        The timestamp of the embed content. This is an aware datetime.
        If a naive datetime is passed, it is converted to an aware
        datetime with the local timezone.
    colour: Optional[:class:`Colour`]
        The colour code of the embed. Aliased to ``color`` as well.
        In addition to :class:`Colour`, :class:`int` can also be assigned to it,
        in which case the value will be converted to a :class:`Colour` object.
    """

    __slots__ = (
        "title",
        "url",
        "type",
        "_timestamp",
        "_colour",
        "_footer",
        "_image",
        "_thumbnail",
        "_video",
        "_provider",
        "_author",
        "_fields",
        "description",
        "_files",
    )

    _default_colour: ClassVar[Optional[Colour]] = None
    _colour: Optional[Colour]

    def __init__(
        self,
        *,
        title: Optional[Any] = None,
        type: Optional[EmbedType] = "rich",
        description: Optional[Any] = None,
        url: Optional[Any] = None,
        timestamp: Optional[datetime.datetime] = None,
        colour: Optional[Union[int, Colour]] = MISSING,
        color: Optional[Union[int, Colour]] = MISSING,
    ) -> None:
        self.title: Optional[str] = str(title) if title is not None else None
        self.type: Optional[EmbedType] = type
        self.description: Optional[str] = str(description) if description is not None else None
        self.url: Optional[str] = str(url) if url is not None else None

        self.timestamp = timestamp

        # possible values:
        # - MISSING: embed color will be _default_color
        # - None: embed color will not be set
        # - Color: embed color will be set to specified color
        if colour is not MISSING:
            color = colour
        self.colour = color

        self._thumbnail: Optional[EmbedThumbnailPayload] = None
        self._video: Optional[EmbedVideoPayload] = None
        self._provider: Optional[EmbedProviderPayload] = None
        self._author: Optional[EmbedAuthorPayload] = None
        self._image: Optional[EmbedImagePayload] = None
        self._footer: Optional[EmbedFooterPayload] = None
        self._fields: Optional[List[EmbedFieldPayload]] = None

        self._files: Dict[_FileKey, File] = {}

    # see `EmptyEmbed` above
    if not TYPE_CHECKING:

        @classproperty
        def Empty(self) -> None:
            warn_deprecated(
                "`Embed.Empty` is deprecated and will be removed in a future version. Use `None` instead.",
                stacklevel=3,
            )
            return None

    @classmethod
    def from_dict(cls, data: EmbedData) -> Self:
        """Converts a :class:`dict` to a :class:`Embed` provided it is in the
        format that Discord expects it to be in.

        You can find out about this format in the
        :ddocs:`official Discord documentation <resources/channel#embed-object>`.

        Parameters
        ----------
        data: :class:`dict`
            The dictionary to convert into an embed.
        """
        # we are bypassing __init__ here since it doesn't apply here
        self = cls.__new__(cls)

        # fill in the basic fields

        self.title = str(title) if (title := data.get("title")) is not None else None
        self.type = data.get("type")
        self.description = (
            str(description) if (description := data.get("description")) is not None else None
        )
        self.url = str(url) if (url := data.get("url")) is not None else None

        self._files = {}

        # try to fill in the more rich fields

        self.colour = data.get("color")
        self.timestamp = utils.parse_time(data.get("timestamp"))

        self._thumbnail = data.get("thumbnail")
        self._video = data.get("video")
        self._provider = data.get("provider")
        self._author = data.get("author")
        self._image = data.get("image")
        self._footer = data.get("footer")
        self._fields = data.get("fields")

        return self

    def copy(self) -> Self:
        """Returns a shallow copy of the embed."""
        embed = type(self).from_dict(self.to_dict())

        # assign manually to keep behavior of default colors
        embed._colour = self._colour

        # copy files and fields collections
        embed._files = self._files.copy()
        if self._fields is not None:
            embed._fields = self._fields.copy()

        return embed

    def __len__(self) -> int:
        total = len((self.title or "").strip()) + len((self.description or "").strip())
        if self._fields:
            for field in self._fields:
                total += len(field["name"].strip()) + len(field["value"].strip())

        if self._footer and (footer_text := self._footer.get("text")):
            total += len(footer_text.strip())

        if self._author and (author_name := self._author.get("name")):
            total += len(author_name.strip())

        return total

    def __bool__(self) -> bool:
        return any(
            (
                self.title,
                self.url,
                self.description,
                self._colour,
                self._fields,
                self._timestamp,
                self._author,
                self._thumbnail,
                self._footer,
                self._image,
                self._provider,
                self._video,
            )
        )

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Embed):
            return False
        for slot in self.__slots__:
            if slot == "_colour":
                slot = "color"
            if (getattr(self, slot) or None) != (getattr(other, slot) or None):
                return False
        return True

    @property
    def colour(self) -> Optional[Colour]:
        col = self._colour
        return col if col is not MISSING else type(self)._default_colour

    @colour.setter
    def colour(self, value: Optional[Union[int, Colour]]) -> None:
        if isinstance(value, int):
            self._colour = Colour(value=value)
        elif value is MISSING or value is None or isinstance(value, Colour):
            self._colour = value
        else:
            raise TypeError(
                f"Expected disnake.Colour, int, or None but received {type(value).__name__} instead."
            )

    @colour.deleter
    def colour(self) -> None:
        self._colour = MISSING

    color = colour

    @property
    def timestamp(self) -> Optional[datetime.datetime]:
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value: Optional[datetime.datetime]) -> None:
        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                value = value.astimezone()
            self._timestamp = value
        elif value is None:
            self._timestamp = value
        else:
            raise TypeError(
                f"Expected datetime.datetime or None received {type(value).__name__} instead"
            )

    @property
    def footer(self) -> _EmbedFooterProxy:
        """Returns an ``EmbedProxy`` denoting the footer contents.

        Possible attributes you can access are:

        - ``text``
        - ``icon_url``
        - ``proxy_icon_url``

        If an attribute is not set, it will be ``None``.
        """
        return cast("_EmbedFooterProxy", EmbedProxy(self._footer))

    def set_footer(self, *, text: Any, icon_url: Optional[Any] = None) -> Self:
        """Sets the footer for the embed content.

        This function returns the class instance to allow for fluent-style
        chaining.

        Parameters
        ----------
        text: :class:`str`
            The footer text.

            .. versionchanged:: 2.6
                No longer optional, must be set to a valid string.

        icon_url: Optional[:class:`str`]
            The URL of the footer icon. Only HTTP(S) is supported.
        """
        self._footer = {
            "text": str(text),
        }

        if icon_url is not None:
            self._footer["icon_url"] = str(icon_url)

        return self

    def remove_footer(self) -> Self:
        """Clears embed's footer information.

        This function returns the class instance to allow for fluent-style
        chaining.

        .. versionadded:: 2.0
        """
        self._footer = None
        return self

    @property
    def image(self) -> _EmbedMediaProxy:
        """Returns an ``EmbedProxy`` denoting the image contents.

        Possible attributes you can access are:

        - ``url``
        - ``proxy_url``
        - ``width``
        - ``height``

        If an attribute is not set, it will be ``None``.
        """
        return cast("_EmbedMediaProxy", EmbedProxy(self._image))

    @overload
    def set_image(self, url: Optional[Any]) -> Self:
        ...

    @overload
    def set_image(self, *, file: File) -> Self:
        ...

    def set_image(self, url: Optional[Any] = MISSING, *, file: File = MISSING) -> Self:
        """Sets the image for the embed content.

        This function returns the class instance to allow for fluent-style
        chaining.

        Exactly one of ``url`` or ``file`` must be passed.

        .. warning::
            Passing a :class:`disnake.File` object will make the embed not
            reusable.

        .. versionchanged:: 1.4
            Passing ``None`` removes the image.

        Parameters
        ----------
        url: Optional[:class:`str`]
            The source URL for the image. Only HTTP(S) is supported.
        file: :class:`File`
            The file to use as the image.

            .. versionadded:: 2.2
        """
        result = self._handle_resource(url, file, key="image")
        self._image = {"url": result} if result is not None else None
        return self

    @property
    def thumbnail(self) -> _EmbedMediaProxy:
        """Returns an ``EmbedProxy`` denoting the thumbnail contents.

        Possible attributes you can access are:

        - ``url``
        - ``proxy_url``
        - ``width``
        - ``height``

        If an attribute is not set, it will be ``None``.
        """
        return cast("_EmbedMediaProxy", EmbedProxy(self._thumbnail))

    @overload
    def set_thumbnail(self, url: Optional[Any]) -> Self:
        ...

    @overload
    def set_thumbnail(self, *, file: File) -> Self:
        ...

    def set_thumbnail(self, url: Optional[Any] = MISSING, *, file: File = MISSING) -> Self:
        """Sets the thumbnail for the embed content.

        This function returns the class instance to allow for fluent-style
        chaining.

        Exactly one of ``url`` or ``file`` must be passed.

        .. warning::
            Passing a :class:`disnake.File` object will make the embed not
            reusable.

        .. versionchanged:: 1.4
            Passing ``None`` removes the thumbnail.

        Parameters
        ----------
        url: Optional[:class:`str`]
            The source URL for the thumbnail. Only HTTP(S) is supported.
        file: :class:`File`
            The file to use as the image.

            .. versionadded:: 2.2
        """
        result = self._handle_resource(url, file, key="thumbnail")
        self._thumbnail = {"url": result} if result is not None else None
        return self

    @property
    def video(self) -> _EmbedVideoProxy:
        """Returns an ``EmbedProxy`` denoting the video contents.

        Possible attributes include:

        - ``url`` for the video URL.
        - ``proxy_url`` for the proxied video URL.
        - ``height`` for the video height.
        - ``width`` for the video width.

        If an attribute is not set, it will be ``None``.
        """
        return cast("_EmbedVideoProxy", EmbedProxy(self._video))

    @property
    def provider(self) -> _EmbedProviderProxy:
        """Returns an ``EmbedProxy`` denoting the provider contents.

        The only attributes that might be accessed are ``name`` and ``url``.

        If an attribute is not set, it will be ``None``.
        """
        return cast("_EmbedProviderProxy", EmbedProxy(self._provider))

    @property
    def author(self) -> _EmbedAuthorProxy:
        """Returns an ``EmbedProxy`` denoting the author contents.

        See :meth:`set_author` for possible values you can access.

        If an attribute is not set, it will be ``None``.
        """
        return cast("_EmbedAuthorProxy", EmbedProxy(self._author))

    def set_author(
        self,
        *,
        name: Any,
        url: Optional[Any] = None,
        icon_url: Optional[Any] = None,
    ) -> Self:
        """Sets the author for the embed content.

        This function returns the class instance to allow for fluent-style
        chaining.

        Parameters
        ----------
        name: :class:`str`
            The name of the author.
        url: Optional[:class:`str`]
            The URL for the author.
        icon_url: Optional[:class:`str`]
            The URL of the author icon. Only HTTP(S) is supported.
        """
        self._author = {
            "name": str(name),
        }

        if url is not None:
            self._author["url"] = str(url)

        if icon_url is not None:
            self._author["icon_url"] = str(icon_url)

        return self

    def remove_author(self) -> Self:
        """Clears embed's author information.

        This function returns the class instance to allow for fluent-style
        chaining.

        .. versionadded:: 1.4
        """
        self._author = None
        return self

    @property
    def fields(self) -> List[_EmbedFieldProxy]:
        """List[``EmbedProxy``]: Returns a :class:`list` of ``EmbedProxy`` denoting the field contents.

        See :meth:`add_field` for possible values you can access.

        If an attribute is not set, it will be ``None``.
        """
        return cast("List[_EmbedFieldProxy]", [EmbedProxy(d) for d in (self._fields or [])])

    def add_field(self, name: Any, value: Any, *, inline: bool = True) -> Self:
        """Adds a field to the embed object.

        This function returns the class instance to allow for fluent-style
        chaining.

        Parameters
        ----------
        name: :class:`str`
            The name of the field.
        value: :class:`str`
            The value of the field.
        inline: :class:`bool`
            Whether the field should be displayed inline.
            Defaults to ``True``.
        """
        field: EmbedFieldPayload = {
            "inline": inline,
            "name": str(name),
            "value": str(value),
        }

        if self._fields is not None:
            self._fields.append(field)
        else:
            self._fields = [field]

        return self

    def insert_field_at(self, index: int, name: Any, value: Any, *, inline: bool = True) -> Self:
        """Inserts a field before a specified index to the embed.

        This function returns the class instance to allow for fluent-style
        chaining.

        .. versionadded:: 1.2

        Parameters
        ----------
        index: :class:`int`
            The index of where to insert the field.
        name: :class:`str`
            The name of the field.
        value: :class:`str`
            The value of the field.
        inline: :class:`bool`
            Whether the field should be displayed inline.
            Defaults to ``True``.
        """
        field: EmbedFieldPayload = {
            "inline": inline,
            "name": str(name),
            "value": str(value),
        }

        if self._fields is not None:
            self._fields.insert(index, field)
        else:
            self._fields = [field]

        return self

    def clear_fields(self) -> None:
        """Removes all fields from this embed."""
        self._fields = None

    def remove_field(self, index: int) -> None:
        """Removes a field at a specified index.

        If the index is invalid or out of bounds then the error is
        silently swallowed.

        .. note::

            When deleting a field by index, the index of the other fields
            shift to fill the gap just like a regular list.

        Parameters
        ----------
        index: :class:`int`
            The index of the field to remove.
        """
        if self._fields is not None:
            try:
                del self._fields[index]
            except IndexError:
                pass

    def set_field_at(self, index: int, name: Any, value: Any, *, inline: bool = True) -> Self:
        """Modifies a field to the embed object.

        The index must point to a valid pre-existing field.

        This function returns the class instance to allow for fluent-style
        chaining.

        Parameters
        ----------
        index: :class:`int`
            The index of the field to modify.
        name: :class:`str`
            The name of the field.
        value: :class:`str`
            The value of the field.
        inline: :class:`bool`
            Whether the field should be displayed inline.
            Defaults to ``True``.

        Raises
        ------
        IndexError
            An invalid index was provided.
        """
        if not self._fields:
            raise IndexError("field index out of range")
        try:
            self._fields[index]
        except IndexError:
            raise IndexError("field index out of range") from None

        field: EmbedFieldPayload = {
            "inline": inline,
            "name": str(name),
            "value": str(value),
        }
        self._fields[index] = field
        return self

    def to_dict(self) -> EmbedData:
        """Converts this embed object into a dict."""
        # add in the raw data into the dict
        result: EmbedData = {}
        if self._footer is not None:
            result["footer"] = self._footer
        if self._image is not None:
            result["image"] = self._image
        if self._thumbnail is not None:
            result["thumbnail"] = self._thumbnail
        if self._video is not None:
            result["video"] = self._video
        if self._provider is not None:
            result["provider"] = self._provider
        if self._author is not None:
            result["author"] = self._author
        if self._fields is not None:
            result["fields"] = self._fields

        # deal with basic convenience wrappers
        if self.colour:
            result["color"] = self.colour.value

        if self._timestamp:
            result["timestamp"] = utils.isoformat_utc(self._timestamp)

        # add in the non raw attribute ones
        if self.type:
            result["type"] = self.type

        if self.description:
            result["description"] = self.description

        if self.url:
            result["url"] = self.url

        if self.title:
            result["title"] = self.title

        return result

    @classmethod
    def set_default_colour(cls, value: Optional[Union[int, Colour]]):
        """Set the default colour of all new embeds.

        .. versionadded:: 2.4

        Returns
        -------
        Optional[:class:`Colour`]
            The colour that was set.
        """
        if value is None or isinstance(value, Colour):
            cls._default_colour = value
        elif isinstance(value, int):
            cls._default_colour = Colour(value=value)
        else:
            raise TypeError(
                f"Expected disnake.Colour, int, or None but received {type(value).__name__} instead."
            )
        return cls._default_colour

    set_default_color = set_default_colour

    @classmethod
    def get_default_colour(cls) -> Optional[Colour]:
        """Get the default colour of all new embeds.

        .. versionadded:: 2.4

        Returns
        -------
        Optional[:class:`Colour`]
            The default colour.

        """
        return cls._default_colour

    get_default_color = get_default_colour

    def _handle_resource(self, url: Optional[Any], file: File, *, key: _FileKey) -> Optional[str]:
        if not (url is MISSING) ^ (file is MISSING):
            raise TypeError("Exactly one of url or file must be provided")

        if file:
            if file.filename is None:
                raise TypeError("File must have a filename")
            self._files[key] = file
            return f"attachment://{file.filename}"
        self._files.pop(key, None)
        return str(url) if url is not None else None

    def check_limits(self) -> None:
        """Checks if this embed fits within the limits dictated by Discord.
        There is also a 6000 character limit across all embeds in a message.

        Returns nothing on success, raises :exc:`ValueError` if an attribute exceeds the limits.

        +--------------------------+------------------------------------+
        |   Field                  |              Limit                 |
        +--------------------------+------------------------------------+
        | title                    |        256 characters              |
        +--------------------------+------------------------------------+
        | description              |        4096 characters             |
        +--------------------------+------------------------------------+
        | fields                   |        Up to 25 field objects      |
        +--------------------------+------------------------------------+
        | field.name               |        256 characters              |
        +--------------------------+------------------------------------+
        | field.value              |        1024 characters             |
        +--------------------------+------------------------------------+
        | footer.text              |        2048 characters             |
        +--------------------------+------------------------------------+
        | author.name              |        256 characters              |
        +--------------------------+------------------------------------+

        .. versionadded:: 2.6

        Raises
        ------
        ValueError
            One or more of the embed attributes are too long.
        """
        if self.title and len(self.title.strip()) > 256:
            raise ValueError("Embed title cannot be longer than 256 characters")

        if self.description and len(self.description.strip()) > 4096:
            raise ValueError("Embed description cannot be longer than 4096 characters")

        if self._footer and len(self._footer.get("text", "").strip()) > 2048:
            raise ValueError("Embed footer text cannot be longer than 2048 characters")

        if self._author and len(self._author.get("name", "").strip()) > 256:
            raise ValueError("Embed author name cannot be longer than 256 characters")

        if self._fields:
            if len(self._fields) > 25:
                raise ValueError("Embeds cannot have more than 25 fields")

            for field_index, field in enumerate(self._fields):
                if len(field["name"].strip()) > 256:
                    raise ValueError(
                        f"Embed field {field_index} name cannot be longer than 256 characters"
                    )
                if len(field["value"].strip()) > 1024:
                    raise ValueError(
                        f"Embed field {field_index} value cannot be longer than 1024 characters"
                    )

        if len(self) > 6000:
            raise ValueError("Embed total size cannot be longer than 6000 characters")
