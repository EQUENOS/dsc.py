# SPDX-License-Identifier: MIT

"""A simple number guessing game, using `bot.wait_for`."""

import asyncio
import os
import random

import disnake
from disnake.ext import commands

intents = disnake.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents)


@bot.command()
async def guess(ctx: commands.Context):
    await ctx.send("Guess a number between 1 and 10.")

    def is_guess_message(m: disnake.Message):
        return m.author == ctx.message.author and m.content.isdigit()

    answer = random.randint(1, 10)

    try:
        guess = await ctx.bot.wait_for("message", check=is_guess_message, timeout=10)
    except asyncio.TimeoutError:
        await ctx.send(f"Sorry, you took too long. The answer was {answer}.")
        return

    if int(guess.content) == answer:
        await ctx.send("You guessed correctly!")
    else:
        await ctx.send(f"Oops. It is actually {answer}.")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})\n------")


if __name__ == "__main__":
    bot.run(os.getenv("BOT_TOKEN"))
