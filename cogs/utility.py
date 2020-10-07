import os
import json
from datetime import datetime, timedelta
from io import BytesIO

import discord
from discord.ext import commands, tasks
from utils import globalcommands, paginator

gcmds = globalcommands.GlobalCMDS()
invite_url = "https://discord.com/oauth2/authorize?client_id=623317451811061763&scope=bot&permissions=2146958583"


class Utility(commands.Cog):

    def __init__(self, bot: commands.AutoShardedBot):
        global gcmds
        self.bot = bot
        self.messages = {}
        self.update_server_stats.start()
        gcmds = globalcommands.GlobalCMDS(bot=self.bot)
        self.bot.loop.create_task(self.init_requests())

    def cog_unload(self):
        self.update_server_stats.cancel()

    async def init_requests(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS requests(message_id bigint PRIMARY KEY, user_id bigint, type text)")

    @tasks.loop(minutes=15)
    async def update_server_stats(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            result = await con.fetch("SELECT guild_id from guild WHERE serverstats=TRUE")

        guild_ids = [item['guild_id'] for item in result] if result else None
        if not guild_ids:
            return

        for guild_id in guild_ids:
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                await self.remove_ss_entry(int(guild_id))
            for category in guild.categories:
                if "server stats" in category.name.lower():
                    names = await self.get_guild_info(guild)
                    index = 0
                    for voice_channel in category.voice_channels:
                        if not str(voice_channel.name) == str(names[index]):
                            try:
                                await voice_channel.edit(name=names[index])
                            except discord.Forbidden:
                                pass
                        index += 1
                    break
        return

    async def add_entry(self, ctx, message_id: int, type: str):
        async with self.bot.db.acquire() as con:
            await con.execute(f"INSERT INTO requests(message_id, user_id, type) VALUES ({message_id}, {ctx.author.id}, '{type}')")

    async def get_entry(self, message_id: int):
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT * FROM requests WHERE message_id = {message_id}")
        return result if result else None

    async def remove_entry(self, message_id: int):
        async with self.bot.db.acquire() as con:
            await con.execute(f"DELETE FROM requests WHERE message_id = {message_id}")

    async def get_guild_info(self, guild: discord.Guild) -> list:
        botCount = 0
        for member in guild.members:
            if member.bot:
                botCount += 1

        totalMembers = f"👥Members: {guild.member_count - botCount}"
        totalText = f"📑Text Channels: {int(len(guild.text_channels))}"
        totalVoice = f"🎧Voice Channels: {int(len(guild.voice_channels))}"
        totalChannels = f"📖Total Channels: {int(len(guild.text_channels)) + int(len(guild.voice_channels))}"
        totalRole = f"📜Roles: {int(len(guild.roles))}"
        totalEmoji = f"😄Custom Emotes: {int(len(guild.emojis))}"
        return [totalMembers, totalChannels, totalText, totalVoice, totalRole, totalEmoji]

    async def add_ss_entry(self, guild_id: int):
        async with self.bot.db.acquire() as con:
            await con.execute(f"UPDATE guild SET serverstats=TRUE WHERE guild_id = {guild_id}")

    async def remove_ss_entry(self, guild_id: int):
        async with self.bot.db.acquire() as con:
            await con.execute(f"UPDATE guild SET serverstats=FALSE WHERE guild_id = {guild_id}")

    @commands.command(aliases=['counters', 'used', 'usedcount'],
                      desc="Displays the used counter for commands",
                      usage="counter (command) (mode)",
                      note="Valid arguments for `(mode)` are \"server\" and \"global\". "
                      "If `(command)` is unspecified, it will show the counters for all commands. "
                      "If `(mode)` is unspecified, it will show the count for only commands executed in this server.")
    async def counter(self, ctx, name=None, mode='server'):
        if name == "server" or name == "global":
            mode = name
            name = None
        if not name:
            async with self.bot.db.acquire() as con:
                if mode == 'server':
                    result = (await con.fetch(f"SELECT counter FROM guild WHERE guild_id = {ctx.guild.id}"))[0]['counter']
                    result_dict = json.loads(result)
                    title = f"Counters for {ctx.guild.name}"
                    entries = [
                        f"***{key.lower()}:*** *used {result_dict[key]} {'times' if result_dict[key] != 1 else 'time'}*" for key in result_dict.keys()]
                else:
                    result = (await con.fetch(f"SELECT * from global_counters"))
                    title = "Global Counters"
                    entries = [
                        f"***{record['command'].lower()}:*** *used {record['amount']} {'times' if record['amount'] != 1 else 'time'}*" for record in result]
            pag = paginator.EmbedPaginator(ctx, entries=sorted(entries), per_page=20, show_entry_count=True)
            pag.embed.title = title
            return await pag.paginate()
        else:
            command = self.bot.get_command(name)
            async with self.bot.db.acquire() as con:
                if mode == "global":
                    amount = (await con.fetch(f"SELECT amount from global_counters WHERE command = '{command.name}'"))[0]['amount']
                    title = f"Global Counter for {command.name.title()}"
                else:
                    amount = (
                        await con.fetch(
                            f"SELECT counter->>'{command.name}' from guild WHERE guild_id = {ctx.guild.id}"
                        )
                    )[0][0]
                    title = f"Server Counter for {command.name.title()}"
            description = f"***{command.name}:*** *used {amount} {'times' if amount != 1 else 'time'}*"
            embed = discord.Embed(title=title,
                                  description=description,
                                  color=discord.Color.blue())
            return await ctx.channel.send(embed=embed)

    @commands.command(desc="Displays MarwynnBot's invite link",
                      usage="invite")
    async def invite(self, ctx):
        embed = discord.Embed(title="MarwynnBot's Invite Link",
                              description=f"{ctx.author.mention}, thank you for using MarwynnBot! Here is MarwynnBot's"
                              f" invite link that you can share:\n\n {invite_url}",
                              color=discord.Color.blue(),
                              url=invite_url)
        await ctx.channel.send(embed=embed)

    @commands.group(invoke_without_command=True,
                    desc="Displays the help command for request",
                    usage="request")
    async def request(self, ctx):
        menu = discord.Embed(title="Request Options",
                             description=f"{ctx.author.mention}, do `{await gcmds.prefix(ctx)}request feature` "
                             f"to submit a feature request with a 60 second cooldown",
                             color=discord.Color.blue())
        await ctx.channel.send(embed=menu)

    @request.command()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def feature(self, ctx, *, feature_message: str = None):
        if not feature_message:
            menu = discord.Embed(title="Request Options",
                                 description=f"{ctx.author.mention}, do `{await gcmds.prefix(ctx)}request feature` "
                                             f"to submit a feature request",
                                 color=discord.Color.dark_red())
            return await ctx.channel.send(embed=menu)

        timestamp = f"Executed at: " + "{:%m/%d/%Y %H:%M:%S}".format(datetime.now())

        feature_embed = discord.Embed(title="Feature Request",
                                      description=feature_message,
                                      color=discord.Color.blue())
        feature_embed.set_footer(text=timestamp)
        owner_id = gcmds.env_check("OWNER_ID")
        if not owner_id:
            no_api = discord.Embed(title="Missing Owner ID",
                                   description="This command is disabled",
                                   color=discord.Color.dark_red())
            return await ctx.channel.send(embed=no_api)
        owner = self.bot.get_user(int(owner_id))
        message = await owner.send(embed=feature_embed)
        feature_embed.set_footer(text=f"{timestamp}\nMessage ID: {message.id}")
        await message.edit(embed=feature_embed)
        if not feature_message.endswith(" --noreceipt"):
            feature_embed.set_author(name=f"Copy of your request", icon_url=ctx.author.avatar_url)
            await ctx.author.send(embed=feature_embed)
        self.add_entry(ctx, message.id, "feature")

    @request.command()
    @commands.is_owner()
    async def reply(self, ctx, message_id: int = None, *, reply_message: str = None):
        if not reply_message or not message_id:
            menu = discord.Embed(title="Request Options",
                                 description=f"{ctx.author.mention}, please write specify a valid message ID and a "
                                             f"reply message",
                                 color=discord.Color.dark_red())
            return await ctx.channel.send(embed=menu)
        user_id = self.get_entry(message_id)
        user = await self.bot.fetch_user(user_id)
        raw_reply = reply_message
        if reply_message == "spam":
            reply_message = f"{user.mention}, your request was either not related to a feature, or was categorised as " \
                            f"spam. Please review the content of your request carefully next time so that it isn't " \
                            f"marked as this. If you believe this was a mistake, please contact the bot owner: " \
                            f"{ctx.author.mention}"
        if reply_message == "no":
            reply_message = f"{user.mention}, unfortunately, your request could not be considered as of this time."
        thank = f"{user.mention}, thank you for submitting your feature request. Here is a message from" \
                f"{ctx.author.mention}, the bot owner:\n\n "
        timestamp = f"Replied at: " + "{:%m/%d/%Y %H:%M:%S}".format(datetime.now())
        reply_embed = discord.Embed(title=f"Reply From {ctx.author} To Your Request",
                                    description=thank + reply_message,
                                    color=discord.Color.blue())
        reply_embed.set_footer(text=timestamp)

        await user.send(embed=reply_embed)
        reply_embed.description = f"Message was successfully sent:\n\n{raw_reply}"
        await ctx.author.send(embed=reply_embed)
        self.remove_entry(message_id)

    @commands.command(aliases=['emotes', 'serveremotes', 'serveremote', 'serverEmote', 'emojis', 'emoji'],
                      desc="Queries emotes that belong to this server",
                      usage="serveremotes (query)",
                      note="If `(query)` is unspecified, it will display all the emojis that belong to this server")
    async def serverEmotes(self, ctx, *, search=None):
        description = [f"**{emoji.name}:** \\<:{emoji.name}:{emoji.id}>"
                       for emoji in ctx.guild.emojis] if not search else \
            [f"**{emoji.name}:** \\<:{emoji.name}:{emoji.id}>"
             for emoji in ctx.guild.emojis
             if search in emoji.name]

        emojiEmbed = discord.Embed(title="Server Custom Emotes:",
                                   description="\n".join(sorted(description)),
                                   color=discord.Color.blue())
        await ctx.channel.send(embed=emojiEmbed)

    @commands.command(aliases=['info', 'si', 'serverinfo'],
                      desc="Displays the current server's information",
                      usage="serverinfo")
    async def serverInfo(self, ctx):
        description = (f"Owner: {ctx.guild.owner.mention}",
                       f"Created At: `{str(ctx.guild.created_at)[:-7]}`",
                       f"Members: `{ctx.guild.member_count}`",
                       f"Roles: `{len(ctx.guild.roles)}`",
                       f"Total Channels: `{len(ctx.guild.channels) - len(ctx.guild.categories)}`",
                       f"Boosts: `{len(ctx.guild.premium_subscribers)}`")
        embed = discord.Embed(title=ctx.guild.name, description="\n".join(description), color=discord.Color.blue())
        embed.set_image(url=ctx.guild.icon_url)
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['pfp'],
                      desc="Displays a member's profile picture",
                      usage="profile [@member]")
    async def profile(self, ctx, *, member: discord.Member):
        icon = member.avatar_url_as(static_format="png", size=4096)
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_author(name=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        embed.set_image(url=icon)
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['p', 'checkprefix', 'prefixes'],
                      desc="Displays the server's custom prefix",
                      usage="prefix")
    async def prefix(self, ctx):
        serverPrefix = await gcmds.prefix(ctx)
        prefixEmbed = discord.Embed(title='Prefixes',
                                    color=discord.Color.blue())
        prefixEmbed.add_field(name="Current Server Prefix",
                              value=f"The current server prefix is: `{serverPrefix}`",
                              inline=False)
        prefixEmbed.add_field(name="Global Prefixes",
                              value=f"{self.bot.user.mention} or `mb ` - *ignorecase*",
                              inline=False)
        await ctx.channel.send(embed=prefixEmbed)

    @commands.command(aliases=['sp', 'setprefix'],
                      desc="Sets the server's custom prefix",
                      usage="setprefix [prefix]",
                      uperms=["Manage Server"],
                      note="If `[prefix]` is \"reset\", then the custom prefix will be set to \"m!\"")
    @commands.has_permissions(manage_guild=True)
    async def setPrefix(self, ctx, prefix):
        async with self.db.acquire() as con:
            if prefix != 'reset':
                await con.execute(f"UPDATE guild SET custom_prefix=$tag${prefix}$tag$ WHERE guild_id={ctx.guild.id}")
                prefixEmbed = discord.Embed(title='Server Prefix Set',
                                            description=f"Server prefix is now set to `{prefix}` \n\n"
                                                        f"You will still be able to use {self.bot.user.mention} "
                                                        f"and `mb ` as prefixes",
                                            color=discord.Color.blue())
            else:
                await con.execute(f"UPDATE guild SET custom_prefix='m!' WHERE guild_id={ctx.guild.id}")
                prefixEmbed = discord.Embed(title='Server Prefix Set',
                                            description=f"Server prefix has been reset to `m!`",
                                            color=discord.Color.blue())
            await ctx.channel.send(embed=prefixEmbed)

    @commands.command(aliases=['ss', 'serverstats', 'serverstatistics'],
                      desc="Sets the server's server stats panel",
                      usage="serverstats (flag)",
                      uperms=["Manage Server", "Manage Channels"],
                      bperms=["Manage Server", "Manage Channels"],
                      note="If `(flag)` is \"rest\", the server stats panel will be deleted")
    @commands.bot_has_permissions(manage_guild=True, manage_channels=True)
    @commands.has_permissions(manage_guild=True, manage_channels=True)
    async def serverStats(self, ctx, reset=None):
        for category in ctx.guild.categories:
            if "server stats" in category.name.lower():
                if reset == "reset":
                    for channel in category.channels:
                        await channel.delete()
                    await category.delete()
                    await self.remove_ss_entry(ctx.guild.id)
                    reset_embed = discord.Embed(title="Server Stats Reset",
                                                description=f"{ctx.author.mention}, your server stats panel for this "
                                                "server has been deleted",
                                                color=discord.Color.blue())
                    return await ctx.channel.send(embed=reset_embed)
                elif not reset:
                    exists = discord.Embed(title="Server Stats Panel Exists",
                                           description=f"{ctx.author.mention}, this server already has a server stats "
                                           "panel set up!",
                                           color=discord.Color.dark_red())
                    return await ctx.channel.send(embed=exists)
            else:
                category = await ctx.guild.create_category_channel("📊 Server Stats 📊")
                await category.edit(position=0)
                await category.set_permissions(ctx.guild.default_role, connect=False)
                names = await self.get_guild_info(ctx.guild)
                for name in names:
                    await category.create_voice_channel(name)
                await self.add_ss_entry(ctx.guild.id)
                created_embed = discord.Embed(title="Server Stats Panel Created",
                                              description=f"{ctx.author.mention}, I have created the server stats "
                                              "panel for this server",
                                              color=discord.Color.blue())
                return await ctx.channel.send(embed=created_embed)

    @commands.command(aliases=['tz'],
                      desc="Appends a timezone tag to yourself",
                      usage="timezone [timezone]",
                      uperms=["Change Nickname"],
                      bperms=["Manage Nicknames"],
                      note="`[timezone]` must be in GMT format. If `[timezone]` is \"reset\" or \"r\", "
                      "the tag will be removed")
    @commands.has_permissions(change_nickname=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def timezone(self, ctx, *, timezoneInput: str):
        name = timezoneInput.replace(" ", "")
        if name == 'reset' or name == 'r':
            await ctx.author.edit(nick=f"{ctx.author.name}")
            title = "Timezone Reset Success"
            description = f"{ctx.author.mention}'s timezone has been removed from their name"
            color = discord.Color.blue()
        elif name:
            if "GMT" in name:
                nick = f"{ctx.author.display_name} [{name}]"
                await ctx.author.edit(nick=nick)
                title = "Timezone Update Success"
                description = f"{ctx.author.mention}'s timezone has been added to their nickname"
                color = discord.Color.blue()

            else:
                title = "Invalid Timezone Format"
                description = "Please put your timezone in `GMT+` or `GMT-` format"
                color = discord.Color.dark_red()
        else:
            title = "Invalid Timezone Format"
            description = "Please put your timezone in `GMT+` or `GMT-` format"
            color = discord.Color.dark_red()
        gmt = discord.Embed(title=title,
                            description=description,
                            color=color)
        await ctx.channel.send(embed=gmt)

    @commands.command(desc="Displays MarwynnBot's uptime since the last restart",
                      usage="uptime")
    async def uptime(self, ctx):
        time_now = int(datetime.now().timestamp())
        td = timedelta(seconds=time_now - self.bot.uptime)
        embed = discord.Embed(title="Uptime",
                              description=f"MarwynnBot has been up and running for\n```\n{str(td)}\n```",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Utility(bot))
