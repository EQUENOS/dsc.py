# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import List, Literal, TypedDict, Union

from typing_extensions import NotRequired

from .snowflake import Snowflake, SnowflakeList

AutoModTriggerType = Literal[1, 2, 3, 4, 5, 6]
AutoModEventType = Literal[1, 2]
AutoModActionType = Literal[1, 2, 3, 4]
AutoModPresetType = Literal[1, 2, 3]


class AutoModBlockMessageActionMetadata(TypedDict):
    custom_message: NotRequired[str]


class AutoModSendAlertActionMetadata(TypedDict):
    channel_id: Snowflake


class AutoModTimeoutActionMetadata(TypedDict):
    duration_seconds: int


class AutoModBlockInteractionActionMetadata(TypedDict):
    ...  # currently empty


AutoModActionMetadata = Union[
    AutoModBlockMessageActionMetadata,
    AutoModSendAlertActionMetadata,
    AutoModTimeoutActionMetadata,
    AutoModBlockInteractionActionMetadata,
]


class AutoModAction(TypedDict):
    type: AutoModActionType
    metadata: NotRequired[AutoModActionMetadata]


class AutoModTriggerMetadata(TypedDict, total=False):
    keyword_filter: List[str]
    regex_patterns: List[str]
    presets: List[AutoModPresetType]
    allow_list: List[str]
    mention_total_limit: int
    mention_raid_protection_enabled: bool


class AutoModRule(TypedDict):
    id: Snowflake
    guild_id: Snowflake
    name: str
    creator_id: Snowflake
    event_type: AutoModEventType
    trigger_type: AutoModTriggerType
    trigger_metadata: AutoModTriggerMetadata
    actions: List[AutoModAction]
    enabled: bool
    exempt_roles: SnowflakeList
    exempt_channels: SnowflakeList


class EditAutoModRule(TypedDict, total=False):
    name: str
    event_type: AutoModEventType
    trigger_metadata: AutoModTriggerMetadata
    actions: List[AutoModAction]
    enabled: bool
    exempt_roles: SnowflakeList
    exempt_channels: SnowflakeList


class CreateAutoModRule(TypedDict):
    name: str
    event_type: AutoModEventType
    trigger_type: AutoModTriggerType
    trigger_metadata: NotRequired[AutoModTriggerMetadata]
    actions: List[AutoModAction]
    enabled: NotRequired[bool]
    exempt_roles: NotRequired[SnowflakeList]
    exempt_channels: NotRequired[SnowflakeList]
