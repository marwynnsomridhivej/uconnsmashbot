import random
from collections import namedtuple
from datetime import datetime

import discord
from discord.ext import commands
from utils import customerrors, globalcommands

gcmds = globalcommands.GlobalCMDS()
GAMES = ['Blackjack', 'Coinflip', 'ConnectFour', 'Slots', 'UNO']
NON_DETAILED = ['Actions', 'Disboard', 'Locks', 'Minecraft', 'Nintendo', 'Pokedex', 'Reddit',
                'Redirects', 'Reminders', 'Serverlink', 'Starboard', 'Tags', 'Todo']
DEFAULT_THUMBNAIL = "https://www.jing.fm/clipimg/full/71-716621_transparent-clip-art-open-book-frame-line-art.png"
SUPPORT_SERVER_INVITE = "https://discord.gg/78XXt3Q"
CogCommands = namedtuple("CogCommands", ['cog_name', 'cog'])


class Help(commands.Cog):

    def __init__(self, bot):
        global gcmds
        self.bot = bot
        self.bot.loop.create_task(self.init_cogs_list())
        gcmds = globalcommands.GlobalCMDS(self.bot)

    async def init_cogs_list(self):
        await self.bot.wait_until_ready()
        self.mb_cogs = sorted([CogCommands(cog.title(), self.bot.get_cog(cog))
                               for cog in self.bot.cogs
                               if cog not in GAMES])
        return

    async def dispatch(self, ctx, command: commands.Command):
        timestamp = f"Executed by {ctx.author.display_name} " + "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now())
        pfx = await gcmds.prefix(ctx)
        kwargs = command.__original_kwargs__
        embed = discord.Embed(title=f"Detailed Help ⟶ {command.name.title()}",
                              description=f"```{kwargs['desc']}```", color=discord.Color.blue())
        embed.add_field(name="Usage", value=f"```{pfx}{command.usage}```", inline=False)
        for attr in [key for key in kwargs.keys() if not key in ['name', 'desc', 'usage', 'invoke_without_command']]:
            if attr == 'uperms':
                name = "User Permissions"
                value = f"`{'` `'.join(kwargs[attr])}`"
            elif attr == 'bperms':
                name = "Bot Permissions"
                value = f"`{'` `'.join(kwargs[attr])}`"
            elif attr == 'aliases':
                name = attr.title()
                value = f"`{'` `'.join([alias for alias in command.aliases if alias != command.name.lower()])}`"
            elif attr == 'note':
                name = attr.title()
                value = f"*{kwargs[attr]}*"
            else:
                name = attr.title()
                value = kwargs[attr]
            embed.add_field(name=name, value=value, inline=False)
        embed.set_thumbnail(url=kwargs.get("thumb", DEFAULT_THUMBNAIL))
        embed.set_footer(text=timestamp, icon_url=ctx.author.avatar_url)
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['h'],
                      desc="The help command for the help command",
                      usage="help (command)",
                      note="If `(command)` is specified, it will show the detailed"
                      " help for that command")
    async def help(self, ctx, *, name: str = None):
        if name:
            command = self.bot.get_command(name)
            if not command:
                raise customerrors.CommandNotFound(name)
            try:
                return await self.dispatch(ctx, self.bot.get_command(name))
            except KeyError:
                raise customerrors.CommandHelpDirectlyCalled(name)
        timestamp = f"Executed by {ctx.author.display_name} " + "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now())
        embed = discord.Embed(title="UCONN Smash Bot Help Menu",
                              color=discord.Color.blue(),
                              url=SUPPORT_SERVER_INVITE,
                              description="These are all the commands I currently support! "
                              f"To get help on a specific command, type:```{await gcmds.prefix(ctx)}help (command)```")
        embed.set_thumbnail(url=DEFAULT_THUMBNAIL)
        embed.set_author(name="UCONN Smash Bot", icon_url=ctx.me.avatar_url)
        embed.set_footer(text=timestamp, icon_url=ctx.author.avatar_url)
        for name, cog in self.mb_cogs:
            if name in NON_DETAILED:
                cog_commands = []
                value = f"*Do `{await gcmds.prefix(ctx)}{name.lower()}` for more info*"
            else:
                cog_commands = cog.get_commands()
                value = f"`{'` `'.join([command.name.lower() for command in cog_commands])}`"
            if value == "``":
                continue
            else:
                embed.add_field(name=name, value=value,
                                inline=False if len(cog_commands) > 3 else True)
        return await ctx.channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Help(bot))
