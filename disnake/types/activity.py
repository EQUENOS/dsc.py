"""
The MIT License (MIT)

Copyright (c) 2015-2021 Rapptz
Copyright (c) 2021-present Disnake Development

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

from typing import List, Literal, Optional, TypedDict

from .snowflake import Snowflake
from .user import User

StatusType = Literal["idle", "dnd", "online", "offline"]


class PresenceData(TypedDict):
    user: User
    status: StatusType
    activities: List[Activity]
    client_status: ClientStatus


class PartialPresenceUpdate(PresenceData):
    guild_id: Snowflake


class ClientStatus(TypedDict, total=False):
    desktop: str
    mobile: str
    web: str


class ActivityTimestamps(TypedDict, total=False):
    start: int
    end: int


class ActivityParty(TypedDict, total=False):
    id: str
    size: List[int]  # (current size, max size)


class ActivityAssets(TypedDict, total=False):
    # large_image/small_image may be a snowflake or prefixed media proxy ID, see:
    # https://discord.com/developers/docs/topics/gateway#activity-object-activity-asset-image
    large_image: str
    large_text: str
    small_image: str
    small_text: str


class ActivitySecrets(TypedDict, total=False):
    join: str
    spectate: str
    match: str


class _ActivityEmojiOptional(TypedDict, total=False):
    id: Snowflake
    animated: bool


class ActivityEmoji(_ActivityEmojiOptional):
    name: str


class _SendableActivityOptional(TypedDict, total=False):
    url: Optional[str]


ActivityType = Literal[0, 1, 2, 3, 4, 5]


class SendableActivity(_SendableActivityOptional):
    name: str
    type: ActivityType


class Activity(SendableActivity, total=False):
    created_at: int  # required according to docs, but we treat it as optional for simplicity
    timestamps: ActivityTimestamps
    application_id: Snowflake
    details: Optional[str]
    state: Optional[str]
    emoji: Optional[ActivityEmoji]
    party: ActivityParty
    assets: ActivityAssets
    secrets: ActivitySecrets
    instance: bool
    flags: int
    # `buttons` is a list of strings when received over gw,
    # bots cannot access the full button data (like urls)
    buttons: List[str]
    session_id: Optional[str]
