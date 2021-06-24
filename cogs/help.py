import json
import os
from collections import namedtuple
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands
from utils import FieldPaginator, GlobalCMDS, customerrors

GAMES = [
    'Blackjack',
    'Coinflip',
    'ConnectFour',
    'Slots',
    'Uno'
]
NON_DETAILED = [
    'Actions',
    'Disboard',
    'Gather',
    'Locks',
    'Logging',
    'Pokedex',
    'Reddit',
    'Redirects',
    'Reminders',
    'Serverlink',
    'Starboard',
    'Suggestions',
    'Tags',
    'Todo',
    'Trigger',
]
HIDDEN = ['Hidden']
DEFAULT_THUMBNAIL = "https://www.jing.fm/clipimg/full/71-716621_transparent-clip-art-open-book-frame-line-art.png"
SUPPORT_SERVER_INVITE = "https://discord.gg/78XXt3Q"
_HELP_BASE = "https://bot.marwynn.me/commands"
CogCommands = namedtuple("CogCommands", ['cog_name', 'cog'])


class Help(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self.client_session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.bot.loop.create_task(self.init_cogs_list())

    async def init_cogs_list(self):
        await self.bot.wait_until_ready()
        self.mb_cogs = sorted([CogCommands(cog.title(), self.bot.get_cog(cog))
                               for cog in self.bot.cogs
                               if cog not in GAMES])
        return

    async def dispatch(self, ctx, command: commands.Command):
        timestamp = f"Executed by {ctx.author.display_name} " + "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now())
        pfx = await self.gcmds.prefix(ctx)
        kwargs = command.__original_kwargs__
        embed = discord.Embed(
            title=f"Detailed Help ⟶ {command.name.title()}",
            description=f"```{kwargs['desc']}```",
            color=discord.Color.blue(),
            url=f"{_HELP_BASE}?command={command.name}#main-commands")
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
            if name == "fuck":
                return
            command = self.bot.get_command(name)
            if not command:
                raise customerrors.CommandNotFound(name)
            try:
                return await self.dispatch(ctx, self.bot.get_command(name))
            except KeyError:
                raise customerrors.CommandHelpDirectlyCalled(name)
        nv = []
        for name, cog in self.mb_cogs:
            if name in NON_DETAILED:
                cog_commands = []
                value = f"*Do `{await self.gcmds.prefix(ctx)}{name.lower()}` for more info*"
            elif name in HIDDEN:
                continue
            else:
                cog_commands = cog.get_commands()
                value = f"`{'` `'.join([command.name.lower() for command in cog_commands])}`"
            if value == "``":
                continue
            else:
                nv.append((name, value, False))
        timestamp = f"Requested by: {ctx.author.display_name} " + "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now())
        embed = discord.Embed(
            title="UconnSmashBot Help Menu",
            description="This is a paginated panel of all the commands I currently support! "
            f"To get help on a specific command, type:```{await self.gcmds.prefix(ctx)}help (command)```",
            color=discord.Color.blue(),
            url=_HELP_BASE,
        )
        embed.set_thumbnail(url=DEFAULT_THUMBNAIL)
        embed.set_author(name="UconnSmashBot", icon_url=ctx.me.avatar_url)
        pag = FieldPaginator(ctx, entries=nv, per_page=6, show_entry_count=False, footer=timestamp, embed=embed)
        return await pag.paginate()

    @commands.command(aliases=['docs', 'notation'],
                      desc="Displays what the symbols in the help messages of commands mean",
                      usage="documentation")
    async def documentation(self, ctx):
        embed = discord.Embed(title="Documentation",
                              description="The help commands all use a specific way of notating "
                              "how to use UconnSmashBot's commands. This is a detailed explanation of "
                              "what the notation means",
                              color=discord.Color.blue(),
                              url=SUPPORT_SERVER_INVITE)
        definitions = ("- `command` ⟶ the command you are getting help on. Appears immediately after the prefix",
                       "- `subcommand` ⟶ other commands that are based on a base command. Subcommands are "
                       "specified after the base command",
                       "- `argument/parameter` ⟶ the additional elements you need to "
                       "supply in order for the commands to work as intended",
                       "- `mention/ping` ⟶ using Discord's @user for users or #channel for channels")
        embed.add_field(name="Definitions",
                        value="Here are some important definitions to be aware of:"
                        "\n> " + "\n> ".join(definitions),
                        inline=False)
        brackets = ("Brackets `[argument]` and parentheses `(argument)` indicate the necessity for "
                    "the `argument` to be specified. Brackets around an argument like `[argument]` "
                    "indicate that `argument` must be specified. Parentheses around an argument like "
                    "`(argument)` indicate that `argument` may be specified, but is not required")
        mentionable = ("The presence of `@` or `#` in front of an argument specifies that this argument "
                       "can be in the form of a mentionable, such as `@user` or `#channel`. Arguments that "
                       "can be mentioned can also be entered using their ID, or in specific cases, their "
                       "name, although this can sometimes not work as well as mentioning")
        var_amt = ("The presence of `*va` directly after an argument indicates that the argument "
                   "accepts more than one argument of the same type. Bracket and parenthesis notation "
                   "still apply, as `*va` is an extension to the notation")
        nv = [("Argument Requirements", brackets), ("Mentionables", mentionable), ("Variable Amounts", var_amt)]
        for name, value in nv:
            embed.add_field(name=name, value=f"> {value}", inline=False)
        timestamp = f"Requested by: {ctx.author.display_name} " + "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now())
        embed.set_footer(text=timestamp, icon_url=ctx.author.avatar_url)
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Fetches the invite link to the UconnSmashBot Support Server",
                      usage="support")
    async def support(self, ctx):
        embed = discord.Embed(title="Support Server",
                              description=f"Join my support server using this link:\n> https://discord.gg/78XXt3Q\n"
                              "Thank you for using UconnSmashBot!",
                              color=discord.Color.blue())
        embed.set_thumbnail(url=self.bot.user.avatar_url)
        return await ctx.channel.send(content="https://discord.gg/78XXt3Q", embed=embed)


def setup(bot):
    bot.add_cog(Help(bot))
