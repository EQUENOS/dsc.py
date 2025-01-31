# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import List, Literal, Optional, TypedDict, Union

from typing_extensions import NotRequired

from .appinfo import AppInfo
from .channel import ChannelType
from .components import Component
from .embed import Embed
from .emoji import PartialEmoji
from .interactions import InteractionDataResolved, InteractionMessageReference, InteractionMetadata
from .member import Member, UserWithMember
from .poll import Poll
from .snowflake import Snowflake, SnowflakeList
from .sticker import StickerItem
from .threads import Thread
from .user import User


class ChannelMention(TypedDict):
    id: Snowflake
    guild_id: Snowflake
    type: ChannelType
    name: str


class Reaction(TypedDict):
    count: int
    me: bool
    emoji: PartialEmoji


class Attachment(TypedDict):
    id: Snowflake
    filename: str
    title: NotRequired[str]
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
    clip_participants: NotRequired[List[User]]
    clip_created_at: NotRequired[str]
    application: NotRequired[Optional[AppInfo]]


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


MessageReferenceType = Literal[0, 1]


class MessageReference(TypedDict):
    type: MessageReferenceType
    message_id: NotRequired[Snowflake]
    channel_id: Snowflake
    guild_id: NotRequired[Snowflake]
    fail_if_not_exists: NotRequired[bool]


class ForwardedMessage(TypedDict):
    type: MessageType
    content: str
    embeds: List[Embed]
    attachments: List[Attachment]
    timestamp: str
    edited_timestamp: Optional[str]
    flags: NotRequired[int]
    mentions: Union[List[User], List[UserWithMember]]
    # apparently mention_roles list is not sent if the msg
    # is not forwarded in the same guild
    mention_roles: NotRequired[SnowflakeList]
    sticker_items: NotRequired[List[StickerItem]]
    components: NotRequired[List[Component]]


class MessageSnapshot(TypedDict):
    message: ForwardedMessage


class RoleSubscriptionData(TypedDict):
    role_subscription_listing_id: Snowflake
    tier_name: str
    total_months_subscribed: int
    is_renewal: bool


# fmt: off
MessageType = Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 36, 37, 38, 39, 46]
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
    message_snapshots: NotRequired[List[MessageSnapshot]]
    flags: NotRequired[int]
    referenced_message: NotRequired[Optional[Message]]
    interaction: NotRequired[InteractionMessageReference]  # deprecated
    interaction_metadata: NotRequired[InteractionMetadata]
    thread: NotRequired[Thread]
    components: NotRequired[List[Component]]
    sticker_items: NotRequired[List[StickerItem]]
    position: NotRequired[int]
    role_subscription_data: NotRequired[RoleSubscriptionData]
    poll: NotRequired[Poll]
    # contains resolved objects for `default_values` of select menus in this message; we currently don't have a use for this
    resolved: NotRequired[InteractionDataResolved]

    # specific to MESSAGE_CREATE/MESSAGE_UPDATE events
    guild_id: NotRequired[Snowflake]
    member: NotRequired[Member]


AllowedMentionType = Literal["roles", "users", "everyone"]


class AllowedMentions(TypedDict):
    parse: List[AllowedMentionType]
    roles: SnowflakeList
    users: SnowflakeList
    replied_user: bool
