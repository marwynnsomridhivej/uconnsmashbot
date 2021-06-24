import asyncio
import typing

import discord
from discord.ext import commands
from discord.ext.commands import AutoShardedBot, Context
from utils import GlobalCMDS

_CONF = ["✅", "❌"]
_GAMES = ["blackjack", "coinflip", "connectfour", "uno"]
_STATS = {
    "blackjack": [
        "win",
        "lose",
        "tie",
        "blackjack",
    ],
    "coinflip": [
        "win",
        "lose",
    ],
    "connectfour": [
        "win",
        "lose",
        "tie",
    ],
    "uno": [
        "win",
        "played",
    ]
}


class Games(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)

    @commands.command(aliases=['bal'],
                      desc="Check your balance and compare with other people",
                      usage="balance (member)*va")
    async def balance(self, ctx, member: commands.Greedy[discord.Member] = None):
        embed = discord.Embed().set_thumbnail(
            url="https://cdn.discordapp.com/attachments/734962101432615006/738390147514499163/chips.png",
        )
        if not member:
            balance = await self.gcmds.get_balance(ctx.author)
            if balance is None:
                await self.gcmds.balance_db(f"INSERT INTO balance(user_id, amount) VALUES ({ctx.author.id}, 1000)")
                balance = 1000

            if balance > 0:
                color = discord.Color.blue()
            else:
                color = discord.Color.dark_red()

            embed.title = "Your Current Balance"
            embed.description = f"{ctx.author.mention}, your current balance is: ```{balance} credit{'s' if balance != 1 else ''}```"
            embed.color = color
        else:
            description = ""
            color = 0
            for user in member:
                balance = await self.gcmds.get_balance(user)
                if balance is None:
                    await self.gcmds.balance_db(f"INSERT INTO balance(user_id, amount) VALUES ({user.id}, 1000)")
                    balance = 1000
                if balance != 1:
                    spelling = "credits"
                elif balance == 1:
                    spelling = 'credit'
                if balance == 0:
                    color += 1
                description += f"{user.mention} has ```{balance} {spelling}```\n"

            if color == len(member):
                color = discord.Color.dark_red()
            else:
                color = discord.Color.blue()
            embed.title = "Balances"
            embed.description = description
            embed.color = color
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['gs'],
                      desc="Check your stats for UconnSmashBot's games",
                      usage="gamestats (member) (game_name)")
    async def gameStats(self, ctx: Context, member: typing.Optional[discord.Member] = None, game: str = None):
        if not member:
            member = ctx.author
        async with self.bot.db.acquire() as con:
            if game:
                game = game.lower()
                if not game.lower() in _GAMES:
                    return await ctx.channel.send(
                        embed=discord.Embed(
                            title="Invalid Game",
                            description=f"{ctx.author.mention}, I don't have that game",
                            color=discord.Color.dark_red(),
                        )
                    )
                embed = discord.Embed(
                    title=f"{ctx.author.display_name}'s Stats for {game.title()}",
                    color=discord.Color.blue(),
                )
                results = await con.fetch(
                    f"SELECT * FROM {game} WHERE user_id={ctx.author.id}"
                )
                if results:
                    for stat in _STATS.get(game):
                        embed.add_field(
                            name=stat.title(),
                            value=results[0][stat],
                        )
                else:
                    embed.description = "No data available. Play this game to see your stats appear!"
            else:
                embed = discord.Embed(
                    title=f"{ctx.author.display_name}'s Stats for All Games",
                    color=discord.Color.blue(),
                )
                results = []
                for game in _GAMES:
                    results.append(await con.fetch(
                        f"SELECT * FROM {game} WHERE user_id={ctx.author.id}",
                    ))
                if all(not _ for _ in results):
                    embed.description = "No data is available. Play any game to see your stats appear!"
                else:
                    for result, game in zip(results, _GAMES):
                        embed.add_field(
                            name=game.title(),
                            value="\n".join(
                                f"> {stat.title()}: *{result[0][stat]}*" for stat in _STATS.get(game)
                            ) if result else "No data is available",
                            inline=False
                        )
        return await ctx.channel.send(embed=embed.set_thumbnail(url=ctx.author.avatar_url))

    @commands.command(desc="Transfer credits to other server members",
                      usage="transfer [amount] (@member)*va",
                      note="If you specify more than one member, `[amount]` credits will be given to each member. "
                      "You cannot transfer more credits than you have")
    async def transfer(self, ctx: Context, amount: int = None, members: commands.Greedy[discord.Member] = None):
        if amount is None or amount <= 0:
            return await ctx.channel.send(embed=discord.Embed(
                title="No Amount Specified",
                description=f"{ctx.author.mention}, you must specify a non-zero positive integer amount to transfer",
                color=discord.Color.dark_red(),
            ))
        elif not members:
            return await ctx.channel.send(embed=discord.Embed(
                title="No Members Specified",
                description=f"{ctx.author.mention}, please specify members to transfer credits to",
                color=discord.Color.dark_red(),
            ))
        async with self.bot.db.acquire() as con:
            ctx_bal = await con.fetchval(f"SELECT amount FROM balance WHERE user_id={ctx.author.id}")
            if ctx_bal is None:
                ctx_bal = 1000
                await con.execute(f"INSERT INTO balance(user_id, amount) VALUES ({ctx.author.id}, 1000) ON CONFLICT DO NOTHING")
            transfer_amount = amount * len(members)
        if transfer_amount > ctx_bal:
            return await ctx.channel.send(embed=discord.Embed(
                title="Insufficient Balance",
                description=f"{ctx.author.mention}, you only have {ctx_bal} credit{'s' if ctx_bal != 1 else ''}, "
                f"need {transfer_amount} credit{'s' if transfer_amount != 1 else ''}",
                color=discord.Color.dark_red(),
            ))
        members_str = ", ".join(member.mention for member in members)
        message: discord.Message = await ctx.channel.send(embed=discord.Embed(
            title="Transfer Confirmation",
            description=f"{ctx.author.mention}, to transfer {amount} credit{'s' if amount != 1 else ''} to {members_str}, react with "
            f"{_CONF[0]}, or cancel with {_CONF[1]}",
            color=discord.Color.blue(),
        ))
        for reaction in _CONF:
            await message.add_reaction(reaction)

        timeout = 60
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", check=lambda r, u: r.message == message and str(r.emoji) in _CONF and u.id == ctx.author.id, timeout=timeout)
        except asyncio.TimeoutError:
            return await ctx.channel.send(embed=discord.Embed(
                title="Transfer Confirmation Timed Out",
                description=f"{ctx.author.mention}, your request timed out after {timeout} seconds of inactivity",
                color=discord.Color.dark_red(),
            ))
        if str(reaction.emoji) == _CONF[0]:
            async with self.bot.db.acquire() as con:
                await con.execute(f"UPDATE balance SET amount=amount-{transfer_amount} WHERE user_id={ctx.author.id}")
                for member in members:
                    await con.execute(f"INSERT INTO balance(user_id, amount) VALUES ({member.id}, {1000 + amount}) ON CONFLICT "
                                      f"(user_id) DO UPDATE SET amount=balance.amount+{amount} WHERE balance.user_id=EXCLUDED.user_id")
            embed = discord.Embed(
                title="Transfer Successful",
                description=f"{ctx.author.mention}, {amount} credit{'s' if amount != 1 else ''} have been transferred to {members_str}{' each' if len(members) > 1 else ''}",
                color=discord.Color.blue(),
            ).set_thumbnail(
                url="https://cdn.discordapp.com/attachments/734962101432615006/738390147514499163/chips.png",
            )
        else:
            embed = discord.Embed(
                title="Transfer Canceled",
                description=f"{ctx.author.mention}, you canceled the transfer",
                color=discord.Color.blue(),
            )
        return await ctx.channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Games(bot))
