import asyncio
import itertools
import logging
import os
import socket
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

import asyncpg
import discord
from aiohttp import ClientSession
from discord.ext import commands, tasks
from lavalink.exceptions import NodeException

from utils import context, globalcommands

try:
    import uvloop
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
finally:
    loop = asyncio.get_event_loop()

gcmds = globalcommands.GlobalCMDS()
DISABLED_COGS = ["Blackjack", 'Coinflip', 'Connectfour', 'Oldmaid', 'Slots', 'Uno',
                 'Reactions', 'Moderation', 'Music', 'Utility']
DISABLED_COMMANDS = []
version = f"Running UconnSmashBot {gcmds.version}"

if os.path.exists('discord.log'):
    os.remove('discord.log')

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler("discord.log", mode="a", maxBytes=25000000,
                              backupCount=2, encoding="utf-8", delay=0)
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


async def get_prefix(self: commands.AutoShardedBot, message):
    if not message.guild:
        extras = ('usb ', 'USB ', 'Usb ', 'u!', 'U! ')
    else:
        async with self.db.acquire() as con:
            prefix = await con.fetchval(f"SELECT custom_prefix from guild WHERE guild_id = {message.guild.id}")
        extras = (
            f'{prefix}', 'usb ', 'USB ', 'Usb ', 'u!', 'U! ')
    return commands.when_mentioned_or(*extras)(self, message)


async def run(uptime):
    credentials = {
        "user": os.getenv("PG_USER"),
        "password": os.getenv("PG_PASSWORD"),
        "database": os.getenv("PG_DATABASE"),
        "host": os.getenv("PG_HOST")
    }

    mb_credentials = {
        "user": os.getenv("MB_PG_USER"),
        "password": os.getenv("MB_PG_PASSWORD"),
        "database": os.getenv("MB_PG_DATABASE"),
        "host": os.getenv("MB_PG_HOST")
    }

    db = await asyncpg.create_pool(**credentials)
    await db.execute("CREATE TABLE IF NOT EXISTS guild(guild_id bigint PRIMARY KEY, custom_prefix text, automod boolean "
                     "DEFAULT FALSE, token BOOLEAN DEFAULT FALSE, log_channel bigint, log_level smallint DEFAULT 0)")
    await db.execute("CREATE TABLE IF NOT EXISTS global_counters(command text PRIMARY KEY, amount NUMERIC)")
    await db.execute("CREATE TABLE IF NOT EXISTS guild_counters(guild_id bigint, command text, amount NUMERIC)")
    mbdb = await asyncpg.create_pool(**mb_credentials)

    description = "A MarwynnBot port for the University of Connecticut's Super Smash Bros. club."
    startup = discord.Activity(name="Starting Up...", type=discord.ActivityType.playing)
    intents = discord.Intents.all()
    bot = Bot(command_prefix=get_prefix, help_command=None, shard_count=1, description=description, db=db,
              fetch_offline_members=True, status=discord.Status.online, activity=startup, uptime=uptime,
              intents=intents, owner_id=int(os.getenv("OWNER_ID")))

    try:
        await bot.start(gcmds.env_check("TOKEN"))
    except KeyboardInterrupt:
        await db.close()
        await bot.close()


class Bot(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        global gcmds
        super().__init__(
            command_prefix=kwargs['command_prefix'],
            help_command=kwargs["help_command"],
            shard_count=kwargs['shard_count'],
            description=kwargs["description"],
            fetch_offline_members=kwargs['fetch_offline_members'],
            status=kwargs['status'],
            activity=kwargs['activity'],
            intents=kwargs['intents'],
            owner_id=kwargs['owner_id'],
        )
        self.uptime = kwargs['uptime']
        self.db = kwargs.pop("db")
        self.mbdb = kwargs.pop("mbdb")
        gcmds = globalcommands.GlobalCMDS(bot=self)
        func_checks = (self.check_blacklist, self.disable_dm_exec, context.redirect)
        for func in func_checks:
            self.add_check(func)
        cogs = [filename[:-3] for filename in os.listdir('./cogs') if filename.endswith(".py")]
        for cog in sorted(cogs):
            self.load_extension(f'cogs.{cog}')
            print(f"Cog \"{cog}\" has been loaded")
        self.loop.create_task(self.init_counters())
        self.loop.create_task(self.all_loaded())
        self.loop.create_task(self._init_guilds())

    async def _init_guilds(self):
        await self.wait_until_ready()
        async with self.db.acquire() as con:
            for guild in self.guilds:
                await con.execute(f"INSERT INTO guild(guild_id) VALUES ({guild.id}) ON CONFLICT DO NOTHING")

    async def init_counters(self):
        await self.wait_until_ready()
        async with self.db.acquire() as con:
            values = "('" + "', 0), ('".join(command.name for command in self.commands) + "', 0)"
            names = "'{\"" + '", "'.join(command.name for command in self.commands) + "\"}'"
            await con.execute(f"INSERT INTO global_counters(command, amount) VALUES {values} ON CONFLICT DO NOTHING")
            await con.execute(f"DELETE FROM global_counters WHERE command != ALL({names}::text[])")
            await con.execute(f"DELETE FROM guild_counters WHERE command != ALL({names}::text[])")
        return

    async def on_command_completion(self, ctx):
        async with self.db.acquire() as con:
            command = ctx.command.root_parent.name.lower() if ctx.command.parent else ctx.command.name.lower()
            await con.execute(f"INSERT INTO global_counters(command, amount) VALUES ($tag${command}$tag$, 1) "
                              f"ON CONFLICT (command) DO UPDATE SET amount=global_counters.amount+1 "
                              f"WHERE global_counters.command=$tag${command}$tag$")
            if ctx.guild:
                entry = await con.fetchval(f"SELECT amount FROM guild_counters "
                                           f"WHERE guild_id={ctx.guild.id} AND command=$tag${command}$tag$")
                if not entry:
                    await con.execute(f"INSERT INTO guild_counters(guild_id, command, amount) "
                                      f"VALUES ({ctx.guild.id}, $tag${command}$tag$, 1)")
                else:
                    await con.execute(f"UPDATE guild_counters SET amount=amount+1 "
                                      f"WHERE guild_id={ctx.guild.id} AND command=$tag${command}$tag$")
        return

    @tasks.loop(seconds=120)
    async def status(self):
        await self.wait_until_ready()
        at = await self.get_aliases()
        activity1 = discord.Activity(name="m!h for help!", type=discord.ActivityType.listening)
        activity2 = discord.Activity(name=f"{len(self.users)} users!", type=discord.ActivityType.watching)
        activity3 = discord.Activity(name=f"{len(self.guilds)} servers!", type=discord.ActivityType.watching)
        activity4 = discord.Activity(name=f"USB {gcmds.version}", type=discord.ActivityType.playing)
        activity5 = discord.Activity(name=f"{len(self.commands)} commands & {at} aliases",
                                     type=discord.ActivityType.listening)
        activity = itertools.cycle([activity1, activity2, activity3, activity4, activity5])
        await self.change_presence(status=discord.Status.online, activity=next(activity))

    async def on_message(self, message):
        await self.wait_until_ready()
        if await self.check_locks(message) and await self.check_gatherers(message):
            await self.process_commands(message)

    async def check_locks(self, message):
        await self.wait_until_ready()
        if not message.guild:
            return True
        async with self.db.acquire() as con:
            try_ae = await con.fetchval(f"SELECT channel_id FROM locks WHERE guild_id={message.guild.id} AND type='all_except'")
            if not try_ae:
                lock_type = await con.fetchval(f"SELECT type FROM locks WHERE channel_id={message.channel.id}")
                if lock_type and lock_type != "unlocked":
                    return False
                else:
                    return True
            else:
                if int(try_ae) == message.channel.id:
                    return True
                else:
                    lock_type = await con.fetchval(f"SELECT type FROM locks WHERE channel_id={message.channel.id}")
                    if not lock_type or lock_type != "unlocked":
                        return False
                    else:
                        return True

    async def check_gatherers(self, message: discord.Message) -> bool:
        await self.wait_until_ready()
        if not message.guild:
            return True
        async with self.db.acquire() as con:
            res = await con.fetchval(
                f"SELECT channel_id FROM gather WHERE channel_id={message.channel.id}",
            )
        return not bool(res)

    async def disable_dm_exec(self, ctx):
        if not ctx.guild and (ctx.cog.qualified_name in DISABLED_COGS or ctx.command.name in DISABLED_COMMANDS):
            disabled = discord.Embed(title="Command Disabled in Non Server Channels",
                                     description=f"{ctx.author.mention}, `m!{ctx.invoked_with}` can only be accessed "
                                     f"in a server",
                                     color=discord.Color.dark_red())
            await ctx.channel.send(embed=disabled)
            return False
        else:
            return True

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Missing Required Argument",
                    description=f"{ctx.author.mention}, `[{error.param.name}]` is a required argument",
                    color=discord.Color.dark_red(),
                )
            )
        elif isinstance(error, commands.MissingPermissions):
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Insufficient User Permissions",
                    description=f"{ctx.author.mention}, to execute this command, you need "
                    f"`{'` `'.join(error.missing_perms).replace('_', ' ').title()}`",
                    color=discord.Color.dark_red()
                )
            )
        elif isinstance(error, commands.BotMissingPermissions):
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Insufficient Bot Permissions",
                    description=f"{ctx.author.mention}, to execute this command, I need "
                    f"`{'` `'.join(error.missing_perms).replace('_', ' ').title()}`",
                    color=discord.Color.dark_red()
                )
            )
        elif isinstance(error, commands.MemberNotFound):
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Member Not Found",
                    description=f"{ctx.author.mention}, I couldn't find a member with the name `{error.argument}`",
                    color=discord.Color.dark_red(),
                )
            )
        elif isinstance(error, commands.NotOwner):
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Insufficient User Permissions",
                    description=f"{ctx.author.mention}, only the bot owner is authorised to use this "
                    f"command",
                    color=discord.Color.dark_red(),
                )
            )
        elif isinstance(error, commands.CommandOnCooldown):
            cooldown_time_truncated = gcmds.truncate(error.retry_after, 3)
            if cooldown_time_truncated < 1:
                cooldown_time_truncated *= 1000
            spell = "milliseconds" if cooldown_time_truncated < 1 else "seconds"
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Command on Cooldown",
                    description=f"{ctx.author.mention}, this command is still on cooldown for {cooldown_time_truncated} {spell}",
                    color=discord.Color.dark_red(),
                )
            )
        elif hasattr(error, "original"):
            if isinstance(error.original, NodeException):
                return await ctx.channel.send(
                    embed=discord.Embed(
                        title="Music Error",
                        description="NodeException: " + str(error.original),
                        color=discord.Color.dark_red(),
                    )
                )
            elif isinstance(error.original, discord.Forbidden):
                return await ctx.channel.send(
                    embed=discord.Embed(
                        title="Forbidden",
                        description=f"{ctx.author.mention}, I cannot execute this command because I lack "
                        f"the permissions to do so, or my role is lower in the hierarchy.",
                        color=discord.Color.dark_red(),
                    )
                )
            else:
                raise error
        elif isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.CommandNotFound):
            pass
        else:
            try:
                return await ctx.channel.send(embed=error.embed)
            except Exception:
                raise error

    async def on_guild_join(self, guild):
        async with self.db.acquire() as con:
            await con.execute(f"INSERT INTO guild (guild_id, custom_prefix) VALUES ({guild.id}, 'm!')"
                              " ON CONFLICT DO NOTHING")
            await con.execute(f"INSERT INTO logging(guild_id) VALUES ({guild.id}) ON CONFLICT DO NOTHING")

    async def on_member_join(self, member: discord.Member):
        async with self.db.acquire() as con:
            if member.bot:
                result = await con.fetch(f"SELECT role_id FROM autoroles WHERE guild_id={member.guild.id} AND type='bot'")
            else:
                result = await con.fetch(f"SELECT role_id FROM autoroles WHERE guild_id={member.guild.id} AND type='member'")
        if not result:
            return
        else:
            for item in result:
                try:
                    await member.add_roles(member.guild.get_role(int(item['role_id'])), reason=f"Given member {member.display_name} roles from set autoroles")
                except Exception:
                    pass
        return

    async def all_loaded(self):
        await self.wait_until_ready()
        globalcommands.start_time = int(datetime.now().timestamp())
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        users = len(self.users)
        guilds = len(self.guilds)
        ct = len(self.commands)
        at = await self.get_aliases()
        print(f'Successfully logged in as {self.user}\nIP: {ip}\nHost: {str(hostname)}\nServing '
              f'{users} users across {guilds} servers\nCommands: {ct}\nAliases: {at}\n{version}')
        self.status.start()

    async def get_aliases(self):
        return len([alias for command in self.commands for alias in command.aliases if command.aliases])


uptime = int(datetime.now().timestamp())
loop.run_until_complete(run(uptime))
