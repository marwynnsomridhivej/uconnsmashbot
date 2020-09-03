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

gcmds = GlobalCMDS()


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
