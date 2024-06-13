# SPDX-License-Identifier: MIT

import random
from pprint import pformat

import disnake
from disnake import Localized
from disnake.enums import Locale
from disnake.ext import commands


class Localizations(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot

    @commands.slash_command()
    async def localized_command(
        self,
        inter: disnake.AppCmdInter[commands.Bot],
        auto: str,
        choice: str = commands.Param(
            choices=[
                # lookup keys for choices
                Localized("a", key="CHOICE_A"),
                Localized("o", key="CHOICE_O"),
                Localized("u", key="CHOICE_U"),
            ]
        ),
        other: str = commands.Param(
            # by lookup key
            name=Localized(key="OTHER_NAME"),
            # specify localizations directly
            description=Localized(data={Locale.en_GB: "insert bri'ish description here"}),
        ),
    ) -> None:
        """{{ MY_LOC_CMD }} Does absolutely nothing

        Parameters
        ----------
        auto: Autocompletes with numbers from 1-5
        choice: Shows umlauts for german users {{CHOICE_PARAM}}
        other: Another value
        """
        await inter.response.send_message(f"```py\n{pformat(locals())}\n```")

    @localized_command.autocomplete("auto")
    async def autocomp(
        self, inter: disnake.AppCmdInter[commands.Bot], value: str
    ) -> "disnake.app_commands.Choices":
        # not really autocomplete, only used for showing autocomplete localization
        x = list(map(str, range(1, 6)))
        random.shuffle(x)
        return [Localized(v, key=f"AUTOCOMP_{v}") for v in x]

    @commands.slash_command()
    async def localized_top_level(self, inter: disnake.AppCmdInter[commands.Bot]) -> None:
        pass

    @localized_top_level.sub_command_group()
    async def second(self, inter: disnake.AppCmdInter[commands.Bot]) -> None:
        pass

    @second.sub_command(
        name=Localized(data={Locale.en_GB: "british_subcommand"}),
        description=Localized(key="MY_SUBCMD_DESC"),
    )
    async def third(
        self,
        inter: disnake.AppCmdInter[commands.Bot],
        value: str = commands.Param(name=Localized("a_string", key="A_VERY_COOL_PARAM_NAME")),
    ) -> None:
        await inter.response.send_message(f"```py\n{pformat(locals())}\n```")

    # works for message/user commands as well
    @commands.message_command(
        name=Localized("Localized Reverse", key="MSG_REVERSE"),
    )
    async def cmd_msg(self, inter: disnake.AppCmdInter[commands.Bot], msg: disnake.Message) -> None:
        await inter.response.send_message(msg.content[::-1])


async def setup(bot) -> None:
    await bot.add_cog(Localizations(bot))
