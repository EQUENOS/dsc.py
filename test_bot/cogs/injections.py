# SPDX-License-Identifier: MIT

# pyright: reportUnknownLambdaType=false

from __future__ import annotations

from pprint import pformat
from typing import Optional, Tuple

import disnake
from disnake.ext import commands


def injected(user: disnake.User, channel: disnake.TextChannel):
    """An injection callback. This description should not be shown.

    Parameters
    ----------
    user: A User from `injected` - saves its id
    channel: A TextChannel from `injected` - saves its name
    """
    return (user.id, channel.name)


async def converter(interaction, number: float) -> float:
    return number**0.5


class PrefixConverter:
    def __init__(self, prefix: str, suffix: str = "") -> None:
        self.prefix = prefix
        self.suffix = suffix

    def __call__(self, inter: disnake.CommandInteraction[commands.Bot], a: str = "init"):
        return self.prefix + a + self.suffix


class HopeToGod:
    def __init__(self, username: str, discriminator: str) -> None:
        self.username = username
        self.discriminator = discriminator

    @commands.converter_method
    async def convert(cls, inter: disnake.CommandInteraction[commands.Bot], user: disnake.User):
        return cls(user.name, user.discriminator)

    def __repr__(self) -> str:
        return f"HopeToGod({self.username!r}, {self.discriminator!r})"


class PerhapsThis:
    def __init__(self, a: int, b: float) -> None:
        self.a = a
        self.b = b

    def __repr__(self) -> str:
        return f"PerhapsThis({self.a!r}, {self.b!r})"


@commands.register_injection
async def perhaps_this_is_it(
    disc_channel: disnake.TextChannel = commands.Param(lambda i: i.channel),
    large: int = commands.Param(0, large=True),
) -> PerhapsThis:
    """A registered injection callback. This description should not be shown.

    Parameters
    ----------
    disc_channel: A channel which should default to the current one - uses the id
    large: A large number which defaults to 0 - divided by 2
    """
    return PerhapsThis(disc_channel.id, large / 2)


class InjectionSlashCommands(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot
        self.exponent = 2

    async def injected_method(self, number: int = 3):
        """An instance injection callback. This description should not be shown.

        Parameters
        ----------
        number: A number which will be squared, 3^2 == 9 by default
        """
        return number**self.exponent

    @commands.slash_command()
    async def injection_command(
        self,
        inter: disnake.CommandInteraction[commands.Bot],
        sqrt: Optional[float] = commands.Param(None, converter=lambda i, x: x**0.5),
        prefixed: str = commands.Param(converter=PrefixConverter("__", "__")),
        other: Tuple[int, str] = commands.inject(injected),
        some: int = commands.inject(injected_method),
    ) -> None:
        """A command gotten from explicit converts and injections

        Parameters
        ----------
        sqrt: Does the square root of this number, None if not provided
        prefixed: Adds dunders to a string, created `__init__` by default
        other: This should not be shown
        some: This should not be shown
        """
        await inter.response.send_message(f"```py\n{pformat(locals())}\n```")

    @commands.slash_command()
    async def discerned_injections(
        self,
        inter: disnake.CommandInteraction[commands.Bot],
        perhaps: PerhapsThis,
        god: Optional[HopeToGod] = None,
    ) -> None:
        """A command gotten just with annotations

        Parameters
        ----------
        perhaps: This should not be shown
        god: Gets the name and discriminator of a user - None by default
        """
        await inter.response.send_message(f"```py\n{pformat(locals())}\n```")


async def setup(bot) -> None:
    await bot.add_cog(InjectionSlashCommands(bot))
