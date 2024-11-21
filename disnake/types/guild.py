# SPDX-License-Identifier: MIT

from typing import List, Literal, Optional, TypedDict

from typing_extensions import NotRequired

from .activity import PartialPresenceUpdate
from .channel import CreateGuildChannel, GuildChannel, StageInstance
from .emoji import Emoji
from .guild_scheduled_event import GuildScheduledEvent
from .member import Member
from .role import CreateRole, Role
from .snowflake import Snowflake
from .sticker import GuildSticker
from .threads import Thread
from .user import User
from .voice import GuildVoiceState
from .welcome_screen import WelcomeScreen


class Ban(TypedDict):
    reason: Optional[str]
    user: User


class BulkBanResult(TypedDict):
    banned_users: List[Snowflake]
    failed_users: List[Snowflake]


class UnavailableGuild(TypedDict):
    id: Snowflake
    unavailable: NotRequired[bool]


DefaultMessageNotificationLevel = Literal[0, 1]
ExplicitContentFilterLevel = Literal[0, 1, 2]
MFALevel = Literal[0, 1]
VerificationLevel = Literal[0, 1, 2, 3, 4]
NSFWLevel = Literal[0, 1, 2, 3]
PremiumTier = Literal[0, 1, 2, 3]
GuildFeature = Literal[
    "ANIMATED_BANNER",
    "ANIMATED_ICON",
    "AUTO_MODERATION",
    "BANNER",
    "COMMUNITY",
    "CREATOR_MONETIZABLE",  # not yet documented/finalised
    "CREATOR_MONETIZABLE_PROVISIONAL",
    "CREATOR_STORE_PAGE",
    "DEVELOPER_SUPPORT_SERVER",
    "DISCOVERABLE",
    "ENABLED_DISCOVERABLE_BEFORE",
    "FEATURABLE",
    "GUILD_HOME_TEST",  # not yet documented/finalised
    "HAS_DIRECTORY_ENTRY",
    "HUB",
    "INVITE_SPLASH",
    "INVITES_DISABLED",
    "LINKED_TO_HUB",
    "MEMBER_PROFILES",  # not sure what this does, if anything
    "MEMBER_VERIFICATION_GATE_ENABLED",
    "MORE_EMOJI",
    "MORE_STICKERS",
    "NEWS",
    "NEW_THREAD_PERMISSIONS",  # deprecated
    "PARTNERED",
    "PREVIEW_ENABLED",
    "PRIVATE_THREADS",  # deprecated
    "RAID_ALERTS_DISABLED",
    "RELAY_ENABLED",
    "ROLE_ICONS",
    "ROLE_SUBSCRIPTIONS_AVAILABLE_FOR_PURCHASE",
    "ROLE_SUBSCRIPTIONS_ENABLED",
    "SEVEN_DAY_THREAD_ARCHIVE",  # deprecated
    "TEXT_IN_VOICE_ENABLED",  # deprecated
    "THREADS_ENABLED",  # deprecated
    "THREE_DAY_THREAD_ARCHIVE",  # deprecated
    "TICKETED_EVENTS_ENABLED",  # deprecated
    "VANITY_URL",
    "VERIFIED",
    "VIP_REGIONS",
    "WELCOME_SCREEN_ENABLED",
]


class _BaseGuildPreview(UnavailableGuild):
    name: str
    icon: Optional[str]
    splash: Optional[str]
    discovery_splash: Optional[str]
    emojis: List[Emoji]
    features: List[GuildFeature]
    description: Optional[str]
    stickers: List[GuildSticker]


class GuildPreview(_BaseGuildPreview):
    approximate_member_count: int
    approximate_presence_count: int


class Guild(_BaseGuildPreview):
    icon_hash: NotRequired[Optional[str]]
    owner: NotRequired[bool]
    owner_id: Snowflake
    permissions: NotRequired[str]
    region: str
    afk_channel_id: Optional[Snowflake]
    afk_timeout: int
    widget_enabled: NotRequired[bool]
    widget_channel_id: NotRequired[Optional[Snowflake]]
    verification_level: VerificationLevel
    default_message_notifications: DefaultMessageNotificationLevel
    explicit_content_filter: ExplicitContentFilterLevel
    roles: List[Role]
    mfa_level: MFALevel
    application_id: Optional[Snowflake]
    system_channel_id: Optional[Snowflake]
    system_channel_flags: int
    rules_channel_id: Optional[Snowflake]
    max_presences: NotRequired[Optional[int]]
    max_members: NotRequired[int]
    vanity_url_code: Optional[str]
    banner: Optional[str]
    premium_tier: PremiumTier
    premium_subscription_count: NotRequired[int]
    preferred_locale: str
    public_updates_channel_id: Optional[Snowflake]
    max_video_channel_users: NotRequired[int]
    max_stage_video_channel_users: NotRequired[int]
    approximate_member_count: NotRequired[int]
    approximate_presence_count: NotRequired[int]
    nsfw_level: NSFWLevel
    stickers: NotRequired[List[GuildSticker]]
    premium_progress_bar_enabled: bool
    safety_alerts_channel_id: Optional[Snowflake]

    # specific to GUILD_CREATE event
    joined_at: NotRequired[Optional[str]]
    large: NotRequired[bool]
    member_count: NotRequired[int]
    voice_states: NotRequired[List[GuildVoiceState]]
    members: NotRequired[List[Member]]
    channels: NotRequired[List[GuildChannel]]
    threads: NotRequired[List[Thread]]
    presences: NotRequired[List[PartialPresenceUpdate]]
    stage_instances: NotRequired[List[StageInstance]]
    guild_scheduled_events: NotRequired[List[GuildScheduledEvent]]


class PartialGuild(Guild, total=False):
    pass


class InviteGuild(Guild, total=False):
    welcome_screen: WelcomeScreen


class GuildPrune(TypedDict):
    pruned: int


class ChannelPositionUpdate(TypedDict):
    id: Snowflake
    position: Optional[int]
    lock_permissions: Optional[bool]
    parent_id: Optional[Snowflake]


class RolePositionUpdate(TypedDict):
    id: Snowflake
    position: NotRequired[Optional[Snowflake]]


class MFALevelUpdate(TypedDict):
    level: MFALevel


class CreateGuildPlaceholderRole(CreateRole):
    id: Snowflake


class CreateGuildPlaceholderChannel(CreateGuildChannel):
    id: NotRequired[Snowflake]


class CreateGuild(TypedDict):
    name: str
    icon: NotRequired[str]
    verification_level: NotRequired[VerificationLevel]
    default_message_notifications: NotRequired[DefaultMessageNotificationLevel]
    explicit_content_filter: NotRequired[ExplicitContentFilterLevel]
    roles: NotRequired[List[CreateGuildPlaceholderRole]]
    channels: NotRequired[List[CreateGuildPlaceholderChannel]]
    afk_channel_id: NotRequired[Snowflake]
    afk_timeout: NotRequired[int]
    system_channel_id: NotRequired[Snowflake]
    system_channel_flags: NotRequired[int]
