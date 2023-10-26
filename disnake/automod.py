# SPDX-License-Identifier: MIT

from __future__ import annotations

import datetime
from typing import (
    TYPE_CHECKING,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Optional,
    Sequence,
    Type,
    Union,
    overload,
)

from .enums import (
    AutoModActionType,
    AutoModEventType,
    AutoModTriggerType,
    enum_if_int,
    try_enum,
    try_enum_to_int,
)
from .flags import AutoModKeywordPresets
from .utils import MISSING, _get_as_snowflake, snowflake_time

if TYPE_CHECKING:
    from typing_extensions import Self

    from .abc import Snowflake
    from .guild import Guild, GuildChannel
    from .member import Member
    from .message import Message
    from .role import Role
    from .threads import Thread
    from .types.automod import (
        AutoModAction as AutoModActionPayload,
        AutoModActionMetadata,
        AutoModBlockInteractionActionMetadata,
        AutoModBlockMessageActionMetadata,
        AutoModRule as AutoModRulePayload,
        AutoModSendAlertActionMetadata,
        AutoModTimeoutActionMetadata,
        AutoModTriggerMetadata as AutoModTriggerMetadataPayload,
        EditAutoModRule as EditAutoModRulePayload,
    )
    from .types.gateway import AutoModerationActionExecutionEvent

__all__ = (
    "AutoModAction",
    "AutoModBlockMessageAction",
    "AutoModSendAlertAction",
    "AutoModTimeoutAction",
    "AutoModBlockInteractionAction",
    "AutoModTriggerMetadata",
    "AutoModRule",
    "AutoModActionExecution",
)


class AutoModAction:
    """A base class for auto moderation actions.

    This class is not meant to be instantiated by the user.
    The user-constructible subclasses are:

    - :class:`AutoModBlockMessageAction`
    - :class:`AutoModSendAlertAction`
    - :class:`AutoModTimeoutAction`
    - :class:`AutoModBlockInteractionAction`

    Actions received from the API may be of this type
    (and not one of the subtypes above) if the action type is not implemented yet.

    To see which actions can be used with specific trigger types,
    refer to :ref:`this table <automod_trigger_action_table>`.

    .. versionadded:: 2.6

    Attributes
    ----------
    type: :class:`AutoModActionType`
        The action type.
    """

    __slots__ = ("type", "_metadata")

    def __init__(
        self,
        *,
        type: AutoModActionType,
    ) -> None:
        self.type: AutoModActionType = enum_if_int(AutoModActionType, type)
        self._metadata: AutoModActionMetadata = {}

    def __repr__(self) -> str:
        return f"<{type(self).__name__} type={self.type!r}>"

    @classmethod
    def _from_dict(cls, data: AutoModActionPayload) -> Self:
        self = cls.__new__(cls)

        self.type = try_enum(AutoModActionType, data["type"])
        self._metadata = data.get("metadata", {})

        return self

    def to_dict(self) -> AutoModActionPayload:
        return {
            "type": self.type.value,
            "metadata": self._metadata,
        }


class AutoModBlockMessageAction(AutoModAction):
    """Represents an auto moderation action that blocks content from being sent.

    To see which trigger types this can be used with,
    refer to :ref:`this table <automod_trigger_action_table>`.

    .. versionadded:: 2.6

    Parameters
    ----------
    custom_message: Optional[:class:`str`]
        The custom message to show to the user when the rule is triggered.
        Maximum length is 150 characters.

        .. versionadded:: 2.9

    Attributes
    ----------
    type: :class:`AutoModActionType`
        The action type.
        Always set to :attr:`~AutoModActionType.block_message`.
    """

    __slots__ = ()

    _metadata: AutoModBlockMessageActionMetadata

    def __init__(self, custom_message: Optional[str] = None) -> None:
        super().__init__(type=AutoModActionType.block_message)

        if custom_message is not None:
            self._metadata["custom_message"] = custom_message

    @property
    def custom_message(self) -> Optional[str]:
        """Optional[:class:`str`]: The custom message to show to the user when the rule is triggered.

        .. versionadded:: 2.9
        """
        return self._metadata.get("custom_message")

    def __repr__(self) -> str:
        return f"<{type(self).__name__} custom_message={self.custom_message!r}>"


class AutoModSendAlertAction(AutoModAction):
    """Represents an auto moderation action that sends an alert to a channel.

    To see which trigger types this can be used with,
    refer to :ref:`this table <automod_trigger_action_table>`.

    .. versionadded:: 2.6

    Parameters
    ----------
    channel: :class:`abc.Snowflake`
        The channel to send an alert in when the rule is triggered.

    Attributes
    ----------
    type: :class:`AutoModActionType`
        The action type.
        Always set to :attr:`~AutoModActionType.send_alert_message`.
    """

    __slots__ = ()

    _metadata: AutoModSendAlertActionMetadata

    def __init__(self, channel: Snowflake) -> None:
        super().__init__(type=AutoModActionType.send_alert_message)

        self._metadata["channel_id"] = channel.id

    @property
    def channel_id(self) -> int:
        """:class:`int`: The channel ID to send an alert in when the rule is triggered."""
        return int(self._metadata["channel_id"])

    def __repr__(self) -> str:
        return f"<{type(self).__name__} channel_id={self.channel_id!r}>"


class AutoModTimeoutAction(AutoModAction):
    """Represents an auto moderation action that times out the user.

    To see which trigger types this can be used with,
    refer to :ref:`this table <automod_trigger_action_table>`.

    .. versionadded:: 2.6

    Parameters
    ----------
    duration: Union[:class:`int`, :class:`datetime.timedelta`]
        The duration (seconds or timedelta) for which to timeout the user when the rule is triggered.

    Attributes
    ----------
    type: :class:`AutoModActionType`
        The action type.
        Always set to :attr:`~AutoModActionType.timeout`.
    """

    __slots__ = ()

    _metadata: AutoModTimeoutActionMetadata

    def __init__(self, duration: Union[int, datetime.timedelta]) -> None:
        super().__init__(type=AutoModActionType.timeout)

        if isinstance(duration, datetime.timedelta):
            duration = int(duration.total_seconds())
        self._metadata["duration_seconds"] = duration

    @property
    def duration(self) -> int:
        """:class:`int`: The duration (in seconds) for which to timeout
        the user when the rule is triggered.
        """
        return self._metadata["duration_seconds"]

    def __repr__(self) -> str:
        return f"<{type(self).__name__} duration={self.duration!r}>"


class AutoModBlockInteractionAction(AutoModAction):
    """Represents an auto moderation action that prevents the user
    from using text, voice, or other interactions.

    To see which trigger types this can be used with,
    refer to :ref:`this table <automod_trigger_action_table>`.

    .. versionadded:: 2.10

    Attributes
    ----------
    type: :class:`AutoModActionType`
        The action type.
        Always set to :attr:`~AutoModActionType.block_member_interaction`.
    """

    __slots__ = ()

    _metadata: AutoModBlockInteractionActionMetadata

    def __init__(self) -> None:
        super().__init__(type=AutoModActionType.block_member_interaction)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


class AutoModTriggerMetadata:
    """Metadata for an auto moderation trigger.

    Based on the trigger type, different fields can be used with various limits:

    .. csv-table::
        :header: "Trigger Type", ``keyword_filter``, ``regex_patterns``, ``presets``, ``allow_list``, ``mention_total_limit``, ``mention_raid_protection_enabled``

        :attr:`~AutoModTriggerType.keyword`,        ✅ (x1000), ✅ (x10), ❌, ✅ (x100),  ❌, ❌
        :attr:`~AutoModTriggerType.spam`,           ❌,         ❌,       ❌, ❌,         ❌, ❌
        :attr:`~AutoModTriggerType.keyword_preset`, ❌,         ❌,       ✅, ✅ (x1000), ❌, ❌
        :attr:`~AutoModTriggerType.mention_spam`,   ❌,         ❌,       ❌, ❌,         ✅, ✅
        :attr:`~AutoModTriggerType.member_profile`, ✅ (x1000), ✅ (x10), ❌, ✅ (x100),  ❌, ❌

    .. versionadded:: 2.6

    Attributes
    ----------
    keyword_filter: Optional[Sequence[:class:`str`]]
        The list of keywords to check for, up to 1000 keywords.

        See :ddocs:`api docs <resources/auto-moderation#auto-moderation-rule-object-keyword-matching-strategies>`
        for details about how keyword matching works.
        Each keyword must be 60 characters or less.

    regex_patterns: Optional[Sequence[:class:`str`]]
        The list of regular expressions to check for.

        A maximum of 10 regexes can be added, each with up to 260 characters.

        .. note::

            Only Rust flavored regex is currently supported, which can be tested in online editors such as `Rustexp <https://rustexp.lpil.uk/>`__.

        .. versionadded:: 2.7

    presets: Optional[:class:`AutoModKeywordPresets`]
        The keyword presets (pre-defined wordsets defined by Discord).

    allow_list: Optional[Sequence[:class:`str`]]
        The keywords that should be exempt from a preset,
        up to 100 or 1000 depending on the used trigger type - see the table above.

        Each keyword must be 60 characters or less.

    mention_total_limit: Optional[:class:`int`]
        The maximum number of mentions (members + roles) allowed, between 1 and 50.

    mention_raid_protection_enabled: Optional[:class:`bool`]
        Whether to automatically detect mention raids.

        Defaults to ``False``.

        .. versionadded:: 2.9
    """

    __slots__ = (
        "keyword_filter",
        "regex_patterns",
        "presets",
        "allow_list",
        "mention_total_limit",
        "mention_raid_protection_enabled",
    )

    @overload
    def __init__(
        self,
        *,
        keyword_filter: Optional[Sequence[str]],
        regex_patterns: Optional[Sequence[str]] = None,
        allow_list: Optional[Sequence[str]] = None,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        *,
        keyword_filter: Optional[Sequence[str]] = None,
        regex_patterns: Optional[Sequence[str]],
        allow_list: Optional[Sequence[str]] = None,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        *,
        presets: AutoModKeywordPresets,
        allow_list: Optional[Sequence[str]] = None,
    ) -> None:
        ...

    @overload
    def __init__(
        self, *, mention_total_limit: int, mention_raid_protection_enabled: bool = False
    ) -> None:
        ...

    def __init__(
        self,
        *,
        keyword_filter: Optional[Sequence[str]] = None,
        regex_patterns: Optional[Sequence[str]] = None,
        presets: Optional[AutoModKeywordPresets] = None,
        allow_list: Optional[Sequence[str]] = None,
        mention_total_limit: Optional[int] = None,
        mention_raid_protection_enabled: Optional[bool] = None,
    ) -> None:
        self.keyword_filter: Optional[Sequence[str]] = keyword_filter
        self.regex_patterns: Optional[Sequence[str]] = regex_patterns
        self.presets: Optional[AutoModKeywordPresets] = presets
        self.allow_list: Optional[Sequence[str]] = allow_list
        self.mention_total_limit: Optional[int] = mention_total_limit
        self.mention_raid_protection_enabled: Optional[bool] = mention_raid_protection_enabled

    def with_changes(
        self,
        *,
        keyword_filter: Optional[Sequence[str]] = MISSING,
        regex_patterns: Optional[Sequence[str]] = MISSING,
        presets: Optional[AutoModKeywordPresets] = MISSING,
        allow_list: Optional[Sequence[str]] = MISSING,
        mention_total_limit: Optional[int] = MISSING,
        mention_raid_protection_enabled: Optional[bool] = MISSING,
    ) -> Self:
        """Returns a new instance with the given changes applied.
        All other fields will be kept intact.

        Returns
        -------
        :class:`AutoModTriggerMetadata`
            The new metadata instance.
        """
        return self.__class__(  # type: ignore  # call doesn't match any overloads
            keyword_filter=self.keyword_filter if keyword_filter is MISSING else keyword_filter,
            regex_patterns=self.regex_patterns if regex_patterns is MISSING else regex_patterns,
            presets=self.presets if presets is MISSING else presets,
            allow_list=self.allow_list if allow_list is MISSING else allow_list,
            mention_total_limit=(
                self.mention_total_limit if mention_total_limit is MISSING else mention_total_limit
            ),
            mention_raid_protection_enabled=(
                self.mention_raid_protection_enabled
                if mention_raid_protection_enabled is MISSING
                else mention_raid_protection_enabled
            ),
        )

    @classmethod
    def _from_dict(cls, data: AutoModTriggerMetadataPayload) -> Self:
        if (presets_data := data.get("presets")) is not None:
            presets = AutoModKeywordPresets._from_values(presets_data)
        else:
            presets = None

        return cls(  # type: ignore  # call doesn't match any overloads
            keyword_filter=data.get("keyword_filter"),
            regex_patterns=data.get("regex_patterns"),
            presets=presets,
            allow_list=data.get("allow_list"),
            mention_total_limit=data.get("mention_total_limit"),
            mention_raid_protection_enabled=data.get("mention_raid_protection_enabled"),
        )

    def to_dict(self) -> AutoModTriggerMetadataPayload:
        data: AutoModTriggerMetadataPayload = {}
        if self.keyword_filter is not None:
            data["keyword_filter"] = list(self.keyword_filter)
        if self.regex_patterns is not None:
            data["regex_patterns"] = list(self.regex_patterns)
        if self.presets is not None:
            data["presets"] = self.presets.values  # type: ignore  # `values` contains ints instead of preset literal values
        if self.allow_list is not None:
            data["allow_list"] = list(self.allow_list)
        if self.mention_total_limit is not None:
            data["mention_total_limit"] = self.mention_total_limit
        if self.mention_raid_protection_enabled is not None:
            data["mention_raid_protection_enabled"] = self.mention_raid_protection_enabled
        return data

    def __repr__(self) -> str:
        s = f"<{type(self).__name__}"
        if self.keyword_filter is not None:
            s += f" keyword_filter={self.keyword_filter!r}"
        if self.regex_patterns is not None:
            s += f" regex_patterns={self.regex_patterns!r}"
        if self.presets is not None:
            s += f" presets={self.presets!r}"
        if self.allow_list is not None:
            s += f" allow_list={self.allow_list!r}"
        if self.mention_total_limit is not None:
            s += f" mention_total_limit={self.mention_total_limit!r}"
        if self.mention_raid_protection_enabled is not None:
            s += f" mention_raid_protection_enabled={self.mention_raid_protection_enabled!r}"
        return f"{s}>"


class AutoModRule:
    """Represents an auto moderation rule.

    .. versionadded:: 2.6

    Attributes
    ----------
    id: :class:`int`
        The rule ID.
    name: :class:`str`
        The rule name.
    enabled: :class:`bool`
        Whether this rule is enabled.
    guild: :class:`Guild`
        The guild of the rule.
    creator_id: :class:`int`
        The rule creator's ID. See also :attr:`.creator`.
    event_type: :class:`AutoModEventType`
        The event type this rule is applied to.
    trigger_type: :class:`AutoModTriggerType`
        The type of trigger that determines whether this rule's actions should run for a specific event.
    trigger_metadata: :class:`AutoModTriggerMetadata`
        Additional metadata associated with this rule's :attr:`.trigger_type`.
    exempt_role_ids: FrozenSet[:class:`int`]
        The role IDs that are exempt from this rule.
    exempt_channel_ids: FrozenSet[:class:`int`]
        The channel IDs that are exempt from this rule.
    """

    __slots__ = (
        "id",
        "name",
        "enabled",
        "guild",
        "creator_id",
        "event_type",
        "trigger_type",
        "trigger_metadata",
        "_actions",
        "exempt_role_ids",
        "exempt_channel_ids",
    )

    def __init__(self, *, data: AutoModRulePayload, guild: Guild) -> None:
        self.guild: Guild = guild

        self.id: int = int(data["id"])
        self.name: str = data["name"]
        self.enabled: bool = data["enabled"]
        self.creator_id: int = int(data["creator_id"])
        self.event_type: AutoModEventType = try_enum(AutoModEventType, data["event_type"])
        self.trigger_type: AutoModTriggerType = try_enum(AutoModTriggerType, data["trigger_type"])
        self._actions: List[AutoModAction] = [
            _automod_action_factory(action) for action in data["actions"]
        ]
        self.trigger_metadata: AutoModTriggerMetadata = AutoModTriggerMetadata._from_dict(
            data.get("trigger_metadata", {})
        )
        self.exempt_role_ids: FrozenSet[int] = (
            frozenset(map(int, exempt_roles))
            if (exempt_roles := data.get("exempt_roles"))
            else frozenset()
        )
        self.exempt_channel_ids: FrozenSet[int] = (
            frozenset(map(int, exempt_channels))
            if (exempt_channels := data.get("exempt_channels"))
            else frozenset()
        )

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the rule's creation time in UTC.

        .. versionadded:: 2.10
        """
        return snowflake_time(self.id)

    @property
    def actions(self) -> List[AutoModAction]:
        """List[Union[:class:`AutoModBlockMessageAction`, :class:`AutoModSendAlertAction`, :class:`AutoModTimeoutAction`, :class:`AutoModBlockInteractionAction`, :class:`AutoModAction`]]:
        The list of actions that will execute if a matching event triggered this rule.
        """
        return list(self._actions)  # return a copy

    @property
    def creator(self) -> Optional[Member]:
        """Optional[:class:`Member`]: The guild member that created this rule.
        May be ``None`` if the member cannot be found. See also :attr:`.creator_id`.
        """
        return self.guild.get_member(self.creator_id)

    @property
    def exempt_roles(self) -> List[Role]:
        """List[:class:`Role`]: The list of roles that are exempt from this rule."""
        return list(filter(None, map(self.guild.get_role, self.exempt_role_ids)))

    @property
    def exempt_channels(self) -> List[GuildChannel]:
        """List[:class:`abc.GuildChannel`]: The list of channels that are exempt from this rule."""
        return list(filter(None, map(self.guild.get_channel, self.exempt_channel_ids)))

    def __repr__(self) -> str:
        return (
            f"<AutoModRule id={self.id!r} name={self.name!r} enabled={self.enabled!r}"
            f" creator={self.creator!r} event_type={self.event_type!r} trigger_type={self.trigger_type!r}"
            f" actions={self._actions!r} exempt_roles={self.exempt_role_ids!r} exempt_channels={self.exempt_channel_ids!r}"
            f" trigger_metadata={self.trigger_metadata!r}>"
        )

    async def edit(
        self,
        *,
        name: str = MISSING,
        event_type: AutoModEventType = MISSING,
        trigger_metadata: AutoModTriggerMetadata = MISSING,
        actions: Sequence[AutoModAction] = MISSING,
        enabled: bool = MISSING,
        exempt_roles: Optional[Iterable[Snowflake]] = MISSING,
        exempt_channels: Optional[Iterable[Snowflake]] = MISSING,
        reason: Optional[str] = None,
    ) -> AutoModRule:
        """|coro|

        Edits the auto moderation rule.

        You must have :attr:`.Permissions.manage_guild` permission to do this.

        All fields are optional.

        .. versionchanged:: 2.9
            Now raises a :exc:`TypeError` if given ``actions`` have an invalid type.

        Examples
        --------
        Edit name and enable rule:

        .. code-block:: python3

            await rule.edit(name="cool new rule", enabled=True)

        Add an action:

        .. code-block:: python3

            await rule.edit(
                actions=rule.actions + [AutoModTimeoutAction(3600)],
            )

        Add a keyword to a keyword filter rule:

        .. code-block:: python3

            meta = rule.trigger_metadata
            await rule.edit(
                trigger_metadata=meta.with_changes(
                    keyword_filter=meta.keyword_filter + ["stuff"],
                ),
            )

        Parameters
        ----------
        name: :class:`str`
            The rule's new name.
        event_type: :class:`AutoModEventType`
            The rule's new event type.

            Refer to :ref:`this table <automod_trigger_event_table>` to see how event types can be used.
        trigger_metadata: :class:`AutoModTriggerMetadata`
            The rule's new associated trigger metadata.
        actions: Sequence[Union[:class:`AutoModBlockMessageAction`, :class:`AutoModSendAlertAction`, :class:`AutoModTimeoutAction`, :class:`AutoModBlockInteractionAction`, :class:`AutoModAction`]]
            The rule's new actions.
            If provided, must contain at least one action.
        enabled: :class:`bool`
            Whether to enable the rule.
        exempt_roles: Optional[Iterable[:class:`abc.Snowflake`]]
            The rule's new exempt roles, up to 20.
            If ``[]`` or ``None`` is passed then all role exemptions are removed.
        exempt_channels: Optional[Iterable[:class:`abc.Snowflake`]]
            The rule's new exempt channels, up to 50.
            Can also include categories, in which case all channels inside that category will be exempt.
            If ``[]`` or ``None`` is passed then all channel exemptions are removed.
        reason: Optional[:class:`str`]
            The reason for editing the rule. Shows up on the audit log.

        Raises
        ------
        ValueError
            When editing the list of actions, at least one action must be provided.
        TypeError
            The specified ``actions`` are of an invalid type.
        Forbidden
            You do not have proper permissions to edit the rule.
        NotFound
            The rule does not exist.
        HTTPException
            Editing the rule failed.

        Returns
        -------
        :class:`AutoModRule`
            The newly updated auto moderation rule.
        """
        payload: EditAutoModRulePayload = {}

        if name is not MISSING:
            payload["name"] = name
        if event_type is not MISSING:
            payload["event_type"] = try_enum_to_int(event_type)
        if trigger_metadata is not MISSING:
            payload["trigger_metadata"] = trigger_metadata.to_dict()
        if actions is not MISSING:
            if not actions:
                raise ValueError("At least one action must be provided.")
            for action in actions:
                if not isinstance(action, AutoModAction):
                    raise TypeError(
                        f"actions must be of type `AutoModAction` (or subtype), not {type(action)!r}"
                    )
            payload["actions"] = [a.to_dict() for a in actions]
        if enabled is not MISSING:
            payload["enabled"] = enabled
        if exempt_roles is not MISSING:
            payload["exempt_roles"] = (
                [e.id for e in exempt_roles] if exempt_roles is not None else []
            )
        if exempt_channels is not MISSING:
            payload["exempt_channels"] = (
                [e.id for e in exempt_channels] if exempt_channels is not None else []
            )

        data = await self.guild._state.http.edit_auto_moderation_rule(
            self.guild.id, self.id, reason=reason, **payload
        )
        return AutoModRule(data=data, guild=self.guild)

    async def delete(self, *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes the auto moderation rule.

        You must have :attr:`.Permissions.manage_guild` permission to do this.

        Parameters
        ----------
        reason: Optional[:class:`str`]
            The reason for deleting this rule. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have proper permissions to delete the rule.
        NotFound
            The rule does not exist.
        HTTPException
            Deleting the rule failed.
        """
        await self.guild._state.http.delete_auto_moderation_rule(
            self.guild.id, self.id, reason=reason
        )


class AutoModActionExecution:
    """Represents the data for an :func:`on_automod_action_execution` event.

    .. versionadded:: 2.6

    Attributes
    ----------
    action: Union[:class:`AutoModBlockMessageAction`, :class:`AutoModSendAlertAction`, :class:`AutoModTimeoutAction`, :class:`AutoModBlockInteractionAction`, :class:`AutoModAction`]
        The action that was executed.
    guild: :class:`Guild`
        The guild this action was executed in.
    rule_id: :class:`int`
        The ID of the rule that matched.
    rule_trigger_type: :class:`AutoModTriggerType`
        The trigger type of the rule that matched.
    user_id: :class:`int`
        The ID of the user that triggered this action.
        See also :attr:`.user`.
    channel_id: Optional[:class:`int`]
        The channel or thread ID in which the event occurred, if any.
        See also :attr:`.channel`.
    message_id: Optional[:class:`int`]
        The ID of the message that matched. ``None`` if the message was blocked,
        or if the content was not part of a message.
        See also :attr:`.message`.
    alert_message_id: Optional[:class:`int`]
        The ID of the alert message sent as a result of this action, if any.
        See also :attr:`.alert_message`.
    content: :class:`str`
        The content that matched.

        Requires :attr:`Intents.message_content` to be enabled,
        otherwise this field will be empty.

    matched_keyword: Optional[:class:`str`]
        The keyword or regex that matched.

    matched_content: Optional[:class:`str`]
        The substring of :attr:`.content` that matched the rule/keyword.

        Requires :attr:`Intents.message_content` to be enabled,
        otherwise this field will be empty.
    """

    __slots__ = (
        "action",
        "guild",
        "rule_id",
        "rule_trigger_type",
        "user_id",
        "channel_id",
        "message_id",
        "alert_message_id",
        "content",
        "matched_keyword",
        "matched_content",
    )

    def __init__(self, *, data: AutoModerationActionExecutionEvent, guild: Guild) -> None:
        self.guild: Guild = guild
        self.action: AutoModAction = _automod_action_factory(data["action"])
        self.rule_id: int = int(data["rule_id"])
        self.rule_trigger_type: AutoModTriggerType = try_enum(
            AutoModTriggerType, data["rule_trigger_type"]
        )
        self.user_id: int = int(data["user_id"])
        self.channel_id: Optional[int] = _get_as_snowflake(data, "channel_id")
        self.message_id: Optional[int] = _get_as_snowflake(data, "message_id")
        self.alert_message_id: Optional[int] = _get_as_snowflake(data, "alert_system_message_id")
        self.content: str = data.get("content") or ""
        self.matched_keyword: Optional[str] = data.get("matched_keyword")
        self.matched_content: Optional[str] = data.get("matched_content")

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} guild={self.guild!r} action={self.action!r}"
            f" rule_id={self.rule_id!r} rule_trigger_type={self.rule_trigger_type!r}"
            f" channel={self.channel!r} user_id={self.user_id!r} message_id={self.message_id!r}"
            f" alert_message_id={self.alert_message_id!r} content={self.content!r}"
            f" matched_keyword={self.matched_keyword!r} matched_content={self.matched_content!r}>"
        )

    @property
    def user(self) -> Optional[Member]:
        """Optional[:class:`Member`]: The guild member that triggered this action.
        May be ``None`` if the member cannot be found. See also :attr:`.user_id`.
        """
        return self.guild.get_member(self.user_id)

    @property
    def channel(self) -> Optional[Union[GuildChannel, Thread]]:
        """Optional[Union[:class:`abc.GuildChannel`, :class:`Thread`]]:
        The channel or thread in which the event occurred, if any.
        """
        return self.guild._resolve_channel(self.channel_id)

    @property
    def message(self) -> Optional[Message]:
        """Optional[:class:`Message`]: The message that matched, if any.
        Not available if the message was blocked, if the content was not part of a message,
        or if the message was not found in the message cache.
        """
        return self.guild._state._get_message(self.message_id)

    @property
    def alert_message(self) -> Optional[Message]:
        """Optional[:class:`Message`]: The alert message sent as a result of this action, if any.
        Only available if :attr:`action.type <AutoModAction.type>` is :attr:`~AutoModActionType.send_alert_message`
        and the message was found in the message cache.
        """
        return self.guild._state._get_message(self.alert_message_id)


_action_map: Dict[int, Type[AutoModAction]] = {
    AutoModActionType.block_message.value: AutoModBlockMessageAction,
    AutoModActionType.send_alert_message.value: AutoModSendAlertAction,
    AutoModActionType.timeout.value: AutoModTimeoutAction,
    AutoModActionType.block_member_interaction.value: AutoModBlockInteractionAction,
}


def _automod_action_factory(data: AutoModActionPayload) -> AutoModAction:
    tp = _action_map.get(data["type"], AutoModAction)
    return tp._from_dict(data)
