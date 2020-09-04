import discord
import typing
from discord.ext import commands, tasks
from globalcommands import GlobalCMDS
import os
import json
import asyncio
import random
from dateparser.search import search_dates
from datetime import datetime, timezone, timedelta
import base64
from num2words import num2words

gcmds = GlobalCMDS()
auto_mute_duration = 600
auto_warn_actions = [None, None, "mute", "kick", "ban"]


class Moderation(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.check_mute_expire.start()

    def cog_unload(self):
        self.check_mute_expire.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Cog "{self.qualified_name}" has been loaded')

    @tasks.loop(seconds=60)
    async def check_mute_expire(self):
        current_time = int(datetime.now().timestamp())
        if not os.path.exists('db/mutes.json'):
            return

        with open('db/mutes.json', 'r') as f:
            file = json.load(f)
            f.close()
        for guild_id in file:
            if not file[guild_id]:
                continue
            for user_id in file[guild_id]:
                time = file[guild_id][user_id]['time']
                if not time:
                    continue
                sleep_time = int(time - current_time)
                if sleep_time > 60:
                    continue
                await asyncio.create_task(self.unmute_user(int(guild_id), int(user_id), sleep_time))

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
        guild = self.client.get_guild(guild_id)
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
            await member.send(embed=embed)
        with open('db/mutes.json', 'r') as f:
            file = json.load(f)
            f.close()
        try:
            del file[str(guild_id)][str(user_id)]
        except KeyError:
            pass
        with open('db/mutes.json', 'w') as g:
            json.dump(file, g, indent=4)
            g.close()
        return

    async def set_mute(self, ctx, member: discord.Member, time: int = None):
        init = {
            str(ctx.guild.id): {
                str(member.id): {
                    "time": time
                }
            }
        }
        gcmds.json_load('db/mutes.json', init)
        with open('db/mutes.json', 'r') as f:
            file = json.load(f)
            f.close()
        file.update({str(ctx.guild.id): {}})
        file[str(ctx.guild.id)].update({str(member.id): {}})
        file[str(ctx.guild.id)][str(member.id)].update({'time': time})
        with open('db/mutes.json', 'w') as g:
            json.dump(file, g, indent=4)
            g.close()

    async def get_warns(self, ctx, members) -> list:
        if not os.path.exists('db/warns.json'):
            return [(member, 0) for member in members]

        with open('db/warns.json', 'r') as f:
            file = json.load(f)
            f.close()
        warns = []
        for member in members:
            try:
                warns.append((member, file[str(ctx.guild.id)][str(member.id)]['count']))
            except KeyError:
                warns.append((member, 0))
        return warns

    async def remove_warn(self, ctx, member: discord.Member, index) -> bool:
        try:
            with open('db/warns.json', 'r') as f:
                file = json.load(f)
                f.close()
            if isinstance(index, str):
                del file[str(ctx.guild.id)][str(member.id)]
            else:
                del file[str(ctx.guild.id)][str(member.id)]['history'][index]
                count = file[str(ctx.guild.id)][str(member.id)]['count']
                if count == 1:
                    del file[str(ctx.guild.id)][str(member.id)]
                else:
                    file[str(ctx.guild.id)][str(member.id)]['count'] -= 1
            with open('db/warns.json', 'w') as g:
                json.dump(file, g, indent=4)
            return True
        except KeyError:
            return False

    async def get_administered_warns(self, ctx, member: discord.Member = None) -> list:
        if not os.path.exists('db/warns.json'):
            return None
        with open('db/warns.json', 'r') as f:
            file = json.load(f)
            f.close()

        warns = []
        count = 0

        try:
            if not member:
                for users in file[str(ctx.guild.id)]:
                    for item in file[str(ctx.guild.id)][str(users)]['history']:
                        if int(item['moderator']) == ctx.author.id:
                            count += 1
                    warns.append((users, count))
            else:
                history = []
                for item in file[str(ctx.guild.id)][str(member.id)]['history']:
                    if int(item['moderator']) == ctx.author.id:
                        count += 1
                        history.append((item['reason'], item['timestamp']))
                warns = [count, history]
        except KeyError:
            return None

        return warns

    async def auto_warn_action(self, ctx, member: discord.Member, reason: str, count: int, timestamp):
        count_adj = count + 1
        action = auto_warn_actions[count_adj]
        title = f"Warning from {ctx.guild.name}"
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
        except (discord.Forbidden, discord.HTTPException):
            pass

        embed.set_author(name=f"Warning sent to {member.display_name}", icon_url=member.avatar_url)
        await ctx.author.send(embed=embed)

        if not os.path.exists('db/warns.json'):
            gcmds.json_load('db/warns.json', {})
        with open('db/warns.json', 'r') as f:
            file = json.load(f)
            f.close()
        try:
            if file[str(ctx.guild.id)]:
                pass
        except KeyError:
            file.update({str(ctx.guild.id): {}})
        
        try:
            file[str(ctx.guild.id)][str(member.id)]['count'] += 1
            file[str(ctx.guild.id)][str(member.id)]['history'].append(
                {"moderator": ctx.author.id, "reason": reason, "timestamp": int(timestamp)})
        except KeyError:
            file[str(ctx.guild.id)].update({str(member.id): {}})
            file[str(ctx.guild.id)][str(member.id)]['count'] = 1
            file[str(ctx.guild.id)][str(member.id)]['history'] = [{"moderator": ctx.author.id,
                                                                   "reason": reason, "timestamp": int(timestamp)}]

        with open('db/warns.json', 'w') as g:
            json.dump(file, g, indent=4)
            g.close()

    @commands.command(aliases=['clear', 'clean', 'chatclear', 'cleanchat', 'clearchat', 'purge'])
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
        await ctx.channel.send(embed=clearEmbed, delete_after=5)

    @commands.command(aliases=['silence', 'stfu', 'shut', 'shush', 'shh', 'shhh', 'shhhh', 'quiet'])
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, members: commands.Greedy[discord.Member], *, reason="Unspecified"):
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not role:
            role = await ctx.guild.create_role(name="Muted",
                                               reason="Use for mutes")
            for channel in ctx.guild.channels:
                await channel.set_permissions(role, send_messages=False)

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

    @commands.command(aliases=['unsilence', 'unstfu', 'unshut', 'unshush', 'unshh', 'unshhh', 'unshhhh', 'unquiet'])
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, members: commands.Greedy[discord.Member], *, reason="Unspecified"):
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        for member in members:
            if not role:
                unmuteEmbed = discord.Embed(title="No Muted Role",
                                            description="There is no muted role on this server.",
                                            color=discord.Color.dark_red())
                await ctx.channel.send(embed=unmuteEmbed, delete_after=5)
            if not (role in member.roles):
                unmuteEmbed = discord.Embed(title=f"User {member} Not Muted",
                                            description="You cannot unmute an already unmuted user.",
                                            color=discord.Color.dark_red())
                await ctx.channel.send(embed=unmuteEmbed, delete_after=5)
            else:
                await member.remove_roles(role)
                unmuteEmbed = discord.Embed(title=f"Unmuted {member}",
                                            description=f"**Reason:** {reason}",
                                            color=discord.Color.blue())
                unmuteEmbed.set_footer(text=f'{member} was unmuted by: {ctx.author}')
                await ctx.channel.send(embed=unmuteEmbed)

    @commands.command()
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

    @commands.command()
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

    @commands.command()
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, users: commands.Greedy[discord.User]):
        for user in users:
            try:
                user = await commands.converter.UserConverter().convert(ctx, user)
            except commands.BadArgument:
                error = discord.Embed(title='Error',
                                      description='User could not be found!',
                                      color=discord.Color.dark_red())
                await ctx.channel.send(embed=error, delete_after=5)

            bans = tuple(ban_entry.user for ban_entry in await ctx.guild.bans())
            if user in bans:
                unban = discord.Embed(title='Unbanned',
                                      color=discord.Color.blue())
                unban.set_thumbnail(url=user.avatar_url)
                unban.add_field(name='User:',
                                value=user.mention)
                unban.add_field(name='Moderator:',
                                value=ctx.author.mention)
                await ctx.guild.unban(user, reason="Moderator: " + str(ctx.author))
                await ctx.channel.send(embed=unban)

            else:
                notBanned = discord.Embed(title="User Not Banned!",
                                          description='For now :)',
                                          color=discord.Color.blue())
                notBanned.set_thumbnail(url=user.avatar_url)
                notBanned.add_field(name='Moderator',
                                    value=ctx.author.mention,
                                    inline=False)
                await ctx.channel.send(embed=notBanned, delete_after=5)

    @commands.command()
    async def warn(self, ctx, members: commands.Greedy[discord.Member], *, reason="Unspecified"):
        timestamp = datetime.now().timestamp()
        warned_by = ctx.author
        warns = await self.get_warns(ctx, members)
        for member, count in warns:
            await self.auto_warn_action(ctx, member, reason, count, timestamp)
        return

    @commands.command(aliases=['offenses'])
    async def offense(self, ctx, member: discord.Member = None):
        if not os.path.exists('db/warns.json'):
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
            if isinstance(administered[0], int):
                count = administered.pop(0)
                if count != 1:
                    title = f"{count} Warnings Given"
                else:
                    title = "1 Warning Given"
                index = 1
                embed = discord.Embed(title=title,
                                      description=f"{ctx.author.mention}, here is a list of warnings you have given to "
                                      f"{member.mention}",
                                      color=discord.Color.blue())
                administered = administered[0]
                for reason, timestamp in administered:
                    formatted_time = "{:%m/%d/%Y %H:%M:%S}".format(datetime.fromtimestamp(timestamp))
                    embed.add_field(name=f"{num2words((index), to='ordinal_num')} Warning",
                                    value=f"**Time: ** {formatted_time}\n**Reason:** {reason}",
                                    inline=False)
                    index += 1
            else:
                description = ""
                for item in administered:
                    if item[1] != 1:
                        spell = "times"
                    else:
                        spell = "time"
                    description += f"**User:** <@{item[0]}\n**Warned:** {item[1]} {spell}\n\n"
                embed = discord.Embed(title="Warnings Given",
                                      description=f"{ctx.author.mention}, here is a list of warnings you have given in "
                                      f"{ctx.guild.name}:\n\n{description}",
                                      color=discord.Color.blue())
        await ctx.channel.send(embed=embed)

    @commands.command()
    async def expunge(self, ctx, member: discord.Member = None):
        if not member:
            embed = discord.Embed(title="No Member Specified",
                                  description=f"{ctx.author.mention}, please specify the member you want to expunge "
                                  "warn records",
                                  color=discord.Color.dark_red())
            return await ctx.channel.send(embed=embed, delete_after=10)
        administered = await self.get_administered_warns(ctx, member)
        if not administered:
            embed = discord.Embed(title="No Warnings Given",
                                  description=f"{ctx.author.mention}, you have not given any warnings to "
                                  f"{member.mention}",
                                  color=discord.Color.blue())
            return await ctx.channel.send(embed=embed)

        records = ""
        index = 1
        administered.pop(0)
        print(administered)
        for reason, timestamp in administered[0]:
                    formatted_time = "{:%m/%d/%Y %H:%M:%S}".format(datetime.fromtimestamp(timestamp))
                    records += f"**{index}:**\n**Time: ** {formatted_time}\n**Reason:** {reason}\n\n"
                    index += 1
        panel_embed = discord.Embed(title="Expunge Warn Records",
                                    description=f"{ctx.author.mention}, please type the number of the record you would "
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
                result = await self.client.wait_for("message", check=from_user, timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, cmd_name, timeout)
            if result.content == "cancel":
                return await self.end_setup(ctx, cmd_name, "cancel")
            elif result.content == "all":
                index = result.content
                break
            try:
                index = int(result.content) - 1
                break
            except TypeError:
                continue

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
                result = await self.client.wait_for("reaction_add", check=user_reacted, timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, cmd_name, timeout)
            if result[0].emoji == "✅":
                break
            elif result[0].emoji == "🛑":
                return await self.end_setup(ctx, cmd_name, "cancel")
            continue
        await result[0].message.delete()

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

    @commands.command(aliases=['mod', 'mods', 'modsonline', 'mo'])
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
            description = ""
            color = discord.Color.blue()
            for mods in modsList:
                description = f"{description} {mods}"
        else:
            title = "No Moderators Online"
            description = "There are currently no users that are moderators on this server\n\n*No users have a role " \
                          "with the substring* `moderator` *(case insensitive) in it*"
            color = discord.Color.dark_red()

        modsEmbed = discord.Embed(title=title,
                                  description=description,
                                  color=color)
        modsEmbed.set_thumbnail(url="https://www.pinclipart.com/picdir/big/529-5290012_gavel-clipart.png")
        await ctx.channel.send(embed=modsEmbed, delete_after=60)


def setup(client):
    client.add_cog(Moderation(client))
