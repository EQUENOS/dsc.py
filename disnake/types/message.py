# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import List, Literal, Optional, TypedDict, Union

from typing_extensions import NotRequired

from .channel import ChannelType
from .components import Component
from .embed import Embed
from .emoji import PartialEmoji
from .interactions import InteractionMessageReference
from .member import Member, UserWithMember
from .snowflake import Snowflake, SnowflakeList
from .sticker import StickerItem
from .threads import Thread
from .user import User


class ChannelMention(TypedDict):
    id: Snowflake
    guild_id: Snowflake
    type: ChannelType
    name: str


class ReactionCountDetails(TypedDict):
    normal: int
    burst: int


class Reaction(TypedDict):
    count: int
    count_details: ReactionCountDetails
    me: bool
    me_burst: bool
    emoji: PartialEmoji
    burst_count: int
    burst_colors: List[str]


class Attachment(TypedDict):
    id: Snowflake
    filename: str
    description: NotRequired[str]
    content_type: NotRequired[str]
    size: int
    url: str
    proxy_url: str
    height: NotRequired[Optional[int]]
    width: NotRequired[Optional[int]]
    ephemeral: NotRequired[bool]
    duration_secs: NotRequired[float]
    waveform: NotRequired[str]
    flags: NotRequired[int]


MessageActivityType = Literal[1, 2, 3, 5]


class MessageActivity(TypedDict):
    type: MessageActivityType
    party_id: NotRequired[str]


class MessageApplication(TypedDict):
    id: Snowflake
    description: str
    icon: Optional[str]
    name: str
    cover_image: NotRequired[str]


class MessageReference(TypedDict):
    message_id: NotRequired[Snowflake]
    channel_id: Snowflake
    guild_id: NotRequired[Snowflake]
    fail_if_not_exists: NotRequired[bool]


class RoleSubscriptionData(TypedDict):
    role_subscription_listing_id: Snowflake
    tier_name: str
    total_months_subscribed: int
    is_renewal: bool


# fmt: off
MessageType = Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]
# fmt: on


class Message(TypedDict):
    id: Snowflake
    channel_id: Snowflake
    author: User
    content: str
    timestamp: str
    edited_timestamp: Optional[str]
    tts: bool
    mention_everyone: bool
    # this only contains (partial) member data in gateway events
    mentions: Union[List[User], List[UserWithMember]]
    mention_roles: SnowflakeList
    mention_channels: NotRequired[List[ChannelMention]]
    attachments: List[Attachment]
    embeds: List[Embed]
    reactions: NotRequired[List[Reaction]]
    nonce: NotRequired[Union[int, str]]
    pinned: bool
    webhook_id: NotRequired[Snowflake]
    type: MessageType
    activity: NotRequired[MessageActivity]
    application: NotRequired[MessageApplication]
    application_id: NotRequired[Snowflake]
    message_reference: NotRequired[MessageReference]
    flags: NotRequired[int]
    referenced_message: NotRequired[Optional[Message]]
    interaction: NotRequired[InteractionMessageReference]
    thread: NotRequired[Thread]
    components: NotRequired[List[Component]]
    sticker_items: NotRequired[List[StickerItem]]
    position: NotRequired[int]
    role_subscription_data: NotRequired[RoleSubscriptionData]

    # specific to MESSAGE_CREATE/MESSAGE_UPDATE events
    guild_id: NotRequired[Snowflake]
    member: NotRequired[Member]


AllowedMentionType = Literal["roles", "users", "everyone"]


class AllowedMentions(TypedDict):
    parse: List[AllowedMentionType]
    roles: SnowflakeList
    users: SnowflakeList
    replied_user: bool
