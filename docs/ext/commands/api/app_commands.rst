.. SPDX-License-Identifier: MIT

.. currentmodule:: disnake.ext.commands

Application Commands
====================

This section documents everything about handling application commands with this extension.

Classes
-------

Application Command
~~~~~~~~~~~~~~~~~~~

.. attributetable:: InvokableApplicationCommand

.. autoclass:: InvokableApplicationCommand
    :members:
    :exclude-members: before_invoke, after_invoke, error

    .. automethod:: InvokableApplicationCommand.before_invoke()
        :decorator:

    .. automethod:: InvokableApplicationCommand.after_invoke()
        :decorator:

    .. automethod:: InvokableApplicationCommand.error()
        :decorator:

Slash Command
~~~~~~~~~~~~~

.. attributetable:: InvokableSlashCommand

.. autoclass:: InvokableSlashCommand
    :members:
    :special-members: __call__
    :exclude-members: sub_command, sub_command_group, after_invoke, before_invoke, error

    .. automethod:: InvokableSlashCommand.sub_command(*args, **kwargs)
        :decorator:

    .. automethod:: InvokableSlashCommand.sub_command_group(*args, **kwargs)
        :decorator:

    .. automethod:: InvokableSlashCommand.after_invoke()
        :decorator:

    .. automethod:: InvokableSlashCommand.before_invoke()
        :decorator:

    .. automethod:: InvokableSlashCommand.error()
        :decorator:

Slash Subcommand
~~~~~~~~~~~~~~~~

.. attributetable:: SubCommand

.. autoclass:: SubCommand
    :members:
    :exclude-members: after_invoke, before_invoke, error

    .. automethod:: SubCommand.after_invoke()
        :decorator:

    .. automethod:: SubCommand.before_invoke()
        :decorator:

    .. automethod:: SubCommand.error()
        :decorator:

Slash Subcommand Group
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: SubCommandGroup

.. autoclass:: SubCommandGroup
    :members:
    :exclude-members: sub_command, after_invoke, before_invoke, error

    .. automethod:: SubCommandGroup.sub_command(*args, **kwargs)
        :decorator:

    .. automethod:: SubCommandGroup.after_invoke()
        :decorator:

    .. automethod:: SubCommandGroup.before_invoke()
        :decorator:

    .. automethod:: SubCommandGroup.error()
        :decorator:

User Command
~~~~~~~~~~~~

.. attributetable:: InvokableUserCommand

.. autoclass:: InvokableUserCommand
    :members:
    :special-members: __call__
    :exclude-members: after_invoke, before_invoke, error

    .. automethod:: InvokableUserCommand.after_invoke()
        :decorator:

    .. automethod:: InvokableUserCommand.before_invoke()
        :decorator:

    .. automethod:: InvokableUserCommand.error()
        :decorator:

Message Command
~~~~~~~~~~~~~~~

.. attributetable:: InvokableMessageCommand

.. autoclass:: InvokableMessageCommand
    :members:
    :special-members: __call__
    :exclude-members: after_invoke, before_invoke, error

    .. automethod:: InvokableMessageCommand.after_invoke()
        :decorator:

    .. automethod:: InvokableMessageCommand.before_invoke()
        :decorator:

    .. automethod:: InvokableMessageCommand.error()
        :decorator:

CommandSyncFlags
~~~~~~~~~~~~~~~~~

.. attributetable:: CommandSyncFlags

.. autoclass:: CommandSyncFlags()
    :members:

AppCmdIndex
~~~~~~~~~~~

.. attributetable:: AppCmdIndex

.. autoclass:: AppCmdIndex

Injection
~~~~~~~~~

.. attributetable:: Injection

.. autoclass:: Injection
    :members:
    :special-members: __call__
    :exclude-members: autocomplete

    .. automethod:: Injection.autocomplete
        :decorator:

ParamInfo
~~~~~~~~~

.. attributetable:: ParamInfo

.. autoclass:: ParamInfo

LargeInt
~~~~~~~~

.. autoclass:: LargeInt

    This is a class which inherits from :class:`int` to allow large numbers in slash commands, meant to be used only for annotations.

Range
~~~~~

.. autoclass:: Range

String
~~~~~~

.. autoclass:: String

Functions
---------

.. autofunction:: Param

.. autofunction:: slash_command
    :decorator:

.. autofunction:: message_command
    :decorator:

.. autofunction:: user_command
    :decorator:

.. autofunction:: inject

.. autofunction:: register_injection
    :decorator:

.. autofunction:: injection
    :decorator:

.. autofunction:: option_enum

Events
------

- :func:`on_slash_command_error(inter, error) <.on_slash_command_error>`
- :func:`on_slash_command(inter) <.on_slash_command>`
- :func:`on_slash_command_completion(inter) <.on_slash_command_completion>`
- :func:`on_user_command_error(inter, error) <.on_user_command_error>`
- :func:`on_user_command(inter) <.on_user_command>`
- :func:`on_user_command_completion(inter) <.on_user_command_completion>`
- :func:`on_message_command_error(inter, error) <.on_message_command_error>`
- :func:`on_message_command(inter) <.on_message_command>`
- :func:`on_message_command_completion(inter) <.on_message_command_completion>`
