# SPDX-License-Identifier: MIT

from typing import Literal, NamedTuple

class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: Literal["alpha", "beta", "candidate", "final"]
    serial: int

__version__: str
version_info: VersionInfo
