import asyncio
import datetime
import functools
import json
from typing import Callable, List, Tuple

import discord
from discord.ext import commands
from discord.ext.commands import AutoShardedBot, Context
from setuppanel import SetupPanel
from utils import EmbedPaginator, GlobalCMDS, SubcommandHelp

_CONF = ["✅", "❌"]


def validate_channel():
    def wrapper(func: Callable):
        @functools.wraps(func)
        async def deco(self: commands.Cog, ctx: Context, channel: discord.TextChannel):
            async with self.bot.db.acquire() as con:
                res = await con.fetchval(
                    f"SELECT channel_id FROM gather WHERE channel_id={channel.id}"
                )
            if ctx.command.name == "create":
                if res:
                    return await ctx.channel.send(
                        embed=discord.Embed(
                            title="Gatherer Already Exists",
                            description=f"{ctx.author.mention}, a gatherer already exists for the channel {channel.mention}. "
                            "Please select a different channel",
                            color=discord.Color.dark_red(),
                        )
                    )
                perms = channel.permissions_for(ctx.guild.me)
                if not perms.send_messages and perms.manage_messages:
                    return await ctx.channel.send(
                        embed=discord.Embed(
                            title="Insufficient Permissions",
                            description=f"{ctx.author.mention}, I require the `Send Messages` and `Manage Messages` "
                            f"to create a gatherer in {channel.mention}",
                            colr=discord.Color.dark_red(),
                        )
                    )
                return await func(self, ctx, channel)
            elif ctx.command.name in ["expire", "delete", "peek"]:
                if not res:
                    return await ctx.channel.send(
                        embed=discord.Embed(
                            title="No Gatherer Exists",
                            description=f"{ctx.author.mention}, no gatherer exists for the channel {channel.mention}. "
                            "Please select a different channel",
                            color=discord.Color.dark_red(),
                        )
                    )
                return await func(self, ctx, channel)
        return deco
    return wrapper


def cleanup_task():
    def wrapper(func: Callable):
        @functools.wraps(func)
        async def deco(self: commands.Cog, channel_id: int, *args, **kwargs):
            tasks = [task for task in self._tasks if task.get_name() == str(channel_id)]
            if tasks:
                tasks[0].cancel()
            return await func(self, channel_id, *args, **kwargs)
        return deco
    return wrapper


class Gather(commands.Cog):
    def __init__(self, bot: AutoShardedBot) -> None:
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self._tasks: List[asyncio.Task] = []
        self.bot.loop.create_task(self._init_table())

    @staticmethod
    def _handle_task_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _validate_timestamp(timestamp: str, convert: bool = False) -> bool:
        try:
            ret = [int(_) for _ in timestamp.split(":", maxsplit=3)]
        except (TypeError, ValueError):
            return [] if convert else False
        if convert:
            return int(sum(item * (60 ** (len(ret) - index)) * ((24 / 60) if len(ret) - index == 3 else 1) for index, item in enumerate(ret, 1)))
        return bool(ret)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        context = await self.bot.get_context(message)
        if not context.valid and message.guild:
            async with self.bot.db.acquire() as con:
                data = await con.fetch(
                    f"SELECT channel_id, message_id, entries FROM gather WHERE channel_id={message.channel.id}",
                )
                if data:
                    channel_id, message_id, entries = data[0]["channel_id"], data[0]["message_id"], data[0]["entries"]
                    if entries is not None and not message.content in entries and len(message.content) <= 144 and not message.author.bot:
                        entries.append(message.content)
                        payload = json.dumps({
                            "user_id": message.author.id,
                            "content": message.content,
                        })
                        await con.execute(
                            f"UPDATE gather SET entries=array_append(entries, $text${payload}$text$) WHERE channel_id={channel_id}"
                        )
                        channel: discord.TextChannel = self.bot.get_channel(channel_id)
                        gather_message = await channel.fetch_message(message_id)
                        embed: discord.Embed = gather_message.embeds[0]
                        await gather_message.edit(
                            embed=embed.set_footer(
                                text="This gatherer is accepting responses. To enter a response, "
                                "simply type into this channel. Note that duplicate responses will "
                                f"not be counted\n\nReceived {len(entries)} response{'s' if len(entries) != 1 else ''} so far..."
                            )
                        )
                    await self.gcmds.smart_delete(message)
        return

    def cog_unload(self):
        for task in self._tasks:
            task.cancel()

    async def _init_table(self) -> None:
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute(
                "CREATE TABLE IF NOT EXISTS gather(guild_id BIGINT, channel_id BIGINT PRIMARY KEY, "
                "message_id BIGINT, expire_at NUMERIC, entries TEXT[] DEFAULT NULL, anonymous BOOLEAN DEFAULT FALSE)"
            )
        task = self.bot.loop.create_task(self._check_expiry())
        task.add_done_callback(self._handle_task_result)
        self._tasks.append(task)

    async def _check_expiry(self) -> None:
        while True:
            async with self.bot.db.acquire() as con:
                entries = await con.fetch(
                    f"SELECT channel_id, expire_at FROM gather"
                )
            now = int(datetime.datetime.now().timestamp())
            for entry in entries:
                channel_id, expire_at = entry["channel_id"], entry["expire_at"]
                if now + 60 >= expire_at:
                    task = self.bot.loop.create_task(
                        self._wrapper(
                            channel_id, delay=expire_at - now
                        )
                    )
                    task.add_done_callback(self._handle_task_result)
                    self._tasks.append(task)
            await asyncio.sleep(60)

    async def _wrapper(self, channel_id: int, delay: int = 0) -> None:
        await asyncio.sleep(delay)
        return await self._expire(channel_id, send_embed=True)

    async def _show_all_gatherers(self, ctx: Context) -> discord.Message:
        async with self.bot.db.acquire() as con:
            gatherers = await con.fetch(
                f"SELECT * FROM gather WHERE guild_id={ctx.guild.id}"
            )
        if gatherers:
            entries = [
                "\n".join([
                    f"**Gatherer {index}:**",
                    f"> Channel: <#{entry['channel_id']}>",
                    f"> Expires At: {datetime.datetime.fromtimestamp(entry['expire_at']).strftime('%m/%d/%Y %H:%M:%S')}",
                    f"> Anonymous: {_CONF[0 if entry['anonymous'] else 1]}",
                ])
                for index, entry in enumerate(gatherers, 1)
            ]
            return await EmbedPaginator(
                ctx,
                entries=entries,
                per_page=10,
                show_index=False,
            ).paginate()
        return await ctx.channel.send(
            embed=discord.Embed(
                title="No Active Gatherers",
                description=f"{ctx.author.mention}, there are no active gatherers set on this server",
                color=discord.Color.blue(),
            )
        )

    async def _create_gatherer(self, ctx: Context, channel: discord.TextChannel,
                               title: str, description: str,
                               color: discord.Color, timestamp: int,
                               anonymous: bool):
        expire_at = int(datetime.datetime.now().timestamp()) + timestamp
        message = await channel.send(
            embed=discord.Embed(
                title=title,
                description=description,
                color=color,
            ).set_footer(
                text="This gatherer is accepting responses. To enter a response, "
                "simply type into this channel. Note that duplicate responses will "
                "not be counted\n\nReceived 0 responses so far..."
            )
        )
        async with self.bot.db.acquire() as con:
            await con.execute(
                "INSERT INTO gather(guild_id, channel_id, message_id, expire_at, entries, anonymous) VALUES "
                f"({ctx.guild.id}, {channel.id}, {message.id}, {expire_at}, '{'{}'}', {anonymous})"
            )
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Gatherer Successfully Created",
                description=f"{ctx.author.mention}, your gatherer has been created in {channel.mention}, and "
                "will add all messages sent to that channel into its list",
                color=discord.Color.blue(),
            ).set_footer(
                text="Please note that while this gatherer is active, all incoming messages will be deleted and "
                "command invocations will be ignored",
            )
        )

    async def _conf_op(self, ctx: Context, channel: discord.TextChannel, *, op: str) -> discord.Message:
        message: discord.Message = await ctx.channel.send(
            embed=discord.Embed(
                title="Confirmation",
                description=f"{ctx.author.mention}, react with {_CONF[0]} to {op} the gatherer "
                f"or {_CONF[1]} to cancel",
                color=discord.Color.blue(),
            )
        )
        for reaction in _CONF:
            await message.add_reaction(reaction)
        try:
            reaction, _ = await self.bot.wait_for(
                "reaction_add",
                check=lambda r, u: str(r.emoji) in _CONF and r.message.id == message.id and u.id == ctx.author.id,
                timeout=60,
            )
        except asyncio.TimeoutError:
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Confirmation Timed Out",
                    description=f"{ctx.author.mention}, you did not react within the time limit. No "
                    "changes have been made",
                    color=discord.Color.dark_red(),
                )
            )
        if str(reaction.emoji) == _CONF[0]:
            await ctx.channel.send(
                embed=discord.Embed(
                    title=f"Gatherer {op.title()}d",
                    description=f"{ctx.author.mention}, the gatherer in {channel.mention} has been forcefully {op}d",
                    color=discord.Color.blue(),
                )
            )
            return await getattr(self, f"_{op}_gatherer")(channel.id, send_embed=True, ctx=ctx)
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Gatherer Not Expired",
                description=f"{ctx.author.mention}, the gatherer in {channel.mention} was not forcefully {op}d",
                color=discord.Color.blue(),
            )
        )

    async def _expire(self, channel_id: int, send_embed: bool = False) -> None:
        async with self.bot.db.acquire() as con:
            data = await con.fetch(
                f"DELETE FROM gather WHERE channel_id={channel_id} RETURNING entries, anonymous"
            )
        if send_embed:
            channel: discord.TextChannel = self.bot.get_channel(channel_id)
            embed = discord.Embed(
                title="Gatherer Results",
                description="These are the results of the gatherer:\n",
                color=discord.Color.blue(),
            )
            anonymous, entries = data[0]["anonymous"], data[0]["entries"]
            for index, entry in enumerate(entries, 1):
                try:
                    payload = json.loads(entry)
                    val = f"{payload['content']}" + str(f" - <@{payload['user_id']}>" if not anonymous else "")
                except json.JSONDecodeError:
                    val = entry
                _desc = f"\n**{index}:** {val}"
                if len(embed.description) + len(_desc) > 2000:
                    await channel.send(embed=embed)
                    embed = discord.Embed(description="", color=discord.Color.blue())
                embed.description += _desc
            await channel.send(embed=embed)
        return

    @cleanup_task()
    async def _expire_gatherer(self, channel_id: int, send_embed: bool = False, **kwargs) -> None:
        return await self._expire(channel_id, send_embed=send_embed)

    @cleanup_task()
    async def _delete_gatherer(self, channel_id: int, *, send_embed: bool, ctx: Context) -> None:
        async with self.bot.db.acquire() as con:
            message_id = await con.fetchval(
                f"DELETE FROM gather WHERE channel_id={channel_id} RETURNING message_id"
            )
            channel: discord.TextChannel = self.bot.get_channel(channel_id)
            message = await channel.fetch_message(message_id)
            await self.gcmds.smart_delete(message)
            await channel.send(
                embed=discord.Embed(
                    title="Gatherer Deleted",
                    description="The gatherer for this channel has been deleted. Results will not be shown",
                    color=discord.Color.dark_red(),
                )
            )
        return

    @commands.group(invoke_without_command=True,
                    aliases=["gthr", "gatherer"],
                    desc="Shows the help for gather commands",
                    usage="gather (subcommand)")
    async def gather(self, ctx: Context):
        pfx = f"{await self.gcmds.prefix(ctx)}gather"
        return await SubcommandHelp(
            pfx=pfx,
            title="Gather Help",
            description="UconnSmashBot's gather command functions similar to a poll, except it allows users "
            "to enter short-answer responses and accumulates them to be revealed upon the gatherer expiring. "
            f"The base command is `{pfx}`. Here are all valid subcommands",
            per_page=3,
        ).from_config("gather").show_help(ctx)

    @gather.command(name="create",
                    aliases=["set"])
    @commands.has_permissions(manage_guild=True,)
    @validate_channel()
    async def gather_create(self, ctx: Context, channel: discord.TextChannel):
        _ET = "Gatherer Setup"
        _EC = discord.Color.blue()
        _FT = "Enter \"cancel\" to cancel setup"
        _BC = lambda m: m.content == "cancel"
        sp = SetupPanel(
            bot=self.bot,
            ctx=ctx,
            title="Gatherer",
        ).add_step(
            name="title",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, what should the title of the "
                "gatherer embed be?",
                color=_EC,
            ).set_footer(
                text=_FT,
            ),
            timeout=300,
            break_check=_BC,
        ).add_step(
            name="description",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, what should the description "
                "of the gatherer embed be?",
                color=_EC,
            ).set_footer(
                text=_FT,
            ),
            timeout=300,
            break_check=_BC,
        ).add_step(
            name="color",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, what hex color should the embed "
                "be?",
                color=_EC,
            ).set_footer(
                text=_FT,
            ),
            timeout=300,
            break_check=_BC,
        ).add_step(
            name="message",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, in how long should this gatherer expire? "
                "Enter a time in the following formats: " +
                ", ".join([
                    "DD:HH:MM:SS",
                    "HH:MM:SS",
                    "MM:SS",
                    "SS",
                ]),
                color=_EC,
            ).set_footer(
                text=_FT,
            ),
            timeout=300,
            predicate=lambda m: m.author.id == ctx.author.id and (
                m.content == "cancel" or self._validate_timestamp(m.content)
            ),
            break_check=_BC,
        ).add_step(
            name="message",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, would you like this gatherer's results "
                "to be anonymous? If so, enter \"yes\" or \"y\", otherwise the user will be "
                "displayed next to their response content",
                color=_EC,
            ).set_footer(
                text=_FT,
            ),
            timeout=300,
            break_check=_BC,
        )
        res: Tuple[str, str, discord.Color, str, str] = await sp.start()
        if res:
            title, description, color, timestamp, anonymous = res
            timestamp = self._validate_timestamp(timestamp, convert=True)
            anonymous = True if anonymous.lower() in ["y", "yes"] else False
            return await self._create_gatherer(ctx, channel, title, description, color, timestamp, anonymous)

    @gather.command(name="expire",
                    aliases=["finish"])
    @commands.has_permissions(manage_guild=True,)
    @validate_channel()
    async def gather_expire(self, ctx: Context, channel: discord.TextChannel):
        return await self._conf_op(ctx, channel, op="expire")

    @gather.command(name="delete",
                    aliases=["unset"])
    @commands.has_permissions(manage_guild=True,)
    @validate_channel()
    async def gather_delete(self, ctx: Context, channel: discord.TextChannel):
        return await self._conf_op(ctx, channel, op="delete")

    @gather.command(name="list",
                    aliases=["ls", "show"])
    async def gather_list(self, ctx: Context):
        return await self._show_all_gatherers(ctx)

    @gather.command(name="peek",)
    @commands.has_permissions(manage_guild=True)
    @validate_channel()
    async def gather_peek(self, ctx: Context, channel: discord.TextChannel):
        async with self.bot.db.acquire() as con:
            data = await con.fetch(
                f"SELECT entries, anonymous FROM gather WHERE guild_id={ctx.guild.id} AND channel_id={channel.id}"
            )
        if data:
            anonymous = data[0]["anonymous"]
            entries = []
            for entry in data[0]["entries"]:
                try:
                    _data = json.loads(entry)
                    entries.append(
                        f"{_data['content']}" + str(f" - <@{_data['user_id']}>" if not anonymous else '')
                    )
                except json.JSONDecodeError:
                    entries.append(entry)
            return await EmbedPaginator(
                ctx,
                entries=entries,
                per_page=10,
                show_entry_count=True,
                embed=discord.Embed(
                    title="Responses to Gatherer",
                    color=discord.Color.blue(),
                ),
                description=f"{ctx.author.mention}, here are the responses for the gatherer "
                f"in {channel.mention} thus far:\n\n",
            ).paginate()
        return await ctx.channel.send(
            embed=discord.Embed(
                title="No Responses",
                description=f"{ctx.author.mention}, the gatherer in {channel.mention} has not received any responses",
                color=discord.Color.blue(),
            )
        )


def setup(bot: AutoShardedBot) -> None:
    bot.add_cog(Gather(bot))
