import asyncio
import base64
import os
import random
import typing
from datetime import datetime, timedelta, timezone

import discord
from dateparser.search import search_dates
from discord.ext import commands, tasks
from num2words import num2words
from utils import globalcommands

gcmds = globalcommands.GlobalCMDS()
auto_mute_duration = 600
auto_warn_actions = [None, None, "mute", "kick", "ban"]


class Moderation(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.tasks = []
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
            if sleep_time > 60:
                continue
            self.tasks.append(self.bot.loop.create_task(
                self.unmute_user(int(guild_id), int(user_id), sleep_time)))

    async def check_panel(self, panel: discord.Message) -> bool:
        try:
            if panel.id:
                return True
            else:
                return False
        except (discord.NotFound, discord.Forbidden, discord.HTTPError):
            return False

    async def end_setup(self, ctx, name: str, type: str) -> discord.Message:
        if type == "no_panel":
            description = "because the panel was deleted or could not be found"
        elif type == "cancel":
            description = ""
        embed = discord.Embed(title=f"{name.title()} Cancelled",
                              description=f"{ctx.author.mention}, your {name} request was cancelled {description}",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def timeout(self, ctx, name: str, timeout: int) -> discord.Message:
        embed = discord.Embed(title=f"{name.title()} Cancelled",
                              description=f"{ctx.author.mention}, {name} request timed out after {timeout} seconds",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def edit_panel(self, ctx, panel: discord.Message, title: str = None, description: str = None,
                         color: discord.Color = None) -> bool:
        if not await self.check_panel(panel):
            return False
        try:
            panel_embed = panel.embeds[0]
            if not title:
                title = panel_embed.title
            if not description:
                description = panel_embed.description
            if not color:
                color = panel_embed.color
            embed = discord.Embed(title=title,
                                  description=description,
                                  color=color)
            await panel.edit(embed=embed)
            return True
        except (discord.NotFound, discord.Forbidden, discord.HTTPError):
            return False

    async def unmute_user(self, guild_id: int, user_id: int, sleep_time: int):
        await asyncio.sleep(sleep_time)
        guild = self.bot.get_guild(guild_id)
        role = discord.utils.get(guild.roles, name="Muted")
        if not role:
            return
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
        try:
            async with self.bot.db.acquire() as con:
                result = await con.execute(f"DELETE FROM mutes WHERE user_id = {user_id} AND guild_id = {guild_id}")
        except Exception:
            pass

        return

    async def set_mute(self, ctx, member: discord.Member, time: int = None):
        if not time:
            op = f"INSERT INTO mutes(guild_id, user_id) VALUES({ctx.guild.id}, {member.id})"
        else:
            op = f"INSERT INTO mutes(guild_id, user_id, time) VALUES({ctx.guild.id}, {member.id}, {time})"
        async with self.bot.db.acquire() as con:
            await con.execute(f"DELETE FROM mutes WHERE guild_id = {ctx.guild.id} AND user_id = {member.id}")
            await con.execute(op)

    async def get_warns(self, ctx, members) -> list:
        warns = []
        async with self.bot.db.acquire() as con:
            for member in members:
                result = await con.fetch(f"SELECT * FROM warns WHERE user_id = {member.id} AND guild_id = {ctx.guild.id}")
                if not result:
                    warns.append((member, 0))
                else:
                    warns.append((member, len(result)))
        return warns

    async def remove_warn(self, ctx, member: discord.Member, index) -> bool:
        try:
            async with self.bot.db.acquire() as con:
                if isinstance(index, str):
                    await con.execute(f"DELETE FROM warns WHERE user_id = {member.id} AND guild_id = {ctx.guild.id}")
                else:
                    await con.fetch(f"DELETE FROM warns WHERE id={index}")
            return True
        except Exception:
            return False

    async def get_administered_warns(self, ctx, member: discord.Member = None) -> list:
        async with self.bot.db.acquire() as con:
            if member:
                result = await con.fetch(f"SELECT reason, timestamp, id from warns WHERE user_id = {member.id} AND guild_id = {ctx.guild.id} AND moderator = {ctx.author.id}")
                return [(base64.urlsafe_b64decode(str.encode(info['reason'])).decode("ascii"), info['timestamp'], info['id']) for info in result]
            else:
                result = await con.fetch(f"SELECT user_id, id FROM warns WHERE guild_id = {ctx.guild.id} AND moderator = {ctx.author.id}")
                return [(info['user_id'], info['id']) for info in result]

    async def auto_warn_action(self, ctx, member: discord.Member, reason: str, count: int, timestamp):
        count_adj = count + 1
        async with self.bot.db.acquire() as con:
            am_status = await con.fetchval(f"SELECT automod FROM guild WHERE guild_id={ctx.guild.id}")
        if am_status:
            action = auto_warn_actions[count_adj]
        else:
            action = None
        title = f"Warning from {ctx.author.display_name} in {ctx.guild.name}"
        ord_count = num2words((count_adj), to='ordinal_num')
        description = f"{member.mention}, this is your **{ord_count}** warning in {ctx.guild.name}\n\n**Reason:**\n{reason}"
        if not action:
            description += "\n\nThis is just a warning. Please do not do whatever you did to get you warned again"
        elif action == "mute":
            description += "\n\nYou have also been muted for 10 minutes as a consequence. You will be notified when " \
                "your mute expires"
            await self.set_mute(ctx, member, (int(auto_mute_duration) + int(timestamp)))
            role = discord.utils.get(ctx.guild.roles, name="Muted")
            if not role:
                role = await ctx.guild.create_role(name="Muted",
                                                   reason="Use for mutes")
                for channel in ctx.guild.channels:
                    await channel.set_permissions(role, send_messages=False)
            if not role in member.roles:
                await member.add_roles(role)
        elif action == "kick":
            description += f"\n\nYou have also been kicked from {ctx.guild.name}"
            try:
                await ctx.guild.kick(member, reason=reason)
            except discord.Forbidden:
                pass
        elif action == "ban":
            description += f"\n\nYou have also been banned from {ctx.guild.name}"
            try:
                await ctx.guild.ban(member, reason=reason)
            except discord.Forbidden:
                pass
        embed = discord.Embed(title=title,
                              description=description,
                              color=discord.Color.dark_red())
        embed.set_footer(text=(f"Warned by {ctx.author.display_name} at " + "{:%m/%d/%Y %H:%M:%S}".format(
            datetime.fromtimestamp(timestamp))), icon_url=ctx.author.avatar_url)
        try:
            await member.send(embed=embed)
        except Exception:
            pass

        embed.set_author(name=f"Warning sent to {member.display_name}", icon_url=member.avatar_url)
        await ctx.author.send(embed=embed)

        reason = str(base64.urlsafe_b64encode(reason.encode("ascii")), encoding="utf-8")

        async with self.bot.db.acquire() as con:
            await con.execute("INSERT INTO warns(guild_id, user_id, moderator, reason, timestamp) VALUES "
                              f"({ctx.guild.id}, {member.id}, {ctx.author.id}, '{reason}', {int(timestamp)})")

    @commands.command(aliases=['clear', 'clean', 'chatclear', 'cleanchat', 'clearchat', 'purge'],
                      desc="Mass clear chat",
                      usage="chatclean (amount) (@member)",
                      uperms=["Manage Messages"],
                      bperms=["Manage Messages"],
                      note="If `(amount)` is not specified, it defaults to 1")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def chatclean(self, ctx, amount=1, member: discord.Member = None):
        def from_user(message):
            return member is None or message.author == member

        deleted = await ctx.channel.purge(limit=amount, check=from_user)
        if amount == 1:
            dMessage = "Cleared 1 message."
        else:
            dMessage = "Cleared {} messages.".format(len(deleted))

        clearEmbed = discord.Embed(title="Cleared Chat",
                                   description=dMessage,
                                   color=discord.Color.blue())
        clearEmbed.set_thumbnail(
            url="https://cdn.discordapp.com/attachments/734962101432615006/734962158290468944/eraser.png")
        await ctx.channel.send(embed=clearEmbed)

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
    async def mute(self, ctx, members: commands.Greedy[discord.Member], *, reason="Unspecified"):
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        overwrite = discord.PermissionOverwrite(send_messages=False)
        if not role:
            role = await ctx.guild.create_role(name="Muted",
                                               reason="Use for mutes")
            for channel in ctx.guild.channels:
                try:
                    await channel.set_permissions(role, overwrite=overwrite)
                except Exception:
                    pass

        dates = search_dates(text=reason, settings={'PREFER_DATES_FROM': 'future'})
        if not dates:
            reason_nd = reason
            timestring = "Indefinite"
            timestamp = None
        else:
            reason_nd = reason.replace(f"{dates[0][0]}", "")
            timestring = dates[0][0]
            timestamp = dates[0][1].timestamp()
        if reason.startswith(" "):
            reason_nd = reason[1:]

        for member in members:
            if role in member.roles:
                mutedEmbed = discord.Embed(title=f"{member} Already Muted",
                                           description=f"{member} has already been muted",
                                           color=discord.Color.dark_red())
                await ctx.channel.send(embed=mutedEmbed)
            else:
                await member.add_roles(role)
                path = './muted'
                files = os.listdir(path)
                name = random.choice(files)
                d = f'{path}//{name}'
                with open(d, 'rb') as f:
                    picture = discord.File(f, d)
                mutedEmbed = discord.Embed(title=f'Muted {member}️',
                                           description=f"**Reason:** {reason_nd}\n**Duration:** {timestring}",
                                           color=discord.Color.blue())
                mutedEmbed.set_thumbnail(url=f"attachment://muted_{name}")
                mutedEmbed.set_footer(text=f'{member} was muted by: {ctx.author}')
                await ctx.channel.send(file=picture, embed=mutedEmbed)
            await self.set_mute(ctx, member, timestamp)

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
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        for member in members:
            if not role:
                unmuteEmbed = discord.Embed(title="No Muted Role",
                                            description="There is no muted role on this server.",
                                            color=discord.Color.dark_red())
                await ctx.channel.send(embed=unmuteEmbed)
            if not (role in member.roles):
                unmuteEmbed = discord.Embed(title=f"User {member} Not Muted",
                                            description="You cannot unmute an already unmuted user.",
                                            color=discord.Color.dark_red())
                await ctx.channel.send(embed=unmuteEmbed)
            else:
                await member.remove_roles(role)
                unmuteEmbed = discord.Embed(title=f"Unmuted {member}",
                                            description=f"**Reason:** {reason}",
                                            color=discord.Color.blue())
                unmuteEmbed.set_footer(text=f'{member} was unmuted by: {ctx.author}')
                await ctx.channel.send(embed=unmuteEmbed)
                async with self.bot.db.acquire() as con:
                    await con.execute(f"DELETE FROM mutes WHERE user_id = {member.id} AND guild_id = {ctx.guild.id}")

    @commands.command(desc="Kick members from the server",
                      usage="kick [@member]*va (reason)",
                      uperms=["Kick Members"],
                      bperms=["Kick Members"])
    @commands.bot_has_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, members: commands.Greedy[discord.Member], *, reason='Unspecified'):
        for member in members:
            await member.kick(reason=reason)
            kickEmbed = discord.Embed(title="Kicked User",
                                      description=f'{member.mention} has been kicked from the server!',
                                      color=discord.Color.blue())
            kickEmbed.set_thumbnail(url=member.avatar_url)
            kickEmbed.add_field(name='Reason:',
                                value=reason,
                                inline=False)
            await ctx.channel.send(embed=kickEmbed)

    @commands.command(desc="Bans members from the server",
                      usage="ban [@member]*va (message_delete_days) (reason)",
                      uperms=["Ban Members"],
                      bperms=["Ban Members"],
                      note="If unspecified, `(message_delete_days)` and `(reason)` default to 0 and \"unspecified\" respectively")
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, members: commands.Greedy[discord.Member], days: typing.Optional[int] = 0, *,
                  reason='Unspecified'):
        for member in members:
            await member.ban(delete_message_days=days, reason=reason)
            if days != 0:
                dMessage = f"{member.mention} has been banned from the server! \n\nDeleted {member.mention}'s " \
                           f"messages from the past {days} days "
            else:
                dMessage = f'{member.mention} has been banned from the server!'

            banEmbed = discord.Embed(title="Banned User",
                                     description=dMessage,
                                     color=discord.Color.blue())
            banEmbed.set_thumbnail(url=member.avatar_url)
            banEmbed.add_field(name='Reason:',
                               value=reason,
                               inline=False)
            await ctx.channel.send(embed=banEmbed)

    @commands.command(desc="Unbans users that are banned",
                      usage="unban [user]*va",
                      uperms=["Ban Members"],
                      bperms=["Ban Members"],
                      note="Since those `[user]` aren't in your server anymore, you can specify by "
                      "username and discriminator and the bot will attempt to identify which users you are "
                      "referring to and unban them if found.")
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, users: commands.Greedy[discord.User]):
        for user in users:
            try:
                await ctx.guild.fetch_ban(user)
            except Exception:
                notBanned = discord.Embed(title="User Not Banned!",
                                          description='For now :)',
                                          color=discord.Color.blue())
                notBanned.set_thumbnail(url=user.avatar_url)
                notBanned.add_field(name='Moderator',
                                    value=ctx.author.mention,
                                    inline=False)
                await ctx.channel.send(embed=notBanned)
            else:
                unban = discord.Embed(title='Unbanned',
                                      color=discord.Color.blue())
                unban.set_thumbnail(url=user.avatar_url)
                unban.add_field(name='User:',
                                value=user.mention)
                unban.add_field(name='Moderator:',
                                value=ctx.author.mention)
                await ctx.guild.unban(user, reason="Moderator: " + str(ctx.author))
                await ctx.channel.send(embed=unban)

    @commands.command(desc="Administers warns for certain users",
                      usage="warn [@member]*va (reason)",
                      uperms=["Ban Members"],
                      bperms=["Ban Members"],
                      note="If enabled, the automod actions will take place upon warns based on "
                      "the warn count for each member")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def warn(self, ctx, members: commands.Greedy[discord.Member], *, reason="Unspecified"):
        timestamp = datetime.now().timestamp()
        warned_by = ctx.author
        warns = await self.get_warns(ctx, members)
        for member, count in warns:
            await self.auto_warn_action(ctx, member, reason, count, timestamp)
        return

    @commands.command(desc="Toggle the automod function for warns",
                      usage="automod",
                      uperms=["Ban Members"],
                      note="**Actions:**\n1st Warn: Nothing\n2nd Warn: 10 minute mute\n3rd Warn: Kick\n4th Warn: Ban")
    @commands.has_permissions(ban_members=True)
    async def automod(self, ctx):
        async with self.bot.db.acquire() as con:
            am_status = await con.fetchval(f"SELECT automod FROM guild WHERE guild_id={ctx.guild.id}")
            await con.execute(f"UPDATE guild SET automod={not am_status} WHERE guild_id={ctx.guild.id}")
        embed = discord.Embed(title="Automod Toggle",
                              description=f"{ctx.author.mention}, automod has been turned "
                              f"{'on' if not am_status else 'off'} for this server",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['offenses'],
                      desc="Lists warns to a given member or warns you have given",
                      usage="offense (@member)",
                      note="If `(member)` is unspecified, it will display all the warnings you have "
                      "given to other members")
    async def offense(self, ctx, member: discord.Member = None):
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT guild_id FROM warns WHERE guild_id = {ctx.guild.id}")
        if not result:
            embed = discord.Embed(title="No Warning History",
                                  description=f"{ctx.author.mention}, no warnings have been issued on this server",
                                  color=discord.Color.blue())
            return await ctx.channel.send(embed=embed)

        administered = await self.get_administered_warns(ctx, member)
        if not administered:
            embed = discord.Embed(title="No Warnings Given",
                                  description=f"{ctx.author.mention}, you have not given any warnings to "
                                  f"{member.mention}",
                                  color=discord.Color.blue())
        else:
            if member:
                count = len(administered)
                if count != 1:
                    title = f"{count} Warnings Given"
                else:
                    title = "1 Warning Given"
                index = 1
                embed = discord.Embed(title=title,
                                      description=f"{ctx.author.mention}, here is a list of warnings you have given to "
                                      f"{member.mention}",
                                      color=discord.Color.blue())
                for counter, values in enumerate(administered, 1):
                    formatted_time = "{:%m/%d/%Y %H:%M:%S}".format(datetime.fromtimestamp(values[1]))
                    embed.add_field(name=f"Warning ID {values[2]}",
                                    value=f"> **Time:** {formatted_time}\n> **Reason:** {values[0]}",
                                    inline=False)
            else:
                description = ""
                for item in administered:
                    amount = administered.count(item)
                    if amount != 1:
                        spell = "times"
                    else:
                        spell = "time"
                    administered = list(filter(lambda e: e != item, administered))
                    description += f"**User:** <@{item[0]}> - warned {amount} {spell}\n\n"
                embed = discord.Embed(title="Warnings Given",
                                      description=f"{ctx.author.mention}, here is a list of warnings you have given in "
                                      f"{ctx.guild.name}:\n\n{description}",
                                      color=discord.Color.blue())
        await ctx.channel.send(embed=embed)

    @commands.command(desc="Expunge warns from a member",
                      usage="expunge [@member]",
                      uperms=["Ban Members"],
                      bperms=["Ban Members"])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def expunge(self, ctx, member: discord.Member = None):
        if not member:
            embed = discord.Embed(title="No Member Specified",
                                  description=f"{ctx.author.mention}, please specify the member you want to expunge "
                                  "warn records",
                                  color=discord.Color.dark_red())
            return await ctx.channel.send(embed=embed)
        administered = await self.get_administered_warns(ctx, member)
        if not administered:
            embed = discord.Embed(title="No Warnings Given",
                                  description=f"{ctx.author.mention}, you have not given any warnings to "
                                  f"{member.mention}",
                                  color=discord.Color.blue())
            return await ctx.channel.send(embed=embed)

        records = ""
        for counter, values in enumerate(administered, 1):
            formatted_time = "{:%m/%d/%Y %H:%M:%S}".format(datetime.fromtimestamp(values[1]))
            records += f"**Warning ID {values[2]}**\n> **Time: ** {formatted_time}\n> **Reason:** {values[0]}\n\n"

        panel_embed = discord.Embed(title="Expunge Warn Records",
                                    description=f"{ctx.author.mention}, please type the id number of the record you would "
                                    f"like to expunge, or enter \"all\" to expunge all\n\n{records}",
                                    color=discord.Color.blue())
        panel_embed.set_footer(text='Type "cancel" to cancel')

        panel = await ctx.channel.send(embed=panel_embed)

        def from_user(message: discord.Message) -> bool:
            if message.author.id == ctx.author.id and message.channel.id == ctx.channel.id:
                return True
            else:
                return False

        reactions = ["✅", "🛑"]

        def user_reacted(reaction: discord.Reaction, user: discord.User) -> bool:
            if reaction.emoji in reactions and reaction.message.id == panel.id and user.id == ctx.author.id:
                return True
            else:
                return False

        cmd_name = "expunge warn record"
        timeout = 60

        # Get number from user or all
        while True:
            try:
                if not await self.check_panel(panel):
                    return await self.end_setup(ctx, cmd_name, "no_panel")
                result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, cmd_name, timeout)
            if result.content == "cancel":
                return await self.end_setup(ctx, cmd_name, "cancel")
            elif result.content == "all":
                index = result.content
                break
            try:
                index = int(result.content)
                break
            except TypeError:
                continue
        await gcmds.smart_delete(result)

        description = "This action is irreversible. React with ✅ to confirm or 🛑 to cancel"
        try:
            for reaction in reactions:
                await panel.add_reaction(reaction)
        except (discord.Forbidden, discord.NotFound, discord.HTTPError):
            return await self.end_setup(ctx, cmd_name, "cancel")

        # Get confirmation
        while True:
            try:
                if not await self.edit_panel(ctx, panel, None, description, None):
                    return await self.end_setup(ctx, cmd_name, "no_panel")
                result = await self.bot.wait_for("reaction_add", check=user_reacted, timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, cmd_name, timeout)
            if result[0].emoji == "✅":
                break
            elif result[0].emoji == "🛑":
                return await self.end_setup(ctx, cmd_name, "cancel")
            continue

        try:
            await panel.delete()
        except Exception:
            pass

        succeeded = await self.remove_warn(ctx, member, index)
        if succeeded:
            embed = discord.Embed(title="Warn Expunged Successfully",
                                  description=f"{ctx.author.mention}, {member.mention}'s warn has been expunged",
                                  color=discord.Color.blue())
        else:
            embed = discord.Embed(title="Warn Expunge Failed",
                                  description=f"{ctx.author.mention}, {member.mention}'s warn could not be expunged",
                                  color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['mod', 'mods', 'modsonline', 'mo'],
                      desc="Displays the moderators that are online",
                      usage="modsonline",
                      note="This feature works if the substring \"moderator\" is in the moderator role or its equivalent")
    async def modsOnline(self, ctx):
        modsList = []
        for member in ctx.guild.members:
            if member.status is not discord.Status.offline:
                if not member.bot:
                    for role in member.roles:
                        if "moderator" in role.name.casefold():
                            modsList += [member.mention]
        if modsList:
            title = "Moderators Online"
            description = "\n".join(modsList)
            color = discord.Color.blue()
        else:
            title = "No Moderators Online"
            description = "There are currently no users that are moderators on this server\n\n*No users have a role " \
                          "with the substring* `moderator` *(case insensitive) in it*"
            color = discord.Color.dark_red()

        modsEmbed = discord.Embed(title=title,
                                  description=description,
                                  color=color)
        modsEmbed.set_thumbnail(url="https://www.pinclipart.com/picdir/big/529-5290012_gavel-clipart.png")
        await ctx.channel.send(embed=modsEmbed)


def setup(bot):
    bot.add_cog(Moderation(bot))
