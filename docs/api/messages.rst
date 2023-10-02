.. SPDX-License-Identifier: MIT

.. currentmodule:: disnake

Messages
========

This section documents everything related to Discord messages.

Discord Models
---------------

Message
~~~~~~~

.. attributetable:: Message

.. autoclass:: Message()
    :members:

Reaction
~~~~~~~~

.. attributetable:: Reaction

.. autoclass:: Reaction()
    :members:
    :exclude-members: users

    .. automethod:: users
        :async-for:

BurstReaction
~~~~~~~~~~~~~~

.. attributetable:: BurstReaction

.. autoclass:: BurstReaction()
    :members:

Attachment
~~~~~~~~~~

.. attributetable:: Attachment

.. autoclass:: Attachment()
    :members:

DeletedReferencedMessage
~~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: DeletedReferencedMessage

.. autoclass:: DeletedReferencedMessage()
    :members:

InteractionReference
~~~~~~~~~~~~~~~~~~~~

.. attributetable:: InteractionReference

.. autoclass:: InteractionReference
    :members:

RoleSubscriptionData
~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RoleSubscriptionData

.. autoclass:: RoleSubscriptionData
    :members:

RawTypingEvent
~~~~~~~~~~~~~~

.. attributetable:: RawTypingEvent

.. autoclass:: RawTypingEvent()
    :members:

RawMessageDeleteEvent
~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawMessageDeleteEvent

.. autoclass:: RawMessageDeleteEvent()
    :members:

RawBulkMessageDeleteEvent
~~~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawBulkMessageDeleteEvent

.. autoclass:: RawBulkMessageDeleteEvent()
    :members:

RawMessageUpdateEvent
~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawMessageUpdateEvent

.. autoclass:: RawMessageUpdateEvent()
    :members:

RawReactionActionEvent
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawReactionActionEvent

.. autoclass:: RawReactionActionEvent()
    :members:

RawReactionClearEvent
~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawReactionClearEvent

.. autoclass:: RawReactionClearEvent()
    :members:

RawReactionClearEmojiEvent
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawReactionClearEmojiEvent

.. autoclass:: RawReactionClearEmojiEvent()
    :members:

Data Classes
------------

Embed
~~~~~

.. attributetable:: Embed

.. autoclass:: Embed
    :members:

File
~~~~

.. attributetable:: File

.. autoclass:: File
    :members:

MessageFlags
~~~~~~~~~~~~

.. attributetable:: MessageFlags

.. autoclass:: MessageFlags()
    :members:

AttachmentFlags
~~~~~~~~~~~~~~~

.. attributetable:: AttachmentFlags

.. autoclass:: AttachmentFlags()
    :members:

AllowedMentions
~~~~~~~~~~~~~~~

.. attributetable:: AllowedMentions

.. autoclass:: AllowedMentions
    :members:

MessageReference
~~~~~~~~~~~~~~~~

.. attributetable:: MessageReference

.. autoclass:: MessageReference
    :members:

PartialMessage
~~~~~~~~~~~~~~

.. attributetable:: PartialMessage

.. autoclass:: PartialMessage
    :members:

Enumerations
------------

MessageType
~~~~~~~~~~~

.. class:: MessageType

    Specifies the type of :class:`Message`. This is used to denote if a message
    is to be interpreted as a system message or a regular message.

    .. container:: operations

      .. describe:: x == y

          Checks if two messages are equal.
      .. describe:: x != y

          Checks if two messages are not equal.

    .. attribute:: default

        The default message type. This is the same as regular messages.
    .. attribute:: recipient_add

        The system message when a user is added to a group private
        message or a thread.
    .. attribute:: recipient_remove

        The system message when a user is removed from a group private
        message or a thread.
    .. attribute:: call

        The system message denoting call state, e.g. missed call, started call,
        etc.
    .. attribute:: channel_name_change

        The system message denoting that a channel's name has been changed.
    .. attribute:: channel_icon_change

        The system message denoting that a channel's icon has been changed.
    .. attribute:: pins_add

        The system message denoting that a pinned message has been added to a channel.
    .. attribute:: new_member

        The system message denoting that a new member has joined a Guild.

    .. attribute:: premium_guild_subscription

        The system message denoting that a member has "nitro boosted" a guild.
    .. attribute:: premium_guild_tier_1

        The system message denoting that a member has "nitro boosted" a guild
        and it achieved level 1.
    .. attribute:: premium_guild_tier_2

        The system message denoting that a member has "nitro boosted" a guild
        and it achieved level 2.
    .. attribute:: premium_guild_tier_3

        The system message denoting that a member has "nitro boosted" a guild
        and it achieved level 3.
    .. attribute:: channel_follow_add

        The system message denoting that an announcement channel has been followed.

        .. versionadded:: 1.3
    .. attribute:: guild_stream

        The system message denoting that a member is streaming in the guild.

        .. versionadded:: 1.7
    .. attribute:: guild_discovery_disqualified

        The system message denoting that the guild is no longer eligible for Server
        Discovery.

        .. versionadded:: 1.7
    .. attribute:: guild_discovery_requalified

        The system message denoting that the guild has become eligible again for Server
        Discovery.

        .. versionadded:: 1.7
    .. attribute:: guild_discovery_grace_period_initial_warning

        The system message denoting that the guild has failed to meet the Server
        Discovery requirements for one week.

        .. versionadded:: 1.7
    .. attribute:: guild_discovery_grace_period_final_warning

        The system message denoting that the guild has failed to meet the Server
        Discovery requirements for 3 weeks in a row.

        .. versionadded:: 1.7
    .. attribute:: thread_created

        The system message denoting that a thread has been created. This is only
        sent if the thread has been created from an older message. The period of time
        required for a message to be considered old cannot be relied upon and is up to
        Discord.

        .. versionadded:: 2.0
    .. attribute:: reply

        The system message denoting that the author is replying to a message.

        .. versionadded:: 2.0
    .. attribute:: application_command

        The system message denoting that an application (or "slash") command was executed.

        .. versionadded:: 2.0
    .. attribute:: guild_invite_reminder

        The system message sent as a reminder to invite people to the guild.

        .. versionadded:: 2.0
    .. attribute:: thread_starter_message

        The system message denoting the message in the thread that is the one that started the
        thread's conversation topic.

        .. versionadded:: 2.0
    .. attribute:: context_menu_command

        The system message denoting that a context menu command was executed.

        .. versionadded:: 2.3
    .. attribute:: auto_moderation_action

        The system message denoting that an auto moderation action was executed.

        .. versionadded:: 2.5
    .. attribute:: role_subscription_purchase

        The system message denoting that a role subscription was purchased.

        .. versionadded:: 2.9
    .. attribute:: interaction_premium_upsell

        The system message for an application premium subscription upsell.

        .. versionadded:: 2.8
    .. attribute:: stage_start

        The system message denoting the stage has been started.

        .. versionadded:: 2.9
    .. attribute:: stage_end

        The system message denoting the stage has ended.

        .. versionadded:: 2.9
    .. attribute:: stage_speaker

        The system message denoting a user has become a speaker.

        .. versionadded:: 2.9
    .. attribute:: stage_topic

        The system message denoting the stage topic has been changed.

        .. versionadded:: 2.9
    .. attribute:: guild_application_premium_subscription

        The system message denoting that a guild member has subscribed to an application.

        .. versionadded:: 2.8

Events
------

- :func:`on_message(message) <disnake.on_message>`
- :func:`on_message_edit(before, after) <disnake.on_message_edit>`
- :func:`on_message_delete(message) <disnake.on_message_delete>`
- :func:`on_bulk_message_delete(messages) <disnake.on_bulk_message_delete>`

- :func:`on_raw_message_edit(payload) <disnake.on_raw_message_edit>`
- :func:`on_raw_message_delete(payload) <disnake.on_raw_message_delete>`
- :func:`on_raw_bulk_message_delete(payload) <disnake.on_raw_bulk_message_delete>`

- :func:`on_reaction_add(reaction, user) <disnake.on_reaction_add>`
- :func:`on_reaction_remove(reaction, user) <disnake.on_reaction_remove>`
- :func:`on_reaction_clear(message, reactions) <disnake.on_reaction_clear>`
- :func:`on_reaction_clear_emoji(reaction) <disnake.on_reaction_clear_emoji>`

- :func:`on_raw_reaction_add(payload) <disnake.on_raw_reaction_add>`
- :func:`on_raw_reaction_remove(payload) <disnake.on_raw_reaction_remove>`
- :func:`on_raw_reaction_clear(payload) <disnake.on_raw_reaction_clear>`
- :func:`on_raw_reaction_clear_emoji(payload) <disnake.on_raw_reaction_clear_emoji>`

- :func:`on_typing(channel, user, when) <disnake.on_typing>`
- :func:`on_raw_typing(data) <disnake.on_raw_typing>`
