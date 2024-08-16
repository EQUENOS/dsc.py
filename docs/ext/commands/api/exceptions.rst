.. SPDX-License-Identifier: MIT

.. currentmodule:: disnake.ext.commands

.. _ext_commands_api_exceptions:

Exceptions and Warnings
=======================

This section documents exceptions and warnings specific to commands extension.

Exceptions
----------

.. autoexception:: CommandError
    :members:

.. autoexception:: ConversionError
    :members:

.. autoexception:: MissingRequiredArgument
    :members:

.. autoexception:: ArgumentParsingError
    :members:

.. autoexception:: UnexpectedQuoteError
    :members:

.. autoexception:: InvalidEndOfQuotedStringError
    :members:

.. autoexception:: ExpectedClosingQuoteError
    :members:

.. autoexception:: BadArgument
    :members:

.. autoexception:: BadUnionArgument
    :members:

.. autoexception:: BadLiteralArgument
    :members:

.. autoexception:: PrivateMessageOnly
    :members:

.. autoexception:: NoPrivateMessage
    :members:

.. autoexception:: CheckFailure
    :members:

.. autoexception:: CheckAnyFailure
    :members:

.. autoexception:: CommandNotFound
    :members:

.. autoexception:: DisabledCommand
    :members:

.. autoexception:: CommandInvokeError
    :members:

.. autoexception:: TooManyArguments
    :members:

.. autoexception:: UserInputError
    :members:

.. autoexception:: CommandOnCooldown
    :members:

.. autoexception:: MaxConcurrencyReached
    :members:

.. autoexception:: NotOwner
    :members:

.. autoexception:: ObjectNotFound
    :members:

.. autoexception:: MessageNotFound
    :members:

.. autoexception:: MemberNotFound
    :members:

.. autoexception:: GuildNotFound
    :members:

.. autoexception:: UserNotFound
    :members:

.. autoexception:: ChannelNotFound
    :members:

.. autoexception:: ChannelNotReadable
    :members:

.. autoexception:: ThreadNotFound
    :members:

.. autoexception:: BadColourArgument
    :members:

.. autoexception:: RoleNotFound
    :members:

.. autoexception:: BadInviteArgument
    :members:

.. autoexception:: EmojiNotFound
    :members:

.. autoexception:: PartialEmojiConversionFailure
    :members:

.. autoexception:: GuildStickerNotFound
    :members:

.. autoexception:: GuildScheduledEventNotFound
    :members:

.. autoexception:: BadBoolArgument
    :members:

.. autoexception:: LargeIntConversionFailure
    :members:

.. autoexception:: MissingPermissions
    :members:

.. autoexception:: BotMissingPermissions
    :members:

.. autoexception:: MissingRole
    :members:

.. autoexception:: BotMissingRole
    :members:

.. autoexception:: MissingAnyRole
    :members:

.. autoexception:: BotMissingAnyRole
    :members:

.. autoexception:: NSFWChannelRequired
    :members:

.. autoexception:: FlagError
    :members:

.. autoexception:: BadFlagArgument
    :members:

.. autoexception:: MissingFlagArgument
    :members:

.. autoexception:: TooManyFlags
    :members:

.. autoexception:: MissingRequiredFlag
    :members:

.. autoexception:: ExtensionError
    :members:

.. autoexception:: ExtensionAlreadyLoaded
    :members:

.. autoexception:: ExtensionNotLoaded
    :members:

.. autoexception:: NoEntryPointError
    :members:

.. autoexception:: ExtensionFailed
    :members:

.. autoexception:: ExtensionNotFound
    :members:

.. autoexception:: CommandRegistrationError
    :members:

.. autoexception:: ApplicationCommandRegistrationError
    :members:


Exception Hierarchy
~~~~~~~~~~~~~~~~~~~

.. exception_hierarchy::

    - :exc:`disnake.DiscordException`
        - :exc:`CommandError`
            - :exc:`ConversionError`
            - :exc:`UserInputError`
                - :exc:`MissingRequiredArgument`
                - :exc:`TooManyArguments`
                - :exc:`BadArgument`
                    - :exc:`ObjectNotFound`
                    - :exc:`MemberNotFound`
                    - :exc:`GuildNotFound`
                    - :exc:`UserNotFound`
                    - :exc:`MessageNotFound`
                    - :exc:`ChannelNotReadable`
                    - :exc:`ChannelNotFound`
                    - :exc:`ThreadNotFound`
                    - :exc:`BadColourArgument`
                    - :exc:`RoleNotFound`
                    - :exc:`BadInviteArgument`
                    - :exc:`EmojiNotFound`
                    - :exc:`PartialEmojiConversionFailure`
                    - :exc:`GuildStickerNotFound`
                    - :exc:`GuildScheduledEventNotFound`
                    - :exc:`BadBoolArgument`
                    - :exc:`LargeIntConversionFailure`
                    - :exc:`FlagError`
                        - :exc:`BadFlagArgument`
                        - :exc:`MissingFlagArgument`
                        - :exc:`TooManyFlags`
                        - :exc:`MissingRequiredFlag`
                - :exc:`BadUnionArgument`
                - :exc:`BadLiteralArgument`
                - :exc:`ArgumentParsingError`
                    - :exc:`UnexpectedQuoteError`
                    - :exc:`InvalidEndOfQuotedStringError`
                    - :exc:`ExpectedClosingQuoteError`
            - :exc:`CommandNotFound`
            - :exc:`CheckFailure`
                - :exc:`CheckAnyFailure`
                - :exc:`PrivateMessageOnly`
                - :exc:`NoPrivateMessage`
                - :exc:`NotOwner`
                - :exc:`MissingPermissions`
                - :exc:`BotMissingPermissions`
                - :exc:`MissingRole`
                - :exc:`BotMissingRole`
                - :exc:`MissingAnyRole`
                - :exc:`BotMissingAnyRole`
                - :exc:`NSFWChannelRequired`
            - :exc:`DisabledCommand`
            - :exc:`CommandInvokeError`
            - :exc:`CommandOnCooldown`
            - :exc:`MaxConcurrencyReached`
        - :exc:`ExtensionError`
            - :exc:`ExtensionAlreadyLoaded`
            - :exc:`ExtensionNotLoaded`
            - :exc:`NoEntryPointError`
            - :exc:`ExtensionFailed`
            - :exc:`ExtensionNotFound`
    - :exc:`~.ClientException`
        - :exc:`CommandRegistrationError`
            - :exc:`ApplicationCommandRegistrationError`

Warnings
--------

.. autoclass:: MessageContentPrefixWarning

Warning Hierarchy
~~~~~~~~~~~~~~~~~

.. exception_hierarchy::

    - :class:`disnake.DiscordWarning`
        - :class:`MessageContentPrefixWarning`
