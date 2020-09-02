import json
import logging
import math
import os
import random
import socket
import sys
import re
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from globalcommands import GlobalCMDS as gcmds

DISABLED_COGS = ["Blackjack", 'Coinflip', 'Connectfour', 'Oldmaid', 'Slots', 'Uno',
                 'Reactions', 'Moderation', 'Music', 'Utility']
DISABLED_COMMANDS = []
token_rx = re.compile(r'[MN]\w{23}.\w{6}.\w{27}')

if os.path.exists('discord.log'):
    os.remove('discord.log')


async def get_prefix(client, message):
    if isinstance(message.channel, discord.DMChannel) or isinstance(message.channel, discord.GroupChannel):
        extras = ('mb ', 'mB ', 'Mb ', 'MB ', 'm!', 'm! ')
        return commands.when_mentioned_or(*extras)(client, message)
    else:
        with open('prefixes.json', 'r') as f:
            prefixes = json.load(f)
            extras = (
                f'{prefixes[str(message.guild.id)]}', f'{prefixes[str(message.guild.id)]} ', 'mb ', 'mB ', 'Mb ', 'MB ',
                'm!')
            return commands.when_mentioned_or(*extras)(client, message)


client = commands.AutoShardedBot(command_prefix=get_prefix, help_command=None, shard_count=1)

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


@tasks.loop(seconds=120)
async def status():
    activity1 = discord.Activity(name="m!h for help!", type=discord.ActivityType.listening)
    activity2 = discord.Activity(name=f"{len(client.users)} users!", type=discord.ActivityType.watching)
    activity3 = discord.Activity(name=f"{len(client.guilds)} servers!", type=discord.ActivityType.watching)
    activity4 = discord.Activity(name="Under development [WIP]", type=discord.ActivityType.playing)
    activity5 = discord.Activity(name="MS Arranges#3060 for source code info", type=discord.ActivityType.watching)
    activity6 = discord.Activity(name=f"{len(client.commands)} commands", type=discord.ActivityType.listening)
    activityList = [activity1, activity2, activity3, activity4, activity5, activity6]
    activity = random.choice(activityList)
    await client.change_presence(status=discord.Status.online, activity=activity)


@client.event
async def on_ready():
    cogs = [filename[:-3] for filename in os.listdir('./cogs') if filename.endswith(".py")]
    for cog in sorted(cogs):
        client.load_extension(f'cogs.{cog}')
        print(f"Cog \"{cog}\" has been loaded")
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    print(f'Successfully logged in as {client.user}\nIP: {ip}\nHost: {str(hostname)}\nServing '
          f'{len(client.users)} users across {len(client.guilds)} servers')
    await status.start()


@client.event
async def on_message(message):
    if re.search(token_rx, message.content) and message.guild:
        try:
            await gcmds.msgDelete(gcmds, message)
        except (discord.NotFound, discord.Forbidden):
            pass
        embed = discord.Embed(title="Token Found",
                              description=f"{message.author.mention}, a Discord token was found in your message. It has "
                              "automatically been deleted.",
                              color=discord.Color.dark_red())
        await message.channel.send(embed=embed, delete_after=10)
    
    await client.process_commands(message)


@client.check
async def check_blacklist(ctx):
    if not os.path.exists('blacklist.json'):
        with open('blacklist.json', 'w') as f:
            json.dump({'Users': {}}, f, indent=4)
    with open('blacklist.json', 'r') as f:
        blacklist = json.load(f)
        try:
            blacklist["Users"]
            blacklist["Guilds"]
        except KeyError:
            blacklist["Users"] = {}
            blacklist["Guilds"] = {}

        try:
            if blacklist["Users"][str(ctx.author.id)]:
                blacklisted = discord.Embed(title="You Are Blacklisted",
                                            description=f"{ctx.author.mention}, you are blacklisted from using this bot. "
                                                        f"Please contact `MS Arranges#3060` if you believe this is a "
                                                        f"mistake",
                                            color=discord.Color.dark_red())
                await ctx.channel.send(embed=blacklisted, delete_after=10)
                return False
            elif blacklist["Guilds"][str(ctx.guild.id)]:
                blacklisted = discord.Embed(title="Guild is Blacklisted",
                                            description=f"{ctx.guild.name} is blacklisted from using this bot. "
                                                        f"Please contact `MS Arranges#3060` if you believe this is a "
                                                        f"mistake",
                                            color=discord.Color.dark_red())
                await ctx.channel.send(embed=blacklisted, delete_after=10)
                return False
            else:
                return True
        except KeyError:
            return True


@client.check
async def disable_dm_exec(ctx):
    if not ctx.guild and (ctx.cog.qualified_name in DISABLED_COGS or ctx.command.name in DISABLED_COMMANDS):
        disabled = discord.Embed(title="Command Disabled in Non Server Channels",
                                 description=f"{ctx.author.mention}, `m!{ctx.invoked_with}` can only be accessed "
                                             f"in a server",
                                 color=discord.Color.dark_red())
        await ctx.channel.send(embed=disabled)
        return False
    else:
        return True


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        req_arg = discord.Embed(title="Missing Required Argument",
                                description=f"{ctx.author.mention}, `[{error.param.name}]` is a required argument",
                                color=discord.Color.dark_red())
        await ctx.channel.send(embed=req_arg, delete_after=10)
    elif isinstance(error, discord.ext.commands.MissingPermissions):
        missing = discord.Embed(title="Insufficient User Permissions",
                                description=f"{ctx.author.mention}, to execute this command, you need "
                                            f"`{'` `'.join(error.missing_perms).replace('_', ' ').title()}`",
                                color=discord.Color.dark_red())
        await ctx.channel.send(embed=missing, delete_after=10)
    elif isinstance(error, discord.ext.commands.BotMissingPermissions):
        missing = discord.Embed(title="Insufficient Bot Permissions",
                                description=f"{ctx.author.mention}, to execute this command, I need "
                                            f"`{'` `'.join(error.missing_perms).replace('_', ' ').title()}`",
                                color=discord.Color.dark_red())
        await ctx.channel.send(embed=missing, delete_after=10)
    elif isinstance(error, commands.NotOwner):
        not_owner = discord.Embed(title="Insufficient User Permissions",
                                  description=f"{ctx.author.mention}, only the bot owner is authorised to use this "
                                              f"command",
                                  color=discord.Color.dark_red())
        await ctx.channel.send(embed=not_owner, delete_after=10)
    elif isinstance(error, commands.CommandNotFound):
        await gcmds.invkDelete(gcmds, ctx)
        notFound = discord.Embed(title="Command Not Found",
                                 description=f"{ctx.author.mention}, `{ctx.message.content}` "
                                             f"does not exist\n\nDo `{gcmds.prefix(gcmds, ctx)}help` for help",
                                 color=discord.Color.dark_red())
        await ctx.channel.send(embed=notFound, delete_after=10)
    elif isinstance(error, commands.CommandOnCooldown):
        cooldown_time_truncated = truncate(error.retry_after, 3)
        if cooldown_time_truncated < 1:
            spell = "milliseconds"
            cooldown_time_truncated *= 1000
        else:
            spell = "seconds"
        cooldown = discord.Embed(title="Command on Cooldown",
                                 description=f"{ctx.author.mention}, this command is still on cooldown for {cooldown_time_truncated} {spell}",
                                 color=discord.Color.dark_red())
        await ctx.channel.send(embed=cooldown, delete_after=math.ceil(error.retry_after))
    elif isinstance(error, commands.CheckFailure):
        pass
    else:
        raise error


def truncate(number: float, decimal_places: int):
    stepper = 10.0 ** decimal_places
    return math.trunc(stepper * number) / stepper


@client.event
async def on_guild_join(guild):
    if not os.path.exists('blacklist.json'):
        with open('blacklist.json', 'w') as f:
            json.dump({'Guilds': {}}, f, indent=4)
    with open('blacklist.json', 'r') as f:
        blacklist = json.load(f)
        try:
            blacklist["Guilds"]
        except KeyError:
            blacklist["Guilds"] = {}
        if guild.id in blacklist["Guilds"]:
            to_leave = client.get_guild(guild.id)
            await to_leave.leave()
    if not os.path.exists('prefixes.json'):
        with open('prefixes.json', 'w') as f:
            f.write('{\n\n}')
    with open('prefixes.json', 'r') as f:
        prefixes = json.load(f)
    prefixes[str(guild.id)] = 'm!'

    with open('prefixes.json', 'w') as f:
        json.dump(prefixes, f, indent=4)


@client.event
async def on_guild_remove(guild):
    with open('prefixes.json', 'r') as f:
        prefixes = json.load(f)

    prefixes.pop(str(guild.id))

    with open('prefixes.json', 'w') as f:
        json.dump(prefixes, f, indent=4)


if not gcmds.init_env(gcmds):
    sys.exit("Please put your bot's token inside the created .env file")
load_dotenv()
token = os.getenv('TOKEN')
client.run(token)