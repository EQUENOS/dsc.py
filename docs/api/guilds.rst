.. SPDX-License-Identifier: MIT

.. currentmodule:: disnake

Guilds
======

This section documents everything related to
:ddocs:`Guilds <resources/guild>` - main hubs for communication in Discord,
referred to as Servers in the official UI.

Discord Models
---------------

Guild
~~~~~

.. attributetable:: Guild

.. autoclass:: Guild()
    :members:
    :exclude-members: fetch_members, audit_logs

    .. automethod:: fetch_members
        :async-for:

    .. automethod:: audit_logs
        :async-for:

GuildPreview
~~~~~~~~~~~~

.. attributetable:: GuildPreview

.. autoclass:: GuildPreview()
    :members:

Template
~~~~~~~~

.. attributetable:: Template

.. autoclass:: Template()
    :members:

WelcomeScreen
~~~~~~~~~~~~~

.. attributetable:: WelcomeScreen

.. autoclass:: WelcomeScreen()
    :members:

BanEntry
~~~~~~~~

.. class:: BanEntry

    A :class:`~typing.NamedTuple` which represents a ban returned from :meth:`~Guild.bans`.

    .. attribute:: reason

        The reason this user was banned.

        :type: Optional[:class:`str`]
    .. attribute:: user

        The :class:`User` that was banned.

        :type: :class:`User`

BulkBanResult
~~~~~~~~~~~~~

.. class:: BulkBanResult

    A :class:`~typing.NamedTuple` which represents the successful and failed bans returned from :meth:`~Guild.bulk_ban`.

    .. versionadded:: 2.10

    .. attribute:: banned

        The users that were successfully banned.

        :type: Sequence[:class:`Object`]
    .. attribute:: failed

        The users that were not banned.

        :type: Sequence[:class:`Object`]

Onboarding
~~~~~~~~~~

.. attributetable:: Onboarding

.. autoclass:: Onboarding()
    :members:

OnboardingPrompt
~~~~~~~~~~~~~~~~

.. attributetable:: OnboardingPrompt

.. autoclass:: OnboardingPrompt()
    :members:

OnboardingPromptOption
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: OnboardingPromptOption

.. autoclass:: OnboardingPromptOption()
    :members:

IncidentsData
~~~~~~~~~~~~~

.. attributetable:: IncidentsData

.. autoclass:: IncidentsData()
    :members:

Data Classes
------------

SystemChannelFlags
~~~~~~~~~~~~~~~~~~

.. attributetable:: SystemChannelFlags

.. autoclass:: SystemChannelFlags()
    :members:

WelcomeScreenChannel
~~~~~~~~~~~~~~~~~~~~

.. attributetable:: WelcomeScreenChannel

.. autoclass:: WelcomeScreenChannel()

GuildBuilder
~~~~~~~~~~~~~

.. attributetable:: GuildBuilder

.. autoclass:: GuildBuilder()
    :members:
    :exclude-members: add_category_channel

Enumerations
------------

VerificationLevel
~~~~~~~~~~~~~~~~~

.. autoclass:: VerificationLevel()
    :members:

NotificationLevel
~~~~~~~~~~~~~~~~~

.. autoclass:: NotificationLevel()
    :members:

ContentFilter
~~~~~~~~~~~~~

.. autoclass:: ContentFilter()
    :members:

NSFWLevel
~~~~~~~~~

.. autoclass:: NSFWLevel()
    :members:

OnboardingPromptType
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: OnboardingPromptType()
    :members:

Events
------

- :func:`on_guild_join(guild) <disnake.on_guild_join>`
- :func:`on_guild_remove(guild) <disnake.on_guild_remove>`
- :func:`on_guild_update(before, after) <disnake.on_guild_update>`
- :func:`on_guild_available(guild) <disnake.on_guild_available>`
- :func:`on_guild_unavailable(guild) <disnake.on_guild_unavailable>`
