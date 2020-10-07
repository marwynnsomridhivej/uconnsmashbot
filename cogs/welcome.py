import asyncio
import mimetypes
import os
import random
import re

import aiohttp
import discord
from discord.ext import commands
from num2words import num2words
from utils import globalcommands

gcmds = globalcommands.GlobalCMDS()
timeout = 120
channel_tag_rx = re.compile(r'<#[0-9]{18}>')
channel_id_rx = re.compile(r'[0-9]{18}')
api_key = gcmds.env_check("TENOR_API")


class Welcome(commands.Cog):

    def __init__(self, bot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_welcomer())

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.send_welcomer(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.send_leaver(member)

    async def init_welcomer(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS welcomers(guild_id bigint PRIMARY KEY, channel_id bigint, title text, description text, media text[], leaver boolean)")

    async def send_welcomer(self, member: discord.Member):
        if not member.bot:
            async with self.bot.db.acquire() as con:
                result = await con.fetch(f"SELECT * FROM welcomers WHERE guild_id = {member.guild.id}")
            member = member
            if result:
                info = result[0]
                guild = member.guild
                channel_to_send = await self.bot.fetch_channel(int(info["channel_id"]))
                embed_title = info['title']
                edv = str(info['description'])
                media = info['media']
                bot_count = 0
                for members in guild.members:
                    if members.bot:
                        bot_count += 1
                embed_description = ((((edv.replace("{server_name}", member.guild.name)
                                        ).replace("{user_name}", member.display_name)
                                       ).replace("{user_mention}", member.mention)
                                      ).replace("{member_count}", str(len(member.guild.members) - bot_count))
                                     ).replace("{member_count_ord}", num2words((len(member.guild.members) - bot_count),
                                                                               to="ordinal_num"))
                welcome_embed = discord.Embed(title=embed_title,
                                              description=embed_description,
                                              color=discord.Color.blue())
                welcome_embed.set_thumbnail(url=member.avatar_url)
                if isinstance(media, list):
                    image_url = random.choice(media)
                else:
                    query = "anime wave"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                                "https://api.tenor.com/v1/search?q=%s&key=%s&limit=%s" % (query, api_key, 6)) as image:
                            response = await image.json()
                            getURL = []
                            for i in range(len(response['results'])):
                                for j in range(len(response['results'][i]['media'])):
                                    getURL.append(response['results'][i]['media'][j]['gif']['url'])
                            image_url = random.choice(getURL)
                            await session.close()

                welcome_embed.set_image(url=image_url)
                return await channel_to_send.send(embed=welcome_embed)

    async def send_leaver(self, member: discord.Member):
        if not member.bot:
            async with self.bot.db.acquire() as con:
                result = await con.fetch(f"SELECT channel_id FROM welcomers WHERE guild_id = {member.guild.id}")
            if not result:
                return
            else:
                info = result[0]

            member = member
            guild = member.guild
            channel_to_send = await self.bot.fetch_channel(info["channel_id"])
            leave_embed = discord.Embed(title=f"{member.display_name} left {guild.name}",
                                        description=f"{member.mention}, we're sad to see you go!",
                                        color=discord.Color.dark_red())
            leave_embed.set_thumbnail(url=member.avatar_url)
            leave_embed.set_image(url="https://media1.tenor.com/images/e69ebde3631408c200777ebe10f84367/tenor.gif?"
                                    "itemid=5081296")
            return await channel_to_send.send(embed=leave_embed)

    async def get_welcome_help(self, ctx) -> discord.Message:
        title = "Welcomer Help Menu"
        description = f"{ctx.author.mention}, the welcomer is used to greet new members of your server when they join. " \
            f"The base command is `{await gcmds.prefix(ctx)}welcomer [option]` *alias=welcome*. Here are the valid " \
            "options for `[option]`\n\n"
        create = f"**Usage:** `{await gcmds.prefix(ctx)}welcomer create`\n" \
            "**Returns:** An interactive setup panel that will create a working welcomer in your server\n" \
            "**Aliases:** `make` `start` `-c`\n" \
            "**Special Cases:** You will be unable to use this command if you already have a welcomer set up. If you" \
            " try to use this command when you already have a welcomer set up, it will automatically redirect you to " \
            "the interactive edit panel"
        edit = f"**Usage:** `{await gcmds.prefix(ctx)}welcomer edit`\n" \
            "**Returns:** An interactive setup panel that will edit your current welcomer\n" \
            "**Aliases:** `adjust` `modify` `-e`\n" \
            "**Special Cases:** You must have a welcomer currently set up in this server to use this command"
        delete = f"**Usage:** `{await gcmds.prefix(ctx)}welcomer delete`\n" \
            "**Returns:** A confirmation panel that will delete your current welcomer if you choose to do so\n" \
            "**Aliases:** `trash` `cancel` `-rm`\n" \
            "**Special Cases:** You must have a welcomer currently set up in this server to use this command"
        test = (f"**Usage:** `{await gcmds.prefix(ctx)}welcomer test`\n"
                "**Returns:** A test welcomer in your currently set welcome channel")
        fields = [("Create", create), ("Edit", edit), ("Delete", delete), ("Test", test)]

        embed = discord.Embed(title=title,
                              description=description,
                              color=discord.Color.blue())
        for name, value in fields:
            embed.add_field(name=name,
                            value=value,
                            inline=False)
        return await ctx.channel.send(embed=embed)

    async def check_panel(self, panel: discord.Message) -> bool:
        try:
            if panel.id:
                return True
            else:
                return False
        except Exception:
            return False

    async def get_panel_embed(self, panel: discord.Message) -> discord.Message:
        try:
            if not await self.check_panel(panel):
                return False
            if panel.embeds:
                return panel.embeds[0]
            else:
                return False
        except Exception:
            return False

    async def edit_panel(self, ctx, panel: discord.Message, title: str = None,
                         description: str = None, color: discord.Color = None) -> bool:
        try:
            panel_embed = await self.get_panel_embed(panel)
            if not panel_embed:
                return False
            if not color:
                if title:
                    panel_embed.title = title
                if description:
                    panel_embed.description = description
            else:
                if title:
                    embed_title = title
                else:
                    embed_title = panel_embed.title
                if description:
                    embed_description = description
                else:
                    embed_description = panel_embed.description
                panel_embed = discord.Embed(title=embed_title,
                                            description=embed_description,
                                            color=color)
            await panel.edit(embed=panel_embed)
            return True
        except Exception:
            return False

    async def create_welcomer(self, ctx, channel_id: int, title: str = None,
                              description: str = None, media: list = None) -> bool:
        try:
            title = f"'{title}'" if title else "'New Member Joined!'"
            description = f"'{description}'" if description else "'Welcome to {server_name}! {user_mention} is our {member_count_ord} member!'"
            media = "'{" + '", "'.join(media) + "}'::text[]" if media else "NULL"
            values = f"VALUES ({ctx.guild.id}, {channel_id}, {title}, {description}, {media}, false)"

            async with self.bot.db.acquire() as con:
                await con.execute(f"INSERT INTO welcomers(guild_id, channel_id, title, description, media, leaver) {values}")
            return True
        except Exception:
            return False

    async def has_welcomer(self, ctx):
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT * FROM welcomers WHERE guild_id = {ctx.guild.id}")
        return True if result else False

    async def get_welcomer(self, ctx) -> list:
        if not await self.has_welcomer(ctx):
            return None

        async with self.bot.db.acquire() as con:
            info = (await con.fetch(f"SELECT * FROM welcomers WHERE guild_id = {ctx.guild.id}"))[0]
        return [info['channel_id'], info['title'], info['description'], info['media']]

    async def edit_welcomer(self, ctx, channel_id: int, title: str, description: str, media=None) -> bool:
        op = []
        if channel_id:
            op.append(f"channel_id = {channel_id}")
        op.append(f"title = '{title}'") if title else op.append(f"title = 'New Member Joined!'")
        op.append(f"description = '{description}'") if description else op.append(
            "description = 'Welcome to {server_name}! {user_mention} is our {member_count_ord} member!'"
            )
        if media:
            if media == "default":
                op.append("media = NULL")
            else:
                values = "'{\"" + '", "'.join(media) + "\"}'"
                op.append(f"media = {values}")

        try:
            async with self.bot.db.acquire() as con:
                await con.execute(f"UPDATE welcomers SET {', '.join(op)} WHERE guild_id = {ctx.guild.id}")
            return True
        except Exception:
            return False

    async def no_welcomer(self, ctx) -> discord.Message:
        embed = discord.Embed(title="No Welcomer Set",
                              description=f"{ctx.author.mention}, no welcomer is set to display for this server",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def delete_welcomer(self, ctx) -> bool:
        try:
            async with self.bot.db.acquire() as con:
                await con.execute(f"DELETE FROM welcomers WHERE guild_id = {ctx.guild.id}")
            return True
        except Exception:
            return False

    async def get_leaver_help(self, ctx) -> discord.Message:
        title = "Leaver Help"
        description = (f"{ctx.author.mention}, the leaver function will automatically send a goodbye message in the "
                       f"welcomer's channel once a member leaves the server. The base command is "
                       f"`{await gcmds.prefix(ctx)}leaver [option]`. Here are the valid options for `[option]`\n\n")
        create = (f"**Usage:** `{await gcmds.prefix(ctx)}leaver create`\n"
                  "**Returns:** An embed that details the status of the leaver creation\n"
                  "**Aliases:** `-c` `make` `start`\n"
                  "**Special Cases:** Only works if there is a welcomer set up")
        delete = (f"**Usage:** `{await gcmds.prefix(ctx)}leaver delete`\n"
                  "**Returns:** An embed that details the status of the leaver deletion\n"
                  "**Aliases:** `-rm` `trash` `cancel`\n"
                  "**Special Cases:** Only works if there is a welcomer and leaver set up")
        test = (f"**Usage:** `{await gcmds.prefix(ctx)}leaver test`\n"
                "**Returns:** A test leaver in your currently set welcome channel")
        fields = [("Create", create), ("Delete", delete), ("Test", test)]
        embed = discord.Embed(title=title,
                              description=description,
                              color=discord.Color.blue())
        for name, value in fields:
            embed.add_field(name=name,
                            value=value,
                            inline=False)
        return await ctx.channel.send(embed=embed)

    async def create_leaver(self, ctx) -> bool:
        if await self.has_leaver(ctx):
            return False
        else:
            try:
                async with self.bot.db.acquire() as con:
                    await con.execute(f"UPDATE welcomers SET leaver = TRUE WHERE guild_id = {ctx.guild.id}")
                return True
            except Exception:
                return False

    async def has_leaver(self, ctx) -> bool:
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT leaver FROM welcomers WHERE guild_id = {ctx.guild.id} AND leaver = TRUE")
        return True if result else False

    async def no_leaver(self, ctx) -> discord.Message:
        embed = discord.Embed(title="No Leaver Set",
                              description=f"{ctx.author.mention}, you don't have a leaver set up for this server yet",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def delete_leaver(self, ctx) -> bool:
        try:
            async with self.bot.db.acquire() as con:
                await con.execute(f"UPDATE welcomers SET leaver = FALSE WHERE guild_id = {ctx.guild.id}")
            return True
        except Exception:
            return False

    @commands.group(invoke_without_command=True,
                    aliases=['welcome'],
                    desc="Displays the help command for welcomer",
                    usage="welcomer")
    async def welcomer(self, ctx):
        return await self.get_welcome_help(ctx)

    @welcomer.command(aliases=['make', 'start', '-c'])
    @commands.has_permissions(manage_guild=True)
    async def create(self, ctx):
        if await self.has_welcomer(ctx):
            await ctx.invoke(self.edit)
            return

        def from_user(message: discord.Message) -> bool:
            if message.author.id == ctx.author.id and message.channel.id == ctx.channel.id:
                return True
            else:
                return False

        panel_embed = discord.Embed(title="Welcomer Setup Panel",
                                    description=f"{ctx.author.mention}, this is the interactive welcomer setup panel. "
                                    "Follow all the prompts and you will have a fully functioning welcomer in no time!",
                                    color=discord.Color.blue())
        panel_embed.set_footer(text="Cancel anytime by entering \"cancel\"")
        panel = await ctx.channel.send(embed=panel_embed)

        or_default = "or type *\"skip\"* to use the default value"
        cmd_title = "welcomer setup"
        await asyncio.sleep(5.0)

        description = f"{ctx.author.mention}, please tag or enter the ID of the channel that you would like " \
            "the welcomer to send messages in"

        # User provides the channel that the welcome embed will be sent in
        while True:
            try:
                edit_success = await self.edit_panel(ctx, panel, title=None, description=description)
                if not edit_success:
                    return await gcmds.panel_deleted(gcmds, ctx, cmd_title)
                result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
            except asyncio.TimeoutError:
                return await gcmds.timeout(ctx, cmd_title, timeout)
            if re.match(channel_tag_rx, result.content):
                channel_id = result.content[2:20]
                break
            elif re.match(channel_id_rx, result.content):
                channel_id = result.content
                break
            elif result.content == "cancel":
                return await gcmds.cancelled(ctx, cmd_title)
            else:
                continue
        await gcmds.smart_delete(result)

        description = f"{ctx.author.mention}, please enter the title of the welcome embed, {or_default}\n\n" \
            "Default Value: New Member Joined!"

        # User provides welcome embed title
        try:
            edit_success = await self.edit_panel(ctx, panel, title=None, description=description)
            if not edit_success:
                return await gcmds.panel_deleted(gcmds, ctx, cmd_title)
            result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, cmd_title, timeout)
        if result.content == "cancel":
            return await gcmds.cancelled(ctx, cmd_title)
        elif result.content == "skip":
            embed_title = None
        else:
            embed_title = result.content
        await gcmds.smart_delete(result)

        bot_count = 0
        for member in ctx.guild.members:
            if member.bot:
                bot_count += 1

        description = f"{ctx.author.mention}, please enter the description of the welcome embed, {or_default}\n\n" \
            "Default Value: Welcome to {server_name}! {user_mention} is our {member_count_ord} member!\n\n" \
            "Variables Supported:\n" \
            "`{server_name}` ⟶ Your server's name ⟶ " + f"{ctx.guild.name}\n" \
            "`{user_name}` ⟶ The name of the user that just joined ⟶ " + f"{ctx.author.display_name}\n" \
            "`{user_mention}` ⟶ The mention for the user that just joined ⟶ " + f"{ctx.author.mention}\n" \
            "`{member_count}` ⟶ The number of members in this server ⟶ " + f"{int(len(ctx.guild.members) - bot_count)}\n" \
            "`{member_count_ord}` ⟶ The ordinal number of members in this server ⟶ " \
            f"{num2words((len(ctx.guild.members) - bot_count), to='ordinal_num')}"

        # User provides welcome embed description
        try:
            edit_success = await self.edit_panel(ctx, panel, title=None, description=description)
            if not edit_success:
                return await gcmds.panel_deleted(gcmds, ctx, cmd_title)
            result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, cmd_title, timeout)
        if result.content == "cancel":
            return await gcmds.cancelled(ctx, cmd_title)
        elif result.content == "skip":
            embed_description = None
        else:
            embed_description = result.content
        await gcmds.smart_delete(result)

        # User provides media links
        url_list = []
        while True:
            if not url_list:
                formatted_urls = ""
            else:
                formatted_urls = '\n==============\n'.join(url_list)
            description = f"{ctx.author.mention}, you can set custom images or gifs to be sent in the welcomer message " \
                f"when someone joins this server. Please enter a valid image URL *(.png, .jpg, .gif)*, {or_default}." \
                f" Enter *\"finish\"* to finish adding URLs\n\nCurrent URLs:\n {formatted_urls}"
            try:
                edit_success = await self.edit_panel(ctx, panel, title=None, description=description)
                if not edit_success:
                    return await gcmds.panel_deleted(gcmds, ctx, cmd_title)
                result = await self.bot.wait_for("message", check=from_user, timeout=120)
            except asyncio.TimeoutError:
                return await gcmds.timeout(ctx, cmd_title, 120)
            if result.content == "cancel":
                return await gcmds.cancelled(ctx, cmd_title)
            elif result.content == "skip":
                url_list = None
                break
            elif result.content == "finish":
                break
            else:
                mimetype, encoding = mimetypes.guess_type(result.content)
                if mimetype and mimetype in ["image/gif", "image/jpeg", "image/jpg", "image/png"]:
                    url_list.append(result.content)
                    await gcmds.smart_delete(result)
                continue
        await gcmds.smart_delete(result)

        succeeded = await self.create_welcomer(ctx, channel_id, embed_title, embed_description, url_list)
        if succeeded:
            title = "Successfully Created Welcomer"
            description = f"{ctx.author.mention}, your welcomer will be fired at <#{channel_id}> every time a new " \
                "member joins your server!"
            edit_success = await self.edit_panel(ctx, panel, title=title, description=description)
            if not edit_success:
                embed = discord.Embed(title=title,
                                      description=description,
                                      color=discord.Color.blue())
                return await ctx.channel.send(embed=embed)
        else:
            title = "Could Not Create Welcomer"
            description = f"{ctx.author.mention}, there was a problem creating your welcomer"
            edit_success = await self.edit_panel(ctx, panel, title=title, description=description,
                                                 color=discord.Color.dark_red())
            if not edit_success:
                embed = discord.Embed(title=title,
                                      description=description,
                                      color=discord.Color.dark_red())
                return await ctx.channel.send(embed=embed)

    @welcomer.command(aliases=['adjust', 'modify', '-e'])
    @commands.has_permissions(manage_guild=True)
    async def edit(self, ctx):
        info = await self.get_welcomer(ctx)
        if not info:
            return await self.no_welcomer(ctx)

        cmd_title = "welcomer edit"
        or_default = "type *\"skip\"* to use the currently set value, or type *\"default\"* to use the default value"

        def from_user(message: discord.Message) -> bool:
            if message.author.id == ctx.author.id and message.channel.id == ctx.channel.id:
                return True
            else:
                return False

        if not info[3]:
            media = "Current Images: Default"
        else:
            media = "Current Images:\n" + '\n==============\n'.join(info[3])

        # Display the current welcomer
        temp_welcomer_embed = discord.Embed(title=info[1],
                                            description=info[2] + "\n\n" + media,
                                            color=discord.Color.blue())
        temp_welcomer = await ctx.channel.send(embed=temp_welcomer_embed)

        panel_embed = discord.Embed(title="Welcomer Edit Setup",
                                    description=f"{ctx.author.mention}, this welcomer edit panel will walk you through "
                                    "editing your current server welcome message",
                                    color=discord.Color.blue())
        panel_embed.set_footer(text="Type \"cancel\" to cancel at any time")
        panel = await ctx.channel.send(embed=panel_embed)

        await asyncio.sleep(5)

        description = "Please tag or enter the ID of the channel you would like MarwynnBot to send the welcomer" \
            f" message, {or_default}\n\nCurrent Channel: <#{info[0]}>"

        # Get channel ID from user
        while True:
            try:
                edit_success = await self.edit_panel(ctx, panel, title=None, description=description)
                if not edit_success:
                    return await gcmds.panel_deleted(gcmds, ctx, cmd_title)
                result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
            except asyncio.TimeoutError:
                return await gcmds.timeout(ctx, cmd_title, timeout)
            if result.content == "cancel":
                try:
                    await temp_welcomer.delete()
                except Exception:
                    pass
                return await gcmds.cancelled(ctx, cmd_title)
            elif result.content == "skip" or result.content == "default":
                new_channel_id = info[0]
                break
            elif re.match(result.content, channel_tag_rx):
                new_channel_id = result.content[2:20]
                break
            elif re.match(result.content, channel_id_rx):
                new_channel_id = result.content
                break
            else:
                continue
        await gcmds.smart_delete(result)

        description = f"{ctx.author.mention}, please enter the title of the welcomer you would like " \
            f"MarwynnBot to display, {or_default}\n\nCurrent Title: {info[1]}"

        # Get title from user
        try:
            edit_success = await self.edit_panel(ctx, panel, title=None, description=description)
            if not edit_success:
                return await gcmds.panel_deleted(gcmds, ctx, cmd_title)
            result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, cmd_title, timeout)
        if result.content == "cancel":
            try:
                await temp_welcomer.delete()
            except Exception:
                pass
            return await gcmds.cancelled(ctx, cmd_title)
        elif result.content == "skip":
            new_title = info[1]
        elif result.content == "default":
            new_title = None
        else:
            new_title = result.content
        await gcmds.smart_delete(result)

        # Update temp_welcomer

        try:
            temp_welcomer_embed.title = new_title
            await temp_welcomer.edit(embed=temp_welcomer_embed)
        except (discord.NotFound, discord.HTTPException, discord.Forbidden):
            return await gcmds.cancelled(ctx, cmd_title)

        # Edit panel description
        bot_count = 0
        for member in ctx.guild.members:
            if member.bot:
                bot_count += 1

        desc_variables = "Variables Supported:\n" \
            "`{server_name}` ⟶ Your server's name ⟶ " + f"{ctx.guild.name}\n" \
            "`{user_name}` ⟶ The name of the user that just joined ⟶ " + f"{ctx.author.display_name}\n" \
            "`{user_mention}` ⟶ The mention for the user that just joined ⟶ " + f"{ctx.author.mention}\n" \
            "`{member_count}` ⟶ The number of members in this server ⟶ " + f"{int(len(ctx.guild.members) - bot_count)}\n" \
            "`{member_count_ord}` ⟶ The ordinal number of members in this server ⟶ " \
            f"{num2words((len(ctx.guild.members) - bot_count), to='ordinal_num')}"

        description = "Please enter the description of the welcomer message you would like MarwynnBot to" \
            f" display, {or_default}\n\nCurrent Description: {info[2]}\n\n{desc_variables}"

        # Get desription from user
        try:
            edit_success = await self.edit_panel(ctx, panel, title=None, description=description)
            if not edit_success:
                return await gcmds.panel_deleted(gcmds, ctx, cmd_title)
            result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, cmd_title, timeout)
        if result.content == "cancel":
            try:
                await temp_welcomer.delete()
            except Exception:
                pass
            return await gcmds.cancelled(ctx, cmd_title)
        elif result.content == "skip":
            new_description = info[2]
        elif result.content == "default":
            new_description = None
        else:
            new_description = result.content
        await gcmds.smart_delete(result)

        # User provides media links
        url_list = []
        while True:
            if not url_list:
                formatted_urls = ""
            else:
                formatted_urls = '\n==============\n'.join(url_list)
            description = f"{ctx.author.mention}, you can set custom images or gifs to be sent in the welcomer message " \
                f"when someone joins this server. Please enter a valid image URL *(.png, .jpg, .gif)*, {or_default}." \
                f" Enter *\"finish\"* to finish adding URLs\n\nCurrent URLs:\n {formatted_urls}"
            try:
                edit_success = await self.edit_panel(ctx, panel, title=None, description=description)
                if not edit_success:
                    return await gcmds.panel_deleted(gcmds, ctx, cmd_title)
                result = await self.bot.wait_for("message", check=from_user, timeout=120)
            except asyncio.TimeoutError:
                return await gcmds.timeout(ctx, cmd_title, 120)
            if result.content == "cancel":
                try:
                    await temp_welcomer.delete()
                except Exception:
                    pass
                return await gcmds.cancelled(ctx, cmd_title)
            elif result.content == "skip":
                url_list = None
                break
            elif result.content == "default":
                url_list = "default"
                break
            elif result.content == "finish":
                break
            else:
                mimetype, encoding = mimetypes.guess_type(result.content)
                if mimetype and mimetype in ["image/gif", "image/jpeg", "image/jpg", "image/png"]:
                    url_list.append(result.content)
                await gcmds.smart_delete(result)
                continue
        await gcmds.smart_delete(result)

        succeeded = await self.edit_welcomer(ctx, new_channel_id, new_title, new_description, url_list)
        await temp_welcomer.delete()
        if succeeded:
            title = "Successfully Edited Welcomer"
            description = f"{ctx.author.mention}, your welcomer will be fired at <#{new_channel_id}> every time a new " \
                "member joins your server!"
            edit_success = await self.edit_panel(ctx, panel, title=title, description=description)
            if not edit_success:
                embed = discord.Embed(title=title,
                                      description=description,
                                      color=discord.Color.blue())
                return await ctx.channel.send(embed=embed)
        else:
            title = "Could Not Edit Welcomer"
            description = f"{ctx.author.mention}, there was a problem editing your welcomer"
            edit_success = await self.edit_panel(ctx, panel, title=title, description=description,
                                                 color=discord.Color.dark_red())
            if not edit_success:
                embed = discord.Embed(title=title,
                                      description=description,
                                      color=discord.Color.dark_red())
                return await ctx.channel.send(embed=embed)

    @welcomer.command(aliases=['-rm', 'trash', 'cancel'])
    @commands.has_permissions(manage_guild=True)
    async def delete(self, ctx):
        info = await self.get_welcomer(ctx)
        if not info:
            return await self.no_welcomer(ctx)

        reactions = ["✅", "🛑"]
        cmd_title = "welcomer delete"

        panel_embed = discord.Embed(title="Confirm Welcomer Delete",
                                    description=f"{ctx.author.mention}, please react with ✅ to delete this server's "
                                    "welcomer message or react with 🛑 to cancel",
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)
        for reaction in reactions:
            await panel.add_reaction(reaction)

        def user_reacted(reaction: discord.Reaction, user: discord.User) -> bool:
            if reaction.emoji in reactions and user.id == ctx.author.id and \
                    reaction.message.id == panel.id and not user.bot:
                return True
            else:
                return False

        # Get confirmation from user
        while True:
            try:
                result = await self.bot.wait_for("reaction_add", check=user_reacted, timeout=timeout)
            except asyncio.TimeoutError:
                return await gcmds.timeout(ctx, cmd_title, timeout)
            if result[0].emoji in reactions:
                break
            else:
                continue
        await panel.clear_reactions()

        if result[0].emoji == "✅":
            succeeded = await self.delete_welcomer(ctx)
            if succeeded:
                title = "Successfully Deleted Welcomer"
                description = f"{ctx.author.mention}, your welcomer was successfully deleted"
                edit_success = await self.edit_panel(ctx, panel, title=title, description=description)
                if not edit_success:
                    embed = discord.Embed(title=title,
                                          description=description,
                                          color=discord.Color.blue())
                    return await ctx.channel.send(embed=embed)
        else:
            title = "Could Not Delete Welcomer"
            description = f"{ctx.author.mention}, there was a problem deleting your welcomer"
            edit_success = await self.edit_panel(ctx, panel, title=title, description=description,
                                                 color=discord.Color.dark_red())
            if not edit_success:
                embed = discord.Embed(title=title,
                                      description=description,
                                      color=discord.Color.dark_red())
                return await ctx.channel.send(embed=embed)

    @welcomer.command()
    @commands.has_permissions(manage_guild=True)
    async def test(self, ctx):
        await self.send_welcomer(ctx.author)

    @commands.group(invoke_without_command=True,
                    desc="Displays the help command for leaver",
                    usage="leaver")
    async def leaver(self, ctx):
        return await self.get_leaver_help(ctx)

    @leaver.command(aliases=['-c', 'make', 'start', 'create'])
    @commands.has_permissions(manage_guild=True)
    async def _create(self, ctx):
        welcomer = await self.get_welcomer(ctx)
        if not welcomer:
            return await self.no_welcomer(ctx)

        if await self.has_leaver(ctx):
            embed = discord.Embed(title="Leaver Already Set",
                                  description=f"{ctx.author.mention}, this server already has a leaver set up",
                                  color=discord.Color.dark_red())
            return await ctx.channel.send(embed=embed)

        def from_user(message: discord.Message) -> bool:
            if message.author.id == ctx.author.id and message.channel.id == ctx.channel.id:
                return True
            else:
                return False

        channel_id = welcomer[0]

        succeeded = await self.create_leaver(ctx)
        if succeeded:
            embed = discord.Embed(title="Leaver Successfully Created",
                                  description=f"{ctx.author.mention}, a leaver has been set for this server. It will "
                                  "fire in the same channel as the welcomer",
                                  color=discord.Color.blue())
        else:
            embed = discord.Embed(title="Leaver Creation Failed",
                                  description=f"{ctx.author.mention}, the leaver could not be set for this server",
                                  color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    @leaver.command(aliases=['-rm', 'cancel', 'trash', 'delete'])
    @commands.has_permissions(manage_guild=True)
    async def _delete(self, ctx):
        if not await self.has_leaver(ctx):
            return await self.no_leaver(ctx)

        succeeded = await self.delete_leaver(ctx)
        if succeeded:
            embed = discord.Embed(title="Leaver Successfully Deleteed",
                                  description=f"{ctx.author.mention}, your leaver for this server has been deleted",
                                  color=discord.Color.blue())
        else:
            embed = discord.Embed(title="Leaver Deletion Failed",
                                  description=f"{ctx.author.mention}, the leaver for this server could not be deleted",
                                  color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    @leaver.command(aliases=['test'])
    @commands.has_permissions(manage_guild=True)
    async def _test(self, ctx):
        await self.send_leaver(ctx.author)


def setup(bot):
    bot.add_cog(Welcome(bot))
