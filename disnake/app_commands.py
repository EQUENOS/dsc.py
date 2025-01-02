# SPDX-License-Identifier: MIT

from __future__ import annotations

import math
import re
from abc import ABC
from typing import TYPE_CHECKING, ClassVar, List, Mapping, Optional, Sequence, Tuple, Union

from .enums import (
    ApplicationCommandPermissionType,
    ApplicationCommandType,
    ChannelType,
    Locale,
    OptionType,
    enum_if_int,
    try_enum,
    try_enum_to_int,
)
from .flags import ApplicationInstallTypes, InteractionContextTypes
from .i18n import Localized
from .permissions import Permissions
from .utils import MISSING, _get_as_snowflake, _maybe_cast, deprecated, warn_deprecated

if TYPE_CHECKING:
    from typing_extensions import Self

    from .i18n import LocalizationProtocol, LocalizationValue, LocalizedOptional, LocalizedRequired
    from .state import ConnectionState
    from .types.interactions import (
        ApplicationCommand as ApplicationCommandPayload,
        ApplicationCommandOption as ApplicationCommandOptionPayload,
        ApplicationCommandOptionChoice as ApplicationCommandOptionChoicePayload,
        ApplicationCommandOptionChoiceValue,
        ApplicationCommandPermissions as ApplicationCommandPermissionsPayload,
        EditApplicationCommand as EditApplicationCommandPayload,
        GuildApplicationCommandPermissions as GuildApplicationCommandPermissionsPayload,
    )

    Choices = Union[
        Sequence["OptionChoice"],
        Sequence[ApplicationCommandOptionChoiceValue],
        Mapping[str, ApplicationCommandOptionChoiceValue],
        Sequence[Localized[str]],
    ]

    APIApplicationCommand = Union["APIUserCommand", "APIMessageCommand", "APISlashCommand"]


__all__ = (
    "application_command_factory",
    "ApplicationCommand",
    "SlashCommand",
    "APISlashCommand",
    "UserCommand",
    "APIUserCommand",
    "MessageCommand",
    "APIMessageCommand",
    "OptionChoice",
    "Option",
    "ApplicationCommandPermissions",
    "GuildApplicationCommandPermissions",
)


def application_command_factory(data: ApplicationCommandPayload) -> APIApplicationCommand:
    cmd_type = try_enum(ApplicationCommandType, data.get("type", 1))
    if cmd_type is ApplicationCommandType.chat_input:
        return APISlashCommand.from_dict(data)
    if cmd_type is ApplicationCommandType.user:
        return APIUserCommand.from_dict(data)
    if cmd_type is ApplicationCommandType.message:
        return APIMessageCommand.from_dict(data)

    raise TypeError(f"Application command of type {cmd_type} is not valid")


def _validate_name(name: str) -> None:
    # used for slash command names and option names
    # see https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-naming

    if not isinstance(name, str):
        raise TypeError(
            f"Slash command name and option names must be an instance of class 'str', received '{name.__class__}'"
        )

    if name != name.lower() or not re.fullmatch(r"[\w-]{1,32}", name):
        raise ValueError(
            f"Slash command or option name '{name}' should be lowercase, "
            "between 1 and 32 characters long, and only consist of "
            "these symbols: a-z, 0-9, -, _, and other languages'/scripts' symbols"
        )


class OptionChoice:
    """Represents an option choice.

    Parameters
    ----------
    name: Union[:class:`str`, :class:`.Localized`]
        The name of the option choice (visible to users).

        .. versionchanged:: 2.5
            Added support for localizations.

    value: Union[:class:`str`, :class:`int`]
        The value of the option choice.
    """

    def __init__(
        self,
        name: LocalizedRequired,
        value: ApplicationCommandOptionChoiceValue,
    ) -> None:
        name_loc = Localized._cast(name, True)
        self.name: str = name_loc.string
        self.name_localizations: LocalizationValue = name_loc.localizations
        self.value: ApplicationCommandOptionChoiceValue = value

    def __repr__(self) -> str:
        return f"<OptionChoice name={self.name!r} value={self.value!r}>"

    def __eq__(self, other) -> bool:
        return (
            self.name == other.name
            and self.value == other.value
            and self.name_localizations == other.name_localizations
        )

    def to_dict(self, *, locale: Optional[Locale] = None) -> ApplicationCommandOptionChoicePayload:
        localizations = self.name_localizations.data

        name: Optional[str] = None
        # if `locale` provided, get localized name from dict
        if locale is not None and localizations:
            name = localizations.get(str(locale))

        # fall back to default name if no locale or no localized name
        if name is None:
            name = self.name

        payload: ApplicationCommandOptionChoicePayload = {
            "name": name,
            "value": self.value,
        }
        # if no `locale` provided, include all localizations in payload
        if locale is None and localizations:
            payload["name_localizations"] = localizations
        return payload

    @classmethod
    def from_dict(cls, data: ApplicationCommandOptionChoicePayload):
        return OptionChoice(
            name=Localized(data["name"], data=data.get("name_localizations")),
            value=data["value"],
        )

    def localize(self, store: LocalizationProtocol) -> None:
        self.name_localizations._link(store)


class Option:
    """Represents a slash command option.

    Parameters
    ----------
    name: Union[:class:`str`, :class:`.Localized`]
        The option's name.

        .. versionchanged:: 2.5
            Added support for localizations.

    description: Optional[Union[:class:`str`, :class:`.Localized`]]
        The option's description.

        .. versionchanged:: 2.5
            Added support for localizations.

    type: :class:`OptionType`
        The option type, e.g. :class:`OptionType.user`.
    required: :class:`bool`
        Whether this option is required.
    choices: Union[Sequence[:class:`OptionChoice`], Sequence[Union[:class:`str`, :class:`int`, :class:`float`]], Mapping[:class:`str`, Union[:class:`str`, :class:`int`, :class:`float`]]]
        The pre-defined choices for this option.
    options: List[:class:`Option`]
        The list of sub options. Normally you don't have to specify it directly,
        instead consider using ``@main_cmd.sub_command`` or ``@main_cmd.sub_command_group`` decorators.
    channel_types: List[:class:`ChannelType`]
        The list of channel types that your option supports, if the type is :class:`OptionType.channel`.
        By default, it supports all channel types.
    autocomplete: :class:`bool`
        Whether this option can be autocompleted.
    min_value: Union[:class:`int`, :class:`float`]
        The minimum value permitted.
    max_value: Union[:class:`int`, :class:`float`]
        The maximum value permitted.
    min_length: :class:`int`
        The minimum length for this option if this is a string option.

        .. versionadded:: 2.6

    max_length: :class:`int`
        The maximum length for this option if this is a string option.

        .. versionadded:: 2.6

    Attributes
    ----------
    name: :class:`str`
        The option's name.
    description: :class:`str`
        The option's description.
    type: :class:`OptionType`
        The option type, e.g. :class:`OptionType.user`.
    required: :class:`bool`
        Whether this option is required.
    choices: List[:class:`OptionChoice`]
        The list of pre-defined choices.
    options: List[:class:`Option`]
        The list of sub options. Normally you don't have to specify it directly,
        instead consider using ``@main_cmd.sub_command`` or ``@main_cmd.sub_command_group`` decorators.
    channel_types: List[:class:`ChannelType`]
        The list of channel types that your option supports, if the type is :class:`OptionType.channel`.
        By default, it supports all channel types.
    autocomplete: :class:`bool`
        Whether this option can be autocompleted.
    min_value: Union[:class:`int`, :class:`float`]
        The minimum value permitted.
    max_value: Union[:class:`int`, :class:`float`]
        The maximum value permitted.
    min_length: :class:`int`
        The minimum length for this option if this is a string option.

        .. versionadded:: 2.6

    max_length: :class:`int`
        The maximum length for this option if this is a string option.

        .. versionadded:: 2.6
    """

    __slots__ = (
        "name",
        "description",
        "type",
        "required",
        "choices",
        "options",
        "channel_types",
        "autocomplete",
        "min_value",
        "max_value",
        "name_localizations",
        "description_localizations",
        "min_length",
        "max_length",
    )

    def __init__(
        self,
        name: LocalizedRequired,
        description: LocalizedOptional = None,
        type: Optional[Union[OptionType, int]] = None,
        required: bool = False,
        choices: Optional[Choices] = None,
        options: Optional[list] = None,
        channel_types: Optional[List[ChannelType]] = None,
        autocomplete: bool = False,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
    ) -> None:
        name_loc = Localized._cast(name, True)
        _validate_name(name_loc.string)
        self.name: str = name_loc.string
        self.name_localizations: LocalizationValue = name_loc.localizations

        desc_loc = Localized._cast(description, False)
        self.description: str = desc_loc.string or "-"
        self.description_localizations: LocalizationValue = desc_loc.localizations

        self.type: OptionType = enum_if_int(OptionType, type) or OptionType.string
        self.required: bool = required
        self.options: List[Option] = options or []

        if min_value is not None and self.type is OptionType.integer:
            min_value = math.ceil(min_value)
        if max_value is not None and self.type is OptionType.integer:
            max_value = math.floor(max_value)

        self.min_value: Optional[float] = min_value
        self.max_value: Optional[float] = max_value

        self.min_length: Optional[int] = min_length
        self.max_length: Optional[int] = max_length

        if channel_types is not None and not all(isinstance(t, ChannelType) for t in channel_types):
            raise TypeError("channel_types must be a list of `ChannelType`s")

        self.channel_types: List[ChannelType] = channel_types or []

        self.choices: List[OptionChoice] = []
        if choices is not None:
            if autocomplete:
                raise TypeError("can not specify both choices and autocomplete args")

            if isinstance(choices, str):  # str matches `Sequence[str]`, but isn't meant to be used
                raise TypeError("choices argument should be a list/sequence or dict, not str")

            if isinstance(choices, Mapping):
                self.choices = [OptionChoice(name, value) for name, value in choices.items()]
            else:
                for c in choices:
                    if isinstance(c, Localized):
                        c = OptionChoice(c, c.string)
                    elif not isinstance(c, OptionChoice):
                        c = OptionChoice(str(c), c)
                    self.choices.append(c)

        self.autocomplete: bool = autocomplete

    def __repr__(self) -> str:
        return (
            f"<Option name={self.name!r} description={self.description!r}"
            f" type={self.type!r} required={self.required!r} choices={self.choices!r}"
            f" options={self.options!r} min_value={self.min_value!r} max_value={self.max_value!r}"
            f" min_length={self.min_length!r} max_length={self.max_length!r}>"
        )

    def __eq__(self, other) -> bool:
        return (
            self.name == other.name
            and self.description == other.description
            and self.type == other.type
            and self.required == other.required
            and self.choices == other.choices
            and self.options == other.options
            and set(self.channel_types) == set(other.channel_types)
            and self.autocomplete == other.autocomplete
            and self.min_value == other.min_value
            and self.max_value == other.max_value
            and self.min_length == other.min_length
            and self.max_length == other.max_length
            and self.name_localizations == other.name_localizations
            and self.description_localizations == other.description_localizations
        )

    @classmethod
    def from_dict(cls, data: ApplicationCommandOptionPayload) -> Option:
        return Option(
            name=Localized(data["name"], data=data.get("name_localizations")),
            description=Localized(
                data.get("description"), data=data.get("description_localizations")
            ),
            type=data.get("type"),
            required=data.get("required", False),
            choices=_maybe_cast(
                data.get("choices", MISSING), lambda x: list(map(OptionChoice.from_dict, x))
            ),
            options=_maybe_cast(
                data.get("options", MISSING), lambda x: list(map(Option.from_dict, x))
            ),
            channel_types=_maybe_cast(
                data.get("channel_types", MISSING), lambda x: [try_enum(ChannelType, t) for t in x]
            ),
            autocomplete=data.get("autocomplete", False),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            min_length=data.get("min_length"),
            max_length=data.get("max_length"),
        )

    def add_choice(
        self,
        name: LocalizedRequired,
        value: ApplicationCommandOptionChoiceValue,
    ) -> None:
        """Adds an OptionChoice to the list of current choices,
        parameters are the same as for :class:`OptionChoice`.
        """
        self.choices.append(
            OptionChoice(
                name=name,
                value=value,
            )
        )

    def add_option(
        self,
        name: LocalizedRequired,
        description: LocalizedOptional = None,
        type: Optional[OptionType] = None,
        required: bool = False,
        choices: Optional[Choices] = None,
        options: Optional[list] = None,
        channel_types: Optional[List[ChannelType]] = None,
        autocomplete: bool = False,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
    ) -> None:
        """Adds an option to the current list of options,
        parameters are the same as for :class:`Option`.
        """
        type = type or OptionType.string
        self.options.append(
            Option(
                name=name,
                description=description,
                type=type,
                required=required,
                choices=choices,
                options=options,
                channel_types=channel_types,
                autocomplete=autocomplete,
                min_value=min_value,
                max_value=max_value,
                min_length=min_length,
                max_length=max_length,
            )
        )

    def to_dict(self) -> ApplicationCommandOptionPayload:
        payload: ApplicationCommandOptionPayload = {
            "name": self.name,
            "description": self.description,
            "type": try_enum_to_int(self.type),
        }
        if self.required:
            payload["required"] = True
        if self.autocomplete:
            payload["autocomplete"] = True
        if self.choices:
            payload["choices"] = [c.to_dict() for c in self.choices]
        if self.options:
            payload["options"] = [o.to_dict() for o in self.options]
        if self.channel_types:
            payload["channel_types"] = [v.value for v in self.channel_types]
        if self.min_value is not None:
            payload["min_value"] = self.min_value
        if self.max_value is not None:
            payload["max_value"] = self.max_value
        if self.min_length is not None:
            payload["min_length"] = self.min_length
        if self.max_length is not None:
            payload["max_length"] = self.max_length
        if (loc := self.name_localizations.data) is not None:
            payload["name_localizations"] = loc
        if (loc := self.description_localizations.data) is not None:
            payload["description_localizations"] = loc
        return payload

    def localize(self, store: LocalizationProtocol) -> None:
        self.name_localizations._link(store)
        self.description_localizations._link(store)

        if (name_loc := self.name_localizations.data) is not None:
            for value in name_loc.values():
                _validate_name(value)

        for c in self.choices:
            c.localize(store)
        for o in self.options:
            o.localize(store)


class ApplicationCommand(ABC):  # noqa: B024  # this will get refactored eventually
    """The base class for application commands.

    The following classes implement this ABC:

    - :class:`~.SlashCommand`
    - :class:`~.MessageCommand`
    - :class:`~.UserCommand`

    Attributes
    ----------
    type: :class:`ApplicationCommandType`
        The command type
    name: :class:`str`
        The command name
    name_localizations: :class:`.LocalizationValue`
        Localizations for ``name``.

        .. versionadded:: 2.5

    nsfw: :class:`bool`
        Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
        Defaults to ``False``.

        .. versionadded:: 2.8

    install_types: Optional[:class:`ApplicationInstallTypes`]
        The installation types where the command is available.
        Defaults to :attr:`ApplicationInstallTypes.guild` only.
        Only available for global commands.

        .. versionadded:: 2.10

    contexts: Optional[:class:`InteractionContextTypes`]
        The interaction contexts where the command can be used.
        Only available for global commands.

        .. versionadded:: 2.10
    """

    __repr_info__: ClassVar[Tuple[str, ...]] = (
        "type",
        "name",
        "default_member_permissions",
        "nsfw",
        "install_types",
        "contexts",
    )

    def __init__(
        self,
        type: ApplicationCommandType,
        name: LocalizedRequired,
        dm_permission: Optional[bool] = None,  # deprecated
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
        install_types: Optional[ApplicationInstallTypes] = None,
        contexts: Optional[InteractionContextTypes] = None,
    ) -> None:
        self.type: ApplicationCommandType = enum_if_int(ApplicationCommandType, type)

        name_loc = Localized._cast(name, True)
        self.name: str = name_loc.string
        self.name_localizations: LocalizationValue = name_loc.localizations
        self.nsfw: bool = False if nsfw is None else nsfw

        self._default_member_permissions: Optional[int]
        if default_member_permissions is None:
            # allow everyone to use the command if its not supplied
            self._default_member_permissions = None
        elif isinstance(default_member_permissions, bool):
            raise TypeError("`default_member_permissions` cannot be a bool")
        elif isinstance(default_member_permissions, int):
            self._default_member_permissions = default_member_permissions
        else:
            self._default_member_permissions = default_member_permissions.value

        # note: this defaults to `[0]` for syncing purposes only
        self.install_types: Optional[ApplicationInstallTypes] = install_types
        self.contexts: Optional[InteractionContextTypes] = contexts

        # TODO(3.0): refactor
        # These are for ext.commands defaults. It's quite ugly to do it this way,
        # but since __eq__ and to_dict functionality is encapsulated here and can't be moved trivially,
        # it'll do until the presumably soon-ish refactor of the entire commands framework.
        self._default_install_types: Optional[ApplicationInstallTypes] = None
        self._default_contexts: Optional[InteractionContextTypes] = None

        self._always_synced: bool = False

        # reset `default_permission` if set before
        self._default_permission: bool = True

        self._dm_permission: Optional[bool] = dm_permission
        if self._dm_permission is not None:
            warn_deprecated(
                "dm_permission is deprecated, use contexts instead.",
                stacklevel=2,
                # the call stack can have different depths, depending on how the
                # user created the command, so we can't reliably set a fixed stacklevel
                skip_internal_frames=True,
            )

            # if both are provided, raise an exception
            # (n.b. these can be assigned to later, in which case no exception will be raised.
            # assume the user knows what they're doing, in that case)
            if self.contexts is not None:
                raise ValueError("Cannot use both `dm_permission` and `contexts` at the same time")

    @property
    def default_member_permissions(self) -> Optional[Permissions]:
        """Optional[:class:`Permissions`]: The default required member permissions for this command.
        A member must have *all* these permissions to be able to invoke the command in a guild.

        This is a default value, the set of users/roles that may invoke this command can be
        overridden by moderators on a guild-specific basis, disregarding this setting.

        If ``None`` is returned, it means everyone can use the command by default.
        If an empty :class:`Permissions` object is returned (that is, all permissions set to ``False``),
        this means no one can use the command.

        .. versionadded:: 2.5
        """
        if self._default_member_permissions is None:
            return None
        return Permissions(self._default_member_permissions)

    @property
    @deprecated("contexts")
    def dm_permission(self) -> bool:
        """
        Whether this command can be used in DMs with the bot.

        .. versionadded:: 2.5

        .. deprecated:: 2.10
            Use :attr:`contexts` instead.
            This is equivalent to the :attr:`InteractionContextTypes.bot_dm` flag.
        """
        # a `None` value is equivalent to `True` here
        return self._dm_permission is not False

    @dm_permission.setter
    @deprecated("contexts")
    def dm_permission(self, value: bool) -> None:
        self._dm_permission = value

    def __repr__(self) -> str:
        attrs = " ".join(f"{key}={getattr(self, key)!r}" for key in self.__repr_info__)
        return f"<{type(self).__name__} {attrs}>"

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other) -> bool:
        if not isinstance(other, ApplicationCommand):
            return False

        if not (
            self.type == other.type
            and self.name == other.name
            and self.name_localizations == other.name_localizations
            and self.nsfw == other.nsfw
            and self._default_member_permissions == other._default_member_permissions
            and self._default_permission == other._default_permission
        ):
            return False

        # ignore global-only fields if comparing guild commands
        if not any(
            (isinstance(obj, _APIApplicationCommandMixin) and obj.guild_id) for obj in (self, other)
        ):
            if self._install_types_with_default != other._install_types_with_default:
                return False

            # `contexts` takes priority over `dm_permission`;
            # ignore `dm_permission` if `contexts` is set,
            # since the API returns both even when only `contexts` was provided
            self_contexts = self._contexts_with_default
            other_contexts = other._contexts_with_default
            if self_contexts is not None or other_contexts is not None:
                if self_contexts != other_contexts:
                    return False
            else:
                # this is a bit awkward; `None` is equivalent to `True` in this case
                if (self._dm_permission is not False) != (other._dm_permission is not False):
                    return False

        return True

    @property
    def _install_types_with_default(self) -> Optional[ApplicationInstallTypes]:
        # if this is an api-provided command object, keep things as-is
        if self.install_types is None and not isinstance(self, _APIApplicationCommandMixin):
            if self._default_install_types is not None:
                return self._default_install_types

            # The purpose of this default is to avoid re-syncing after the updating to the new version,
            # at least as long as the user hasn't enabled user installs in the dev portal
            # (i.e. if they haven't, the api defaults to this value as well).
            # Additionally, this provides consistency independent of the dev portal configuration,
            # even if it might not be ideal.
            # In an ideal world, we would make use of `application_info().install_types_config`.
            return ApplicationInstallTypes(guild=True)

        return self.install_types

    @property
    def _contexts_with_default(self) -> Optional[InteractionContextTypes]:
        # (basically the same logic as `_install_types_with_default`, but without a fallback)
        if (
            self.contexts is None
            and not isinstance(self, _APIApplicationCommandMixin)
            and self._default_contexts is not None
            # only use default if legacy `dm_permission` wasn't set
            and self._dm_permission is None
        ):
            return self._default_contexts

        return self.contexts

    def to_dict(self) -> EditApplicationCommandPayload:
        data: EditApplicationCommandPayload = {
            "type": try_enum_to_int(self.type),
            "name": self.name,
            "default_member_permissions": (
                str(self._default_member_permissions)
                if self._default_member_permissions is not None
                else None
            ),
            "default_permission": True,
            "nsfw": self.nsfw,
        }

        install_types = (
            self._install_types_with_default.values
            if self._install_types_with_default is not None
            else None
        )
        data["integration_types"] = install_types

        contexts = (
            self._contexts_with_default.values if self._contexts_with_default is not None else None
        )
        data["contexts"] = contexts

        # don't set `dm_permission` if `contexts` is set
        if contexts is None:
            data["dm_permission"] = self._dm_permission is not False

        if (loc := self.name_localizations.data) is not None:
            data["name_localizations"] = loc

        return data

    def localize(self, store: LocalizationProtocol) -> None:
        self.name_localizations._link(store)


class _APIApplicationCommandMixin:
    __repr_info__ = ("id",)

    def _update_common(self, data: ApplicationCommandPayload) -> None:
        if not isinstance(self, ApplicationCommand):
            raise TypeError("_APIApplicationCommandMixin must be used with ApplicationCommand")

        self.id: int = int(data["id"])
        self.application_id: int = int(data["application_id"])
        self.guild_id: Optional[int] = _get_as_snowflake(data, "guild_id")
        self.version: int = int(data["version"])

        # deprecated, but kept until API stops returning this field
        self._default_permission = data.get("default_permission") is not False

        # same deal, also deprecated.
        self._dm_permission = data.get("dm_permission")


class UserCommand(ApplicationCommand):
    """A user context menu command.

    Attributes
    ----------
    name: :class:`str`
        The user command's name.
    name_localizations: :class:`.LocalizationValue`
        Localizations for ``name``.

        .. versionadded:: 2.5

    nsfw: :class:`bool`
        Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
        Defaults to ``False``.

        .. versionadded:: 2.8

    install_types: Optional[:class:`ApplicationInstallTypes`]
        The installation types where the command is available.
        Defaults to :attr:`ApplicationInstallTypes.guild` only.
        Only available for global commands.

        .. versionadded:: 2.10

    contexts: Optional[:class:`InteractionContextTypes`]
        The interaction contexts where the command can be used.
        Only available for global commands.

        .. versionadded:: 2.10
    """

    __repr_info__ = tuple(n for n in ApplicationCommand.__repr_info__ if n != "type")

    def __init__(
        self,
        name: LocalizedRequired,
        dm_permission: Optional[bool] = None,  # deprecated
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
        install_types: Optional[ApplicationInstallTypes] = None,
        contexts: Optional[InteractionContextTypes] = None,
    ) -> None:
        super().__init__(
            type=ApplicationCommandType.user,
            name=name,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            nsfw=nsfw,
            install_types=install_types,
            contexts=contexts,
        )


class APIUserCommand(UserCommand, _APIApplicationCommandMixin):
    """A user context menu command returned by the API.

    .. versionadded:: 2.4

    Attributes
    ----------
    name: :class:`str`
        The user command's name.
    name_localizations: :class:`.LocalizationValue`
        Localizations for ``name``.

        .. versionadded:: 2.5

    nsfw: :class:`bool`
        Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.

        .. versionadded:: 2.8

    install_types: Optional[:class:`ApplicationInstallTypes`]
        The installation types where the command is available.
        Defaults to :attr:`ApplicationInstallTypes.guild` only.
        Only available for global commands.

        .. versionadded:: 2.10

    contexts: Optional[:class:`InteractionContextTypes`]
        The interaction contexts where the command can be used.
        Only available for global commands.

        .. versionadded:: 2.10

    id: :class:`int`
        The user command's ID.
    application_id: :class:`int`
        The application ID this command belongs to.
    guild_id: Optional[:class:`int`]
        The ID of the guild this user command is enabled in, or ``None`` if it's global.
    version: :class:`int`
        Autoincrementing version identifier updated during substantial record changes.
    """

    __repr_info__ = UserCommand.__repr_info__ + _APIApplicationCommandMixin.__repr_info__

    @classmethod
    def from_dict(cls, data: ApplicationCommandPayload) -> Self:
        cmd_type = data.get("type", 0)
        if cmd_type != ApplicationCommandType.user.value:
            raise ValueError(f"Invalid payload type for UserCommand: {cmd_type}")

        self = cls(
            name=Localized(data["name"], data=data.get("name_localizations")),
            default_member_permissions=_get_as_snowflake(data, "default_member_permissions"),
            nsfw=data.get("nsfw"),
            install_types=(
                ApplicationInstallTypes._from_values(install_types)
                if (install_types := data.get("integration_types")) is not None
                else None
            ),
            contexts=(
                InteractionContextTypes._from_values(contexts)
                if (contexts := data.get("contexts")) is not None
                else None
            ),
        )
        self._update_common(data)
        return self


class MessageCommand(ApplicationCommand):
    """A message context menu command

    Attributes
    ----------
    name: :class:`str`
        The message command's name.
    name_localizations: :class:`.LocalizationValue`
        Localizations for ``name``.

        .. versionadded:: 2.5

    nsfw: :class:`bool`
        Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
        Defaults to ``False``.

        .. versionadded:: 2.8

    install_types: Optional[:class:`ApplicationInstallTypes`]
        The installation types where the command is available.
        Defaults to :attr:`ApplicationInstallTypes.guild` only.
        Only available for global commands.

        .. versionadded:: 2.10

    contexts: Optional[:class:`InteractionContextTypes`]
        The interaction contexts where the command can be used.
        Only available for global commands.

        .. versionadded:: 2.10
    """

    __repr_info__ = tuple(n for n in ApplicationCommand.__repr_info__ if n != "type")

    def __init__(
        self,
        name: LocalizedRequired,
        dm_permission: Optional[bool] = None,  # deprecated
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
        install_types: Optional[ApplicationInstallTypes] = None,
        contexts: Optional[InteractionContextTypes] = None,
    ) -> None:
        super().__init__(
            type=ApplicationCommandType.message,
            name=name,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            nsfw=nsfw,
            install_types=install_types,
            contexts=contexts,
        )


class APIMessageCommand(MessageCommand, _APIApplicationCommandMixin):
    """A message context menu command returned by the API.

    .. versionadded:: 2.4

    Attributes
    ----------
    name: :class:`str`
        The message command's name.
    name_localizations: :class:`.LocalizationValue`
        Localizations for ``name``.

        .. versionadded:: 2.5

    nsfw: :class:`bool`
        Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.

        .. versionadded:: 2.8

    install_types: Optional[:class:`ApplicationInstallTypes`]
        The installation types where the command is available.
        Defaults to :attr:`ApplicationInstallTypes.guild` only.
        Only available for global commands.

        .. versionadded:: 2.10

    contexts: Optional[:class:`InteractionContextTypes`]
        The interaction contexts where the command can be used.
        Only available for global commands.

        .. versionadded:: 2.10

    id: :class:`int`
        The message command's ID.
    application_id: :class:`int`
        The application ID this command belongs to.
    guild_id: Optional[:class:`int`]
        The ID of the guild this message command is enabled in, or ``None`` if it's global.
    version: :class:`int`
        Autoincrementing version identifier updated during substantial record changes.
    """

    __repr_info__ = MessageCommand.__repr_info__ + _APIApplicationCommandMixin.__repr_info__

    @classmethod
    def from_dict(cls, data: ApplicationCommandPayload) -> Self:
        cmd_type = data.get("type", 0)
        if cmd_type != ApplicationCommandType.message.value:
            raise ValueError(f"Invalid payload type for MessageCommand: {cmd_type}")

        self = cls(
            name=Localized(data["name"], data=data.get("name_localizations")),
            default_member_permissions=_get_as_snowflake(data, "default_member_permissions"),
            nsfw=data.get("nsfw"),
            install_types=(
                ApplicationInstallTypes._from_values(install_types)
                if (install_types := data.get("integration_types")) is not None
                else None
            ),
            contexts=(
                InteractionContextTypes._from_values(contexts)
                if (contexts := data.get("contexts")) is not None
                else None
            ),
        )
        self._update_common(data)
        return self


class SlashCommand(ApplicationCommand):
    """The base class for building slash commands.

    Attributes
    ----------
    name: :class:`str`
        The slash command's name.
    name_localizations: :class:`.LocalizationValue`
        Localizations for ``name``.

        .. versionadded:: 2.5

    description: :class:`str`
        The slash command's description.
    description_localizations: :class:`.LocalizationValue`
        Localizations for ``description``.

        .. versionadded:: 2.5

    nsfw: :class:`bool`
        Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.
        Defaults to ``False``.

        .. versionadded:: 2.8

    install_types: Optional[:class:`ApplicationInstallTypes`]
        The installation types where the command is available.
        Defaults to :attr:`ApplicationInstallTypes.guild` only.
        Only available for global commands.

        .. versionadded:: 2.10

    contexts: Optional[:class:`InteractionContextTypes`]
        The interaction contexts where the command can be used.
        Only available for global commands.

        .. versionadded:: 2.10

    options: List[:class:`Option`]
        The list of options the slash command has.
    """

    __repr_info__ = tuple(n for n in ApplicationCommand.__repr_info__ if n != "type") + (
        "description",
        "options",
    )

    def __init__(
        self,
        name: LocalizedRequired,
        description: LocalizedRequired,
        options: Optional[List[Option]] = None,
        dm_permission: Optional[bool] = None,  # deprecated
        default_member_permissions: Optional[Union[Permissions, int]] = None,
        nsfw: Optional[bool] = None,
        install_types: Optional[ApplicationInstallTypes] = None,
        contexts: Optional[InteractionContextTypes] = None,
    ) -> None:
        super().__init__(
            type=ApplicationCommandType.chat_input,
            name=name,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            nsfw=nsfw,
            install_types=install_types,
            contexts=contexts,
        )
        _validate_name(self.name)

        desc_loc = Localized._cast(description, True)
        self.description: str = desc_loc.string
        self.description_localizations: LocalizationValue = desc_loc.localizations

        self.options: List[Option] = options or []

    def __eq__(self, other) -> bool:
        return (
            super().__eq__(other)
            and self.description == other.description
            and self.options == other.options
            and self.description_localizations == other.description_localizations
        )

    def add_option(
        self,
        name: LocalizedRequired,
        description: LocalizedOptional = None,
        type: Optional[OptionType] = None,
        required: bool = False,
        choices: Optional[Choices] = None,
        options: Optional[list] = None,
        channel_types: Optional[List[ChannelType]] = None,
        autocomplete: bool = False,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
    ) -> None:
        """Adds an option to the current list of options,
        parameters are the same as for :class:`Option`
        """
        self.options.append(
            Option(
                name=name,
                description=description,
                type=type or OptionType.string,
                required=required,
                choices=choices,
                options=options,
                channel_types=channel_types,
                autocomplete=autocomplete,
                min_value=min_value,
                max_value=max_value,
                min_length=min_length,
                max_length=max_length,
            )
        )

    def to_dict(self) -> EditApplicationCommandPayload:
        res = super().to_dict()
        res["description"] = self.description
        res["options"] = [o.to_dict() for o in self.options]
        if (loc := self.description_localizations.data) is not None:
            res["description_localizations"] = loc
        return res

    def localize(self, store: LocalizationProtocol) -> None:
        super().localize(store)
        if (name_loc := self.name_localizations.data) is not None:
            for value in name_loc.values():
                _validate_name(value)

        self.description_localizations._link(store)

        for o in self.options:
            o.localize(store)


class APISlashCommand(SlashCommand, _APIApplicationCommandMixin):
    """A slash command returned by the API.

    .. versionadded:: 2.4

    Attributes
    ----------
    name: :class:`str`
        The slash command's name.
    name_localizations: :class:`.LocalizationValue`
        Localizations for ``name``.

        .. versionadded:: 2.5

    description: :class:`str`
        The slash command's description.
    description_localizations: :class:`.LocalizationValue`
        Localizations for ``description``.

        .. versionadded:: 2.5

    nsfw: :class:`bool`
        Whether this command is :ddocs:`age-restricted <interactions/application-commands#agerestricted-commands>`.

        .. versionadded:: 2.8

    install_types: Optional[:class:`ApplicationInstallTypes`]
        The installation types where the command is available.
        Defaults to :attr:`ApplicationInstallTypes.guild` only.
        Only available for global commands.

        .. versionadded:: 2.10

    contexts: Optional[:class:`InteractionContextTypes`]
        The interaction contexts where the command can be used.
        Only available for global commands.

        .. versionadded:: 2.10

    id: :class:`int`
        The slash command's ID.
    options: List[:class:`Option`]
        The list of options the slash command has.
    application_id: :class:`int`
        The application ID this command belongs to.
    guild_id: Optional[:class:`int`]
        The ID of the guild this slash command is enabled in, or ``None`` if it's global.
    version: :class:`int`
        Autoincrementing version identifier updated during substantial record changes.
    """

    __repr_info__ = SlashCommand.__repr_info__ + _APIApplicationCommandMixin.__repr_info__

    @classmethod
    def from_dict(cls, data: ApplicationCommandPayload) -> Self:
        cmd_type = data.get("type", 0)
        if cmd_type != ApplicationCommandType.chat_input.value:
            raise ValueError(f"Invalid payload type for SlashCommand: {cmd_type}")

        self = cls(
            name=Localized(data["name"], data=data.get("name_localizations")),
            description=Localized(data["description"], data=data.get("description_localizations")),
            options=_maybe_cast(
                data.get("options", MISSING), lambda x: list(map(Option.from_dict, x))
            ),
            default_member_permissions=_get_as_snowflake(data, "default_member_permissions"),
            nsfw=data.get("nsfw"),
            install_types=(
                ApplicationInstallTypes._from_values(install_types)
                if (install_types := data.get("integration_types")) is not None
                else None
            ),
            contexts=(
                InteractionContextTypes._from_values(contexts)
                if (contexts := data.get("contexts")) is not None
                else None
            ),
        )
        self._update_common(data)
        return self


class ApplicationCommandPermissions:
    """Represents application command permissions for a role, user, or channel.

    Attributes
    ----------
    id: :class:`int`
        The ID of the role, user, or channel.
    type: :class:`ApplicationCommandPermissionType`
        The type of the target.
    permission: :class:`bool`
        Whether to allow or deny the access to the application command.
    """

    __slots__ = ("id", "type", "permission", "_guild_id")

    def __init__(self, *, data: ApplicationCommandPermissionsPayload, guild_id: int) -> None:
        self.id: int = int(data["id"])
        self.type: ApplicationCommandPermissionType = try_enum(
            ApplicationCommandPermissionType, data["type"]
        )
        self.permission: bool = data["permission"]
        self._guild_id: int = guild_id

    def __repr__(self) -> str:
        return f"<ApplicationCommandPermissions id={self.id!r} type={self.type!r} permission={self.permission!r}>"

    def __eq__(self, other):
        return (
            self.id == other.id and self.type == other.type and self.permission == other.permission
        )

    def to_dict(self) -> ApplicationCommandPermissionsPayload:
        return {"id": self.id, "type": int(self.type), "permission": self.permission}  # type: ignore

    def is_everyone(self) -> bool:
        """Whether this permission object is affecting the @everyone role.

        .. versionadded:: 2.5

        :return type: :class:`bool`
        """
        return self.id == self._guild_id

    def is_all_channels(self) -> bool:
        """Whether this permission object is affecting all channels.

        .. versionadded:: 2.5

        :return type: :class:`bool`
        """
        return self.id == self._guild_id - 1


class GuildApplicationCommandPermissions:
    """Represents application command permissions in a guild.

    .. versionchanged:: 2.5
        Can now also represent application-wide permissions that apply to every command by default.

    Attributes
    ----------
    id: :class:`int`
        The application command's ID, or the application ID if these are application-wide permissions.
    application_id: :class:`int`
        The application ID this command belongs to.
    guild_id: :class:`int`
        The ID of the guild where these permissions are applied.
    permissions: List[:class:`ApplicationCommandPermissions`]
        A list of :class:`ApplicationCommandPermissions`.
    """

    __slots__ = ("_state", "id", "application_id", "guild_id", "permissions")

    def __init__(
        self, *, data: GuildApplicationCommandPermissionsPayload, state: ConnectionState
    ) -> None:
        self._state: ConnectionState = state
        self.id: int = int(data["id"])
        self.application_id: int = int(data["application_id"])
        self.guild_id: int = int(data["guild_id"])

        self.permissions: List[ApplicationCommandPermissions] = [
            ApplicationCommandPermissions(data=elem, guild_id=self.guild_id)
            for elem in data["permissions"]
        ]

    def __repr__(self) -> str:
        return (
            f"<GuildApplicationCommandPermissions id={self.id!r} application_id={self.application_id!r}"
            f" guild_id={self.guild_id!r} permissions={self.permissions!r}>"
        )

    def to_dict(self) -> GuildApplicationCommandPermissionsPayload:
        return {
            "id": self.id,
            "application_id": self.application_id,
            "guild_id": self.guild_id,
            "permissions": [perm.to_dict() for perm in self.permissions],
        }
