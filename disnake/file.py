# SPDX-License-Identifier: MIT

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING, Optional, Union

__all__ = ("File",)


class File:
    """A parameter object used for sending file objects.

    .. note::

        File objects are single use and are not meant to be reused in
        multiple :meth:`abc.Messageable.send`, :meth:`Message.edit`, :meth:`Interaction.send`,
        or :meth:`Interaction.edit_original_response` calls or similar methods.

    Attributes
    ----------
    fp: Union[:class:`os.PathLike`, :class:`io.BufferedIOBase`]
        A file-like object opened in binary mode and read mode
        or a filename representing a file in the hard drive to
        open.

        .. note::

            If the file-like object passed is opened via ``open`` then the
            modes 'rb' should be used.

            To pass binary data, consider usage of ``io.BytesIO``.

    filename: Optional[:class:`str`]
        The filename to display when uploading to Discord.
        If this is not given then it defaults to ``fp.name`` or if ``fp`` is
        a string then the ``filename`` will default to the string given.
    spoiler: :class:`bool`
        Whether the attachment is a spoiler.
    description: Optional[:class:`str`]
        The file's description.

        .. versionadded:: 2.3
    """

    __slots__ = ("fp", "filename", "spoiler", "description", "_original_pos", "_owner", "_closer")

    if TYPE_CHECKING:
        fp: io.BufferedIOBase
        filename: Optional[str]
        spoiler: bool
        description: Optional[str]

    def __init__(
        self,
        fp: Union[str, bytes, os.PathLike[str], os.PathLike[bytes], io.StringIO, io.BufferedIOBase],
        filename: Optional[str] = None,
        *,
        spoiler: bool = False,
        description: Optional[str] = None,
    ) -> None:
        if isinstance(fp, io.StringIO):
            self.fp = io.BytesIO(fp.getvalue().encode())
            self._original_pos = 0
            self._owner = True
        elif isinstance(fp, io.IOBase):
            if not (fp.seekable() and fp.readable()):
                raise ValueError(f"File buffer {fp!r} must be seekable and readable")
            self.fp = fp
            self._original_pos = fp.tell()
            self._owner = False
        else:
            self.fp = open(fp, "rb")
            self._original_pos = 0
            self._owner = True

        # aiohttp only uses two methods from IOBase
        # read and close, since I want to control when the files
        # close, I need to stub it so it doesn't close unless
        # I tell it to
        self._closer = self.fp.close
        self.fp.close = lambda: None

        if filename is None:
            if isinstance(fp, str):
                _, self.filename = os.path.split(fp)
            else:
                self.filename = getattr(fp, "name", None)
        else:
            self.filename = filename

        if spoiler and self.filename is not None and not self.filename.startswith("SPOILER_"):
            self.filename = "SPOILER_" + self.filename

        self.spoiler = spoiler or (
            self.filename is not None and self.filename.startswith("SPOILER_")
        )
        self.description = description

    def reset(self, *, seek: Union[int, bool] = True) -> None:
        # The `seek` parameter is needed because
        # the retry-loop is iterated over multiple times
        # starting from 0, as an implementation quirk
        # the resetting must be done at the beginning
        # before a request is done, since the first index
        # is 0, and thus false, then this prevents an
        # unnecessary seek since it's the first request
        # done.
        if seek:
            self.fp.seek(self._original_pos)

    def close(self) -> None:
        self.fp.close = self._closer
        if self._owner:
            self._closer()

    @property
    def closed(self) -> bool:
        """:class:`bool`: Whether the file is closed.

        This is a shorthand for ``File.fp.closed``.

        .. versionadded:: 2.8
        """
        return self.fp.closed

    @property
    def bytes_length(self) -> int:
        """:class:`int`: The bytes length of the :attr:`~File.fp` object.

        .. versionadded:: 2.8
        """
        current_position = self.fp.tell()
        bytes_length = self.fp.seek(0, io.SEEK_END)
        self.fp.seek(current_position)
        return bytes_length - current_position
