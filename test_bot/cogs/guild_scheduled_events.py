# SPDX-License-Identifier: MIT

from datetime import timedelta

import disnake
from disnake.enums import GuildScheduledEventEntityType, GuildScheduledEventPrivacyLevel
from disnake.ext import commands


class GuildScheduledEvents(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.slash_command()
    async def fetch_event(
        self, inter: disnake.GuildCommandInteraction[commands.Bot], id: commands.LargeInt
    ) -> None:
        gse = await inter.guild.fetch_scheduled_event(id)
        await inter.response.send_message(str(gse.image))

    @commands.slash_command()
    async def edit_event(
        self,
        inter: disnake.GuildCommandInteraction[commands.Bot],
        id: commands.LargeInt,
        new_image: bool,
    ) -> None:
        await inter.response.defer()
        gse = await inter.guild.fetch_scheduled_event(id)
        image = disnake.File("./assets/banner.png")
        if new_image:
            gse2 = await gse.edit(image=image.fp.read())
        else:
            gse2 = await gse.edit(image=None)
        await inter.edit_original_response(content=str(gse2.image))

    @commands.slash_command()
    async def create_event(
        self,
        inter: disnake.GuildCommandInteraction[commands.Bot],
        name: str,
        channel: disnake.VoiceChannel,
    ) -> None:
        image = disnake.File("./assets/banner.png")
        gse = await inter.guild.create_scheduled_event(
            name=name,
            privacy_level=GuildScheduledEventPrivacyLevel.guild_only,
            scheduled_start_time=disnake.utils.utcnow() + timedelta(days=1),
            entity_type=GuildScheduledEventEntityType.voice,
            channel=channel,
            image=image.fp.read(),
        )
        await inter.response.send_message(str(gse.image))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GuildScheduledEvents(bot))
