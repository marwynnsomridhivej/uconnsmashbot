import asyncio
import os
import random
import re
import string
from datetime import datetime, timedelta

import discord
import psutil
from discord.ext import commands
from discord.ext.commands import AutoShardedBot, Context
from utils import GlobalCMDS

updates_reaction = ['✅', '📝', '🛑']
hex_color_rx = re.compile(r'#[A-Fa-f0-9]{6}')
url_rx = re.compile(r'https?://(?:www\.)?.+')
timeout = 300
_CHARS = [_ for _ in string.printable if not _ in string.whitespace]


class Debug(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)

    async def timeout(self, ctx, message: discord.Message) -> discord.Message:
        embed = discord.Embed(title="Report Update Canceled",
                              description=f"{ctx.author.mention}, your report update request timed out",
                              color=discord.Color.dark_red())
        try:
            return await message.edit(embed=embed)
        except (discord.NotFound, discord.HTTPError, discord.Forbidden):
            return await ctx.author.send(embed=embed)

    async def cancel(self, ctx, message: discord.Message) -> discord.Message:
        embed = discord.Embed(title="Report Update Canceled",
                              description=f"{ctx.author.mention}, your report update request was canceled",
                              color=discord.Color.dark_red())
        try:
            return await message.edit(embed=embed)
        except (discord.NotFound, discord.HTTPError, discord.Forbidden):
            return await ctx.author.send(embed=embed)

    @commands.command(desc="Displays UconnSmashBot's ping in milliseconds (ms)",
                      usage="ping")
    async def ping(self, ctx):
        ping = discord.Embed(title='Ping', color=discord.Color.blue())
        ping.set_thumbnail(url='https://cdn1.iconfinder.com/data/icons/travel-and-leisure-vol-1/512/16-512.png')
        ping.add_field(name="UconnSmashBot", value=f'{round(self.bot.latency * 1000)}ms')
        await ctx.send(embed=ping)

    @commands.command(aliases=['usb', 'selfinfo', 'about', 'me'],
                      desc="Get info about me! Mostly for debug purposes though",
                      usage="uconnsmashbot")
    async def uconnsmashbot(self, ctx):
        async with self.bot.db.acquire() as con:
            command_amount = await con.fetchval("SELECT SUM (amount) FROM global_counters")
        current_process = psutil.Process(os.getpid())
        mem = psutil.virtual_memory()
        mem_used = current_process.memory_full_info().uss
        swap = psutil.swap_memory()
        swap_used = getattr(current_process.memory_full_info(), "swap", swap.used)
        disk = psutil.disk_usage("/")
        time_now = int(datetime.now().timestamp())
        complete_command_list = [command for cog in self.bot.cogs
                                 for command in self.bot.get_cog(cog).walk_commands()]
        td = timedelta(seconds=time_now - self.bot.uptime)
        description = (f"Hi there! I am a multipurpose Discord Bot made by <@{self.bot.owner_id}> "
                       "written in Python using the `discord.py` API wrapper. Here are some of my stats:")
        stats = (f"Servers Joined: {len(self.bot.guilds)}",
                 f"Users Served: {len(self.bot.users)}",
                 f"Commands: {len(self.bot.commands)}",
                 f"Commands Including Subcommands: {len(complete_command_list)}",
                 f"Aliases: {len([alias for command in self.bot.commands for alias in command.aliases if command.aliases])}",
                 f"Commands Processed: {command_amount}",
                 f"Uptime: {str(td)}")
        cpu_stats = "```{}```".format(
            "\n".join(
                    [f"Core {counter}: {round(freq, 2)}%"
                     for counter, freq in enumerate(psutil.cpu_percent(percpu=True))]
            )
        )
        memory_stats = "```{}```".format(
            "\n".join(
                [f"Total: {round((mem.total / 1000000), 2)} MB",
                 f"Available: {round((mem.available / 1000000), 2)} MB",
                 f"Used: {round((mem_used / 1000000), 2)} MB",
                 f"Percent: {round(100 * (mem_used / mem.total), 2)}%"]
            )
        )
        swap_stats = "```{}```".format(
            "\n".join(
                [f"Total: {round((swap.total / 1000000))} MB",
                 f"Free: {round((swap.free / 1000000), 2)} MB",
                 f"Used: {round((swap_used / 1000000), 2)} MB",
                 f"Percentage: {round(100 * (swap_used / swap.total), 2)}%"]
            )
        )
        disk_stats = "```{}```".format(
            "\n".join(
                [f"Total: {round((disk.total / 1000000000), 2)} GB",
                 f"Used: {round((disk.used / 1000000000), 2)} GB",
                 f"Free: {round((disk.free / 1000000000), 2)} GB",
                 f"Percentage: {round((100 * disk.used / disk.total), 2)}%"]
            )
        )
        nv = [
            ("Stats", "```{}```".format("\n".join(stats))),
            ("CPU Info", cpu_stats),
            ("Memory Info", memory_stats),
            ("Swap Info", swap_stats),
            ("Disk Info", disk_stats)
        ]
        embed = discord.Embed(title="Info About Me!", description=description, color=discord.Color.blue())
        for name, value in nv:
            embed.add_field(name=name, value=value, inline=False)
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["randomtext"],
                      desc="Generates a random, fixed length string",
                      usage="randomstring (length)",
                      note="`(length)` may be a non-zero, positive integer between 1 and 2000. If `(length)` is unspecified, it defaults to 20")
    async def randomstring(self, ctx: Context, length: int = 20):
        if 1 <= length <= 2000:
            return await ctx.channel.send(
                embed=discord.Embed(
                    title=f"Random String Length {length}",
                    description=f"```{''.join(random.choice(_CHARS) for _ in range(length))}```",
                    color=discord.Color.blue(),
                ).set_footer(
                    text=f"Requested by: {ctx.author.display_name}",
                    icon_url=ctx.author.avatar_url,
                )
            )
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Invalid Length",
                description=f"{ctx.author.mention}, length {length} is an invalid length",
                color=discord.Color.dark_red(),
            )
        )

    @commands.command(aliases=["randomchars"],
                      desc="Generates a random, fixed length string composed of only ASCII letters",
                      usage="randomletters (length)",
                      note="`(length)` may be a non-zero, positive integer between 1 and 2000. If `(length)` is unspecified, it defaults to 20")
    async def randomletters(self, ctx: Context, length: int = 20):
        if 1 <= length <= 2000:
            return await ctx.channel.send(
                embed=discord.Embed(
                    title=f"Random Letters Length {length}",
                    description=f"```{''.join(random.choice(string.ascii_letters) for _ in range(length))}```",
                    color=discord.Color.blue(),
                ).set_footer(
                    text=f"Requested by: {ctx.author.display_name}",
                    icon_url=ctx.author.avatar_url,
                )
            )
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Invalid Length",
                description=f"{ctx.author.mention}, length {length} is an invalid length",
                color=discord.Color.dark_red(),
            )
        )

    @commands.command(aliases=["randomnums", "randomnumbers"],
                      desc="Generates a random, fixed length number composed of the digits from 0-9",
                      usage="randomdigits (length)",
                      note="`(length)` may be a non-zero, positive integer between 1 and 2000. If `(length)` is unspecified, it defaults to 20")
    async def randomdigits(self, ctx: Context, length: int = 20):
        if 1 <= length <= 2000:
            return await ctx.channel.send(
                embed=discord.Embed(
                    title=f"Random Digits Length {length}",
                    description=f"```{''.join(random.choice(string.digits) for _ in range(length))}```",
                    color=discord.Color.blue(),
                ).set_footer(
                    text=f"Requested by: {ctx.author.display_name}",
                    icon_url=ctx.author.avatar_url,
                )
            )
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Invalid Length",
                description=f"{ctx.author.mention}, length {length} is an invalid length",
                color=discord.Color.dark_red(),
            )
        )

    @commands.command(aliases=["randoman"],
                      desc="Generates a random, fixed length string composed of alphanumeric characters",
                      usage="randomalphanumerics (length)",
                      note="`(length)` may be a non-zero, positive integer between 1 and 2000. If `(length)` is unspecified, it defaults to 20")
    async def randomdigits(self, ctx: Context, length: int = 20):
        if 1 <= length <= 2000:
            return await ctx.channel.send(
                embed=discord.Embed(
                    title=f"Random Alphanumerics Length {length}",
                    description=f"```{''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))}```",
                    color=discord.Color.blue(),
                ).set_footer(
                    text=f"Requested by: {ctx.author.display_name}",
                    icon_url=ctx.author.avatar_url,
                )
            )
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Invalid Length",
                description=f"{ctx.author.mention}, length {length} is an invalid length",
                color=discord.Color.dark_red(),
            )
        )

    @commands.command(desc="Picks a random number from the specified range",
                      usage="randomrange [min] [max]",
                      note="Both `[min]` and `[max]` should be integer values")
    async def randomrange(self, ctx: Context, min: int, max: int):
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Random Range",
                description=f"From the range {min} to {max}, I pick...\n```{random.choice(range(min, max))}```",
                color=discord.Color.blue(),
            )
        )


def setup(bot):
    bot.add_cog(Debug(bot))
