import asyncio
import typing

import discord
import numpy as np
from discord.ext import commands
from utils import GlobalCMDS

gcmds = GlobalCMDS()


async def win(ctx, betAmount, bot):
    op = (f"UPDATE balance SET amount = amount + {betAmount} WHERE user_id = {ctx.author.id}")
    bot.loop.create_task(gcmds.balance_db(op))
    async with bot.db.acquire() as con:
        result = await con.fetch(f"SELECT * FROM coinflip WHERE user_id={ctx.author.id}")
        if not result:
            await con.execute(f"INSERT INTO coinflip(user_id, win) VALUES ({ctx.author.id}, 1)")
        else:
            await con.execute(f"UPDATE coinflip SET win = win + 1 WHERE user_id = {ctx.author.id}")
    return


async def lose(ctx, betAmount, bot):
    op = (f"UPDATE balance SET amount = amount - {betAmount} WHERE user_id = {ctx.author.id}")
    bot.loop.create_task(gcmds.balance_db(op))
    async with bot.db.acquire() as con:
        result = await con.fetch(f"SELECT * FROM coinflip WHERE user_id={ctx.author.id}")
        if not result:
            await con.execute(f"INSERT INTO coinflip(user_id, lose) VALUES ({ctx.author.id}, 1)")
        else:
            await con.execute(f"UPDATE coinflip SET lose = lose + 1 WHERE user_id = {ctx.author.id}")
    return


class Coinflip(commands.Cog):
    def __init__(self, bot):
        global gcmds
        self.bot = bot
        gcmds = GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_cf())

    async def init_cf(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute(
                "CREATE TABLE IF NOT EXISTS coinflip(user_id bigint PRIMARY KEY, win NUMERIC DEFAULT 0, "
                "lose NUMERIC DEFAULT 0)"
            )

    @commands.command(aliases=['cf'],
                      desc="Gamble by flipping a coin",
                      usage="coinflip (bet)",
                      note="If `(bet)` is not specified, it defaults to 1. "
                      "You may only bet up to your balance amount")
    async def coinflip(self, ctx, betAmount: typing.Optional[int] = 1, side="heads"):
        balance = await gcmds.get_balance(ctx.author)
        if not balance:
            await gcmds.balance_db(f"INSERT INTO balance(user_id, amount) VALUES ({ctx.author.id}, 1000)")
            balance = 1000
            initEmbed = discord.Embed(title="Initialised Credit Balance",
                                      description=f"{ctx.author.mention}, you have been credited `1000` credits "
                                      f"to start!\n\nCheck your current"
                                      f" balance using `{await gcmds.prefix(ctx)}balance`",
                                      color=discord.Color.blue())
            initEmbed.set_thumbnail(url="https://cdn.discordapp.com/attachments/734962101432615006"
                                        "/738390147514499163/chips.png")
            await ctx.channel.send(embed=initEmbed)

        if balance < betAmount:
            insuf = discord.Embed(title="Insufficient Credit Balance",
                                  description=f"{ctx.author.mention}, you have `{balance}` credits"
                                              f"\nYour bet of `{betAmount}` credits exceeds your current balance",
                                  color=discord.Color.dark_red())
            await ctx.channel.send(embed=insuf)
            return

        emoji = "<a:Coin_spin:742197823537414254>"
        staticemoji = "<:Coin_spin:742208039310065683>"

        sides = ["heads", "tails"]

        if side == "heads":
            weight = [0.45, 0.55]
        else:
            weight = [0.55, 0.45]

        picked_side = np.random.choice(a=sides, size=1, replace=True, p=weight)[0]

        title = f"{picked_side.capitalize()}!"
        description = staticemoji + f" `[{picked_side}]`"
        color = discord.Color.blue()

        if betAmount != 1:
            spell = "credits"
        else:
            spell = "credit"

        footer = f"{ctx.author.display_name} bet {betAmount} {spell} and selected {side}"

        if picked_side == side:
            author = f"{ctx.author.display_name}, you win {betAmount} {spell}"
            await win(ctx, betAmount, self.bot)
        else:
            author = f"{ctx.author.display_name}, you lose {betAmount} {spell}"
            await lose(ctx, betAmount, self.bot)

        loadingEmbed = discord.Embed(title="Coinflip",
                                     description=emoji,
                                     color=color)
        loadingEmbed.set_author(name=f"{ctx.author.display_name} flipped a coin", icon_url=ctx.author.avatar_url)
        loadingEmbed.set_footer(text=footer)
        message = await ctx.channel.send(embed=loadingEmbed)
        await asyncio.sleep(3.0)

        coinEmbed = discord.Embed(title=title,
                                  description=description,
                                  color=color)
        coinEmbed.set_author(name=author, icon_url=ctx.author.avatar_url)
        coinEmbed.set_footer(text=footer)

        try:
            await message.edit(embed=coinEmbed)
        except discord.NotFound:
            notFound = discord.Embed(title="Game Canceled",
                                     description="The original coinflip message was deleted",
                                     color=discord.Color.dark_red())
            return await ctx.channel.send(embed=notFound)


def setup(bot):
    bot.add_cog(Coinflip(bot))
