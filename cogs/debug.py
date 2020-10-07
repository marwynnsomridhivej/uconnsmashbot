import asyncio
import datetime

import discord
import dotenv
from discord.ext import commands
from utils import globalcommands

gcmds = globalcommands.GlobalCMDS()
updates_reaction = ['✅', '📝', '🛑']


class Debug(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(desc="Displays UconnSmashBot's ping in milliseconds (ms)",
                      usage="ping")
    async def ping(self, ctx):
        ping = discord.Embed(title='Ping', color=discord.Color.blue())
        ping.set_thumbnail(url='https://cdn1.iconfinder.com/data/icons/travel-and-leisure-vol-1/512/16-512.png')
        ping.add_field(name="UconnSmashBot", value=f'{round(self.bot.latency * 1000)}ms')
        await ctx.send(embed=ping)

    @commands.command(desc="Displays what UconnSmashBot shard is connected to your server",
                      usage="shard (flag)",
                      note="If `(flag)` is \"count\", it will display the total number of shards")
    async def shard(self, ctx, option=None):
        if option != 'count':
            shardDesc = f"This server is running on shard: {ctx.guild.shard_id}"
        else:
            shardDesc = f"**Shards:** {self.bot.shard_count}"
        shardEmbed = discord.Embed(title="Shard Info",
                                   description=shardDesc,
                                   color=discord.Color.blue())
        await ctx.channel.send(embed=shardEmbed)


def setup(bot):
    bot.add_cog(Debug(bot))
