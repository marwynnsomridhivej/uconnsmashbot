import re
import typing

import discord
from discord.ext import commands
from utils import customerrors, globalcommands

gcmds = globalcommands.GlobalCMDS()
FC_REGEX = re.compile(r"SW-[\d]{4}-[\d]{4}-[\d]{4}")


class Nintendo(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        global gcmds
        self.bot = bot
        self.bot.loop.create_task(self.init_nintendo())
        gcmds = globalcommands.GlobalCMDS(self.bot)

    async def init_nintendo(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS nintendo(user_id bigint PRIMARY KEY, "
                              "friend_code text)")
        return

    async def send_nintendo_help(self, ctx):
        pfx = f"{await gcmds.prefix(ctx)}nintendo"
        description = (f"UconnSmashBot's various Nintendo features allows users to register their Nintendo Switch friend "
                       "code. Connect with other people and make some new friends! UconnSmashBot respects your privacy and "
                       "will allow you to register and unregister your information at any time")
        register = (f"**Usage:** `{pfx} register [friend_code]`",
                    "**Returns:** An embed that confirms you have successfully registered your information",
                    "**Aliases:** `reg`",
                    "**Note:** `[friend_code]` must be specified and be in the format ```SW-XXXX-XXXX-XXXX```")
        unregister = (f"**Usage:** `{pfx} unregister`",
                      "**Returns:** An embed that confirms you have successfully unregistered your information",
                      "**Aliases:** `unreg`",
                      "**Special Cases:** You must be registered in order to successfully unregister")
        profile = (f"**Usage:** `{pfx} profile (@user)`",
                   "**Returns:** An embed with user's profile details if registered",
                   "**Aliases:** `prof` `pfl`")
        nv = [("Register", register), ("Unregister", unregister), ("Profile", profile)]
        embed = discord.Embed(title="Nintendo Commands Help",
                              description=description,
                              color=discord.Color.blue())
        for name, value in nv:
            embed.add_field(name=name,
                            value="> " + "\n> ".join(value),
                            inline=False)
        return await ctx.channel.send(embed=embed)

    async def not_valid_friend_code(self, ctx, friend_code: str):
        embed = discord.Embed(title="Invalid Friend Code",
                              description=f"{ctx.author.mention}, `{friend_code}` is not a valid friend code",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def not_registered(self, ctx, member: discord.Member = None):
        embed = discord.Embed(title="Not Registered",
                              description=f"{ctx.author.mention}, you are not registered in the first place",
                              color=discord.Color.dark_red())
        if member:
            embed.description = f"{member.mention} has not registered their profile"
        return await ctx.channel.send(embed=embed)

    @commands.group(invoke_without_command=True,
                    aliases=['ntd'],
                    desc="Displays the help command for nintendo",
                    usage="nintendo")
    async def nintendo(self, ctx):
        return await self.send_nintendo_help(ctx)

    @nintendo.command(aliases=['reg', 'register'])
    async def nintendo_register(self, ctx, *, friend_code: str):
        if not re.match(FC_REGEX, friend_code):
            return await self.not_valid_friend_code(ctx, friend_code)
        async with self.bot.db.acquire() as con:
            await con.execute(f"DELETE FROM nintendo WHERE user_id={ctx.author.id};"
                              f"INSERT INTO nintendo(user_id, friend_code) VALUES ({ctx.author.id}, $t${friend_code}$t$)")
        embed = discord.Embed(title="Registration Successful",
                              description=f"{ctx.author.mention}, your friend code was registered successfully",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @nintendo.command(aliases=['unreg', 'unregister'])
    async def nintendo_unregister(self, ctx):
        async with self.bot.db.acquire() as con:
            prev_val = await con.fetchval(f"DELETE FROM nintendo WHERE user_id={ctx.author.id} RETURNING user_id")
        if not prev_val:
            return await self.not_registered(ctx)
        else:
            embed = discord.Embed(title="Successfully Unregistered",
                                  description=f"{ctx.author.mention}, your information is no longer registered",
                                  color=discord.Color.blue())
            return await ctx.channel.send(embed=embed)

    @nintendo.command(aliases=['prof', 'pfl', 'profile'])
    async def nintendo_profile(self, ctx, *, member: typing.Optional[discord.Member] = None):
        if not member:
            member = ctx.author
        async with self.bot.db.acquire() as con:
            friend_code = await con.fetchval(f"SELECT friend_code FROM nintendo WHERE user_id={member.id}")
        if not friend_code:
            return await self.not_registered(ctx, member)
        embed = discord.Embed(title=f"{member.display_name}'s Profile",
                              description=f"**Friend Code:** ```{friend_code}```",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Nintendo(bot))
