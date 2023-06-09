# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Generator,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from . import abc, enums, flags, utils
from .app_commands import ApplicationCommandPermissions
from .asset import Asset
from .automod import AutoModAction, AutoModTriggerMetadata, _automod_action_factory
from .colour import Colour
from .invite import Invite
from .mixins import Hashable
from .object import Object
from .onboarding import OnboardingPrompt, OnboardingPromptOption
from .partial_emoji import PartialEmoji
from .permissions import PermissionOverwrite, Permissions
from .threads import ForumTag, Thread

__all__ = (
    "AuditLogDiff",
    "AuditLogChanges",
    "AuditLogEntry",
)


if TYPE_CHECKING:
    import datetime

    from .app_commands import APIApplicationCommand
    from .automod import AutoModRule
    from .emoji import Emoji
    from .guild import Guild
    from .guild_scheduled_event import GuildScheduledEvent
    from .integrations import PartialIntegration
    from .member import Member
    from .role import Role
    from .stage_instance import StageInstance
    from .sticker import GuildSticker
    from .types.audit_log import (
        AuditLogChange as AuditLogChangePayload,
        AuditLogEntry as AuditLogEntryPayload,
        _AuditLogChange_ApplicationCommandPermissions as AuditLogChangeAppCmdPermsPayload,
    )
    from .types.automod import (
        AutoModAction as AutoModActionPayload,
        AutoModTriggerMetadata as AutoModTriggerMetadataPayload,
    )
    from .types.channel import (
        DefaultReaction as DefaultReactionPayload,
        PermissionOverwrite as PermissionOverwritePayload,
    )
    from .types.onboarding import (
        OnboardingPrompt as OnboardingPromptPayload,
        OnboardingPromptOption as OnboardingPromptOptionPayload,
    )
    from .types.role import Role as RolePayload
    from .types.snowflake import Snowflake
    from .types.threads import ForumTag as ForumTagPayload
    from .user import User
    from .webhook import Webhook


def _transform_permissions(entry: AuditLogEntry, data: str) -> Permissions:
    return Permissions(int(data))


def _transform_color(entry: AuditLogEntry, data: int) -> Colour:
    return Colour(data)


def _transform_snowflake(entry: AuditLogEntry, data: Snowflake) -> int:
    return int(data)


def _transform_channel(
    entry: AuditLogEntry, data: Optional[Snowflake]
) -> Optional[Union[abc.GuildChannel, Object]]:
    if data is None:
        return None
    channel = entry.guild.get_channel(int(data))
    return channel or Object(id=data)


def _transform_role(
    entry: AuditLogEntry, data: Optional[Snowflake]
) -> Optional[Union[Role, Object]]:
    if data is None:
        return None
    role = entry.guild.get_role(int(data))
    return role or Object(id=data)


def _transform_member_id(
    entry: AuditLogEntry, data: Optional[Snowflake]
) -> Union[Member, User, Object, None]:
    if data is None:
        return None
    return entry._get_member(int(data))


def _transform_guild_id(entry: AuditLogEntry, data: Optional[Snowflake]) -> Optional[Guild]:
    if data is None:
        return None
    return entry._state._get_guild(int(data))


def _transform_overwrites(
    entry: AuditLogEntry, data: List[PermissionOverwritePayload]
) -> List[Tuple[Object, PermissionOverwrite]]:
    overwrites = []
    for elem in data:
        allow = Permissions(int(elem["allow"]))
        deny = Permissions(int(elem["deny"]))
        ow = PermissionOverwrite.from_pair(allow, deny)

        ow_type = elem["type"]
        ow_id = int(elem["id"])
        target = None
        if ow_type == 0:
            target = entry.guild.get_role(ow_id)
        elif ow_type == 1:
            target = entry._get_member(ow_id)

        if target is None:
            target = Object(id=ow_id)

        overwrites.append((target, ow))

    return overwrites


def _transform_icon(entry: AuditLogEntry, data: Optional[str]) -> Optional[Asset]:
    if data is None:
        return None
    if entry.action.name.startswith("role_"):
        return Asset._from_role_icon(entry._state, entry._target_id, data)  # type: ignore
    return Asset._from_guild_icon(entry._state, entry.guild.id, data)


def _transform_avatar(entry: AuditLogEntry, data: Optional[str]) -> Optional[Asset]:
    if data is None:
        return None
    return Asset._from_avatar(entry._state, entry._target_id, data)  # type: ignore


def _guild_hash_transformer(path: str) -> Callable[[AuditLogEntry, Optional[str]], Optional[Asset]]:
    def _transform(entry: AuditLogEntry, data: Optional[str]) -> Optional[Asset]:
        if data is None:
            return None
        return Asset._from_guild_image(entry._state, entry.guild.id, data, path=path)

    return _transform


def _transform_tag(entry: AuditLogEntry, data: Optional[ForumTagPayload]) -> Optional[ForumTag]:
    if data is None:
        return None
    return ForumTag._from_data(data=data, state=entry._state)


def _transform_tag_id(
    entry: AuditLogEntry, data: Optional[str]
) -> Optional[Union[ForumTag, Object]]:
    if data is None:
        return None

    # cyclic imports
    from .channel import ForumChannel

    tag: Optional[ForumTag] = None
    tag_id = int(data)
    thread = entry.target
    # try thread parent first
    if isinstance(thread, Thread) and isinstance(thread.parent, ForumChannel):
        tag = thread.parent.get_tag(tag_id)
    else:
        # if not found (possibly deleted thread), search all forum channels
        for forum in entry.guild.forum_channels:
            if tag := forum.get_tag(tag_id):
                break

    return tag or Object(id=tag_id)


T = TypeVar("T")
EnumT = TypeVar("EnumT", bound=enums.Enum)
FlagsT = TypeVar("FlagsT", bound=flags.BaseFlags)


def _enum_transformer(enum: Type[EnumT]) -> Callable[[AuditLogEntry, int], EnumT]:
    def _transform(entry: AuditLogEntry, data: int) -> EnumT:
        return enums.try_enum(enum, data)

    return _transform


def _flags_transformer(
    flags_type: Type[FlagsT],
) -> Callable[[AuditLogEntry, Optional[int]], Optional[FlagsT]]:
    def _transform(entry: AuditLogEntry, data: Optional[int]) -> Optional[FlagsT]:
        return flags_type._from_value(data) if data is not None else None

    return _transform


def _list_transformer(
    func: Callable[[AuditLogEntry, Any], T]
) -> Callable[[AuditLogEntry, Any], List[T]]:
    def _transform(entry: AuditLogEntry, data: Any) -> List[T]:
        if not data:
            return []
        return [func(entry, value) for value in data if value is not None]

    return _transform


def _transform_type(
    entry: AuditLogEntry, data: Any
) -> Union[
    enums.ChannelType, enums.StickerType, enums.WebhookType, enums.OnboardingPromptType, str, int
]:
    action_name = entry.action.name
    if action_name.startswith("sticker_"):
        return enums.try_enum(enums.StickerType, data)
    elif action_name.startswith("webhook_"):
        return enums.try_enum(enums.WebhookType, data)
    elif action_name.startswith("integration_") or action_name.startswith("overwrite_"):
        # integration: str, overwrite: int
        return data
    elif action_name.startswith("onboarding_prompt_"):
        return enums.try_enum(enums.OnboardingPromptType, data)
    else:
        return enums.try_enum(enums.ChannelType, data)


def _transform_datetime(entry: AuditLogEntry, data: Optional[str]) -> Optional[datetime.datetime]:
    return utils.parse_time(data)


def _transform_privacy_level(
    entry: AuditLogEntry, data: int
) -> Optional[Union[enums.StagePrivacyLevel, enums.GuildScheduledEventPrivacyLevel]]:
    if data is None:
        return None
    if entry.action.target_type == "guild_scheduled_event":
        return enums.try_enum(enums.GuildScheduledEventPrivacyLevel, data)
    return enums.try_enum(enums.StagePrivacyLevel, data)


def _transform_guild_scheduled_event_image(
    entry: AuditLogEntry, data: Optional[str]
) -> Optional[Asset]:
    if data is None:
        return None
    return Asset._from_guild_scheduled_event_image(entry._state, entry._target_id, data)  # type: ignore


def _transform_automod_action(
    entry: AuditLogEntry, data: Optional[AutoModActionPayload]
) -> Optional[AutoModAction]:
    if data is None:
        return None
    return _automod_action_factory(data)


def _transform_automod_trigger_metadata(
    entry: AuditLogEntry, data: Optional[AutoModTriggerMetadataPayload]
) -> Optional[AutoModTriggerMetadata]:
    if data is None:
        return None
    return AutoModTriggerMetadata._from_dict(data)


def _transform_default_reaction(
    entry: AuditLogEntry, data: Optional[DefaultReactionPayload]
) -> Optional[Union[Emoji, PartialEmoji]]:
    if data is None:
        return None
    return entry._state._get_emoji_from_fields(
        name=data.get("emoji_name"),
        id=utils._get_as_snowflake(data, "emoji_id"),
    )


def _transform_onboarding_prompt_option(
    entry: AuditLogEntry, data: Optional[OnboardingPromptOptionPayload]
) -> Optional[OnboardingPromptOption]:
    if data is None:
        return None

    return OnboardingPromptOption(data=data, guild=entry.guild)


def _transform_onboarding_prompt(
    entry: AuditLogEntry, data: Optional[OnboardingPromptPayload]
) -> Optional[OnboardingPrompt]:
    if data is None:
        return None

    return OnboardingPrompt(data=data, guild=entry.guild)


class AuditLogDiff:
    def __len__(self) -> int:
        return len(self.__dict__)

    def __iter__(self) -> Generator[Tuple[str, Any], None, None]:
        yield from self.__dict__.items()

    def __repr__(self) -> str:
        values = " ".join(f"{k!s}={v!r}" for k, v in self.__dict__.items())
        return f"<AuditLogDiff {values}>"

    if TYPE_CHECKING:

        def __getattr__(self, item: str) -> Any:
            ...

        def __setattr__(self, key: str, value: Any) -> Any:
            ...


Transformer = Callable[["AuditLogEntry", Any], Any]


class AuditLogChanges:
    # fmt: off
    TRANSFORMERS: ClassVar[Dict[str, Tuple[Optional[str], Optional[Transformer]]]] = {
        "verification_level":                 (None, _enum_transformer(enums.VerificationLevel)),
        "explicit_content_filter":            (None, _enum_transformer(enums.ContentFilter)),
        "allow":                              (None, _transform_permissions),
        "deny":                               (None, _transform_permissions),
        "permissions":                        (None, _transform_permissions),
        "id":                                 (None, _transform_snowflake),
        "application_id":                     (None, _transform_snowflake),
        "color":                              ("colour", _transform_color),
        "owner_id":                           ("owner", _transform_member_id),
        "inviter_id":                         ("inviter", _transform_member_id),
        "channel_id":                         ("channel", _transform_channel),
        "afk_channel_id":                     ("afk_channel", _transform_channel),
        "system_channel_id":                  ("system_channel", _transform_channel),
        "widget_channel_id":                  ("widget_channel", _transform_channel),
        "rules_channel_id":                   ("rules_channel", _transform_channel),
        "public_updates_channel_id":          ("public_updates_channel", _transform_channel),
        "permission_overwrites":              ("overwrites", _transform_overwrites),
        "splash_hash":                        ("splash", _guild_hash_transformer("splashes")),
        "banner_hash":                        ("banner", _guild_hash_transformer("banners")),
        "discovery_splash_hash":              ("discovery_splash", _guild_hash_transformer("discovery-splashes")),
        "icon_hash":                          ("icon", _transform_icon),
        "avatar_hash":                        ("avatar", _transform_avatar),
        "rate_limit_per_user":                ("slowmode_delay", None),
        "default_thread_rate_limit_per_user": ("default_thread_slowmode_delay", None),
        "guild_id":                           ("guild", _transform_guild_id),
        "tags":                               ("emoji", None),
        "unicode_emoji":                      ("emoji", None),
        "default_message_notifications":      ("default_notifications", _enum_transformer(enums.NotificationLevel)),
        "communication_disabled_until":       ("timeout", _transform_datetime),
        "image_hash":                         ("image", _transform_guild_scheduled_event_image),
        "video_quality_mode":                 (None, _enum_transformer(enums.VideoQualityMode)),
        "preferred_locale":                   (None, _enum_transformer(enums.Locale)),
        "privacy_level":                      (None, _transform_privacy_level),
        "format_type":                        (None, _enum_transformer(enums.StickerFormatType)),
        "entity_type":                        (None, _enum_transformer(enums.GuildScheduledEventEntityType)),
        "status":                             (None, _enum_transformer(enums.GuildScheduledEventStatus)),
        "type":                               (None, _transform_type),
        "flags":                              (None, _flags_transformer(flags.ChannelFlags)),
        "system_channel_flags":               (None, _flags_transformer(flags.SystemChannelFlags)),
        "trigger_type":                       (None, _enum_transformer(enums.AutoModTriggerType)),
        "event_type":                         (None, _enum_transformer(enums.AutoModEventType)),
        "actions":                            (None, _list_transformer(_transform_automod_action)),
        "trigger_metadata":                   (None, _transform_automod_trigger_metadata),
        "exempt_roles":                       (None, _list_transformer(_transform_role)),
        "exempt_channels":                    (None, _list_transformer(_transform_channel)),
        "applied_tags":                       (None, _list_transformer(_transform_tag_id)),
        "available_tags":                     (None, _list_transformer(_transform_tag)),
        "default_reaction_emoji":             ("default_reaction", _transform_default_reaction),
        "default_sort_order":                 (None, _enum_transformer(enums.ThreadSortOrder)),
        "options":                            (None, _list_transformer(_transform_onboarding_prompt_option)),
        "prompts":                            (None, _list_transformer(_transform_onboarding_prompt)),
        "default_channel_ids":                ("default_channels", _list_transformer(_transform_channel)),
    }
    # fmt: on

    def __init__(self, entry: AuditLogEntry, data: List[AuditLogChangePayload]) -> None:
        self.before = AuditLogDiff()
        self.after = AuditLogDiff()

        for elem in data:
            attr = elem["key"]

            # special cases for role add/remove
            if attr == "$add":
                self._handle_role(self.before, self.after, entry, elem["new_value"])  # type: ignore
                continue
            elif attr == "$remove":
                self._handle_role(self.after, self.before, entry, elem["new_value"])  # type: ignore
                continue

            # special case for application command permissions update
            if entry.action == enums.AuditLogAction.application_command_permission_update:
                self._handle_command_permissions(
                    entry, cast("AuditLogChangeAppCmdPermsPayload", elem)
                )
                continue

            transformer: Optional[Transformer]

            try:
                key, transformer = self.TRANSFORMERS[attr]
            except (ValueError, KeyError):
                transformer = None
            else:
                if key:
                    attr = key

            try:
                before = elem["old_value"]
            except KeyError:
                before = None
            else:
                if transformer:
                    before = transformer(entry, before)

            setattr(self.before, attr, before)

            try:
                after = elem["new_value"]
            except KeyError:
                after = None
            else:
                if transformer:
                    after = transformer(entry, after)

            setattr(self.after, attr, after)

        # add an alias
        if hasattr(self.after, "colour"):
            self.after.color = self.after.colour
            self.before.color = self.before.colour
        if hasattr(self.after, "expire_behavior"):
            self.after.expire_behaviour = self.after.expire_behavior
            self.before.expire_behaviour = self.before.expire_behavior

    def __repr__(self) -> str:
        return f"<AuditLogChanges before={self.before!r} after={self.after!r}>"

    def _handle_role(
        self,
        first: AuditLogDiff,
        second: AuditLogDiff,
        entry: AuditLogEntry,
        elem: List[RolePayload],
    ) -> None:
        if not hasattr(first, "roles"):
            first.roles = []

        data = []
        g: Guild = entry.guild

        for e in elem:
            role_id = int(e["id"])
            role = g.get_role(role_id)

            if role is None:
                role = Object(id=role_id)
                role.name = e["name"]  # type: ignore

            data.append(role)

        second.roles = data

    def _handle_command_permissions(
        self,
        entry: AuditLogEntry,
        data: AuditLogChangeAppCmdPermsPayload,
    ) -> None:
        guild_id = entry.guild.id
        entity_id = int(data["key"])

        if not hasattr(self.before, "command_permissions"):
            self.before.command_permissions = {}
        if (old := data.get("old_value")) is not None:
            self.before.command_permissions[entity_id] = ApplicationCommandPermissions(
                data=old, guild_id=guild_id
            )

        if not hasattr(self.after, "command_permissions"):
            self.after.command_permissions = {}
        if (new := data.get("new_value")) is not None:
            self.after.command_permissions[entity_id] = ApplicationCommandPermissions(
                data=new, guild_id=guild_id
            )


class _AuditLogProxyMemberPrune:
    delete_member_days: int
    members_removed: int


class _AuditLogProxyMemberMoveOrMessageDelete:
    channel: abc.GuildChannel
    count: int


class _AuditLogProxyMemberDisconnect:
    count: int


class _AuditLogProxyPinAction:
    channel: abc.GuildChannel
    message_id: int


class _AuditLogProxyStageInstanceAction:
    channel: abc.GuildChannel


class _AuditLogProxyAutoModBlockMessage:
    channel: abc.GuildChannel
    rule_name: str
    rule_trigger_type: enums.AutoModTriggerType


class AuditLogEntry(Hashable):
    """Represents an Audit Log entry.

    You retrieve these via :meth:`Guild.audit_logs`.

    .. container:: operations

        .. describe:: x == y

            Checks if two entries are equal.

        .. describe:: x != y

            Checks if two entries are not equal.

        .. describe:: hash(x)

            Returns the entry's hash.

    .. versionchanged:: 1.7
        Audit log entries are now comparable and hashable.

    .. versionchanged:: 2.8
        :attr:`user` can return :class:`Object` if the user is not found.

    Attributes
    ----------
    action: :class:`AuditLogAction`
        The action that was done.
    user: Optional[Union[:class:`Member`, :class:`User`, :class:`Object`]]
        The user who initiated this action. Usually :class:`Member`\\, unless gone
        then it's a :class:`User`.
    id: :class:`int`
        The entry ID.
    target: Any
        The target that got changed. The exact type of this depends on
        the action being done.
    extra: Any
        Extra information that this entry has that might be useful.
        For most actions, this is ``None``. However in some cases it
        contains extra information. See :class:`AuditLogAction` for
        which actions have this field filled out.
    reason: Optional[:class:`str`]
        The reason this action was done.
    """

    def __init__(
        self,
        *,
        data: AuditLogEntryPayload,
        guild: Guild,
        application_commands: Mapping[int, APIApplicationCommand],
        automod_rules: Mapping[int, AutoModRule],
        guild_scheduled_events: Mapping[int, GuildScheduledEvent],
        integrations: Mapping[int, PartialIntegration],
        threads: Mapping[int, Thread],
        users: Mapping[int, User],
        webhooks: Mapping[int, Webhook],
    ) -> None:
        self._state = guild._state
        self.guild = guild

        self._application_commands = application_commands
        self._automod_rules = automod_rules
        self._guild_scheduled_events = guild_scheduled_events
        self._integrations = integrations
        self._threads = threads
        self._users = users
        self._webhooks = webhooks

        self._from_data(data)

    def _from_data(self, data: AuditLogEntryPayload) -> None:
        self.action = enums.try_enum(enums.AuditLogAction, data["action_type"])
        self.id = int(data["id"])

        # this key is technically not usually present
        self.reason = data.get("reason")
        self.extra = extra = data.get("options")

        if isinstance(self.action, enums.AuditLogAction) and extra:
            if self.action is enums.AuditLogAction.member_prune:
                # member prune has two keys with useful information
                self.extra = type(
                    "_AuditLogProxy", (), {k: int(v) for k, v in extra.items()}  # type: ignore
                )()
            elif (
                self.action is enums.AuditLogAction.member_move
                or self.action is enums.AuditLogAction.message_delete
            ):
                elems = {
                    "count": int(extra["count"]),
                    "channel": self._get_channel(utils._get_as_snowflake(extra, "channel_id")),
                }
                self.extra = type("_AuditLogProxy", (), elems)()
            elif self.action is enums.AuditLogAction.member_disconnect:
                # The member disconnect action has a dict with some information
                elems = {
                    "count": int(extra["count"]),
                }
                self.extra = type("_AuditLogProxy", (), elems)()
            elif self.action.name.endswith("pin"):
                # the pin actions have a dict with some information
                elems = {
                    "channel": self._get_channel(utils._get_as_snowflake(extra, "channel_id")),
                    "message_id": int(extra["message_id"]),
                }
                self.extra = type("_AuditLogProxy", (), elems)()
            elif self.action.name.startswith("overwrite_"):
                # the overwrite_ actions have a dict with some information
                instance_id = int(extra["id"])
                the_type = extra.get("type")
                if the_type == "1":
                    self.extra = self._get_member(instance_id)
                elif the_type == "0":
                    role = self.guild.get_role(instance_id)
                    if role is None:
                        role = Object(id=instance_id)
                        role.name = extra.get("role_name")  # type: ignore
                    self.extra = role
            elif self.action.name.startswith("stage_instance"):
                elems = {
                    "channel": self._get_channel(utils._get_as_snowflake(extra, "channel_id")),
                }
                self.extra = type("_AuditLogProxy", (), elems)()
            elif self.action is enums.AuditLogAction.application_command_permission_update:
                app_id = int(extra["application_id"])
                elems = {
                    "integration": self._get_integration_by_application_id(app_id) or Object(app_id)
                }
                self.extra = type("_AuditLogProxy", (), elems)()
            elif self.action in (
                enums.AuditLogAction.automod_block_message,
                enums.AuditLogAction.automod_send_alert_message,
                enums.AuditLogAction.automod_timeout,
            ):
                elems = {
                    "channel": (self._get_channel(utils._get_as_snowflake(extra, "channel_id"))),
                    "rule_name": extra["auto_moderation_rule_name"],
                    "rule_trigger_type": enums.try_enum(
                        enums.AutoModTriggerType,
                        int(extra["auto_moderation_rule_trigger_type"]),
                    ),
                }
                self.extra = type("_AuditLogProxy", (), elems)()

        self.extra: Any
        # actually this but there's no reason to annoy users with this:
        # Union[
        #     _AuditLogProxyMemberPrune,
        #     _AuditLogProxyMemberMoveOrMessageDelete,
        #     _AuditLogProxyMemberDisconnect,
        #     _AuditLogProxyPinAction,
        #     _AuditLogProxyStageInstanceAction,
        #     _AuditLogProxyAutoModBlockMessage,
        #     Member, User, None,
        #     Role,
        # ]

        # this key is not present when the above is present, typically.
        # It's a list of { new_value: a, old_value: b, key: c }
        # where new_value and old_value are not guaranteed to be there depending
        # on the action type, so let's just fetch it for now and only turn it
        # into meaningful data when requested
        self._changes = data.get("changes", [])

        self.user = self._get_member(utils._get_as_snowflake(data, "user_id"))
        self._target_id = utils._get_as_snowflake(data, "target_id")

    def _get_member(self, user_id: Optional[int]) -> Union[Member, User, Object, None]:
        if not user_id:
            return None
        return self.guild.get_member(user_id) or self._users.get(user_id) or Object(id=user_id)

    def _get_channel(self, channel_id: Optional[int]) -> Union[abc.GuildChannel, Object, None]:
        if not channel_id:
            return None
        return self.guild.get_channel(channel_id) or Object(channel_id)

    def _get_integration_by_application_id(
        self, application_id: int
    ) -> Optional[PartialIntegration]:
        if not application_id:
            return None

        for integration in self._integrations.values():
            if integration.application_id == application_id:
                return integration
        return None

    def __repr__(self) -> str:
        return f"<AuditLogEntry id={self.id} action={self.action} user={self.user!r}>"

    @utils.cached_property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the entry's creation time in UTC."""
        return utils.snowflake_time(self.id)

    @utils.cached_property
    def target(
        self,
    ) -> Union[
        Guild,
        abc.GuildChannel,
        Member,
        User,
        Role,
        Invite,
        Webhook,
        Emoji,
        PartialIntegration,
        StageInstance,
        GuildSticker,
        Thread,
        GuildScheduledEvent,
        APIApplicationCommand,
        AutoModRule,
        Object,
        None,
    ]:
        if self.action.target_type is None:
            return Object(id=self._target_id) if self._target_id else None

        try:
            converter = getattr(self, f"_convert_target_{self.action.target_type}")
        except AttributeError:
            return Object(id=self._target_id) if self._target_id else None
        else:
            return converter(self._target_id)

    @utils.cached_property
    def category(self) -> Optional[enums.AuditLogActionCategory]:
        """Optional[:class:`AuditLogActionCategory`]: The category of the action, if applicable."""
        return self.action.category

    @utils.cached_property
    def changes(self) -> AuditLogChanges:
        """:class:`AuditLogChanges`: The list of changes this entry has."""
        obj = AuditLogChanges(self, self._changes)
        del self._changes
        return obj

    @utils.cached_property
    def before(self) -> AuditLogDiff:
        """:class:`AuditLogDiff`: The target's prior state."""
        return self.changes.before

    @utils.cached_property
    def after(self) -> AuditLogDiff:
        """:class:`AuditLogDiff`: The target's subsequent state."""
        return self.changes.after

    def _convert_target_guild(self, target_id: int) -> Guild:
        return self.guild

    def _convert_target_channel(self, target_id: int) -> Union[abc.GuildChannel, Object]:
        return self.guild.get_channel(target_id) or Object(id=target_id)

    def _convert_target_user(self, target_id: int) -> Union[Member, User, Object, None]:
        return self._get_member(target_id)

    def _convert_target_role(self, target_id: int) -> Union[Role, Object]:
        return self.guild.get_role(target_id) or Object(id=target_id)

    def _convert_target_invite(self, target_id: int) -> Invite:
        # invites have target_id set to null
        # so figure out which change has the full invite data
        changeset = self.before if self.action is enums.AuditLogAction.invite_delete else self.after

        fake_payload = {
            "max_age": changeset.max_age,
            "max_uses": changeset.max_uses,
            "code": changeset.code,
            "temporary": changeset.temporary,
            "uses": changeset.uses,
        }

        obj = Invite(state=self._state, data=fake_payload, guild=self.guild, channel=changeset.channel)  # type: ignore
        try:
            obj.inviter = changeset.inviter
        except AttributeError:
            pass
        return obj

    def _convert_target_webhook(self, target_id: int) -> Union[Webhook, Object]:
        return self._webhooks.get(target_id) or Object(id=target_id)

    def _convert_target_emoji(self, target_id: int) -> Union[Emoji, Object]:
        return self._state.get_emoji(target_id) or Object(id=target_id)

    def _convert_target_message(self, target_id: int) -> Union[Member, User, Object, None]:
        return self._get_member(target_id)

    def _convert_target_integration(self, target_id: int) -> Union[PartialIntegration, Object]:
        return self._integrations.get(target_id) or Object(id=target_id)

    def _convert_target_stage_instance(self, target_id: int) -> Union[StageInstance, Object]:
        return self.guild.get_stage_instance(target_id) or Object(id=target_id)

    def _convert_target_sticker(self, target_id: int) -> Union[GuildSticker, Object]:
        return self._state.get_sticker(target_id) or Object(id=target_id)

    def _convert_target_thread(self, target_id: int) -> Union[Thread, Object]:
        return (
            self.guild.get_thread(target_id) or self._threads.get(target_id) or Object(id=target_id)
        )

    def _convert_target_guild_scheduled_event(
        self, target_id: int
    ) -> Union[GuildScheduledEvent, Object]:
        return (
            self.guild.get_scheduled_event(target_id)
            or self._guild_scheduled_events.get(target_id)
            or Object(id=target_id)
        )

    def _convert_target_application_command_or_integration(
        self, target_id: int
    ) -> Union[APIApplicationCommand, PartialIntegration, Object]:
        # try application command
        if target := (
            self._state._get_guild_application_command(self.guild.id, target_id)
            or self._state._get_global_application_command(target_id)
            or self._application_commands.get(target_id)
        ):
            return target

        # permissions may also be changed for the entire application,
        # however the target ID is the application ID, not the integration ID
        if target := self._get_integration_by_application_id(target_id):
            return target

        # fall back to object
        return Object(id=target_id)

    def _convert_target_automod_rule(self, target_id: int) -> Union[AutoModRule, Object]:
        return self._automod_rules.get(target_id) or Object(id=target_id)

    def _convert_target_onboarding_prompt(self, target_id: int) -> Object:
        return Object(id=target_id)
