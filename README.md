[![Disnake Banner](./assets/banner.png)](https://disnake.dev/)

disnake
=======

<p align="center">
    <a href="https://discord.gg/gJDbCw8aQy"><img src="https://img.shields.io/discord/808030843078836254?style=flat-square&color=5865f2&logo=discord&logoColor=ffffff&label=discord" alt="Discord server invite" /></a>
    <a href="https://pypi.python.org/pypi/disnake"><img src="https://img.shields.io/pypi/v/disnake.svg?style=flat-square" alt="PyPI version info" /></a>
    <a href="https://pypi.python.org/pypi/disnake"><img src="https://img.shields.io/pypi/pyversions/disnake.svg?style=flat-square" alt="PyPI supported Python versions" /></a>
    <a href="https://github.com/DisnakeDev/disnake/commits"><img src="https://img.shields.io/github/commit-activity/w/DisnakeDev/disnake.svg?style=flat-square" alt="Commit activity" /></a>
</p>

A modern, easy to use, feature-rich, and async ready API wrapper for Discord written in Python. All contributors and developers associated with disnake, are trying their best to add new features to the library as soon as possible. 

Key Features
------------

- Proper rate limit handling.
- Type-safety measures.
- [FastAPI](https://fastapi.tiangolo.com/)-like slash command syntax.

<sup>The syntax and structure of `discord.py 2.0` is preserved.</sup>

Installing
----------

**Python 3.8 or higher is required.**

To install the library without full voice support, you can just run the
following command:

``` sh
# Linux/macOS
python3 -m pip install -U disnake

# Windows
py -3 -m pip install -U disnake
```

Installing `disnake` with full voice support requires you to replace `disnake` here, with `disnake[voice]`. To learn more about voice support (or installing the development version), please visit [this section of our guide](https://guide.disnake.dev/000-prerequisites/001-installing-python/#installing-disnake). 

(You can also optionally install [PyNaCl](https://pypi.org/project/PyNaCl/) for voice support.)

Note that on voice support on Linux requires installation of `libffi-dev` and `python-dev` packages, via your favourite package manager (e.g. `apt`, `dnf`, etc.) before running the following commands.

Quick Example
-------------

### Slash Commands Example

``` py
import disnake
from disnake.ext import commands

bot = commands.Bot(command_prefix='>', test_guilds=[12345])

@bot.slash_command()
async def ping(inter):
    await inter.response.send_message('Pong!')

bot.run('BOT_TOKEN')
```

### Context Menus Example

``` py
import disnake
from disnake.ext import commands

bot = commands.Bot(command_prefix='>', test_guilds=[12345])

@bot.user_command()
async def avatar(inter, user):
    embed = disnake.Embed(title=str(user))
    embed.set_image(url=user.display_avatar.url)
    await inter.response.send_message(embed=embed)

bot.run('BOT_TOKEN')
```

### Prefix Commands Example

``` py
import disnake
from disnake.ext import commands

bot = commands.Bot(command_prefix='>')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

bot.run('BOT_TOKEN')
```

You can find more examples in the [examples directory](./examples).

<br>
<p align="center">
    <a href="https://docs.disnake.dev/">Documentation</a>
    ⁕
    <a href="https://guide.disnake.dev/">Guide</a>
    ⁕
    <a href="https://discord.gg/gJDbCw8aQy">Discord Server</a>
    ⁕
    <a href="https://discord.gg/discord-api">Discord API</a>
</p>
<br>