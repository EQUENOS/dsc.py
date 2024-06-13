# SPDX-License-Identifier: MIT
from typing import Any

import pytest

import disnake
from disnake import Event
from disnake.ext import commands


# n.b. the specific choice of events used in this file is irrelevant
@pytest.fixture
def client():
    return disnake.Client()


@pytest.fixture
def bot():
    return commands.Bot(
        command_prefix=commands.when_mentioned,
        command_sync_flags=commands.CommandSyncFlags.none(),
    )


@pytest.fixture(params=["client", "bot"])
def client_or_bot(request):
    return request.getfixturevalue(request.param)


# @Client.event


def test_event(client_or_bot: disnake.Client) -> None:
    assert not hasattr(client_or_bot, "on_message_edit")

    @client_or_bot.event
    async def on_message_edit(self, *args: Any) -> None:
        ...

    assert client_or_bot.on_message_edit is on_message_edit  # type: ignore


# Client.wait_for


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["thread_create", Event.thread_create])
async def test_wait_for(client_or_bot: disnake.Client, event) -> None:
    coro = client_or_bot.wait_for(event)
    assert len(client_or_bot._listeners["thread_create"]) == 1
    coro.close()  # close coroutine to avoid warning


# Client.add_listener / Client.remove_listener


@pytest.mark.parametrize("event", ["on_guild_remove", Event.guild_remove])
def test_addremove_listener(client_or_bot: disnake.Client, event) -> None:
    async def callback(self, *args: Any) -> None:
        ...

    client_or_bot.add_listener(callback, event)
    assert len(client_or_bot.extra_events["on_guild_remove"]) == 1
    client_or_bot.remove_listener(callback, event)
    assert len(client_or_bot.extra_events["on_guild_remove"]) == 0


def test_addremove_listener__implicit(client_or_bot: disnake.Client) -> None:
    async def on_guild_remove(self, *args: Any) -> None:
        ...

    client_or_bot.add_listener(on_guild_remove)
    assert len(client_or_bot.extra_events["on_guild_remove"]) == 1
    client_or_bot.remove_listener(on_guild_remove)
    assert len(client_or_bot.extra_events["on_guild_remove"]) == 0


# @Client.listen


@pytest.mark.parametrize("event", ["on_guild_role_create", Event.guild_role_create])
def test_listen(client_or_bot: disnake.Client, event) -> None:
    @client_or_bot.listen(event)
    async def callback(self, *args: Any) -> None:
        ...

    assert len(client_or_bot.extra_events["on_guild_role_create"]) == 1


def test_listen__implicit(client_or_bot: disnake.Client) -> None:
    @client_or_bot.listen()
    async def on_guild_role_create(self, *args: Any) -> None:
        ...

    assert len(client_or_bot.extra_events["on_guild_role_create"]) == 1


# @commands.Cog.listener
@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["on_automod_rule_update", Event.automod_rule_update])
async def test_listener(bot: commands.Bot, event) -> None:
    class Cog(commands.Cog):
        @commands.Cog.listener(event)
        async def callback(self, *args: Any) -> None:
            ...

    await bot.add_cog(Cog())
    assert len(bot.extra_events["on_automod_rule_update"]) == 1


@pytest.mark.asyncio
async def test_listener__implicit(bot: commands.Bot) -> None:
    class Cog(commands.Cog):
        @commands.Cog.listener()
        async def on_automod_rule_update(self, *args: Any) -> None:
            ...

    await bot.add_cog(Cog())
    assert len(bot.extra_events["on_automod_rule_update"]) == 1
