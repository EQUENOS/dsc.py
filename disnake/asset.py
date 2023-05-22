# SPDX-License-Identifier: MIT

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING, Any, Literal, Optional, Tuple, Union

import yarl

from . import utils
from .errors import DiscordException
from .file import File

__all__ = ("Asset",)

if TYPE_CHECKING:
    from typing_extensions import Self

    from .state import ConnectionState
    from .webhook.async_ import BaseWebhook, _WebhookState

    ValidStaticFormatTypes = Literal["webp", "jpeg", "jpg", "png"]
    ValidAssetFormatTypes = Literal["webp", "jpeg", "jpg", "png", "gif"]
    AnyState = Union[ConnectionState, _WebhookState[BaseWebhook]]

AssetBytes = Union[bytes, "AssetMixin"]

VALID_STATIC_FORMATS = frozenset({"jpeg", "jpg", "webp", "png"})
VALID_ASSET_FORMATS = VALID_STATIC_FORMATS | {"gif"}


MISSING = utils.MISSING


class AssetMixin:
    url: str
    _state: Optional[AnyState]

    __slots__: Tuple[str, ...] = ("_state",)

    async def read(self) -> bytes:
        """|coro|

        Retrieves the content of this asset as a :class:`bytes` object.

        Raises
        ------
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
        if self._state is None:
            raise DiscordException("Invalid state (no ConnectionState provided)")

        return await self._state.http.get_from_cdn(self.url)

    async def save(
        self, fp: Union[str, bytes, os.PathLike, io.BufferedIOBase], *, seek_begin: bool = True
    ) -> int:
        """|coro|

        Saves this asset into a file-like object.

        Parameters
        ----------
        fp: Union[:class:`io.BufferedIOBase`, :class:`os.PathLike`]
            The file-like object to save this asset to or the filename
            to use. If a filename is passed then a file is created with that
            filename and used instead.
        seek_begin: :class:`bool`
            Whether to seek to the beginning of the file after saving is
            successfully done.

        Raises
        ------
        DiscordException
            There was no internal connection state.
        HTTPException
            Downloading the asset failed.
        NotFound
            The asset was deleted.

        Returns
        -------
        :class:`int`
            The number of bytes written.
        """
        data = await self.read()
        if isinstance(fp, io.BufferedIOBase):
            written = fp.write(data)
            if seek_begin:
                fp.seek(0)
            return written
        with open(fp, "wb") as f:
            return f.write(data)

    async def to_file(
        self,
        *,
        spoiler: bool = False,
        filename: Optional[str] = None,
        description: Optional[str] = None,
    ) -> File:
        """|coro|

        Converts the asset into a :class:`File` suitable for sending via
        :meth:`abc.Messageable.send`.

        .. versionadded:: 2.5

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Parameters
        ----------
        spoiler: :class:`bool`
            Whether the file is a spoiler.
        filename: Optional[:class:`str`]
            The filename to display when uploading to Discord. If this is not given, it defaults to
            the name of the asset's URL.
        description: Optional[:class:`str`]
            The file's description.

        Raises
        ------
        DiscordException
            The asset does not have an associated state.
        HTTPException
            Downloading the asset failed.
        NotFound
            The asset was deleted.
        TypeError
            The asset is a unicode emoji or a sticker with lottie type.

        Returns
        -------
        :class:`File`
            The asset as a file suitable for sending.
        """
        data = await self.read()

        if not filename:
            filename = yarl.URL(self.url).name
            # if the filename doesn't have an extension (e.g. widget member avatars),
            # try to infer it from the data
            if not os.path.splitext(filename)[1]:
                ext = utils._get_extension_for_image(data)
                if ext:
                    filename += ext

        return File(io.BytesIO(data), filename=filename, spoiler=spoiler, description=description)


class Asset(AssetMixin):
    """Represents a CDN asset on Discord.

    .. container:: operations

        .. describe:: str(x)

            Returns the URL of the CDN asset.

        .. describe:: len(x)

            Returns the length of the CDN asset's URL.

        .. describe:: x == y

            Checks if the asset is equal to another asset.

        .. describe:: x != y

            Checks if the asset is not equal to another asset.

        .. describe:: hash(x)

            Returns the hash of the asset.
    """

    __slots__: Tuple[str, ...] = (
        "_url",
        "_animated",
        "_key",
    )

    BASE = "https://cdn.discordapp.com"

    def __init__(self, state: AnyState, *, url: str, key: str, animated: bool = False) -> None:
        self._state: AnyState = state
        self._url: str = url
        self._animated: bool = animated
        self._key: str = key

    @classmethod
    def _from_default_avatar(cls, state: AnyState, index: int) -> Self:
        return cls(
            state,
            url=f"{cls.BASE}/embed/avatars/{index}.png",
            key=str(index),
            animated=False,
        )

    @classmethod
    def _from_avatar(cls, state: AnyState, user_id: int, avatar: str) -> Self:
        animated = avatar.startswith("a_")
        format = "gif" if animated else "png"
        return cls(
            state,
            url=f"{cls.BASE}/avatars/{user_id}/{avatar}.{format}?size=1024",
            key=avatar,
            animated=animated,
        )

    @classmethod
    def _from_guild_avatar(
        cls, state: AnyState, guild_id: int, member_id: int, avatar: str
    ) -> Self:
        animated = avatar.startswith("a_")
        format = "gif" if animated else "png"
        return cls(
            state,
            url=f"{cls.BASE}/guilds/{guild_id}/users/{member_id}/avatars/{avatar}.{format}?size=1024",
            key=avatar,
            animated=animated,
        )

    @classmethod
    def _from_icon(cls, state: AnyState, object_id: int, icon_hash: str, path: str) -> Self:
        return cls(
            state,
            url=f"{cls.BASE}/{path}-icons/{object_id}/{icon_hash}.png?size=1024",
            key=icon_hash,
            animated=False,
        )

    @classmethod
    def _from_cover_image(cls, state: AnyState, object_id: int, cover_image_hash: str) -> Self:
        return cls(
            state,
            url=f"{cls.BASE}/app-assets/{object_id}/store/{cover_image_hash}.png?size=1024",
            key=cover_image_hash,
            animated=False,
        )

    @classmethod
    def _from_guild_image(cls, state: AnyState, guild_id: int, image: str, path: str) -> Self:
        return cls(
            state,
            url=f"{cls.BASE}/{path}/{guild_id}/{image}.png?size=1024",
            key=image,
            animated=False,
        )

    @classmethod
    def _from_guild_icon(cls, state: AnyState, guild_id: int, icon_hash: str) -> Self:
        animated = icon_hash.startswith("a_")
        format = "gif" if animated else "png"
        return cls(
            state,
            url=f"{cls.BASE}/icons/{guild_id}/{icon_hash}.{format}?size=1024",
            key=icon_hash,
            animated=animated,
        )

    @classmethod
    def _from_sticker_banner(cls, state: AnyState, banner: int) -> Self:
        return cls(
            state,
            url=f"{cls.BASE}/app-assets/710982414301790216/store/{banner}.png",
            key=str(banner),
            animated=False,
        )

    @classmethod
    def _from_banner(cls, state: AnyState, id: int, banner_hash: str) -> Self:
        animated = banner_hash.startswith("a_")
        format = "gif" if animated else "png"
        return cls(
            state,
            url=f"{cls.BASE}/banners/{id}/{banner_hash}.{format}?size=1024",
            key=banner_hash,
            animated=animated,
        )

    @classmethod
    def _from_role_icon(cls, state: AnyState, role_id: int, icon_hash: str) -> Self:
        animated = icon_hash.startswith("a_")
        format = "gif" if animated else "png"
        return cls(
            state,
            url=f"{cls.BASE}/role-icons/{role_id}/{icon_hash}.{format}?size=1024",
            key=icon_hash,
            animated=animated,
        )

    @classmethod
    def _from_guild_scheduled_event_image(
        cls, state: AnyState, event_id: int, image_hash: str
    ) -> Self:
        return cls(
            state,
            url=f"{cls.BASE}/guild-events/{event_id}/{image_hash}.png?size=2048",
            key=image_hash,
            animated=False,
        )

    def __str__(self) -> str:
        return self._url

    def __len__(self) -> int:
        return len(self._url)

    def __repr__(self) -> str:
        shorten = self._url.replace(self.BASE, "")
        return f"<Asset url={shorten!r}>"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Asset) and self._url == other._url

    def __hash__(self) -> int:
        return hash(self._url)

    @property
    def url(self) -> str:
        """:class:`str`: Returns the underlying URL of the asset."""
        return self._url

    @property
    def key(self) -> str:
        """:class:`str`: Returns the identifying key of the asset."""
        return self._key

    def is_animated(self) -> bool:
        """Whether the asset is animated.

        :return type: :class:`bool`
        """
        return self._animated

    def replace(
        self,
        *,
        size: int = MISSING,
        format: ValidAssetFormatTypes = MISSING,
        static_format: ValidStaticFormatTypes = MISSING,
    ) -> Asset:
        """Returns a new asset with the passed components replaced.

        .. versionchanged:: 2.6
            Raises :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        size: :class:`int`
            The new size of the asset.
        format: :class:`str`
            The new format to change it to. Must be either
            'webp', 'jpeg', 'jpg', 'png', or 'gif' if it's animated.
        static_format: :class:`str`
            The new format to change it to if the asset isn't animated.
            Must be either 'webp', 'jpeg', 'jpg', or 'png'.

        Raises
        ------
        ValueError
            An invalid size or format was passed.

        Returns
        -------
        :class:`Asset`
            The newly updated asset.
        """
        url = yarl.URL(self._url)
        path, _ = os.path.splitext(url.path)

        if format is not MISSING:
            if self._animated:
                if format not in VALID_ASSET_FORMATS:
                    raise ValueError(f"format must be one of {VALID_ASSET_FORMATS}")
            else:
                if format not in VALID_STATIC_FORMATS:
                    raise ValueError(f"format must be one of {VALID_STATIC_FORMATS}")
            url = url.with_path(f"{path}.{format}")

        if static_format is not MISSING and not self._animated:
            if static_format not in VALID_STATIC_FORMATS:
                raise ValueError(f"static_format must be one of {VALID_STATIC_FORMATS}")
            url = url.with_path(f"{path}.{static_format}")

        if size is not MISSING:
            if not utils.valid_icon_size(size):
                raise ValueError("size must be a power of 2 between 16 and 4096")
            url = url.with_query(size=size)
        else:
            url = url.with_query(url.raw_query_string)

        url_str = str(url)
        return Asset(state=self._state, url=url_str, key=self._key, animated=self._animated)

    def with_size(self, size: int, /) -> Asset:
        """Returns a new asset with the specified size.

        .. versionchanged:: 2.6
            Raises :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        size: :class:`int`
            The new size of the asset.

        Raises
        ------
        ValueError
            The asset had an invalid size.

        Returns
        -------
        :class:`Asset`
            The newly updated asset.
        """
        if not utils.valid_icon_size(size):
            raise ValueError("size must be a power of 2 between 16 and 4096")

        url = str(yarl.URL(self._url).with_query(size=size))
        return Asset(state=self._state, url=url, key=self._key, animated=self._animated)

    def with_format(self, format: ValidAssetFormatTypes, /) -> Asset:
        """Returns a new asset with the specified format.

        .. versionchanged:: 2.6
            Raises :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        format: :class:`str`
            The new format of the asset.

        Raises
        ------
        ValueError
            The asset had an invalid format.

        Returns
        -------
        :class:`Asset`
            The newly updated asset.
        """
        if self._animated:
            if format not in VALID_ASSET_FORMATS:
                raise ValueError(f"format must be one of {VALID_ASSET_FORMATS}")
        else:
            if format not in VALID_STATIC_FORMATS:
                raise ValueError(f"format must be one of {VALID_STATIC_FORMATS}")

        url = yarl.URL(self._url)
        path, _ = os.path.splitext(url.path)
        url_str = str(url.with_path(f"{path}.{format}").with_query(url.raw_query_string))
        return Asset(state=self._state, url=url_str, key=self._key, animated=self._animated)

    def with_static_format(self, format: ValidStaticFormatTypes, /) -> Asset:
        """Returns a new asset with the specified static format.

        This only changes the format if the underlying asset is
        not animated. Otherwise, the asset is not changed.

        .. versionchanged:: 2.6
            Raises :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        format: :class:`str`
            The new static format of the asset.

        Raises
        ------
        ValueError
            The asset had an invalid format.

        Returns
        -------
        :class:`Asset`
            The newly updated asset.
        """
        if self._animated:
            return self
        return self.with_format(format)
