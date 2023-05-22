# SPDX-License-Identifier: MIT

"""A Tic Tac Toe game, implemented using views."""

import os
from enum import IntEnum
from typing import List, Optional

import disnake
from disnake.ext import commands


class Player(IntEnum):
    X = -1
    O = 1

    unknown = 0
    tie = 2

    def __str__(self) -> str:
        return self.name

    @property
    def other(self) -> "Player":
        # Returns `Player.O` if self is `Player.X`, and vice versa
        return self.O if self is self.X else self.X


# Defines a custom button that contains the logic of the game.
# The ["TicTacToe"] bit is for type hinting purposes to tell your IDE or linter
# what the type of `self.view` is. It is not required.
class TicTacToeButton(disnake.ui.Button["TicTacToe"]):
    def __init__(self, x: int, y: int):
        # A label is required, but we don't need one so a zero-width space is used
        # The row parameter tells the View which row to place the button under.
        # A View can only contain up to 5 rows -- each row can only have 5 buttons.
        # Since a Tic Tac Toe grid is 3x3 that means we have 3 rows and 3 columns.
        super().__init__(style=disnake.ButtonStyle.grey, label="\u200b", row=y)
        self.x = x
        self.y = y

    # This function is called whenever this particular button is pressed
    # This is part of the "meat" of the game logic
    async def callback(self, inter: disnake.MessageInteraction):
        view = self.view
        state = view.board[self.y][self.x]
        if state in (Player.X, Player.O):
            return

        # Update the current button, as well as the internal game state
        curr = view.current_player
        self.style = disnake.ButtonStyle.red if curr == Player.X else disnake.ButtonStyle.green
        self.label = curr.name
        self.disabled = True
        view.board[self.y][self.x] = curr
        view.current_player = curr.other
        content = f"It is now {view.current_player}'s turn"

        # Check if there's a winner
        winner = view.check_board_winner()
        if winner is not None:
            if winner in (Player.X, Player.O):
                content = f"{winner} won!"
            else:
                content = "It's a tie!"

            for child in view.children:
                child.disabled = True

            view.stop()

        await inter.response.edit_message(content=content, view=view)


# This is our actual board View
class TicTacToe(disnake.ui.View):
    # This tells the IDE or linter that all our children will be TicTacToeButtons
    # (this is not required)
    children: List[TicTacToeButton]

    def __init__(self):
        super().__init__()

        self.current_player: Player = Player.X

        u = Player.unknown
        self.board: List[List[Player]] = [
            [u, u, u],
            [u, u, u],
            [u, u, u],
        ]

        # Our board is made up of 3 by 3 TicTacToeButtons
        # The TicTacToeButton maintains the callbacks and helps steer the actual game.
        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    # This method checks for the board winner -- it is used by the TicTacToeButton
    def check_board_winner(self):
        def check_winner(value: int) -> Optional[Player]:
            if value == Player.O * 3:
                return Player.O
            if value == Player.X * 3:
                return Player.X
            return None

        for across in self.board:
            value = sum(across)
            if winner := check_winner(value):
                return winner

        # Check vertical
        for line in range(3):
            value = self.board[0][line] + self.board[1][line] + self.board[2][line]
            if winner := check_winner(value):
                return winner

        # Check diagonals
        diag = self.board[0][2] + self.board[1][1] + self.board[2][0]
        if winner := check_winner(diag):
            return winner

        diag = self.board[0][0] + self.board[1][1] + self.board[2][2]
        if winner := check_winner(diag):
            return winner

        # If we're here, we need to check if a tie was made
        if all(i != Player.unknown for row in self.board for i in row):
            return Player.tie

        return None


bot = commands.Bot(command_prefix=commands.when_mentioned)


@bot.command()
async def tic(ctx: commands.Context):
    """Starts a tic-tac-toe game with yourself."""
    await ctx.send("Tic Tac Toe: X goes first", view=TicTacToe())


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})\n------")


if __name__ == "__main__":
    bot.run(os.getenv("BOT_TOKEN"))
