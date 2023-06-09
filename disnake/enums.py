# SPDX-License-Identifier: MIT
from __future__ import annotations

import types
from functools import total_ordering
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Iterator,
    List,
    NamedTuple,
    NoReturn,
    Optional,
    Type,
    TypeVar,
)

if TYPE_CHECKING:
    from typing_extensions import Self

__all__ = (
    "Enum",
    "ChannelType",
    "MessageType",
    "SpeakingState",
    "VerificationLevel",
    "ContentFilter",
    "Status",
    "DefaultAvatar",
    "AuditLogAction",
    "AuditLogActionCategory",
    "UserFlags",
    "ActivityType",
    "NotificationLevel",
    "TeamMembershipState",
    "WebhookType",
    "ExpireBehaviour",
    "ExpireBehavior",
    "StickerType",
    "StickerFormatType",
    "InviteTarget",
    "VideoQualityMode",
    "ComponentType",
    "ButtonStyle",
    "TextInputStyle",
    "StagePrivacyLevel",
    "InteractionType",
    "InteractionResponseType",
    "NSFWLevel",
    "OptionType",
    "ApplicationCommandType",
    "ApplicationCommandPermissionType",
    "PartyType",
    "GuildScheduledEventEntityType",
    "GuildScheduledEventStatus",
    "GuildScheduledEventPrivacyLevel",
    "ThreadArchiveDuration",
    "WidgetStyle",
    "Locale",
    "AutoModTriggerType",
    "AutoModEventType",
    "AutoModActionType",
    "ThreadSortOrder",
    "ThreadLayout",
    "Event",
    "ApplicationRoleConnectionMetadataType",
    "OnboardingPromptType",
)


class _EnumValueBase(NamedTuple):
    if TYPE_CHECKING:
        _cls_name: ClassVar[str]

    name: str
    value: Any

    def __repr__(self) -> str:
        return f"<{self._cls_name}.{self.name}: {self.value!r}>"

    def __str__(self) -> str:
        return f"{self._cls_name}.{self.name}"


@total_ordering
class _EnumValueComparable(_EnumValueBase):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__) and self.value == other.value

    def __lt__(self, other: object) -> bool:
        return isinstance(other, self.__class__) and self.value < other.value


def _create_value_cls(name: str, comparable: bool) -> Type[_EnumValueBase]:
    parent = _EnumValueComparable if comparable else _EnumValueBase
    return type(f"{parent.__name__}_{name}", (parent,), {"_cls_name": name})  # type: ignore


def _is_descriptor(obj):
    return hasattr(obj, "__get__") or hasattr(obj, "__set__") or hasattr(obj, "__delete__")


class EnumMeta(type):
    if TYPE_CHECKING:
        __name__: ClassVar[str]
        _enum_member_names_: ClassVar[List[str]]
        _enum_member_map_: ClassVar[Dict[str, Any]]
        _enum_value_map_: ClassVar[Dict[Any, Any]]

    def __new__(cls, name: str, bases, attrs, *, comparable: bool = False):
        value_mapping = {}
        member_mapping = {}
        member_names = []

        value_cls = _create_value_cls(name, comparable)
        for key, value in list(attrs.items()):
            is_descriptor = _is_descriptor(value)
            if key[0] == "_" and not is_descriptor:
                continue

            # Special case classmethod to just pass through
            if isinstance(value, classmethod):
                continue

            if is_descriptor:
                setattr(value_cls, key, value)
                del attrs[key]
                continue

            try:
                new_value = value_mapping[value]
            except KeyError:
                new_value = value_cls(name=key, value=value)
                value_mapping[value] = new_value
                member_names.append(key)

            member_mapping[key] = new_value
            attrs[key] = new_value

        attrs["_enum_value_map_"] = value_mapping
        attrs["_enum_member_map_"] = member_mapping
        attrs["_enum_member_names_"] = member_names
        attrs["_enum_value_cls_"] = value_cls
        actual_cls = super().__new__(cls, name, bases, attrs)
        value_cls._actual_enum_cls_ = actual_cls  # type: ignore
        return actual_cls

    def __iter__(cls) -> Iterator[Self]:
        return (cls._enum_member_map_[name] for name in cls._enum_member_names_)

    def __reversed__(cls) -> Iterator[Self]:
        return (cls._enum_member_map_[name] for name in reversed(cls._enum_member_names_))

    def __len__(cls) -> int:
        return len(cls._enum_member_names_)

    def __repr__(cls) -> str:
        return f"<enum {cls.__name__}>"

    @property
    def __members__(cls):
        return types.MappingProxyType(cls._enum_member_map_)

    def __call__(cls, value):
        try:
            return cls._enum_value_map_[value]
        except (KeyError, TypeError):
            raise ValueError(f"{value!r} is not a valid {cls.__name__}") from None

    def __getitem__(cls, key):
        return cls._enum_member_map_[key]

    def __setattr__(cls, name: str, value) -> NoReturn:
        raise TypeError("Enums are immutable.")

    def __delattr__(cls, attr) -> NoReturn:
        raise TypeError("Enums are immutable")

    def __instancecheck__(self, instance) -> bool:
        # isinstance(x, Y)
        # -> __instancecheck__(Y, x)
        try:
            return instance._actual_enum_cls_ is self
        except AttributeError:
            return False


if TYPE_CHECKING:
    from enum import Enum
else:

    class Enum(metaclass=EnumMeta):
        @classmethod
        def try_value(cls, value):
            try:
                return cls._enum_value_map_[value]
            except (KeyError, TypeError):
                return value


class ChannelType(Enum):
    text = 0
    private = 1
    voice = 2
    group = 3
    category = 4
    news = 5
    news_thread = 10
    public_thread = 11
    private_thread = 12
    stage_voice = 13
    guild_directory = 14
    forum = 15

    def __str__(self) -> str:
        return self.name


class MessageType(Enum):
    default = 0
    recipient_add = 1
    recipient_remove = 2
    call = 3
    channel_name_change = 4
    channel_icon_change = 5
    pins_add = 6
    new_member = 7
    premium_guild_subscription = 8
    premium_guild_tier_1 = 9
    premium_guild_tier_2 = 10
    premium_guild_tier_3 = 11
    channel_follow_add = 12
    guild_stream = 13
    guild_discovery_disqualified = 14
    guild_discovery_requalified = 15
    guild_discovery_grace_period_initial_warning = 16
    guild_discovery_grace_period_final_warning = 17
    thread_created = 18
    reply = 19
    application_command = 20
    thread_starter_message = 21
    guild_invite_reminder = 22
    context_menu_command = 23
    auto_moderation_action = 24
    role_subscription_purchase = 25
    interaction_premium_upsell = 26
    stage_start = 27
    stage_end = 28
    stage_speaker = 29
    stage_topic = 31
    guild_application_premium_subscription = 32


class PartyType(Enum):
    poker = 755827207812677713
    betrayal = 773336526917861400
    fishing = 814288819477020702
    chess = 832012774040141894
    letter_tile = 879863686565621790
    word_snack = 879863976006127627
    doodle_crew = 878067389634314250
    checkers = 832013003968348200
    spellcast = 852509694341283871
    watch_together = 880218394199220334
    sketch_heads = 902271654783242291
    ocho = 832025144389533716
    gartic_phone = 1007373802981822582


class SpeakingState(Enum):
    none = 0
    voice = 1 << 0
    soundshare = 1 << 1
    priority = 1 << 2

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class VerificationLevel(Enum, comparable=True):
    none = 0
    low = 1
    medium = 2
    high = 3
    highest = 4

    def __str__(self) -> str:
        return self.name


class ContentFilter(Enum, comparable=True):
    disabled = 0
    no_role = 1
    all_members = 2

    def __str__(self) -> str:
        return self.name


class Status(Enum):
    online = "online"
    offline = "offline"
    idle = "idle"
    dnd = "dnd"
    do_not_disturb = "dnd"
    invisible = "invisible"
    streaming = "streaming"

    def __str__(self) -> str:
        return self.value


class DefaultAvatar(Enum):
    blurple = 0
    grey = 1
    gray = 1
    green = 2
    orange = 3
    red = 4

    def __str__(self) -> str:
        return self.name


class NotificationLevel(Enum, comparable=True):
    all_messages = 0
    only_mentions = 1


class AuditLogActionCategory(Enum):
    create = 1
    delete = 2
    update = 3


class AuditLogAction(Enum):
    # fmt: off
    guild_update                          = 1
    channel_create                        = 10
    channel_update                        = 11
    channel_delete                        = 12
    overwrite_create                      = 13
    overwrite_update                      = 14
    overwrite_delete                      = 15
    kick                                  = 20
    member_prune                          = 21
    ban                                   = 22
    unban                                 = 23
    member_update                         = 24
    member_role_update                    = 25
    member_move                           = 26
    member_disconnect                     = 27
    bot_add                               = 28
    role_create                           = 30
    role_update                           = 31
    role_delete                           = 32
    invite_create                         = 40
    invite_update                         = 41
    invite_delete                         = 42
    webhook_create                        = 50
    webhook_update                        = 51
    webhook_delete                        = 52
    emoji_create                          = 60
    emoji_update                          = 61
    emoji_delete                          = 62
    message_delete                        = 72
    message_bulk_delete                   = 73
    message_pin                           = 74
    message_unpin                         = 75
    integration_create                    = 80
    integration_update                    = 81
    integration_delete                    = 82
    stage_instance_create                 = 83
    stage_instance_update                 = 84
    stage_instance_delete                 = 85
    sticker_create                        = 90
    sticker_update                        = 91
    sticker_delete                        = 92
    guild_scheduled_event_create          = 100
    guild_scheduled_event_update          = 101
    guild_scheduled_event_delete          = 102
    thread_create                         = 110
    thread_update                         = 111
    thread_delete                         = 112
    application_command_permission_update = 121
    automod_rule_create                   = 140
    automod_rule_update                   = 141
    automod_rule_delete                   = 142
    automod_block_message                 = 143
    automod_send_alert_message            = 144
    automod_timeout                       = 145
    onboarding_prompt_create              = 163
    onboarding_prompt_update              = 164
    onboarding_update                     = 167
    # fmt: on

    @property
    def category(self) -> Optional[AuditLogActionCategory]:
        # fmt: off
        lookup: Dict[AuditLogAction, Optional[AuditLogActionCategory]] = {
            AuditLogAction.guild_update:                          AuditLogActionCategory.update,
            AuditLogAction.channel_create:                        AuditLogActionCategory.create,
            AuditLogAction.channel_update:                        AuditLogActionCategory.update,
            AuditLogAction.channel_delete:                        AuditLogActionCategory.delete,
            AuditLogAction.overwrite_create:                      AuditLogActionCategory.create,
            AuditLogAction.overwrite_update:                      AuditLogActionCategory.update,
            AuditLogAction.overwrite_delete:                      AuditLogActionCategory.delete,
            AuditLogAction.kick:                                  None,
            AuditLogAction.member_prune:                          None,
            AuditLogAction.ban:                                   None,
            AuditLogAction.unban:                                 None,
            AuditLogAction.member_update:                         AuditLogActionCategory.update,
            AuditLogAction.member_role_update:                    AuditLogActionCategory.update,
            AuditLogAction.member_move:                           None,
            AuditLogAction.member_disconnect:                     None,
            AuditLogAction.bot_add:                               None,
            AuditLogAction.role_create:                           AuditLogActionCategory.create,
            AuditLogAction.role_update:                           AuditLogActionCategory.update,
            AuditLogAction.role_delete:                           AuditLogActionCategory.delete,
            AuditLogAction.invite_create:                         AuditLogActionCategory.create,
            AuditLogAction.invite_update:                         AuditLogActionCategory.update,
            AuditLogAction.invite_delete:                         AuditLogActionCategory.delete,
            AuditLogAction.webhook_create:                        AuditLogActionCategory.create,
            AuditLogAction.webhook_update:                        AuditLogActionCategory.update,
            AuditLogAction.webhook_delete:                        AuditLogActionCategory.delete,
            AuditLogAction.emoji_create:                          AuditLogActionCategory.create,
            AuditLogAction.emoji_update:                          AuditLogActionCategory.update,
            AuditLogAction.emoji_delete:                          AuditLogActionCategory.delete,
            AuditLogAction.message_delete:                        AuditLogActionCategory.delete,
            AuditLogAction.message_bulk_delete:                   AuditLogActionCategory.delete,
            AuditLogAction.message_pin:                           None,
            AuditLogAction.message_unpin:                         None,
            AuditLogAction.integration_create:                    AuditLogActionCategory.create,
            AuditLogAction.integration_update:                    AuditLogActionCategory.update,
            AuditLogAction.integration_delete:                    AuditLogActionCategory.delete,
            AuditLogAction.stage_instance_create:                 AuditLogActionCategory.create,
            AuditLogAction.stage_instance_update:                 AuditLogActionCategory.update,
            AuditLogAction.stage_instance_delete:                 AuditLogActionCategory.delete,
            AuditLogAction.sticker_create:                        AuditLogActionCategory.create,
            AuditLogAction.sticker_update:                        AuditLogActionCategory.update,
            AuditLogAction.sticker_delete:                        AuditLogActionCategory.delete,
            AuditLogAction.thread_create:                         AuditLogActionCategory.create,
            AuditLogAction.thread_update:                         AuditLogActionCategory.update,
            AuditLogAction.thread_delete:                         AuditLogActionCategory.delete,
            AuditLogAction.guild_scheduled_event_create:          AuditLogActionCategory.create,
            AuditLogAction.guild_scheduled_event_update:          AuditLogActionCategory.update,
            AuditLogAction.guild_scheduled_event_delete:          AuditLogActionCategory.delete,
            AuditLogAction.application_command_permission_update: AuditLogActionCategory.update,
            AuditLogAction.automod_rule_create:                   AuditLogActionCategory.create,
            AuditLogAction.automod_rule_update:                   AuditLogActionCategory.update,
            AuditLogAction.automod_rule_delete:                   AuditLogActionCategory.delete,
            AuditLogAction.automod_block_message:                 None,
            AuditLogAction.automod_send_alert_message:            None,
            AuditLogAction.automod_timeout:                       None,
            AuditLogAction.onboarding_prompt_create:              AuditLogActionCategory.create,
            AuditLogAction.onboarding_prompt_update:              AuditLogActionCategory.update,
            AuditLogAction.onboarding_update:                     AuditLogActionCategory.update,
        }
        # fmt: on
        return lookup[self]

    @property
    def target_type(self) -> Optional[str]:
        v = self.value
        if v == -1:
            return "all"
        elif v < 10:
            return "guild"
        elif v < 20:
            return "channel"
        elif v < 30:
            return "user"
        elif v < 40:
            return "role"
        elif v < 50:
            return "invite"
        elif v < 60:
            return "webhook"
        elif v < 70:
            return "emoji"
        elif v == 73:
            return "channel"
        elif v < 80:
            return "message"
        elif v < 83:
            return "integration"
        elif v < 90:
            return "stage_instance"
        elif v < 93:
            return "sticker"
        elif v < 103:
            return "guild_scheduled_event"
        elif v < 113:
            return "thread"
        elif v < 122:
            return "application_command_or_integration"
        elif v < 140:
            return None
        elif v < 143:
            return "automod_rule"
        elif v < 146:
            return "user"
        elif v < 160:
            return None
        elif v < 166:
            return "onboarding_prompt"
        elif v < 168:
            return "onboarding"
        else:
            return None


class UserFlags(Enum):
    staff = 1 << 0
    partner = 1 << 1
    hypesquad = 1 << 2
    bug_hunter = 1 << 3
    mfa_sms = 1 << 4
    premium_promo_dismissed = 1 << 5
    hypesquad_bravery = 1 << 6
    hypesquad_brilliance = 1 << 7
    hypesquad_balance = 1 << 8
    early_supporter = 1 << 9
    team_user = 1 << 10
    system = 1 << 12
    has_unread_urgent_messages = 1 << 13
    bug_hunter_level_2 = 1 << 14
    verified_bot = 1 << 16
    verified_bot_developer = 1 << 17
    discord_certified_moderator = 1 << 18
    http_interactions_bot = 1 << 19
    spammer = 1 << 20
    active_developer = 1 << 22


class ActivityType(Enum):
    unknown = -1
    playing = 0
    streaming = 1
    listening = 2
    watching = 3
    custom = 4
    competing = 5

    def __int__(self) -> int:
        return self.value


class TeamMembershipState(Enum):
    invited = 1
    accepted = 2


class WebhookType(Enum):
    incoming = 1
    channel_follower = 2
    application = 3


class ExpireBehaviour(Enum):
    remove_role = 0
    kick = 1


ExpireBehavior = ExpireBehaviour


class StickerType(Enum):
    standard = 1
    guild = 2


class StickerFormatType(Enum):
    png = 1
    apng = 2
    lottie = 3
    gif = 4

    @property
    def file_extension(self) -> str:
        return STICKER_FORMAT_LOOKUP[self]


STICKER_FORMAT_LOOKUP: Dict[StickerFormatType, str] = {
    StickerFormatType.png: "png",
    StickerFormatType.apng: "png",
    StickerFormatType.lottie: "json",
    StickerFormatType.gif: "gif",
}


class InviteTarget(Enum):
    unknown = 0
    stream = 1
    embedded_application = 2


class InteractionType(Enum):
    ping = 1
    application_command = 2
    component = 3
    application_command_autocomplete = 4
    modal_submit = 5


class InteractionResponseType(Enum):
    pong = 1
    # ack = 2 (deprecated)
    # channel_message = 3 (deprecated)
    channel_message = 4  # (with source)
    deferred_channel_message = 5  # (with source)
    deferred_message_update = 6  # for components
    message_update = 7  # for components
    application_command_autocomplete_result = 8  # for autocomplete
    modal = 9  # for modals


class VideoQualityMode(Enum):
    auto = 1
    full = 2

    def __int__(self) -> int:
        return self.value


class ComponentType(Enum):
    action_row = 1
    button = 2
    string_select = 3
    select = string_select  # backwards compatibility
    text_input = 4
    user_select = 5
    role_select = 6
    mentionable_select = 7
    channel_select = 8

    def __int__(self) -> int:
        return self.value


class ButtonStyle(Enum):
    primary = 1
    secondary = 2
    success = 3
    danger = 4
    link = 5

    # Aliases
    blurple = 1
    grey = 2
    gray = 2
    green = 3
    red = 4
    url = 5

    def __int__(self) -> int:
        return self.value


class TextInputStyle(Enum):
    short = 1
    paragraph = 2
    # Aliases
    single_line = 1
    multi_line = 2
    long = 2

    def __int__(self) -> int:
        return self.value


class ApplicationCommandType(Enum):
    chat_input = 1
    user = 2
    message = 3


class ApplicationCommandPermissionType(Enum):
    role = 1
    user = 2
    channel = 3

    def __int__(self) -> int:
        return self.value


class OptionType(Enum):
    sub_command = 1
    sub_command_group = 2
    string = 3
    integer = 4
    boolean = 5
    user = 6
    channel = 7
    role = 8
    mentionable = 9
    number = 10
    attachment = 11


class StagePrivacyLevel(Enum):
    public = 1
    closed = 2
    guild_only = 2


class NSFWLevel(Enum, comparable=True):
    default = 0
    explicit = 1
    safe = 2
    age_restricted = 3


class GuildScheduledEventEntityType(Enum):
    stage_instance = 1
    voice = 2
    external = 3


class GuildScheduledEventStatus(Enum):
    scheduled = 1
    active = 2
    completed = 3
    canceled = 4
    cancelled = 4


class GuildScheduledEventPrivacyLevel(Enum):
    guild_only = 2


class ThreadArchiveDuration(Enum):
    hour = 60
    day = 1440
    three_days = 4320
    week = 10080

    def __int__(self) -> int:
        return self.value


class WidgetStyle(Enum):
    shield = "shield"
    banner1 = "banner1"
    banner2 = "banner2"
    banner3 = "banner3"
    banner4 = "banner4"

    def __str__(self) -> str:
        return self.value


# reference: https://discord.com/developers/docs/reference#locales
class Locale(Enum):
    bg = "bg"
    "Bulgarian | български"  # noqa: RUF001
    cs = "cs"
    "Czech | Čeština"
    da = "da"
    "Danish | Dansk"
    de = "de"
    "German | Deutsch"
    el = "el"
    "Greek | Ελληνικά"  # noqa: RUF001
    en_GB = "en-GB"
    "English, UK | English, UK"
    en_US = "en-US"
    "English, US | English, US"
    es_ES = "es-ES"
    "Spanish | Español"
    fi = "fi"
    "Finnish | Suomi"
    fr = "fr"
    "French | Français"
    hi = "hi"
    "Hindi | हिन्दी"
    hr = "hr"
    "Croatian | Hrvatski"
    hu = "hu"
    "Hungarian | Magyar"
    id = "id"
    "Indonesian | Bahasa Indonesia"
    it = "it"
    "Italian | Italiano"
    ja = "ja"
    "Japanese | 日本語"
    ko = "ko"
    "Korean | 한국어"
    lt = "lt"
    "Lithuanian | Lietuviškai"
    nl = "nl"
    "Dutch | Nederlands"
    no = "no"
    "Norwegian | Norsk"
    pl = "pl"
    "Polish | Polski"
    pt_BR = "pt-BR"
    "Portuguese, Brazilian | Português do Brasil"
    ro = "ro"
    "Romanian, Romania | Română"
    ru = "ru"
    "Russian | Pусский"  # noqa: RUF001
    sv_SE = "sv-SE"
    "Swedish | Svenska"
    th = "th"
    "Thai | ไทย"
    tr = "tr"
    "Turkish | Türkçe"
    uk = "uk"
    "Ukrainian | Українська"  # noqa: RUF001
    vi = "vi"
    "Vietnamese | Tiếng Việt"
    zh_CN = "zh-CN"
    "Chinese, China | 中文"
    zh_TW = "zh-TW"
    "Chinese, Taiwan | 繁體中文"

    def __str__(self) -> str:
        return self.value


class AutoModActionType(Enum):
    block_message = 1
    send_alert_message = 2
    timeout = 3


class AutoModEventType(Enum):
    message_send = 1


class AutoModTriggerType(Enum):
    keyword = 1
    if not TYPE_CHECKING:
        harmful_link = 2  # obsolete/deprecated
    spam = 3
    keyword_preset = 4
    mention_spam = 5


class ThreadSortOrder(Enum):
    latest_activity = 0
    creation_date = 1


class ThreadLayout(Enum):
    not_set = 0
    list_view = 1
    gallery_view = 2


class Event(Enum):
    """Represents all the events of the library.

    These offer to register listeners/events in a more pythonic way; additionally autocompletion and documentation are both supported.

    .. versionadded:: 2.8

    """

    connect = "connect"
    """Called when the client has successfully connected to Discord.
    Represents the :func:`on_connect` event.
    """
    disconnect = "disconnect"
    """Called when the client has disconnected from Discord, or a connection attempt to Discord has failed.
    Represents the :func:`on_disconnect` event.
    """
    error = "error"
    """Called when an uncaught exception occurred.
    Represents the :func:`on_error` event.
    """
    gateway_error = "gateway_error"
    """Called when a known gateway event cannot be parsed.
    Represents the :func:`on_gateway_error` event.
    """
    ready = "ready"
    """Called when the client is done preparing the data received from Discord.
    Represents the :func:`on_ready` event.
    """
    resumed = "resumed"
    """Called when the client has resumed a session.
    Represents the :func:`on_resumed` event.
    """
    shard_connect = "shard_connect"
    """Called when a shard has successfully connected to Discord.
    Represents the :func:`on_shard_connect` event.
    """
    shard_disconnect = "shard_disconnect"
    """Called when a shard has disconnected from Discord.
    Represents the :func:`on_shard_disconnect` event.
    """
    shard_ready = "shard_ready"
    """Called when a shard has become ready.
    Represents the :func:`on_shard_ready` event.
    """
    shard_resumed = "shard_resumed"
    """Called when a shard has resumed a session.
    Represents the :func:`on_shard_resumed` event.
    """
    socket_event_type = "socket_event_type"
    """Called whenever a websocket event is received from the WebSocket.
    Represents the :func:`on_socket_event_type` event.
    """
    socket_raw_receive = "socket_raw_receive"
    """Called whenever a message is completely received from the WebSocket, before it's processed and parsed.
    Represents the :func:`on_socket_raw_receive` event.
    """
    socket_raw_send = "socket_raw_send"
    """Called whenever a send operation is done on the WebSocket before the message is sent.
    Represents the :func:`on_socket_raw_send` event.
    """
    guild_channel_create = "guild_channel_create"
    """Called whenever a guild channel is created.
    Represents the :func:`on_guild_channel_create` event.
    """
    guild_channel_update = "guild_channel_update"
    """Called whenever a guild channel is updated.
    Represents the :func:`on_guild_channel_update` event.
    """
    guild_channel_delete = "guild_channel_delete"
    """Called whenever a guild channel is deleted.
    Represents the :func:`on_guild_channel_delete` event.
    """
    guild_channel_pins_update = "guild_channel_pins_update"
    """Called whenever a message is pinned or unpinned from a guild channel.
    Represents the :func:`on_guild_channel_pins_update` event.
    """
    invite_create = "invite_create"
    """Called when an :class:`Invite` is created.
    Represents the :func:`.on_invite_create` event.
    """
    invite_delete = "invite_delete"
    """Called when an Invite is deleted.
    Represents the :func:`.on_invite_delete` event.
    """
    private_channel_update = "private_channel_update"
    """Called whenever a private group DM is updated.
    Represents the :func:`on_private_channel_update` event.
    """
    private_channel_pins_update = "private_channel_pins_update"
    """Called whenever a message is pinned or unpinned from a private channel.
    Represents the :func:`on_private_channel_pins_update` event.
    """
    webhooks_update = "webhooks_update"
    """Called whenever a webhook is created, modified, or removed from a guild channel.
    Represents the :func:`on_webhooks_update` event.
    """
    thread_create = "thread_create"
    """Called whenever a thread is created.
    Represents the :func:`on_thread_create` event.
    """
    thread_update = "thread_update"
    """Called when a thread is updated.
    Represents the :func:`on_thread_update` event.
    """
    thread_delete = "thread_delete"
    """Called when a thread is deleted.
    Represents the :func:`on_thread_delete` event.
    """
    thread_join = "thread_join"
    """Called whenever the bot joins a thread or gets access to a thread.
    Represents the :func:`on_thread_join` event.
    """
    thread_remove = "thread_remove"
    """Called whenever a thread is removed. This is different from a thread being deleted.
    Represents the :func:`on_thread_remove` event.
    """
    thread_member_join = "thread_member_join"
    """Called when a `ThreadMember` joins a `Thread`.
    Represents the :func:`on_thread_member_join` event.
    """
    thread_member_remove = "thread_member_remove"
    """Called when a `ThreadMember` leaves a `Thread`.
    Represents the :func:`on_thread_member_remove` event.
    """
    raw_thread_member_remove = "raw_thread_member_remove"
    """Called when a `ThreadMember` leaves `Thread` regardless of the thread member cache.
    Represents the :func:`on_raw_thread_member_remove` event.
    """
    raw_thread_update = "raw_thread_update"
    """Called whenever a thread is updated regardless of the state of the internal thread cache.
    Represents the :func:`on_raw_thread_update` event.
    """
    raw_thread_delete = "raw_thread_delete"
    """Called whenever a thread is deleted regardless of the state of the internal thread cache.
    Represents the :func:`on_raw_thread_delete` event.
    """
    guild_join = "guild_join"
    """Called when a `Guild` is either created by the `Client` or when the Client joins a guild.
    Represents the :func:`on_guild_join` event.
    """
    guild_remove = "guild_remove"
    """Called when a `Guild` is removed from the :class:`Client`.
    Represents the :func:`on_guild_remove` event.
    """
    guild_update = "guild_update"
    """Called when a `Guild` updates.
    Represents the :func:`on_guild_update` event.
    """
    guild_available = "guild_available"
    """Called when a guild becomes available.
    Represents the :func:`on_guild_available` event.
    """
    guild_unavailable = "guild_unavailable"
    """Called when a guild becomes unavailable.
    Represents the :func:`on_guild_unavailable` event.
    """
    guild_role_create = "guild_role_create"
    """Called when a `Guild` creates a new `Role`.
    Represents the :func:`on_guild_role_create` event.
    """
    guild_role_delete = "guild_role_delete"
    """Called when a `Guild` deletes a `Role`.
    Represents the :func:`on_guild_role_delete` event.
    """
    guild_role_update = "guild_role_update"
    """Called when a `Guild` updates a `Role`.
    Represents the :func:`on_guild_role_update` event.
    """
    guild_emojis_update = "guild_emojis_update"
    """Called when a `Guild` adds or removes `Emoji`.
    Represents the :func:`on_guild_emojis_update` event.
    """
    guild_stickers_update = "guild_stickers_update"
    """Called when a `Guild` updates its stickers.
    Represents the :func:`on_guild_stickers_update` event.
    """
    guild_integrations_update = "guild_integrations_update"
    """Called whenever an integration is created, modified, or removed from a guild.
    Represents the :func:`on_guild_integrations_update` event.
    """
    guild_scheduled_event_create = "guild_scheduled_event_create"
    """Called when a guild scheduled event is created.
    Represents the :func:`on_guild_scheduled_event_create` event.
    """
    guild_scheduled_event_update = "guild_scheduled_event_update"
    """Called when a guild scheduled event is updated.
    Represents the :func:`on_guild_scheduled_event_update` event.
    """
    guild_scheduled_event_delete = "guild_scheduled_event_delete"
    """Called when a guild scheduled event is deleted.
    Represents the :func:`on_guild_scheduled_event_delete` event.
    """
    guild_scheduled_event_subscribe = "guild_scheduled_event_subscribe"
    """Called when a user subscribes from a guild scheduled event.
    Represents the :func:`on_guild_scheduled_event_subscribe` event.
    """
    guild_scheduled_event_unsubscribe = "guild_scheduled_event_unsubscribe"
    """Called when a user unsubscribes from a guild scheduled event.
    Represents the :func:`on_guild_scheduled_event_unsubscribe` event.
    """
    raw_guild_scheduled_event_subscribe = "raw_guild_scheduled_event_subscribe"
    """Called when a user subscribes from a guild scheduled event regardless of the guild scheduled event cache.
    Represents the :func:`on_raw_guild_scheduled_event_subscribe` event.
    """
    raw_guild_scheduled_event_unsubscribe = "raw_guild_scheduled_event_unsubscribe"
    """Called when a user subscribes to or unsubscribes from a guild scheduled event regardless of the guild scheduled event cache.
    Represents the :func:`on_raw_guild_scheduled_event_unsubscribe` event.
    """
    application_command_permissions_update = "application_command_permissions_update"
    """Called when the permissions of an application command or the application-wide command permissions are updated.
    Represents the :func:`on_application_command_permissions_update` event.
    """
    automod_action_execution = "automod_action_execution"
    """Called when an auto moderation action is executed due to a rule triggering for a particular event.
    Represents the :func:`on_automod_action_execution` event.
    """
    automod_rule_create = "automod_rule_create"
    """Called when an `AutoModRule` is created.
    Represents the :func:`on_automod_rule_create` event.
    """
    automod_rule_update = "automod_rule_update"
    """Called when an `AutoModRule` is updated.
    Represents the :func:`on_automod_rule_update` event.
    """
    automod_rule_delete = "automod_rule_delete"
    """Called when an `AutoModRule` is deleted.
    Represents the :func:`on_automod_rule_delete` event.
    """
    audit_log_entry_create = "audit_log_entry_create"
    """Called when an audit log entry is created.
    Represents the :func:`on_audit_log_entry_create` event.
    """
    integration_create = "integration_create"
    """Called when an integration is created.
    Represents the :func:`on_integration_create` event.
    """
    integration_update = "integration_update"
    """Called when an integration is updated.
    Represents the :func:`on_integration_update` event.
    """
    raw_integration_delete = "raw_integration_delete"
    """Called when an integration is deleted.
    Represents the :func:`on_raw_integration_delete` event.
    """
    member_join = "member_join"
    """Called when a `Member` joins a `Guild`.
    Represents the :func:`on_member_join` event.
    """
    member_remove = "member_remove"
    """Called when a `Member` leaves a `Guild`.
    Represents the :func:`on_member_remove` event.
    """
    member_update = "member_update"
    """Called when a `Member` is updated in a `Guild`.
    Represents the :func:`on_member_update` event.
    """
    raw_member_remove = "raw_member_remove"
    """Called when a member leaves a `Guild` regardless of the member cache.
    Represents the :func:`on_raw_member_remove` event.
    """
    raw_member_update = "raw_member_update"
    """Called when a `Member` is updated in a `Guild` regardless of the member cache.
    Represents the :func:`on_raw_member_update` event.
    """
    member_ban = "member_ban"
    """Called when user gets banned from a `Guild`.
    Represents the :func:`on_member_ban` event.
    """
    member_unban = "member_unban"
    """Called when a `User` gets unbanned from a `Guild`.
    Represents the :func:`on_member_unban` event.
    """
    presence_update = "presence_update"
    """Called when a `Member` updates their presence.
    Represents the :func:`on_presence_update` event.
    """
    user_update = "user_update"
    """Called when a `User` is updated.
    Represents the :func:`on_user_update` event.
    """
    voice_state_update = "voice_state_update"
    """Called when a `Member` changes their `VoiceState`.
    Represents the :func:`on_voice_state_update` event.
    """
    stage_instance_create = "stage_instance_create"
    """Called when a `StageInstance` is created for a `StageChannel`.
    Represents the :func:`on_stage_instance_create` event.
    """
    stage_instance_delete = "stage_instance_delete"
    """Called when a `StageInstance` is deleted for a `StageChannel`.
    Represents the :func:`on_stage_instance_delete` event.
    """
    stage_instance_update = "stage_instance_update"
    """Called when a `StageInstance` is updated.
    Represents the :func:`on_stage_instance_update` event.
    """
    application_command = "application_command"
    """Called when an application command is invoked.
    Represents the :func:`on_application_command` event.
    """
    application_command_autocomplete = "application_command_autocomplete"
    """Called when an application command autocomplete is called.
    Represents the :func:`on_application_command_autocomplete` event.
    """
    button_click = "button_click"
    """Called when a button is clicked.
    Represents the :func:`on_button_click` event.
    """
    dropdown = "dropdown"
    """Called when a select menu is clicked.
    Represents the :func:`on_dropdown` event.
    """
    interaction = "interaction"
    """Called when an interaction happened.
    Represents the :func:`on_interaction` event.
    """
    message_interaction = "message_interaction"
    """Called when a message interaction happened.
    Represents the :func:`on_message_interaction` event.
    """
    modal_submit = "modal_submit"
    """Called when a modal is submitted.
    Represents the :func:`on_modal_submit` event.
    """
    message = "message"
    """Called when a `Message` is created and sent.
    Represents the :func:`on_message` event.
    """
    message_edit = "message_edit"
    """Called when a `Message` receives an update event.
    Represents the :func:`on_message_edit` event.
    """
    message_delete = "message_delete"
    """Called when a message is deleted.
    Represents the :func:`on_message_delete` event.
    """
    bulk_message_delete = "bulk_message_delete"
    """Called when messages are bulk deleted.
    Represents the :func:`on_bulk_message_delete` event.
    """
    raw_message_edit = "raw_message_edit"
    """Called when a message is edited regardless of the state of the internal message cache.
    Represents the :func:`on_raw_message_edit` event.
    """
    raw_message_delete = "raw_message_delete"
    """Called when a message is deleted regardless of the message being in the internal message cache or not.
    Represents the :func:`on_raw_message_delete` event.
    """
    raw_bulk_message_delete = "raw_bulk_message_delete"
    """Called when a bulk delete is triggered regardless of the messages being in the internal message cache or not.
    Represents the :func:`on_raw_bulk_message_delete` event.
    """
    reaction_add = "reaction_add"
    """Called when a message has a reaction added to it.
    Represents the :func:`on_reaction_add` event.
    """
    reaction_remove = "reaction_remove"
    """Called when a message has a reaction removed from it.
    Represents the :func:`on_reaction_remove` event.
    """
    reaction_clear = "reaction_clear"
    """Called when a message has all its reactions removed from it.
    Represents the :func:`on_reaction_clear` event.
    """
    reaction_clear_emoji = "reaction_clear_emoji"
    """Called when a message has a specific reaction removed from it.
    Represents the :func:`on_reaction_clear_emoji` event.
    """
    raw_reaction_add = "raw_reaction_add"
    """Called when a message has a reaction added regardless of the state of the internal message cache.
    Represents the :func:`on_raw_reaction_add` event.
    """
    raw_reaction_remove = "raw_reaction_remove"
    """Called when a message has a reaction removed regardless of the state of the internal message cache.
    Represents the :func:`on_raw_reaction_remove` event.
    """
    raw_reaction_clear = "raw_reaction_clear"
    """Called when a message has all its reactions removed regardless of the state of the internal message cache.
    Represents the :func:`on_raw_reaction_clear` event.
    """
    raw_reaction_clear_emoji = "raw_reaction_clear_emoji"
    """Called when a message has a specific reaction removed from it regardless of the state of the internal message cache.
    Represents the :func:`on_raw_reaction_clear_emoji` event.
    """
    typing = "typing"
    """Called when someone begins typing a message.
    Represents the :func:`on_typing` event.
    """
    raw_typing = "raw_typing"
    """Called when someone begins typing a message regardless of whether `Intents.members` and `Intents.guilds` are enabled.
    Represents the :func:`on_raw_typing` event.
    """
    # ext.commands events
    command = "command"
    """Called when a command is found and is about to be invoked.
    Represents the :func:`.on_command` event.
    """
    command_completion = "command_completion"
    """Called when a command has completed its invocation.
    Represents the :func:`.on_command_completion` event.
    """
    command_error = "command_error"
    """Called when an error is raised inside a command either through user input error, check failure, or an error in your own code.
    Represents the :func:`.on_command_error` event.
    """
    slash_command = "slash_command"
    """Called when a slash command is found and is about to be invoked.
    Represents the :func:`.on_slash_command` event.
    """
    slash_command_completion = "slash_command_completion"
    """Called when a slash command has completed its invocation.
    Represents the :func:`.on_slash_command_completion` event.
    """
    slash_command_error = "slash_command_error"
    """Called when an error is raised inside a slash command either through user input error, check failure, or an error in your own code.
    Represents the :func:`.on_slash_command_error` event.
    """
    user_command = "user_command"
    """Called when a user command is found and is about to be invoked.
    Represents the :func:`.on_user_command` event.
    """
    user_command_completion = "user_command_completion"
    """Called when a user command has completed its invocation.
    Represents the :func:`.on_user_command_completion` event.
    """
    user_command_error = "user_command_error"
    """Called when an error is raised inside a user command either through check failure, or an error in your own code.
    Represents the :func:`.on_user_command_error` event.
    """
    message_command = "message_command"
    """Called when a message command is found and is about to be invoked.
    Represents the :func:`.on_message_command` event.
    """
    message_command_completion = "message_command_completion"
    """Called when a message command has completed its invocation.
    Represents the :func:`.on_message_command_completion` event.
    """
    message_command_error = "message_command_error"
    """Called when an error is raised inside a message command either through check failure, or an error in your own code.
    Represents the :func:`.on_message_command_error` event.
    """


class ApplicationRoleConnectionMetadataType(Enum):
    integer_less_than_or_equal = 1
    integer_greater_than_or_equal = 2
    integer_equal = 3
    integer_not_equal = 4
    datetime_less_than_or_equal = 5
    datetime_greater_than_or_equal = 6
    boolean_equal = 7
    boolean_not_equal = 8


class OnboardingPromptType(Enum):
    multiple_choice = 0
    dropdown = 1


T = TypeVar("T")


def create_unknown_value(cls: Type[T], val: Any) -> T:
    value_cls = cls._enum_value_cls_  # type: ignore
    name = f"unknown_{val}"
    return value_cls(name=name, value=val)


def try_enum(cls: Type[T], val: Any) -> T:
    """A function that tries to turn the value into enum ``cls``.

    If it fails it returns a proxy invalid value instead.
    """
    try:
        return cls._enum_value_map_[val]  # type: ignore
    except (KeyError, TypeError, AttributeError):
        return create_unknown_value(cls, val)


def enum_if_int(cls: Type[T], val: Any) -> T:
    """A function that tries to turn the value into enum ``cls``.

    If it fails it returns a proxy invalid value instead.
    """
    if not isinstance(val, int):
        return val
    return try_enum(cls, val)


def try_enum_to_int(val: Any) -> Any:
    if isinstance(val, int):
        return val
    try:
        return val.value
    except Exception:
        return val
