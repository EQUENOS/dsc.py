# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import copy
from abc import ABC
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)

from . import utils
from .context_managers import Typing
from .enums import (
    ChannelType,
    PartyType,
    ThreadLayout,
    ThreadSortOrder,
    VideoQualityMode,
    try_enum_to_int,
)
from .errors import ClientException
from .file import File
from .flags import ChannelFlags, MessageFlags
from .invite import Invite
from .mentions import AllowedMentions
from .partial_emoji import PartialEmoji
from .permissions import PermissionOverwrite, Permissions
from .role import Role
from .sticker import GuildSticker, StickerItem
from .ui.action_row import components_to_dict
from .utils import _overload_with_permissions
from .voice_client import VoiceClient, VoiceProtocol

__all__ = (
    "Snowflake",
    "User",
    "PrivateChannel",
    "GuildChannel",
    "Messageable",
    "Connectable",
)

VoiceProtocolT = TypeVar("VoiceProtocolT", bound=VoiceProtocol)

if TYPE_CHECKING:
    from datetime import datetime

    from typing_extensions import Self

    from .asset import Asset
    from .channel import CategoryChannel, DMChannel, PartialMessageable
    from .client import Client
    from .embeds import Embed
    from .emoji import Emoji
    from .enums import InviteTarget
    from .guild import Guild, GuildMessageable
    from .guild_scheduled_event import GuildScheduledEvent
    from .iterators import HistoryIterator
    from .member import Member
    from .message import Message, MessageReference, PartialMessage
    from .state import ConnectionState
    from .threads import AnyThreadArchiveDuration, ForumTag
    from .types.channel import (
        Channel as ChannelPayload,
        DefaultReaction as DefaultReactionPayload,
        GuildChannel as GuildChannelPayload,
        OverwriteType,
        PermissionOverwrite as PermissionOverwritePayload,
    )
    from .types.threads import PartialForumTag as PartialForumTagPayload
    from .ui.action_row import Components, MessageUIComponent
    from .ui.view import View
    from .user import ClientUser
    from .voice_region import VoiceRegion

    MessageableChannel = Union[GuildMessageable, DMChannel, PartialMessageable]
    SnowflakeTime = Union["Snowflake", datetime]

MISSING = utils.MISSING


@runtime_checkable
class Snowflake(Protocol):
    """An ABC that details the common operations on a Discord model.

    Almost all :ref:`Discord models <discord_model>` meet this
    abstract base class.

    If you want to create a snowflake on your own, consider using
    :class:`.Object`.

    Attributes
    ----------
    id: :class:`int`
        The model's unique ID.
    """

    __slots__ = ()
    id: int


@runtime_checkable
class User(Snowflake, Protocol):
    """An ABC that details the common operations on a Discord user.

    The following classes implement this ABC:

    - :class:`~disnake.User`
    - :class:`~disnake.ClientUser`
    - :class:`~disnake.Member`

    This ABC must also implement :class:`~disnake.abc.Snowflake`.

    Attributes
    ----------
    name: :class:`str`
        The user's username.
    discriminator: :class:`str`
        The user's discriminator.
    avatar: :class:`~disnake.Asset`
        The avatar asset the user has.
    bot: :class:`bool`
        Whether the user is a bot account.
    """

    __slots__ = ()

    name: str
    discriminator: str
    avatar: Asset
    bot: bool

    @property
    def display_name(self) -> str:
        """:class:`str`: Returns the user's display name."""
        raise NotImplementedError

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a string that allows you to mention the given user."""
        raise NotImplementedError


@runtime_checkable
class PrivateChannel(Snowflake, Protocol):
    """An ABC that details the common operations on a private Discord channel.

    The following classes implement this ABC:

    - :class:`~disnake.DMChannel`
    - :class:`~disnake.GroupChannel`

    This ABC must also implement :class:`~disnake.abc.Snowflake`.

    Attributes
    ----------
    me: :class:`~disnake.ClientUser`
        The user representing yourself.
    """

    __slots__ = ()

    me: ClientUser


class _Overwrites:
    __slots__ = ("id", "allow", "deny", "type")

    ROLE = 0
    MEMBER = 1

    def __init__(self, data: PermissionOverwritePayload) -> None:
        self.id: int = int(data["id"])
        self.allow: int = int(data.get("allow", 0))
        self.deny: int = int(data.get("deny", 0))
        self.type: OverwriteType = data["type"]

    def _asdict(self) -> PermissionOverwritePayload:
        return {
            "id": self.id,
            "allow": str(self.allow),
            "deny": str(self.deny),
            "type": self.type,
        }

    def is_role(self) -> bool:
        return self.type == 0

    def is_member(self) -> bool:
        return self.type == 1


class GuildChannel(ABC):
    """An ABC that details the common operations on a Discord guild channel.

    The following classes implement this ABC:

    - :class:`.TextChannel`
    - :class:`.VoiceChannel`
    - :class:`.CategoryChannel`
    - :class:`.StageChannel`
    - :class:`.ForumChannel`

    This ABC must also implement :class:`.abc.Snowflake`.

    Attributes
    ----------
    name: :class:`str`
        The channel name.
    guild: :class:`.Guild`
        The guild the channel belongs to.
    position: :class:`int`
        The position in the channel list. This is a number that starts at 0.
        e.g. the top channel is position 0.
    """

    __slots__ = ()

    id: int
    name: str
    guild: Guild
    type: ChannelType
    position: int
    category_id: Optional[int]
    _flags: int
    _state: ConnectionState
    _overwrites: List[_Overwrites]

    if TYPE_CHECKING:

        def __init__(
            self, *, state: ConnectionState, guild: Guild, data: Mapping[str, Any]
        ) -> None:
            ...

    def __str__(self) -> str:
        return self.name

    @property
    def _sorting_bucket(self) -> int:
        raise NotImplementedError

    def _update(self, guild: Guild, data: Dict[str, Any]) -> None:
        raise NotImplementedError

    async def _move(
        self,
        position: int,
        parent_id: Optional[int] = None,
        lock_permissions: bool = False,
        *,
        reason: Optional[str],
    ) -> None:
        if position < 0:
            raise ValueError("Channel position cannot be less than 0.")

        http = self._state.http
        bucket = self._sorting_bucket
        channels = [c for c in self.guild.channels if c._sorting_bucket == bucket]
        channels = cast(List[GuildChannel], channels)

        channels.sort(key=lambda c: c.position)

        try:
            # remove ourselves from the channel list
            channels.remove(self)
        except ValueError:
            # not there somehow lol
            return
        else:
            index = next(
                (i for i, c in enumerate(channels) if c.position >= position), len(channels)
            )
            # add ourselves at our designated position
            channels.insert(index, self)

        payload = []
        for index, c in enumerate(channels):
            d: Dict[str, Any] = {"id": c.id, "position": index}
            if parent_id is not MISSING and c.id == self.id:
                d.update(parent_id=parent_id, lock_permissions=lock_permissions)
            payload.append(d)

        await http.bulk_channel_update(self.guild.id, payload, reason=reason)

    async def _edit(
        self,
        *,
        name: str = MISSING,
        topic: Optional[str] = MISSING,
        position: int = MISSING,
        nsfw: bool = MISSING,
        sync_permissions: bool = MISSING,
        category: Optional[Snowflake] = MISSING,
        slowmode_delay: Optional[int] = MISSING,
        default_thread_slowmode_delay: Optional[int] = MISSING,
        default_auto_archive_duration: Optional[AnyThreadArchiveDuration] = MISSING,
        type: ChannelType = MISSING,
        overwrites: Mapping[Union[Role, Member], PermissionOverwrite] = MISSING,
        bitrate: int = MISSING,
        user_limit: int = MISSING,
        rtc_region: Optional[Union[str, VoiceRegion]] = MISSING,
        video_quality_mode: VideoQualityMode = MISSING,
        flags: ChannelFlags = MISSING,
        available_tags: Sequence[ForumTag] = MISSING,
        default_reaction: Optional[Union[str, Emoji, PartialEmoji]] = MISSING,
        default_sort_order: Optional[ThreadSortOrder] = MISSING,
        default_layout: ThreadLayout = MISSING,
        reason: Optional[str] = None,
    ) -> Optional[ChannelPayload]:
        parent_id: Optional[int]
        if category is not MISSING:
            # if category is given, it's either `None` (no parent) or a category channel
            parent_id = category.id if category else None
        else:
            # if it's not given, don't change the category
            parent_id = MISSING

        rtc_region_payload: Optional[str]
        if rtc_region is not MISSING:
            rtc_region_payload = str(rtc_region) if rtc_region is not None else None
        else:
            rtc_region_payload = MISSING

        video_quality_mode_payload: Optional[int]
        if video_quality_mode is not MISSING:
            video_quality_mode_payload = int(video_quality_mode)
        else:
            video_quality_mode_payload = MISSING

        default_auto_archive_duration_payload: Optional[int]
        if default_auto_archive_duration is not MISSING:
            default_auto_archive_duration_payload = (
                int(default_auto_archive_duration)
                if default_auto_archive_duration is not None
                else default_auto_archive_duration
            )
        else:
            default_auto_archive_duration_payload = MISSING

        lock_permissions: bool = bool(sync_permissions)

        overwrites_payload: List[PermissionOverwritePayload] = MISSING

        if position is not MISSING:
            await self._move(
                position, parent_id=parent_id, lock_permissions=lock_permissions, reason=reason
            )
            parent_id = MISSING  # no need to change it again in the edit request below
        elif lock_permissions:
            if parent_id is not MISSING:
                p_id = parent_id
            else:
                p_id = self.category_id

            if p_id is not None and (parent := self.guild.get_channel(p_id)):
                overwrites_payload = [c._asdict() for c in parent._overwrites]

        if overwrites is not MISSING and overwrites is not None:
            overwrites_payload = []
            for target, perm in overwrites.items():
                if not isinstance(perm, PermissionOverwrite):
                    raise TypeError(
                        f"Expected PermissionOverwrite, received {perm.__class__.__name__}"
                    )

                allow, deny = perm.pair()
                payload: PermissionOverwritePayload = {
                    "allow": str(allow.value),
                    "deny": str(deny.value),
                    "id": target.id,
                    "type": _Overwrites.ROLE if isinstance(target, Role) else _Overwrites.MEMBER,
                }
                overwrites_payload.append(payload)

        type_payload: int
        if type is not MISSING:
            if not isinstance(type, ChannelType):
                raise TypeError("type field must be of type ChannelType")
            type_payload = type.value
        else:
            type_payload = MISSING

        flags_payload: int
        if flags is not MISSING:
            if not isinstance(flags, ChannelFlags):
                raise TypeError("flags field must be of type ChannelFlags")
            flags_payload = flags.value
        else:
            flags_payload = MISSING

        available_tags_payload: List[PartialForumTagPayload] = MISSING
        if available_tags is not MISSING:
            available_tags_payload = [tag.to_dict() for tag in available_tags]

        default_reaction_emoji_payload: Optional[DefaultReactionPayload] = MISSING
        if default_reaction is not MISSING:
            if default_reaction is not None:
                emoji_name, emoji_id = PartialEmoji._emoji_to_name_id(default_reaction)
                default_reaction_emoji_payload = {
                    "emoji_name": emoji_name,
                    "emoji_id": emoji_id,
                }
            else:
                default_reaction_emoji_payload = None

        default_sort_order_payload: Optional[int] = MISSING
        if default_sort_order is not MISSING:
            default_sort_order_payload = (
                try_enum_to_int(default_sort_order) if default_sort_order is not None else None
            )

        default_layout_payload: int = MISSING
        if default_layout is not MISSING:
            default_layout_payload = try_enum_to_int(default_layout)

        options: Dict[str, Any] = {
            "name": name,
            "parent_id": parent_id,
            "topic": topic,
            "bitrate": bitrate,
            "nsfw": nsfw,
            "user_limit": user_limit,
            # note: not passing `position` as it already got updated before, if passed
            "permission_overwrites": overwrites_payload,
            "rate_limit_per_user": slowmode_delay,
            "default_thread_rate_limit_per_user": default_thread_slowmode_delay,
            "type": type_payload,
            "rtc_region": rtc_region_payload,
            "video_quality_mode": video_quality_mode_payload,
            "default_auto_archive_duration": default_auto_archive_duration_payload,
            "flags": flags_payload,
            "available_tags": available_tags_payload,
            "default_reaction_emoji": default_reaction_emoji_payload,
            "default_sort_order": default_sort_order_payload,
            "default_forum_layout": default_layout_payload,
        }
        options = {k: v for k, v in options.items() if v is not MISSING}

        if options:
            return await self._state.http.edit_channel(self.id, reason=reason, **options)
        return None

    def _fill_overwrites(self, data: GuildChannelPayload) -> None:
        self._overwrites = []
        everyone_index = 0
        everyone_id = self.guild.id

        for index, overridden in enumerate(data.get("permission_overwrites", [])):
            overwrite = _Overwrites(overridden)
            self._overwrites.append(overwrite)

            if overwrite.type == _Overwrites.MEMBER:
                continue

            if overwrite.id == everyone_id:
                # the @everyone role is not guaranteed to be the first one
                # in the list of permission overwrites, however the permission
                # resolution code kind of requires that it is the first one in
                # the list since it is special. So we need the index so we can
                # swap it to be the first one.
                everyone_index = index

        # do the swap
        tmp = self._overwrites
        if tmp:
            tmp[everyone_index], tmp[0] = tmp[0], tmp[everyone_index]

    @property
    def changed_roles(self) -> List[Role]:
        """List[:class:`.Role`]: Returns a list of roles that have been overridden from
        their default values in the :attr:`.Guild.roles` attribute.
        """
        ret = []
        g = self.guild
        for overwrite in filter(lambda o: o.is_role(), self._overwrites):
            role = g.get_role(overwrite.id)
            if role is None:
                continue

            role = copy.copy(role)
            role.permissions.handle_overwrite(overwrite.allow, overwrite.deny)
            ret.append(role)
        return ret

    @property
    def mention(self) -> str:
        """:class:`str`: The string that allows you to mention the channel."""
        return f"<#{self.id}>"

    @property
    def created_at(self) -> datetime:
        """:class:`datetime.datetime`: Returns the channel's creation time in UTC."""
        return utils.snowflake_time(self.id)

    def overwrites_for(self, obj: Union[Role, User]) -> PermissionOverwrite:
        """Returns the channel-specific overwrites for a member or a role.

        Parameters
        ----------
        obj: Union[:class:`.Role`, :class:`.abc.User`]
            The role or user denoting
            whose overwrite to get.

        Returns
        -------
        :class:`~disnake.PermissionOverwrite`
            The permission overwrites for this object.
        """
        predicate: Callable[[_Overwrites], bool]
        if isinstance(obj, User):
            predicate = lambda p: p.is_member()
        elif isinstance(obj, Role):
            predicate = lambda p: p.is_role()
        else:
            predicate = lambda p: True

        for overwrite in filter(predicate, self._overwrites):
            if overwrite.id == obj.id:
                allow = Permissions(overwrite.allow)
                deny = Permissions(overwrite.deny)
                return PermissionOverwrite.from_pair(allow, deny)

        return PermissionOverwrite()

    @property
    def overwrites(self) -> Dict[Union[Role, Member], PermissionOverwrite]:
        """Returns all of the channel's overwrites.

        This is returned as a dictionary where the key contains the target which
        can be either a :class:`~disnake.Role` or a :class:`~disnake.Member` and the value is the
        overwrite as a :class:`~disnake.PermissionOverwrite`.

        Returns
        -------
        Dict[Union[:class:`~disnake.Role`, :class:`~disnake.Member`], :class:`~disnake.PermissionOverwrite`]
            The channel's permission overwrites.
        """
        ret = {}
        for ow in self._overwrites:
            allow = Permissions(ow.allow)
            deny = Permissions(ow.deny)
            overwrite = PermissionOverwrite.from_pair(allow, deny)
            target = None

            if ow.is_role():
                target = self.guild.get_role(ow.id)
            elif ow.is_member():
                target = self.guild.get_member(ow.id)

            # TODO: There is potential data loss here in the non-chunked
            # case, i.e. target is None because get_member returned nothing.
            # This can be fixed with a slight breaking change to the return type,
            # i.e. adding disnake.Object to the list of it
            # However, for now this is an acceptable compromise.
            if target is not None:
                ret[target] = overwrite
        return ret

    @property
    def category(self) -> Optional[CategoryChannel]:
        """Optional[:class:`~disnake.CategoryChannel`]: The category this channel belongs to.

        If there is no category then this is ``None``.
        """
        return self.guild.get_channel(self.category_id)  # type: ignore

    @property
    def permissions_synced(self) -> bool:
        """:class:`bool`: Whether or not the permissions for this channel are synced with the
        category it belongs to.

        If there is no category then this is ``False``.

        .. versionadded:: 1.3
        """
        if self.category_id is None:
            return False

        category = self.guild.get_channel(self.category_id)
        return bool(category and category.overwrites == self.overwrites)

    @property
    def flags(self) -> ChannelFlags:
        """:class:`.ChannelFlags`: The channel flags for this channel.

        .. versionadded:: 2.6
        """
        return ChannelFlags._from_value(self._flags)

    @property
    def jump_url(self) -> str:
        """A URL that can be used to jump to this channel.

        .. versionadded:: 2.4

        .. note::

            This exists for all guild channels but may not be usable by the client for all guild channel types.
        """
        return f"https://discord.com/channels/{self.guild.id}/{self.id}"

    def permissions_for(
        self,
        obj: Union[Member, Role],
        /,
        *,
        ignore_timeout: bool = MISSING,
    ) -> Permissions:
        """Handles permission resolution for the :class:`~disnake.Member`
        or :class:`~disnake.Role`.

        This function takes into consideration the following cases:

        - Guild owner
        - Guild roles
        - Channel overrides
        - Member overrides
        - Timeouts

        If a :class:`~disnake.Role` is passed, then it checks the permissions
        someone with that role would have, which is essentially:

        - The default role permissions
        - The permissions of the role used as a parameter
        - The default role permission overwrites
        - The permission overwrites of the role used as a parameter

        .. versionchanged:: 2.0
            The object passed in can now be a role object.

        Parameters
        ----------
        obj: Union[:class:`~disnake.Member`, :class:`~disnake.Role`]
            The object to resolve permissions for. This could be either
            a member or a role. If it's a role then member overwrites
            are not computed.
        ignore_timeout: :class:`bool`
            Whether or not to ignore the user's timeout.
            Defaults to ``False``.

            .. versionadded:: 2.4

            .. note::

                This only applies to :class:`~disnake.Member` objects.

            .. versionchanged:: 2.6

                The default was changed to ``False``.

        Raises
        ------
        TypeError
            ``ignore_timeout`` is only supported for :class:`~disnake.Member` objects.

        Returns
        -------
        :class:`~disnake.Permissions`
            The resolved permissions for the member or role.
        """
        # The current cases can be explained as:
        # Guild owner get all permissions -- no questions asked. Otherwise...
        # The @everyone role gets the first application.
        # After that, the applied roles that the user has in the channel
        # (or otherwise) are then OR'd together.
        # After the role permissions are resolved, the member permissions
        # have to take into effect.
        # After all that is done.. you have to do the following:

        # The operation first takes into consideration the denied
        # and then the allowed.

        # Timeouted users have only view_channel and read_message_history
        # if they already have them.
        if ignore_timeout is not MISSING and isinstance(obj, Role):
            raise TypeError("ignore_timeout is only supported for disnake.Member objects")

        if ignore_timeout is MISSING:
            ignore_timeout = False

        if self.guild.owner_id == obj.id:
            return Permissions.all()

        default = self.guild.default_role
        base = Permissions(default.permissions.value)

        # Handle the role case first
        if isinstance(obj, Role):
            base.value |= obj._permissions

            if base.administrator:
                return Permissions.all()

            # Apply @everyone allow/deny first since it's special
            try:
                maybe_everyone = self._overwrites[0]
                if maybe_everyone.id == self.guild.id:
                    base.handle_overwrite(allow=maybe_everyone.allow, deny=maybe_everyone.deny)
            except IndexError:
                pass

            if obj.is_default():
                return base

            overwrite = utils.get(self._overwrites, type=_Overwrites.ROLE, id=obj.id)
            if overwrite is not None:
                base.handle_overwrite(overwrite.allow, overwrite.deny)

            return base

        roles = obj._roles
        get_role = self.guild.get_role

        # Apply guild roles that the member has.
        for role_id in roles:
            role = get_role(role_id)
            if role is not None:
                base.value |= role._permissions

        # Guild-wide Administrator -> True for everything
        # Bypass all channel-specific overrides
        if base.administrator:
            return Permissions.all()

        # Apply @everyone allow/deny first since it's special
        try:
            maybe_everyone = self._overwrites[0]
            if maybe_everyone.id == self.guild.id:
                base.handle_overwrite(allow=maybe_everyone.allow, deny=maybe_everyone.deny)
                remaining_overwrites = self._overwrites[1:]
            else:
                remaining_overwrites = self._overwrites
        except IndexError:
            remaining_overwrites = self._overwrites

        denies = 0
        allows = 0

        # Apply channel specific role permission overwrites
        for overwrite in remaining_overwrites:
            if overwrite.is_role() and roles.has(overwrite.id):
                denies |= overwrite.deny
                allows |= overwrite.allow

        base.handle_overwrite(allow=allows, deny=denies)

        # Apply member specific permission overwrites
        for overwrite in remaining_overwrites:
            if overwrite.is_member() and overwrite.id == obj.id:
                base.handle_overwrite(allow=overwrite.allow, deny=overwrite.deny)
                break

        # if you can't send a message in a channel then you can't have certain
        # permissions as well
        if not base.send_messages:
            base.send_tts_messages = False
            base.mention_everyone = False
            base.embed_links = False
            base.attach_files = False

        # if you can't view a channel then you have no permissions there
        if not base.view_channel:
            denied = Permissions.all_channel()
            base.value &= ~denied.value

        # if you have a timeout then you can't have any permissions
        # except read messages and read message history
        if not ignore_timeout and obj.current_timeout:
            denied = Permissions(view_channel=True, read_message_history=True)
            base.value &= denied.value

        return base

    async def delete(self, *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes the channel.

        You must have :attr:`.Permissions.manage_channels` permission to do this.

        Parameters
        ----------
        reason: Optional[:class:`str`]
            The reason for deleting this channel. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have proper permissions to delete the channel.
        NotFound
            The channel was not found or was already deleted.
        HTTPException
            Deleting the channel failed.
        """
        await self._state.http.delete_channel(self.id, reason=reason)

    @overload
    async def set_permissions(
        self,
        target: Union[Member, Role],
        *,
        overwrite: Optional[PermissionOverwrite] = ...,
        reason: Optional[str] = ...,
    ) -> None:
        ...

    @overload
    @_overload_with_permissions
    async def set_permissions(
        self,
        target: Union[Member, Role],
        *,
        reason: Optional[str] = ...,
        add_reactions: Optional[bool] = ...,
        administrator: Optional[bool] = ...,
        attach_files: Optional[bool] = ...,
        ban_members: Optional[bool] = ...,
        change_nickname: Optional[bool] = ...,
        connect: Optional[bool] = ...,
        create_forum_threads: Optional[bool] = ...,
        create_instant_invite: Optional[bool] = ...,
        create_private_threads: Optional[bool] = ...,
        create_public_threads: Optional[bool] = ...,
        deafen_members: Optional[bool] = ...,
        embed_links: Optional[bool] = ...,
        external_emojis: Optional[bool] = ...,
        external_stickers: Optional[bool] = ...,
        kick_members: Optional[bool] = ...,
        manage_channels: Optional[bool] = ...,
        manage_emojis: Optional[bool] = ...,
        manage_emojis_and_stickers: Optional[bool] = ...,
        manage_events: Optional[bool] = ...,
        manage_guild: Optional[bool] = ...,
        manage_guild_expressions: Optional[bool] = ...,
        manage_messages: Optional[bool] = ...,
        manage_nicknames: Optional[bool] = ...,
        manage_permissions: Optional[bool] = ...,
        manage_roles: Optional[bool] = ...,
        manage_threads: Optional[bool] = ...,
        manage_webhooks: Optional[bool] = ...,
        mention_everyone: Optional[bool] = ...,
        moderate_members: Optional[bool] = ...,
        move_members: Optional[bool] = ...,
        mute_members: Optional[bool] = ...,
        priority_speaker: Optional[bool] = ...,
        read_message_history: Optional[bool] = ...,
        read_messages: Optional[bool] = ...,
        request_to_speak: Optional[bool] = ...,
        send_messages: Optional[bool] = ...,
        send_messages_in_threads: Optional[bool] = ...,
        send_tts_messages: Optional[bool] = ...,
        speak: Optional[bool] = ...,
        start_embedded_activities: Optional[bool] = ...,
        stream: Optional[bool] = ...,
        use_application_commands: Optional[bool] = ...,
        use_embedded_activities: Optional[bool] = ...,
        use_external_emojis: Optional[bool] = ...,
        use_external_stickers: Optional[bool] = ...,
        use_slash_commands: Optional[bool] = ...,
        use_soundboard: Optional[bool] = ...,
        use_voice_activation: Optional[bool] = ...,
        view_audit_log: Optional[bool] = ...,
        view_channel: Optional[bool] = ...,
        view_creator_monetization_analytics: Optional[bool] = ...,
        view_guild_insights: Optional[bool] = ...,
    ) -> None:
        ...

    async def set_permissions(
        self,
        target,
        *,
        overwrite: Optional[PermissionOverwrite] = MISSING,
        reason: Optional[str] = None,
        **permissions,
    ) -> None:
        """|coro|

        Sets the channel specific permission overwrites for a target in the
        channel.

        The ``target`` parameter should either be a :class:`.Member` or a
        :class:`.Role` that belongs to guild.

        The ``overwrite`` parameter, if given, must either be ``None`` or
        :class:`.PermissionOverwrite`. For convenience, you can pass in
        keyword arguments denoting :class:`.Permissions` attributes. If this is
        done, then you cannot mix the keyword arguments with the ``overwrite``
        parameter.

        If the ``overwrite`` parameter is ``None``, then the permission
        overwrites are deleted.

        You must have :attr:`.Permissions.manage_roles` permission to do this.

        .. note::

            This method *replaces* the old overwrites with the ones given.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` instead of ``InvalidArgument``.

        Examples
        --------
        Setting allow and deny: ::

            await message.channel.set_permissions(message.author, view_channel=True,
                                                                  send_messages=False)

        Deleting overwrites ::

            await channel.set_permissions(member, overwrite=None)

        Using :class:`.PermissionOverwrite` ::

            overwrite = disnake.PermissionOverwrite()
            overwrite.send_messages = False
            overwrite.view_channel = True
            await channel.set_permissions(member, overwrite=overwrite)

        Parameters
        ----------
        target: Union[:class:`.Member`, :class:`.Role`]
            The member or role to overwrite permissions for.
        overwrite: Optional[:class:`.PermissionOverwrite`]
            The permissions to allow and deny to the target, or ``None`` to
            delete the overwrite.
        **permissions
            A keyword argument list of permissions to set for ease of use.
            Cannot be mixed with ``overwrite``.
        reason: Optional[:class:`str`]
            The reason for doing this action. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have permissions to edit channel specific permissions.
        HTTPException
            Editing channel specific permissions failed.
        NotFound
            The role or member being edited is not part of the guild.
        TypeError
            ``overwrite`` is invalid,
            the target type was not :class:`.Role` or :class:`.Member`,
            both keyword arguments and ``overwrite`` were provided,
            or invalid permissions were provided as keyword arguments.
        """
        http = self._state.http

        if isinstance(target, User):
            perm_type = _Overwrites.MEMBER
        elif isinstance(target, Role):
            perm_type = _Overwrites.ROLE
        else:
            raise TypeError("target parameter must be either Member or Role")

        if overwrite is MISSING:
            if len(permissions) == 0:
                raise TypeError("No overwrite provided.")
            try:
                overwrite = PermissionOverwrite(**permissions)
            except (ValueError, TypeError) as e:
                raise TypeError("Invalid permissions given to keyword arguments.") from e
        else:
            if len(permissions) > 0:
                raise TypeError("Cannot mix overwrite and keyword arguments.")

        # TODO: wait for event

        if overwrite is None:
            await http.delete_channel_permissions(self.id, target.id, reason=reason)
        elif isinstance(overwrite, PermissionOverwrite):
            (allow, deny) = overwrite.pair()
            await http.edit_channel_permissions(
                self.id, target.id, allow.value, deny.value, perm_type, reason=reason
            )
        else:
            raise TypeError("Invalid overwrite type provided.")

    async def _clone_impl(
        self,
        base_attrs: Dict[str, Any],
        *,
        name: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Self:
        base_attrs["permission_overwrites"] = [x._asdict() for x in self._overwrites]
        base_attrs["parent_id"] = self.category_id
        base_attrs["name"] = name or self.name
        guild_id = self.guild.id
        cls = self.__class__
        data = await self._state.http.create_channel(
            guild_id, self.type.value, reason=reason, **base_attrs
        )
        obj = cls(state=self._state, guild=self.guild, data=data)

        # temporarily add it to the cache
        self.guild._channels[obj.id] = obj  # type: ignore
        return obj

    async def clone(self, *, name: Optional[str] = None, reason: Optional[str] = None) -> Self:
        """|coro|

        Clones this channel. This creates a channel with the same properties
        as this channel.

        You must have :attr:`.Permissions.manage_channels` permission to
        do this.

        .. versionadded:: 1.1

        Parameters
        ----------
        name: Optional[:class:`str`]
            The name of the new channel. If not provided, defaults to this channel name.
        reason: Optional[:class:`str`]
            The reason for cloning this channel. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.

        Returns
        -------
        :class:`.abc.GuildChannel`
            The channel that was created.
        """
        raise NotImplementedError

    @overload
    async def move(
        self,
        *,
        beginning: bool,
        offset: int = ...,
        category: Optional[Snowflake] = ...,
        sync_permissions: bool = ...,
        reason: Optional[str] = ...,
    ) -> None:
        ...

    @overload
    async def move(
        self,
        *,
        end: bool,
        offset: int = ...,
        category: Optional[Snowflake] = ...,
        sync_permissions: bool = ...,
        reason: Optional[str] = ...,
    ) -> None:
        ...

    @overload
    async def move(
        self,
        *,
        before: Snowflake,
        offset: int = ...,
        category: Optional[Snowflake] = ...,
        sync_permissions: bool = ...,
        reason: Optional[str] = ...,
    ) -> None:
        ...

    @overload
    async def move(
        self,
        *,
        after: Snowflake,
        offset: int = ...,
        category: Optional[Snowflake] = ...,
        sync_permissions: bool = ...,
        reason: Optional[str] = ...,
    ) -> None:
        ...

    async def move(self, **kwargs) -> None:
        """|coro|

        A rich interface to help move a channel relative to other channels.

        If exact position movement is required, ``edit`` should be used instead.

        You must have :attr:`.Permissions.manage_channels` permission to
        do this.

        .. note::

            Voice channels will always be sorted below text channels.
            This is a Discord limitation.

        .. versionadded:: 1.7

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` or :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        beginning: :class:`bool`
            Whether to move the channel to the beginning of the
            channel list (or category if given).
            This is mutually exclusive with ``end``, ``before``, and ``after``.
        end: :class:`bool`
            Whether to move the channel to the end of the
            channel list (or category if given).
            This is mutually exclusive with ``beginning``, ``before``, and ``after``.
        before: :class:`.abc.Snowflake`
            The channel that should be before our current channel.
            This is mutually exclusive with ``beginning``, ``end``, and ``after``.
        after: :class:`.abc.Snowflake`
            The channel that should be after our current channel.
            This is mutually exclusive with ``beginning``, ``end``, and ``before``.
        offset: :class:`int`
            The number of channels to offset the move by. For example,
            an offset of ``2`` with ``beginning=True`` would move
            it 2 after the beginning. A positive number moves it below
            while a negative number moves it above. Note that this
            number is relative and computed after the ``beginning``,
            ``end``, ``before``, and ``after`` parameters.
        category: Optional[:class:`.abc.Snowflake`]
            The category to move this channel under.
            If ``None`` is given then it moves it out of the category.
            This parameter is ignored if moving a category channel.
        sync_permissions: :class:`bool`
            Whether to sync the permissions with the category (if given).
        reason: Optional[:class:`str`]
            The reason for moving this channel. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have permissions to move the channel.
        HTTPException
            Moving the channel failed.
        TypeError
            A bad mix of arguments were passed.
        ValueError
            An invalid position was given.
        """
        if not kwargs:
            return

        beginning, end = kwargs.get("beginning"), kwargs.get("end")
        before, after = kwargs.get("before"), kwargs.get("after")
        offset = kwargs.get("offset", 0)
        if sum(bool(a) for a in (beginning, end, before, after)) > 1:
            raise TypeError("Only one of [before, after, end, beginning] can be used.")

        bucket = self._sorting_bucket
        parent_id = kwargs.get("category", MISSING)
        if parent_id not in (MISSING, None):
            parent_id = parent_id.id
            channels = [
                ch
                for ch in self.guild.channels
                if ch._sorting_bucket == bucket and ch.category_id == parent_id
            ]
        else:
            channels = [
                ch
                for ch in self.guild.channels
                if ch._sorting_bucket == bucket and ch.category_id == self.category_id
            ]

        channels.sort(key=lambda c: (c.position, c.id))
        channels = cast(List[GuildChannel], channels)

        try:
            # Try to remove ourselves from the channel list
            channels.remove(self)
        except ValueError:
            # If we're not there then it's probably due to not being in the category
            pass

        index = None
        if beginning:
            index = 0
        elif end:
            index = len(channels)
        elif before:
            index = next((i for i, c in enumerate(channels) if c.id == before.id), None)
        elif after:
            index = next((i + 1 for i, c in enumerate(channels) if c.id == after.id), None)

        if index is None:
            raise ValueError("Could not resolve appropriate move position")

        channels.insert(max((index + offset), 0), self)
        payload = []
        lock_permissions = kwargs.get("sync_permissions", False)
        reason = kwargs.get("reason")
        for index, channel in enumerate(channels):
            d = {"id": channel.id, "position": index}
            if parent_id is not MISSING and channel.id == self.id:
                d.update(parent_id=parent_id, lock_permissions=lock_permissions)
            payload.append(d)

        await self._state.http.bulk_channel_update(self.guild.id, payload, reason=reason)

    async def create_invite(
        self,
        *,
        reason: Optional[str] = None,
        max_age: int = 0,
        max_uses: int = 0,
        temporary: bool = False,
        unique: bool = True,
        target_type: Optional[InviteTarget] = None,
        target_user: Optional[User] = None,
        target_application: Optional[PartyType] = None,
        guild_scheduled_event: Optional[GuildScheduledEvent] = None,
    ) -> Invite:
        """|coro|

        Creates an instant invite from a text or voice channel.

        You must have :attr:`.Permissions.create_instant_invite` permission to
        do this.

        Parameters
        ----------
        max_age: :class:`int`
            How long the invite should last in seconds. If it's 0 then the invite
            doesn't expire. Defaults to ``0``.
        max_uses: :class:`int`
            How many uses the invite could be used for. If it's 0 then there
            are unlimited uses. Defaults to ``0``.
        temporary: :class:`bool`
            Whether the invite grants temporary membership
            (i.e. they get kicked after they disconnect). Defaults to ``False``.
        unique: :class:`bool`
            Whether a unique invite URL should be created. Defaults to ``True``.
            If this is set to ``False`` then it will return a previously created
            invite.
        target_type: Optional[:class:`.InviteTarget`]
            The type of target for the voice channel invite, if any.

            .. versionadded:: 2.0

        target_user: Optional[:class:`User`]
            The user whose stream to display for this invite, required if `target_type` is `TargetType.stream`.
            The user must be streaming in the channel.

            .. versionadded:: 2.0

        target_application: Optional[:class:`.PartyType`]
            The ID of the embedded application for the invite, required if `target_type` is `TargetType.embedded_application`.

            .. versionadded:: 2.0

        guild_scheduled_event: Optional[:class:`.GuildScheduledEvent`]
            The guild scheduled event to include with the invite.

            .. versionadded:: 2.3

        reason: Optional[:class:`str`]
            The reason for creating this invite. Shows up on the audit log.

        Raises
        ------
        HTTPException
            Invite creation failed.
        NotFound
            The channel that was passed is a category or an invalid channel.

        Returns
        -------
        :class:`.Invite`
            The newly created invite.
        """
        data = await self._state.http.create_invite(
            self.id,
            reason=reason,
            max_age=max_age,
            max_uses=max_uses,
            temporary=temporary,
            unique=unique,
            target_type=try_enum_to_int(target_type),
            target_user_id=target_user.id if target_user else None,
            target_application_id=try_enum_to_int(target_application),
        )
        invite = Invite.from_incomplete(data=data, state=self._state)
        invite.guild_scheduled_event = guild_scheduled_event
        return invite

    async def invites(self) -> List[Invite]:
        """|coro|

        Returns a list of all active instant invites from this channel.

        You must have :attr:`.Permissions.manage_channels` permission to use this.

        Raises
        ------
        Forbidden
            You do not have proper permissions to get the information.
        HTTPException
            An error occurred while fetching the information.

        Returns
        -------
        List[:class:`.Invite`]
            The list of invites that are currently active.
        """
        state = self._state
        data = await state.http.invites_from_channel(self.id)
        guild = self.guild
        return [Invite(state=state, data=invite, channel=self, guild=guild) for invite in data]


class Messageable:
    """An ABC that details the common operations on a model that can send messages.

    The following classes implement this ABC:

    - :class:`~disnake.TextChannel`
    - :class:`~disnake.DMChannel`
    - :class:`~disnake.GroupChannel`
    - :class:`~disnake.User`
    - :class:`~disnake.Member`
    - :class:`~disnake.Thread`
    - :class:`~disnake.VoiceChannel`
    - :class:`~disnake.StageChannel`
    - :class:`~disnake.ext.commands.Context`
    - :class:`~disnake.PartialMessageable`
    """

    __slots__ = ()
    _state: ConnectionState

    async def _get_channel(self) -> MessageableChannel:
        raise NotImplementedError

    @overload
    async def send(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embed: Embed = ...,
        file: File = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        suppress_embeds: bool = ...,
        flags: MessageFlags = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        components: Components[MessageUIComponent] = ...,
    ) -> Message:
        ...

    @overload
    async def send(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embed: Embed = ...,
        files: List[File] = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        suppress_embeds: bool = ...,
        flags: MessageFlags = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        components: Components[MessageUIComponent] = ...,
    ) -> Message:
        ...

    @overload
    async def send(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embeds: List[Embed] = ...,
        file: File = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        suppress_embeds: bool = ...,
        flags: MessageFlags = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        components: Components[MessageUIComponent] = ...,
    ) -> Message:
        ...

    @overload
    async def send(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embeds: List[Embed] = ...,
        files: List[File] = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        suppress_embeds: bool = ...,
        flags: MessageFlags = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        components: Components[MessageUIComponent] = ...,
    ) -> Message:
        ...

    async def send(
        self,
        content: Optional[str] = None,
        *,
        tts: bool = False,
        embed: Optional[Embed] = None,
        embeds: Optional[List[Embed]] = None,
        file: Optional[File] = None,
        files: Optional[List[File]] = None,
        stickers: Optional[Sequence[Union[GuildSticker, StickerItem]]] = None,
        delete_after: Optional[float] = None,
        nonce: Optional[Union[str, int]] = None,
        suppress_embeds: Optional[bool] = None,
        flags: Optional[MessageFlags] = None,
        allowed_mentions: Optional[AllowedMentions] = None,
        reference: Optional[Union[Message, MessageReference, PartialMessage]] = None,
        mention_author: Optional[bool] = None,
        view: Optional[View] = None,
        components: Optional[Components[MessageUIComponent]] = None,
    ):
        """|coro|

        Sends a message to the destination with the content given.

        The content must be a type that can convert to a string through ``str(content)``.

        At least one of ``content``, ``embed``/``embeds``, ``file``/``files``,
        ``stickers``, ``components``, or ``view`` must be provided.

        To upload a single file, the ``file`` parameter should be used with a
        single :class:`.File` object. To upload multiple files, the ``files``
        parameter should be used with a :class:`list` of :class:`.File` objects.
        **Specifying both parameters will lead to an exception**.

        To upload a single embed, the ``embed`` parameter should be used with a
        single :class:`.Embed` object. To upload multiple embeds, the ``embeds``
        parameter should be used with a :class:`list` of :class:`.Embed` objects.
        **Specifying both parameters will lead to an exception**.

        .. versionchanged:: 2.6
            Raises :exc:`TypeError` or :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        content: Optional[:class:`str`]
            The content of the message to send.
        tts: :class:`bool`
            Whether the message should be sent using text-to-speech.
        embed: :class:`.Embed`
            The rich embed for the content to send. This cannot be mixed with the
            ``embeds`` parameter.
        embeds: List[:class:`.Embed`]
            A list of embeds to send with the content. Must be a maximum of 10.
            This cannot be mixed with the ``embed`` parameter.

            .. versionadded:: 2.0

        file: :class:`.File`
            The file to upload. This cannot be mixed with the ``files`` parameter.
        files: List[:class:`.File`]
            A list of files to upload. Must be a maximum of 10.
            This cannot be mixed with the ``file`` parameter.
        stickers: Sequence[Union[:class:`.GuildSticker`, :class:`.StickerItem`]]
            A list of stickers to upload. Must be a maximum of 3.

            .. versionadded:: 2.0

        nonce: Union[:class:`str`, :class:`int`]
            The nonce to use for sending this message. If the message was successfully sent,
            then the message will have a nonce with this value.
        delete_after: :class:`float`
            If provided, the number of seconds to wait in the background
            before deleting the message we just sent. If the deletion fails,
            then it is silently ignored.
        allowed_mentions: :class:`.AllowedMentions`
            Controls the mentions being processed in this message. If this is
            passed, then the object is merged with :attr:`.Client.allowed_mentions`.
            The merging behaviour only overrides attributes that have been explicitly passed
            to the object, otherwise it uses the attributes set in :attr:`.Client.allowed_mentions`.
            If no object is passed at all then the defaults given by :attr:`.Client.allowed_mentions`
            are used instead.

            .. versionadded:: 1.4

        reference: Union[:class:`.Message`, :class:`.MessageReference`, :class:`.PartialMessage`]
            A reference to the :class:`.Message` to which you are replying, this can be created using
            :meth:`.Message.to_reference` or passed directly as a :class:`.Message`. You can control
            whether this mentions the author of the referenced message using the :attr:`.AllowedMentions.replied_user`
            attribute of ``allowed_mentions`` or by setting ``mention_author``.

            .. versionadded:: 1.6

        mention_author: Optional[:class:`bool`]
            If set, overrides the :attr:`.AllowedMentions.replied_user` attribute of ``allowed_mentions``.

            .. versionadded:: 1.6

        view: :class:`.ui.View`
            A Discord UI View to add to the message. This cannot be mixed with ``components``.

            .. versionadded:: 2.0

        components: |components_type|
            A list of components to include in the message. This cannot be mixed with ``view``.

            .. versionadded:: 2.4

        suppress_embeds: :class:`bool`
            Whether to suppress embeds for the message. This hides
            all the embeds from the UI if set to ``True``.

            .. versionadded:: 2.5

        flags: :class:`.MessageFlags`
            The flags to set for this message.
            Only :attr:`~.MessageFlags.suppress_embeds` and :attr:`~.MessageFlags.suppress_notifications`
            are supported.

            If parameter ``suppress_embeds`` is provided,
            that will override the setting of :attr:`.MessageFlags.suppress_embeds`.

            .. versionadded:: 2.9

        Raises
        ------
        HTTPException
            Sending the message failed.
        Forbidden
            You do not have the proper permissions to send the message.
        TypeError
            Specified both ``file`` and ``files``,
            or you specified both ``embed`` and ``embeds``,
            or you specified both ``view`` and ``components``,
            or the ``reference`` object is not a :class:`.Message`,
            :class:`.MessageReference` or :class:`.PartialMessage`.
        ValueError
            The ``files`` or ``embeds`` list is too large.

        Returns
        -------
        :class:`.Message`
            The message that was sent.
        """
        channel = await self._get_channel()
        state = self._state
        content = str(content) if content is not None else None

        if file is not None and files is not None:
            raise TypeError("cannot pass both file and files parameter to send()")

        if file is not None:
            if not isinstance(file, File):
                raise TypeError("file parameter must be File")
            files = [file]

        if embed is not None and embeds is not None:
            raise TypeError("cannot pass both embed and embeds parameter to send()")

        if embed is not None:
            embeds = [embed]

        embeds_payload = None
        if embeds is not None:
            if len(embeds) > 10:
                raise ValueError("embeds parameter must be a list of up to 10 elements")
            for embed in embeds:
                if embed._files:
                    files = files or []
                    files.extend(embed._files.values())
            embeds_payload = [embed.to_dict() for embed in embeds]

        stickers_payload = None
        if stickers is not None:
            stickers_payload = [sticker.id for sticker in stickers]

        allowed_mentions_payload = None
        if allowed_mentions is None:
            allowed_mentions_payload = state.allowed_mentions and state.allowed_mentions.to_dict()
        elif state.allowed_mentions is not None:
            allowed_mentions_payload = state.allowed_mentions.merge(allowed_mentions).to_dict()
        else:
            allowed_mentions_payload = allowed_mentions.to_dict()

        if mention_author is not None:
            allowed_mentions_payload = allowed_mentions_payload or AllowedMentions().to_dict()
            allowed_mentions_payload["replied_user"] = bool(mention_author)

        reference_payload = None
        if reference is not None:
            try:
                reference_payload = reference.to_message_reference_dict()
            except AttributeError:
                raise TypeError(
                    "reference parameter must be Message, MessageReference, or PartialMessage"
                ) from None

        if view is not None and components is not None:
            raise TypeError("cannot pass both view and components parameter to send()")

        if view:
            if not hasattr(view, "__discord_ui_view__"):
                raise TypeError(f"view parameter must be View not {view.__class__!r}")

            components_payload = view.to_components()

        elif components:
            components_payload = components_to_dict(components)

        else:
            components_payload = None

        flags_payload = None
        if suppress_embeds is not None:
            flags = MessageFlags._from_value(0 if flags is None else flags.value)
            flags.suppress_embeds = suppress_embeds
        if flags is not None:
            flags_payload = flags.value

        if files is not None:
            if len(files) > 10:
                raise ValueError("files parameter must be a list of up to 10 elements")
            if not all(isinstance(file, File) for file in files):
                raise TypeError("files parameter must be a list of File")

            try:
                data = await state.http.send_files(
                    channel.id,
                    files=files,
                    content=content,
                    tts=tts,
                    embeds=embeds_payload,
                    nonce=nonce,
                    allowed_mentions=allowed_mentions_payload,
                    message_reference=reference_payload,
                    stickers=stickers_payload,
                    components=components_payload,
                    flags=flags_payload,
                )
            finally:
                for f in files:
                    f.close()
        else:
            data = await state.http.send_message(
                channel.id,
                content,
                tts=tts,
                embeds=embeds_payload,
                nonce=nonce,
                allowed_mentions=allowed_mentions_payload,
                message_reference=reference_payload,
                stickers=stickers_payload,
                components=components_payload,
                flags=flags_payload,
            )

        ret = state.create_message(channel=channel, data=data)
        if view:
            state.store_view(view, ret.id)

        if delete_after is not None:
            await ret.delete(delay=delete_after)
        return ret

    async def trigger_typing(self) -> None:
        """|coro|

        Triggers a *typing* indicator to the destination.

        *Typing* indicator will go away after 10 seconds, or after a message is sent.
        """
        channel = await self._get_channel()
        await self._state.http.send_typing(channel.id)

    def typing(self) -> Typing:
        """Returns a context manager that allows you to type for an indefinite period of time.

        This is useful for denoting long computations in your bot.

        .. note::

            This is both a regular context manager and an async context manager.
            This means that both ``with`` and ``async with`` work with this.

        Example Usage: ::

            async with channel.typing():
                # simulate something heavy
                await asyncio.sleep(10)

            await channel.send('done!')

        """
        return Typing(self)

    async def fetch_message(self, id: int, /) -> Message:
        """|coro|

        Retrieves a single :class:`.Message` from the destination.

        Parameters
        ----------
        id: :class:`int`
            The message ID to look for.

        Raises
        ------
        NotFound
            The specified message was not found.
        Forbidden
            You do not have the permissions required to get a message.
        HTTPException
            Retrieving the message failed.

        Returns
        -------
        :class:`.Message`
            The message asked for.
        """
        channel = await self._get_channel()
        data = await self._state.http.get_message(channel.id, id)
        return self._state.create_message(channel=channel, data=data)

    async def pins(self) -> List[Message]:
        """|coro|

        Retrieves all messages that are currently pinned in the channel.

        .. note::

            Due to a limitation with the Discord API, the :class:`.Message`
            objects returned by this method do not contain complete
            :attr:`.Message.reactions` data.

        Raises
        ------
        HTTPException
            Retrieving the pinned messages failed.

        Returns
        -------
        List[:class:`.Message`]
            The messages that are currently pinned.
        """
        channel = await self._get_channel()
        state = self._state
        data = await state.http.pins_from(channel.id)
        return [state.create_message(channel=channel, data=m) for m in data]

    def history(
        self,
        *,
        limit: Optional[int] = 100,
        before: Optional[SnowflakeTime] = None,
        after: Optional[SnowflakeTime] = None,
        around: Optional[SnowflakeTime] = None,
        oldest_first: Optional[bool] = None,
    ) -> HistoryIterator:
        """Returns an :class:`.AsyncIterator` that enables receiving the destination's message history.

        You must have :attr:`.Permissions.read_message_history` permission to use this.

        Examples
        --------
        Usage ::

            counter = 0
            async for message in channel.history(limit=200):
                if message.author == client.user:
                    counter += 1

        Flattening into a list: ::

            messages = await channel.history(limit=123).flatten()
            # messages is now a list of Message...

        All parameters are optional.

        Parameters
        ----------
        limit: Optional[:class:`int`]
            The number of messages to retrieve.
            If ``None``, retrieves every message in the channel. Note, however,
            that this would make it a slow operation.
        before: Optional[Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve messages before this date or message.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        after: Optional[Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve messages after this date or message.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        around: Optional[Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve messages around this date or message.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
            When using this argument, the maximum limit is 101. Note that if the limit is an
            even number then this will return at most limit + 1 messages.
        oldest_first: Optional[:class:`bool`]
            If set to ``True``, return messages in oldest->newest order. Defaults to ``True`` if
            ``after`` is specified, otherwise ``False``.

        Raises
        ------
        Forbidden
            You do not have permissions to get channel message history.
        HTTPException
            The request to get message history failed.

        Yields
        ------
        :class:`.Message`
            The message with the message data parsed.
        """
        from .iterators import HistoryIterator  # cyclic import

        return HistoryIterator(
            self, limit=limit, before=before, after=after, around=around, oldest_first=oldest_first
        )


class Connectable(Protocol):
    """An ABC that details the common operations on a channel that can
    connect to a voice server.

    The following classes implement this ABC:

    - :class:`~disnake.VoiceChannel`
    - :class:`~disnake.StageChannel`

    Note
    ----
    This ABC is not decorated with :func:`typing.runtime_checkable`, so will fail :func:`isinstance`/:func:`issubclass`
    checks.
    """

    __slots__ = ()
    _state: ConnectionState
    guild: Guild
    id: int

    def _get_voice_client_key(self) -> Tuple[int, str]:
        raise NotImplementedError

    def _get_voice_state_pair(self) -> Tuple[int, int]:
        raise NotImplementedError

    async def connect(
        self,
        *,
        timeout: float = 60.0,
        reconnect: bool = True,
        cls: Callable[[Client, Connectable], VoiceProtocolT] = VoiceClient,
    ) -> VoiceProtocolT:
        """|coro|

        Connects to voice and creates a :class:`VoiceClient` to establish
        your connection to the voice server.

        This requires :attr:`Intents.voice_states`.

        Parameters
        ----------
        timeout: :class:`float`
            The timeout in seconds to wait for the voice endpoint.
        reconnect: :class:`bool`
            Whether the bot should automatically attempt
            a reconnect if a part of the handshake fails
            or the gateway goes down.
        cls: Type[:class:`VoiceProtocol`]
            A type that subclasses :class:`VoiceProtocol` to connect with.
            Defaults to :class:`VoiceClient`.

        Raises
        ------
        asyncio.TimeoutError
            Could not connect to the voice channel in time.
        ClientException
            You are already connected to a voice channel.
        opus.OpusNotLoaded
            The opus library has not been loaded.

        Returns
        -------
        :class:`VoiceProtocol`
            A voice client that is fully connected to the voice server.
        """
        key_id, _ = self._get_voice_client_key()
        state = self._state

        if state._get_voice_client(key_id):
            raise ClientException("Already connected to a voice channel.")

        client = state._get_client()
        voice = cls(client, self)

        if not isinstance(voice, VoiceProtocol):
            raise TypeError("Type must meet VoiceProtocol abstract base class.")

        state._add_voice_client(key_id, voice)

        try:
            await voice.connect(timeout=timeout, reconnect=reconnect)
        except asyncio.TimeoutError:
            try:
                await voice.disconnect(force=True)
            except Exception:
                # we don't care if disconnect failed because connection failed
                pass
            raise  # re-raise

        return voice
