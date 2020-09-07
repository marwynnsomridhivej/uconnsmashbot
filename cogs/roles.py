import discord
from discord.ext import commands
from globalcommands import GlobalCMDS
import asyncio
import json
import re
import os

gcmds = GlobalCMDS()
role_names = ["Wi-Fi Warriors", "Netplay $quad", "PP Gang", "Not a UConn Student"]
newline = '\n'
channel_tag_rx = re.compile(r'<#[0-9]{18}>')
channel_id_rx = re.compile(r'[0-9]{18}')
role_tag_rx = re.compile(r'<@&[0-9]{18}>')
hex_color_rx = re.compile(r'#[A-Fa-f0-9]{6}')
timeout = 60
gcmds.json_load('db/reactionroles.json', {})
with open('db/reactionroles.json', 'r') as rr:
    rr_json = json.load(rr)

class Roles(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not os.path.exists('db/reactionroles.json'):
            return
        with open('db/reactionroles.json', 'r') as f:
            file = json.load(f)
            f.close()
        member = payload.member
        if not member:
            return
        guild_id = payload.guild_id
        event_type = payload.event_type

        if not member.bot and event_type == "REACTION_ADD" and str(guild_id) in file.keys():
            reacted_emoji = payload.emoji
            message_id = payload.message_id
            channel_id = payload.channel_id
            channel = await self.client.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
            reactions = message.reactions
            guild = await commands.AutoShardedBot.fetch_guild(self.client, guild_id)
            try:
                users = [(reaction.emoji, await reaction.users().flatten()) for reaction in reactions]
                role_emoji = rr_json[str(guild_id)][str(message_id)]
                type_name = role_emoji['type']
                for item in role_emoji['details']:
                    role = guild.get_role(int(item['role_id']))
                    if str(reacted_emoji) == str(item['emoji']):
                        if type_name == "normal" or type_name == "single_normal":
                            if role not in member.roles:
                                await member.add_roles(role)
                        if type_name == "reverse":
                            if role in member.roles:
                                await member.remove_roles(role)
                    elif str(reacted_emoji) != str(item['emoji']) and type_name == "single_normal":
                        if role in member.roles:
                            await member.remove_roles(role)
                if type_name == "single_normal":
                    for emoji, user in users:
                        if str(emoji) != str(reacted_emoji):
                            for reacted in user:
                                if member.id == reacted.id:
                                    await message.remove_reaction(emoji, member)
            except (discord.Forbidden, discord.NotFound, KeyError):
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        with open('db/reactionroles.json', 'r') as f:
            file = json.load(f)
            f.close()
        guild_id = payload.guild_id
        guild = await commands.AutoShardedBot.fetch_guild(self.client, guild_id)
        member_id = payload.user_id
        member = await guild.fetch_member(member_id)
        event_type = payload.event_type
        if not member.bot and event_type == "REACTION_REMOVE" and str(guild_id) in file.keys():
            reacted_emoji = payload.emoji
            message_id = payload.message_id
            try:
                role_emoji = rr_json[str(guild_id)][str(message_id)]
                type_name = role_emoji['type']
                for item in role_emoji['details']:
                    role = guild.get_role(int(item['role_id']))
                    if str(reacted_emoji) == str(item['emoji']):
                        if type_name == "normal" or type_name == "single_normal":
                            if role in member.roles:
                                await member.remove_roles(role)
                        if type_name == "reverse":
                            if role not in member.roles:
                                await member.add_roles(role)
            except (discord.Forbidden, discord.NotFound, KeyError):
                pass

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            return await self.no_panel(ctx)
        else:
            raise error

    async def check_panel(self, panel: discord.Message) -> discord.Message:
        return panel

    async def edit_panel(self, panel_embed: discord.Embed, panel: discord.Message,
                         title: str = None, description: str = None) -> discord.Message:
        if title:
            panel_embed.title = title
        if description:
            panel_embed.description = description
        return await panel.edit(embed=panel_embed)

    async def no_panel(self, ctx) -> discord.Message:
        embed = discord.Embed(title="Reacton Roles Setup Cancelled",
                              description=f"{ctx.author.mention}, the reaction roles setup was cancelled because the "
                                          f"setup panel was deleted or could not be found",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def no_message(self, ctx) -> discord.Message:
        embed = discord.Embed(title="No Message Found",
                              description=f"{ctx.author.mention}, no reaction roles panel was found for that message ID",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed, delete_after=5)

    async def user_cancelled(self, ctx, panel: discord.Message) -> discord.Message:
        embed = discord.Embed(title="Reaction Roles Setup Cancelled",
                              description=f"{ctx.author.mention}, you have cancelled reaction roles setup",
                              color=discord.Color.dark_red())
        panel_message = await self.check_panel(panel)
        if not panel_message:
            return await ctx.channel.send(embed=embed, delete_after=10)
        else:
            return await panel_message.edit(embed=embed, delete_after=10)

    async def timeout(self, ctx, timeout: int, panel: discord.Message) -> discord.Message:
        embed = discord.Embed(title="Reaction Roles Setup Cancelled",
                              description=f"{ctx.author.mention}, the reaction roles setup was canelled because you "
                                          f"did not provide a valid action within {timeout} seconds",
                              color=discord.Color.dark_red())
        panel_message = await self.check_panel(panel)
        if not panel_message:
            return await ctx.channel.send(embed=embed, delete_after=10)
        else:
            return await panel_message.edit(embed=embed, delete_after=10)

    async def success(self, ctx, success_str: str) -> discord.Message:
        embed = discord.Embed(title=f"Successfully {success_str.title()} Reaction Role Panel",
                              description=f"{ctx.author.mention}, your reaction role panel was successfully"
                                          f" {success_str}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    async def failure(self, ctx, success_str: str) -> discord.Message:
        embed = discord.Embed(title=f"Failed to {success_str.title()} Reaction Role Panel",
                              description=f"{ctx.author.mention}, your reaction role panel could not be"
                                          f" {success_str}ed",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def send_rr_message(self, ctx, channel: discord.TextChannel, send_embed: discord.Embed, emoji_list: list,
                              role_emoji: list, type_name: str):
        rr_message = await channel.send(embed=send_embed)
        for emoji in emoji_list:
            await rr_message.add_reaction(emoji)
        init = {str(ctx.guild.id): {str(rr_message.id): {"type": type_name, "details": []}}}
        gcmds.json_load('db/reactionroles.json', init)
        with open('db/reactionroles.json', 'r') as f:
            file = json.load(f)
            f.close()
        file.update({str(ctx.guild.id): {}})
        file.update({str(ctx.guild.id): {str(rr_message.id): {}}})
        file[str(ctx.guild.id)].update({str(rr_message.id): {"type": type_name, "author": str(ctx.author.id),
                                                             "details": []}})
        for role, emoji in role_emoji:
            file[str(ctx.guild.id)][str(rr_message.id)]['details'].append({"role_id": str(role), "emoji": str(emoji)})
        with open('db/reactionroles.json', 'w') as g:
            json.dump(file, g, indent=4)

    async def edit_rr_message(self, ctx, message_id: int, guild_id: int, title: str, description: str, color: str,
                              emoji_list, emoji_role_list, type_name):
        for text_channel in ctx.guild.text_channels:
            try:
                message = await text_channel.fetch_message(message_id)
                break
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        embed = discord.Embed(title=title,
                              description=description,
                              color=color)
        try:
            await message.edit(embed=embed)
        except discord.NotFound:
            return await self.failure(ctx, "edit")

        if emoji_list or emoji_role_list or type_name:
            with open('db/reactionroles.json', 'r') as f:
                file = json.load(f)
                f.close()

        if emoji_list and emoji_role_list:
            await message.clear_reactions()
            for emoji in emoji_list:
                await message.add_reaction(emoji)
            file[str(guild_id)][str(message_id)]['details'] = []
            for role, emoji in emoji_role_list:
                file[str(ctx.guild.id)][str(message_id)]['details'].append({"role_id": str(role), "emoji": str(emoji)})
        if type_name:
            file[str(guild_id)][str(message_id)]['type'] = type_name

    async def check_rr_author(self, message_id: int, user_id: int, guild_id: int) -> bool:
        with open('db/reactionroles.json', 'r') as f:
            file = json.load(f)
            f.close()
        try:
            if file[str(guild_id)][str(message_id)]['author'] == str(user_id):
                return True
            else:
                return False
        except KeyError:
            return False

    async def check_rr_exists(self, ctx, message_id: int, guild_id: int):
        with open('db/reactionroles.json', 'r') as f:
            file = json.load(f)
            f.close()
        try:
            if str(message_id) in file[str(guild_id)].keys() and await self.get_rr_info(ctx, message_id):
                return True
            else:
                del file[str(guild_id)][str(message_id)]
                if len(file[str(guild_id)]) == 0:
                    del file[str(guild_id)]
                with open('db/reactionroles.json', 'w') as g:
                    json.dump(file, g, indent=4)
        except KeyError:
            return False

    async def get_rr_info(self, ctx, message_id: int) -> discord.Embed:
        found = False
        for text_channel in ctx.guild.text_channels:
            try:
                message = await text_channel.fetch_message(message_id)
                found = True
                break
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        if found:
            embed = message.embeds[0]
            return embed
        else:
            return None

    async def delete_rr_message(self, ctx, message_id: int, guild_id: int):
        found = False
        for text_channel in ctx.guild.text_channels:
            try:
                message = await text_channel.fetch_message(message_id)
                found = True
                break
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        if found:
            title = "Successfully Deleted Reaction Role"
            description = f"{ctx.author.mention}, I have deleted the reaction roles panel and cleared the record from " \
                          f"my database "
            color = discord.Color.blue()
            try:
                await message.delete()
            except discord.Forbidden:
                title = "404 Forbidden"
                description = f"{ctx.author}, I could not delete the reaction roles panel"
                color = discord.Color.dark_red()

            with open('db/reactionroles.json', 'r') as f:
                file = json.load(f)
                f.close()
            try:
                del file[str(guild_id)][str(message_id)]
                if len(file[str(guild_id)]) == 0:
                    del file[str(guild_id)]
                with open('db/reactionroles.json', 'w') as g:
                    json.dump(file, g, indent=4)
            except KeyError:
                pass
            embed = discord.Embed(title=title,
                                  description=description,
                                  color=color)
            return await ctx.channel.send(embed=embed)

    async def get_rr_type(self, message_id: int, guild_id: int) -> str:
        with open('db/reactionroles.json', 'r') as f:
            file = json.load(f)
            f.close()
        return file[str(guild_id)][str(message_id)]['type'].replace("_", " ").title()

    @commands.group(aliases=['rr'])
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True)
    @commands.has_permissions(manage_guild=True)
    async def reactionrole(self, ctx):
        if not ctx.invoked_subcommand:
            message_id_message = f"The `[messageID]` argument must be the message ID of a reaction " \
                                 f"roles panel that you have created. You will be unable to edit the panel if you " \
                                 f"provide an invalid message ID or provide a message ID of a panel that was " \
                                 f"not created by you"
            embed = discord.Embed(title="ReactionRoles Help Menu",
                                  description=f"All reaction roles commands can be accessed using "
                                              f"`?reactionrole [option]`. "
                                              f"Below is a list of all the valid options",
                                  color=discord.Color.blue())
            embed.add_field(name="Create",
                            value=f"**Usage:** `?reactionrole create`\n"
                                  f"**Returns:** Interactive reaction roles setup panel\n"
                                  f"**Aliases:** `-c` `start` `make`")
            embed.add_field(name="Edit",
                            value=f"**Usage:** `?reactionrole edit [messageID]`\n"
                                  f"**Returns:** Interactive reaction roles edit panel\n"
                                  f"**Aliases:** `-e` `adjust`\n"
                                  f"**Special Cases:** {message_id_message}",
                            inline=False)
            embed.add_field(name="Delete",
                            value=f"**Usage:** `?reactionrole delete [messageID]`\n"
                                  f"**Returns:** Message that details status of the deletion\n"
                                  f"**Aliases:** `-d` `-rm` `del`\n"
                                  f"**Special Cases:** {message_id_message}. If the panel was manually deleted, "
                                  f"I will delete the panel's record from its database of reaction role panels",
                            inline=False)
            embed.add_field(name="Useful Resources",
                            value="**Hex Color Picker:** https://www.google.com/search?q=color+picker",
                            inline=False)
            return await ctx.channel.send(embed=embed)

    @reactionrole.command(aliases=['-c', 'start', 'make'])
    async def create(self, ctx):

        panel_embed = discord.Embed(title="Reaction Role Setup Menu",
                                    description=f"{ctx.author.mention}, welcome to my reaction role setup "
                                                f"menu. Just follow the prompts and you will have a working reaction "
                                                f"roles panel!",
                                    color=discord.Color.blue())
        panel_embed.set_footer(text="Type \"cancel\" to cancel at any time")
        panel = await ctx.channel.send(embed=panel_embed)

        await asyncio.sleep(5.0)

        def from_user(message: discord.Message) -> bool:
            if message.author == ctx.author and message.channel == ctx.channel:
                return True
            else:
                return False

        def panel_react(reaction: discord.Reaction, user: discord.User) -> bool:
            if reaction.message.id == panel.id and ctx.author.id == user.id:
                return True
            else:
                return False

        # User will input the channel by tag
        while True:
            try:
                panel_message = await self.check_panel(panel)
                if not panel_message:
                    return await self.no_panel(ctx)
                await self.edit_panel(panel_embed, panel_message, title=None,
                                      description=f"{ctx.author.mention}, please tag the channel you would like the "
                                                  f"embed to be sent in (or type its ID)")
                result = await self.client.wait_for("message", check=from_user,
                                                                timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, timeout, panel)
            if not re.match(channel_tag_rx, result.content):
                if re.match(channel_id_rx, result.content):
                    channel_id = result.content
                    await result.delete()
                    break
                else:
                    if result.content == "cancel":
                        return await self.user_cancelled(ctx, panel_message)
                    continue
            else:
                channel_id = result.content[2:20]
            await result.delete()
            break

        channel = await commands.AutoShardedBot.fetch_channel(self.client, channel_id)

        # User will input the embed title
        try:
            panel_message = await self.check_panel(panel)
            if not panel_message:
                return await self.no_panel(ctx)
            await self.edit_panel(panel_embed, panel_message, title=None,
                                  description=f"{ctx.author.mention}, please enter the title of the embed that will "
                                              f"be sent")
            result = await self.client.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await self.timeout(ctx, timeout, panel)
        else:
            if result.content == "cancel":
                return await self.user_cancelled(ctx, panel_message)

        title = result.content
        await result.delete()

        # User will input the embed description
        try:
            panel_message = await self.check_panel(panel)
            if not panel_message:
                return await self.no_panel(ctx)
            await self.edit_panel(panel_embed, panel_message, title=None,
                                  description=f"{ctx.author.mention}, please enter the description of the embed that "
                                              f"will be sent")
            result = await self.client.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await self.timeout(ctx, timeout, panel)
        else:
            if result.content == "cancel":
                return await self.user_cancelled(ctx, panel_message)

        description = result.content
        await result.delete()

        # User will input the embed color
        while True:
            try:
                panel_message = await self.check_panel(panel)
                if not panel_message:
                    return await self.no_panel(ctx)
                await self.edit_panel(panel_embed, panel_message, title=None,
                                      description=f"{ctx.author.mention}, please enter the hex color of the embed "
                                                  f"that will be sent")
                result = await self.client.wait_for("message", check=from_user,
                                                                timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, timeout, panel)
            if not re.match(hex_color_rx, result.content):
                if result.content == "cancel":
                    return await self.user_cancelled(ctx, panel_message)
                else:
                    continue
            break

        color = int(result.content[1:], 16)
        await result.delete()

        # User will tag the role, then react with the corresponding emoji
        emoji_role_list = []
        emoji_list = []
        while True:
            while True:
                try:
                    panel_message = await self.check_panel(panel)
                    if not panel_message:
                        return await self.no_panel(ctx)
                    await self.edit_panel(panel_embed, panel_message, title=None,
                                          description=f"{ctx.author.mention}, please tag the role you would like to be "
                                                      f"added into the reaction role or type *finish* to finish setup")
                    result = await self.client.wait_for("message", check=from_user,
                                                                    timeout=timeout)
                except asyncio.TimeoutError:
                    return await self.timeout(ctx, timeout, panel)
                if not re.match(role_tag_rx, result.content):
                    if result.content == "cancel":
                        return await self.user_cancelled(ctx, panel_message)
                    elif result.content == "finish":
                        break
                    else:
                        continue
                else:
                    break
            if result.content == "finish":
                await result.delete()
                break

            role = result.content[3:21]
            await result.delete()

            while True:
                try:
                    panel_message = await self.check_panel(panel)
                    if not panel_message:
                        return await self.no_panel(ctx)
                    await self.edit_panel(panel_embed, panel_message, title=None,
                                          description=f"{ctx.author.mention}, please react to this panel with the emoji"
                                                      f" you want the user to react with to get the role <@&{role}>")
                    result = await self.client.wait_for("reaction_add", check=panel_react,
                                                                    timeout=timeout)
                except asyncio.TimeoutError:
                    return await self.timeout(ctx, timeout, panel)
                if result[0].emoji in emoji_list:
                    continue
                else:
                    break

            emoji = result[0].emoji
            emoji_list.append(emoji)
            await result[0].message.clear_reactions()

            emoji_role_list.append((role, emoji))

        # User will input number to dictate type of reaction role
        while True:
            try:
                panel_message = await self.check_panel(panel)
                if not panel_message:
                    return await self.no_panel(ctx)
                await self.edit_panel(panel_embed, panel_message, title=None,
                                      description=f"{ctx.author.mention}, please enter the number that corresponds to "
                                                  f"the type of reaction role behavior you would like\n\n"
                                                  f"**1:** Normal *(react to add, unreact to remove, multiple at a "
                                                  f"time)*\n "
                                                  f"**2:** Reverse *(react to remove, unreact to add, multiple at a "
                                                  f"time)*\n "
                                                  f"**3:** Single Normal *(same as normal, except you can only have one"
                                                  f" role at a time)*\n\n"
                                                  f"*If I wanted to pick `Normal`, I would type \"1\" as the response*")
                result = await self.client.wait_for("message", check=from_user,
                                                                timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, timeout, panel)
            else:
                if result.content == "cancel":
                    return await self.user_cancelled(ctx, panel_message)
                if result.content == "1":
                    type_name = "normal"
                    break
                if result.content == "2":
                    type_name = "reverse"
                    break
                if result.content == "3":
                    type_name = "single_normal"
                    break
                continue

        type_name = type_name
        await result.delete()
        await panel.delete()

        await self.success(ctx, "created")

        # Post reaction role panel in the channel
        rr_embed = discord.Embed(title=title,
                                 description=description,
                                 color=color)
        return await self.send_rr_message(ctx, channel, rr_embed, emoji_list, emoji_role_list, type_name)

    @reactionrole.command(aliases=['adjust', '-e'])
    async def edit(self, ctx, message_id: int = None):
        if not message_id:
            return await ctx.invoke(self.reactionrole)

        exists = await self.check_rr_exists(ctx, message_id, ctx.guild.id)
        if not exists:
            return await self.no_message(ctx)

        is_author = await self.check_rr_author(message_id, ctx.author.id, ctx.guild.id)
        if not is_author:
            not_author = discord.Embed(title="Not Panel Author",
                                       description=f"{ctx.author.mention}, you must be the author of that reaction "
                                                   f"roles panel to edit the panel",
                                       color=discord.Color.dark_red())
            return await ctx.channel.send(embed=not_author, delete_after=10)

        panel_embed = discord.Embed(title="Reaction Role Setup Menu",
                                    description=f"{ctx.author.mention}, welcome to my reaction role setup "
                                                f"menu. Just follow the prompts to edit your panel!",
                                    color=discord.Color.blue())
        panel_embed.set_footer(text="Type \"cancel\" to cancel at any time")
        panel = await ctx.channel.send(embed=panel_embed)

        await asyncio.sleep(5.0)

        old_embed = await self.get_rr_info(ctx, message_id)
        if not old_embed:
            return await self.no_message(ctx)

        def from_user(message: discord.Message) -> bool:
            if message.author == ctx.author and message.channel == ctx.channel:
                return True
            else:
                return False

        def panel_react(reaction: discord.Reaction, user: discord.User) -> bool:
            if reaction.message.id == panel.id and ctx.author.id == user.id:
                return True
            else:
                return False

        # User provides the panel's new title
        try:
            panel_message = await self.check_panel(panel)
            if not panel_message:
                return await self.no_panel(ctx)
            await self.edit_panel(panel_embed, panel_message, title=None,
                                  description=f"{ctx.author.mention}, please enter the new title of the embed, "
                                              f"or enter *\"skip\"* to keep the current title\n\n**Current Title:**\n"
                                              f"{old_embed.title}")
            result = await self.client.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await self.timeout(ctx, timeout, panel)
        else:
            if result.content == "cancel":
                return await self.user_cancelled(ctx, panel_message)
            elif result.content == "skip":
                title = old_embed.title
            else:
                title = result.content
            await result.delete()

        # User provides the panel's new description
        try:
            panel_message = await self.check_panel(panel)
            if not panel_message:
                return await self.no_panel(ctx)
            await self.edit_panel(panel_embed, panel_message, title=None,
                                  description=f"{ctx.author.mention}, please enter the new description of the "
                                              f"embed, or enter *\"skip\"* to keep the current "
                                              f"description\n\n**Current Description:**\n{old_embed.description}")
            result = await self.client.wait_for("message", check=from_user,
                                                            timeout=timeout)
        except asyncio.TimeoutError:
            return await self.timeout(ctx, timeout, panel)
        else:
            if result.content == "cancel":
                return await self.user_cancelled(ctx, panel_message)
            elif result.content == "skip":
                description = old_embed.description
            else:
                description = result.content
            await result.delete()

        # User will input the embed color
        while True:
            try:
                panel_message = await self.check_panel(panel)
                if not panel_message:
                    return await self.no_panel(ctx)
                await self.edit_panel(panel_embed, panel_message, title=None,
                                      description=f"{ctx.author.mention}, please enter the new hex color of the "
                                                  f"embed, or enter *\"skip\"* to keep the current "
                                                  f"color\n\n**Current Color:**\n{str(old_embed.color)}")
                result = await self.client.wait_for("message", check=from_user,
                                                                timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, timeout, panel)
            if not re.match(hex_color_rx, result.content):
                if result.content == "cancel":
                    return await self.user_cancelled(ctx, panel_message)
                elif result.content == "skip":
                    color = old_embed.color
                    break
                else:
                    continue
            else:
                color = int(result.content[1:], 16)
                await result.delete()
                break

        # User will tag the role, then react with the corresponding emoji
        emoji_role_list = []
        emoji_list = []
        while True:
            while True:
                try:
                    panel_message = await self.check_panel(panel)
                    if not panel_message:
                        return await self.no_panel(ctx)
                    await self.edit_panel(panel_embed, panel_message, title=None,
                                          description=f"{ctx.author.mention}, please tag the role you would like to be "
                                                      f"added into the reaction role, type *finish* to finish setup, "
                                                      f"or type *skip* to keep the current roles and reactions")
                    result = await self.client.wait_for("message", check=from_user,
                                                                    timeout=timeout)
                except asyncio.TimeoutError:
                    return await self.timeout(ctx, timeout, panel)
                if not re.match(role_tag_rx, result.content):
                    if result.content == "cancel":
                        return await self.user_cancelled(ctx, panel_message)
                    elif result.content == "finish":
                        break
                    elif result.content == "skip":
                        break
                    else:
                        continue
                else:
                    break
            if result.content == "finish" or result.content == "skip":
                await result.delete()
                break

            role = result.content[3:21]
            await result.delete()

            while True:
                try:
                    panel_message = await self.check_panel(panel)
                    if not panel_message:
                        return await self.no_panel(ctx)
                    await self.edit_panel(panel_embed, panel_message, title=None,
                                          description=f"{ctx.author.mention}, please react to this panel with the emoji"
                                                      f" you want the user to react with to get the role <@&{role}>")
                    result = await self.client.wait_for("reaction_add",
                                                                    check=panel_react,
                                                                    timeout=timeout)
                except asyncio.TimeoutError:
                    return await self.timeout(ctx, timeout, panel)
                if result[0].emoji in emoji_list:
                    continue
                else:
                    break

            emoji = result[0].emoji
            emoji_list.append(emoji)
            await result[0].message.clear_reactions()

            emoji_role_list.append((role, emoji))

        if result.content == "skip":
            emoji_list = None
            emoji_role_list = None

        # User will input number to dictate type of reaction role
        while True:
            try:
                panel_message = await self.check_panel(panel)
                if not panel_message:
                    return await self.no_panel(ctx)
                await self.edit_panel(panel_embed, panel_message, title=None,
                                      description=f"{ctx.author.mention}, please enter the number that corresponds to "
                                                  f"the type of reaction role behavior you would like, or type *skip* "
                                                  f"to keep the current type\nCurrent type: "
                                                  f"{await self.get_rr_type(message_id, ctx.guild.id)}\n\n "
                                                  f"**1:** Normal *(react to add, unreact to remove, multiple at a "
                                                  f"time)*\n "
                                                  f"**2:** Reverse *(react to remove, unreact to add, multiple at a "
                                                  f"time)*\n "
                                                  f"**3:** Single Normal *(same as normal, except you can only have one"
                                                  f" role at a time)*\n\n"
                                                  f"*If I wanted to pick `Normal`, I would type \"1\" as the response*")
                result = await self.client.wait_for("message", check=from_user,
                                                                timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, timeout, panel)
            else:
                if result.content == "cancel":
                    return await self.user_cancelled(ctx, panel_message)
                if result.content == "skip":
                    break
                if result.content == "1":
                    type_name = "normal"
                    break
                if result.content == "2":
                    type_name = "reverse"
                    break
                if result.content == "3":
                    type_name = "single_normal"
                    break
                continue

        if result.content == "skip":
            type_name = None
        else:
            type_name = type_name
        await result.delete()
        await panel.delete()

        await self.success(ctx, "edited")

        return await self.edit_rr_message(ctx, message_id, ctx.guild.id, title, description,
                                          color, emoji_list, emoji_role_list, type_name)

    @reactionrole.command(aliases=['-d', '-rm', 'del'])
    async def delete(self, ctx, message_id: int = None):
        if not message_id:
            return await ctx.invoke(self.reactionrole)

        exists = await self.check_rr_exists(ctx, message_id, ctx.guild.id)
        if not exists:
            return await self.no_message(ctx)

        is_author = await self.check_rr_author(message_id, ctx.author.id, ctx.guild.id)
        if not is_author:
            not_author = discord.Embed(title="Not Panel Author",
                                       description=f"{ctx.author.mention}, you must be the author of that reaction "
                                                   f"roles panel to edit the panel",
                                       color=discord.Color.dark_red())
            return await ctx.channel.send(embed=not_author, delete_after=10)

        return await self.delete_rr_message(ctx, message_id, ctx.guild.id)

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    async def rank(self, ctx, *, name: str = None):
        if not name or name not in role_names:
            embed = discord.Embed(title="Available Roles",
                                  description=f"{ctx.author.mention}, get a role using `?rank [role_name]`"
                                  f"\n\n**Valid Role Names:**\n```{newline.join(role_names)}```",
                                  color=discord.Color.blue())
        elif name in role_names:
            role_converter = commands.RoleConverter()
            role = await role_converter.convert(ctx, name)
            if role not in ctx.author.roles:
                await ctx.author.add_roles(role)
                embed = discord.Embed(title="Role Added",
                                    description=f"{ctx.author.mention}, you have been given the {role.mention} role",
                                    color=discord.Color.blue())
            else:
                await ctx.author.remove_roles(role)
                embed = discord.Embed(title="Role Removed",
                                      description=f"{ctx.author.mention}, you are no longer in {role.mention}",
                                      color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

def setup(client):
    client.add_cog(Roles(client))
