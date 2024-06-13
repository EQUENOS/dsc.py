# SPDX-License-Identifier: MIT

import disnake
from disnake.ext import commands


class MessageCommands(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot

    @commands.message_command(name="Reverse")
    async def reverse(self, inter: disnake.MessageCommandInteraction[commands.Bot]) -> None:
        await inter.response.send_message(inter.target.content[::-1])


async def setup(bot) -> None:
    await bot.add_cog(MessageCommands(bot))
