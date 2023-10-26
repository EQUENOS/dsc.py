.. SPDX-License-Identifier: MIT

.. currentmodule:: disnake

AutoMod
=======

This section documents everything related to Discord's :ddocs:`AutoMod features <resources/auto-moderation>`.

Discord Models
---------------

AutoModRule
~~~~~~~~~~~

.. attributetable:: AutoModRule

.. autoclass:: AutoModRule()
    :members:

AutoModActionExecution
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: AutoModActionExecution

.. autoclass:: AutoModActionExecution()
    :members:

Data Classes
------------

AutoModKeywordPresets
~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: AutoModKeywordPresets

.. autoclass:: AutoModKeywordPresets
    :members:

AutoModTriggerMetadata
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: AutoModTriggerMetadata

.. autoclass:: AutoModTriggerMetadata
    :members:

AutoModAction
~~~~~~~~~~~~~

.. attributetable:: AutoModAction

.. autoclass:: AutoModAction()
    :members:

AutoModBlockMessageAction
~~~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: AutoModBlockMessageAction

.. autoclass:: AutoModBlockMessageAction
    :members:

AutoModSendAlertAction
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: AutoModSendAlertAction

.. autoclass:: AutoModSendAlertAction
    :members:

AutoModTimeoutAction
~~~~~~~~~~~~~~~~~~~~

.. attributetable:: AutoModTimeoutAction

.. autoclass:: AutoModTimeoutAction
    :members:

AutoModBlockInteractionAction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: AutoModBlockInteractionAction

.. autoclass:: AutoModBlockInteractionAction
    :members:

Enumerations
------------

AutoModActionType
~~~~~~~~~~~~~~~~~

.. class:: AutoModActionType

    Represents the type of action an auto moderation rule will take upon execution.

    .. _automod_trigger_action_table:

    Based on the trigger type, different action types can be used:

    .. csv-table::
        :header: "Trigger Type", ``block_message``, ``send_alert_message``, ``timeout``, ``block_member_interaction``

        :attr:`~AutoModTriggerType.keyword`,        ✅, ✅, ✅, ❌
        :attr:`~AutoModTriggerType.spam`,           ✅, ✅, ❌, ❌
        :attr:`~AutoModTriggerType.keyword_preset`, ✅, ✅, ❌, ❌
        :attr:`~AutoModTriggerType.mention_spam`,   ✅, ✅, ✅, ❌
        :attr:`~AutoModTriggerType.member_profile`, ❌, ✅, ❌, ✅

    .. versionadded:: 2.6

    .. attribute:: block_message

        The rule will prevent matching messages from being posted.

    .. attribute:: send_alert_message

        The rule will send an alert to a specified channel.

    .. attribute:: timeout

        The rule will timeout the user that sent the message.

        .. note::
            Configuring this action type requires :attr:`~Permissions.moderate_members` permissions.

    .. attribute:: block_member_interaction

        The rule will prevent the user from using text, voice, or other interactions.

        .. versionadded:: 2.10

AutoModEventType
~~~~~~~~~~~~~~~~

.. class:: AutoModEventType

    Represents the type of event/context an auto moderation rule will be checked in.

    .. _automod_trigger_event_table:

    Based on the trigger type, different event types are used:

    .. csv-table::
        :header: "Trigger Type", ``message_send``, ``member_update``

        :attr:`~AutoModTriggerType.keyword`,        ✅, ❌
        :attr:`~AutoModTriggerType.spam`,           ✅, ❌
        :attr:`~AutoModTriggerType.keyword_preset`, ✅, ❌
        :attr:`~AutoModTriggerType.mention_spam`,   ✅, ❌
        :attr:`~AutoModTriggerType.member_profile`, ❌, ✅

    .. versionadded:: 2.6

    .. attribute:: message_send

        The rule will apply when a member sends or edits a message in the guild.

    .. attribute:: member_update

        The rule will apply when a member joins or edits their profile.

        .. versionadded:: 2.10

AutoModTriggerType
~~~~~~~~~~~~~~~~~~

.. class:: AutoModTriggerType

    Represents the type of content that can trigger an auto moderation rule.

    Trigger types only work with specific event types,
    refer to :ref:`this table <automod_trigger_event_table>` for more.

    .. versionadded:: 2.6

    .. versionchanged:: 2.9
        Removed obsolete ``harmful_link`` type.

    .. attribute:: keyword

        The rule will filter messages based on a custom keyword list.

        This trigger type requires additional :class:`metadata <AutoModTriggerMetadata>`.

    .. attribute:: spam

        The rule will filter messages suspected of being spam.

    .. attribute:: keyword_preset

        The rule will filter messages based on predefined lists containing commonly flagged words.

        This trigger type requires additional :class:`metadata <AutoModTriggerMetadata>`.

    .. attribute:: mention_spam

        The rule will filter messages based on the number of member/role mentions they contain.

        This trigger type requires additional :class:`metadata <AutoModTriggerMetadata>`.

    .. attribute:: member_profile

        The rule will filter member profiles based on a custom keyword list.

        This trigger type requires additional :class:`metadata <AutoModTriggerMetadata>`.

Events
------

- :func:`on_automod_action_execution(execution) <disnake.on_automod_action_execution>`
- :func:`on_automod_rule_create(rule) <disnake.on_automod_rule_create>`
- :func:`on_automod_rule_update(rule) <disnake.on_automod_rule_update>`
- :func:`on_automod_rule_delete(rule) <disnake.on_automod_rule_delete>`
