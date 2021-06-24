import asyncio
import os
import random
import typing
from datetime import datetime, timedelta
from typing import List, Optional, Union

import discord
from discord.ext import commands, tasks
from discord.ext.commands import AutoShardedBot, Context
from setuppanel import SetupPanel
from utils import GlobalCMDS


class Moderation(commands.Cog):

    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self.tasks: List[asyncio.Task] = []
        self.bot.loop.create_task(self.setup_tables())

    def cog_unload(self):
        for task in self.tasks:
            task.cancel()
        self.check_mute_expire.cancel()

    async def setup_tables(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS mutes(id SERIAL PRIMARY KEY, guild_id bigint, user_id bigint, "
                              "time NUMERIC DEFAULT NULL)")
            await con.execute("CREATE TABLE IF NOT EXISTS warns(id SERIAL PRIMARY KEY, guild_id bigint, user_id bigint,"
                              " moderator bigint, reason text, timestamp NUMERIC)")
        self.check_mute_expire.start()

    @tasks.loop(seconds=60)
    async def check_mute_expire(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            result = await con.fetch("SELECT guild_id, user_id, time FROM mutes WHERE time IS NOT NULL")
        if not result:
            return

        for info in result:
            user_id = info['user_id']
            guild_id = info['guild_id']
            current_time = int(datetime.now().timestamp())
            time = int(info['time'])
            sleep_time = int(time - current_time)
            if sleep_time <= 60 and not any(task.get_name() == f"{guild_id}{user_id}" for task in self.tasks):
                task = self.bot.loop.create_task(
                    self.unmute_user(int(guild_id), int(user_id), sleep_time)
                )
                task.add_done_callback(self._handle_task_result)
                self.tasks.append(task)

    @staticmethod
    def _handle_task_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except (Exception, asyncio.CancelledError):
            pass
        return

    @staticmethod
    async def set_overwrites(ctx: Context, channel: discord.abc.GuildChannel, role: discord.Role, overwrite: discord.PermissionOverwrite):
        try:
            await channel.set_permissions(role, overwrite=overwrite)
        except Exception:
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Cannot Set Permission Overwrites",
                    description=f"{ctx.author.mention}, I cannot set the `Send Message` overwrite for channels in this server for the role {role.mention}",
                    color=discord.Color.dark_red(),
                )
            )

    @staticmethod
    def _convert_to_timestamp(timestamp: str) -> Union[int, None]:
        try:
            ret = [int(_) for _ in timestamp.split(":", maxsplit=3)]
            return int(datetime.now().timestamp()) + int(sum(item * (60 ** (len(ret) - index)) * ((24 / 60) if len(ret) - index == 3 else 1) for index, item in enumerate(ret, 1)))
        except (TypeError, ValueError):
            return None

    async def _config_mutes(self, ctx: Context) -> discord.Role:
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not role:
            role = await ctx.guild.create_role(name="Muted",
                                               reason="Use for mutes")
            for channel in ctx.guild.channels:
                task = self.bot.loop.create_task(
                    self.set_overwrites(
                        ctx, channel, role, discord.PermissionOverwrite(send_messages=False)
                    )
                )
                task.add_done_callback(self._handle_task_result)
        return role

    async def unmute_user(self, guild_id: int, user_id: int, sleep_time: int):
        await asyncio.sleep(sleep_time)
        guild = self.bot.get_guild(guild_id)
        role = discord.utils.get(guild.roles, name="Muted")
        if role:
            member = guild.get_member(user_id)
            if role in member.roles:
                await member.remove_roles(role)
                embed = discord.Embed(title="Your Mute Expired",
                                      description=f"{member.mention}, your mute has expired in {guild.name}. Please avoid "
                                      "doing what you were doing to get muted",
                                      color=discord.Color.blue())
                try:
                    await member.send(embed=embed)
                except (discord.HTTPError, discord.Forbidden):
                    pass
            async with self.bot.db.acquire() as con:
                await con.execute(f"DELETE FROM mutes WHERE user_id={user_id} AND guild_id={guild_id}")
        return

    async def set_mute(self, ctx, member: discord.Member, time: int = None):
        if not time:
            op = f"INSERT INTO mutes(guild_id, user_id) VALUES({ctx.guild.id}, {member.id})"
        else:
            op = f"INSERT INTO mutes(guild_id, user_id, time) VALUES({ctx.guild.id}, {member.id}, {time})"
            sleep_time = time - int(datetime.now().timestamp())
            if sleep_time <= 60 and not any(task.get_name() == f"{ctx.guild.id}{member.id}" for task in self.tasks):
                task = self.bot.loop.create_task(
                    self.unmute_user(ctx.guild.id, member.id, sleep_time)
                )
                task.set_name(f"{ctx.guild.id}{member.id}")
                task.add_done_callback(self._handle_task_result)
                self.tasks.append(task)
        async with self.bot.db.acquire() as con:
            await con.execute(f"DELETE FROM mutes WHERE guild_id={ctx.guild.id} AND user_id={member.id}")
            await con.execute(op)

    @commands.command(aliases=['clear', 'clean', 'chatclear', 'cleanchat', 'clearchat', 'purge'],
                      desc="Mass clear chat",
                      usage="chatclean (amount) (@member)",
                      uperms=["Manage Messages"],
                      bperms=["Manage Messages"],
                      note="If `(amount)` is not specified, it defaults to 1")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def chatclean(self, ctx, amount: Optional[int] = 1, member: discord.Member = None):
        if amount >= 1:
            deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author == member if member else True)
            embed = discord.Embed(
                title="Cleared Chat",
                description=f"Cleared {len(deleted)} message{'s' if len(deleted) != 1 else ''}",
                color=discord.Color.blue(),
            ).set_thumbnail(
                url="https://cdn.discordapp.com/attachments/734962101432615006/734962158290468944/eraser.png"
            )
        else:
            embed = discord.Embed(
                title="Invalid Amount",
                description=f"{ctx.author.mention}, the amount must be at least 1",
                color=discord.Color.dark_red(),
            )
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['silence', 'stfu', 'shut', 'shush', 'shh', 'shhh', 'shhhh', 'quiet'],
                      desc="Mutes members from all text channels",
                      usage="mute [@member]*va (reason)",
                      uperms=["Manage Roles"],
                      bperms=["Manage Roles"],
                      note="Using this command creates a role called \"Muted\" that restricts the ability "
                      "for members to send messages in all channels. Any overrides to this role may cause this "
                      "command to not function as planned. Please do not modify the automatically created role."
                      "You may specify a time or duration the mute should expire by providing it in the `(reason)`. "
                      "If `(reason)` is unspecified, it defaults to \"unspecified\" and the member is muted indefinitely")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, members: commands.Greedy[discord.Member], *, reason: str = "Unspecified"):
        role = await self._config_mutes(ctx)
        ret = await SetupPanel(
            bot=self.bot,
            ctx=ctx,
            title="Mute",
        ).add_step(
            name="content",
            embed=discord.Embed(
                title="Mute Duration",
                description=f"{ctx.author.mention}, please enter the duration you would like this mute to last. "
                "You may specify a time in DD:HH:MM:SS, HH:MM:SS, MM:SS, or SS format. To mute indefinitely, "
                "enter \"none\"",
                color=discord.Color.blue(),
            ),
            timeout=60,
        )()
        current = int(datetime.now().timestamp())
        timestamp = self._convert_to_timestamp(ret[0]) if ret[0] else None
        embed = discord.Embed(color=discord.Color.blue())
        success = []
        failed = []
        for member in members:
            if role in member.roles:
                failed.append(member)
            else:
                await member.add_roles(role)
                success.append(member)
                await self.set_mute(ctx, member, timestamp)
        if success:
            embed.add_field(
                name="Members Muted",
                value="\n".join(member.mention for member in success)
            )
        if failed:
            embed.add_field(
                name="Unable to Mute",
                value="\n".join(member.mention for member in failed)
            )
        if timestamp:
            embed.add_field(
                name="Expires In",
                value=str(timedelta(seconds=timestamp - current)),
                inline=False,
            )
        embed.add_field(
            name="Reason",
            value=f"```{reason}```",
            inline=False,
        )
        path = './assets/muted'
        name = random.choice(os.listdir(path))
        directory = f'{path}/{name}'
        with open(directory, 'rb') as image:
            picture = discord.File(fp=image, filename=name)
        return await ctx.channel.send(embed=embed.set_thumbnail(url=f"attachment://{name}"), file=picture)

    @commands.command(aliases=['unsilence', 'unstfu', 'unshut', 'unshush', 'unshh', 'unshhh', 'unshhhh', 'unquiet'],
                      desc="Unmutes members from all text channels",
                      usage="unmute [@member]*va (reason)",
                      uperms=["Manage Roles"],
                      bperms=["Manage Roles"],
                      note="This command removes the \"Muted\" role from the specified users, making "
                      "them able to chat in all channels again. Modifications to the role may cause the command "
                      "to not function properly, so please do not modify the automatically generated role in mute."
                      " If `(reason)` is unspecified, it defaults to \"unspecified\"")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, members: commands.Greedy[discord.Member], *, reason="Unspecified"):
        embed = discord.Embed(
            color=discord.Color.dark_red(),
        )
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not role:
            embed.title = "No Muted Role"
            embed.description = f"{ctx.author.mention}, there is no muted role on this server"
        else:
            success = []
            failed = []
            for member in members:
                if not role in member.roles:
                    failed.append(member)
                else:
                    success.append(member)
                    async with self.bot.db.acquire() as con:
                        await con.execute(f"DELETE FROM mutes WHERE user_id={member.id} AND guild_id={ctx.guild.id}")
                    await member.remove_roles(role)
            if success:
                embed.add_field(
                    name=f"Member{'s' if len(success) != 1 else ''} Unmuted",
                    value="\n".join(member.mention for member in success),
                )
                embed.color = discord.Color.blue()
            if failed:
                embed.add_field(
                    name="Unmute Failed For",
                    value="\n".join(member.mention for member in failed),
                )
            embed.add_field(
                name="Reason",
                value=f"```{reason}```",
                inline=False
            )
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Kick members from the server",
                      usage="kick [@member]*va (reason)",
                      uperms=["Kick Members"],
                      bperms=["Kick Members"])
    @commands.bot_has_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, members: commands.Greedy[discord.Member], *, reason='Unspecified'):
        embed = discord.Embed(
            title="Kick Successful",
            color=discord.Color.blue()
        ).add_field(
            name="Members Kicked",
            value="\n".join(member.mention for member in members),
            inline=False,
        ).add_field(
            name="Reason",
            value=f"```{reason}```",
            inline=False,
        )
        for member in members:
            await member.kick(reason=reason)
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["yeet", "cya", "begone"],
                      desc="Bans members from the server",
                      usage="ban [@member]*va (message_delete_days) (reason)",
                      uperms=["Ban Members"],
                      bperms=["Ban Members"],
                      note="If unspecified, `(message_delete_days)` and `(reason)` default to 0 and \"unspecified\" respectively")
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, members: commands.Greedy[discord.Member], days: typing.Optional[int] = 0, *, reason='Unspecified'):
        for member in members:
            await member.ban(delete_message_days=days, reason=reason)
        embed = discord.Embed(
            title="Ban Successful",
            color=discord.Color.blue(),
        ).add_field(
            name="Members Banned",
            value="\n".join(member.mention for member in members),
            inline=False,
        ).add_field(
            name='Reason:',
            value=f"```{reason}```",
            inline=False,
        ).add_field(
            name="Messages Deleted",
            value=f"Deleted messages from the past {days} day{'s' if days != 1 else ''}",
            inline=False,
        )
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Unbans users that are banned",
                      usage="unban [user]*va (reason)",
                      uperms=["Ban Members"],
                      bperms=["Ban Members"],
                      note="Since those `[user]` aren't in your server anymore, you can specify by "
                      "username and discriminator and the bot will attempt to identify which users you are "
                      "referring to and unban them if found. If `(reason)` is unspecified, it defaults to \"unspecified\"")
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: Context, users: commands.Greedy[discord.User], *, reason: str = "Unspecified"):
        success = []
        failed = []
        for user in users:
            try:
                await ctx.guild.fetch_ban(user)
            except discord.NotFound:
                failed.append(user)
            else:
                await ctx.guild.unban(user, reason=reason)
                success.append(user)
        if not success and failed:
            embed = discord.Embed(
                title="Unban Failed",
                description=f"{ctx.author.mention}, the specified members are already unbanned",
                color=discord.Color.dark_red(),
            )
        else:
            embed = discord.Embed(
                title="Unban Successful",
                color=discord.Color.blue(),
            ).add_field(
                name="Members Unbanned",
                value="\n".join(user.mention for user in success),
                inline=False,
            )
            if failed:
                embed.add_field(
                    name="Unable to Unban",
                    value="\n".join(user.mention for user in failed),
                    inline=False,
                )
        return await ctx.channel.send(embed=embed)

    # @commands.command(desc="Administers warns for certain users",
    #                  usage="warn [@member]*va (reason)",
    #                  uperms=["Ban Members"],
    #                  bperms=["Ban Members"],
    #                  note="If enabled, the automod actions will take place upon warns based on "
    #                  "the warn count for each member")
    # @commands.has_permissions(ban_members=True)
    # @commands.bot_has_permissions(ban_members=True)
    # async def warn(self, ctx, members: commands.Greedy[discord.Member], *, reason="Unspecified"):
    #    pass
    #
    # @commands.command(desc="Toggle the automod function for warns",
    #                  usage="automod",
    #                  uperms=["Ban Members"],
    #                  note="**Actions:**\n1st Warn: Nothing\n2nd Warn: 10 minute mute\n3rd Warn: Kick\n4th Warn: Ban")
    # @commands.has_permissions(ban_members=True)
    # async def automod(self, ctx):
    #    pass
    #
    # @commands.command(aliases=['offenses'],
    #                  desc="Lists warns to a given member or warns you have given",
    #                  usage="offense (@member)",
    #                  note="If `(member)` is unspecified, it will display all the warnings you have "
    #                  "given to other members")
    # async def offense(self, ctx, member: discord.Member = None):
    #    pass
    #
    # @commands.command(desc="Expunge warns from a member",
    #                  usage="expunge [@member]",
    #                  uperms=["Ban Members"],
    #                  bperms=["Ban Members"])
    # @commands.has_permissions(ban_members=True)
    # @commands.bot_has_permissions(ban_members=True)
    # async def expunge(self, ctx, member: discord.Member = None):
    #    pass


def setup(bot):
    bot.add_cog(Moderation(bot))
