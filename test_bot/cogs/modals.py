# SPDX-License-Identifier: MIT

import disnake
from disnake.enums import TextInputStyle
from disnake.ext import commands


class MyModal(disnake.ui.Modal):
    def __init__(self) -> None:
        components = [
            disnake.ui.TextInput(
                label="Name",
                placeholder="The name of the tag",
                custom_id="name",
                style=TextInputStyle.short,
                max_length=50,
            ),
            disnake.ui.TextInput(
                label="Description",
                placeholder="The description of the tag",
                custom_id="description",
                style=TextInputStyle.paragraph,
            ),
        ]
        super().__init__(title="Create Tag", components=components)

    async def callback(self, inter: disnake.ModalInteraction[commands.Bot]) -> None:
        embed = disnake.Embed(title="Tag Creation")
        for key, value in inter.text_values.items():
            embed.add_field(name=key.capitalize(), value=value, inline=False)
        await inter.response.send_message(embed=embed)


class Modals(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.slash_command()
    async def create_tag(self, inter: disnake.AppCmdInter[commands.Bot]) -> None:
        """Sends a Modal to create a tag."""
        await inter.response.send_modal(modal=MyModal())

    @commands.slash_command()
    async def create_tag_low(self, inter: disnake.AppCmdInter[commands.Bot]) -> None:
        """Sends a Modal to create a tag but with a low-level implementation."""
        await inter.response.send_modal(
            title="Create Tag",
            custom_id="create_tag2",
            components=[
                disnake.ui.TextInput(
                    label="Name",
                    placeholder="The name of the tag",
                    custom_id="name",
                    style=TextInputStyle.short,
                    max_length=50,
                ),
                disnake.ui.TextInput(
                    label="Description",
                    placeholder="The description of the tag",
                    custom_id="description",
                    style=TextInputStyle.paragraph,
                ),
            ],
        )

        modal_inter: disnake.ModalInteraction = await self.bot.wait_for(
            "modal_submit",
            check=lambda i: i.custom_id == "create_tag2" and i.author.id == inter.author.id,
        )

        embed = disnake.Embed(title="Tag Creation")
        for key, value in modal_inter.text_values.items():
            embed.add_field(name=key.capitalize(), value=value, inline=False)
        await modal_inter.response.send_message(embed=embed)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Modals(bot))
