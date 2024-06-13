# SPDX-License-Identifier: MIT

import asyncio
import logging
import os
import sys
import traceback
from typing import Union

import disnake
from disnake.ext import commands

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from .config import Config

logger = logging.getLogger(__name__)

if not Config.test_guilds:
    logger.warning("No test guilds configured. Using global commands.")


def fancy_traceback(exc: Exception) -> str:
    """May not fit the message content limit"""
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"```py\n{text[-4086:]}\n```"


class TestBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=Config.prefix,
            intents=disnake.Intents.all(),
            help_command=None,
            command_sync_flags=commands.CommandSyncFlags.all(),
            strict_localization=Config.strict_localization,
            test_guilds=Config.test_guilds,
            reload=Config.auto_reload,
            enable_gateway_error_handler=Config.enable_gateway_error_handler,
        )

        self.i18n.load("test_bot/locale")

    async def on_ready(self) -> None:
        # fmt: off
        print(
            f"\n"
            f"The bot is ready.\n"
            f"User: {self.user}\n"
            f"ID: {self.user.id}\n"
        )
        # fmt: on

    async def setup_hook(self) -> None:
        await self.load_extensions(os.path.join(__package__, Config.cogs_folder))

    async def add_cog(self, cog: commands.Cog, *, override: bool = False) -> None:
        logger.info("Loading cog %s", cog.qualified_name)
        return await super().add_cog(cog, override=override)

    async def _handle_error(
        self, ctx: Union[commands.Context, disnake.AppCommandInter], error: Exception, prefix: str
    ) -> None:
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        msg = f"{prefix} failed due to `{error}`"
        logger.error(msg, exc_info=error)

        embed = disnake.Embed(
            title=msg,
            description=fancy_traceback(error),
            color=disnake.Color.red(),
        )
        await ctx.send(embed=embed)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        await self._handle_error(ctx, error, f"Prefix command `{ctx.command}`")

    async def on_slash_command_error(
        self, inter: disnake.AppCommandInter, error: commands.CommandError
    ) -> None:
        cmd = inter.application_command
        await self._handle_error(inter, error, f"Slash command `/{cmd.qualified_name}`")

    async def on_user_command_error(
        self, inter: disnake.AppCommandInter, error: commands.CommandError
    ) -> None:
        cmd = inter.application_command
        await self._handle_error(inter, error, f"User command `{cmd.name}`")

    async def on_message_command_error(
        self, inter: disnake.AppCommandInter, error: commands.CommandError
    ) -> None:
        cmd = inter.application_command
        await self._handle_error(inter, error, f"Message command `{cmd.name}`")


print(f"disnake: {disnake.__version__}\n")

if __name__ == "__main__":
    bot = TestBot()
    bot.run(Config.token)
