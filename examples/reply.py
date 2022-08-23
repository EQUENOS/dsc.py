"""
An example showing how to reply to received messages.
"""

import os

import disnake


class MyClient(disnake.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

    async def on_message(self, message: disnake.Message):
        # we do not want the bot to reply to itself
        if message.author.id == self.user.id:
            return

        if message.content.startswith("!hello"):
            await message.reply("Hello!", mention_author=True)


intents = disnake.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(os.getenv("BOT_TOKEN"))
