# SPDX-License-Identifier: MIT

"""Discord API Wrapper
~~~~~~~~~~~~~~~~~~~

A basic wrapper for the Discord API.

:copyright: (c) 2015-2021 Rapptz, 2021-present Disnake Development
:license: MIT, see LICENSE for more details.

"""

__title__ = "disnake"
__author__ = "Rapptz, EQUENOS"
__license__ = "MIT"
__copyright__ = "Copyright 2015-present Rapptz, 2021-present EQUENOS"

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from ._version import (  # type: ignore
    VersionInfo as VersionInfo,
    __version__ as __version__,
    version_info as version_info,
)

# isort: split

import logging

from . import abc as abc, opus as opus, ui as ui, utils as utils  # explicitly re-export modules
from .activity import *
from .app_commands import *
from .appinfo import *
from .application_role_connection import *
from .asset import *
from .audit_logs import *
from .automod import *
from .bans import *
from .channel import *
from .client import *
from .colour import *
from .components import *
from .custom_warnings import *
from .embeds import *
from .emoji import *
from .enums import *
from .errors import *
from .file import *
from .flags import *
from .guild import *
from .guild_preview import *
from .guild_scheduled_event import *
from .i18n import *
from .integrations import *
from .interactions import *
from .invite import *
from .member import *
from .mentions import *
from .message import *
from .object import *
from .onboarding import *
from .partial_emoji import *
from .permissions import *
from .player import *
from .raw_models import *
from .reaction import *
from .role import *
from .shard import *
from .stage_instance import *
from .sticker import *
from .team import *
from .template import *
from .threads import *
from .user import *
from .voice_client import *
from .voice_region import *
from .webhook import *
from .welcome_screen import *
from .widget import *

logging.getLogger(__name__).addHandler(logging.NullHandler())
