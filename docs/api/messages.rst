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

.. autoclass:: InteractionReference()
    :members:

InteractionMetadata
~~~~~~~~~~~~~~~~~~~

.. attributetable:: InteractionMetadata

.. autoclass:: InteractionMetadata()
    :members:

RoleSubscriptionData
~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RoleSubscriptionData

.. autoclass:: RoleSubscriptionData()
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

RawPollVoteActionEvent
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawPollVoteActionEvent

.. autoclass:: RawPollVoteActionEvent()
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

EmbedFlags
~~~~~~~~~~

.. attributetable:: EmbedFlags

.. autoclass:: EmbedFlags()
    :members:

EmbedMediaFlags
~~~~~~~~~~~~~~~

.. attributetable:: EmbedMediaFlags

.. autoclass:: EmbedMediaFlags()
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

Poll
~~~~

.. attributetable:: Poll

.. autoclass:: Poll
    :members:

PollAnswer
~~~~~~~~~~

.. attributetable:: PollAnswer

.. autoclass:: PollAnswer
    :members:

PollMedia
~~~~~~~~~

.. attributetable:: PollMedia

.. autoclass:: PollMedia
    :members:

ForwardedMessage
~~~~~~~~~~~~~~~~

.. attributetable:: ForwardedMessage

.. autoclass:: ForwardedMessage
    :members:

Enumerations
------------

MessageType
~~~~~~~~~~~

.. autoclass:: MessageType()
    :members:

PollLayoutType
~~~~~~~~~~~~~~

.. autoclass:: PollLayoutType()
    :members:

MessageReferenceType
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: MessageReferenceType()
    :members:

Events
------

- :func:`on_message(message) <disnake.on_message>`
- :func:`on_message_edit(before, after) <disnake.on_message_edit>`
- :func:`on_message_delete(message) <disnake.on_message_delete>`
- :func:`on_bulk_message_delete(messages) <disnake.on_bulk_message_delete>`
- :func:`on_poll_vote_add(member, answer) <disnake.on_poll_vote_add>`
- :func:`on_poll_vote_removed(member, answer) <disnake.on_poll_vote_remove>`

- :func:`on_raw_message_edit(payload) <disnake.on_raw_message_edit>`
- :func:`on_raw_message_delete(payload) <disnake.on_raw_message_delete>`
- :func:`on_raw_bulk_message_delete(payload) <disnake.on_raw_bulk_message_delete>`
- :func:`on_raw_poll_vote_add(payload) <disnake.on_raw_poll_vote_add>`
- :func:`on_raw_poll_vote_remove(payload) <disnake.on_raw_poll_vote_remove>`

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
