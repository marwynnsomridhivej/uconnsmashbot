import asyncio
import discord
import typing
from discord.ext import commands
from utils import globalcommands, customerrors

gcmds = globalcommands.GlobalCMDS()


class Games(commands.Cog):

    def __init__(self, bot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)

    @commands.command(aliases=['bal'],
                      desc="Check your balance and compare with other people",
                      usage="balance (member)*va")
    async def balance(self, ctx, member: commands.Greedy[discord.Member] = None):
        if not member:
            balance = await gcmds.get_balance(ctx.author)
            if not balance:
                await gcmds.balance_db(f"INSERT INTO balance(user_id, amount) VALUES ({ctx.author.id}, 1000)")
                balance = 1000
        else:
            description = ""
            color = 0
            for user in member:
                balance = await gcmds.get_balance(user)
                if not balance:
                    await gcmds.balance_db(f"INSERT INTO balance(user_id, amount) VALUES ({user.id}, 1000)")
                    balance = 1000
                if balance != 1:
                    spelling = "credits"
                elif balance == 1:
                    spelling = 'credit'
                if balance == 0:
                    color += 1
                description += f"{user.mention} has ```{balance} {spelling}```\n"

        if not member:
            if balance != 1:
                spelling = "credits"
            elif balance == 1:
                spelling = 'credit'
            if balance > 0:
                color = discord.Color.blue()
            else:
                color = discord.Color.dark_red()

            balanceEmbed = discord.Embed(title="Your Current Balance",
                                         description=f"{ctx.author.mention}, your current balance is: ```{balance} {spelling}```",
                                         color=color)
            balanceEmbed.set_thumbnail(
                url="https://cdn.discordapp.com/attachments/734962101432615006/738390147514499163"
                    "/chips.png")
            await ctx.channel.send(embed=balanceEmbed)

        else:
            if color == len(member):
                color = discord.Color.dark_red()
            else:
                color = discord.Color.blue()
            balanceEmbed = discord.Embed(title="Balances",
                                         description=description,
                                         color=color)
            balanceEmbed.set_thumbnail(
                url="https://cdn.discordapp.com/attachments/734962101432615006/738390147514499163"
                    "/chips.png")
            await ctx.channel.send(embed=balanceEmbed)

    @commands.command(aliases=['gamestats', 'gs'],
                      desc="Check your stats for UconnSmashBot's games",
                      usage="gamestats (member)*va (game_name)")
    async def gameStats(self, ctx, member: typing.Optional[discord.Member] = None, game: str = None):
        if not member:
            member = ctx.author
        game_names = ["blackjack", "coinflip", "connectfour", "slots", "uno"]
        async with self.bot.db.acquire() as con:
            if not game:
                result = [await con.fetch(f"SELECT * FROM {name} WHERE user_id = {member.id}") for name in game_names]
            else:
                result = await con.fetch(f"SELECT * FROM {game.lower()} WHERE user_id = {member.id}")
        if not result:
            raise customerrors.NoStatsGame(member, game.lower()) if game else customerrors.NoStatsAll(member)

        if not game:
            if not [sub_elem for elem in result for sub_elem in elem]:
                raise customerrors.NoStatsAll(member)
            embed = discord.Embed(title=f"Stats for {member.display_name}",
                                  color=discord.Color.blue())
            for name in game_names:
                pre_item = result[int(game_names.index(name))]
                if pre_item:
                    item = result[int(game_names.index(name))][0]
                    if item:
                        values = [f"> {key}: *{item[key]}*" for key in item.keys() if key != "user_id"]
                        embed.add_field(name=name.title(),
                                        value="\n".join(values),
                                        inline=True)
                else:
                    embed.add_field(name=name.title(),
                                    value="> N/A",
                                    inline=True)
        else:
            jsoned = dict(result[0])
            desc_list = [f"> {key}: *{jsoned[key]}*" for key in sorted(jsoned.keys(), reverse=True)]
            embed = discord.Embed(title=f"{game.title()} Stats for {member.display_name}",
                                  description="\n".join(desc_list),
                                  color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Transfer credits to other server members",
                      usage="transfer [amount] (@member)*va",
                      note="If you specify more than one member, `[amount]` credits will be given to each member. "
                      "You cannot transfer more credits than you have")
    async def transfer(self, ctx, amount: int = None, member: commands.Greedy[discord.Member] = None):
        cmdExit = False
        if amount is None:
            errorEmbed = discord.Embed(title="No Amount Specified",
                                       description=f"{ctx.author.mention}, you must specify a credit amount to transfer",
                                       color=discord.Color.dark_red())
            await ctx.channel.send(embed=errorEmbed)
            cmdExit = True
        if member is None:
            errorEmbed = discord.Embed(title="No User Specified",
                                       description=f"{ctx.author.mention}, you must specify user to transfer credit to",
                                       color=discord.Color.dark_red())
            await ctx.channel.send(embed=errorEmbed)
            cmdExit = True
        if cmdExit:
            return

        memberString = ""
        userlist = [ctx.author.id]
        for members in member:
            memberString += f"{members.mention}, "
            userlist.append(members.id)

        await gcmds.balance_db(f"INSERT INTO balance(user_id, amount) VALUES ({ctx.author.id}, 1000) ON CONFLICT DO NOTHING")
        balance = await gcmds.get_balance(ctx.author)

        if (balance) < (amount * (int(len(userlist)) - 1)):
            if amount != 1:
                spell = "credits"
            else:
                spell = "credit"
            errorEmbed = discord.Embed(title="Insufficient Funds",
                                       description=f"{ctx.author.mention}, you cannot transfer more than you have\n"
                                                   f"*Attempted to transfer* "
                                                   f"```{(amount * (int(len(userlist)) - 1))} {spell}```, only have"
                                                   f"```{balance} {spell}```",
                                       color=discord.Color.dark_red())
            await ctx.channel.send(embed=errorEmbed)
            return
        else:
            if amount != 1:
                spell = "credits"
            else:
                spell = "credit"
            confirmEmbed = discord.Embed(title="Credits Transfer",
                                         description=f"{ctx.author.mention}, are you sure you want to transfer\n"
                                                     f"```{amount} {spell}```\nto {memberString[:-2]}",
                                         color=discord.Color.blue())
            message = await ctx.channel.send(embed=confirmEmbed)
            await message.add_reaction('✅')
            await message.add_reaction('❌')

            def check(reaction, user):
                if ctx.author == user and str(reaction.emoji) == '✅':
                    return True
                elif ctx.author == user and str(reaction.emoji) == '❌':
                    return True
                else:
                    return False

            try:
                choice = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                for item in choice:
                    if str(item) == '✅':
                        choice = 'confirm'
                        break
                    if str(item) == '❌':
                        choice = 'cancel'
                        break
                if choice == 'confirm':
                    await message.clear_reactions()
                    description = "Successfully transferred:\n"
                    await gcmds.balance_db(f"UPDATE balance SET amount = amount - {amount * (int(len(userlist)) - 1)} WHERE user_id = {ctx.author.id}")
                    for members in member:
                        await gcmds.balance_db(f"UPDATE balance SET amount = amount + {amount} WHERE user_id = {members.id}")
                        description += f"```{amount}``` ➡ {members.mention}\n"
                    confirmEmbed = discord.Embed(title="Credits Transfer Successful",
                                                 description=description,
                                                 color=discord.Color.blue())
                    await message.edit(embed=confirmEmbed)

                    return
                if choice == 'cancel':
                    await message.clear_reactions()
                    confirmEmbed = discord.Embed(title="Credits Transfer Cancelled",
                                                 description=f"{ctx.author.mention} cancelled the transfer\n",
                                                 color=discord.Color.dark_red())
                    await message.edit(embed=confirmEmbed)
                    return
            except asyncio.TimeoutError:
                await message.clear_reactions()
                canceled = discord.Embed(title="Confirmation Timeout",
                                         description=f"{ctx.author.mention}, transfer cancelled due to inactivity",
                                         color=discord.Color.dark_red())
                canceled.set_thumbnail(url='https://cdn.discordapp.com/attachments/734962101432615006'
                                           '/738083697726849034/nocap.jpg')
                canceled.set_footer(text=f"{ctx.author.name} did not provide a valid reaction within 60 seconds")
                await message.edit(embed=canceled)
                return


def setup(bot):
    bot.add_cog(Games(bot))
