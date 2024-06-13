# SPDX-License-Identifier: MIT

"""An example using subcommand groups and subcommands."""

import os

from disnake.ext import commands

bot = commands.Bot(command_prefix=commands.when_mentioned)


# Slash command subcommands differ from classic text subcommands & groups.
#
# The gist of it is:
#   - Any slash command which takes no arguments can be considered a parent.
#   - A parent has children, which are subcommands or subcommand groups
#   - Groups have subcommand children themselves
#
# Parent slash commands and groups cannot be invoked by users directly,
# but their callback will be invoked before any of their children are called.
#
# For a full explanation, see https://discord.com/developers/docs/interactions/application-commands#subcommands-and-subcommand-groups


# Define a new command with two children:
@bot.slash_command()
async def parent(inter):
    print("This code is ran every time any subcommand is invoked")


@parent.sub_command()
async def foo(inter, option: str):
    await inter.response.send_message(f"foo: {option}")


@parent.sub_command()
async def bar(inter, option: int):
    await inter.response.send_message(f"bar: {option}")


# Define a new command with sub command groups (this time in a cog).
# This results in two commands that can be called:
#   - /command foo a
#   - /command bar b
# Note that `/command`, `/command foo`, or `/command bar` cannot be
# called directly by users.
class MyCog(commands.Cog):
    @commands.slash_command()
    async def command(self, inter):
        print("This code is ran every time any subcommand is invoked")

    @command.sub_command_group()
    async def foo(self, inter):
        print("This code is ran every time any subcommand of `foo` is invoked")

    @foo.sub_command()
    async def a(self, inter, option: int):
        await inter.response.send_message(f"You ran `/command foo a` with {option}")

    @command.sub_command_group()
    async def bar(self, inter):
        print("This code is ran every time any subcommand of `bar` is invoked")

    @bar.sub_command()
    async def b(self, inter, option: float):
        await inter.response.send_message(f"You ran `/command bar b` with {option}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})\n------")


async def setup_hook():
    await bot.add_cog(MyCog())


bot.setup_hook = setup_hook

if __name__ == "__main__":
    bot.run(os.getenv("BOT_TOKEN"))
