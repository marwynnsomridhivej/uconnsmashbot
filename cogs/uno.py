import asyncio
from typing import List, Optional

import discord
from discord.ext import commands
from discord.ext.commands import AutoShardedBot, Context
from setuppanel import SetupPanel
from utils.customerrors import InvalidBetAmount, SilentButDeadly
from utils.unoutils import UnoGame


class Uno(commands.Cog):
    def __init__(self, bot: AutoShardedBot) -> None:
        self.bot = bot
        self.bot.loop.create_task(self._init_table())

    async def _init_table(self) -> None:
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute(
                f"CREATE TABLE IF NOT EXISTS uno(user_id bigint PRIMARY KEY, played bigint DEFAULT 1, win bigint DEFAULT 0)"
            )

    async def _validate_bet(self, ctx: Context, bet: str, members: List[discord.Member]) -> int:
        try:
            bet = int(bet)
            if not bet >= 1:
                raise ValueError
        except (TypeError, ValueError):
            raise InvalidBetAmount(ctx.author, bet, "is not an integer greater than or equal to 1")
        for member in members:
            async with self.bot.db.acquire() as con:
                balance = await con.fetchval(
                    f"SELECT amount FROM balance WHERE user_id={member.id}"
                )
            if balance is None:
                balance = 1000
            if bet > balance:
                raise InvalidBetAmount(member, bet, "exceeds your current balance")
        return bet

    async def _validate_game(self, ctx: Context, members: List[discord.Member], bet: int, tourney: bool = False) -> List[discord.Member]:
        if not members or len(members) > 9:
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="No Members Specified",
                    description=f"{ctx.author.mention}, please specify up to 9 other people to start an Uno game",
                    color=discord.Color.dark_red(),
                )
            )
        if ctx.author in members:
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Invalid Members Specified",
                    description=f"{ctx.author.mention}, you may not specify yourself as one of the opponents",
                    color=discord.Color.dark_red(),
                )
            )
        members = list(set(members + [ctx.author]))
        if any(member.bot for member in members):
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Invalid Members Specified",
                    description=f"{ctx.author.mention}, please specify only human members",
                    color=discord.Color.dark_red(),
                )
            )
        if not tourney:
            await self._validate_bet(ctx, bet, members)
        return members

    async def _pregame_setup(self, ctx: Context, members: List[discord.Member], modes: List[str]) -> dict:
        data = {
            "card_mode": "normal",
            "stack": False,
            "skip": False,
            "defer": False,
            "forever": False,
            "jump": False,
            "default_stack": "n",
            "default_defer": "n",
            "strict_stack": True,
            "timeout": 60,
        }
        debug = False
        _modes = modes.split(" ")
        for mode in set(_modes):
            if mode == "debug" and ctx.author.id == self.bot.owner_id:
                debug = True
            elif mode in ["skip", "stack", "defer", "forever", "jump"]:
                data[mode] = True
            if mode == "stack":
                _data = await SetupPanel(
                    bot=self.bot,
                    ctx=ctx,
                    title="Uno Options",
                ).add_step(
                    name="message",
                    embed=discord.Embed(
                        title="Stacking Strictness",
                        description=f"{ctx.author.mention}, should this game's stacking be strict? Enter \"y\" or \"yes\" "
                        "to use strict stacking, otherwise stacking will be non-strict",
                        color=discord.Color.blue(),
                    ),
                    timeout=300,
                ).start()
                if not str(_data[0]).lower() in ["y", "yes"]:
                    data["strict_stack"] = False
        _modes = [
            key for key, _ in data.items() if key in [
                "debug", "stack", "skip", "defer", "forever", "jump"
            ] and data[key]
        ]
        if "stack" in _modes and data["strict_stack"]:
            _modes[_modes.index("stack")] = "strict stack"
        if len(_modes) == 0:
            _modes = ["normal"]
        await ctx.channel.send(
            embed=discord.Embed(
                title="Starting Uno Game",
                description=f"I am setting up an Uno game for {len(members)} players with {', '.join(_modes)} mode{'s' if len(_modes) != 1 else ''}",
                color=discord.Color.blue(),
            )
        )
        await asyncio.sleep(2.0)
        if debug:
            card_mode, default_stack, default_defer, timeout = await SetupPanel(
                bot=self.bot,
                ctx=ctx,
                title="Debug Options",
            ).add_step(
                name="message",
                embed=discord.Embed(
                    title="UnoCard Mode",
                    description=f"{ctx.author.mention}, what should the UnoCard mode be?",
                    color=discord.Color.blue(),
                ),
                timeout=300,
            ).add_step(
                name="message",
                embed=discord.Embed(
                    title="Default Stack Choice",
                    description=f"{ctx.author.mention}, should autoplay always choose to stack when able to?",
                    color=discord.Color.blue(),
                ),
                timeout=300,
            ).add_step(
                name="message",
                embed=discord.Embed(
                    title="Default Defer Choice",
                    description=f"{ctx.author.mention}, should autoplay always choose to defer when able to?",
                    color=discord.Color.blue(),
                ),
                timeout=300,
            ).add_step(
                name="integer",
                embed=discord.Embed(
                    title="Default Timeout Length",
                    description=f"{ctx.author.mention}, how long should users have to input a card before autoplay takes over?",
                    color=discord.Color.blue(),
                ),
                timeout=300,
            ).start()
            data["card_mode"] = card_mode
            data["default_stack"] = default_stack
            data["default_defer"] = default_defer
            data["timeout"] = timeout
        return data

    async def _show_tourney_progress(self, ctx: Context, members: List[discord.Member], progress: dict, max_games: int, threshold: int) -> discord.Message:
        results = "\n".join(
            f"<@{key}>: {value} game{'s' if value != 1 else ''} won" for key, value in progress.items()
        )
        return await ctx.channel.send(
            embed=discord.Embed(
                title=f"Tournament Progress",
                description=f"Here are the results so far of the set between {' and '.join(member.mention for member in members)}: \n{results}"
                "\n\nA new game will begin in 10 seconds",
                color=discord.Color.blue(),
            ).set_footer(
                text=f"Best of {max_games}, require {threshold} win{'s' if threshold != 1 else ''} to win the set",
            )
        )

    async def _send_tourney_winner(self, ctx: Context, members: List[discord.Member], winner: discord.Member, progress: dict) -> discord.Message:
        results = "\n".join(
            f"<@{key}>: {value} game{'s' if value != 1 else ''} won" for key, value in progress.items()
        )
        return await ctx.channel.send(
            embed=discord.Embed(
                title=f"{winner.display_name} Wins!",
                description=f"Here are the results of the set between {' and '.join(member.mention for member in members)}: \n{results}",
                color=discord.Color.blue(),
            )
        )

    @commands.command(desc="Uno in Discord!",
                      usage="uno (bet) [@member]*va (mode)*va",
                      note="If `(bet)` is unspecified, it defaults to 1. You must specify up to "
                      "9 other members. When it is your first turn, you can type \"cancel\" to cancel the game.\n\n"
                      "MarywnnBot offers the following modes:\n" + "\n".join([
                          "**normal** - official uno rules",
                          "**skip** - allows for skipping your turn if you can place a card. To skip, enter \"skip\" "
                          "when asked for the card index",
                          "**stack** - house rule allows stacking of cards. You will be asked if you would like strict "
                          "stacking, which only allows stacking of identical cards. Non-strict stacking allows stacking "
                          "of cards that share the same value, but may be of a different color",
                          "**defer** - defer the power card penalty if you are able to place it and transfer the combined "
                          "penalty to the next player",
                          "**forever** - you must draw until you are able to play a card",
                          "**jump** - any player, at any time, may place a card down if they have "
                          "that identical card in their hand",
                      ]) +
                      "\n\nTo specify multiple modes, separate each mode with a space. The default mode is \"normal\" only")
    async def uno(self, ctx: Context, bet: Optional[int] = 1, members: commands.Greedy[discord.Member] = None, *, modes: str = "normal"):
        members = await self._validate_game(ctx, members, bet)
        if isinstance(members, discord.Message):
            raise SilentButDeadly()
        data = await self._pregame_setup(ctx, members, modes)
        return await UnoGame(
            ctx,
            self.bot,
            bet,
            members,
            **data,
        ).play()

    @commands.command(aliases=["unot"],
                      desc="Automatic best of n tournament style game between two players",
                      usage="unotourney (best of) [@member] (mode)*va",
                      note="`(best of)` refers to the \"best of n\", or the maximum number of games to play. "
                      "If unspecified, it defaults to 3. You may only specify one other member. Tournament "
                      "uno does not cost any credits to play")
    async def unotourney(self, ctx: Context, max_games: Optional[int] = 3, member: discord.Member = None, *, modes: str = "normal"):
        if not max_games >= 1 or not max_games % 2:
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Invalid Best of Number",
                    description=f"{ctx.author.mention}, the best of number must be at least 1 and odd",
                    color=discord.Color.dark_red(),
                )
            )
        members = await self._validate_game(ctx, [member], 0, tourney=True)
        if isinstance(members, discord.Message):
            raise SilentButDeadly()
        data = await self._pregame_setup(ctx, members, modes)
        _progress = {
            ctx.author.id: 0,
            member.id: 0,
        }
        winner = None
        threshold = max_games // 2 + 1
        for _ in range(max_games):
            game = UnoGame(
                ctx,
                self.bot,
                0,
                members,
                **data,
            )
            await game.play()
            _winner = game.winner
            _progress[_winner.id] += 1
            for key, value in _progress.items():
                if value == threshold:
                    winner = [member for member in members if member.id == key]
                    break
            if winner:
                winner = winner[0]
                break
            await self._show_tourney_progress(ctx, members, _progress, max_games, threshold)
            await asyncio.sleep(10)
        return await self._send_tourney_winner(ctx, members, winner, _progress)


def setup(bot):
    bot.add_cog(Uno(bot))
