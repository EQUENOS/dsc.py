# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    List,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)

from .. import utils
from ..app_commands import OptionChoice
from ..channel import PartialMessageable
from ..entitlement import Entitlement
from ..enums import (
    ComponentType,
    InteractionResponseType,
    InteractionType,
    Locale,
    OptionType,
    WebhookType,
    try_enum,
)
from ..errors import (
    HTTPException,
    InteractionNotEditable,
    InteractionNotResponded,
    InteractionResponded,
    InteractionTimedOut,
    ModalChainNotSupported,
    NotFound,
)
from ..flags import MessageFlags
from ..guild import Guild, PartialInteractionGuild
from ..i18n import Localized
from ..member import Member
from ..message import Attachment, Message
from ..object import Object
from ..permissions import Permissions
from ..role import Role
from ..ui.action_row import components_to_dict
from ..user import ClientUser, User
from ..webhook.async_ import Webhook, async_context, handle_message_parameters

__all__ = (
    "Interaction",
    "InteractionMessage",
    "InteractionResponse",
    "InteractionDataResolved",
)

if TYPE_CHECKING:
    from datetime import datetime

    from aiohttp import ClientSession

    from ..abc import AnyChannel, MessageableChannel
    from ..app_commands import Choices
    from ..client import Client
    from ..embeds import Embed
    from ..ext.commands import AutoShardedBot, Bot
    from ..file import File
    from ..mentions import AllowedMentions
    from ..poll import Poll
    from ..state import ConnectionState
    from ..types.components import Modal as ModalPayload
    from ..types.guild import PartialGuild as PartialGuildPayload
    from ..types.interactions import (
        ApplicationCommandOptionChoice as ApplicationCommandOptionChoicePayload,
        Interaction as InteractionPayload,
        InteractionDataResolved as InteractionDataResolvedPayload,
    )
    from ..types.snowflake import Snowflake
    from ..ui.action_row import Components, MessageUIComponent, ModalUIComponent
    from ..ui.modal import Modal
    from ..ui.view import View
    from .message import MessageInteraction
    from .modal import ModalInteraction

    AnyBot = Union[Bot, AutoShardedBot]


MISSING: Any = utils.MISSING

T = TypeVar("T")
ClientT = TypeVar("ClientT", bound="Client", covariant=True)


class Interaction(Generic[ClientT]):
    """A base class representing a user-initiated Discord interaction.

    An interaction happens when a user performs an action that the client needs to
    be notified of. Current examples are application commands and components.

    .. versionadded:: 2.0

    Attributes
    ----------
    data: Mapping[:class:`str`, Any]
        The interaction's raw data. This might be replaced with a more processed version in subclasses.
    id: :class:`int`
        The interaction's ID.
    type: :class:`InteractionType`
        The interaction's type.
    application_id: :class:`int`
        The application ID that the interaction was for.
    guild_id: Optional[:class:`int`]
        The guild ID the interaction was sent from.
    guild_locale: Optional[:class:`Locale`]
        The selected language of the interaction's guild.
        This value is only meaningful in guilds with ``COMMUNITY`` feature and receives a default value otherwise.
        If the interaction was in a DM, then this value is ``None``.

        .. versionadded:: 2.4

        .. versionchanged:: 2.5
            Changed to :class:`Locale` instead of :class:`str`.

    channel: Union[:class:`abc.GuildChannel`, :class:`Thread`, :class:`abc.PrivateChannel`, :class:`PartialMessageable`]
        The channel the interaction was sent from.

        Note that due to a Discord limitation, DM channels
        may not contain recipient information.
        Unknown channel types will be :class:`PartialMessageable`.

        .. versionchanged:: 2.10
            If the interaction was sent from a thread and the bot cannot normally access the thread,
            this is now a proper :class:`Thread` object.
            Private channels are now proper :class:`DMChannel`/:class:`GroupChannel`
            objects instead of :class:`PartialMessageable`.

        .. note::
            If you want to compute the interaction author's or bot's permissions in the channel,
            consider using :attr:`permissions` or :attr:`app_permissions`.

    author: Union[:class:`User`, :class:`Member`]
        The user or member that sent the interaction.
    locale: :class:`Locale`
        The selected language of the interaction's author.

        .. versionadded:: 2.4

        .. versionchanged:: 2.5
            Changed to :class:`Locale` instead of :class:`str`.

    token: :class:`str`
        The token to continue the interaction. These are valid for 15 minutes.
    client: :class:`Client`
        The interaction client.
    entitlements: List[:class:`Entitlement`]
        The entitlements for the invoking user and guild,
        representing access to an application subscription.

        .. versionadded:: 2.10
    """

    __slots__: Tuple[str, ...] = (
        "data",
        "id",
        "type",
        "guild_id",
        "channel",
        "application_id",
        "author",
        "token",
        "version",
        "locale",
        "guild_locale",
        "client",
        "entitlements",
        "_app_permissions",
        "_permissions",
        "_state",
        "_session",
        "_original_response",
        "_guild",
        "_cs_response",
        "_cs_followup",
        "_cs_me",
        "_cs_expires_at",
    )

    def __init__(self, *, data: InteractionPayload, state: ConnectionState) -> None:
        self.data: Mapping[str, Any] = data.get("data") or {}
        self._state: ConnectionState = state
        # TODO: Maybe use a unique session
        self._session: ClientSession = state.http._HTTPClient__session  # type: ignore
        self.client: ClientT = cast(ClientT, state._get_client())
        self._original_response: Optional[InteractionMessage] = None

        self.id: int = int(data["id"])
        self.type: InteractionType = try_enum(InteractionType, data["type"])
        self.token: str = data["token"]
        self.version: int = data["version"]
        self.application_id: int = int(data["application_id"])
        self.guild_id: Optional[int] = utils._get_as_snowflake(data, "guild_id")
        self._guild: Optional[PartialGuildPayload] = data.get("guild")

        self.locale: Locale = try_enum(Locale, data["locale"])
        guild_locale = data.get("guild_locale")
        self.guild_locale: Optional[Locale] = (
            try_enum(Locale, guild_locale) if guild_locale else None
        )

        self._app_permissions: int = int(data.get("app_permissions", 0))
        self._permissions: Optional[int] = None
        # one of user and member will always exist
        self.author: Union[User, Member] = MISSING

        guild_fallback: Optional[Union[Guild, Object]] = None

        if self.guild_id and (guild_fallback := self.guild) and (member := data.get("member")):
            self.author = guild_fallback.get_member(int(member["user"]["id"])) or Member(
                state=self._state,
                guild=guild_fallback,
                data=member,
            )
            self._permissions = int(member.get("permissions", 0))
        elif user := data.get("user"):
            self.author = self._state.store_user(user)

        # TODO: consider making this optional in 3.0
        self.channel: MessageableChannel = state._get_partial_interaction_channel(
            data["channel"], guild_fallback, return_messageable=True
        )

        self.entitlements: List[Entitlement] = (
            [Entitlement(data=e, state=state) for e in entitlements_data]
            if (entitlements_data := data.get("entitlements"))
            else []
        )

    @property
    def bot(self) -> ClientT:
        """:class:`~disnake.ext.commands.Bot`: An alias for :attr:`.client`."""
        return self.client

    @property
    def created_at(self) -> datetime:
        """:class:`datetime.datetime`: Returns the interaction's creation time in UTC."""
        return utils.snowflake_time(self.id)

    @property
    def user(self) -> Union[User, Member]:
        """Union[:class:`.User`, :class:`.Member`]: The user or member that sent the interaction.
        There is an alias for this named :attr:`author`.
        """
        return self.author

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: The guild the interaction was sent from.

        .. versionchanged:: 2.10
            Returns a :class:`Guild` object when the guild could not be resolved from cache.
            This object is created from the data provided by Discord, but it is not complete.
            The only populated attributes are:
                - :attr:`Guild.id`
                - :attr:`Guild.preferred_locale`
                - :attr:`Guild.features`
        """
        if self.guild_id is None:
            return None

        guild = self._state._get_guild(self.guild_id)
        if guild:
            return guild
        if self._guild is None:
            return None

        # create a guild mash
        # honestly we should cache this for the duration of the interaction
        # but not if we fetch it from the cache, just the result of this creation
        guild = PartialInteractionGuild(data=self._guild, state=self._state, interaction=self)
        return guild

    @utils.cached_slot_property("_cs_me")
    def me(self) -> Union[Member, ClientUser]:
        """Union[:class:`.Member`, :class:`.ClientUser`]:
        Similar to :attr:`.Guild.me` except it may return the :class:`.ClientUser` in private message contexts.
        """
        if self.guild is None:
            return None if self.bot is None else self.bot.user  # type: ignore
        return self.guild.me

    @property
    def channel_id(self) -> int:
        """The channel ID the interaction was sent from.

        See also :attr:`channel`.
        """
        return self.channel.id

    @property
    def permissions(self) -> Permissions:
        """:class:`Permissions`: The resolved permissions of the member in the channel, including overwrites.

        In a guild context, this is provided directly by Discord.

        In a non-guild context this will be an instance of :meth:`Permissions.private_channel`.
        """
        if self._permissions is not None:
            return Permissions(self._permissions)
        return Permissions.private_channel()

    @property
    def app_permissions(self) -> Permissions:
        """:class:`Permissions`: The resolved permissions of the bot in the channel, including overwrites.

        In a guild context, this is provided directly by Discord.

        In a non-guild context this will be an instance of :meth:`Permissions.private_channel`.

        .. versionadded:: 2.6
        """
        if self.guild_id:
            return Permissions(self._app_permissions)
        return Permissions.private_channel()

    @utils.cached_slot_property("_cs_response")
    def response(self) -> InteractionResponse:
        """:class:`InteractionResponse`: Returns an object responsible for handling responding to the interaction.

        A response can only be done once. If secondary messages need to be sent, consider using :attr:`followup`
        instead.
        """
        return InteractionResponse(self)

    @utils.cached_slot_property("_cs_followup")
    def followup(self) -> Webhook:
        """:class:`Webhook`: Returns the follow up webhook for follow up interactions."""
        payload = {
            "id": self.application_id,
            "type": WebhookType.application.value,
            "token": self.token,
        }
        return Webhook.from_state(data=payload, state=self._state)

    @utils.cached_slot_property("_cs_expires_at")
    def expires_at(self) -> datetime:
        """:class:`datetime.datetime`: Returns the interaction's expiration time in UTC.

        This is exactly 15 minutes after the interaction was created.

        .. versionadded:: 2.5
        """
        return self.created_at + timedelta(minutes=15)

    def is_expired(self) -> bool:
        """Whether the interaction can still be used to make requests to Discord.

        This does not take into account the 3 second limit for the initial response.

        .. versionadded:: 2.5

        :return type: :class:`bool`
        """
        return self.expires_at <= utils.utcnow()

    async def original_response(self) -> InteractionMessage:
        """|coro|

        Fetches the original interaction response message associated with the interaction.

        Repeated calls to this will return a cached value.

        .. versionchanged:: 2.6

            This function was renamed from ``original_message``.

        Raises
        ------
        HTTPException
            Fetching the original response message failed.

        Returns
        -------
        InteractionMessage
            The original interaction response message.
        """
        if self._original_response is not None:
            return self._original_response

        adapter = async_context.get()
        data = await adapter.get_original_interaction_response(
            application_id=self.application_id,
            token=self.token,
            session=self._session,
        )
        state = _InteractionMessageState(self, self._state)
        message = InteractionMessage(state=state, channel=self.channel, data=data)  # type: ignore
        self._original_response = message
        return message

    async def edit_original_response(
        self,
        content: Optional[str] = MISSING,
        *,
        embed: Optional[Embed] = MISSING,
        embeds: List[Embed] = MISSING,
        file: File = MISSING,
        files: List[File] = MISSING,
        attachments: Optional[List[Attachment]] = MISSING,
        view: Optional[View] = MISSING,
        components: Optional[Components[MessageUIComponent]] = MISSING,
        poll: Poll = MISSING,
        suppress_embeds: bool = MISSING,
        flags: MessageFlags = MISSING,
        allowed_mentions: Optional[AllowedMentions] = None,
        delete_after: Optional[float] = None,
    ) -> InteractionMessage:
        """|coro|

        Edits the original, previously sent interaction response message.

        This is a lower level interface to :meth:`InteractionMessage.edit` in case
        you do not want to fetch the message and save an HTTP request.

        This method is also the only way to edit the original response if
        the message sent was ephemeral.

        .. note::
            If the original response message has embeds with images that were created from local files
            (using the ``file`` parameter with :meth:`Embed.set_image` or :meth:`Embed.set_thumbnail`),
            those images will be removed if the message's attachments are edited in any way
            (i.e. by setting ``file``/``files``/``attachments``, or adding an embed with local files).

        .. versionchanged:: 2.6

            This function was renamed from ``edit_original_message``.

        Parameters
        ----------
        content: Optional[:class:`str`]
            The content to edit the message with, or ``None`` to clear it.
        embed: Optional[:class:`Embed`]
            The new embed to replace the original with. This cannot be mixed with the
            ``embeds`` parameter.
            Could be ``None`` to remove the embed.
        embeds: List[:class:`Embed`]
            The new embeds to replace the original with. Must be a maximum of 10.
            This cannot be mixed with the ``embed`` parameter.
            To remove all embeds ``[]`` should be passed.
        file: :class:`File`
            The file to upload. This cannot be mixed with the ``files`` parameter.
            Files will be appended to the message, see the ``attachments`` parameter
            to remove/replace existing files.
        files: List[:class:`File`]
            A list of files to upload. This cannot be mixed with the ``file`` parameter.
            Files will be appended to the message, see the ``attachments`` parameter
            to remove/replace existing files.
        attachments: Optional[List[:class:`Attachment`]]
            A list of attachments to keep in the message.
            If ``[]`` or ``None`` is passed then all existing attachments are removed.
            Keeps existing attachments if not provided.

            .. versionadded:: 2.2

            .. versionchanged:: 2.5
                Supports passing ``None`` to clear attachments.

        view: Optional[:class:`~disnake.ui.View`]
            The updated view to update this message with. This cannot be mixed with ``components``.
            If ``None`` is passed then the view is removed.
        components: Optional[|components_type|]
            A list of components to update this message with. This cannot be mixed with ``view``.
            If ``None`` is passed then the components are removed.

            .. versionadded:: 2.4

        poll: :class:`Poll`
            A poll. This can only be sent after a defer. If not used after a defer the
            discord API ignore the field.

            .. versionadded:: 2.10

        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.
            See :meth:`.abc.Messageable.send` for more information.

        suppress_embeds: :class:`bool`
            Whether to suppress embeds for the message. This hides
            all the embeds from the UI if set to ``True``. If set
            to ``False``, this brings the embeds back if they were
            suppressed.

            .. versionadded:: 2.7

        flags: :class:`MessageFlags`
            The new flags to set for this message. Overrides existing flags.
            Only :attr:`~MessageFlags.suppress_embeds` is supported.

            If parameter ``suppress_embeds`` is provided,
            that will override the setting of :attr:`.MessageFlags.suppress_embeds`.

            .. versionadded:: 2.9

        delete_after: Optional[:class:`float`]
            If provided, the number of seconds to wait in the background
            before deleting the message we just edited. If the deletion fails,
            then it is silently ignored.

            Can be up to 15 minutes after the interaction was created
            (see also :attr:`Interaction.expires_at`/:attr:`~Interaction.is_expired`).

            .. versionadded:: 2.10

        Raises
        ------
        HTTPException
            Editing the message failed.
        Forbidden
            Edited a message that is not yours.
        TypeError
            You specified both ``embed`` and ``embeds`` or ``file`` and ``files``
        ValueError
            The length of ``embeds`` was invalid.

        Returns
        -------
        :class:`InteractionMessage`
            The newly edited message.
        """
        # if no attachment list was provided but we're uploading new files,
        # use current attachments as the base
        if attachments is MISSING and (file or files):
            attachments = (await self.original_response()).attachments

        previous_mentions: Optional[AllowedMentions] = self._state.allowed_mentions
        params = handle_message_parameters(
            content=content,
            file=file,
            files=files,
            attachments=attachments,
            embed=embed,
            embeds=embeds,
            view=view,
            components=components,
            poll=poll,
            suppress_embeds=suppress_embeds,
            flags=flags,
            allowed_mentions=allowed_mentions,
            previous_allowed_mentions=previous_mentions,
        )
        adapter = async_context.get()
        try:
            data = await adapter.edit_original_interaction_response(
                self.application_id,
                self.token,
                session=self._session,
                payload=params.payload,
                multipart=params.multipart,
                files=params.files,
            )
        except NotFound as e:
            if e.code == 10015:
                raise InteractionNotResponded(self) from e
            raise
        finally:
            if params.files:
                for f in params.files:
                    f.close()

        # The message channel types should always match
        state = _InteractionMessageState(self, self._state)
        message = InteractionMessage(state=state, channel=self.channel, data=data)  # type: ignore

        if view and not view.is_finished():
            self._state.store_view(view, message.id)

        if delete_after is not None:
            await self.delete_original_response(delay=delete_after)

        return message

    async def delete_original_response(self, *, delay: Optional[float] = None) -> None:
        """|coro|

        Deletes the original interaction response message.

        This is a lower level interface to :meth:`InteractionMessage.delete` in case
        you do not want to fetch the message and save an HTTP request.

        .. versionchanged:: 2.6

            This function was renamed from ``delete_original_message``.

        Parameters
        ----------
        delay: Optional[:class:`float`]
            If provided, the number of seconds to wait in the background
            before deleting the original response message. If the deletion fails,
            then it is silently ignored.

            Can be up to 15 minutes after the interaction was created
            (see also :attr:`Interaction.expires_at`/:attr:`~Interaction.is_expired`).

        Raises
        ------
        HTTPException
            Deleting the message failed.
        Forbidden
            Deleted a message that is not yours.
        """
        adapter = async_context.get()
        deleter = adapter.delete_original_interaction_response(
            self.application_id,
            self.token,
            session=self._session,
        )

        if delay is not None:

            async def delete(delay: float) -> None:
                await asyncio.sleep(delay)
                try:
                    await deleter
                except HTTPException:
                    pass

            asyncio.create_task(delete(delay))
            return

        try:
            await deleter
        except NotFound as e:
            if e.code == 10015:
                raise InteractionNotResponded(self) from e
            raise

    # legacy namings
    # these MAY begin a deprecation warning in 2.7 but SHOULD have a deprecation version in 2.8
    original_message = original_response
    edit_original_message = edit_original_response
    delete_original_message = delete_original_response

    async def send(
        self,
        content: Optional[str] = None,
        *,
        embed: Embed = MISSING,
        embeds: List[Embed] = MISSING,
        file: File = MISSING,
        files: List[File] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        view: View = MISSING,
        components: Components[MessageUIComponent] = MISSING,
        tts: bool = False,
        ephemeral: bool = MISSING,
        suppress_embeds: bool = MISSING,
        flags: MessageFlags = MISSING,
        delete_after: float = MISSING,
        poll: Poll = MISSING,
    ) -> None:
        """|coro|

        Sends a message using either :meth:`response.send_message <InteractionResponse.send_message>`
        or :meth:`followup.send <Webhook.send>`.

        If the interaction hasn't been responded to yet, this method will call :meth:`response.send_message <InteractionResponse.send_message>`.
        Otherwise, it will call :meth:`followup.send <Webhook.send>`.

        .. note::
            This method does not return a :class:`Message` object. If you need a message object,
            use :meth:`original_response` to fetch it, or use :meth:`followup.send <Webhook.send>`
            directly instead of this method if you're sending a followup message.

        Parameters
        ----------
        content: Optional[:class:`str`]
            The content of the message to send.
        embed: :class:`Embed`
            The rich embed for the content to send. This cannot be mixed with the
            ``embeds`` parameter.
        embeds: List[:class:`Embed`]
            A list of embeds to send with the content. Must be a maximum of 10.
            This cannot be mixed with the ``embed`` parameter.
        file: :class:`File`
            The file to upload. This cannot be mixed with the ``files`` parameter.
        files: List[:class:`File`]
            A list of files to upload. Must be a maximum of 10.
            This cannot be mixed with the ``file`` parameter.
        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message. If this is
            passed, then the object is merged with :attr:`Client.allowed_mentions <disnake.Client.allowed_mentions>`.
            The merging behaviour only overrides attributes that have been explicitly passed
            to the object, otherwise it uses the attributes set in :attr:`Client.allowed_mentions <disnake.Client.allowed_mentions>`.
            If no object is passed at all then the defaults given by :attr:`Client.allowed_mentions <disnake.Client.allowed_mentions>`
            are used instead.
        tts: :class:`bool`
            Whether the message should be sent using text-to-speech.
        view: :class:`disnake.ui.View`
            The view to send with the message. This cannot be mixed with ``components``.
        components: |components_type|
            A list of components to send with the message. This cannot be mixed with ``view``.

            .. versionadded:: 2.4

        ephemeral: :class:`bool`
            Whether the message should only be visible to the user who started the interaction.
            If a view is sent with an ephemeral message and it has no timeout set then the timeout
            is set to 15 minutes.
        suppress_embeds: :class:`bool`
            Whether to suppress embeds for the message. This hides
            all the embeds from the UI if set to ``True``.

            .. versionadded:: 2.5

        flags: :class:`MessageFlags`
            The flags to set for this message.
            Only :attr:`~MessageFlags.suppress_embeds`, :attr:`~MessageFlags.ephemeral`
            and :attr:`~MessageFlags.suppress_notifications` are supported.

            If parameters ``suppress_embeds`` or ``ephemeral`` are provided,
            they will override the corresponding setting of this ``flags`` parameter.

            .. versionadded:: 2.9

        delete_after: :class:`float`
            If provided, the number of seconds to wait in the background
            before deleting the message we just sent. If the deletion fails,
            then it is silently ignored.

            Can be up to 15 minutes after the interaction was created
            (see also :attr:`expires_at`/:attr:`is_expired`).

            .. versionchanged:: 2.7
                Added support for ephemeral responses.

        poll: :class:`Poll`
            The poll to send with the message.

            .. versionadded:: 2.10

        Raises
        ------
        HTTPException
            Sending the message failed.
        TypeError
            You specified both ``embed`` and ``embeds``.
        ValueError
            The length of ``embeds`` was invalid.
        """
        if self.response._response_type is not None:
            sender = self.followup.send
        else:
            sender = self.response.send_message
        await sender(
            content=content,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            allowed_mentions=allowed_mentions,
            view=view,
            components=components,
            tts=tts,
            ephemeral=ephemeral,
            suppress_embeds=suppress_embeds,
            flags=flags,
            delete_after=delete_after,
            poll=poll,
        )


class InteractionResponse:
    """Represents a Discord interaction response.

    This type can be accessed through :attr:`Interaction.response`.

    .. versionadded:: 2.0
    """

    __slots__: Tuple[str, ...] = (
        "_parent",
        "_response_type",
    )

    def __init__(self, parent: Interaction) -> None:
        self._parent: Interaction = parent
        self._response_type: Optional[InteractionResponseType] = None

    @property
    def type(self) -> Optional[InteractionResponseType]:
        """Optional[:class:`InteractionResponseType`]: If a response was successfully made, this is the type of the response.

        .. versionadded:: 2.6
        """
        return self._response_type

    def is_done(self) -> bool:
        """Whether an interaction response has been done before.

        An interaction can only be responded to once.

        :return type: :class:`bool`
        """
        return self._response_type is not None

    async def defer(
        self,
        *,
        with_message: bool = MISSING,
        ephemeral: bool = MISSING,
    ) -> None:
        """|coro|

        Defers the interaction response.

        This is typically used when the interaction is acknowledged
        and a secondary action will be done later.

        .. versionchanged:: 2.5

            Raises :exc:`TypeError` when an interaction cannot be deferred.

        Parameters
        ----------
        with_message: :class:`bool`
            Whether the response will be a separate message with thinking state (bot is thinking...).
            This only applies to interactions of type :attr:`InteractionType.component`
            (default ``False``) and :attr:`InteractionType.modal_submit` (default ``True``).

            ``True`` corresponds to a :attr:`~InteractionResponseType.deferred_channel_message` response type,
            while ``False`` corresponds to :attr:`~InteractionResponseType.deferred_message_update`.

            .. note::
                Responses to interactions of type :attr:`InteractionType.application_command` must
                defer using a message, i.e. this will effectively always be ``True`` for those.

            .. versionadded:: 2.4

            .. versionchanged:: 2.6
                Added support for setting this to ``False`` in modal interactions.

        ephemeral: :class:`bool`
            Whether the deferred message will eventually be ephemeral.
            This applies to interactions of type :attr:`InteractionType.application_command`,
            or when the ``with_message`` parameter is ``True``.

            Defaults to ``False``.

        Raises
        ------
        HTTPException
            Deferring the interaction failed.
        InteractionResponded
            This interaction has already been responded to before.
        TypeError
            This interaction cannot be deferred.
        """
        if self._response_type is not None:
            raise InteractionResponded(self._parent)

        defer_type: Optional[InteractionResponseType] = None
        data: Dict[str, Any] = {}
        parent = self._parent

        if parent.type is InteractionType.application_command:
            defer_type = InteractionResponseType.deferred_channel_message
        elif parent.type in (InteractionType.component, InteractionType.modal_submit):
            # if not provided, set default based on interaction type
            # (true for modal_submit, false for component)
            if with_message is MISSING:
                with_message = parent.type is InteractionType.modal_submit

            if with_message:
                defer_type = InteractionResponseType.deferred_channel_message
            else:
                defer_type = InteractionResponseType.deferred_message_update
        else:
            raise TypeError(
                "This interaction must be of type 'application_command', 'modal_submit', or 'component' in order to defer."
            )

        if defer_type is InteractionResponseType.deferred_channel_message:
            # we only want to set flags if we are sending a message
            data["flags"] = 0
            if ephemeral:
                data["flags"] |= MessageFlags.ephemeral.flag

        adapter = async_context.get()
        await adapter.create_interaction_response(
            parent.id,
            parent.token,
            session=parent._session,
            type=defer_type.value,
            data=data or None,
        )
        self._response_type = defer_type

    async def pong(self) -> None:
        """|coro|

        Pongs the ping interaction.

        This should rarely be used.

        Raises
        ------
        HTTPException
            Ponging the interaction failed.
        InteractionResponded
            This interaction has already been responded to before.
        """
        if self._response_type is not None:
            raise InteractionResponded(self._parent)

        parent = self._parent
        if parent.type is InteractionType.ping:
            adapter = async_context.get()
            response_type = InteractionResponseType.pong
            await adapter.create_interaction_response(
                parent.id,
                parent.token,
                session=parent._session,
                type=response_type.value,
            )
            self._response_type = response_type

    async def send_message(
        self,
        content: Optional[str] = None,
        *,
        embed: Embed = MISSING,
        embeds: List[Embed] = MISSING,
        file: File = MISSING,
        files: List[File] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        view: View = MISSING,
        components: Components[MessageUIComponent] = MISSING,
        tts: bool = False,
        ephemeral: bool = MISSING,
        suppress_embeds: bool = MISSING,
        flags: MessageFlags = MISSING,
        delete_after: float = MISSING,
        poll: Poll = MISSING,
    ) -> None:
        """|coro|

        Responds to this interaction by sending a message.

        Parameters
        ----------
        content: Optional[:class:`str`]
            The content of the message to send.
        embed: :class:`Embed`
            The rich embed for the content to send. This cannot be mixed with the
            ``embeds`` parameter.
        embeds: List[:class:`Embed`]
            A list of embeds to send with the content. Must be a maximum of 10.
            This cannot be mixed with the ``embed`` parameter.
        file: :class:`File`
            The file to upload. This cannot be mixed with the ``files`` parameter.
        files: List[:class:`File`]
            A list of files to upload. Must be a maximum of 10.
            This cannot be mixed with the ``file`` parameter.
        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.
        view: :class:`disnake.ui.View`
            The view to send with the message. This cannot be mixed with ``components``.
        components: |components_type|
            A list of components to send with the message. This cannot be mixed with ``view``.

            .. versionadded:: 2.4

        tts: :class:`bool`
            Whether the message should be sent using text-to-speech.
        ephemeral: :class:`bool`
            Whether the message should only be visible to the user who started the interaction.
            If a view is sent with an ephemeral message and it has no timeout set then the timeout
            is set to 15 minutes.
        delete_after: :class:`float`
            If provided, the number of seconds to wait in the background
            before deleting the message we just sent. If the deletion fails,
            then it is silently ignored.

            Can be up to 15 minutes after the interaction was created
            (see also :attr:`Interaction.expires_at`/:attr:`~Interaction.is_expired`).

            .. versionchanged:: 2.7
                Added support for ephemeral responses.

        suppress_embeds: :class:`bool`
            Whether to suppress embeds for the message. This hides
            all the embeds from the UI if set to ``True``.

            .. versionadded:: 2.5

        flags: :class:`MessageFlags`
            The flags to set for this message.
            Only :attr:`~MessageFlags.suppress_embeds`, :attr:`~MessageFlags.ephemeral`
            and :attr:`~MessageFlags.suppress_notifications` are supported.

            If parameters ``suppress_embeds`` or ``ephemeral`` are provided,
            they will override the corresponding setting of this ``flags`` parameter.

            .. versionadded:: 2.9

        poll: :class:`Poll`
            The poll to send with the message.

            .. versionadded:: 2.10


        Raises
        ------
        HTTPException
            Sending the message failed.
        TypeError
            You specified both ``embed`` and ``embeds``.
        ValueError
            The length of ``embeds`` was invalid.
        InteractionResponded
            This interaction has already been responded to before.
        """
        if self._response_type is not None:
            raise InteractionResponded(self._parent)

        payload: Dict[str, Any] = {
            "tts": tts,
        }

        if embed is not MISSING and embeds is not MISSING:
            raise TypeError("cannot mix embed and embeds keyword arguments")

        if file is not MISSING and files is not MISSING:
            raise TypeError("cannot mix file and files keyword arguments")

        if view is not MISSING and components is not MISSING:
            raise TypeError("cannot mix view and components keyword arguments")

        if file is not MISSING:
            files = [file]

        if embed is not MISSING:
            embeds = [embed]

        if embeds:
            if len(embeds) > 10:
                raise ValueError("embeds cannot exceed maximum of 10 elements")
            payload["embeds"] = [e.to_dict() for e in embeds]
            for embed in embeds:
                if embed._files:
                    files = files or []
                    files.extend(embed._files.values())

        if files is not MISSING and len(files) > 10:
            raise ValueError("files cannot exceed maximum of 10 elements")

        previous_mentions: Optional[AllowedMentions] = getattr(
            self._parent._state, "allowed_mentions", None
        )
        if allowed_mentions:
            if previous_mentions is not None:
                payload["allowed_mentions"] = previous_mentions.merge(allowed_mentions).to_dict()
            else:
                payload["allowed_mentions"] = allowed_mentions.to_dict()
        elif previous_mentions is not None:
            payload["allowed_mentions"] = previous_mentions.to_dict()

        if content is not None:
            payload["content"] = str(content)

        if suppress_embeds is not MISSING or ephemeral is not MISSING:
            flags = MessageFlags._from_value(0 if flags is MISSING else flags.value)
            if suppress_embeds is not MISSING:
                flags.suppress_embeds = suppress_embeds
            if ephemeral is not MISSING:
                flags.ephemeral = ephemeral
        if flags is not MISSING:
            payload["flags"] = flags.value

        if view is not MISSING:
            payload["components"] = view.to_components()

        if components is not MISSING:
            payload["components"] = components_to_dict(components)
        if poll is not MISSING:
            payload["poll"] = poll._to_dict()

        parent = self._parent
        adapter = async_context.get()
        response_type = InteractionResponseType.channel_message
        try:
            await adapter.create_interaction_response(
                parent.id,
                parent.token,
                session=parent._session,
                type=response_type.value,
                data=payload,
                files=files or None,
            )
        except NotFound as e:
            if e.code == 10062:
                raise InteractionTimedOut(self._parent) from e
            raise
        finally:
            if files:
                for f in files:
                    f.close()

        self._response_type = response_type

        if view is not MISSING:
            if ephemeral and view.timeout is None:
                view.timeout = 15 * 60.0

            self._parent._state.store_view(view)

        if delete_after is not MISSING:
            await self._parent.delete_original_response(delay=delete_after)

    async def edit_message(
        self,
        content: Optional[str] = MISSING,
        *,
        embed: Optional[Embed] = MISSING,
        embeds: List[Embed] = MISSING,
        file: File = MISSING,
        files: List[File] = MISSING,
        attachments: Optional[List[Attachment]] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        view: Optional[View] = MISSING,
        components: Optional[Components[MessageUIComponent]] = MISSING,
        delete_after: Optional[float] = None,
    ) -> None:
        """|coro|

        Responds to this interaction by editing the original message of
        a component interaction or modal interaction (if the modal was sent in
        response to a component interaction).

        .. versionchanged:: 2.5

            Now supports editing the original message of modal interactions that started from a component.

        .. note::
            If the original message has embeds with images that were created from local files
            (using the ``file`` parameter with :meth:`Embed.set_image` or :meth:`Embed.set_thumbnail`),
            those images will be removed if the message's attachments are edited in any way
            (i.e. by setting ``file``/``files``/``attachments``, or adding an embed with local files).

        Parameters
        ----------
        content: Optional[:class:`str`]
            The new content to replace the message with. ``None`` removes the content.
        embed: Optional[:class:`Embed`]
            The new embed to replace the original with. This cannot be mixed with the
            ``embeds`` parameter.
            Could be ``None`` to remove the embed.
        embeds: List[:class:`Embed`]
            The new embeds to replace the original with. Must be a maximum of 10.
            This cannot be mixed with the ``embed`` parameter.
            To remove all embeds ``[]`` should be passed.
        file: :class:`File`
            The file to upload. This cannot be mixed with the ``files`` parameter.
            Files will be appended to the message.

            .. versionadded:: 2.2

        files: List[:class:`File`]
            A list of files to upload. This cannot be mixed with the ``file`` parameter.
            Files will be appended to the message.

            .. versionadded:: 2.2

        attachments: Optional[List[:class:`Attachment`]]
            A list of attachments to keep in the message.
            If ``[]`` or ``None`` is passed then all existing attachments are removed.
            Keeps existing attachments if not provided.

            .. versionadded:: 2.4

            .. versionchanged:: 2.5
                Supports passing ``None`` to clear attachments.

        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.
        view: Optional[:class:`~disnake.ui.View`]
            The updated view to update this message with. This cannot be mixed with ``components``.
            If ``None`` is passed then the view is removed.
        components: Optional[|components_type|]
            A list of components to update this message with. This cannot be mixed with ``view``.
            If ``None`` is passed then the components are removed.

            .. versionadded:: 2.4

        delete_after: Optional[:class:`float`]
            If provided, the number of seconds to wait in the background
            before deleting the message we just edited. If the deletion fails,
            then it is silently ignored.

            Can be up to 15 minutes after the interaction was created
            (see also :attr:`Interaction.expires_at`/:attr:`~Interaction.is_expired`).

            .. versionadded:: 2.10

        Raises
        ------
        HTTPException
            Editing the message failed.
        TypeError
            You specified both ``embed`` and ``embeds``.
        InteractionResponded
            This interaction has already been responded to before.
        """
        if self._response_type is not None:
            raise InteractionResponded(self._parent)

        parent = self._parent
        state = parent._state

        if parent.type not in (InteractionType.component, InteractionType.modal_submit):
            raise InteractionNotEditable(parent)
        parent = cast("Union[MessageInteraction, ModalInteraction]", parent)
        message = parent.message
        # message in modal interactions only exists if modal was sent from component interaction
        if not message:
            raise InteractionNotEditable(parent)

        payload = {}
        if content is not MISSING:
            payload["content"] = None if content is None else str(content)

        if file is not MISSING and files is not MISSING:
            raise TypeError("cannot mix file and files keyword arguments")

        if file is not MISSING:
            files = [file]

        if embed is not MISSING and embeds is not MISSING:
            raise TypeError("cannot mix both embed and embeds keyword arguments")

        if embed is not MISSING:
            embeds = [] if embed is None else [embed]
        if embeds is not MISSING:
            payload["embeds"] = [e.to_dict() for e in embeds]
            for embed in embeds:
                if embed._files:
                    files = files or []
                    files.extend(embed._files.values())

        if files is not MISSING and len(files) > 10:
            raise ValueError("files cannot exceed maximum of 10 elements")

        previous_mentions: Optional[AllowedMentions] = getattr(
            self._parent._state, "allowed_mentions", None
        )
        if allowed_mentions:
            if previous_mentions is not None:
                payload["allowed_mentions"] = previous_mentions.merge(allowed_mentions).to_dict()
            else:
                payload["allowed_mentions"] = allowed_mentions.to_dict()
        elif previous_mentions is not None:
            payload["allowed_mentions"] = previous_mentions.to_dict()

        # if no attachment list was provided but we're uploading new files,
        # use current attachments as the base
        if attachments is MISSING and (file or files):
            attachments = message.attachments
        if attachments is not MISSING:
            payload["attachments"] = (
                [] if attachments is None else [a.to_dict() for a in attachments]
            )

        if view is not MISSING and components is not MISSING:
            raise TypeError("cannot mix view and components keyword arguments")

        if view is not MISSING:
            state.prevent_view_updates_for(message.id)
            payload["components"] = [] if view is None else view.to_components()

        if components is not MISSING:
            payload["components"] = [] if components is None else components_to_dict(components)

        adapter = async_context.get()
        response_type = InteractionResponseType.message_update
        try:
            await adapter.create_interaction_response(
                parent.id,
                parent.token,
                session=parent._session,
                type=response_type.value,
                data=payload,
                files=files,
            )
        finally:
            if files:
                for f in files:
                    f.close()

        if view and not view.is_finished():
            state.store_view(view, message.id)

        self._response_type = response_type

        if delete_after is not None:
            await self._parent.delete_original_response(delay=delete_after)

    async def autocomplete(self, *, choices: Choices) -> None:
        """|coro|

        Responds to this interaction by displaying a list of possible autocomplete results.
        Only works for autocomplete interactions.

        Parameters
        ----------
        choices: Union[Sequence[:class:`OptionChoice`], Sequence[Union[:class:`str`, :class:`int`, :class:`float`]], Mapping[:class:`str`, Union[:class:`str`, :class:`int`, :class:`float`]]]
            The choices to suggest.

        Raises
        ------
        HTTPException
            Autocomplete response has failed.
        InteractionResponded
            This interaction has already been responded to before.
        """
        if self._response_type is not None:
            raise InteractionResponded(self._parent)

        choices_data: List[ApplicationCommandOptionChoicePayload]
        if isinstance(choices, Mapping):
            choices_data = [{"name": n, "value": v} for n, v in choices.items()]
        else:
            if isinstance(choices, str):  # str matches `Sequence[str]`, but isn't meant to be used
                raise TypeError("choices argument should be a list/sequence or dict, not str")

            choices_data = []
            value: ApplicationCommandOptionChoicePayload
            i18n = self._parent.client.i18n
            for c in choices:
                if isinstance(c, Localized):
                    c = OptionChoice(c, c.string)

                if isinstance(c, OptionChoice):
                    c.localize(i18n)
                    value = c.to_dict(locale=self._parent.locale)
                else:
                    value = {"name": str(c), "value": c}
                choices_data.append(value)

        parent = self._parent
        adapter = async_context.get()
        response_type = InteractionResponseType.application_command_autocomplete_result
        await adapter.create_interaction_response(
            parent.id,
            parent.token,
            session=parent._session,
            type=response_type.value,
            data={"choices": choices_data},
        )

        self._response_type = response_type

    @overload
    async def send_modal(self, modal: Modal) -> None:
        ...

    @overload
    async def send_modal(
        self,
        *,
        title: str,
        custom_id: str,
        components: Components[ModalUIComponent],
    ) -> None:
        ...

    async def send_modal(
        self,
        modal: Optional[Modal] = None,
        *,
        title: Optional[str] = None,
        custom_id: Optional[str] = None,
        components: Optional[Components[ModalUIComponent]] = None,
    ) -> None:
        """|coro|

        Responds to this interaction by displaying a modal.

        .. versionadded:: 2.4

        .. note::

            Not passing the ``modal`` parameter here will not register a callback, and a :func:`on_modal_submit`
            interaction will need to be handled manually.

        Parameters
        ----------
        modal: :class:`~.ui.Modal`
            The modal to display. This cannot be mixed with the ``title``, ``custom_id`` and ``components`` parameters.
        title: :class:`str`
            The title of the modal. This cannot be mixed with the ``modal`` parameter.
        custom_id: :class:`str`
            The ID of the modal that gets received during an interaction.
            This cannot be mixed with the ``modal`` parameter.
        components: |components_type|
            The components to display in the modal. A maximum of 5.
            This cannot be mixed with the ``modal`` parameter.

        Raises
        ------
        TypeError
            Cannot mix the ``modal`` parameter and the ``title``, ``custom_id``, ``components`` parameters.
        ValueError
            Maximum number of components (5) exceeded.
        HTTPException
            Displaying the modal failed.
        ModalChainNotSupported
            This interaction cannot be responded with a modal.
        InteractionResponded
            This interaction has already been responded to before.
        """
        if modal is not None and any((title, components, custom_id)):
            raise TypeError("Cannot mix modal argument and title, custom_id, components arguments")

        parent = self._parent

        if parent.type is InteractionType.modal_submit:
            raise ModalChainNotSupported(parent)  # type: ignore

        if self._response_type is not None:
            raise InteractionResponded(parent)

        modal_data: ModalPayload

        if modal is not None:
            modal_data = modal.to_components()
        elif title and components and custom_id:
            rows = components_to_dict(components)
            if len(rows) > 5:
                raise ValueError("Maximum number of components exceeded.")

            modal_data = {
                "title": title,
                "custom_id": custom_id,
                "components": rows,
            }
        else:
            raise TypeError("Either modal or title, custom_id, components must be provided")

        adapter = async_context.get()
        response_type = InteractionResponseType.modal
        await adapter.create_interaction_response(
            parent.id,
            parent.token,
            session=parent._session,
            type=response_type.value,
            data=modal_data,  # type: ignore
        )
        self._response_type = response_type

        if modal is not None:
            parent._state.store_modal(parent.author.id, modal)

    async def require_premium(self) -> None:
        """|coro|

        Responds to this interaction with a message containing an upgrade button.

        Only available for applications with monetization enabled.

        .. versionadded:: 2.10

        Example
        -------
        Require an application subscription for a command: ::

            @bot.slash_command()
            async def cool_command(inter: disnake.ApplicationCommandInteraction):
                if not inter.entitlements:
                    await inter.response.require_premium()
                    return  # skip remaining code
                ...

        Raises
        ------
        HTTPException
            Sending the response has failed.
        InteractionResponded
            This interaction has already been responded to before.
        """
        if self._response_type is not None:
            raise InteractionResponded(self._parent)

        parent = self._parent
        adapter = async_context.get()
        response_type = InteractionResponseType.premium_required
        await adapter.create_interaction_response(
            parent.id,
            parent.token,
            session=parent._session,
            type=response_type.value,
        )

        self._response_type = response_type


class _InteractionMessageState:
    __slots__ = ("_parent", "_interaction")

    def __init__(self, interaction: Interaction, parent: ConnectionState) -> None:
        self._interaction: Interaction = interaction
        self._parent: ConnectionState = parent

    def _get_guild(self, guild_id):
        return self._parent._get_guild(guild_id)

    def store_user(self, data):
        return self._parent.store_user(data)

    def create_user(self, data):
        return self._parent.create_user(data)

    @property
    def http(self):
        return self._parent.http

    def __getattr__(self, attr):
        return getattr(self._parent, attr)


class InteractionMessage(Message):
    """Represents the original interaction response message.

    This allows you to edit or delete the message associated with
    the interaction response. To retrieve this object see :meth:`Interaction.original_response`.

    This inherits from :class:`disnake.Message` with changes to
    :meth:`edit` and :meth:`delete` to work.

    .. versionadded:: 2.0

    Attributes
    ----------
    type: :class:`MessageType`
        The type of message.
    author: Union[:class:`Member`, :class:`abc.User`]
        A :class:`Member` that sent the message. If :attr:`channel` is a
        private channel, then it is a :class:`User` instead.
    content: :class:`str`
        The actual contents of the message.
    embeds: List[:class:`Embed`]
        A list of embeds the message has.
    channel: Union[:class:`TextChannel`, :class:`VoiceChannel`, :class:`StageChannel`, :class:`Thread`, :class:`DMChannel`, :class:`GroupChannel`, :class:`PartialMessageable`]
        The channel that the message was sent from.
        Could be a :class:`DMChannel` or :class:`GroupChannel` if it's a private message.
    reference: Optional[:class:`~disnake.MessageReference`]
        The message that this message references. This is only applicable to message replies.
    interaction: Optional[:class:`~disnake.InteractionReference`]
        The interaction that this message references.
        This exists only when the message is a response to an interaction without an existing message.

        .. versionadded:: 2.1

    mention_everyone: :class:`bool`
        Specifies if the message mentions everyone.

        .. note::

            This does not check if the ``@everyone`` or the ``@here`` text is in the message itself.
            Rather this boolean indicates if either the ``@everyone`` or the ``@here`` text is in the message
            **and** it did end up mentioning.
    mentions: List[:class:`abc.User`]
        A list of :class:`Member` that were mentioned. If the message is in a private message
        then the list will be of :class:`User` instead.

        .. warning::

            The order of the mentions list is not in any particular order so you should
            not rely on it. This is a Discord limitation, not one with the library.
    role_mentions: List[:class:`Role`]
        A list of :class:`Role` that were mentioned. If the message is in a private message
        then the list is always empty.
    id: :class:`int`
        The message ID.
    webhook_id: Optional[:class:`int`]
        The ID of the application that sent this message.
    attachments: List[:class:`Attachment`]
        A list of attachments given to a message.
    pinned: :class:`bool`
        Specifies if the message is currently pinned.
    flags: :class:`MessageFlags`
        Extra features of the message.
    reactions : List[:class:`Reaction`]
        Reactions to a message. Reactions can be either custom emoji or standard unicode emoji.
    stickers: List[:class:`StickerItem`]
        A list of sticker items given to the message.
    components: List[:class:`Component`]
        A list of components in the message.
    guild: Optional[:class:`Guild`]
        The guild that the message belongs to, if applicable.
    poll: Optional[:class:`Poll`]
        The poll contained in this message.

        .. versionadded:: 2.10
    """

    __slots__ = ()
    _state: _InteractionMessageState

    @overload
    async def edit(
        self,
        content: Optional[str] = ...,
        *,
        embed: Optional[Embed] = ...,
        file: File = ...,
        attachments: Optional[List[Attachment]] = ...,
        suppress_embeds: bool = ...,
        flags: MessageFlags = ...,
        allowed_mentions: Optional[AllowedMentions] = ...,
        view: Optional[View] = ...,
        components: Optional[Components[MessageUIComponent]] = ...,
        delete_after: Optional[float] = ...,
    ) -> InteractionMessage:
        ...

    @overload
    async def edit(
        self,
        content: Optional[str] = ...,
        *,
        embed: Optional[Embed] = ...,
        files: List[File] = ...,
        attachments: Optional[List[Attachment]] = ...,
        suppress_embeds: bool = ...,
        flags: MessageFlags = ...,
        allowed_mentions: Optional[AllowedMentions] = ...,
        view: Optional[View] = ...,
        components: Optional[Components[MessageUIComponent]] = ...,
        delete_after: Optional[float] = ...,
    ) -> InteractionMessage:
        ...

    @overload
    async def edit(
        self,
        content: Optional[str] = ...,
        *,
        embeds: List[Embed] = ...,
        file: File = ...,
        attachments: Optional[List[Attachment]] = ...,
        suppress_embeds: bool = ...,
        flags: MessageFlags = ...,
        allowed_mentions: Optional[AllowedMentions] = ...,
        view: Optional[View] = ...,
        components: Optional[Components[MessageUIComponent]] = ...,
        delete_after: Optional[float] = ...,
    ) -> InteractionMessage:
        ...

    @overload
    async def edit(
        self,
        content: Optional[str] = ...,
        *,
        embeds: List[Embed] = ...,
        files: List[File] = ...,
        attachments: Optional[List[Attachment]] = ...,
        suppress_embeds: bool = ...,
        flags: MessageFlags = ...,
        allowed_mentions: Optional[AllowedMentions] = ...,
        view: Optional[View] = ...,
        components: Optional[Components[MessageUIComponent]] = ...,
        delete_after: Optional[float] = ...,
    ) -> InteractionMessage:
        ...

    async def edit(
        self,
        content: Optional[str] = MISSING,
        *,
        embed: Optional[Embed] = MISSING,
        embeds: List[Embed] = MISSING,
        file: File = MISSING,
        files: List[File] = MISSING,
        attachments: Optional[List[Attachment]] = MISSING,
        suppress_embeds: bool = MISSING,
        flags: MessageFlags = MISSING,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        view: Optional[View] = MISSING,
        components: Optional[Components[MessageUIComponent]] = MISSING,
        delete_after: Optional[float] = None,
    ) -> Message:
        """|coro|

        Edits the message.

        .. note::
            If the original message has embeds with images that were created from local files
            (using the ``file`` parameter with :meth:`Embed.set_image` or :meth:`Embed.set_thumbnail`),
            those images will be removed if the message's attachments are edited in any way
            (i.e. by setting ``file``/``files``/``attachments``, or adding an embed with local files).

        Parameters
        ----------
        content: Optional[:class:`str`]
            The content to edit the message with, or ``None`` to clear it.
        embed: Optional[:class:`Embed`]
            The new embed to replace the original with. This cannot be mixed with the
            ``embeds`` parameter.
            Could be ``None`` to remove the embed.
        embeds: List[:class:`Embed`]
            The new embeds to replace the original with. Must be a maximum of 10.
            This cannot be mixed with the ``embed`` parameter.
            To remove all embeds ``[]`` should be passed.
        file: :class:`File`
            The file to upload. This cannot be mixed with the ``files`` parameter.
            Files will be appended to the message, see the ``attachments`` parameter
            to remove/replace existing files.
        files: List[:class:`File`]
            A list of files to upload. This cannot be mixed with the ``file`` parameter.
            Files will be appended to the message, see the ``attachments`` parameter
            to remove/replace existing files.
        attachments: Optional[List[:class:`Attachment`]]
            A list of attachments to keep in the message.
            If ``[]`` or ``None`` is passed then all existing attachments are removed.
            Keeps existing attachments if not provided.

            .. versionadded:: 2.2

            .. versionchanged:: 2.5
                Supports passing ``None`` to clear attachments.

        view: Optional[:class:`~disnake.ui.View`]
            The updated view to update this message with. This cannot be mixed with ``components``.
            If ``None`` is passed then the view is removed.
        components: Optional[|components_type|]
            A list of components to update this message with. This cannot be mixed with ``view``.
            If ``None`` is passed then the components are removed.

            .. versionadded:: 2.4

        suppress_embeds: :class:`bool`
            Whether to suppress embeds for the message. This hides
            all the embeds from the UI if set to ``True``. If set
            to ``False``, this brings the embeds back if they were
            suppressed.

            .. versionadded:: 2.7

        flags: :class:`MessageFlags`
            The new flags to set for this message. Overrides existing flags.
            Only :attr:`~MessageFlags.suppress_embeds` is supported.

            If parameter ``suppress_embeds`` is provided,
            that will override the setting of :attr:`.MessageFlags.suppress_embeds`.

            .. versionadded:: 2.9

        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.
            See :meth:`.abc.Messageable.send` for more information.
        delete_after: Optional[:class:`float`]
            If provided, the number of seconds to wait in the background
            before deleting the message we just edited. If the deletion fails,
            then it is silently ignored.

            Can be up to 15 minutes after the interaction was created
            (see also :attr:`Interaction.expires_at`/:attr:`~Interaction.is_expired`).

            .. versionadded:: 2.10

        Raises
        ------
        HTTPException
            Editing the message failed.
        Forbidden
            Edited a message that is not yours.
        TypeError
            You specified both ``embed`` and ``embeds`` or ``file`` and ``files``
        ValueError
            The length of ``embeds`` was invalid.

        Returns
        -------
        :class:`InteractionMessage`
            The newly edited message.
        """
        if self._state._interaction.is_expired():
            # We have to choose between type-ignoring the entire call,
            # or not having these specific parameters type-checked,
            # as we'd otherwise not match any of the overloads if all
            # parameters were provided
            params = {"file": file, "embed": embed}
            return await super().edit(
                content=content,
                embeds=embeds,
                files=files,
                attachments=attachments,
                suppress_embeds=suppress_embeds,
                flags=flags,
                allowed_mentions=allowed_mentions,
                view=view,
                components=components,
                delete_after=delete_after,
                **params,
            )

        # if no attachment list was provided but we're uploading new files,
        # use current attachments as the base
        # this isn't necessary when using the superclass, as the implementation there takes care of attachments
        if attachments is MISSING and (file or files):
            attachments = self.attachments

        return await self._state._interaction.edit_original_response(
            content=content,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            attachments=attachments,
            suppress_embeds=suppress_embeds,
            flags=flags,
            allowed_mentions=allowed_mentions,
            view=view,
            components=components,
            delete_after=delete_after,
        )

    async def delete(self, *, delay: Optional[float] = None) -> None:
        """|coro|

        Deletes the message.

        Parameters
        ----------
        delay: Optional[:class:`float`]
            If provided, the number of seconds to wait before deleting the message.
            The waiting is done in the background and deletion failures are ignored.

        Raises
        ------
        Forbidden
            You do not have proper permissions to delete the message.
        NotFound
            The message was deleted already.
        HTTPException
            Deleting the message failed.
        """
        if self._state._interaction.is_expired():
            return await super().delete(delay=delay)
        if delay is not None:

            async def inner_call(delay: float = delay) -> None:
                await asyncio.sleep(delay)
                try:
                    await self._state._interaction.delete_original_response()
                except HTTPException:
                    pass

            asyncio.create_task(inner_call())
        else:
            await self._state._interaction.delete_original_response()


class InteractionDataResolved(Dict[str, Any]):
    """Represents the resolved data related to an interaction.

    .. versionadded:: 2.1

    .. versionchanged:: 2.7
        Renamed from ``ApplicationCommandInteractionDataResolved`` to ``InteractionDataResolved``.

    Attributes
    ----------
    members: Dict[:class:`int`, :class:`Member`]
        A mapping of IDs to partial members (``deaf`` and ``mute`` attributes are missing).
    users: Dict[:class:`int`, :class:`User`]
        A mapping of IDs to users.
    roles: Dict[:class:`int`, :class:`Role`]
        A mapping of IDs to roles.
    channels: Dict[:class:`int`, Union[:class:`abc.GuildChannel`, :class:`Thread`, :class:`abc.PrivateChannel`, :class:`PartialMessageable`]]
        A mapping of IDs to partial channels (only ``id``, ``name`` and ``permissions`` are included,
        threads also have ``thread_metadata`` and ``parent_id``).
    messages: Dict[:class:`int`, :class:`Message`]
        A mapping of IDs to messages.
    attachments: Dict[:class:`int`, :class:`Attachment`]
        A mapping of IDs to attachments.

        .. versionadded:: 2.4
    """

    __slots__ = ("members", "users", "roles", "channels", "messages", "attachments")

    def __init__(
        self,
        *,
        data: InteractionDataResolvedPayload,
        parent: Interaction[ClientT],
    ) -> None:
        data = data or {}
        super().__init__(data)

        self.members: Dict[int, Member] = {}
        self.users: Dict[int, User] = {}
        self.roles: Dict[int, Role] = {}
        self.channels: Dict[int, AnyChannel] = {}
        self.messages: Dict[int, Message] = {}
        self.attachments: Dict[int, Attachment] = {}

        users = data.get("users", {})
        members = data.get("members", {})
        roles = data.get("roles", {})
        channels = data.get("channels", {})
        messages = data.get("messages", {})
        attachments = data.get("attachments", {})

        state = parent._state
        guild_id = parent.guild_id

        guild: Optional[Guild] = None
        # `guild_fallback` is only used in guild contexts, so this `MISSING` value should never be used.
        # We need to define it anyway to satisfy the typechecker.
        guild_fallback: Union[Guild, Object] = MISSING
        if guild_id is not None:
            guild = state._get_guild(guild_id)
            guild_fallback = guild or Object(id=guild_id)

        for str_id, user in users.items():
            user_id = int(str_id)
            member = members.get(str_id)
            if member is not None:
                self.members[user_id] = (
                    guild
                    and guild.get_member(user_id)
                    or Member(
                        data=member,
                        user_data=user,
                        guild=guild_fallback,  # type: ignore
                        state=state,
                    )
                )
            else:
                self.users[user_id] = User(state=state, data=user)

        for str_id, role in roles.items():
            self.roles[int(str_id)] = Role(
                guild=guild_fallback,  # type: ignore
                state=state,
                data=role,
            )

        for str_id, channel_data in channels.items():
            self.channels[int(str_id)] = state._get_partial_interaction_channel(
                channel_data, guild_fallback
            )

        for str_id, message in messages.items():
            channel_id = int(message["channel_id"])
            channel: Optional[MessageableChannel] = None

            if channel_id == parent.channel.id:
                # fast path, this should generally be the case
                channel = parent.channel
            else:
                # in case this ever happens, fall back to guild channel cache
                channel = cast(
                    "Optional[MessageableChannel]",
                    (guild and guild.get_channel(channel_id)),
                )

                if channel is None:
                    # n.b. the message's channel is not sent as part of `resolved.channels`,
                    # so we need to fall back to partials here.
                    channel = PartialMessageable(state=state, id=channel_id, type=None)

            self.messages[int(str_id)] = Message(state=state, channel=channel, data=message)

        for str_id, attachment in attachments.items():
            self.attachments[int(str_id)] = Attachment(data=attachment, state=state)

    def __repr__(self) -> str:
        return (
            f"<InteractionDataResolved members={self.members!r} users={self.users!r} "
            f"roles={self.roles!r} channels={self.channels!r} messages={self.messages!r} attachments={self.attachments!r}>"
        )

    @overload
    def get_with_type(
        self, key: Snowflake, data_type: Union[OptionType, ComponentType]
    ) -> Union[Member, User, Role, AnyChannel, Message, Attachment, None]:
        ...

    @overload
    def get_with_type(
        self, key: Snowflake, data_type: Union[OptionType, ComponentType], default: T
    ) -> Union[Member, User, Role, AnyChannel, Message, Attachment, T]:
        ...

    def get_with_type(
        self, key: Snowflake, data_type: Union[OptionType, ComponentType], default: T = None
    ) -> Union[Member, User, Role, AnyChannel, Message, Attachment, T, None]:
        if data_type is OptionType.mentionable or data_type is ComponentType.mentionable_select:
            key = int(key)
            if (result := self.members.get(key)) is not None:
                return result
            if (result := self.users.get(key)) is not None:
                return result
            return self.roles.get(key, default)

        if data_type is OptionType.user or data_type is ComponentType.user_select:
            key = int(key)
            if (member := self.members.get(key)) is not None:
                return member
            return self.users.get(key, default)

        if data_type is OptionType.channel or data_type is ComponentType.channel_select:
            return self.channels.get(int(key), default)

        if data_type is OptionType.role or data_type is ComponentType.role_select:
            return self.roles.get(int(key), default)

        if data_type is OptionType.attachment:
            return self.attachments.get(int(key), default)

        return default

    def get_by_id(
        self, key: Optional[int]
    ) -> Optional[Union[Member, User, Role, AnyChannel, Message, Attachment]]:
        if key is None:
            return None

        if (res := self.members.get(key)) is not None:
            return res
        if (res := self.users.get(key)) is not None:
            return res
        if (res := self.roles.get(key)) is not None:
            return res
        if (res := self.channels.get(key)) is not None:
            return res
        if (res := self.messages.get(key)) is not None:
            return res
        if (res := self.attachments.get(key)) is not None:
            return res

        return None
