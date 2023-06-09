.. SPDX-License-Identifier: MIT

.. currentmodule:: disnake

.. _disnake_api_audit_logs:

Audit Logs
==========

Working with audit logs is a complicated process with a lot of machinery
involved. The library attempts to make this user-friendly by
making use of a couple of data classes and enums, listed below.

Discord Models
---------------

AuditLogEntry
~~~~~~~~~~~~~

.. attributetable:: AuditLogEntry

.. autoclass:: AuditLogEntry
    :members:

Data Classes
------------

AuditLogChanges
~~~~~~~~~~~~~~~

.. attributetable:: AuditLogChanges

.. class:: AuditLogChanges

    An audit log change set.

    .. attribute:: before

        The old value. The attribute has the type of :class:`AuditLogDiff`.

        Depending on the :class:`AuditLogActionCategory` retrieved by
        :attr:`~AuditLogEntry.category`\, the data retrieved by this
        attribute differs:

        +----------------------------------------+---------------------------------------------------+
        |                Category                |                    Description                    |
        +----------------------------------------+---------------------------------------------------+
        | :attr:`~AuditLogActionCategory.create` | All attributes are set to ``None``.               |
        +----------------------------------------+---------------------------------------------------+
        | :attr:`~AuditLogActionCategory.delete` | All attributes are set the value before deletion. |
        +----------------------------------------+---------------------------------------------------+
        | :attr:`~AuditLogActionCategory.update` | All attributes are set the value before updating. |
        +----------------------------------------+---------------------------------------------------+
        | ``None``                               | No attributes are set.                            |
        +----------------------------------------+---------------------------------------------------+

    .. attribute:: after

        The new value. The attribute has the type of :class:`AuditLogDiff`.

        Depending on the :class:`AuditLogActionCategory` retrieved by
        :attr:`~AuditLogEntry.category`\, the data retrieved by this
        attribute differs:

        +----------------------------------------+--------------------------------------------------+
        |                Category                |                   Description                    |
        +----------------------------------------+--------------------------------------------------+
        | :attr:`~AuditLogActionCategory.create` | All attributes are set to the created value      |
        +----------------------------------------+--------------------------------------------------+
        | :attr:`~AuditLogActionCategory.delete` | All attributes are set to ``None``               |
        +----------------------------------------+--------------------------------------------------+
        | :attr:`~AuditLogActionCategory.update` | All attributes are set the value after updating. |
        +----------------------------------------+--------------------------------------------------+
        | ``None``                               | No attributes are set.                           |
        +----------------------------------------+--------------------------------------------------+

AuditLogDiff
~~~~~~~~~~~~

.. attributetable:: AuditLogDiff

.. class:: AuditLogDiff

    Represents an audit log "change" object. A change object has dynamic
    attributes that depend on the type of action being done. Certain actions
    map to certain attributes being set.

    Note that accessing an attribute that does not match the specified action
    will lead to an attribute error.

    To get a list of attributes that have been set, you can iterate over
    them. To see a list of all possible attributes that could be set based
    on the action being done, check the documentation for :class:`AuditLogAction`,
    otherwise check the documentation below for all attributes that are possible.

    .. container:: operations

        .. describe:: iter(diff)

            Returns an iterator over (attribute, value) tuple of this diff.

    .. attribute:: name

        A name of something.

        :type: :class:`str`

    .. attribute:: icon

        A guild's or role's icon.

        See also :attr:`Guild.icon` or :attr:`Role.icon`.

        :type: :class:`Asset`

    .. attribute:: splash

        The guild's invite splash. See also :attr:`Guild.splash`.

        :type: :class:`Asset`

    .. attribute:: discovery_splash

        The guild's discovery splash. See also :attr:`Guild.discovery_splash`.

        :type: :class:`Asset`

    .. attribute:: banner

        The guild's banner. See also :attr:`Guild.banner`.

        :type: :class:`Asset`

    .. attribute:: owner

        The guild's owner. See also :attr:`Guild.owner`

        :type: Union[:class:`Member`, :class:`User`, :class:`Object`]

    .. attribute:: region

        The guild's voice region. See also :attr:`Guild.region`.

        :type: :class:`str`

    .. attribute:: afk_channel

        The guild's AFK channel.

        If this could not be found, then it falls back to a :class:`Object`
        with the ID being set.

        See :attr:`Guild.afk_channel`.

        :type: Union[:class:`VoiceChannel`, :class:`Object`]

    .. attribute:: system_channel

        The guild's system channel.

        If this could not be found, then it falls back to a :class:`Object`
        with the ID being set.

        See :attr:`Guild.system_channel`.

        :type: Union[:class:`TextChannel`, :class:`Object`]


    .. attribute:: rules_channel

        The guild's rules channel.

        If this could not be found then it falls back to a :class:`Object`
        with the ID being set.

        See :attr:`Guild.rules_channel`.

        :type: Union[:class:`TextChannel`, :class:`Object`]


    .. attribute:: public_updates_channel

        The guild's public updates channel.

        If this could not be found then it falls back to a :class:`Object`
        with the ID being set.

        See :attr:`Guild.public_updates_channel`.

        :type: Union[:class:`TextChannel`, :class:`Object`]

    .. attribute:: afk_timeout

        The guild's AFK timeout. See :attr:`Guild.afk_timeout`.

        :type: :class:`int`

    .. attribute:: mfa_level

        The guild's MFA level. See :attr:`Guild.mfa_level`.

        :type: :class:`int`

    .. attribute:: widget_enabled

        The guild's widget has been enabled or disabled.

        :type: :class:`bool`

    .. attribute:: widget_channel

        The widget's channel.

        If this could not be found then it falls back to a :class:`Object`
        with the ID being set.

        :type: Union[:class:`abc.GuildChannel`, :class:`Object`]

    .. attribute:: verification_level

        The guild's verification level.

        See also :attr:`Guild.verification_level`.

        :type: :class:`VerificationLevel`

    .. attribute:: premium_progress_bar_enabled

        Whether the guild's premium progress bar is enabled.

        See also :attr:`Guild.premium_progress_bar_enabled`.

        :type: :class:`bool`

    .. attribute:: default_notifications

        The guild's default notification level.

        See also :attr:`Guild.default_notifications`.

        :type: :class:`NotificationLevel`

    .. attribute:: explicit_content_filter

        The guild's content filter.

        See also :attr:`Guild.explicit_content_filter`.

        :type: :class:`ContentFilter`

    .. attribute:: default_message_notifications

        The guild's default message notification setting.

        :type: :class:`int`

    .. attribute:: vanity_url_code

        The guild's vanity URL code.

        See also :meth:`Guild.vanity_invite`, :meth:`Guild.edit`, and :attr:`Guild.vanity_url_code`.

        :type: :class:`str`

    .. attribute:: preferred_locale

        The guild's preferred locale.

        :type: :class:`Locale`

    .. attribute:: position

        The position of a :class:`Role` or :class:`abc.GuildChannel`.

        :type: :class:`int`

    .. attribute:: type

        The type of channel/thread, sticker, webhook, onboarding prompt, integration (:class:`str`), or permission overwrite (:class:`int`).

        :type: Union[:class:`ChannelType`, :class:`StickerType`, :class:`WebhookType`, :class:`OnboardingPromptType`, :class:`str`, :class:`int`]

    .. attribute:: topic

        The topic of a :class:`TextChannel`, :class:`StageChannel`, :class:`StageInstance` or :class:`ForumChannel`.

        See also :attr:`TextChannel.topic`, :attr:`StageChannel.topic`,
        :attr:`StageInstance.topic` or :attr:`ForumChannel.topic`.

        :type: :class:`str`

    .. attribute:: bitrate

        The bitrate of a :class:`VoiceChannel` or :class:`StageChannel`.

        See also :attr:`VoiceChannel.bitrate` or :attr:`StageChannel.bitrate`.

        :type: :class:`int`

    .. attribute:: overwrites

        A list of permission overwrite tuples that represents a target and a
        :class:`PermissionOverwrite` for said target.

        The first element is the object being targeted, which can either
        be a :class:`Member` or :class:`User` or :class:`Role`. If this object
        is not found then it is a :class:`Object` with an ID being filled and
        a ``type`` attribute set to either ``'role'`` or ``'member'`` to help
        decide what type of ID it is.

        :type: List[Tuple[Union[:class:`Member`, :class:`User`, :class:`Role`, :class:`Object`], :class:`PermissionOverwrite`]]

    .. attribute:: privacy_level

        The privacy level of the stage instance or guild scheduled event.

        :type: Union[:class:`StagePrivacyLevel`, :class:`GuildScheduledEventPrivacyLevel`]

    .. attribute:: roles

        A list of roles being added or removed from a member.

        If a role is not found then it is a :class:`Object` with the ID and name being
        filled in.

        :type: List[Union[:class:`Role`, :class:`Object`]]

    .. attribute:: nick

        The nickname of a member.

        See also :attr:`Member.nick`

        :type: Optional[:class:`str`]

    .. attribute:: deaf

        Whether the member is being server deafened.

        See also :attr:`VoiceState.deaf`.

        :type: :class:`bool`

    .. attribute:: mute

        Whether the member is being server muted.

        See also :attr:`VoiceState.mute`.

        :type: :class:`bool`

    .. attribute:: permissions

        The permissions of a role.

        See also :attr:`Role.permissions`.

        :type: :class:`Permissions`

    .. attribute:: colour
                   color

        The colour of a role.

        See also :attr:`Role.colour`

        :type: :class:`Colour`

    .. attribute:: hoist

        Whether the role is being hoisted or not.

        See also :attr:`Role.hoist`

        :type: :class:`bool`

    .. attribute:: mentionable

        Whether the role is mentionable or not.

        See also :attr:`Role.mentionable`

        :type: :class:`bool`

    .. attribute:: code

        The invite's code.

        See also :attr:`Invite.code`

        :type: :class:`str`

    .. attribute:: channel

        A guild channel.

        If the channel is not found then it is a :class:`Object` with the ID
        being set. In some cases the channel name is also set.

        :type: Union[:class:`abc.GuildChannel`, :class:`Object`]

    .. attribute:: inviter

        The user who created the invite.

        See also :attr:`Invite.inviter`.

        :type: Optional[:class:`User`, :class:`Object`]

    .. attribute:: max_uses

        The invite's max uses.

        See also :attr:`Invite.max_uses`.

        :type: :class:`int`

    .. attribute:: uses

        The invite's current uses.

        See also :attr:`Invite.uses`.

        :type: :class:`int`

    .. attribute:: max_age

        The invite's max age in seconds.

        See also :attr:`Invite.max_age`.

        :type: :class:`int`

    .. attribute:: temporary

        If the invite is a temporary invite.

        See also :attr:`Invite.temporary`.

        :type: :class:`bool`

    .. attribute:: allow
                   deny

        The permissions being allowed or denied.

        :type: :class:`Permissions`

    .. attribute:: id

        The ID of the object being changed.

        :type: :class:`int`

    .. attribute:: avatar

        The avatar of a member.

        See also :attr:`User.avatar`.

        :type: :class:`Asset`

    .. attribute:: slowmode_delay

        The number of seconds members have to wait before
        sending another message or creating another thread in the channel.

        See also :attr:`TextChannel.slowmode_delay`, :attr:`VoiceChannel.slowmode_delay`,
        :attr:`StageChannel.slowmode_delay`, :attr:`ForumChannel.slowmode_delay`,
        or :attr:`Thread.slowmode_delay`.

        :type: :class:`int`

    .. attribute:: default_thread_slowmode_delay

        The default number of seconds members have to wait before
        sending another message in new threads created in the channel.

        See also :attr:`TextChannel.default_thread_slowmode_delay` or
        :attr:`ForumChannel.default_thread_slowmode_delay`.

        :type: :class:`int`

    .. attribute:: rtc_region

        The region for the voice or stage channel's voice communication.
        A value of ``None`` indicates automatic voice region detection.

        See also :attr:`VoiceChannel.rtc_region` or :attr:`StageChannel.rtc_region`.

        :type: :class:`str`

    .. attribute:: video_quality_mode

        The camera video quality for the voice or stage channel's participants.

        See also :attr:`VoiceChannel.video_quality_mode` or :attr:`StageChannel.video_quality_mode`.

        :type: :class:`VideoQualityMode`

    .. attribute:: user_limit

        The voice channel's user limit.

        See also :attr:`VoiceChannel.user_limit`, or :attr:`StageChannel.user_limit`.

        :type: :class:`int`

    .. attribute:: nsfw

        Whether the channel is marked as "not safe for work".

        See also :attr:`TextChannel.nsfw`, :attr:`VoiceChannel.nsfw`, :attr:`StageChannel.nsfw`, or :attr:`ForumChannel.nsfw`.

        :type: :class:`bool`

    .. attribute:: format_type

        The format type of a sticker being changed.

        See also :attr:`GuildSticker.format`

        :type: :class:`StickerFormatType`

    .. attribute:: emoji

        The name of the sticker's or role's emoji being changed.

        See also :attr:`GuildSticker.emoji` or :attr:`Role.emoji`.

        :type: :class:`str`

    .. attribute:: description

        The description of a guild, sticker or a guild scheduled event being changed.

        See also :attr:`Guild.description`, :attr:`GuildSticker.description`, :attr:`GuildScheduledEvent.description`

        :type: :class:`str`

    .. attribute:: available

        The availability of a sticker being changed.

        See also :attr:`GuildSticker.available`

        :type: :class:`bool`

    .. attribute:: archived

        The thread is now archived.

        :type: :class:`bool`

    .. attribute:: locked

        The thread is being locked or unlocked.

        :type: :class:`bool`

    .. attribute:: auto_archive_duration

        The thread's auto archive duration being changed.

        See also :attr:`Thread.auto_archive_duration`

        :type: :class:`int`

    .. attribute:: default_auto_archive_duration

        The default auto archive duration for newly created threads being changed.

        :type: :class:`int`

    .. attribute:: invitable

        Whether non-moderators can add other non-moderators to the thread.

        :type: :class:`bool`

    .. attribute:: timeout

        The datetime when the timeout expires, if any.

        :type: :class:`datetime.datetime`

    .. attribute:: entity_type

        The entity type of a guild scheduled event being changed.

        :type: :class:`GuildScheduledEventEntityType`

    .. attribute:: location

        The location of a guild scheduled event being changed.

        :type: :class:`str`

    .. attribute:: status

        The status of a guild scheduled event being changed.

        :type: :class:`GuildScheduledEventStatus`

    .. attribute:: image

        The cover image of a guild scheduled event being changed.

        :type: :class:`Asset`

    .. attribute:: command_permissions

        A mapping of target ID to guild permissions of an application command.

        Note that only changed permission entries are included,
        not necessarily all of the command's permissions.

        :type: Dict[:class:`int`, :class:`ApplicationCommandPermissions`]

    .. attribute:: application_id

        The ID of the application that created a webhook.

        :type: :class:`int`

    .. attribute:: flags

        The channel's flags.

        See also :attr:`abc.GuildChannel.flags` or :attr:`Thread.flags`.

        :type: :class:`ChannelFlags`

    .. attribute:: system_channel_flags

        The guild's system channel settings.

        See also :attr:`Guild.system_channel_flags`.

        :type: :class:`SystemChannelFlags`

    .. attribute:: enabled

        Whether something was enabled or disabled.

        :type: :class:`bool`

    .. attribute:: trigger_type

        The trigger type of an auto moderation rule being changed.

        :type: :class:`AutoModTriggerType`

    .. attribute:: event_type

        The event type of an auto moderation rule being changed.

        :type: :class:`AutoModEventType`

    .. attribute:: actions

        The list of actions of an auto moderation rule being changed.

        :type: List[:class:`AutoModAction`]

    .. attribute:: trigger_metadata

        The additional trigger metadata of an auto moderation rule being changed.

        :type: :class:`AutoModTriggerMetadata`

    .. attribute:: exempt_roles

        The list of roles that are exempt from an auto moderation rule being changed.

        If a role is not found then it is an :class:`Object` with the ID being set.

        :type: List[Union[:class:`Role`, :class:`Object`]]

    .. attribute:: exempt_channels

        The list of channels that are exempt from an auto moderation rule being changed.

        If a channel is not found then it is an :class:`Object` with the ID being set.

        :type: List[Union[:class:`abc.GuildChannel`, :class:`Object`]]

    .. attribute:: applied_tags

        The tags applied to a thread in a forum channel being changed.

        If a tag is not found, then it is an :class:`Object` with the ID
        being set.

        :type: List[Union[:class:`ForumTag`, :class:`Object`]]

    .. attribute:: available_tags

        The available tags for threads in a forum channel being changed.

        :type: List[:class:`ForumTag`]

    .. attribute:: default_reaction

        The default emoji shown for reacting to threads in a forum channel being changed.

        Due to a Discord limitation, this will have an empty
        :attr:`~PartialEmoji.name` if it is a custom :class:`PartialEmoji`.

        :type: Optional[Union[:class:`Emoji`, :class:`PartialEmoji`]]

    .. attribute:: default_sort_order

        The default sort order of threads in a forum channel being changed.

        :type: Optional[:class:`ThreadSortOrder`]

    .. attribute:: options

        The list of options of an onboarding prompt being changed.

        :type: List[:class:`OnboardingPromptOption`]

    .. attribute:: prompts

        The list of prompts of an onboarding configuration being changed.

        :type: List[:class:`OnboardingPrompt`]

    .. attribute:: default_channels

        The list of default channels of an onboarding configuration being changed.

        :type: List[Union[:class:`abc.GuildChannel`, :class:`Object`]]

    .. attribute:: title

        The title of an onboarding prompt being changed.

        :type: :class:`str`

    .. attribute:: single_select

        Whether users are limited to selecting one option for the onboarding prompt.

        :type: :class:`bool`

    .. attribute:: required

        Whether an onboarding prompt is required.

        :type: :class:`bool`

    .. attribute:: in_onboarding

        Whether an onboarding prompt is present in the initial onboarding flow.

        :type: :class:`bool`


Enumerations
------------

AuditLogAction
~~~~~~~~~~~~~~

.. class:: AuditLogAction

    Represents the type of action being done for a :class:`AuditLogEntry`\,
    which is retrievable via :meth:`Guild.audit_logs` or via the :func:`on_audit_log_entry_create` event.

    .. attribute:: guild_update

        The guild has updated. Things that trigger this include:

        - Changing the guild vanity URL
        - Changing the guild invite splash
        - Changing the guild AFK channel or timeout
        - Changing the guild voice server region
        - Changing the guild icon, banner, or discovery splash
        - Changing the guild moderation settings
        - Changing things related to the guild widget

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Guild`.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.afk_channel`
        - :attr:`~AuditLogDiff.system_channel`
        - :attr:`~AuditLogDiff.afk_timeout`
        - :attr:`~AuditLogDiff.default_message_notifications`
        - :attr:`~AuditLogDiff.explicit_content_filter`
        - :attr:`~AuditLogDiff.mfa_level`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.owner`
        - :attr:`~AuditLogDiff.splash`
        - :attr:`~AuditLogDiff.discovery_splash`
        - :attr:`~AuditLogDiff.icon`
        - :attr:`~AuditLogDiff.banner`
        - :attr:`~AuditLogDiff.vanity_url_code`
        - :attr:`~AuditLogDiff.preferred_locale`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.rules_channel`
        - :attr:`~AuditLogDiff.public_updates_channel`
        - :attr:`~AuditLogDiff.widget_enabled`
        - :attr:`~AuditLogDiff.widget_channel`
        - :attr:`~AuditLogDiff.verification_level`
        - :attr:`~AuditLogDiff.premium_progress_bar_enabled`
        - :attr:`~AuditLogDiff.system_channel_flags`

    .. attribute:: channel_create

        A new channel was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        either a :class:`abc.GuildChannel` or :class:`Object` with an ID.

        A more filled out object in the :class:`Object` case can be found
        by using :attr:`~AuditLogEntry.after`.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.overwrites`
        - :attr:`~AuditLogDiff.topic`
        - :attr:`~AuditLogDiff.bitrate`
        - :attr:`~AuditLogDiff.rtc_region`
        - :attr:`~AuditLogDiff.video_quality_mode`
        - :attr:`~AuditLogDiff.default_auto_archive_duration`
        - :attr:`~AuditLogDiff.user_limit`
        - :attr:`~AuditLogDiff.slowmode_delay`
        - :attr:`~AuditLogDiff.default_thread_slowmode_delay`
        - :attr:`~AuditLogDiff.nsfw`
        - :attr:`~AuditLogDiff.available_tags`
        - :attr:`~AuditLogDiff.default_reaction`

    .. attribute:: channel_update

        A channel was updated. Things that trigger this include:

        - The channel name or topic was changed
        - The channel bitrate was changed

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`abc.GuildChannel` or :class:`Object` with an ID.

        A more filled out object in the :class:`Object` case can be found
        by using :attr:`~AuditLogEntry.after` or :attr:`~AuditLogEntry.before`.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.position`
        - :attr:`~AuditLogDiff.overwrites`
        - :attr:`~AuditLogDiff.topic`
        - :attr:`~AuditLogDiff.bitrate`
        - :attr:`~AuditLogDiff.rtc_region`
        - :attr:`~AuditLogDiff.video_quality_mode`
        - :attr:`~AuditLogDiff.default_auto_archive_duration`
        - :attr:`~AuditLogDiff.user_limit`
        - :attr:`~AuditLogDiff.slowmode_delay`
        - :attr:`~AuditLogDiff.default_thread_slowmode_delay`
        - :attr:`~AuditLogDiff.nsfw`
        - :attr:`~AuditLogDiff.available_tags`
        - :attr:`~AuditLogDiff.default_reaction`

    .. attribute:: channel_delete

        A channel was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        an :class:`Object` with an ID.

        A more filled out object can be found by using the
        :attr:`~AuditLogEntry.before` object.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.overwrites`
        - :attr:`~AuditLogDiff.topic`
        - :attr:`~AuditLogDiff.bitrate`
        - :attr:`~AuditLogDiff.rtc_region`
        - :attr:`~AuditLogDiff.video_quality_mode`
        - :attr:`~AuditLogDiff.default_auto_archive_duration`
        - :attr:`~AuditLogDiff.user_limit`
        - :attr:`~AuditLogDiff.slowmode_delay`
        - :attr:`~AuditLogDiff.default_thread_slowmode_delay`
        - :attr:`~AuditLogDiff.nsfw`
        - :attr:`~AuditLogDiff.available_tags`
        - :attr:`~AuditLogDiff.default_reaction`

    .. attribute:: overwrite_create

        A channel permission overwrite was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`abc.GuildChannel` or :class:`Object` with an ID.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        either a :class:`Role` or :class:`Member`. If the object is not found
        then it is a :class:`Object` with an ID being filled, a name, and a
        ``type`` attribute set to either ``'role'`` or ``'member'`` to help
        dictate what type of ID it is.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.deny`
        - :attr:`~AuditLogDiff.allow`
        - :attr:`~AuditLogDiff.id`
        - :attr:`~AuditLogDiff.type`

        .. versionchanged:: 2.6
            :attr:`~AuditLogDiff.type` for this action is now an :class:`int`.

    .. attribute:: overwrite_update

        A channel permission overwrite was changed, this is typically
        when the permission values change.

        See :attr:`overwrite_create` for more information on how the
        :attr:`~AuditLogEntry.target` and :attr:`~AuditLogEntry.extra` fields
        are set.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.deny`
        - :attr:`~AuditLogDiff.allow`
        - :attr:`~AuditLogDiff.id`
        - :attr:`~AuditLogDiff.type`

        .. versionchanged:: 2.6
            :attr:`~AuditLogDiff.type` for this action is now an :class:`int`.

    .. attribute:: overwrite_delete

        A channel permission overwrite was deleted.

        See :attr:`overwrite_create` for more information on how the
        :attr:`~AuditLogEntry.target` and :attr:`~AuditLogEntry.extra` fields
        are set.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.deny`
        - :attr:`~AuditLogDiff.allow`
        - :attr:`~AuditLogDiff.id`
        - :attr:`~AuditLogDiff.type`

        .. versionchanged:: 2.6
            :attr:`~AuditLogDiff.type` for this action is now an :class:`int`.

    .. attribute:: kick

        A member was kicked.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`User` who got kicked. If the user is not found then it is
        a :class:`Object` with the user's ID.

        When this is the action, :attr:`~AuditLogEntry.changes` is empty.

    .. attribute:: member_prune

        A member prune was triggered.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        set to ``None``.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with two attributes:

        - ``delete_members_days``: An integer specifying how far the prune was.
        - ``members_removed``: An integer specifying how many members were removed.

        When this is the action, :attr:`~AuditLogEntry.changes` is empty.

    .. attribute:: ban

        A member was banned.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`User` who got banned. If the user is not found then it is
        a :class:`Object` with the user's ID.

        When this is the action, :attr:`~AuditLogEntry.changes` is empty.

    .. attribute:: unban

        A member was unbanned.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`User` who got unbanned. If the user is not found then it is
        a :class:`Object` with the user's ID.

        When this is the action, :attr:`~AuditLogEntry.changes` is empty.

    .. attribute:: member_update

        A member has updated. This triggers in the following situations:

        - A nickname was changed
        - They were server muted or deafened (or it was undone)
        - They were timed out

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member` or :class:`User` who got updated. If the user is not found then it is
        a :class:`Object` with the user's ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.nick`
        - :attr:`~AuditLogDiff.mute`
        - :attr:`~AuditLogDiff.deaf`
        - :attr:`~AuditLogDiff.timeout`

    .. attribute:: member_role_update

        A member's role has been updated. This triggers when a member
        either gains a role or loses a role.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member` or :class:`User` who got the role. If the user is not found then it is
        a :class:`Object` with the user's ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.roles`

    .. attribute:: member_move

        A member's voice channel has been updated. This triggers when a
        member is moved to a different voice channel.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with two attributes:

        - ``channel``: A :class:`TextChannel` or :class:`Object` with the channel ID where the members were moved.
        - ``count``: An integer specifying how many members were moved.

        .. versionadded:: 1.3

    .. attribute:: member_disconnect

        A member's voice state has changed. This triggers when a
        member is force disconnected from voice.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with one attribute:

        - ``count``: An integer specifying how many members were disconnected.

        .. versionadded:: 1.3

    .. attribute:: bot_add

        A bot was added to the guild.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member` or :class:`User` which was added to the guild. If the user is not found then it is
        a :class:`Object` with an ID.

        .. versionadded:: 1.3

    .. attribute:: role_create

        A new role was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Role` or a :class:`Object` with the ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.colour`
        - :attr:`~AuditLogDiff.mentionable`
        - :attr:`~AuditLogDiff.hoist`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.permissions`
        - :attr:`~AuditLogDiff.icon`
        - :attr:`~AuditLogDiff.emoji`

    .. attribute:: role_update

        A role was updated. This triggers in the following situations:

        - The name has changed
        - The permissions have changed
        - The colour has changed
        - Its hoist/mentionable state has changed

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Role` or a :class:`Object` with the ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.colour`
        - :attr:`~AuditLogDiff.mentionable`
        - :attr:`~AuditLogDiff.hoist`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.permissions`
        - :attr:`~AuditLogDiff.icon`
        - :attr:`~AuditLogDiff.emoji`

    .. attribute:: role_delete

        A role was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.colour`
        - :attr:`~AuditLogDiff.mentionable`
        - :attr:`~AuditLogDiff.hoist`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.permissions`
        - :attr:`~AuditLogDiff.icon`
        - :attr:`~AuditLogDiff.emoji`

    .. attribute:: invite_create

        An invite was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Invite` that was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.max_age`
        - :attr:`~AuditLogDiff.code`
        - :attr:`~AuditLogDiff.temporary`
        - :attr:`~AuditLogDiff.inviter`
        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.uses`
        - :attr:`~AuditLogDiff.max_uses`

    .. attribute:: invite_update

        An invite was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Invite` that was updated.

    .. attribute:: invite_delete

        An invite was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Invite` that was deleted.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.max_age`
        - :attr:`~AuditLogDiff.code`
        - :attr:`~AuditLogDiff.temporary`
        - :attr:`~AuditLogDiff.inviter`
        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.uses`
        - :attr:`~AuditLogDiff.max_uses`

    .. attribute:: webhook_create

        A webhook was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Webhook` or :class:`Object` with the webhook ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.application_id`
        - :attr:`~AuditLogDiff.avatar`

        .. versionchanged:: 2.6
            Added :attr:`~AuditLogDiff.application_id`.

        .. versionchanged:: 2.6
            :attr:`~AuditLogDiff.type` for this action is now a :class:`WebhookType`.

        .. versionchanged:: 2.6
            Added support for :class:`Webhook` instead of plain :class:`Object`\s.

    .. attribute:: webhook_update

        A webhook was updated. This trigger in the following situations:

        - The webhook name changed
        - The webhook channel changed

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Webhook` or :class:`Object` with the webhook ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.avatar`

        .. versionchanged:: 2.6
            Added support for :class:`Webhook` instead of plain :class:`Object`\s.

    .. attribute:: webhook_delete

        A webhook was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the webhook ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.application_id`
        - :attr:`~AuditLogDiff.avatar`

        .. versionchanged:: 2.6
            Added :attr:`~AuditLogDiff.application_id`.

        .. versionchanged:: 2.6
            :attr:`~AuditLogDiff.type` for this action is now a :class:`WebhookType`.

    .. attribute:: emoji_create

        An emoji was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Emoji` or :class:`Object` with the emoji ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`

    .. attribute:: emoji_update

        An emoji was updated. This triggers when the name has changed.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Emoji` or :class:`Object` with the emoji ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`

    .. attribute:: emoji_delete

        An emoji was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the emoji ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`

    .. attribute:: message_delete

        A message was deleted by a moderator. Note that this
        only triggers if the message was deleted by someone other than the author.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member` or :class:`User` who had their message deleted.
        If the user is not found then it is a :class:`Object` with the user's ID.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with two attributes:

        - ``count``: An integer specifying how many messages were deleted.
        - ``channel``: A :class:`TextChannel` or :class:`Object` with the channel ID where the message got deleted.

    .. attribute:: message_bulk_delete

        Messages were bulk deleted by a moderator.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`TextChannel` or :class:`Object` with the ID of the channel that was purged.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with one attribute:

        - ``count``: An integer specifying how many messages were deleted.

        .. versionadded:: 1.3

    .. attribute:: message_pin

        A message was pinned in a channel.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member` or :class:`User` who had their message pinned.
        If the user is not found then it is a :class:`Object` with the user's ID.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with two attributes:

        - ``channel``: A :class:`TextChannel` or :class:`Object` with the channel ID where the message was pinned.
        - ``message_id``: the ID of the message which was pinned.

        .. versionadded:: 1.3

    .. attribute:: message_unpin

        A message was unpinned in a channel.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member` or :class:`User` who had their message unpinned.
        If the user is not found then it is a :class:`Object` with the user's ID.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with two attributes:

        - ``channel``: A :class:`TextChannel` or :class:`Object` with the channel ID where the message was unpinned.
        - ``message_id``: the ID of the message which was unpinned.

        .. versionadded:: 1.3

    .. attribute:: integration_create

        A guild integration was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`PartialIntegration` or :class:`Object` with the integration ID
        of the integration which was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.type`

        .. versionadded:: 1.3

        .. versionchanged:: 2.6
            Added support for :class:`PartialIntegration` instead of plain :class:`Object`\s.

    .. attribute:: integration_update

        A guild integration was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`PartialIntegration` or :class:`Object` with the integration ID
        of the integration which was updated.

        .. versionadded:: 1.3

        .. versionchanged:: 2.6
            Added support for :class:`PartialIntegration` instead of plain :class:`Object`\s.

    .. attribute:: integration_delete

        A guild integration was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the integration ID of the integration which was deleted.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.type`

        .. versionadded:: 1.3

    .. attribute:: guild_scheduled_event_create

        A guild scheduled event was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`GuildScheduledEvent` or :class:`Object` with the ID of the event
        which was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.privacy_level`
        - :attr:`~AuditLogDiff.status`
        - :attr:`~AuditLogDiff.entity_type`
        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.location`
        - :attr:`~AuditLogDiff.image`

        .. versionadded:: 2.3

    .. attribute:: guild_scheduled_event_update

        A guild scheduled event was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`GuildScheduledEvent` or :class:`Object` with the ID of the event
        which was updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.privacy_level`
        - :attr:`~AuditLogDiff.status`
        - :attr:`~AuditLogDiff.entity_type`
        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.location`
        - :attr:`~AuditLogDiff.image`

        .. versionadded:: 2.3

    .. attribute:: guild_scheduled_event_delete

        A guild scheduled event was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the ID of the event which was deleted.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.privacy_level`
        - :attr:`~AuditLogDiff.status`
        - :attr:`~AuditLogDiff.entity_type`
        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.location`
        - :attr:`~AuditLogDiff.image`

        .. versionadded:: 2.3

    .. attribute:: stage_instance_create

        A stage instance was started.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`StageInstance` or :class:`Object` with the ID of the stage
        instance which was created.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with one attribute:

        - ``channel``: The :class:`StageChannel` or :class:`Object` with the channel ID where the stage instance was started.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.topic`
        - :attr:`~AuditLogDiff.privacy_level`

        .. versionadded:: 2.0

    .. attribute:: stage_instance_update

        A stage instance was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`StageInstance` or :class:`Object` with the ID of the stage
        instance which was updated.

        See :attr:`stage_instance_create` for more information on how the
        :attr:`~AuditLogEntry.extra` field is set.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.topic`
        - :attr:`~AuditLogDiff.privacy_level`

        .. versionadded:: 2.0

    .. attribute:: stage_instance_delete

        A stage instance was ended.

        See :attr:`stage_instance_create` for more information on how the
        :attr:`~AuditLogEntry.extra` field is set.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.topic`
        - :attr:`~AuditLogDiff.privacy_level`

        .. versionadded:: 2.0

    .. attribute:: sticker_create

        A sticker was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`GuildSticker` or :class:`Object` with the ID of the sticker
        which was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.emoji`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.format_type`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.available`

        .. versionadded:: 2.0

    .. attribute:: sticker_update

        A sticker was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`GuildSticker` or :class:`Object` with the ID of the sticker
        which was updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.emoji`
        - :attr:`~AuditLogDiff.description`

        .. versionadded:: 2.0

    .. attribute:: sticker_delete

        A sticker was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the ID of the sticker which was deleted.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.emoji`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.format_type`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.available`

        .. versionadded:: 2.0

    .. attribute:: thread_create

        A thread was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Thread` or :class:`Object` with the ID of the thread which
        was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.archived`
        - :attr:`~AuditLogDiff.locked`
        - :attr:`~AuditLogDiff.auto_archive_duration`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.slowmode_delay`
        - :attr:`~AuditLogDiff.invitable`
        - :attr:`~AuditLogDiff.flags`
        - :attr:`~AuditLogDiff.applied_tags`

        .. versionadded:: 2.0

    .. attribute:: thread_update

        A thread was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Thread` or :class:`Object` with the ID of the thread which
        was updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.archived`
        - :attr:`~AuditLogDiff.locked`
        - :attr:`~AuditLogDiff.auto_archive_duration`
        - :attr:`~AuditLogDiff.slowmode_delay`
        - :attr:`~AuditLogDiff.invitable`
        - :attr:`~AuditLogDiff.flags`
        - :attr:`~AuditLogDiff.applied_tags`

        .. versionadded:: 2.0

    .. attribute:: thread_delete

        A thread was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the ID of the thread which was deleted.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.archived`
        - :attr:`~AuditLogDiff.locked`
        - :attr:`~AuditLogDiff.auto_archive_duration`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.slowmode_delay`
        - :attr:`~AuditLogDiff.invitable`
        - :attr:`~AuditLogDiff.flags`
        - :attr:`~AuditLogDiff.applied_tags`

        .. versionadded:: 2.0

    .. attribute:: application_command_permission_update

        The permissions of an application command were updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`ApplicationCommand`, :class:`PartialIntegration`, or :class:`Object`
        with the ID of the command whose permissions were updated or the application ID
        if these are application-wide permissions.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with one attribute:

        - ``integration``: The :class:`PartialIntegration` or :class:`Object` with the application ID of the associated application.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.command_permissions`

        .. versionadded:: 2.5

        .. versionchanged:: 2.6
            Added support for :class:`PartialIntegration`, and added ``integration`` to :attr:`~AuditLogEntry.extra`.

    .. attribute:: automod_rule_create

        An auto moderation rule was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`AutoModRule` or :class:`Object` with the ID of the auto moderation rule which
        was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.enabled`
        - :attr:`~AuditLogDiff.trigger_type`
        - :attr:`~AuditLogDiff.event_type`
        - :attr:`~AuditLogDiff.actions`
        - :attr:`~AuditLogDiff.trigger_metadata`
        - :attr:`~AuditLogDiff.exempt_roles`
        - :attr:`~AuditLogDiff.exempt_channels`

        .. versionadded:: 2.6

    .. attribute:: automod_rule_update

        An auto moderation rule was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`AutoModRule` or :class:`Object` with the ID of the auto moderation rule which
        was updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.enabled`
        - :attr:`~AuditLogDiff.trigger_type`
        - :attr:`~AuditLogDiff.event_type`
        - :attr:`~AuditLogDiff.actions`
        - :attr:`~AuditLogDiff.trigger_metadata`
        - :attr:`~AuditLogDiff.exempt_roles`
        - :attr:`~AuditLogDiff.exempt_channels`

        .. versionadded:: 2.6

    .. attribute:: automod_rule_delete

        An auto moderation rule was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the ID of the auto moderation rule which
        was deleted.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.enabled`
        - :attr:`~AuditLogDiff.trigger_type`
        - :attr:`~AuditLogDiff.event_type`
        - :attr:`~AuditLogDiff.actions`
        - :attr:`~AuditLogDiff.trigger_metadata`
        - :attr:`~AuditLogDiff.exempt_roles`
        - :attr:`~AuditLogDiff.exempt_channels`

        .. versionadded:: 2.6

    .. attribute:: automod_block_message

        A message was blocked by an auto moderation rule.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member` or :class:`User` who had their message blocked.
        If the user is not found then it is a :class:`Object` with the user's ID.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with these attributes:

        - ``channel``: A :class:`~abc.GuildChannel`, :class:`Thread` or :class:`Object` with the channel ID where the message got blocked. May also be ``None``.
        - ``rule_name``: A :class:`str` with the name of the rule that matched.
        - ``rule_trigger_type``: An :class:`AutoModTriggerType` value with the trigger type of the rule.

    .. attribute:: automod_send_alert_message

        An alert message was sent by an auto moderation rule.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member` or :class:`User` who had their message flagged.
        If the user is not found then it is a :class:`Object` with the user's ID.

        See :attr:`automod_block_message` for more information on how the
        :attr:`~AuditLogEntry.extra` field is set.

    .. attribute:: automod_timeout

        A user was timed out by an auto moderation rule.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member` or :class:`User` who was timed out.
        If the user is not found then it is a :class:`Object` with the user's ID.

        See :attr:`automod_block_message` for more information on how the
        :attr:`~AuditLogEntry.extra` field is set.

    .. attribute:: onboarding_prompt_create

        An onboarding prompt was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the ID of the onboarding prompt which
        was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.title`
        - :attr:`~AuditLogDiff.options`
        - :attr:`~AuditLogDiff.single_select`
        - :attr:`~AuditLogDiff.required`
        - :attr:`~AuditLogDiff.in_onboarding`
        - :attr:`~AuditLogDiff.type`

    .. attribute:: onboarding_prompt_update

        An onboarding prompt was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the ID of the onboarding prompt which
        was updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.title`
        - :attr:`~AuditLogDiff.options`
        - :attr:`~AuditLogDiff.single_select`
        - :attr:`~AuditLogDiff.required`
        - :attr:`~AuditLogDiff.in_onboarding`
        - :attr:`~AuditLogDiff.type`

    .. attribute:: onboarding_update

        An onboarding configuration was updated.

        When this is the action, :attr:`~AuditLogEntry.target` is ``None``.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.prompts`
        - :attr:`~AuditLogDiff.default_channels`
        - :attr:`~AuditLogDiff.enabled`

AuditLogActionCategory
~~~~~~~~~~~~~~~~~~~~~~

.. class:: AuditLogActionCategory

    Represents the category that the :class:`AuditLogAction` belongs to.

    This can be retrieved via :attr:`AuditLogEntry.category`.

    .. attribute:: create

        The action is the creation of something.

    .. attribute:: delete

        The action is the deletion of something.

    .. attribute:: update

        The action is the update of something.

Events
------

- :func:`on_audit_log_entry_create(entry) <disnake.on_audit_log_entry_create>`
