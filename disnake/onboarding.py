# SPDX-License-Identifier: MIT
from __future__ import annotations

from typing import TYPE_CHECKING, FrozenSet, List, Optional, Union

from .enums import OnboardingPromptType, try_enum
from .mixins import Hashable

if TYPE_CHECKING:
    from .emoji import Emoji, PartialEmoji
    from .guild import Guild, GuildChannel
    from .role import Role
    from .types.onboarding import (
        Onboarding as OnboardingPayload,
        OnboardingPrompt as OnboardingPromptPayload,
        OnboardingPromptOption as OnboardingPromptOptionPayload,
    )

__all__ = (
    "Onboarding",
    "OnboardingPrompt",
    "OnboardingPromptOption",
)


class Onboarding:
    """Represents a guild onboarding object.

    .. versionadded:: 2.9

    Attributes
    ----------
    guild: :class:`Guild`
        The guild this onboarding is part of.
    prompts: List[:class:`OnboardingPrompt`]
        The prompts shown during onboarding and in community customization.
    enabled: :class:`bool`
        Whether onboarding is enabled.
    default_channel_ids: FrozenSet[:class:`int`]
        The IDs of the channels that will be shown to new members by default.
    """

    __slots__ = (
        "guild",
        "prompts",
        "enabled",
        "default_channel_ids",
    )

    def __init__(self, *, guild: Guild, data: OnboardingPayload) -> None:
        self.guild: Guild = guild
        self._from_data(data)

    def _from_data(self, data: OnboardingPayload) -> None:
        self.prompts: List[OnboardingPrompt] = [
            OnboardingPrompt(data=prompt, guild=self.guild) for prompt in data["prompts"]
        ]
        self.enabled: bool = data["enabled"]
        self.default_channel_ids: FrozenSet[int] = (
            frozenset(map(int, exempt_channels))
            if (exempt_channels := data["default_channel_ids"])
            else frozenset()
        )

    def __repr__(self) -> str:
        return (
            f"<Onboarding guild={self.guild!r} prompts={self.prompts!r} enabled={self.enabled!r}>"
        )

    @property
    def default_channels(self) -> List[GuildChannel]:
        """List[:class:`abc.GuildChannel`]: The list of channels that will be shown to new members by default."""
        return list(filter(None, map(self.guild.get_channel, self.default_channel_ids)))


class OnboardingPrompt(Hashable):
    """Represents an onboarding prompt.

    .. versionadded:: 2.9

    Attributes
    ----------
    id: :class:`int`
        The onboarding prompt's ID.
    type: :class:`OnboardingPromptType`
        The onboarding prompt's type.
    options: List[:class:`OnboardingPromptOption`]
        The onboarding prompt's options.
    title: :class:`str`
        The onboarding prompt's title.
    single_select: :class:`bool`
        Whether users are limited to selecting one option for the prompt.
    required: :class:`bool`
        Whether the prompt is required before a user completes the onboarding flow.
    in_onboarding: :class:`bool`
        Whether the prompt is present in the initial onboarding flow.
        If ``False``, the prompt will only appear in community customization.
    """

    __slots__ = (
        "guild",
        "id",
        "title",
        "options",
        "single_select",
        "required",
        "in_onboarding",
        "type",
    )

    def __init__(self, *, guild: Guild, data: OnboardingPromptPayload) -> None:
        self.guild = guild

        self.id: int = int(data["id"])
        self.title: str = data["title"]
        self.options: List[OnboardingPromptOption] = [
            OnboardingPromptOption(data=option, guild=guild) for option in data["options"]
        ]
        self.single_select: bool = data["single_select"]
        self.required: bool = data["required"]
        self.in_onboarding: bool = data["in_onboarding"]
        self.type: OnboardingPromptType = try_enum(OnboardingPromptType, data["type"])

    def __str__(self) -> str:
        return self.title

    def __repr__(self) -> str:
        return (
            f"<OnboardingPrompt id={self.id!r} title={self.title!r} options={self.options!r}"
            f" single_select={self.single_select!r} required={self.required!r}"
            f" in_onboarding={self.in_onboarding!r} type={self.type!r}>"
        )


class OnboardingPromptOption(Hashable):
    """Represents an onboarding prompt option.

    .. versionadded:: 2.9

    Attributes
    ----------
    id: :class:`int`
        The prompt option's ID.
    emoji: Optional[Union[:class:`PartialEmoji`, :class:`Emoji`, :class:`str`]]
        The prompt option's emoji.
    title: :class:`str`
        The prompt option's title.
    description: Optional[:class:`str`]
        The prompt option's description.
    role_ids: FrozenSet[:class:`int`]
        The IDs of the roles that will be added to the user when they select this option.
    channel_ids: FrozenSet[:class:`int`]
        The IDs of the channels that the user will see when they select this option.
    """

    __slots__ = ("id", "title", "description", "emoji", "guild", "role_ids", "channel_ids")

    def __init__(self, *, guild: Guild, data: OnboardingPromptOptionPayload) -> None:
        self.guild: Guild = guild

        self.id: int = int(data["id"])
        self.title: str = data["title"]
        self.description: Optional[str] = data["description"]
        self.role_ids: FrozenSet[int] = (
            frozenset(map(int, roles_ids)) if (roles_ids := data.get("role_ids")) else frozenset()
        )
        self.channel_ids: FrozenSet[int] = (
            frozenset(map(int, channels_ids))
            if (channels_ids := data.get("channel_ids"))
            else frozenset()
        )

        self.emoji: Optional[Union[Emoji, PartialEmoji, str]]
        if emoji_data := data.get("emoji"):
            self.emoji = guild._state.get_reaction_emoji(emoji_data)
        else:
            self.emoji = None

    def __str__(self) -> str:
        return self.title

    def __repr__(self) -> str:
        return (
            f"<OnboardingPromptOption id={self.id!r} title={self.title!r} "
            f"description={self.description!r} emoji={self.emoji!r}>"
        )

    @property
    def roles(self) -> List[Role]:
        """List[:class:`Role`]: A list of roles that will be added to the user when they select this option."""
        return list(filter(None, map(self.guild.get_role, self.role_ids)))

    @property
    def channels(self) -> List[GuildChannel]:
        """List[:class:`abc.GuildChannel`]: A list of channels that the user will see when they select this option."""
        return list(filter(None, map(self.guild.get_channel, self.channel_ids)))
