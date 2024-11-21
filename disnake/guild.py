# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import datetime
import unicodedata
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Iterable,
    List,
    Literal,
    NamedTuple,
    NewType,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
    overload,
)

from . import abc, utils
from .app_commands import GuildApplicationCommandPermissions
from .asset import Asset
from .automod import AutoModAction, AutoModRule
from .bans import BanEntry, BulkBanResult
from .channel import (
    CategoryChannel,
    ForumChannel,
    MediaChannel,
    StageChannel,
    TextChannel,
    VoiceChannel,
    _guild_channel_factory,
    _threaded_guild_channel_factory,
)
from .colour import Colour
from .emoji import Emoji
from .enums import (
    AuditLogAction,
    AutoModEventType,
    AutoModTriggerType,
    ChannelType,
    ContentFilter,
    GuildScheduledEventEntityType,
    GuildScheduledEventPrivacyLevel,
    Locale,
    NotificationLevel,
    NSFWLevel,
    ThreadLayout,
    ThreadSortOrder,
    VerificationLevel,
    VideoQualityMode,
    WidgetStyle,
    try_enum,
    try_enum_to_int,
)
from .errors import ClientException, HTTPException, InvalidData
from .file import File
from .flags import SystemChannelFlags
from .guild_scheduled_event import GuildScheduledEvent, GuildScheduledEventMetadata
from .integrations import Integration, _integration_factory
from .invite import Invite
from .iterators import AuditLogIterator, BanIterator, MemberIterator
from .member import Member, VoiceState
from .mixins import Hashable
from .object import Object
from .onboarding import Onboarding
from .partial_emoji import PartialEmoji
from .permissions import PermissionOverwrite
from .role import Role
from .stage_instance import StageInstance
from .sticker import GuildSticker
from .threads import Thread, ThreadMember
from .user import User
from .voice_region import VoiceRegion
from .welcome_screen import WelcomeScreen, WelcomeScreenChannel
from .widget import Widget, WidgetSettings

__all__ = (
    "Guild",
    "GuildBuilder",
)

VocalGuildChannel = Union[VoiceChannel, StageChannel]
MISSING = utils.MISSING

if TYPE_CHECKING:
    from .abc import Snowflake, SnowflakeTime
    from .app_commands import APIApplicationCommand
    from .asset import AssetBytes
    from .automod import AutoModTriggerMetadata
    from .interactions import Interaction
    from .permissions import Permissions
    from .state import ConnectionState
    from .template import Template
    from .threads import AnyThreadArchiveDuration, ForumTag
    from .types.channel import PermissionOverwrite as PermissionOverwritePayload
    from .types.guild import (
        Ban as BanPayload,
        CreateGuildPlaceholderChannel,
        CreateGuildPlaceholderRole,
        Guild as GuildPayload,
        GuildFeature,
        MFALevel,
        PartialGuild as PartialGuildPayload,
    )
    from .types.integration import IntegrationType
    from .types.role import CreateRole as CreateRolePayload
    from .types.sticker import CreateGuildSticker as CreateStickerPayload
    from .types.threads import Thread as ThreadPayload, ThreadArchiveDurationLiteral
    from .types.voice import GuildVoiceState
    from .voice_client import VoiceProtocol
    from .webhook import Webhook

    GuildMessageable = Union[TextChannel, Thread, VoiceChannel, StageChannel]
    GuildChannel = Union[
        VoiceChannel, StageChannel, TextChannel, CategoryChannel, ForumChannel, MediaChannel
    ]
    ByCategoryItem = Tuple[Optional[CategoryChannel], List[GuildChannel]]


class _GuildLimit(NamedTuple):
    emoji: int
    stickers: int
    bitrate: float
    filesize: int


class Guild(Hashable):
    """Represents a Discord guild.

    This is referred to as a "server" in the official Discord UI.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two guilds are equal.

        .. describe:: x != y

            Checks if two guilds are not equal.

        .. describe:: hash(x)

            Returns the guild's hash.

        .. describe:: str(x)

            Returns the guild's name.

    Attributes
    ----------
    name: :class:`str`
        The guild's name.
    emojis: Tuple[:class:`Emoji`, ...]
        All emojis that the guild owns.
    stickers: Tuple[:class:`GuildSticker`, ...]
        All stickers that the guild owns.

        .. versionadded:: 2.0

    afk_timeout: :class:`int`
        The timeout to get sent to the AFK channel.
    afk_channel: Optional[:class:`VoiceChannel`]
        The channel that denotes the AFK channel. ``None`` if it doesn't exist.
    id: :class:`int`
        The guild's ID.
    owner_id: :class:`int`
        The guild owner's ID. Use :attr:`Guild.owner` if you need a :class:`Member` object instead.
    unavailable: :class:`bool`
        Whether the guild is unavailable. If this is ``True`` then the
        reliability of other attributes outside of :attr:`Guild.id` is slim and they might
        all be ``None``. It is best to not do anything with the guild if it is unavailable.

        Check :func:`on_guild_unavailable` and :func:`on_guild_available` events.
    max_presences: Optional[:class:`int`]
        The maximum amount of presences for the guild.
    max_members: Optional[:class:`int`]
        The maximum amount of members for the guild.

        .. note::

            This attribute is only available via :meth:`.Client.fetch_guild`.
    max_video_channel_users: Optional[:class:`int`]
        The maximum amount of users in a video channel.

        .. versionadded:: 1.4

    max_stage_video_channel_users: Optional[:class:`int`]
        The maximum amount of users in a stage video channel.

        .. versionadded: 2.9

    description: Optional[:class:`str`]
        The guild's description.
    mfa_level: :class:`int`
        Indicates the guild's two-factor authentication level. If this value is 0 then
        the guild does not require 2FA for their administrative members
        to take moderation actions. If the value is 1, then 2FA is required.
    verification_level: :class:`VerificationLevel`
        The guild's verification level.
    explicit_content_filter: :class:`ContentFilter`
        The guild's explicit content filter.
    default_notifications: :class:`NotificationLevel`
        The guild's notification settings.
    features: List[:class:`str`]
        A list of features that the guild has. The features that a guild can have are
        subject to arbitrary change by Discord.

        A partial list of features is below:

        - ``ANIMATED_BANNER``: Guild can upload an animated banner.
        - ``ANIMATED_ICON``: Guild can upload an animated icon.
        - ``AUTO_MODERATION``: Guild has set up auto moderation rules.
        - ``BANNER``: Guild can upload and use a banner. (i.e. :attr:`.banner`)
        - ``COMMUNITY``: Guild is a community server.
        - ``CREATOR_MONETIZABLE_PROVISIONAL``: Guild has enabled monetization.
        - ``CREATOR_STORE_PAGE``: Guild has enabled the role subscription promo page.
        - ``DEVELOPER_SUPPORT_SERVER``: Guild is set as a support server in the app directory.
        - ``DISCOVERABLE``: Guild shows up in Server Discovery.
        - ``ENABLED_DISCOVERABLE_BEFORE``: Guild had Server Discovery enabled at least once.
        - ``FEATURABLE``: Guild is able to be featured in Server Discovery.
        - ``HAS_DIRECTORY_ENTRY``: Guild is listed in a student hub.
        - ``HUB``: Guild is a student hub.
        - ``INVITE_SPLASH``: Guild's invite page can have a special splash.
        - ``INVITES_DISABLED``: Guild has paused invites, preventing new users from joining.
        - ``LINKED_TO_HUB``: Guild is linked to a student hub.
        - ``MEMBER_VERIFICATION_GATE_ENABLED``: Guild has Membership Screening enabled.
        - ``MORE_EMOJI``: Guild has increased custom emoji slots.
        - ``MORE_STICKERS``: Guild has increased custom sticker slots.
        - ``NEWS``: Guild can create news channels.
        - ``NEW_THREAD_PERMISSIONS``: Guild is using the new thread permission system.
        - ``PARTNERED``: Guild is a partnered server.
        - ``PREVIEW_ENABLED``: Guild can be viewed before being accepted via Membership Screening.
        - ``PRIVATE_THREADS``: Guild has access to create private threads (no longer has any effect).
        - ``RAID_ALERTS_DISABLED``: Guild has disabled alerts for join raids in the configured safety alerts channel.
        - ``ROLE_ICONS``: Guild has access to role icons.
        - ``ROLE_SUBSCRIPTIONS_AVAILABLE_FOR_PURCHASE``: Guild has role subscriptions that can be purchased.
        - ``ROLE_SUBSCRIPTIONS_ENABLED``: Guild has enabled role subscriptions.
        - ``SEVEN_DAY_THREAD_ARCHIVE``: Guild has access to the seven day archive time for threads (no longer has any effect).
        - ``TEXT_IN_VOICE_ENABLED``: Guild has text in voice channels enabled (no longer has any effect).
        - ``THREE_DAY_THREAD_ARCHIVE``: Guild has access to the three day archive time for threads (no longer has any effect).
        - ``THREADS_ENABLED``: Guild has access to threads (no longer has any effect).
        - ``TICKETED_EVENTS_ENABLED``: Guild has enabled ticketed events (no longer has any effect).
        - ``VANITY_URL``: Guild can have a vanity invite URL (e.g. discord.gg/disnake).
        - ``VERIFIED``: Guild is a verified server.
        - ``VIP_REGIONS``: Guild has VIP voice regions.
        - ``WELCOME_SCREEN_ENABLED``: Guild has enabled the welcome screen.
    premium_progress_bar_enabled: :class:`bool`
        Whether the server boost progress bar is enabled.
    premium_tier: :class:`int`
        The premium tier for this guild. Corresponds to "Nitro Server" in the official UI.
        The number goes from 0 to 3 inclusive.
    premium_subscription_count: :class:`int`
        The number of "boosts" this guild currently has.
    preferred_locale: :class:`Locale`
        The preferred locale for the guild. Used when filtering Server Discovery
        results to a specific language.

        .. versionchanged:: 2.5
            Changed to :class:`Locale` instead of :class:`str`.

    nsfw_level: :class:`NSFWLevel`
        The guild's NSFW level.

        .. versionadded:: 2.0

    approximate_member_count: Optional[:class:`int`]
        The approximate number of members in the guild.
        Only available for manually fetched guilds.

        .. versionadded:: 2.3

    approximate_presence_count: Optional[:class:`int`]
        The approximate number of members currently active in the guild.
        This includes idle, dnd, online, and invisible members. Offline members are excluded.
        Only available for manually fetched guilds.

        .. versionadded:: 2.3

    widget_enabled: Optional[:class:`bool`]
        Whether the widget is enabled.

        .. versionadded:: 2.5

        .. note::

            This value is unreliable and will only be set after the guild was updated at least once.
            Avoid using this and use :func:`widget_settings` instead.

    widget_channel_id: Optional[:class:`int`]
        The widget channel ID, if set.

        .. versionadded:: 2.5

        .. note::

            This value is unreliable and will only be set after the guild was updated at least once.
            Avoid using this and use :func:`widget_settings` instead.

    vanity_url_code: Optional[:class:`str`]
        The vanity invite code for this guild, if set.

        To get a full :class:`Invite` object, see :attr:`Guild.vanity_invite`.

        .. versionadded:: 2.5
    """

    __slots__ = (
        "afk_timeout",
        "afk_channel",
        "name",
        "id",
        "unavailable",
        "owner_id",
        "mfa_level",
        "emojis",
        "stickers",
        "features",
        "verification_level",
        "explicit_content_filter",
        "default_notifications",
        "description",
        "max_presences",
        "max_members",
        "max_video_channel_users",
        "max_stage_video_channel_users",
        "premium_progress_bar_enabled",
        "premium_tier",
        "premium_subscription_count",
        "preferred_locale",
        "nsfw_level",
        "approximate_member_count",
        "approximate_presence_count",
        "widget_enabled",
        "widget_channel_id",
        "vanity_url_code",
        "_members",
        "_channels",
        "_icon",
        "_banner",
        "_state",
        "_roles",
        "_member_count",
        "_large",
        "_splash",
        "_voice_states",
        "_system_channel_id",
        "_system_channel_flags",
        "_discovery_splash",
        "_rules_channel_id",
        "_public_updates_channel_id",
        "_stage_instances",
        "_scheduled_events",
        "_threads",
        "_region",
        "_safety_alerts_channel_id",
    )

    _PREMIUM_GUILD_LIMITS: ClassVar[Dict[Optional[int], _GuildLimit]] = {
        None: _GuildLimit(emoji=50, stickers=5, bitrate=96e3, filesize=26214400),
        0: _GuildLimit(emoji=50, stickers=5, bitrate=96e3, filesize=26214400),
        1: _GuildLimit(emoji=100, stickers=15, bitrate=128e3, filesize=26214400),
        2: _GuildLimit(emoji=150, stickers=30, bitrate=256e3, filesize=52428800),
        3: _GuildLimit(emoji=250, stickers=60, bitrate=384e3, filesize=104857600),
    }

    def __init__(self, *, data: GuildPayload, state: ConnectionState) -> None:
        self._channels: Dict[int, GuildChannel] = {}
        self._members: Dict[int, Member] = {}
        self._voice_states: Dict[int, VoiceState] = {}
        self._threads: Dict[int, Thread] = {}
        self._stage_instances: Dict[int, StageInstance] = {}
        self._scheduled_events: Dict[int, GuildScheduledEvent] = {}
        self._state: ConnectionState = state
        self._from_data(data)

    def _add_channel(self, channel: GuildChannel, /) -> None:
        self._channels[channel.id] = channel

    def _remove_channel(self, channel: Snowflake, /) -> None:
        self._channels.pop(channel.id, None)

    def _voice_state_for(self, user_id: int, /) -> Optional[VoiceState]:
        return self._voice_states.get(user_id)

    def _add_member(self, member: Member, /) -> None:
        self._members[member.id] = member

    def _store_thread(self, payload: ThreadPayload, /) -> Thread:
        thread = Thread(guild=self, state=self._state, data=payload)
        self._threads[thread.id] = thread
        return thread

    def _remove_member(self, member: Snowflake, /) -> None:
        self._members.pop(member.id, None)

    def _add_thread(self, thread: Thread, /) -> None:
        self._threads[thread.id] = thread

    def _remove_thread(self, thread: Snowflake, /) -> None:
        self._threads.pop(thread.id, None)

    def _clear_threads(self) -> None:
        self._threads.clear()

    def _remove_threads_by_channel(self, channel_id: int) -> None:
        to_remove = [k for k, t in self._threads.items() if t.parent_id == channel_id]
        for k in to_remove:
            del self._threads[k]

    def _filter_threads(self, channel_ids: Set[int]) -> Dict[int, Thread]:
        to_remove: Dict[int, Thread] = {
            k: t for k, t in self._threads.items() if t.parent_id in channel_ids
        }
        for k in to_remove:
            del self._threads[k]
        return to_remove

    def __str__(self) -> str:
        return self.name or ""

    def __repr__(self) -> str:
        attrs = (
            ("id", self.id),
            ("name", self.name),
            ("shard_id", self.shard_id),
            ("chunked", self.chunked),
            ("member_count", getattr(self, "_member_count", None)),
        )
        inner = " ".join(f"{k!s}={v!r}" for k, v in attrs)
        return f"<Guild {inner}>"

    def _update_voice_state(
        self, data: GuildVoiceState, channel_id: Optional[int]
    ) -> Tuple[Optional[Member], VoiceState, VoiceState]:
        user_id = int(data["user_id"])
        channel: Optional[VocalGuildChannel] = self.get_channel(channel_id)  # type: ignore
        try:
            # check if we should remove the voice state from cache
            if channel is None:
                after = self._voice_states.pop(user_id)
            else:
                after = self._voice_states[user_id]

            before = copy.copy(after)
            after._update(data, channel)
        except KeyError:
            # if we're here then we're getting added into the cache
            after = VoiceState(data=data, channel=channel)
            before = VoiceState(data=data, channel=None)
            self._voice_states[user_id] = after

        member = self.get_member(user_id)
        if member is None:
            try:
                member = Member(data=data["member"], state=self._state, guild=self)
            except KeyError:
                member = None

        return member, before, after

    def _add_role(self, role: Role, /) -> None:
        # roles get added to the bottom (position 1, pos 0 is @everyone)
        # so since self.roles has the @everyone role, we can't increment
        # its position because it's stuck at position 0. Luckily x += False
        # is equivalent to adding 0. So we cast the position to a bool and
        # increment it.
        for r in self._roles.values():
            r.position += not r.is_default()

        self._roles[role.id] = role

    def _remove_role(self, role_id: int, /) -> Role:
        # this raises KeyError if it fails..
        role = self._roles.pop(role_id)

        # since it didn't, we can change the positions now
        # basically the same as above except we only decrement
        # the position if we're above the role we deleted.
        for r in self._roles.values():
            r.position -= r.position > role.position

        return role

    def get_command(self, application_command_id: int, /) -> Optional[APIApplicationCommand]:
        """Gets a cached application command matching the specified ID.

        Parameters
        ----------
        application_command_id: :class:`int`
            The application command ID to search for.

        Returns
        -------
        Optional[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            The application command if found, or ``None`` otherwise.
        """
        return self._state._get_guild_application_command(self.id, application_command_id)

    def get_command_named(self, name: str, /) -> Optional[APIApplicationCommand]:
        """Gets a cached application command matching the specified name.

        Parameters
        ----------
        name: :class:`str`
            The application command name to search for.

        Returns
        -------
        Optional[Union[:class:`.APIUserCommand`, :class:`.APIMessageCommand`, :class:`.APISlashCommand`]]
            The application command if found, or ``None`` otherwise.
        """
        return self._state._get_guild_command_named(self.id, name)

    def _from_data(self, guild: GuildPayload) -> None:
        # according to Stan, this is always available even if the guild is unavailable
        # I don't have this guarantee when someone updates the guild.
        member_count = guild.get("member_count", None)
        if member_count is not None:
            self._member_count: int = member_count

        self.name: str = guild.get("name", "")
        self._region: str = guild.get("region", "")
        self.verification_level: VerificationLevel = try_enum(
            VerificationLevel, guild.get("verification_level")
        )
        self.default_notifications: NotificationLevel = try_enum(
            NotificationLevel, guild.get("default_message_notifications")
        )
        self.explicit_content_filter: ContentFilter = try_enum(
            ContentFilter, guild.get("explicit_content_filter", 0)
        )
        self.afk_timeout: int = guild.get("afk_timeout", 0)
        self._icon: Optional[str] = guild.get("icon")
        self._banner: Optional[str] = guild.get("banner")
        self.unavailable: bool = guild.get("unavailable", False)
        self.id: int = int(guild["id"])
        self._roles: Dict[int, Role] = {}
        state = self._state  # speed up attribute access
        for r in guild.get("roles", []):
            role = Role(guild=self, data=r, state=state)
            self._roles[role.id] = role

        self.mfa_level: MFALevel = guild.get("mfa_level", 0)
        self.emojis: Tuple[Emoji, ...] = tuple(
            state.store_emoji(self, d) for d in guild.get("emojis", [])
        )
        self.stickers: Tuple[GuildSticker, ...] = tuple(
            state.store_sticker(self, d) for d in guild.get("stickers", [])
        )
        self.features: List[GuildFeature] = guild.get("features", [])
        self._splash: Optional[str] = guild.get("splash")
        self._system_channel_id: Optional[int] = utils._get_as_snowflake(guild, "system_channel_id")
        self.description: Optional[str] = guild.get("description")
        self.max_presences: Optional[int] = guild.get("max_presences")
        self.max_members: Optional[int] = guild.get("max_members")
        self.max_video_channel_users: Optional[int] = guild.get("max_video_channel_users")
        self.max_stage_video_channel_users: Optional[int] = guild.get(
            "max_stage_video_channel_users"
        )
        self.premium_tier: int = guild.get("premium_tier", 0)
        self.premium_subscription_count: int = guild.get("premium_subscription_count") or 0
        self._system_channel_flags: int = guild.get("system_channel_flags", 0)
        self.preferred_locale: Locale = try_enum(Locale, guild.get("preferred_locale"))
        self._discovery_splash: Optional[str] = guild.get("discovery_splash")
        self._rules_channel_id: Optional[int] = utils._get_as_snowflake(guild, "rules_channel_id")
        self._public_updates_channel_id: Optional[int] = utils._get_as_snowflake(
            guild, "public_updates_channel_id"
        )
        self.nsfw_level: NSFWLevel = try_enum(NSFWLevel, guild.get("nsfw_level", 0))
        self.premium_progress_bar_enabled: bool = guild.get("premium_progress_bar_enabled", False)
        self.approximate_presence_count: Optional[int] = guild.get("approximate_presence_count")
        self.approximate_member_count: Optional[int] = guild.get("approximate_member_count")
        self.widget_enabled: Optional[bool] = guild.get("widget_enabled")
        self.widget_channel_id: Optional[int] = utils._get_as_snowflake(guild, "widget_channel_id")
        self.vanity_url_code: Optional[str] = guild.get("vanity_url_code")
        self._safety_alerts_channel_id: Optional[int] = utils._get_as_snowflake(
            guild, "safety_alerts_channel_id"
        )

        stage_instances = guild.get("stage_instances")
        if stage_instances is not None:
            self._stage_instances = {}
            for s in stage_instances:
                stage_instance = StageInstance(guild=self, data=s, state=state)
                self._stage_instances[stage_instance.id] = stage_instance

        scheduled_events = guild.get("guild_scheduled_events")
        if scheduled_events is not None:
            self._scheduled_events = {}
            for e in scheduled_events:
                scheduled_event = GuildScheduledEvent(state=state, data=e)
                self._scheduled_events[scheduled_event.id] = scheduled_event

        cache_joined = self._state.member_cache_flags.joined
        self_id = self._state.self_id
        for mdata in guild.get("members", []):
            # NOTE: Are we sure it's fine to not have the user part here?
            member = Member(data=mdata, guild=self, state=state)  # type: ignore
            if cache_joined or member.id == self_id:
                self._add_member(member)

        self._sync(guild)
        self._large: Optional[bool] = None if member_count is None else self._member_count >= 250

        self.owner_id: Optional[int] = utils._get_as_snowflake(guild, "owner_id")
        self.afk_channel: Optional[VocalGuildChannel] = self.get_channel(utils._get_as_snowflake(guild, "afk_channel_id"))  # type: ignore

        for obj in guild.get("voice_states", []):
            self._update_voice_state(obj, utils._get_as_snowflake(obj, "channel_id"))

    # TODO: refactor/remove?
    def _sync(self, data: GuildPayload) -> None:
        try:
            self._large = data["large"]
        except KeyError:
            pass

        empty_tuple = ()
        for presence in data.get("presences", []):
            user_id = int(presence["user"]["id"])
            member = self.get_member(user_id)
            if member is not None:
                member._presence_update(presence, empty_tuple)  # type: ignore

        if "channels" in data:
            channels = data["channels"]
            for c in channels:
                factory, _ = _guild_channel_factory(c["type"])
                if factory:
                    self._add_channel(factory(guild=self, data=c, state=self._state))  # type: ignore

        if "threads" in data:
            threads = data["threads"]
            for thread in threads:
                self._add_thread(Thread(guild=self, state=self._state, data=thread))

    @property
    def channels(self) -> List[GuildChannel]:
        """List[:class:`abc.GuildChannel`]: A list of channels that belong to this guild."""
        return list(self._channels.values())

    @property
    def threads(self) -> List[Thread]:
        """List[:class:`Thread`]: A list of threads that you have permission to view.

        .. versionadded:: 2.0
        """
        return list(self._threads.values())

    @property
    def large(self) -> bool:
        """:class:`bool`: Whether the guild is a 'large' guild.

        A large guild is defined as having more than ``large_threshold`` count
        members, which for this library is set to the maximum of 250.
        """
        if self._large is None:
            try:
                return self._member_count >= 250
            except AttributeError:
                return len(self._members) >= 250
        return self._large

    @property
    def voice_channels(self) -> List[VoiceChannel]:
        """List[:class:`VoiceChannel`]: A list of voice channels that belong to this guild.

        This is sorted by the position and are in UI order from top to bottom.
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, VoiceChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def stage_channels(self) -> List[StageChannel]:
        """List[:class:`StageChannel`]: A list of stage channels that belong to this guild.

        .. versionadded:: 1.7

        This is sorted by the position and are in UI order from top to bottom.
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, StageChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def forum_channels(self) -> List[ForumChannel]:
        """List[:class:`ForumChannel`]: A list of forum channels that belong to this guild.

        This is sorted by the position and are in UI order from top to bottom.

        .. versionadded:: 2.5
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, ForumChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def media_channels(self) -> List[MediaChannel]:
        """List[:class:`MediaChannel`]: A list of media channels that belong to this guild.

        This is sorted by the position and are in UI order from top to bottom.

        .. versionadded:: 2.10
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, MediaChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def me(self) -> Member:
        """:class:`Member`: Similar to :attr:`Client.user` except an instance of :class:`Member`.
        This is essentially used to get the member version of yourself.
        """
        self_id = self._state.user.id
        # The self member is *always* cached
        return self.get_member(self_id)  # type: ignore

    @property
    def voice_client(self) -> Optional[VoiceProtocol]:
        """Optional[:class:`VoiceProtocol`]: Returns the :class:`VoiceProtocol` associated with this guild, if any."""
        return self._state._get_voice_client(self.id)

    @property
    def text_channels(self) -> List[TextChannel]:
        """List[:class:`TextChannel`]: A list of text channels that belong to this guild.

        This is sorted by the position and are in UI order from top to bottom.
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, TextChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def categories(self) -> List[CategoryChannel]:
        """List[:class:`CategoryChannel`]: A list of categories that belong to this guild.

        This is sorted by the position and are in UI order from top to bottom.
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, CategoryChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    def by_category(self) -> List[ByCategoryItem]:
        """Returns every :class:`CategoryChannel` and their associated channels.

        These channels and categories are sorted in the official Discord UI order.

        If the channels do not have a category, then the first element of the tuple is
        ``None``.

        Returns
        -------
        List[Tuple[Optional[:class:`CategoryChannel`], List[:class:`abc.GuildChannel`]]]:
            The categories and their associated channels.
        """
        grouped: Dict[Optional[int], List[GuildChannel]] = {}
        for channel in self._channels.values():
            if isinstance(channel, CategoryChannel):
                grouped.setdefault(channel.id, [])
                continue

            try:
                grouped[channel.category_id].append(channel)
            except KeyError:
                grouped[channel.category_id] = [channel]

        def key(t: ByCategoryItem) -> Tuple[Tuple[int, int], List[GuildChannel]]:
            k, v = t
            return ((k.position, k.id) if k else (-1, -1), v)

        _get = self._channels.get
        as_list: List[ByCategoryItem] = [(_get(k), v) for k, v in grouped.items()]  # type: ignore
        as_list.sort(key=key)
        for _, channels in as_list:
            channels.sort(key=lambda c: (c._sorting_bucket, c.position, c.id))
        return as_list

    def _resolve_channel(self, id: Optional[int], /) -> Optional[Union[GuildChannel, Thread]]:
        if id is None:
            return

        return self._channels.get(id) or self._threads.get(id)

    def get_channel_or_thread(self, channel_id: int, /) -> Optional[Union[Thread, GuildChannel]]:
        """Returns a channel or thread with the given ID.

        .. versionadded:: 2.0

        Parameters
        ----------
        channel_id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[Union[:class:`Thread`, :class:`.abc.GuildChannel`]]
            The returned channel or thread or ``None`` if not found.
        """
        return self._channels.get(channel_id) or self._threads.get(channel_id)

    def get_channel(self, channel_id: int, /) -> Optional[GuildChannel]:
        """Returns a channel with the given ID.

        .. note::

            This does *not* search for threads.

        Parameters
        ----------
        channel_id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`.abc.GuildChannel`]
            The returned channel or ``None`` if not found.
        """
        return self._channels.get(channel_id)

    def get_thread(self, thread_id: int, /) -> Optional[Thread]:
        """Returns a thread with the given ID.

        .. versionadded:: 2.0

        Parameters
        ----------
        thread_id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`Thread`]
            The returned thread or ``None`` if not found.
        """
        return self._threads.get(thread_id)

    @property
    def system_channel(self) -> Optional[TextChannel]:
        """Optional[:class:`TextChannel`]: Returns the guild's channel used for system messages.

        If no channel is set, then this returns ``None``.
        """
        channel_id = self._system_channel_id
        return channel_id and self._channels.get(channel_id)  # type: ignore

    @property
    def system_channel_flags(self) -> SystemChannelFlags:
        """:class:`SystemChannelFlags`: Returns the guild's system channel settings."""
        return SystemChannelFlags._from_value(self._system_channel_flags)

    @property
    def rules_channel(self) -> Optional[TextChannel]:
        """Optional[:class:`TextChannel`]: Returns the guild's channel used for the rules.
        The guild must be a Community guild.

        If no channel is set, then this returns ``None``.

        .. versionadded:: 1.3
        """
        channel_id = self._rules_channel_id
        return channel_id and self._channels.get(channel_id)  # type: ignore

    @property
    def public_updates_channel(self) -> Optional[TextChannel]:
        """Optional[:class:`TextChannel`]: Returns the guild's channel where admins and
        moderators of the guild receive notices from Discord. The guild must be a
        Community guild.

        If no channel is set, then this returns ``None``.

        .. versionadded:: 1.4
        """
        channel_id = self._public_updates_channel_id
        return channel_id and self._channels.get(channel_id)  # type: ignore

    @property
    def safety_alerts_channel(self) -> Optional[TextChannel]:
        """Optional[:class:`TextChannel`]: Returns the guild's channel where admins and
        moderators of the guild receive safety alerts from Discord. The guild must be a
        Community guild.

        If no channel is set, then this returns ``None``.

        .. versionadded:: 2.9
        """
        channel_id = self._safety_alerts_channel_id
        return channel_id and self._channels.get(channel_id)  # type: ignore

    @property
    def emoji_limit(self) -> int:
        """:class:`int`: The maximum number of emoji slots this guild has.

        Premium emojis (i.e. those associated with subscription roles) count towards a
        separate limit of 25.
        """
        more_emoji = 200 if "MORE_EMOJI" in self.features else 50
        return max(more_emoji, self._PREMIUM_GUILD_LIMITS[self.premium_tier].emoji)

    @property
    def sticker_limit(self) -> int:
        """:class:`int`: The maximum number of sticker slots this guild has.

        .. versionadded:: 2.0
        """
        more_stickers = 60 if "MORE_STICKERS" in self.features else 0
        return max(more_stickers, self._PREMIUM_GUILD_LIMITS[self.premium_tier].stickers)

    @property
    def bitrate_limit(self) -> float:
        """:class:`float`: The maximum bitrate for voice channels this guild can have.
        For stage channels, the maximum bitrate is 64000.
        """
        vip_guild = self._PREMIUM_GUILD_LIMITS[3].bitrate if "VIP_REGIONS" in self.features else 0
        return max(vip_guild, self._PREMIUM_GUILD_LIMITS[self.premium_tier].bitrate)

    @property
    def filesize_limit(self) -> int:
        """:class:`int`: The maximum number of bytes files can have when uploaded to this guild."""
        return self._PREMIUM_GUILD_LIMITS[self.premium_tier].filesize

    @property
    def members(self) -> List[Member]:
        """List[:class:`Member`]: A list of members that belong to this guild."""
        return list(self._members.values())

    def get_member(self, user_id: int, /) -> Optional[Member]:
        """Returns a member with the given ID.

        Parameters
        ----------
        user_id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`Member`]
            The member or ``None`` if not found.
        """
        return self._members.get(user_id)

    @property
    def premium_subscribers(self) -> List[Member]:
        """List[:class:`Member`]: A list of members who have "boosted" this guild."""
        return [member for member in self.members if member.premium_since is not None]

    @property
    def roles(self) -> List[Role]:
        """List[:class:`Role`]: Returns a :class:`list` of the guild's roles in hierarchy order.

        The first element of this list will be the lowest role in the
        hierarchy.
        """
        return sorted(self._roles.values())

    def get_role(self, role_id: int, /) -> Optional[Role]:
        """Returns a role with the given ID.

        Parameters
        ----------
        role_id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`Role`]
            The role or ``None`` if not found.
        """
        return self._roles.get(role_id)

    @property
    def default_role(self) -> Role:
        """:class:`Role`: Gets the @everyone role that all members have by default."""
        # The @everyone role is *always* given
        return self.get_role(self.id)  # type: ignore

    @property
    def premium_subscriber_role(self) -> Optional[Role]:
        """Optional[:class:`Role`]: Gets the premium subscriber role, AKA "boost" role, in this guild, if any.

        .. versionadded:: 1.6
        """
        for role in self._roles.values():
            if role.is_premium_subscriber():
                return role
        return None

    @property
    def self_role(self) -> Optional[Role]:
        """Optional[:class:`Role`]: Gets the role associated with this client's user, if any.

        .. versionadded:: 1.6
        """
        self_id = self._state.self_id
        for role in self._roles.values():
            tags = role.tags
            if tags and tags.bot_id == self_id:
                return role
        return None

    @property
    def stage_instances(self) -> List[StageInstance]:
        """List[:class:`StageInstance`]: Returns a :class:`list` of the guild's stage instances that
        are currently running.

        .. versionadded:: 2.0
        """
        return list(self._stage_instances.values())

    def get_stage_instance(self, stage_instance_id: int, /) -> Optional[StageInstance]:
        """Returns a stage instance with the given ID.

        .. versionadded:: 2.0

        Parameters
        ----------
        stage_instance_id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`StageInstance`]
            The stage instance or ``None`` if not found.
        """
        return self._stage_instances.get(stage_instance_id)

    @property
    def scheduled_events(self) -> List[GuildScheduledEvent]:
        """List[:class:`GuildScheduledEvent`]: Returns a :class:`list` of existing guild scheduled events.

        .. versionadded:: 2.3
        """
        return list(self._scheduled_events.values())

    def get_scheduled_event(self, event_id: int, /) -> Optional[GuildScheduledEvent]:
        """Returns a guild scheduled event with the given ID.

        .. versionadded:: 2.3

        Parameters
        ----------
        event_id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`GuildScheduledEvent`]
            The guild scheduled event or ``None`` if not found.
        """
        return self._scheduled_events.get(event_id)

    @property
    def owner(self) -> Optional[Member]:
        """Optional[:class:`Member`]: Returns the member that owns the guild."""
        return self.get_member(self.owner_id)  # type: ignore

    @property
    def icon(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's icon asset, if available."""
        if self._icon is None:
            return None
        return Asset._from_guild_icon(self._state, self.id, self._icon)

    @property
    def banner(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's banner asset, if available."""
        if self._banner is None:
            return None
        return Asset._from_banner(self._state, self.id, self._banner)

    @property
    def splash(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's invite splash asset, if available."""
        if self._splash is None:
            return None
        return Asset._from_guild_image(self._state, self.id, self._splash, path="splashes")

    @property
    def discovery_splash(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's discovery splash asset, if available."""
        if self._discovery_splash is None:
            return None
        return Asset._from_guild_image(
            self._state, self.id, self._discovery_splash, path="discovery-splashes"
        )

    @property
    def member_count(self) -> int:
        """:class:`int`: Returns the true member count regardless of it being loaded fully or not.

        .. warning::

            Due to a Discord limitation, in order for this attribute to remain up-to-date and
            accurate, it requires :attr:`Intents.members` to be specified.
        """
        try:
            return self._member_count
        except AttributeError:
            return len(self._members)

    @property
    def region(self) -> str:
        """Optional[:class:`str`]: The region the guild belongs on.

        .. deprecated:: 2.5

            VoiceRegion is no longer set on the guild, and is set on the individual voice channels instead.
            See :attr:`VoiceChannel.rtc_region` and :attr:`StageChannel.rtc_region` instead.

        .. versionchanged:: 2.5
            No longer a ``VoiceRegion`` instance.
        """
        utils.warn_deprecated(
            "Guild.region is deprecated and will be removed in a future version.", stacklevel=2
        )
        return self._region

    @property
    def chunked(self) -> bool:
        """:class:`bool`: Whether the guild is "chunked".

        A chunked guild means that :attr:`member_count` is equal to the
        number of members stored in the internal :attr:`members` cache.

        If this value returns ``False``, then you should request for
        offline members.
        """
        count = getattr(self, "_member_count", None)
        if count is None:
            return False
        return count == len(self._members)

    @property
    def shard_id(self) -> int:
        """:class:`int`: Returns the shard ID for this guild if applicable."""
        count = self._state.shard_count
        if count is None:
            return 0
        return (self.id >> 22) % count

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the guild's creation time in UTC."""
        return utils.snowflake_time(self.id)

    def get_member_named(self, name: str, /) -> Optional[Member]:
        """Returns the first member found that matches the name provided.

        The lookup strategy is as follows (in order):

        1. Lookup by nickname.
        2. Lookup by global name.
        3. Lookup by username.

        The name can have an optional discriminator argument, e.g. "Jake#0001",
        in which case it will be treated as a username + discriminator combo
        (note: this only works with usernames, not nicknames).

        If no member is found, ``None`` is returned.

        .. versionchanged:: 2.9
            Now takes :attr:`User.global_name` into account.

        Parameters
        ----------
        name: :class:`str`
            The name of the member to lookup (with an optional discriminator).

        Returns
        -------
        Optional[:class:`Member`]
            The member in this guild with the associated name. If not found
            then ``None`` is returned.
        """
        username, _, discriminator = name.rpartition("#")
        if username and (
            discriminator == "0" or (len(discriminator) == 4 and discriminator.isdecimal())
        ):
            # legacy behavior
            result = utils.get(self._members.values(), name=username, discriminator=discriminator)
            if result is not None:
                return result

        def pred(m: Member) -> bool:
            return m.nick == name or m.global_name == name or m.name == name

        return utils.find(pred, self._members.values())

    def _create_channel(
        self,
        name: str,
        channel_type: ChannelType,
        overwrites: Dict[Union[Role, Member], PermissionOverwrite] = MISSING,
        category: Optional[Snowflake] = None,
        **options: Any,
    ) -> Any:
        if overwrites is MISSING:
            overwrites = {}
        elif not isinstance(overwrites, dict):
            raise TypeError("overwrites parameter expects a dict.")

        perms = []
        for target, perm in overwrites.items():
            if not isinstance(perm, PermissionOverwrite):
                raise TypeError(f"Expected PermissionOverwrite received {perm.__class__.__name__}")

            allow, deny = perm.pair()
            payload = {"allow": allow.value, "deny": deny.value, "id": target.id}

            if isinstance(target, Role):
                payload["type"] = abc._Overwrites.ROLE
            else:
                payload["type"] = abc._Overwrites.MEMBER

            perms.append(payload)

        parent_id = category.id if category else None
        return self._state.http.create_channel(
            self.id,
            channel_type.value,
            name=name,
            parent_id=parent_id,
            permission_overwrites=perms,
            **options,
        )

    async def create_text_channel(
        self,
        name: str,
        *,
        reason: Optional[str] = None,
        category: Optional[Snowflake] = None,
        position: int = MISSING,
        topic: Optional[str] = MISSING,
        slowmode_delay: int = MISSING,
        default_thread_slowmode_delay: int = MISSING,
        default_auto_archive_duration: AnyThreadArchiveDuration = MISSING,
        nsfw: bool = MISSING,
        news: bool = MISSING,
        overwrites: Dict[Union[Role, Member], PermissionOverwrite] = MISSING,
    ) -> TextChannel:
        """|coro|

        Creates a :class:`TextChannel` for the guild.

        You need :attr:`~Permissions.manage_channels` permission
        to create the channel.

        The ``overwrites`` parameter can be used to create a 'secret'
        channel upon creation. This parameter expects a :class:`dict` of
        overwrites with the target (either a :class:`Member` or a :class:`Role`)
        as the key and a :class:`PermissionOverwrite` as the value.

        .. note::

            Creating a channel of a specified position will not update the position of
            other channels to follow suit. A follow-up call to :meth:`~TextChannel.edit`
            will be required to update the position of the channel in the channel list.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Examples
        --------
        Creating a basic channel:

        .. code-block:: python3

            channel = await guild.create_text_channel('cool-channel')

        Creating a "secret" channel:

        .. code-block:: python3

            overwrites = {
                guild.default_role: disnake.PermissionOverwrite(view_channel=False),
                guild.me: disnake.PermissionOverwrite(view_channel=True)
            }

            channel = await guild.create_text_channel('secret', overwrites=overwrites)

        Parameters
        ----------
        name: :class:`str`
            The channel's name.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`], :class:`PermissionOverwrite`]
            A :class:`dict` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply upon creation of a channel.
            Useful for creating secret channels.
        category: Optional[:class:`abc.Snowflake`]
            The category to place the newly created channel under.
            The permissions will be automatically synced to category if no
            overwrites are provided.
        position: :class:`int`
            The position in the channel list. This is a number that starts
            at 0. e.g. the top channel is position 0.
        topic: Optional[:class:`str`]
            The channel's topic.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for users in this channel, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
            If not provided, slowmode is disabled.
        default_thread_slowmode_delay: :class:`int`
            Specifies the slowmode rate limit at which users can send messages
            in newly created threads in this channel, in seconds.
            A value of ``0`` disables slowmode by default. The maximum value possible is ``21600``.
            If not provided, slowmode is disabled.

            .. versionadded:: 2.8

        default_auto_archive_duration: Union[:class:`int`, :class:`ThreadArchiveDuration`]
            The default auto archive duration in minutes for threads created in this channel.
            Must be one of ``60``, ``1440``, ``4320``, or ``10080``.

            .. versionadded:: 2.5

        nsfw: :class:`bool`
            Whether to mark the channel as NSFW.
        news: :class:`bool`
            Whether to make a news channel. News channels are text channels that can be followed.
            This is only available to guilds that contain ``NEWS`` in :attr:`Guild.features`.

            .. versionadded:: 2.5

        reason: Optional[:class:`str`]
            The reason for creating this channel. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`TextChannel`
            The channel that was just created.
        """
        options = {}
        if position is not MISSING:
            options["position"] = position

        if topic is not MISSING:
            options["topic"] = topic

        if slowmode_delay is not MISSING:
            options["rate_limit_per_user"] = slowmode_delay

        if default_thread_slowmode_delay is not MISSING:
            options["default_thread_rate_limit_per_user"] = default_thread_slowmode_delay

        if nsfw is not MISSING:
            options["nsfw"] = nsfw

        if default_auto_archive_duration is not MISSING:
            options["default_auto_archive_duration"] = cast(
                "ThreadArchiveDurationLiteral", try_enum_to_int(default_auto_archive_duration)
            )

        if news:
            channel_type = ChannelType.news
        else:
            channel_type = ChannelType.text

        data = await self._create_channel(
            name,
            overwrites=overwrites,
            channel_type=channel_type,
            category=category,
            reason=reason,
            **options,
        )
        channel = TextChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_voice_channel(
        self,
        name: str,
        *,
        category: Optional[Snowflake] = None,
        position: int = MISSING,
        bitrate: int = MISSING,
        user_limit: int = MISSING,
        rtc_region: Optional[Union[str, VoiceRegion]] = MISSING,
        video_quality_mode: VideoQualityMode = MISSING,
        nsfw: bool = MISSING,
        slowmode_delay: int = MISSING,
        overwrites: Dict[Union[Role, Member], PermissionOverwrite] = MISSING,
        reason: Optional[str] = None,
    ) -> VoiceChannel:
        """|coro|

        This is similar to :meth:`create_text_channel` except makes a :class:`VoiceChannel` instead.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The channel's name.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`], :class:`PermissionOverwrite`]
            A :class:`dict` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply upon creation of a channel.
            Useful for creating secret channels.
        category: Optional[:class:`abc.Snowflake`]
            The category to place the newly created channel under.
            The permissions will be automatically synced to category if no
            overwrites are provided.
        position: :class:`int`
            The position in the channel list. This is a number that starts
            at 0. e.g. the top channel is position 0.
        bitrate: :class:`int`
            The channel's preferred audio bitrate in bits per second.
        user_limit: :class:`int`
            The channel's limit for number of members that can be in a voice channel.
        rtc_region: Optional[Union[:class:`str`, :class:`VoiceRegion`]]
            The region for the voice channel's voice communication.
            A value of ``None`` indicates automatic voice region detection.

            .. versionadded:: 1.7

        video_quality_mode: :class:`VideoQualityMode`
            The camera video quality for the voice channel's participants.

            .. versionadded:: 2.0

        nsfw: :class:`bool`
            Whether to mark the channel as NSFW.

            .. versionadded:: 2.5

        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for users in this channel, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
            If not provided, slowmode is disabled.

            .. versionadded:: 2.6

        reason: Optional[:class:`str`]
            The reason for creating this channel. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`VoiceChannel`
            The channel that was just created.
        """
        options = {}
        if position is not MISSING:
            options["position"] = position

        if bitrate is not MISSING:
            options["bitrate"] = bitrate

        if user_limit is not MISSING:
            options["user_limit"] = user_limit

        if rtc_region is not MISSING:
            options["rtc_region"] = None if rtc_region is None else str(rtc_region)

        if video_quality_mode is not MISSING:
            options["video_quality_mode"] = video_quality_mode.value

        if nsfw is not MISSING:
            options["nsfw"] = nsfw

        if slowmode_delay is not MISSING:
            options["rate_limit_per_user"] = slowmode_delay

        data = await self._create_channel(
            name,
            overwrites=overwrites,
            channel_type=ChannelType.voice,
            category=category,
            reason=reason,
            **options,
        )
        channel = VoiceChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_stage_channel(
        self,
        name: str,
        *,
        topic: Optional[str] = MISSING,
        position: int = MISSING,
        bitrate: int = MISSING,
        user_limit: int = MISSING,
        rtc_region: Optional[Union[str, VoiceRegion]] = MISSING,
        video_quality_mode: VideoQualityMode = MISSING,
        overwrites: Dict[Union[Role, Member], PermissionOverwrite] = MISSING,
        category: Optional[Snowflake] = None,
        nsfw: bool = MISSING,
        slowmode_delay: int = MISSING,
        reason: Optional[str] = None,
    ) -> StageChannel:
        """|coro|

        This is similar to :meth:`create_text_channel` except makes a :class:`StageChannel` instead.

        .. versionadded:: 1.7

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The channel's name.
        topic: Optional[:class:`str`]
            The channel's topic.

            .. versionchanged:: 2.5
                This is no longer required to be provided.

        overwrites: Dict[Union[:class:`Role`, :class:`Member`], :class:`PermissionOverwrite`]
            A :class:`dict` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply upon creation of a channel.
            Useful for creating secret channels.
        category: Optional[:class:`abc.Snowflake`]
            The category to place the newly created channel under.
            The permissions will be automatically synced to category if no
            overwrites are provided.
        position: :class:`int`
            The position in the channel list. This is a number that starts
            at 0. e.g. the top channel is position 0.
        bitrate: :class:`int`
            The channel's preferred audio bitrate in bits per second.

            .. versionadded:: 2.6

        rtc_region: Optional[Union[:class:`str`, :class:`VoiceRegion`]]
            The region for the stage channel's voice communication.
            A value of ``None`` indicates automatic voice region detection.

            .. versionadded:: 2.5

        nsfw: :class:`bool`
            Whether to mark the channel as NSFW.

            .. versionadded:: 2.9

        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for users in this channel, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
            If not provided, slowmode is disabled.

            .. versionadded:: 2.9


        reason: Optional[:class:`str`]
            The reason for creating this channel. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`StageChannel`
            The channel that was just created.
        """
        options: Dict[str, Any] = {}

        if topic is not MISSING:
            options["topic"] = topic

        if bitrate is not MISSING:
            options["bitrate"] = bitrate

        if user_limit is not MISSING:
            options["user_limit"] = user_limit

        if position is not MISSING:
            options["position"] = position

        if rtc_region is not MISSING:
            options["rtc_region"] = None if rtc_region is None else str(rtc_region)

        if video_quality_mode is not MISSING:
            options["video_quality_mode"] = video_quality_mode.value

        if nsfw is not MISSING:
            options["nsfw"] = nsfw

        if slowmode_delay is not MISSING:
            options["rate_limit_per_user"] = slowmode_delay

        data = await self._create_channel(
            name,
            overwrites=overwrites,
            channel_type=ChannelType.stage_voice,
            category=category,
            reason=reason,
            **options,
        )
        channel = StageChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_forum_channel(
        self,
        name: str,
        *,
        topic: Optional[str] = None,
        category: Optional[Snowflake] = None,
        position: int = MISSING,
        slowmode_delay: int = MISSING,
        default_thread_slowmode_delay: int = MISSING,
        default_auto_archive_duration: Optional[AnyThreadArchiveDuration] = None,
        nsfw: bool = MISSING,
        overwrites: Dict[Union[Role, Member], PermissionOverwrite] = MISSING,
        available_tags: Optional[Sequence[ForumTag]] = None,
        default_reaction: Optional[Union[str, Emoji, PartialEmoji]] = None,
        default_sort_order: Optional[ThreadSortOrder] = None,
        default_layout: Optional[ThreadLayout] = None,
        reason: Optional[str] = None,
    ) -> ForumChannel:
        """|coro|

        This is similar to :meth:`create_text_channel` except makes a :class:`ForumChannel` instead.

        .. versionadded:: 2.5

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The channel's name.
        topic: Optional[:class:`str`]
            The channel's topic.
        category: Optional[:class:`abc.Snowflake`]
            The category to place the newly created channel under.
            The permissions will be automatically synced to category if no
            overwrites are provided.
        position: :class:`int`
            The position in the channel list. This is a number that starts
            at 0. e.g. the top channel is position 0.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit at which users can create
            threads in this channel, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
            If not provided, slowmode is disabled.
        default_thread_slowmode_delay: :class:`int`
            Specifies the slowmode rate limit at which users can send messages
            in newly created threads in this channel, in seconds.
            A value of ``0`` disables slowmode by default. The maximum value possible is ``21600``.
            If not provided, slowmode is disabled.

            .. versionadded:: 2.6

        default_auto_archive_duration: Union[:class:`int`, :class:`ThreadArchiveDuration`]
            The default auto archive duration in minutes for threads created in this channel.
            Must be one of ``60``, ``1440``, ``4320``, or ``10080``.
        nsfw: :class:`bool`
            Whether to mark the channel as NSFW.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`], :class:`PermissionOverwrite`]
            A :class:`dict` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply upon creation of a channel.
            Useful for creating secret channels.
        available_tags: Optional[Sequence[:class:`ForumTag`]]
            The tags available for threads in this channel.

            .. versionadded:: 2.6

        default_reaction: Optional[Union[:class:`str`, :class:`Emoji`, :class:`PartialEmoji`]]
            The default emoji shown for reacting to threads.

            .. versionadded:: 2.6

        default_sort_order: Optional[:class:`ThreadSortOrder`]
            The default sort order of threads in this channel.

            .. versionadded:: 2.6

        default_layout: :class:`ThreadLayout`
            The default layout of threads in this channel.

            .. versionadded:: 2.10

        reason: Optional[:class:`str`]
            The reason for creating this channel. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`ForumChannel`
            The channel that was just created.
        """
        options = {}
        if position is not MISSING:
            options["position"] = position

        if topic is not MISSING:
            options["topic"] = topic

        if slowmode_delay is not MISSING:
            options["rate_limit_per_user"] = slowmode_delay

        if default_thread_slowmode_delay is not MISSING:
            options["default_thread_rate_limit_per_user"] = default_thread_slowmode_delay

        if nsfw is not MISSING:
            options["nsfw"] = nsfw

        if default_auto_archive_duration is not None:
            options["default_auto_archive_duration"] = cast(
                "ThreadArchiveDurationLiteral", try_enum_to_int(default_auto_archive_duration)
            )

        if available_tags is not None:
            options["available_tags"] = [tag.to_dict() for tag in available_tags]

        if default_reaction is not None:
            emoji_name, emoji_id = PartialEmoji._emoji_to_name_id(default_reaction)
            options["default_reaction_emoji"] = {
                "emoji_name": emoji_name,
                "emoji_id": emoji_id,
            }

        if default_sort_order is not None:
            options["default_sort_order"] = try_enum_to_int(default_sort_order)

        if default_layout is not None:
            options["default_forum_layout"] = try_enum_to_int(default_layout)

        data = await self._create_channel(
            name,
            overwrites=overwrites,
            channel_type=ChannelType.forum,
            category=category,
            reason=reason,
            **options,
        )
        channel = ForumChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_media_channel(
        self,
        name: str,
        *,
        topic: Optional[str] = None,
        category: Optional[Snowflake] = None,
        position: int = MISSING,
        slowmode_delay: int = MISSING,
        default_thread_slowmode_delay: int = MISSING,
        default_auto_archive_duration: Optional[AnyThreadArchiveDuration] = None,
        nsfw: bool = MISSING,
        overwrites: Dict[Union[Role, Member], PermissionOverwrite] = MISSING,
        available_tags: Optional[Sequence[ForumTag]] = None,
        default_reaction: Optional[Union[str, Emoji, PartialEmoji]] = None,
        default_sort_order: Optional[ThreadSortOrder] = None,
        reason: Optional[str] = None,
    ) -> MediaChannel:
        """|coro|

        This is similar to :meth:`create_text_channel` except makes a :class:`MediaChannel` instead.

        .. versionadded:: 2.10

        Parameters
        ----------
        name: :class:`str`
            The channel's name.
        topic: Optional[:class:`str`]
            The channel's topic.
        category: Optional[:class:`abc.Snowflake`]
            The category to place the newly created channel under.
            The permissions will be automatically synced to category if no
            overwrites are provided.
        position: :class:`int`
            The position in the channel list. This is a number that starts
            at 0. e.g. the top channel is position 0.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit at which users can create
            threads in this channel, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
            If not provided, slowmode is disabled.
        default_thread_slowmode_delay: :class:`int`
            Specifies the slowmode rate limit at which users can send messages
            in newly created threads in this channel, in seconds.
            A value of ``0`` disables slowmode by default. The maximum value possible is ``21600``.
            If not provided, slowmode is disabled.
        default_auto_archive_duration: Union[:class:`int`, :class:`ThreadArchiveDuration`]
            The default auto archive duration in minutes for threads created in this channel.
            Must be one of ``60``, ``1440``, ``4320``, or ``10080``.
        nsfw: :class:`bool`
            Whether to mark the channel as NSFW.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`], :class:`PermissionOverwrite`]
            A :class:`dict` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply upon creation of a channel.
            Useful for creating secret channels.
        available_tags: Optional[Sequence[:class:`ForumTag`]]
            The tags available for threads in this channel.
        default_reaction: Optional[Union[:class:`str`, :class:`Emoji`, :class:`PartialEmoji`]]
            The default emoji shown for reacting to threads.
        default_sort_order: Optional[:class:`ThreadSortOrder`]
            The default sort order of threads in this channel.
        reason: Optional[:class:`str`]
            The reason for creating this channel. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`MediaChannel`
            The channel that was just created.
        """
        options = {}
        if position is not MISSING:
            options["position"] = position

        if topic is not MISSING:
            options["topic"] = topic

        if slowmode_delay is not MISSING:
            options["rate_limit_per_user"] = slowmode_delay

        if default_thread_slowmode_delay is not MISSING:
            options["default_thread_rate_limit_per_user"] = default_thread_slowmode_delay

        if nsfw is not MISSING:
            options["nsfw"] = nsfw

        if default_auto_archive_duration is not None:
            options["default_auto_archive_duration"] = cast(
                "ThreadArchiveDurationLiteral", try_enum_to_int(default_auto_archive_duration)
            )

        if available_tags is not None:
            options["available_tags"] = [tag.to_dict() for tag in available_tags]

        if default_reaction is not None:
            emoji_name, emoji_id = PartialEmoji._emoji_to_name_id(default_reaction)
            options["default_reaction_emoji"] = {
                "emoji_name": emoji_name,
                "emoji_id": emoji_id,
            }

        if default_sort_order is not None:
            options["default_sort_order"] = try_enum_to_int(default_sort_order)

        data = await self._create_channel(
            name,
            overwrites=overwrites,
            channel_type=ChannelType.media,
            category=category,
            reason=reason,
            **options,
        )
        channel = MediaChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_category(
        self,
        name: str,
        *,
        overwrites: Dict[Union[Role, Member], PermissionOverwrite] = MISSING,
        reason: Optional[str] = None,
        position: int = MISSING,
    ) -> CategoryChannel:
        """|coro|

        Same as :meth:`create_text_channel` except makes a :class:`CategoryChannel` instead.

        .. note::

            The ``category`` parameter is not supported in this function since categories
            cannot have categories.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The category's name.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`], :class:`PermissionOverwrite`]
            A :class:`dict` of target (either a role or a member) to
            :class:`PermissionOverwrite` which can be synced to channels.
        position: :class:`int`
            The position in the channel list. This is a number that starts
            at 0. e.g. the top channel is position 0.
        reason: Optional[:class:`str`]
            The reason for creating this category. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`CategoryChannel`
            The channel that was just created.
        """
        options: Dict[str, Any] = {}
        if position is not MISSING:
            options["position"] = position

        data = await self._create_channel(
            name, overwrites=overwrites, channel_type=ChannelType.category, reason=reason, **options
        )
        channel = CategoryChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    create_category_channel = create_category

    async def leave(self) -> None:
        """|coro|

        Leaves the guild.

        .. note::

            You cannot leave the guild that you own, you must delete it instead
            via :meth:`delete`.

        Raises
        ------
        HTTPException
            Leaving the guild failed.
        """
        await self._state.http.leave_guild(self.id)

    async def delete(self) -> None:
        """|coro|

        Deletes the guild. You must be the guild owner to delete the
        guild.

        Raises
        ------
        HTTPException
            Deleting the guild failed.
        Forbidden
            You do not have permissions to delete the guild.
        """
        await self._state.http.delete_guild(self.id)

    async def edit(
        self,
        *,
        reason: Optional[str] = MISSING,
        name: str = MISSING,
        description: Optional[str] = MISSING,
        icon: Optional[AssetBytes] = MISSING,
        banner: Optional[AssetBytes] = MISSING,
        splash: Optional[AssetBytes] = MISSING,
        discovery_splash: Optional[AssetBytes] = MISSING,
        community: bool = MISSING,
        invites_disabled: bool = MISSING,
        raid_alerts_disabled: bool = MISSING,
        afk_channel: Optional[VoiceChannel] = MISSING,
        owner: Snowflake = MISSING,
        afk_timeout: int = MISSING,
        default_notifications: NotificationLevel = MISSING,
        verification_level: VerificationLevel = MISSING,
        explicit_content_filter: ContentFilter = MISSING,
        vanity_code: str = MISSING,
        system_channel: Optional[TextChannel] = MISSING,
        system_channel_flags: SystemChannelFlags = MISSING,
        preferred_locale: Locale = MISSING,
        rules_channel: Optional[TextChannel] = MISSING,
        public_updates_channel: Optional[TextChannel] = MISSING,
        safety_alerts_channel: Optional[TextChannel] = MISSING,
        premium_progress_bar_enabled: bool = MISSING,
    ) -> Guild:
        """|coro|

        Edits the guild.

        You must have :attr:`~Permissions.manage_guild` permission
        to use this.

        .. versionchanged:: 1.4
            The `rules_channel` and `public_updates_channel` keyword-only parameters were added.

        .. versionchanged:: 2.0
            The `discovery_splash` and `community` keyword-only parameters were added.

        .. versionchanged:: 2.0
            The newly updated guild is returned.

        .. versionchanged:: 2.5
            Removed the ``region`` parameter.
            Use :func:`VoiceChannel.edit` or :func:`StageChannel.edit` with ``rtc_region`` instead.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` or :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The new name of the guild.
        description: Optional[:class:`str`]
            The new description of the guild. Could be ``None`` for no description.
            This is only available to guilds that contain ``COMMUNITY`` in :attr:`Guild.features`.
        icon: Optional[|resource_type|]
            The new guild icon. Only PNG/JPG is supported.
            GIF is only available to guilds that contain ``ANIMATED_ICON`` in :attr:`Guild.features`.
            Could be ``None`` to denote removal of the icon.

            .. versionchanged:: 2.5
                Now accepts various resource types in addition to :class:`bytes`.

        banner: Optional[|resource_type|]
            The new guild banner.
            GIF is only available to guilds that contain ``ANIMATED_BANNER`` in :attr:`Guild.features`.
            Could be ``None`` to denote removal of the banner. This is only available to guilds that contain
            ``BANNER`` in :attr:`Guild.features`.

            .. versionchanged:: 2.5
                Now accepts various resource types in addition to :class:`bytes`.

        splash: Optional[|resource_type|]
            The new guild invite splash.
            Only PNG/JPG is supported. Could be ``None`` to denote removing the
            splash. This is only available to guilds that contain ``INVITE_SPLASH``
            in :attr:`Guild.features`.

            .. versionchanged:: 2.5
                Now accepts various resource types in addition to :class:`bytes`.

        discovery_splash: Optional[|resource_type|]
            The new guild discovery splash.
            Only PNG/JPG is supported. Could be ``None`` to denote removing the
            splash. This is only available to guilds that contain ``DISCOVERABLE``
            in :attr:`Guild.features`.

            .. versionchanged:: 2.5
                Now accepts various resource types in addition to :class:`bytes`.

        community: :class:`bool`
            Whether the guild should be a Community guild. If set to ``True``\\, both ``rules_channel``
            and ``public_updates_channel`` parameters are required.
        invites_disabled: :class:`bool`
            Whether the guild has paused invites, preventing new users from joining.

            This is only available to guilds that contain ``COMMUNITY``
            in :attr:`Guild.features`.

            This cannot be changed at the same time as the ``community`` feature due a Discord API limitation.

            .. versionadded:: 2.6

        raid_alerts_disabled: :class:`bool`
            Whether the guild has disabled join raid alerts.

            This is only available to guilds that contain ``COMMUNITY``
            in :attr:`Guild.features`.

            This cannot be changed at the same time as the ``community`` feature due a Discord API limitation.

            .. versionadded:: 2.9

        afk_channel: Optional[:class:`VoiceChannel`]
            The new channel that is the AFK channel. Could be ``None`` for no AFK channel.
        afk_timeout: :class:`int`
            The number of seconds until someone is moved to the AFK channel.
            This can be set to ``60``, ``300``, ``900``, ``1800``, and ``3600``.
        owner: :class:`Member`
            The new owner of the guild to transfer ownership to. Note that you must
            be owner of the guild to do this.
        verification_level: :class:`VerificationLevel`
            The new verification level for the guild.
        default_notifications: :class:`NotificationLevel`
            The new default notification level for the guild.
        explicit_content_filter: :class:`ContentFilter`
            The new explicit content filter for the guild.
        vanity_code: :class:`str`
            The new vanity code for the guild.
        system_channel: Optional[:class:`TextChannel`]
            The new channel that is used for the system channel. Could be ``None`` for no system channel.
        system_channel_flags: :class:`SystemChannelFlags`
            The new system channel settings to use with the new system channel.
        preferred_locale: :class:`Locale`
            The new preferred locale for the guild. Used as the primary language in the guild.

            .. versionchanged:: 2.5
                Changed to :class:`Locale` instead of :class:`str`.

        rules_channel: Optional[:class:`TextChannel`]
            The new channel that is used for rules. This is only available to
            guilds that contain ``COMMUNITY`` in :attr:`Guild.features`. Could be ``None`` for no rules
            channel.
        public_updates_channel: Optional[:class:`TextChannel`]
            The new channel that is used for public updates from Discord. This is only available to
            guilds that contain ``COMMUNITY`` in :attr:`Guild.features`. Could be ``None`` for no
            public updates channel.
        safety_alerts_channel: Optional[:class:`TextChannel`]
            The new channel that is used for safety alerts. This is only available to
            guilds that contain ``COMMUNITY`` in :attr:`Guild.features`. Could be ``None`` for no
            safety alerts channel.

            .. versionadded:: 2.9

        premium_progress_bar_enabled: :class:`bool`
            Whether the server boost progress bar is enabled.
        reason: Optional[:class:`str`]
            The reason for editing this guild. Shows up on the audit log.

        Raises
        ------
        NotFound
            At least one of the assets (``icon``, ``banner``, ``splash`` or ``discovery_splash``) couldn't be found.
        Forbidden
            You do not have permissions to edit the guild.
        HTTPException
            Editing the guild failed.
        TypeError
            At least one of the assets (``icon``, ``banner``, ``splash`` or ``discovery_splash``)
            is a lottie sticker (see :func:`Sticker.read`),
            or one of the parameters ``default_notifications``, ``verification_level``,
            ``explicit_content_filter``, or ``system_channel_flags`` was of the incorrect type.
        ValueError
            ``community`` was set without setting both ``rules_channel`` and ``public_updates_channel`` parameters,
            or if you are not the owner of the guild and request an ownership transfer,
            or the image format passed in to ``icon`` is invalid,
            or both ``community`` and ``invites_disabled` or ``raid_alerts_disabled`` were provided.

        Returns
        -------
        :class:`Guild`
            The newly updated guild. Note that this has the same limitations as
            mentioned in :meth:`Client.fetch_guild` and may not have full data.
        """
        http = self._state.http

        if vanity_code is not MISSING:
            await http.change_vanity_code(self.id, vanity_code, reason=reason)

        fields: Dict[str, Any] = {}
        if name is not MISSING:
            fields["name"] = name

        if description is not MISSING:
            fields["description"] = description

        if preferred_locale is not MISSING:
            fields["preferred_locale"] = str(preferred_locale)

        if afk_timeout is not MISSING:
            fields["afk_timeout"] = afk_timeout

        if icon is not MISSING:
            fields["icon"] = await utils._assetbytes_to_base64_data(icon)

        if banner is not MISSING:
            fields["banner"] = await utils._assetbytes_to_base64_data(banner)

        if splash is not MISSING:
            fields["splash"] = await utils._assetbytes_to_base64_data(splash)

        if discovery_splash is not MISSING:
            fields["discovery_splash"] = await utils._assetbytes_to_base64_data(discovery_splash)

        if default_notifications is not MISSING:
            if not isinstance(default_notifications, NotificationLevel):
                raise TypeError("default_notifications field must be of type NotificationLevel")
            fields["default_message_notifications"] = default_notifications.value

        if afk_channel is not MISSING:
            if afk_channel is None:
                fields["afk_channel_id"] = afk_channel
            else:
                fields["afk_channel_id"] = afk_channel.id

        if system_channel is not MISSING:
            if system_channel is None:
                fields["system_channel_id"] = system_channel
            else:
                fields["system_channel_id"] = system_channel.id

        if rules_channel is not MISSING:
            if rules_channel is None:
                fields["rules_channel_id"] = rules_channel
            else:
                fields["rules_channel_id"] = rules_channel.id

        if public_updates_channel is not MISSING:
            if public_updates_channel is None:
                fields["public_updates_channel_id"] = public_updates_channel
            else:
                fields["public_updates_channel_id"] = public_updates_channel.id

        if safety_alerts_channel is not MISSING:
            if safety_alerts_channel is None:
                fields["safety_alerts_channel_id"] = safety_alerts_channel
            else:
                fields["safety_alerts_channel_id"] = safety_alerts_channel.id

        if owner is not MISSING:
            if self.owner_id != self._state.self_id:
                raise ValueError("To transfer ownership you must be the owner of the guild.")

            fields["owner_id"] = owner.id

        if verification_level is not MISSING:
            if not isinstance(verification_level, VerificationLevel):
                raise TypeError("verification_level field must be of type VerificationLevel")

            fields["verification_level"] = verification_level.value

        if explicit_content_filter is not MISSING:
            if not isinstance(explicit_content_filter, ContentFilter):
                raise TypeError("explicit_content_filter field must be of type ContentFilter")

            fields["explicit_content_filter"] = explicit_content_filter.value

        if system_channel_flags is not MISSING:
            if not isinstance(system_channel_flags, SystemChannelFlags):
                raise TypeError("system_channel_flags field must be of type SystemChannelFlags")

            fields["system_channel_flags"] = system_channel_flags.value

        if (
            community is not MISSING
            or invites_disabled is not MISSING
            or raid_alerts_disabled is not MISSING
        ):
            # If we don't have complete feature information for the guild,
            # it is possible to disable or enable other features that we didn't intend to touch.
            # To enable or disable a feature, we will need to provide all of the existing features in advance.
            if self.unavailable:
                raise RuntimeError(
                    "cannot modify features of an unavailable guild due to potentially destructive results."
                )
            features = set(self.features)
            if community is not MISSING:
                if not isinstance(community, bool):
                    raise TypeError("community must be a bool")
                if community:
                    if "rules_channel_id" in fields and "public_updates_channel_id" in fields:
                        features.add("COMMUNITY")
                    else:
                        raise ValueError(
                            "community field requires both rules_channel and public_updates_channel fields to be provided"
                        )
                else:
                    features.discard("COMMUNITY")

            if invites_disabled is not MISSING:
                if community is not MISSING:
                    raise ValueError(
                        "cannot modify both the COMMUNITY feature and INVITES_DISABLED feature at the "
                        "same time due to a discord limitation."
                    )
                if not isinstance(invites_disabled, bool):
                    raise TypeError("invites_disabled must be a bool")
                if invites_disabled:
                    features.add("INVITES_DISABLED")
                else:
                    features.discard("INVITES_DISABLED")

            if raid_alerts_disabled is not MISSING:
                if community is not MISSING:
                    raise ValueError(
                        "cannot modify both the COMMUNITY feature and RAID_ALERTS_DISABLED feature at the "
                        "same time due to a discord limitation."
                    )
                if not isinstance(raid_alerts_disabled, bool):
                    raise TypeError("raid_alerts_disabled must be a bool")
                if raid_alerts_disabled:
                    features.add("RAID_ALERTS_DISABLED")
                else:
                    features.discard("RAID_ALERTS_DISABLED")

            fields["features"] = list(features)

        if premium_progress_bar_enabled is not MISSING:
            fields["premium_progress_bar_enabled"] = premium_progress_bar_enabled

        data = await http.edit_guild(self.id, reason=reason, **fields)
        return Guild(data=data, state=self._state)

    async def fetch_channels(self) -> Sequence[GuildChannel]:
        """|coro|

        Retrieves all :class:`abc.GuildChannel` that the guild has.

        .. note::

            This method is an API call. For general usage, consider :attr:`channels` instead.

        .. versionadded:: 1.2

        Raises
        ------
        InvalidData
            An unknown channel type was received from Discord.
        HTTPException
            Retrieving the channels failed.

        Returns
        -------
        Sequence[:class:`abc.GuildChannel`]
            All channels that the guild has.
        """
        data = await self._state.http.get_all_guild_channels(self.id)

        def convert(d):
            factory, _ = _guild_channel_factory(d["type"])
            if factory is None:
                raise InvalidData("Unknown channel type {type} for channel ID {id}.".format_map(d))

            channel = factory(guild=self, state=self._state, data=d)
            return channel

        return [convert(d) for d in data]

    async def active_threads(self) -> List[Thread]:
        """|coro|

        Returns a list of active :class:`Thread` that the client can access.

        This includes both private and public threads.

        .. versionadded:: 2.0

        Raises
        ------
        HTTPException
            The request to get the active threads failed.

        Returns
        -------
        List[:class:`Thread`]
            The active threads.
        """
        data = await self._state.http.get_active_threads(self.id)
        threads = [Thread(guild=self, state=self._state, data=d) for d in data.get("threads", [])]
        thread_lookup: Dict[int, Thread] = {thread.id: thread for thread in threads}
        for member in data.get("members", []):
            thread = thread_lookup.get(int(member["id"]))
            if thread is not None:
                thread._add_member(ThreadMember(parent=thread, data=member))

        return threads

    async def fetch_scheduled_events(
        self, *, with_user_count: bool = False
    ) -> List[GuildScheduledEvent]:
        """|coro|

        Retrieves a list of all :class:`GuildScheduledEvent` instances that the guild has.

        .. versionadded:: 2.3

        Parameters
        ----------
        with_user_count: :class:`bool`
            Whether to include number of users subscribed to each event.

        Raises
        ------
        HTTPException
            Retrieving the guild scheduled events failed.

        Returns
        -------
        List[:class:`GuildScheduledEvent`]
            The existing guild scheduled events.
        """
        raw_events = await self._state.http.get_guild_scheduled_events(
            self.id, with_user_count=with_user_count
        )
        return [GuildScheduledEvent(state=self._state, data=data) for data in raw_events]

    async def fetch_scheduled_event(
        self, event_id: int, *, with_user_count: bool = False
    ) -> GuildScheduledEvent:
        """|coro|

        Retrieves a :class:`GuildScheduledEvent` with the given ID.

        .. versionadded:: 2.3

        Parameters
        ----------
        event_id: :class:`int`
            The ID to look for.
        with_user_count: :class:`bool`
            Whether to include number of users subscribed to the event.

        Raises
        ------
        HTTPException
            Retrieving the guild scheduled event failed.

        Returns
        -------
        :class:`GuildScheduledEvent`
            The guild scheduled event.
        """
        data = await self._state.http.get_guild_scheduled_event(
            self.id, event_id, with_user_count=with_user_count
        )
        return GuildScheduledEvent(state=self._state, data=data)

    @overload
    async def create_scheduled_event(
        self,
        *,
        name: str,
        entity_type: Literal[GuildScheduledEventEntityType.external],
        scheduled_start_time: datetime.datetime,
        scheduled_end_time: datetime.datetime,
        entity_metadata: GuildScheduledEventMetadata,
        privacy_level: GuildScheduledEventPrivacyLevel = ...,
        description: str = ...,
        image: AssetBytes = ...,
        reason: Optional[str] = ...,
    ) -> GuildScheduledEvent:
        ...

    @overload
    async def create_scheduled_event(
        self,
        *,
        name: str,
        channel: Snowflake,
        scheduled_start_time: datetime.datetime,
        entity_type: Literal[
            GuildScheduledEventEntityType.voice,
            GuildScheduledEventEntityType.stage_instance,
        ] = ...,
        scheduled_end_time: Optional[datetime.datetime] = ...,
        privacy_level: GuildScheduledEventPrivacyLevel = ...,
        description: str = ...,
        image: AssetBytes = ...,
        reason: Optional[str] = ...,
    ) -> GuildScheduledEvent:
        ...

    @overload
    async def create_scheduled_event(
        self,
        *,
        name: str,
        channel: None,
        scheduled_start_time: datetime.datetime,
        scheduled_end_time: datetime.datetime,
        entity_metadata: GuildScheduledEventMetadata,
        entity_type: Literal[GuildScheduledEventEntityType.external] = ...,
        privacy_level: GuildScheduledEventPrivacyLevel = ...,
        description: str = ...,
        image: AssetBytes = ...,
        reason: Optional[str] = ...,
    ) -> GuildScheduledEvent:
        ...

    async def create_scheduled_event(
        self,
        *,
        name: str,
        scheduled_start_time: datetime.datetime,
        channel: Optional[Snowflake] = MISSING,
        entity_type: GuildScheduledEventEntityType = MISSING,
        scheduled_end_time: Optional[datetime.datetime] = MISSING,
        privacy_level: GuildScheduledEventPrivacyLevel = MISSING,
        entity_metadata: GuildScheduledEventMetadata = MISSING,
        description: str = MISSING,
        image: AssetBytes = MISSING,
        reason: Optional[str] = None,
    ) -> GuildScheduledEvent:
        """|coro|

        Creates a :class:`GuildScheduledEvent`.

        You must have :attr:`~Permissions.manage_events` permission to do this.

        Based on the channel/entity type, there are different restrictions regarding
        other parameter values, as shown in this table:

        .. csv-table::
            :widths: 30, 30, 20, 20
            :header: "``channel``", "``entity_type``", "``scheduled_end_time``", "``entity_metadata`` with location"

            :class:`.abc.Snowflake` with ``type`` attribute being :class:`ChannelType.voice` , :attr:`~GuildScheduledEventEntityType.voice` (set automatically), optional, unset
            :class:`.abc.Snowflake` with ``type`` attribute being :class:`ChannelType.stage_voice`, :attr:`~GuildScheduledEventEntityType.stage_instance` (set automatically), optional, unset
            :class:`.abc.Snowflake` with missing/other ``type`` attribute, required, optional, unset
            ``None``, :attr:`~GuildScheduledEventEntityType.external` (set automatically), required, required
            unset, :attr:`~GuildScheduledEventEntityType.external`, required, required

        .. versionadded:: 2.3

        .. versionchanged:: 2.6
            Now raises :exc:`TypeError` instead of :exc:`ValueError` for
            invalid parameter types.

        .. versionchanged:: 2.6
            Removed ``channel_id`` parameter in favor of ``channel``.

        .. versionchanged:: 2.6
            Naive datetime parameters are now assumed to be in the local
            timezone instead of UTC.

        .. versionchanged:: 2.6
            Infer ``entity_type`` from channel if provided.

        Parameters
        ----------
        name: :class:`str`
            The name of the guild scheduled event.
        description: :class:`str`
            The description of the guild scheduled event.
        image: |resource_type|
            The cover image of the guild scheduled event.

            .. versionadded:: 2.4

            .. versionchanged:: 2.5
                Now accepts various resource types in addition to :class:`bytes`.

        channel: Optional[:class:`.abc.Snowflake`]
            The channel in which the guild scheduled event will be hosted.
            Passing in `None` assumes the ``entity_type`` to be :class:`GuildScheduledEventEntityType.external`

            .. versionadded:: 2.6

        privacy_level: :class:`GuildScheduledEventPrivacyLevel`
            The privacy level of the guild scheduled event.
        scheduled_start_time: :class:`datetime.datetime`
            The time to schedule the guild scheduled event.
            If the datetime is naive, it is assumed to be local time.
        scheduled_end_time: Optional[:class:`datetime.datetime`]
            The time when the guild scheduled event is scheduled to end.
            If the datetime is naive, it is assumed to be local time.
        entity_type: :class:`GuildScheduledEventEntityType`
            The entity type of the guild scheduled event.
        entity_metadata: :class:`GuildScheduledEventMetadata`
            The entity metadata of the guild scheduled event.
        reason: Optional[:class:`str`]
            The reason for creating the guild scheduled event. Shows up on the audit log.

        Raises
        ------
        NotFound
            The ``image`` asset couldn't be found.
        HTTPException
            The request failed.
        TypeError
            The ``image`` asset is a lottie sticker (see :func:`Sticker.read`),
            one of ``entity_type``, ``privacy_level``, or ``entity_metadata``
            is not of the correct type, or the ``entity_type`` was not provided and
            could not be assumed from the ``channel``.

        Returns
        -------
        :class:`GuildScheduledEvent`
            The newly created guild scheduled event.
        """
        if entity_type is MISSING:
            if channel is None:
                entity_type = GuildScheduledEventEntityType.external
            elif isinstance(channel_type := getattr(channel, "type", None), ChannelType):
                if channel_type is ChannelType.voice:
                    entity_type = GuildScheduledEventEntityType.voice
                elif channel_type is ChannelType.stage_voice:
                    entity_type = GuildScheduledEventEntityType.stage_instance
                else:
                    raise TypeError("channel type must be either 'voice' or 'stage_voice'")
            else:
                raise TypeError(
                    "`entity_type` must be provided if it cannot be derived from `channel`"
                )

        if not isinstance(entity_type, GuildScheduledEventEntityType):
            raise TypeError("entity_type must be an instance of GuildScheduledEventEntityType")

        if privacy_level is MISSING:
            privacy_level = GuildScheduledEventPrivacyLevel.guild_only
        elif not isinstance(privacy_level, GuildScheduledEventPrivacyLevel):
            raise TypeError("privacy_level must be an instance of GuildScheduledEventPrivacyLevel")

        fields: Dict[str, Any] = {
            "name": name,
            "privacy_level": privacy_level.value,
            "scheduled_start_time": utils.isoformat_utc(scheduled_start_time),
            "entity_type": entity_type.value,
        }

        if entity_metadata is not MISSING:
            if not isinstance(entity_metadata, GuildScheduledEventMetadata):
                raise TypeError(
                    "entity_metadata must be an instance of GuildScheduledEventMetadata"
                )

            fields["entity_metadata"] = entity_metadata.to_dict()

        if description is not MISSING:
            fields["description"] = description

        if image is not MISSING:
            fields["image"] = await utils._assetbytes_to_base64_data(image)

        if channel:
            fields["channel_id"] = channel.id

        if scheduled_end_time is not MISSING:
            fields["scheduled_end_time"] = utils.isoformat_utc(scheduled_end_time)

        data = await self._state.http.create_guild_scheduled_event(self.id, reason=reason, **fields)
        return GuildScheduledEvent(state=self._state, data=data)

    async def welcome_screen(self) -> WelcomeScreen:
        """|coro|

        Retrieves the guild's :class:`WelcomeScreen`.

        Requires the :attr:`~Permissions.manage_guild` permission if the welcome screen is not enabled.

        .. note::

            To determine whether the welcome screen is enabled, check for the
            presence of ``WELCOME_SCREEN_ENABLED`` in :attr:`Guild.features`.

        .. versionadded:: 2.5

        Raises
        ------
        NotFound
            The welcome screen is not set up, or you do not have permission to view it.
        HTTPException
            Retrieving the welcome screen failed.

        Returns
        -------
        :class:`WelcomeScreen`
            The guild's welcome screen.
        """
        data = await self._state.http.get_guild_welcome_screen(self.id)
        return WelcomeScreen(state=self._state, data=data, guild=self)

    async def edit_welcome_screen(
        self,
        *,
        enabled: bool = MISSING,
        channels: Optional[List[WelcomeScreenChannel]] = MISSING,
        description: Optional[str] = MISSING,
        reason: Optional[str] = None,
    ) -> WelcomeScreen:
        """|coro|

        This is a lower level method to :meth:`WelcomeScreen.edit` that allows you
        to edit the welcome screen without fetching it and save an API request.

        This requires 'COMMUNITY' in :attr:`.Guild.features`.

        .. versionadded:: 2.5

        Parameters
        ----------
        enabled: :class:`bool`
            Whether the welcome screen is enabled.
        description: Optional[:class:`str`]
            The new guild description in the welcome screen.
        channels: Optional[List[:class:`WelcomeScreenChannel`]]
            The new welcome channels.
        reason: Optional[:class:`str`]
            The reason for editing the welcome screen. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have permissions to change the welcome screen
            or the guild is not allowed to create welcome screens.
        HTTPException
            Editing the welcome screen failed.
        TypeError
            ``channels`` is not a list of :class:`~disnake.WelcomeScreenChannel` instances

        Returns
        -------
        :class:`WelcomeScreen`
            The newly edited welcome screen.
        """
        payload = {}

        if enabled is not MISSING:
            payload["enabled"] = enabled

        if description is not MISSING:
            payload["description"] = description

        if channels is not MISSING:
            if channels is None:
                payload["welcome_channels"] = None
            else:
                welcome_channel_payload = []
                for channel in channels:
                    if not isinstance(channel, WelcomeScreenChannel):
                        raise TypeError(
                            "'channels' must be a list of 'WelcomeScreenChannel' objects"
                        )
                    welcome_channel_payload.append(channel.to_dict())
                payload["welcome_channels"] = welcome_channel_payload

        data = await self._state.http.edit_guild_welcome_screen(self.id, reason=reason, **payload)
        return WelcomeScreen(state=self._state, data=data, guild=self)

    # TODO: Remove Optional typing here when async iterators are refactored
    def fetch_members(
        self, *, limit: Optional[int] = 1000, after: Optional[SnowflakeTime] = None
    ) -> MemberIterator:
        """Retrieves an :class:`.AsyncIterator` that enables receiving the guild's members.

        In order to use this, the :attr:`~Intents.members` intent must be
        enabled in the developer portal.

        .. note::

            This method is an API call. For general usage, consider :attr:`members` instead.

        .. versionadded:: 1.3

        .. versionchanged:: 2.9
            No longer requires the intent to be enabled on the websocket connection.

        All parameters are optional.

        Parameters
        ----------
        limit: Optional[:class:`int`]
            The number of members to retrieve. Defaults to 1000.
            Pass ``None`` to fetch all members. Note that this is potentially slow.
        after: Optional[Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve members after this date or object.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.

        Raises
        ------
        ClientException
            The members intent is not enabled in the developer portal.
        HTTPException
            Retrieving the members failed.

        Yields
        ------
        :class:`.Member`
            The member with the member data parsed.

        Examples
        --------
        Usage ::

            async for member in guild.fetch_members(limit=150):
                print(member.name)

        Flattening into a list ::

            members = await guild.fetch_members(limit=150).flatten()
            # members is now a list of Member...
        """
        # `hasattr` check to avoid issues with uninitialized state
        if hasattr(self._state, "application_flags"):
            flags = self._state.application_flags
            if not (flags.gateway_guild_members_limited or flags.gateway_guild_members):
                raise ClientException(
                    "The `members` intent must be enabled in the Developer Portal to be able to use this method."
                )

        return MemberIterator(self, limit=limit, after=after)

    async def fetch_member(self, member_id: int, /) -> Member:
        """|coro|

        Retrieves a :class:`Member` with the given ID.

        .. note::

            This method is an API call. If you have :attr:`Intents.members` and member cache enabled, consider :meth:`get_member` instead.

        Parameters
        ----------
        member_id: :class:`int`
            The member's ID to fetch from.

        Raises
        ------
        NotFound
            A member with this ID does not exist in the guild.
        Forbidden
            You do not have access to the guild.
        HTTPException
            Retrieving the member failed.

        Returns
        -------
        :class:`Member`
            The member from the member ID.
        """
        data = await self._state.http.get_member(self.id, member_id)
        return Member(data=data, state=self._state, guild=self)

    async def fetch_ban(self, user: Snowflake) -> BanEntry:
        """|coro|

        Retrieves the :class:`BanEntry` for a user.

        You must have :attr:`~Permissions.ban_members` permission
        to use this.

        Parameters
        ----------
        user: :class:`abc.Snowflake`
            The user to get ban information from.

        Raises
        ------
        Forbidden
            You do not have proper permissions to get the information.
        NotFound
            This user is not banned.
        HTTPException
            An error occurred while fetching the information.

        Returns
        -------
        :class:`BanEntry`
            The :class:`BanEntry` object for the specified user.
        """
        data: BanPayload = await self._state.http.get_ban(user.id, self.id)
        return BanEntry(user=User(state=self._state, data=data["user"]), reason=data["reason"])

    async def fetch_channel(self, channel_id: int, /) -> Union[GuildChannel, Thread]:
        """|coro|

        Retrieves a :class:`.abc.GuildChannel` or :class:`.Thread` with the given ID.

        .. note::

            This method is an API call. For general usage, consider :meth:`get_channel_or_thread` instead.

        .. versionadded:: 2.0

        Raises
        ------
        InvalidData
            An unknown channel type was received from Discord
            or the guild the channel belongs to is not the same
            as the one in this object points to.
        HTTPException
            Retrieving the channel failed.
        NotFound
            Invalid Channel ID.
        Forbidden
            You do not have permission to fetch this channel.

        Returns
        -------
        Union[:class:`.abc.GuildChannel`, :class:`.Thread`]
            The channel from the ID.
        """
        data = await self._state.http.get_channel(channel_id)

        factory, ch_type = _threaded_guild_channel_factory(data["type"])
        if factory is None:
            raise InvalidData("Unknown channel type {type} for channel ID {id}.".format_map(data))

        if ch_type in (ChannelType.group, ChannelType.private):
            raise InvalidData("Channel ID resolved to a private channel")

        guild_id = int(data["guild_id"])  # type: ignore
        if self.id != guild_id:
            raise InvalidData("Guild ID resolved to a different guild")

        channel: GuildChannel = factory(guild=self, state=self._state, data=data)  # type: ignore
        return channel

    def bans(
        self,
        *,
        limit: Optional[int] = 1000,
        before: Optional[Snowflake] = None,
        after: Optional[Snowflake] = None,
    ) -> BanIterator:
        """Returns an :class:`~disnake.AsyncIterator` that enables receiving the destination's bans.

        You must have the :attr:`~Permissions.ban_members` permission to get this information.

        .. versionchanged:: 2.5
            Due to a breaking change in Discord's API, this now returns an :class:`~disnake.AsyncIterator` instead of a :class:`list`.

        Examples
        --------
        Usage ::

            counter = 0
            async for ban in guild.bans(limit=200):
                if not ban.user.bot:
                    counter += 1

        Flattening into a list: ::

            bans = await guild.bans(limit=123).flatten()
            # bans is now a list of BanEntry...

        All parameters are optional.

        Parameters
        ----------
        limit: Optional[:class:`int`]
            The number of bans to retrieve.
            If ``None``, it retrieves every ban in the guild. Note, however,
            that this would make it a slow operation.
            Defaults to 1000.
        before: Optional[:class:`~disnake.abc.Snowflake`]
            Retrieve bans before this user.
        after: Optional[:class:`~disnake.abc.Snowflake`]
            Retrieve bans after this user.

        Raises
        ------
        ~disnake.Forbidden
            You do not have permissions to get the bans.
        ~disnake.HTTPException
            An error occurred while fetching the bans.

        Yields
        ------
        :class:`~disnake.BanEntry`
            The ban with the ban data parsed.
        """
        return BanIterator(self, limit=limit, before=before, after=after)

    async def prune_members(
        self,
        *,
        days: int,
        compute_prune_count: bool = True,
        roles: List[Snowflake] = MISSING,
        reason: Optional[str] = None,
    ) -> Optional[int]:
        """|coro|

        Prunes the guild from its inactive members.

        The inactive members are denoted if they have not logged on in
        ``days`` number of days and they have no roles.

        You must have the :attr:`~Permissions.manage_guild` and
        :attr:`~Permissions.kick_members` permissions to use this.

        To check how many members you would prune without actually pruning,
        see the :meth:`estimate_pruned_members` function.

        To prune members that have specific roles see the ``roles`` parameter.

        .. versionchanged:: 1.4
            The ``roles`` keyword-only parameter was added.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Parameters
        ----------
        days: :class:`int`
            The number of days before counting as inactive.
        compute_prune_count: :class:`bool`
            Whether to compute the prune count. This defaults to ``True``
            which makes it prone to timeouts in very large guilds. In order
            to prevent timeouts, you must set this to ``False``. If this is
            set to ``False``\\, then this function will always return ``None``.
        roles: List[:class:`abc.Snowflake`]
            A list of :class:`abc.Snowflake` that represent roles to include in the pruning process. If a member
            has a role that is not specified, they'll be excluded.
        reason: Optional[:class:`str`]
            The reason for doing this action. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have permissions to prune members.
        HTTPException
            An error occurred while pruning members.
        TypeError
            An integer was not passed for ``days``.

        Returns
        -------
        Optional[:class:`int`]
            The number of members pruned. If ``compute_prune_count`` is ``False``
            then this returns ``None``.
        """
        if not isinstance(days, int):
            raise TypeError(
                f"Expected int for ``days``, received {days.__class__.__name__} instead."
            )

        if roles:
            role_ids = [str(role.id) for role in roles]
        else:
            role_ids = []

        data = await self._state.http.prune_members(
            self.id, days, compute_prune_count=compute_prune_count, roles=role_ids, reason=reason
        )
        return data["pruned"]

    async def templates(self) -> List[Template]:
        """|coro|

        Gets the list of templates from this guild.

        You must have :attr:`~.Permissions.manage_guild` permission
        to use this.

        .. versionadded:: 1.7

        Raises
        ------
        Forbidden
            You don't have permissions to get the templates.

        Returns
        -------
        List[:class:`Template`]
            The templates for this guild.
        """
        from .template import Template

        data = await self._state.http.guild_templates(self.id)
        return [Template(data=d, state=self._state) for d in data]

    async def webhooks(self) -> List[Webhook]:
        """|coro|

        Gets the list of webhooks from this guild.

        You must have :attr:`~.Permissions.manage_webhooks` permission
        to use this.

        Raises
        ------
        Forbidden
            You don't have permissions to get the webhooks.

        Returns
        -------
        List[:class:`Webhook`]
            The webhooks for this guild.
        """
        from .webhook import Webhook

        data = await self._state.http.guild_webhooks(self.id)
        return [Webhook.from_state(d, state=self._state) for d in data]

    async def estimate_pruned_members(self, *, days: int, roles: List[Snowflake] = MISSING) -> int:
        """|coro|

        Similar to :meth:`prune_members` except instead of actually
        pruning members, it returns how many members it would prune
        from the guild had it been called.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Parameters
        ----------
        days: :class:`int`
            The number of days before counting as inactive.
        roles: List[:class:`abc.Snowflake`]
            A list of :class:`abc.Snowflake` that represent roles to include in the estimate. If a member
            has a role that is not specified, they'll be excluded.

            .. versionadded:: 1.7

        Raises
        ------
        Forbidden
            You do not have permissions to prune members.
        HTTPException
            An error occurred while fetching the prune members estimate.
        TypeError
            An integer was not passed for ``days``.

        Returns
        -------
        :class:`int`
            The number of members estimated to be pruned.
        """
        if not isinstance(days, int):
            raise TypeError(
                f"Expected int for ``days``, received {days.__class__.__name__} instead."
            )

        if roles:
            role_ids = [str(role.id) for role in roles]
        else:
            role_ids = []

        data = await self._state.http.estimate_pruned_members(self.id, days, role_ids)
        return data["pruned"]

    async def invites(self) -> List[Invite]:
        """|coro|

        Returns a list of all active instant invites from the guild.

        You must have :attr:`~Permissions.manage_guild` permission to
        use this.

        .. note::

            This method does not include the guild's vanity URL invite.
            To get the vanity URL :class:`Invite`, refer to :meth:`Guild.vanity_invite`.

        Raises
        ------
        Forbidden
            You do not have proper permissions to get the information.
        HTTPException
            An error occurred while fetching the information.

        Returns
        -------
        List[:class:`Invite`]
            The list of invites that are currently active.
        """
        data = await self._state.http.invites_from(self.id)
        result = []
        for invite in data:
            if channel_data := invite.get("channel"):
                channel = self.get_channel(int(channel_data["id"]))
            else:
                channel = None
            result.append(Invite(state=self._state, data=invite, guild=self, channel=channel))

        return result

    async def create_template(self, *, name: str, description: str = MISSING) -> Template:
        """|coro|

        Creates a template for the guild.

        You must have :attr:`~Permissions.manage_guild` permission to
        use this.

        .. versionadded:: 1.7

        Parameters
        ----------
        name: :class:`str`
            The name of the template.
        description: :class:`str`
            The description of the template.

        Returns
        -------
        :class:`Template`
            The created template.
        """
        from .template import Template

        payload: Any = {"name": name}

        if description:
            payload["description"] = description

        data = await self._state.http.create_template(self.id, payload)

        return Template(state=self._state, data=data)

    @utils.deprecated()
    async def create_integration(self, *, type: IntegrationType, id: int) -> None:
        """|coro|

        .. deprecated:: 2.5
            No longer supported, bots cannot use this endpoint anymore.

        Attaches an integration to the guild.

        You must have :attr:`~Permissions.manage_guild` permission to
        use this.

        .. versionadded:: 1.4

        Parameters
        ----------
        type: :class:`str`
            The integration type (e.g. Twitch).
        id: :class:`int`
            The integration ID.

        Raises
        ------
        Forbidden
            You do not have permission to create the integration.
        HTTPException
            The account could not be found.
        """
        await self._state.http.create_integration(self.id, type, id)

    async def integrations(self) -> List[Integration]:
        """|coro|

        Returns a list of all integrations attached to the guild.

        You must have :attr:`~Permissions.manage_guild` permission to
        use this.

        .. versionadded:: 1.4

        Raises
        ------
        Forbidden
            You do not have permission to create the integration.
        HTTPException
            Fetching the integrations failed.

        Returns
        -------
        List[:class:`Integration`]
            The list of integrations that are attached to the guild.
        """
        data = await self._state.http.get_all_integrations(self.id)

        def convert(d):
            factory, _ = _integration_factory(d["type"])
            return factory(guild=self, data=d)

        return [convert(d) for d in data]

    async def fetch_stickers(self) -> List[GuildSticker]:
        """|coro|

        Retrieves a list of all :class:`Sticker`\\s that the guild has.

        .. versionadded:: 2.0

        .. note::

            This method is an API call. For general usage, consider :attr:`stickers` instead.

        Raises
        ------
        HTTPException
            Retrieving the stickers failed.

        Returns
        -------
        List[:class:`GuildSticker`]
            The retrieved stickers.
        """
        data = await self._state.http.get_all_guild_stickers(self.id)
        return [GuildSticker(state=self._state, data=d) for d in data]

    async def fetch_sticker(self, sticker_id: int, /) -> GuildSticker:
        """|coro|

        Retrieves a custom :class:`Sticker` from the guild.

        .. versionadded:: 2.0

        .. note::

            This method is an API call.
            For general usage, consider iterating over :attr:`stickers` instead.

        Parameters
        ----------
        sticker_id: :class:`int`
            The sticker's ID.

        Raises
        ------
        NotFound
            The sticker requested could not be found.
        HTTPException
            Retrieving the sticker failed.

        Returns
        -------
        :class:`GuildSticker`
            The retrieved sticker.
        """
        data = await self._state.http.get_guild_sticker(self.id, sticker_id)
        return GuildSticker(state=self._state, data=data)

    async def create_sticker(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        emoji: str,
        file: File,
        reason: Optional[str] = None,
    ) -> GuildSticker:
        """|coro|

        Creates a :class:`Sticker` for the guild.

        You must have :attr:`~Permissions.manage_guild_expressions` permission to
        do this.

        .. versionadded:: 2.0

        Parameters
        ----------
        name: :class:`str`
            The sticker name. Must be at least 2 characters.
        description: Optional[:class:`str`]
            The sticker's description. You can pass ``None`` or an empty string to not set a description.
        emoji: :class:`str`
            The name of a unicode emoji that represents the sticker's expression.
        file: :class:`File`
            The file of the sticker to upload.
        reason: Optional[:class:`str`]
            The reason for creating this sticker. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You are not allowed to create stickers.
        HTTPException
            An error occurred creating a sticker.

        Returns
        -------
        :class:`GuildSticker`
            The newly created sticker.
        """
        if description is None:
            description = ""

        try:
            emoji = unicodedata.name(emoji)
        except TypeError:
            pass
        else:
            emoji = emoji.replace(" ", "_")

        payload: CreateStickerPayload = {"name": name, "description": description, "tags": emoji}

        data = await self._state.http.create_guild_sticker(self.id, payload, file, reason=reason)
        return self._state.store_sticker(self, data)

    async def delete_sticker(self, sticker: Snowflake, *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes the custom :class:`Sticker` from the guild.

        You must have :attr:`~Permissions.manage_guild_expressions` permission to
        do this.

        .. versionadded:: 2.0

        Parameters
        ----------
        sticker: :class:`abc.Snowflake`
            The sticker you are deleting.
        reason: Optional[:class:`str`]
            The reason for deleting this sticker. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You are not allowed to delete this sticker.
        HTTPException
            An error occurred deleting the sticker.
        """
        await self._state.http.delete_guild_sticker(self.id, sticker.id, reason=reason)

    async def fetch_emojis(self) -> List[Emoji]:
        """|coro|

        Retrieves all custom :class:`Emoji`\\s that the guild has.

        .. note::

            This method is an API call. For general usage, consider :attr:`emojis` instead.

        Raises
        ------
        HTTPException
            Retrieving the emojis failed.

        Returns
        -------
        List[:class:`Emoji`]
            The retrieved emojis.
        """
        data = await self._state.http.get_all_custom_emojis(self.id)
        return [Emoji(guild=self, state=self._state, data=d) for d in data]

    async def fetch_emoji(self, emoji_id: int, /) -> Emoji:
        """|coro|

        Retrieves a custom :class:`Emoji` from the guild.

        .. note::

            This method is an API call.
            For general usage, consider iterating over :attr:`emojis` instead.

        Parameters
        ----------
        emoji_id: :class:`int`
            The emoji's ID.

        Raises
        ------
        NotFound
            The emoji requested could not be found.
        HTTPException
            An error occurred fetching the emoji.

        Returns
        -------
        :class:`Emoji`
            The retrieved emoji.
        """
        data = await self._state.http.get_custom_emoji(self.id, emoji_id)
        return Emoji(guild=self, state=self._state, data=data)

    async def create_custom_emoji(
        self,
        *,
        name: str,
        image: AssetBytes,
        roles: Sequence[Role] = MISSING,
        reason: Optional[str] = None,
    ) -> Emoji:
        """|coro|

        Creates a custom :class:`Emoji` for the guild.

        Depending on the boost level of your guild (which can be obtained via :attr:`premium_tier`),
        the amount of custom emojis that can be created changes:

        .. csv-table::
            :header: "Boost level", "Max custom emoji limit"

            "0", "50"
            "1", "100"
            "2", "150"
            "3", "250"

        Emojis with subscription roles (see ``roles`` below) are considered premium emoji,
        and count towards a separate limit of 25 emojis.

        You must have :attr:`~Permissions.manage_guild_expressions` permission to
        do this.

        Parameters
        ----------
        name: :class:`str`
            The emoji name. Must be at least 2 characters.
        image: |resource_type|
            The image data of the emoji.
            Only JPG, PNG and GIF images are supported.

            .. versionchanged:: 2.5
                Now accepts various resource types in addition to :class:`bytes`.

        roles: List[:class:`Role`]
            A list of roles that can use this emoji. Leave empty to make it available to everyone.

            An emoji cannot have both subscription roles (see :attr:`RoleTags.integration_id`) and
            non-subscription roles, and emojis can't be converted between premium and non-premium
            after creation.

        reason: Optional[:class:`str`]
            The reason for creating this emoji. Shows up on the audit log.

        Raises
        ------
        NotFound
            The ``image`` asset couldn't be found.
        Forbidden
            You are not allowed to create emojis.
        HTTPException
            An error occurred creating an emoji.
        TypeError
            The ``image`` asset is a lottie sticker (see :func:`Sticker.read`).
        ValueError
            Wrong image format passed for ``image``.

        Returns
        -------
        :class:`Emoji`
            The newly created emoji.
        """
        img = await utils._assetbytes_to_base64_data(image)
        if roles:
            role_ids = [role.id for role in roles]
        else:
            role_ids = []

        data = await self._state.http.create_custom_emoji(
            self.id, name, img, roles=role_ids, reason=reason
        )
        return self._state.store_emoji(self, data)

    async def delete_emoji(self, emoji: Snowflake, *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes the custom :class:`Emoji` from the guild.

        You must have :attr:`~Permissions.manage_guild_expressions` permission to
        do this.

        Parameters
        ----------
        emoji: :class:`abc.Snowflake`
            The emoji you are deleting.
        reason: Optional[:class:`str`]
            The reason for deleting this emoji. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You are not allowed to delete this emoji.
        HTTPException
            An error occurred deleting the emoji.
        """
        await self._state.http.delete_custom_emoji(self.id, emoji.id, reason=reason)

    async def fetch_roles(self) -> List[Role]:
        """|coro|

        Retrieves all :class:`Role` that the guild has.

        .. note::

            This method is an API call. For general usage, consider :attr:`roles` instead.

        .. versionadded:: 1.3

        Raises
        ------
        HTTPException
            Retrieving the roles failed.

        Returns
        -------
        List[:class:`Role`]
            All roles that the guild has.
        """
        data = await self._state.http.get_roles(self.id)
        return [Role(guild=self, state=self._state, data=d) for d in data]

    @overload
    async def get_or_fetch_member(
        self, member_id: int, *, strict: Literal[False] = ...
    ) -> Optional[Member]:
        ...

    @overload
    async def get_or_fetch_member(self, member_id: int, *, strict: Literal[True]) -> Member:
        ...

    async def get_or_fetch_member(
        self, member_id: int, *, strict: bool = False
    ) -> Optional[Member]:
        """|coro|

        Tries to get the member from the cache. If it fails,
        fetches the member from the API and caches it.

        If you want to make a bulk get-or-fetch call, use :meth:`get_or_fetch_members`.

        This only propagates exceptions when the ``strict`` parameter is enabled.

        Parameters
        ----------
        member_id: :class:`int`
            The ID to search for.
        strict: :class:`bool`
            Whether to propagate exceptions from :func:`fetch_member`
            instead of returning ``None`` in case of failure
            (e.g. if the member wasn't found).
            Defaults to ``False``.

        Returns
        -------
        Optional[:class:`Member`]
            The member with the given ID, or ``None`` if not found and ``strict`` is set to ``False``.
        """
        member = self.get_member(member_id)
        if member is not None:
            return member
        try:
            member = await self.fetch_member(member_id)
            self._add_member(member)
        except HTTPException:
            if strict:
                raise
            return None
        return member

    getch_member = get_or_fetch_member

    @overload
    async def create_role(
        self,
        *,
        reason: Optional[str] = ...,
        name: str = ...,
        permissions: Permissions = ...,
        colour: Union[Colour, int] = ...,
        hoist: bool = ...,
        icon: AssetBytes = ...,
        emoji: str = ...,
        mentionable: bool = ...,
    ) -> Role:
        ...

    @overload
    async def create_role(
        self,
        *,
        reason: Optional[str] = ...,
        name: str = ...,
        permissions: Permissions = ...,
        color: Union[Colour, int] = ...,
        hoist: bool = ...,
        icon: AssetBytes = ...,
        emoji: str = ...,
        mentionable: bool = ...,
    ) -> Role:
        ...

    async def create_role(
        self,
        *,
        name: str = MISSING,
        permissions: Permissions = MISSING,
        color: Union[Colour, int] = MISSING,
        colour: Union[Colour, int] = MISSING,
        hoist: bool = MISSING,
        icon: AssetBytes = MISSING,
        emoji: str = MISSING,
        mentionable: bool = MISSING,
        reason: Optional[str] = None,
    ) -> Role:
        """|coro|

        Creates a :class:`Role` for the guild.

        All fields are optional.

        You must have :attr:`~Permissions.manage_roles` permission to
        do this.

        .. versionchanged:: 1.6
            Can now pass ``int`` to ``colour`` keyword-only parameter.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The role name. Defaults to 'new role'.
        permissions: :class:`Permissions`
            The permissions the role should have. Defaults to no permissions.
        colour: Union[:class:`Colour`, :class:`int`]
            The colour for the role. Defaults to :meth:`Colour.default`.
            This is aliased to ``color`` as well.
        hoist: :class:`bool`
            Whether the role should be shown separately in the member list.
            Defaults to ``False``.
        icon: |resource_type|
            The role's icon image (if the guild has the ``ROLE_ICONS`` feature).

            .. versionchanged:: 2.5
                Now accepts various resource types in addition to :class:`bytes`.

        emoji: :class:`str`
            The role's unicode emoji.
        mentionable: :class:`bool`
            Whether the role should be mentionable by others.
            Defaults to ``False``.
        reason: Optional[:class:`str`]
            The reason for creating this role. Shows up on the audit log.

        Raises
        ------
        NotFound
            The ``icon`` asset couldn't be found.
        Forbidden
            You do not have permissions to create the role.
        HTTPException
            Creating the role failed.
        TypeError
            An invalid keyword argument was given,
            or the ``icon`` asset is a lottie sticker (see :func:`Sticker.read`).

        Returns
        -------
        :class:`Role`
            The newly created role.
        """
        fields: CreateRolePayload = {}
        if permissions is not MISSING:
            fields["permissions"] = str(permissions.value)
        else:
            fields["permissions"] = "0"

        actual_colour = colour or color or Colour.default()
        if isinstance(actual_colour, int):
            fields["color"] = actual_colour
        else:
            fields["color"] = actual_colour.value

        if hoist is not MISSING:
            fields["hoist"] = hoist

        if mentionable is not MISSING:
            fields["mentionable"] = mentionable

        if name is not MISSING:
            fields["name"] = name

        if icon is not MISSING:
            fields["icon"] = await utils._assetbytes_to_base64_data(icon)

        if emoji is not MISSING:
            fields["unicode_emoji"] = emoji

        data = await self._state.http.create_role(self.id, reason=reason, **fields)
        role = Role(guild=self, data=data, state=self._state)

        # TODO: add to cache
        return role

    async def edit_role_positions(
        self, positions: Dict[Snowflake, int], *, reason: Optional[str] = None
    ) -> List[Role]:
        """|coro|

        Bulk edits a list of :class:`Role` in the guild.

        You must have :attr:`~Permissions.manage_roles` permission to
        do this.

        .. versionadded:: 1.4

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Example:

        .. code-block:: python3

            positions = {
                bots_role: 1, # penultimate role
                tester_role: 2,
                admin_role: 6
            }

            await guild.edit_role_positions(positions=positions)

        Parameters
        ----------
        positions
            A :class:`dict` of :class:`Role` to :class:`int` to change the positions
            of each given role.
        reason: Optional[:class:`str`]
            The reason for editing the role positions. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have permissions to move the roles.
        HTTPException
            Moving the roles failed.
        TypeError
            An invalid keyword argument was given.

        Returns
        -------
        List[:class:`Role`]
            A list of all the roles in the guild.
        """
        if not isinstance(positions, dict):
            raise TypeError("positions parameter expects a dict.")

        role_positions: List[Any] = []
        for role, position in positions.items():
            payload = {"id": role.id, "position": position}

            role_positions.append(payload)

        data = await self._state.http.move_role_position(self.id, role_positions, reason=reason)
        roles: List[Role] = []
        for d in data:
            role = Role(guild=self, data=d, state=self._state)
            roles.append(role)
            self._roles[role.id] = role

        return roles

    async def kick(self, user: Snowflake, *, reason: Optional[str] = None) -> None:
        """|coro|

        Kicks a user from the guild.

        The user must meet the :class:`abc.Snowflake` abc.

        You must have :attr:`~Permissions.kick_members` permission to
        do this.

        Parameters
        ----------
        user: :class:`abc.Snowflake`
            The user to kick from the guild.
        reason: Optional[:class:`str`]
            The reason for kicking this user. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to kick.
        HTTPException
            Kicking failed.
        """
        await self._state.http.kick(user.id, self.id, reason=reason)

    @overload
    async def ban(
        self,
        user: Snowflake,
        *,
        clean_history_duration: Union[int, datetime.timedelta] = 86400,
        reason: Optional[str] = None,
    ) -> None:
        ...

    @overload
    async def ban(
        self,
        user: Snowflake,
        *,
        delete_message_days: Literal[0, 1, 2, 3, 4, 5, 6, 7] = 1,
        reason: Optional[str] = None,
    ) -> None:
        ...

    async def ban(
        self,
        user: Snowflake,
        *,
        clean_history_duration: Union[int, datetime.timedelta] = MISSING,
        delete_message_days: Literal[0, 1, 2, 3, 4, 5, 6, 7] = MISSING,
        reason: Optional[str] = None,
    ) -> None:
        """|coro|

        Bans a user from the guild.

        The user must meet the :class:`abc.Snowflake` abc.

        You must have :attr:`~Permissions.ban_members` permission to
        do this.

        Parameters
        ----------
        user: :class:`abc.Snowflake`
            The user to ban from the guild.
        clean_history_duration: Union[:class:`int`, :class:`datetime.timedelta`]
            The timespan (seconds or timedelta) of messages to delete from the user
            in the guild, up to 7 days (604800 seconds).
            Defaults to 1 day (86400 seconds).

            This is incompatible with ``delete_message_days``.

            .. versionadded:: 2.6

            .. note::
                This may not be accurate with small durations (e.g. a few minutes)
                and delete a couple minutes' worth of messages more than specified.

        delete_message_days: :class:`int`
            The number of days worth of messages to delete from the user
            in the guild. The minimum is 0 and the maximum is 7.

            This is incompatible with ``clean_history_duration``.

            .. deprecated:: 2.6
                Use ``clean_history_duration`` instead.

        reason: Optional[:class:`str`]
            The reason for banning this user. Shows up on the audit log.

        Raises
        ------
        TypeError
            Both ``clean_history_duration`` and ``delete_message_days`` were provided,
            or ``clean_history_duration`` has an invalid type.
        Forbidden
            You do not have the proper permissions to ban.
        HTTPException
            Banning failed.
        """
        if delete_message_days is not MISSING and clean_history_duration is not MISSING:
            raise TypeError(
                "Only one of `clean_history_duration` and `delete_message_days` may be provided."
            )

        if delete_message_days is not MISSING:
            utils.warn_deprecated(
                "`delete_message_days` is deprecated and will be removed in a future version. Consider using `clean_history_duration` instead.",
                stacklevel=2,
            )
            delete_message_seconds = delete_message_days * 86400
        elif clean_history_duration is MISSING:
            delete_message_seconds = 86400
        elif isinstance(clean_history_duration, datetime.timedelta):
            delete_message_seconds = int(clean_history_duration.total_seconds())
        elif isinstance(clean_history_duration, int):
            delete_message_seconds = clean_history_duration
        else:
            raise TypeError(
                "`clean_history_duration` should be int or timedelta, "
                f"not {type(clean_history_duration).__name__}"
            )

        await self._state.http.ban(
            user.id, self.id, delete_message_seconds=delete_message_seconds, reason=reason
        )

    async def unban(self, user: Snowflake, *, reason: Optional[str] = None) -> None:
        """|coro|

        Unbans a user from the guild.

        The user must meet the :class:`abc.Snowflake` abc.

        You must have :attr:`~Permissions.ban_members` permission to
        do this.

        Parameters
        ----------
        user: :class:`abc.Snowflake`
            The user to unban.
        reason: Optional[:class:`str`]
            The reason for unbanning this user. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to unban.
        HTTPException
            Unbanning failed.
        """
        await self._state.http.unban(user.id, self.id, reason=reason)

    async def bulk_ban(
        self,
        users: Iterable[Snowflake],
        *,
        clean_history_duration: Union[int, datetime.timedelta] = 0,
        reason: Optional[str] = None,
    ) -> BulkBanResult:
        """|coro|

        Bans multiple users from the guild at once.

        The users must meet the :class:`abc.Snowflake` abc.

        You must have :attr:`~Permissions.ban_members` and :attr:`~Permissions.manage_guild`
        permissions to do this.

        .. versionadded:: 2.10

        Parameters
        ----------
        users: Iterable[:class:`abc.Snowflake`]
            The users to ban from the guild, up to 200.
        clean_history_duration: Union[:class:`int`, :class:`datetime.timedelta`]
            The timespan (seconds or timedelta) of messages to delete from the users
            in the guild, up to 7 days (604800 seconds).
            Defaults to ``0``.

            .. note::
                This may not be accurate with small durations (e.g. a few minutes)
                and delete a couple minutes' worth of messages more than specified.

        reason: Optional[:class:`str`]
            The reason for banning the users. Shows up on the audit log.

        Raises
        ------
        TypeError
            ``clean_history_duration`` has an invalid type.
        Forbidden
            You do not have the proper permissions to bulk ban.
        HTTPException
            Banning failed. This is also raised if none of the users could be banned.

        Returns
        -------
        :class:`BulkBanResult`
            An object containing the successful and failed bans.
        """
        if isinstance(clean_history_duration, datetime.timedelta):
            delete_message_seconds = int(clean_history_duration.total_seconds())
        elif isinstance(clean_history_duration, int):
            delete_message_seconds = clean_history_duration
        else:
            raise TypeError(
                "`clean_history_duration` should be int or timedelta, "
                f"not {type(clean_history_duration).__name__}"
            )

        data = await self._state.http.bulk_ban(
            [user.id for user in users],
            self.id,
            delete_message_seconds=delete_message_seconds,
            reason=reason,
        )

        return BulkBanResult(
            # these keys should always exist, but have a fallback just in case
            [Object(u) for u in (data.get("banned_users") or [])],
            [Object(u) for u in (data.get("failed_users") or [])],
        )

    async def vanity_invite(self, *, use_cached: bool = False) -> Optional[Invite]:
        """|coro|

        Returns the guild's special vanity invite.

        The guild must have ``VANITY_URL`` in :attr:`~Guild.features`.

        If ``use_cached`` is False, then you must have
        :attr:`~Permissions.manage_guild` permission to use this.

        Parameters
        ----------
        use_cached: :class:`bool`
            Whether to use the cached :attr:`Guild.vanity_url_code`
            and attempt to convert it into a full invite.

            .. note::

                If set to ``True``, the :attr:`Invite.uses`
                information will not be accurate.

            .. versionadded:: 2.5

        Raises
        ------
        Forbidden
            You do not have the proper permissions to get this.
        HTTPException
            Retrieving the vanity invite failed.

        Returns
        -------
        Optional[:class:`Invite`]
            The special vanity invite. If ``None`` then the guild does not
            have a vanity invite set.
        """
        # we start with { code: abc }
        if use_cached:
            if not self.vanity_url_code:
                return None
            payload: Any = {"code": self.vanity_url_code}
        else:
            payload: Any = await self._state.http.get_vanity_code(self.id)
            if not payload["code"]:
                return None

        # get the vanity URL channel since default channels aren't
        # reliable or a thing anymore
        data = await self._state.http.get_invite(payload["code"])

        if channel_data := data.get("channel"):
            channel = self.get_channel(int(channel_data["id"]))
        else:
            channel = None
        payload["temporary"] = False
        payload["max_uses"] = 0
        payload["max_age"] = 0
        payload["uses"] = payload.get("uses", 0)
        payload["type"] = 0
        return Invite(state=self._state, data=payload, guild=self, channel=channel)

    # TODO: use MISSING when async iterators get refactored
    def audit_logs(
        self,
        *,
        limit: Optional[int] = 100,
        before: Optional[SnowflakeTime] = None,
        after: Optional[SnowflakeTime] = None,
        user: Optional[Snowflake] = None,
        action: Optional[AuditLogAction] = None,
        oldest_first: bool = False,
    ) -> AuditLogIterator:
        """Returns an :class:`AsyncIterator` that enables receiving the guild's audit logs.

        You must have :attr:`~Permissions.view_audit_log` permission to use this.

        Entries are returned in order from newest to oldest by default;
        pass ``oldest_first=True`` to reverse the iteration order.

        Examples
        --------
        Getting the first 100 entries: ::

            async for entry in guild.audit_logs(limit=100):
                print(f'{entry.user} did {entry.action} to {entry.target}')

        Getting entries for a specific action: ::

            async for entry in guild.audit_logs(action=disnake.AuditLogAction.ban):
                print(f'{entry.user} banned {entry.target}')

        Getting entries made by a specific user: ::

            entries = await guild.audit_logs(limit=None, user=guild.me).flatten()
            await channel.send(f'I made {len(entries)} moderation actions.')

        Parameters
        ----------
        limit: Optional[:class:`int`]
            The number of entries to retrieve. If ``None`` retrieve all entries.
        before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve entries before this date or entry.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        after: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve entries after this date or entry.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        user: Optional[:class:`abc.Snowflake`]
            The moderator to filter entries from.
        action: Optional[:class:`AuditLogAction`]
            The action to filter with.
        oldest_first: :class:`bool`
            If set to ``True``, return entries in oldest->newest order. Defaults to ``False``.

            .. versionadded:: 2.9

        Raises
        ------
        Forbidden
            You are not allowed to fetch audit logs
        HTTPException
            An error occurred while fetching the audit logs.

        Yields
        ------
        :class:`AuditLogEntry`
            The audit log entry.
        """
        if user is not None:
            user_id = user.id
        else:
            user_id = None

        return AuditLogIterator(
            self,
            before=before,
            after=after,
            limit=limit,
            user_id=user_id,
            action_type=action.value if action is not None else None,
            oldest_first=oldest_first,
        )

    async def widget(self) -> Widget:
        """|coro|

        Retrieves the widget of the guild.

        .. note::

            The guild must have the widget enabled to get this information.

        Raises
        ------
        Forbidden
            The widget for this guild is disabled.
        HTTPException
            Retrieving the widget failed.

        Returns
        -------
        :class:`Widget`
            The guild's widget.
        """
        data = await self._state.http.get_widget(self.id)

        return Widget(state=self._state, data=data)

    async def widget_settings(self) -> WidgetSettings:
        """|coro|

        Retrieves the widget settings of the guild.

        To edit the widget settings, you may also use :func:`~Guild.edit_widget`.

        .. versionadded:: 2.5

        Raises
        ------
        Forbidden
            You do not have permission to view the widget settings.
        HTTPException
            Retrieving the widget settings failed.

        Returns
        -------
        :class:`WidgetSettings`
            The guild's widget settings.
        """
        data = await self._state.http.get_widget_settings(self.id)
        return WidgetSettings(state=self._state, guild=self, data=data)

    async def edit_widget(
        self,
        *,
        enabled: bool = MISSING,
        channel: Optional[Snowflake] = MISSING,
        reason: Optional[str] = None,
    ) -> WidgetSettings:
        """|coro|

        Edits the widget of the guild.

        You must have :attr:`~Permissions.manage_guild` permission to
        use this.

        .. versionadded:: 2.0

        .. versionchanged:: 2.5

            Returns the new widget settings.

        Parameters
        ----------
        enabled: :class:`bool`
            Whether to enable the widget for the guild.
        channel: Optional[:class:`~disnake.abc.Snowflake`]
            The new widget channel. ``None`` removes the widget channel.
            If set, an invite link for this channel will be generated,
            which allows users to join the guild from the widget.
        reason: Optional[:class:`str`]
            The reason for editing the widget. Shows up on the audit log.

            .. versionadded:: 2.4

        Raises
        ------
        Forbidden
            You do not have permission to edit the widget.
        HTTPException
            Editing the widget failed.

        Returns
        -------
        :class:`WidgetSettings`
            The new widget settings.
        """
        payload = {}
        if channel is not MISSING:
            payload["channel_id"] = None if channel is None else channel.id
        if enabled is not MISSING:
            payload["enabled"] = enabled

        data = await self._state.http.edit_widget(self.id, payload=payload, reason=reason)
        return WidgetSettings(state=self._state, guild=self, data=data)

    def widget_image_url(self, style: WidgetStyle = WidgetStyle.shield) -> str:
        """Returns an URL to the widget's .png image.

        .. versionadded:: 2.5

        Parameters
        ----------
        style: :class:`WidgetStyle`
            The widget style.

        Returns
        -------
        :class:`str`
            The widget image URL.
        """
        return self._state.http.widget_image_url(self.id, style=str(style))

    async def edit_mfa_level(self, mfa_level: MFALevel, *, reason: Optional[str] = None) -> None:
        """|coro|

        Edits the two-factor authentication level of the guild.

        You must be the guild owner to use this.

        .. versionadded:: 2.6

        Parameters
        ----------
        mfa_level: :class:`int`
            The new 2FA level. If set to 0, the guild does not require
            2FA for their administrative members to take
            moderation actions. If set to 1, then 2FA is required.
        reason: Optional[:class:`str`]
            The reason for editing the mfa level. Shows up on the audit log.

        Raises
        ------
        HTTPException
            Editing the 2FA level failed.
        ValueError
            You are not the owner of the guild.
        """
        if isinstance(mfa_level, bool) or not isinstance(mfa_level, int):
            raise TypeError(f"`mfa_level` must be of type int, got {type(mfa_level).__name__}")
        if self.owner_id != self._state.self_id:
            raise ValueError("To edit the 2FA level, you must be the owner of the guild.")
        # return value unused
        await self._state.http.edit_mfa_level(self.id, mfa_level, reason=reason)

    async def chunk(self, *, cache: bool = True) -> Optional[List[Member]]:
        """|coro|

        Returns a :class:`list` of all guild members.

        Requests all members that belong to this guild. In order to use this,
        :meth:`Intents.members` must be enabled.

        This is a websocket operation and can be slow.

        .. versionadded:: 1.5

        Parameters
        ----------
        cache: :class:`bool`
            Whether to cache the members as well.

        Raises
        ------
        ClientException
            The members intent is not enabled.

        Returns
        -------
        Optional[List[:class:`Member`]]
             Returns a list of all the members within the guild.
        """
        if not self._state._intents.members:
            raise ClientException("Intents.members must be enabled to use this.")

        if not self._state.is_guild_evicted(self):
            return await self._state.chunk_guild(self, cache=cache)

    async def query_members(
        self,
        query: Optional[str] = None,
        *,
        limit: int = 5,
        user_ids: Optional[List[int]] = None,
        presences: bool = False,
        cache: bool = True,
    ) -> List[Member]:
        """|coro|

        Request members that belong to this guild whose name starts with
        the query given.

        This is a websocket operation and can be slow.

        See also :func:`search_members`.

        .. versionadded:: 1.3

        Parameters
        ----------
        query: Optional[:class:`str`]
            The string that the names start with.
        limit: :class:`int`
            The maximum number of members to send back. This must be
            a number between 5 and 100.
        presences: :class:`bool`
            Whether to request for presences to be provided. This defaults
            to ``False``.

            .. versionadded:: 1.6

        cache: :class:`bool`
            Whether to cache the members internally. This makes operations
            such as :meth:`get_member` work for those that matched.
        user_ids: Optional[List[:class:`int`]]
            List of user IDs to search for. If the user ID is not in the guild then it won't be returned.

            .. versionadded:: 1.4


        Raises
        ------
        asyncio.TimeoutError
            The query timed out waiting for the members.
        ValueError
            Invalid parameters were passed to the function
        ClientException
            The presences intent is not enabled.

        Returns
        -------
        List[:class:`Member`]
            The list of members that have matched the query.
        """
        if presences and not self._state._intents.presences:
            raise ClientException("Intents.presences must be enabled to use this.")

        if query is None:
            if user_ids is None:
                raise ValueError("Must pass either query or user_ids")

        elif not query:
            raise ValueError("Cannot pass empty query string.")

        elif user_ids is not None:
            raise ValueError("Cannot pass both query and user_ids")

        if user_ids is not None and not user_ids:
            raise ValueError("user_ids must contain at least 1 value")

        limit = min(100, limit or 5)
        return await self._state.query_members(
            self, query=query, limit=limit, user_ids=user_ids, presences=presences, cache=cache
        )

    async def search_members(
        self,
        query: str,
        *,
        limit: int = 1,
        cache: bool = True,
    ):
        """|coro|

        Retrieves members that belong to this guild whose name starts with
        the query given.

        Note that unlike :func:`query_members`, this is not a websocket operation, but an HTTP operation.

        See also :func:`query_members`.

        .. versionadded:: 2.5

        Parameters
        ----------
        query: :class:`str`
            The string that the names start with.
        limit: :class:`int`
            The maximum number of members to send back. This must be
            a number between 1 and 1000.
        cache: :class:`bool`
            Whether to cache the members internally. This makes operations
            such as :meth:`get_member` work for those that matched.

        Raises
        ------
        ValueError
            Invalid parameters were passed to the function

        Returns
        -------
        List[:class:`Member`]
            The list of members that have matched the query.
        """
        if not query:
            raise ValueError("Cannot pass empty query string.")
        if limit < 1:
            raise ValueError("limit must be at least 1")
        limit = min(1000, limit)
        members = await self._state.http.search_guild_members(self.id, query=query, limit=limit)
        resp = []
        for member in members:
            member = Member(state=self._state, data=member, guild=self)
            if cache and member.id not in self._members:
                self._add_member(member)
            resp.append(member)
        return resp

    async def get_or_fetch_members(
        self,
        user_ids: List[int],
        *,
        presences: bool = False,
        cache: bool = True,
    ) -> List[Member]:
        """|coro|

        Tries to get the guild members matching the provided IDs from cache.
        If some of them were not found, the method requests the missing members using websocket operations.
        If ``cache`` kwarg is ``True`` (default value) the missing members will be cached.

        If more than 100 members are missing, several websocket operations are made.

        Websocket operations can be slow, however, this method is cheaper than multiple :meth:`get_or_fetch_member` calls.

        .. versionadded:: 2.4

        Parameters
        ----------
        user_ids: List[:class:`int`]
            List of user IDs to search for. If the user ID is not in the guild then it won't be returned.
        presences: :class:`bool`
            Whether to request for presences to be provided. Defaults to ``False``.
        cache: :class:`bool`
            Whether to cache the missing members internally. This makes operations
            such as :meth:`get_member` work for those that matched.
            It also speeds up this method on repeated calls. Defaults to ``True``.

        Raises
        ------
        asyncio.TimeoutError
            The query timed out waiting for the members.
        ClientException
            The presences intent is not enabled.

        Returns
        -------
        List[:class:`Member`]
            The list of members with the given IDs, if they exist.
        """
        if presences and not self._state._intents.presences:
            raise ClientException("Intents.presences must be enabled to use this.")

        members: List[Member] = []
        unresolved_ids: List[int] = []

        for user_id in user_ids:
            member = self.get_member(user_id)
            if member is None:
                unresolved_ids.append(user_id)
            else:
                members.append(member)

        if not unresolved_ids:
            return members

        if len(unresolved_ids) == 1:
            # fetch_member is cheaper than query_members
            try:
                member = await self.fetch_member(unresolved_ids[0])
                members.append(member)
                if cache:
                    self._add_member(member)
            except HTTPException:
                pass
        else:
            # We have to split the request into several smaller requests
            # because the limit is 100 members per request.
            for i in range(0, len(unresolved_ids), 100):
                limit = min(100, len(unresolved_ids) - i)
                members += await self._state.query_members(
                    self,
                    query=None,
                    limit=limit,
                    user_ids=unresolved_ids[i : i + 100],
                    presences=presences,
                    cache=cache,
                )

        return members

    getch_members = get_or_fetch_members

    async def fetch_voice_regions(self) -> List[VoiceRegion]:
        """|coro|

        Retrieves a list of :class:`VoiceRegion` for this guild.

        .. versionadded:: 2.5

        Raises
        ------
        HTTPException
            Retrieving voice regions failed.
        """
        data = await self._state.http.get_guild_voice_regions(self.id)
        return [VoiceRegion(data=region) for region in data]

    async def change_voice_state(
        self, *, channel: Optional[Snowflake], self_mute: bool = False, self_deaf: bool = False
    ) -> None:
        """|coro|

        Changes client's voice state in the guild.

        .. versionadded:: 1.4

        Parameters
        ----------
        channel: Optional[:class:`VoiceChannel`]
            The channel the client wants to join. Use ``None`` to disconnect.
        self_mute: :class:`bool`
            Whether the client should be self-muted.
        self_deaf: :class:`bool`
            Whether the client should be self-deafened.
        """
        ws = self._state._get_websocket(self.id)
        channel_id = channel.id if channel else None
        await ws.voice_state(self.id, channel_id, self_mute, self_deaf)

    # Application command permissions

    async def bulk_fetch_command_permissions(self) -> List[GuildApplicationCommandPermissions]:
        """|coro|

        Requests a list of :class:`GuildApplicationCommandPermissions` configured for this guild.

        .. versionadded:: 2.1
        """
        return await self._state.bulk_fetch_command_permissions(self.id)

    async def fetch_command_permissions(
        self, command_id: int
    ) -> GuildApplicationCommandPermissions:
        """|coro|

        Retrieves :class:`GuildApplicationCommandPermissions` for a specific command.

        .. versionadded:: 2.1

        Parameters
        ----------
        command_id: :class:`int`
            The ID of the application command, or the application ID to fetch application-wide permissions.

            .. versionchanged:: 2.5
                Can now also fetch application-wide permissions.

        Returns
        -------
        :class:`GuildApplicationCommandPermissions`
            The application command permissions.
        """
        return await self._state.fetch_command_permissions(self.id, command_id)

    @overload
    async def timeout(
        self,
        user: Snowflake,
        *,
        duration: Optional[Union[float, datetime.timedelta]],
        reason: Optional[str] = None,
    ) -> Member:
        ...

    @overload
    async def timeout(
        self,
        user: Snowflake,
        *,
        until: Optional[datetime.datetime],
        reason: Optional[str] = None,
    ) -> Member:
        ...

    async def timeout(
        self,
        user: Snowflake,
        *,
        duration: Optional[Union[float, datetime.timedelta]] = MISSING,
        until: Optional[datetime.datetime] = MISSING,
        reason: Optional[str] = None,
    ) -> Member:
        """|coro|

        Times out the member from the guild; until then, the member will not be able to interact with the guild.

        Exactly one of ``duration`` or ``until`` must be provided. To remove a timeout, set one of the parameters to ``None``.

        The user must meet the :class:`abc.Snowflake` abc.

        You must have the :attr:`~Permissions.moderate_members` permission to do this.

        .. versionadded:: 2.3

        Parameters
        ----------
        user: :class:`abc.Snowflake`
            The member to timeout.
        duration: Optional[Union[:class:`float`, :class:`datetime.timedelta`]]
            The duration (seconds or timedelta) of the member's timeout. Set to ``None`` to remove the timeout.
            Supports up to 28 days in the future.
            May not be used in combination with the ``until`` parameter.
        until: Optional[:class:`datetime.datetime`]
            The expiry date/time of the member's timeout. Set to ``None`` to remove the timeout.
            Supports up to 28 days in the future.
            May not be used in combination with the ``duration`` parameter.
        reason: Optional[:class:`str`]
            The reason for this timeout. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have permissions to timeout this member.
        HTTPException
            Timing out the member failed.

        Returns
        -------
        :class:`Member`
            The newly updated member.
        """
        if not (duration is MISSING) ^ (until is MISSING):
            raise ValueError("Exactly one of `duration` and `until` must be provided")

        payload: Dict[str, Any] = {}

        if duration is not MISSING:
            if duration is None:
                until = None
            elif isinstance(duration, datetime.timedelta):
                until = utils.utcnow() + duration
            else:
                until = utils.utcnow() + datetime.timedelta(seconds=duration)

        # at this point `until` cannot be `MISSING`
        payload["communication_disabled_until"] = utils.isoformat_utc(until)

        data = await self._state.http.edit_member(self.id, user.id, reason=reason, **payload)
        return Member(data=data, guild=self, state=self._state)

    async def fetch_automod_rule(self, rule_id: int, /) -> AutoModRule:
        """|coro|

        Retrieves an auto moderation rules from the guild.
        See also :func:`~Guild.fetch_automod_rules`.

        Requires the :attr:`~Permissions.manage_guild` permission.

        .. versionadded:: 2.6

        Raises
        ------
        Forbidden
            You do not have proper permissions to retrieve auto moderation rules.
        NotFound
            An auto moderation rule with the provided ID does not exist in the guild.
        HTTPException
            Retrieving the rule failed.

        Returns
        -------
        :class:`AutoModRule`
            The auto moderation rule.
        """
        data = await self._state.http.get_auto_moderation_rule(self.id, rule_id)
        return AutoModRule(data=data, guild=self)

    async def fetch_automod_rules(self) -> List[AutoModRule]:
        """|coro|

        Retrieves the guild's auto moderation rules.
        See also :func:`~Guild.fetch_automod_rule`.

        Requires the :attr:`~Permissions.manage_guild` permission.

        .. versionadded:: 2.6

        Raises
        ------
        Forbidden
            You do not have proper permissions to retrieve auto moderation rules.
        NotFound
            The guild does not have any auto moderation rules set up.
        HTTPException
            Retrieving the rules failed.

        Returns
        -------
        List[:class:`AutoModRule`]
            The guild's auto moderation rules.
        """
        data = await self._state.http.get_auto_moderation_rules(self.id)
        return [AutoModRule(data=rule_data, guild=self) for rule_data in data]

    async def create_automod_rule(
        self,
        *,
        name: str,
        event_type: AutoModEventType,
        trigger_type: AutoModTriggerType,
        actions: Sequence[AutoModAction],
        trigger_metadata: Optional[AutoModTriggerMetadata] = None,
        enabled: bool = False,
        exempt_roles: Optional[Sequence[Snowflake]] = None,
        exempt_channels: Optional[Sequence[Snowflake]] = None,
        reason: Optional[str] = None,
    ) -> AutoModRule:
        """|coro|

        Creates a new :class:`AutoModRule` for the guild.

        You must have :attr:`.Permissions.manage_guild` permission to do this.

        The maximum number of rules for each trigger type is limited, see the
        :ddocs:`api docs <resources/auto-moderation#auto-moderation-rule-object-trigger-types>`
        for more details.

        .. versionadded:: 2.6

        .. versionchanged:: 2.9
            Now raises a :exc:`TypeError` if given ``actions`` have an invalid type.

        Parameters
        ----------
        name: :class:`str`
            The rule name.
        event_type: :class:`AutoModEventType`
            The type of events that this rule will be applied to.
        trigger_type: :class:`AutoModTriggerType`
            The type of trigger that determines whether this rule's actions should run for a specific event.
            If set to :attr:`~AutoModTriggerType.keyword`, :attr:`~AutoModTriggerType.keyword_preset`,
            or :attr:`~AutoModTriggerType.mention_spam`, ``trigger_metadata`` must be set accordingly.
            This cannot be changed after creation.
        actions: Sequence[Union[:class:`AutoModBlockMessageAction`, :class:`AutoModSendAlertAction`, :class:`AutoModTimeoutAction`, :class:`AutoModAction`]]
            The list of actions that will execute if a matching event triggered this rule.
            Must contain at least one action.
        trigger_metadata: Optional[:class:`AutoModTriggerMetadata`]
            Additional metadata associated with the trigger type.
        enabled: :class:`bool`
            Whether to enable the rule. Defaults to ``False``.
        exempt_roles: Optional[Sequence[:class:`abc.Snowflake`]]
            The roles that are exempt from this rule, up to 20. By default, no roles are exempt.
        exempt_channels: Optional[Sequence[:class:`abc.Snowflake`]]
            The channels that are exempt from this rule, up to 50. By default, no channels are exempt.
            Can also include categories, in which case all channels inside that category will be exempt.
        reason: Optional[:class:`str`]
            The reason for creating the rule. Shows up on the audit log.

        Raises
        ------
        ValueError
            The specified trigger type requires ``trigger_metadata`` to be set,
            or no actions have been provided.
        TypeError
            The specified ``actions`` are of an invalid type.
        Forbidden
            You do not have proper permissions to create auto moderation rules.
        HTTPException
            Creating the rule failed.

        Returns
        -------
        :class:`AutoModRule`
            The newly created auto moderation rule.
        """
        trigger_type_int = try_enum_to_int(trigger_type)
        if not trigger_metadata and trigger_type_int in (
            AutoModTriggerType.keyword.value,
            AutoModTriggerType.keyword_preset.value,
            AutoModTriggerType.mention_spam.value,
        ):
            raise ValueError("Specified trigger type requires `trigger_metadata` to not be empty")

        if not actions:
            raise ValueError("At least one action must be provided.")
        for action in actions:
            if not isinstance(action, AutoModAction):
                raise TypeError(
                    f"actions must be of type `AutoModAction` (or subtype), not {type(action)!r}"
                )

        data = await self._state.http.create_auto_moderation_rule(
            self.id,
            name=name,
            event_type=try_enum_to_int(event_type),
            trigger_type=trigger_type_int,
            actions=[a.to_dict() for a in actions],
            trigger_metadata=trigger_metadata.to_dict() if trigger_metadata is not None else None,
            enabled=enabled,
            exempt_roles=[e.id for e in exempt_roles] if exempt_roles is not None else None,
            exempt_channels=(
                [e.id for e in exempt_channels] if exempt_channels is not None else None
            ),
            reason=reason,
        )
        return AutoModRule(data=data, guild=self)

    async def onboarding(self) -> Onboarding:
        """|coro|

        Retrieves the guild onboarding data.

        .. versionadded:: 2.9

        Raises
        ------
        HTTPException
            Retrieving the guild onboarding data failed.

        Returns
        -------
        :class:`Onboarding`
            The guild onboarding data.
        """
        data = await self._state.http.get_guild_onboarding(self.id)
        return Onboarding(data=data, guild=self)


class PartialInteractionGuild(Guild):
    """Reimplementation of :class:`Guild` for guilds interactions."""

    def __init__(
        self,
        *,
        state: ConnectionState,
        data: PartialGuildPayload,
        interaction: Interaction,
    ) -> None:
        super().__init__(state=state, data=data)
        # init the fake data
        self._add_role(
            Role(
                state=state,
                guild=self,
                data={"id": self.id, "name": "@everyone"},  # type: ignore
            )
        )
        self._add_channel(interaction.channel)  # type: ignore
        # honestly we cannot set me, because we do not necessarily have a user in the guild

    @property
    def me(self) -> Any:
        return self._state.user


PlaceholderID = NewType("PlaceholderID", int)


class GuildBuilder:
    """A guild builder object, created by :func:`Client.guild_builder`.

    This allows for easier configuration of more complex guild setups,
    abstracting away some of the quirks of the guild creation endpoint.

    .. versionadded:: 2.8

    .. note::
        Many methods of this class return unspecified placeholder IDs
        (called ``PlaceholderID`` below) that can be used to reference the
        created object in other objects, for example referencing a category when
        creating a new text channel, or a role when setting permission overwrites.

    Examples
    --------
    Basic usage:

    .. code-block:: python3

        builder = client.guild_builder("Cat Pics")
        builder.add_text_channel("meow", topic="cat.")
        guild = await builder.create()

    Adding more channels + roles:

    .. code-block:: python3

        builder = client.guild_builder("More Cat Pics")
        builder.add_text_channel("welcome")

        # add roles
        guests = builder.add_role("guests")
        admins = builder.add_role(
            "catmins",
            permissions=Permissions(administrator=True),
            hoist=True,
        )

        # add cat-egory and text channel
        category = builder.add_category("cats!")
        meow_channel = builder.add_text_channel(
            "meow",
            topic="cat.",
            category=category,
            overwrites={guests: PermissionOverwrite(send_messages=False)}
        )

        # set as system channel
        builder.system_channel = meow_channel

        # add hidden voice channel
        builder.add_voice_channel(
            "secret-admin-vc",
            category=category,
            overwrites={builder.everyone: PermissionOverwrite(view_channel=False)}
        )

        # finally, create the guild
        guild = await builder.create()

    Attributes
    ----------
    name: :class:`str`
        The name of the new guild.
    icon: Optional[|resource_type|]
        The icon of the new guild.
    verification_level: Optional[:class:`VerificationLevel`]
        The verification level of the new guild.
    default_notifications: Optional[:class:`NotificationLevel`]
        The default notification level for the new guild.
    explicit_content_filter: Optional[:class:`ContentFilter`]
        The explicit content filter for the new guild.
    afk_channel: Optional[``PlaceholderID``]
        The channel that is used as the AFK channel.
    afk_timeout: Optional[:class:`int`]
        The number of seconds until someone is moved to the AFK channel.
    system_channel: Optional[``PlaceholderID``]
        The channel that is used as the system channel.
    system_channel_flags: Optional[:class:`SystemChannelFlags`]
        The settings to use with the system channel.
    """

    def __init__(self, *, state: ConnectionState, name: str) -> None:
        self._state = state
        self.name: str = name

        # note: the first role corresponds to @everyone
        self._roles: List[CreateGuildPlaceholderRole] = []
        self._channels: List[CreateGuildPlaceholderChannel] = []

        self.icon: Optional[AssetBytes] = None
        self.verification_level: Optional[VerificationLevel] = None
        self.default_notifications: Optional[NotificationLevel] = None
        self.explicit_content_filter: Optional[ContentFilter] = None
        self.afk_channel: Optional[PlaceholderID] = None
        self.afk_timeout: Optional[int] = None
        self.system_channel: Optional[PlaceholderID] = None
        self.system_channel_flags: Optional[SystemChannelFlags] = None

        self._current_id: int = 1

        self._everyone_id: PlaceholderID = self._next_id()

    def _next_id(self) -> PlaceholderID:
        self._current_id = (_id := self._current_id) + 1
        return PlaceholderID(_id)

    def _add_channel(
        self,
        *,
        type: ChannelType,
        name: str,
        overwrites: Dict[PlaceholderID, PermissionOverwrite] = MISSING,
        category: PlaceholderID = MISSING,
        topic: Optional[str] = MISSING,
        slowmode_delay: int = MISSING,
        nsfw: bool = MISSING,
    ) -> Tuple[PlaceholderID, CreateGuildPlaceholderChannel]:
        _id = self._next_id()
        data: CreateGuildPlaceholderChannel = {
            "id": _id,
            "type": try_enum_to_int(type),
            "name": name,
        }

        if overwrites is not MISSING:
            overwrites_data: List[PermissionOverwritePayload] = []
            for target, perm in overwrites.items():
                allow, deny = perm.pair()
                overwrites_data.append(
                    {
                        "allow": str(allow.value),
                        "deny": str(deny.value),
                        "id": target,
                        # can only set overrides for roles here
                        "type": abc._Overwrites.ROLE,
                    }
                )
            data["permission_overwrites"] = overwrites_data

        if category is not MISSING:
            data["parent_id"] = category

        if topic is not MISSING:
            data["topic"] = topic

        if slowmode_delay is not MISSING:
            data["rate_limit_per_user"] = slowmode_delay

        if nsfw is not MISSING:
            data["nsfw"] = nsfw

        self._channels.append(data)
        return _id, data

    @property
    def everyone(self) -> PlaceholderID:
        """``PlaceholderID``: The placeholder ID used for the ``@everyone`` role."""
        return self._everyone_id

    async def create(self) -> Guild:
        """|coro|

        Creates the configured guild.

        Raises
        ------
        NotFound
            The :attr:`.icon` asset couldn't be found.
        HTTPException
            Guild creation failed.
        ValueError
            Invalid icon image format given. Must be PNG or JPG.
        TypeError
            The :attr:`.icon` asset is a lottie sticker (see :func:`Sticker.read <disnake.Sticker.read>`).

        Returns
        -------
        :class:`.Guild`
            The created guild. This is not the same guild that is added to cache.

            .. note::
                Due to API limitations, this returned guild does
                not contain any of the configured channels.
        """
        if self.icon is not None:
            icon_base64 = await utils._assetbytes_to_base64_data(self.icon)
        else:
            icon_base64 = None

        data = await self._state.http.create_guild(
            name=self.name,
            icon=icon_base64,
            roles=self._roles if self._roles else None,
            channels=self._channels if self._channels else None,
            verification_level=try_enum_to_int(self.verification_level),
            default_message_notifications=try_enum_to_int(self.default_notifications),
            explicit_content_filter=try_enum_to_int(self.explicit_content_filter),
            afk_channel=self.afk_channel,
            afk_timeout=self.afk_timeout,
            system_channel=self.system_channel,
            system_channel_flags=try_enum_to_int(self.system_channel_flags),
        )
        return Guild(data=data, state=self._state)

    def update_everyone_role(self, *, permissions: Permissions = MISSING) -> PlaceholderID:
        """Updates attributes of the ``@everyone`` role.

        Parameters
        ----------
        permissions: :class:`Permissions`
            The permissions the role should have.

        Returns
        -------
        ``PlaceholderID``
            The placeholder ID for the ``@everyone`` role.
            Also available as :attr:`everyone`.
        """
        if len(self._roles) == 0:
            self._roles.append({"id": self._everyone_id})
        role = self._roles[0]

        if permissions is not MISSING:
            role["permissions"] = str(permissions.value)

        return self._everyone_id

    def add_role(
        self,
        name: str = MISSING,
        *,
        permissions: Permissions = MISSING,
        color: Union[Colour, int] = MISSING,
        colour: Union[Colour, int] = MISSING,
        hoist: bool = MISSING,
        mentionable: bool = MISSING,
    ) -> PlaceholderID:
        """Adds a role to the guild builder.

        The default (``@everyone``) role can be referenced using :attr:`everyone`
        and configured through :func:`update_everyone_role`.

        Parameters
        ----------
        name: :class:`str`
            The role name. Defaults to 'new role'.
        permissions: :class:`Permissions`
            The permissions the role should have. Defaults to no permissions.
        colour: Union[:class:`Colour`, :class:`int`]
            The colour for the role. Defaults to :meth:`Colour.default`.
            This is aliased to ``color`` as well.
        hoist: :class:`bool`
            Whether the role should be shown separately in the member list.
            Defaults to ``False``.
        mentionable: :class:`bool`
            Whether the role should be mentionable by others.
            Defaults to ``False``.

        Returns
        -------
        ``PlaceholderID``
            A placeholder ID for the created role.
        """
        # always create @everyone role first if not created already
        if len(self._roles) == 0:
            self.update_everyone_role()

        _id = self._next_id()
        data: CreateGuildPlaceholderRole = {"id": _id}

        if name is not MISSING:
            data["name"] = name

        if permissions is not MISSING:
            data["permissions"] = str(permissions.value)
        else:
            data["permissions"] = "0"

        actual_colour = colour or color or Colour.default()
        if isinstance(actual_colour, int):
            data["color"] = actual_colour
        else:
            data["color"] = actual_colour.value

        if hoist is not MISSING:
            data["hoist"] = hoist

        if mentionable is not MISSING:
            data["mentionable"] = mentionable

        self._roles.append(data)
        return _id

    def add_category(
        self,
        name: str,
        *,
        overwrites: Dict[PlaceholderID, PermissionOverwrite] = MISSING,
    ) -> PlaceholderID:
        """Adds a category channel to the guild builder.

        There is an alias for this named ``add_category_channel``.

        Parameters
        ----------
        name: :class:`str`
            The category's name.
        overwrites: Dict[``PlaceholderID``, :class:`PermissionOverwrite`]
            A :class:`dict` of roles to :class:`PermissionOverwrite`\\s which can be synced to channels.

        Returns
        -------
        ``PlaceholderID``
            A placeholder ID for the created category.
        """
        _id, _ = self._add_channel(type=ChannelType.category, name=name, overwrites=overwrites)
        return _id

    add_category_channel = add_category

    def add_text_channel(
        self,
        name: str,
        *,
        overwrites: Dict[PlaceholderID, PermissionOverwrite] = MISSING,
        category: PlaceholderID = MISSING,
        topic: Optional[str] = MISSING,
        slowmode_delay: int = MISSING,
        nsfw: bool = MISSING,
        default_auto_archive_duration: AnyThreadArchiveDuration = MISSING,
    ) -> PlaceholderID:
        """Adds a text channel to the guild builder.

        Parameters
        ----------
        name: :class:`str`
            The channel's name.
        overwrites: Dict[``PlaceholderID``, :class:`PermissionOverwrite`]
            A :class:`dict` of roles to :class:`PermissionOverwrite`\\s to apply to the channel.
        category: ``PlaceholderID``
            The category to place the new channel under.

            .. warning::
                Unlike :func:`Guild.create_text_channel`, the parent category's
                permissions will *not* be synced to this new channel by default.

        topic: Optional[:class:`str`]
            The channel's topic.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for users in this channel, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
            If not provided, slowmode is disabled.
        nsfw: :class:`bool`
            Whether to mark the channel as NSFW.
        default_auto_archive_duration: Union[:class:`int`, :class:`ThreadArchiveDuration`]
            The default auto archive duration in minutes for threads created in this channel.
            Must be one of ``60``, ``1440``, ``4320``, or ``10080``.

        Returns
        -------
        ``PlaceholderID``
            A placeholder ID for the created text channel.
        """
        _id, data = self._add_channel(
            type=ChannelType.text,
            name=name,
            overwrites=overwrites,
            category=category,
            topic=topic,
            slowmode_delay=slowmode_delay,
            nsfw=nsfw,
        )

        if default_auto_archive_duration is not MISSING:
            data["default_auto_archive_duration"] = cast(
                "ThreadArchiveDurationLiteral", try_enum_to_int(default_auto_archive_duration)
            )

        return _id

    def add_voice_channel(
        self,
        name: str,
        *,
        overwrites: Dict[PlaceholderID, PermissionOverwrite] = MISSING,
        category: PlaceholderID = MISSING,
        slowmode_delay: int = MISSING,
        nsfw: bool = MISSING,
        bitrate: int = MISSING,
        user_limit: int = MISSING,
        rtc_region: Optional[Union[str, VoiceRegion]] = MISSING,
        video_quality_mode: VideoQualityMode = MISSING,
    ) -> PlaceholderID:
        """Adds a voice channel to the guild builder.

        Parameters
        ----------
        name: :class:`str`
            The channel's name.
        overwrites: Dict[``PlaceholderID``, :class:`PermissionOverwrite`]
            A :class:`dict` of roles to :class:`PermissionOverwrite`\\s to apply to the channel.
        category: ``PlaceholderID``
            The category to place the new channel under.

            .. warning::
                Unlike :func:`Guild.create_voice_channel`, the parent category's
                permissions will *not* be synced to this new channel by default.

        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for users in this channel, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
            If not provided, slowmode is disabled.
        nsfw: :class:`bool`
            Whether to mark the channel as NSFW.
        bitrate: :class:`int`
            The channel's preferred audio bitrate in bits per second.
        user_limit: :class:`int`
            The channel's limit for number of members that can be in a voice channel.
        rtc_region: Optional[Union[:class:`str`, :class:`VoiceRegion`]]
            The region for the voice channel's voice communication.
            A value of ``None`` indicates automatic voice region detection.
        video_quality_mode: :class:`VideoQualityMode`
            The camera video quality for the voice channel's participants.

        Returns
        -------
        ``PlaceholderID``
            A placeholder ID for the created voice channel.
        """
        _id, data = self._add_channel(
            type=ChannelType.voice,
            name=name,
            overwrites=overwrites,
            category=category,
            slowmode_delay=slowmode_delay,
            nsfw=nsfw,
        )

        if bitrate is not MISSING:
            data["bitrate"] = bitrate

        if user_limit is not MISSING:
            data["user_limit"] = user_limit

        if rtc_region is not MISSING:
            data["rtc_region"] = None if rtc_region is None else str(rtc_region)

        if video_quality_mode is not MISSING:
            data["video_quality_mode"] = try_enum_to_int(video_quality_mode)

        return _id
