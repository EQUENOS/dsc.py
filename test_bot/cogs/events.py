# SPDX-License-Identifier: MIT

from disnake.ext import commands


class EventListeners(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_guild_scheduled_event_create(self, event) -> None:
        print("Scheduled event create", repr(event), sep="\n", end="\n\n")

    @commands.Cog.listener()
    async def on_guild_scheduled_event_update(self, before, after) -> None:
        print("Scheduled event update", repr(before), repr(after), sep="\n", end="\n\n")

    @commands.Cog.listener()
    async def on_guild_scheduled_event_delete(self, event) -> None:
        print("Scheduled event delete", repr(event), sep="\n", end="\n\n")

    @commands.Cog.listener()
    async def on_guild_scheduled_event_subscribe(self, event, user) -> None:
        print("Scheduled event subscribe", event, user, sep="\n", end="\n\n")

    @commands.Cog.listener()
    async def on_guild_scheduled_event_unsubscribe(self, event, user) -> None:
        print("Scheduled event unsubscribe", event, user, sep="\n", end="\n\n")


async def setup(bot) -> None:
    await bot.add_cog(EventListeners(bot))
