import asyncio
import os
import re
from contextlib import suppress

import discord
from discord.ext import commands
from utils import customerrors, globalcommands, paginator

gcmds = globalcommands.GlobalCMDS()
channel_tag_rx = re.compile(r'<#[0-9]{18}>')
channel_id_rx = re.compile(r'[0-9]{18}')
role_tag_rx = re.compile(r'<@&[0-9]{18}>')
hex_color_rx = re.compile(r'#[A-Fa-f0-9]{6}')
timeout = 180


class Roles(commands.Cog):

    def __init__(self, bot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_roles())

    async def init_roles(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS base_rr(message_id bigint PRIMARY KEY, channel_id bigint, "
                              "type text, author_id bigint, guild_id bigint, jump_url text)")
            await con.execute("CREATE TABLE IF NOT EXISTS emoji_rr(message_id bigint, role_id bigint PRIMARY KEY, emoji text)")
            await con.execute("CREATE TABLE IF NOT EXISTS autoroles(role_id bigint, type text, guild_id bigint, author_id bigint)")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            type = await con.fetchval(f"SELECT type FROM base_rr WHERE message_id={int(payload.message_id)}")
        if not type:
            return

        member = payload.member
        if not member or member.bot:
            return

        with suppress(discord.Forbidden, discord.NotFound, KeyError):
            async with self.bot.db.acquire() as con:
                role_id = await con.fetchval(f"SELECT role_id FROM emoji_rr WHERE message_id={payload.message_id} "
                                             f"AND emoji=$tag${str(payload.emoji)}$tag$")
                role_emoji = await con.fetch(f"SELECT role_id, emoji FROM emoji_rr WHERE message_id={payload.message_id} "
                                             f"AND role_id != {role_id}")
            role = discord.utils.get(member.roles, id=int(role_id))
            if "normal" in type and not role:
                await member.add_roles(member.guild.get_role(int(role_id)))
            if type == "reverse" and role:
                await member.remove_roles(role)
            if type == 'single_normal':
                channel = await self.bot.fetch_channel(payload.channel_id)
                message = await channel.fetch_message(payload.message_id)
                roles = []
                for role_id, emoji in role_emoji:
                    await asyncio.sleep(0)
                    role = discord.utils.get(member.roles, id=role_id)
                    if not role:
                        continue
                    roles.append(role)
                    with suppress(Exception):
                        await message.remove_reaction(emoji, member)
                await member.remove_roles(*roles)
        return

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            type = await con.fetchval(f"SELECT type FROM base_rr WHERE message_id={payload.message_id}")
        if not type:
            return

        guild = await self.bot.fetch_guild(payload.guild_id)
        member = await guild.fetch_member(payload.user_id)
        if member.bot:
            return

        with suppress(discord.Forbidden, discord.NotFound, KeyError):
            async with self.bot.db.acquire() as con:
                role_id = await con.fetchval(f"SELECT role_id FROM emoji_rr WHERE message_id={payload.message_id} "
                                             f"AND emoji=$tag${str(payload.emoji)}$tag$")
            role = discord.utils.get(member.roles, id=int(role_id))
            if "normal" in type and role:
                await member.remove_roles(role)
            if type == "reverse" and not role:
                await member.add_roles(guild.get_role(int(role_id)))
        return

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
        return await ctx.channel.send(embed=embed)

    async def user_cancelled(self, ctx, panel: discord.Message) -> discord.Message:
        embed = discord.Embed(title="Reaction Roles Setup Cancelled",
                              description=f"{ctx.author.mention}, you have cancelled reaction roles setup",
                              color=discord.Color.dark_red())
        panel_message = await self.check_panel(panel)
        if not panel_message:
            return await ctx.channel.send(embed=embed)
        else:
            return await panel_message.edit(embed=embed)

    async def timeout(self, ctx, timeout: int, panel: discord.Message) -> discord.Message:
        embed = discord.Embed(title="Reaction Roles Setup Cancelled",
                              description=f"{ctx.author.mention}, the reaction roles setup was canelled because you "
                                          f"did not provide a valid action within {timeout} seconds",
                              color=discord.Color.dark_red())
        panel_message = await self.check_panel(panel)
        if not panel_message:
            return await ctx.channel.send(embed=embed)
        else:
            return await panel_message.edit(embed=embed)

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

    async def rr_help(self, ctx):
        message_id_message = f"The `[messageID]` argument must be the message ID of a reaction " \
            f"roles panel that you have created. You will be unable to edit the panel if you " \
            f"provide an invalid message ID or provide a message ID of a panel that was " \
            f"not created by you"
        embed = discord.Embed(title="ReactionRoles Help Menu",
                              description=f"All reaction roles commands can be accessed using "
                              f"`{await gcmds.prefix(ctx)}reactionrole [option]`. "
                              f"Below is a list of all the valid options",
                              color=discord.Color.blue())
        rrcreate = (f"**Usage:** `{await gcmds.prefix(ctx)}reactionrole create`",
                    f"**Returns:** Interactive reaction roles setup panel",
                    f"**Aliases:** `-c` `start` `make`")
        rredit = (f"**Usage:** `{await gcmds.prefix(ctx)}reactionrole edit [messageID]`",
                  f"**Returns:** Interactive reaction roles edit panel",
                  f"**Aliases:** `-e` `adjust`",
                  f"**Special Cases:** {message_id_message}")
        rrdelete = (f"**Usage:** `{await gcmds.prefix(ctx)}reactionrole delete [messageID]`",
                    f"**Returns:** Message that details status of the deletion",
                    f"**Aliases:** `-d` `-rm` `del`",
                    f"**Special Cases:** {message_id_message}. If the panel was manually deleted, "
                    f"UconnSmashBot will delete the panel's record from its database of reaction role panels")
        rrur = ("**Hex Color Picker:** https://www.google.com/search?q=color+picker",)
        nv = [("Create", rrcreate), ("Edit", rredit), ("Delete", rrdelete), ("Useful Resources", rrur)]
        for name, value in nv:
            embed.add_field(name=name, value="> " + "\n> ".join(value), inline=False)
        return await ctx.channel.send(embed=embed)

    async def send_rr_message(self, ctx, channel: discord.TextChannel, send_embed: discord.Embed,
                              role_emoji: list, type_name: str):
        rr_message = await channel.send(embed=send_embed)
        async with self.bot.db.acquire() as con:
            await con.execute(f"INSERT INTO base_rr(message_id, channel_id, type, author_id, guild_id, jump_url) VALUES "
                              f"({rr_message.id}, {channel.id}, $tag${type_name}$tag$, {ctx.author.id}, {ctx.guild.id},"
                              f" '{rr_message.jump_url}')")
            for role, emoji in role_emoji:
                await rr_message.add_reaction(emoji)
                await con.execute(f"INSERT INTO emoji_rr(message_id, role_id, emoji) VALUES ({rr_message.id}, {int(role)}, $tag${emoji}$tag$)")
        return

    async def edit_rr_message(self, ctx, message_id: int, guild_id: int, title: str, description: str, color: str,
                              emoji_role_list, type_name):
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

        if emoji_role_list or type_name:
            async with self.bot.db.acquire() as con:
                if emoji_role_list:
                    await message.clear_reactions()
                    await con.execute(f"DELETE FROM emoji_rr WHERE message_id={message.id}")
                    for role, emoji in emoji_role_list:
                        await message.add_reaction(emoji)
                        await con.execute(f"INSERT INTO emoji_rr(message_id, role_id, emoji) VALUES ({message.id}, {role.id}, $tag${emoji}$tag$)")
                if type_name:
                    await con.execute(f"UPDATE base_rr SET type=$tag${type_name}$tag$ WHERE message_id={message.id}")
        return

    async def check_rr_author(self, message_id: int, user_id: int) -> bool:
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT * FROM base_rr WHERE message_id={message_id} AND author_id={user_id}")
        return True if result else False

    async def check_rr_exists(self, ctx, message_id: int):
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT * FROM base_rr WHERE message_id={message_id}")
        return True if result else False

    async def get_guild_rr(self, ctx, flag: str = None):
        async with self.bot.db.acquire() as con:
            if not flag:
                result = await con.fetch(f"SELECT * FROM base_rr WHERE author_id={ctx.author.id} AND guild_id={ctx.guild.id}")
            else:
                result = await con.fetch(f"SELECT * FROM base_rr WHERE guild_id = {ctx.guild.id}")
        if not result:
            return None
        else:
            messages = []
            async with self.bot.db.acquire() as con:
                for item in result:
                    messages.append(((int(item['message_id'])), int(item['author_id']), item['jump_url'],
                                     await con.fetchval(f"SELECT count(*) FROM emoji_rr WHERE message_id={int(item['message_id'])}")))
            return messages

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

    async def delete_rr_message(self, ctx, message_id: int):
        async with self.bot.db.acquire() as con:
            channel_id = await con.fetchval(f"DELETE FROM base_rr WHERE message_id={message_id} RETURNING channel_id")
            await con.execute(f"DELETE FROM emoji_rr WHERE message_id={message_id}")

        with suppress(Exception):
            channel = await self.bot.get_channel(int(channel_id))
            message = await channel.fetch_message(message_id)
            await gcmds.smart_delete(message)

        embed = discord.Embed(title="Successfully Deleted Reaction Role",
                              description=f"{ctx.author.mention}, I have deleted the reaction roles panel and cleared the record from "
                              f"my database ",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    async def get_rr_type(self, message_id: int) -> str:
        async with self.bot.db.acquire() as con:
            type = await con.fetchval(f"SELECT type FROM base_rr WHERE message_id={message_id}")
        return type.replace("_", " ").title()

    async def ar_help(self, ctx):
        spar = f"{await gcmds.prefix(ctx)}autorole [user/bot]"
        description = (f"{ctx.author.mention}, here is some important info about the `autorole` commands\n"
                       "> - Alias: `ar`\n"
                       "> - You can set autoroles for users and bots. The subcommands are `user` and `bot` respectively\n"
                       "> - The subcommands below, with the exception of list, apply for both users and bots and assume that"
                       " you have selected either `user` or `bot` already\n\n"
                       "Here are the supported autorole subcommands")
        set = (f"**Usage:** `{spar} set [roles]`",
               "**Returns:** A confirmation embed with the list of roles that will be set to automatically give to new users/bots"
               " who join the server",
               "**Aliases:** `-s` `create` `assign`",
               "**Special Cases:** `[roles]` must be role tags or role IDs")
        remove = (f"**Usage:** `{spar} remove [roles]`",
                  "**Returns:** A confirmation embed with the list of roles that will be no longer given to new users/bots "
                  "who join the server",
                  "**Aliases:** `-rm` `delete` `cancel`")
        list = (f"**Usage:** `{await gcmds.prefix(ctx)} autorole list (user/bot)`",
                "**Returns:** An embed that lists any active autoroles for users, bots, or both",
                "**Aliases:** `-ls` `show`",
                "**Special Cases:** If `(user/bot)` is not specified, it will show all active autoroles for both users and bots")
        nv = [("Set", set), ("Remove", remove), ("List", list)]

        embed = discord.Embed(title="Autorole Command Help",
                              description=description,
                              color=discord.Color.blue())
        for name, value in nv:
            embed.add_field(name=name, value="> " + "\n> ".join(value), inline=False)
        return await ctx.channel.send(embed=embed)

    @commands.group(invoke_without_command=True,
                    aliases=['ar', 'autoroles'],
                    desc="Displays the help command for autorole",
                    usage="autorole")
    async def autorole(self, ctx):
        return await self.ar_help(ctx)

    @autorole.command(aliases=['list', '-ls', 'show'])
    async def autorole_list(self, ctx, flag: str = "all"):
        try:
            async with self.bot.db.acquire() as con:
                if "user" in flag.lower():
                    flag = "user"
                    result = await con.fetch(f"SELECT * FROM autoroles WHERE type='member' AND guild_id={ctx.guild.id} ORDER BY role_id DESC")
                elif "bot" in flag.lower():
                    flag = "bot"
                    result = await con.fetch(f"SELECT * FROM autoroles WHERE type='bot' AND guild_id={ctx.guild.id} ORDER BY role_id DESC")
                else:
                    flag = "all"
                    result = await con.fetch(f"SELECT * FROM autoroles WHERE guild_id={ctx.guild.id} ORDER BY type DESC")
        except Exception:
            raise customerrors.AutoroleSearchError()

        if not result:
            embed = discord.Embed(title="No Autoroles Set",
                                  description=f"{ctx.author.mention}, this server does not have any autoroles set for {flag}",
                                  color=discord.Color.dark_red())
            return await ctx.channel.send(embed=embed)

        entries = [
            f"<@&{item['role_id']}> *[Type: {item['type']}]*\n> Assigned By: <@{item['author_id']}>\n" for item in result]
        pag = paginator.EmbedPaginator(ctx, entries=entries, per_page=10, show_entry_count=True)
        pag.embed.title = f"{flag.title()} Autoroles"
        await pag.paginate()

    @autorole.group(invoke_without_command=True, aliases=['user', 'users', '-u'])
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_guild=True)
    async def autorole_user(self, ctx):
        return await self.ar_help(ctx)

    @autorole_user.command(aliases=['set', '-s', 'create', 'assign'])
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_guild=True)
    async def autorole_user_set(self, ctx, roles: commands.Greedy[discord.Role]):
        try:
            async with self.bot.db.acquire() as con:
                await con.execute(f"DELETE FROM autoroles WHERE guild_id={ctx.guild.id} AND type='member'")
                values = [f"({role.id}, 'member', {ctx.guild.id}, {ctx.author.id})" for role in roles]
                await con.execute(f"INSERT INTO autoroles(role_id, type, guild_id, author_id) VALUES {', '.join(values)}")
        except Exception:
            raise customerrors.AutoroleInsertError()
        role_desc = "\n".join([f"> {role.mention}" for role in roles])
        embed = discord.Embed(title="Set Autoroles",
                              description=f"{ctx.author.mention}, users will now gain the following roles when joining "
                              f"this server:\n\n {role_desc}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @autorole_user.command(aliases=['remove', '-rm', 'delete', 'cancel'])
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_guild=True)
    async def autorole_user_remove(self, ctx, roles: commands.Greedy[discord.Role] = None):
        reactions = ["✅", "🛑"]
        if not roles:
            description = (f"{ctx.author.mention}, you are about to clear all user autoroles from this server. This action "
                           f"is destructive and irreversible. React with {reactions[0]} to confirm or {reactions[1]} to cancel")
        else:
            role_list = [f"> {role.mention}" for role in roles]
            description = (f"{ctx.author.mention}, you are about to clear these user autoroles from this server:\n\n" + "\n\n".join(role_list) +
                           f"\n\nThis action is destructive and irreversible. React with {reactions[0]} to confirm or {reactions[1]} to cancel")
        panel_embed = discord.Embed(title="Confirmation",
                                    description=description,
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)
        try:
            for reaction in reactions:
                await panel.add_reaction(reaction)
        except Exception:
            raise customerrors.AutoroleDeleteError()

        def reacted(reaction: discord.Reaction, user: discord.User) -> bool:
            return reaction.emoji in reactions and ctx.author.id == user.id and reaction.message.id == panel.id

        try:
            result = await self.bot.wait_for("reaction_add", check=reacted, timeout=30)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, "autoroles remove", 30)
        try:
            await panel.delete()
        except Exception:
            pass
        if result[0].emoji == reactions[0]:
            try:
                async with self.bot.db.acquire() as con:
                    if roles:
                        for role in roles:
                            await con.execute(f"DELETE FROM autoroles WHERE role_id={role.id}")
                    else:
                        await con.execute(f"DELETE FROM autoroles WHERE type='member' AND guild_id={ctx.guild.id}")
            except Exception:
                raise customerrors.AutoroleDeleteError()
        else:
            return await gcmds.cancelled(ctx, "autoroles remove")
        if not roles:
            description = f"{ctx.author.mention}, no roles will be given to new members when they join this server anymore"
        else:
            description = f"{ctx.author.mention}, the roles\n\n" + \
                "\n".join(role_list) + "\n\nwill no longer be given to new members when they join this server"

        embed = discord.Embed(title="Autoroles Remove Success",
                              description=description,
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @autorole.group(invoke_without_command=True, aliases=['bot', 'bots', '-b'])
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_guild=True)
    async def autorole_bot(self, ctx):
        return await self.ar_help(ctx)

    @autorole_bot.command(aliases=['set', '-s', 'create', 'assign'])
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_guild=True)
    async def autorole_bot_set(self, ctx, roles: commands.Greedy[discord.Role]):
        try:
            async with self.bot.db.acquire() as con:
                await con.execute(f"DELETE FROM autoroles WHERE guild_id={ctx.guild.id} AND type='bot'")
                values = [f"({role.id}, 'bot', {ctx.guild.id}, {ctx.author.id})" for role in roles]
                await con.execute(f"INSERT INTO autoroles(role_id, type, guild_id, author_id) VALUES {', '.join(values)}")
        except Exception:
            raise customerrors.AutoroleInsertError()
        role_desc = "\n".join([f"> {role.mention}" for role in roles])
        embed = discord.Embed(title="Set Autoroles",
                              description=f"{ctx.author.mention}, bots will now gain the following roles when joining "
                              f"this server:\n\n {role_desc}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @autorole_bot.command(aliases=['remove', '-rm', 'delete', 'cancel'])
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_guild=True)
    async def autorole_bot_remove(self, ctx, roles: commands.Greedy[discord.Role] = None):
        reactions = ["✅", "🛑"]
        if not roles:
            description = (f"{ctx.author.mention}, you are about to clear all bot autoroles from this server. This action "
                           f"is destructive and irreversible. React with {reactions[0]} to confirm or {reactions[1]} to cancel")
        else:
            role_list = [f"> {role.mention}" for role in roles]
            description = (f"{ctx.author.mention}, you are about to clear these bot autoroles from this server:\n\n" + "\n\n".join(role_list) +
                           f"\n\nThis action is destructive and irreversible. React with {reactions[0]} to confirm or {reactions[1]} to cancel")
        panel_embed = discord.Embed(title="Confirmation",
                                    description=description,
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)
        try:
            for reaction in reactions:
                await panel.add_reaction(reaction)
        except Exception:
            raise customerrors.AutoroleDeleteError()

        def reacted(reaction: discord.Reaction, user: discord.User) -> bool:
            return reaction.emoji in reactions and ctx.author.id == user.id and reaction.message.id == panel.id

        try:
            result = await self.bot.wait_for("reaction_add", check=reacted, timeout=30)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, "autoroles remove", 30)
        try:
            await panel.delete()
        except Exception:
            pass
        if result[0].emoji == reactions[0]:
            try:
                async with self.bot.db.acquire() as con:
                    if roles:
                        for role in roles:
                            await con.execute(f"DELETE FROM autoroles WHERE role_id={role.id}")
                    else:
                        await con.execute(f"DELETE FROM autoroles WHERE type='bot' AND guild_id={ctx.guild.id}")
            except Exception:
                raise customerrors.AutoroleDeleteError()
        else:
            return await gcmds.cancelled(ctx, "autoroles remove")
        if not roles:
            description = f"{ctx.author.mention}, no roles will be given to new bots when they join this server anymore"
        else:
            description = f"{ctx.author.mention}, the roles\n\n" + \
                "\n".join(role_list) + "\n\nwill no longer be given to new bots when they join this server"

        embed = discord.Embed(title="Autoroles Remove Success",
                              description=description,
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.group(invoke_without_command=True,
                    aliases=['rr'],
                    desc="Displays the help command for reactionrole",
                    usage="reactionrole")
    async def reactionrole(self, ctx):
        return await self.rr_help(ctx)

    @reactionrole.command(aliases=['-ls'])
    async def list(self, ctx, flag: str = None):
        messages = await self.get_guild_rr(ctx, flag) if flag == "all" else await self.get_guild_rr(ctx, None)
        if not messages:
            if flag == "all":
                description = f"{ctx.author.mention}, this server does not have any reaction roles panels"
            else:
                description = f"{ctx.author.mention}, you do not own any reaction roles panels in this server"
            embed = discord.Embed(title="No Reaction Roles Panel",
                                  description=description,
                                  color=discord.Color.dark_red())
            return await ctx.channel.send(embed=embed)
        else:
            if flag == "all":
                title = "All Reaction Roles Panels"
            else:
                title = f"{ctx.author.display_name}'s Reaction Roles Panels"
            entries = [
                f"Message ID: [{item[0]}]({item[2]}) *[Emojis: {item[3]}]*\n> Owner: <@{item[1]}>" for item in messages]
            pag = paginator.EmbedPaginator(ctx, entries=entries, per_page=5, show_entry_count=True)
            pag.embed.title = title
            return await pag.paginate()

    @reactionrole.command(aliases=['-c', 'start', 'make'])
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True)
    @commands.has_permissions(manage_guild=True)
    async def create(self, ctx):
        panel_embed = discord.Embed(title="Reaction Role Setup Menu",
                                    description=f"{ctx.author.mention}, welcome to UconnSmashBot's reaction role setup "
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
                result = await self.bot.wait_for("message", check=from_user,
                                                 timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, timeout, panel)
            if not re.match(channel_tag_rx, result.content):
                if re.match(channel_id_rx, result.content):
                    channel_id = result.content
                    break
                else:
                    if result.content == "cancel":
                        return await self.user_cancelled(ctx, panel_message)
                    continue
            else:
                channel_id = result.content[2:20]
            break
        await gcmds.smart_delete(result)

        channel = await commands.AutoShardedBot.fetch_channel(self.bot, channel_id)

        # User will input the embed title
        try:
            panel_message = await self.check_panel(panel)
            if not panel_message:
                return await self.no_panel(ctx)
            await self.edit_panel(panel_embed, panel_message, title=None,
                                  description=f"{ctx.author.mention}, please enter the title of the embed that will "
                                              f"be sent")
            result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await self.timeout(ctx, timeout, panel)
        else:
            if result.content == "cancel":
                return await self.user_cancelled(ctx, panel_message)
        await gcmds.smart_delete(result)

        title = result.content

        # User will input the embed description
        try:
            panel_message = await self.check_panel(panel)
            if not panel_message:
                return await self.no_panel(ctx)
            await self.edit_panel(panel_embed, panel_message, title=None,
                                  description=f"{ctx.author.mention}, please enter the description of the embed that "
                                              f"will be sent")
            result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await self.timeout(ctx, timeout, panel)
        else:
            if result.content == "cancel":
                return await self.user_cancelled(ctx, panel_message)
        await gcmds.smart_delete(result)

        description = result.content

        # User will input the embed color
        while True:
            try:
                panel_message = await self.check_panel(panel)
                if not panel_message:
                    return await self.no_panel(ctx)
                await self.edit_panel(panel_embed, panel_message, title=None,
                                      description=f"{ctx.author.mention}, please enter the hex color of the embed "
                                                  f"that will be sent")
                result = await self.bot.wait_for("message", check=from_user,
                                                 timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx, timeout, panel)
            if not re.match(hex_color_rx, result.content):
                if result.content == "cancel":
                    return await self.user_cancelled(ctx, panel_message)
                else:
                    continue
            break
        await gcmds.smart_delete(result)

        color = int(result.content[1:], 16)

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
                    result = await self.bot.wait_for("message", check=from_user,
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
                    await gcmds.smart_delete(result)
                    break
            if result.content == "finish":
                await gcmds.smart_delete(result)
                break

            role = result.content[3:21]

            while True:
                try:
                    panel_message = await self.check_panel(panel)
                    if not panel_message:
                        return await self.no_panel(ctx)
                    await self.edit_panel(panel_embed, panel_message, title=None,
                                          description=f"{ctx.author.mention}, please react to this panel with the emoji"
                                                      f" you want the user to react with to get the role <@&{role}>")
                    result = await self.bot.wait_for("reaction_add", check=panel_react,
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
                result = await self.bot.wait_for("message", check=from_user,
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
        await gcmds.smart_delete(result)

        type_name = type_name

        await panel.delete()

        await self.success(ctx, "created")

        # Post reaction role panel in the channel
        rr_embed = discord.Embed(title=title,
                                 description=description,
                                 color=color)
        return await self.send_rr_message(ctx, channel, rr_embed, emoji_role_list, type_name)

    @reactionrole.command(aliases=['adjust', '-e'])
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True)
    @commands.has_permissions(manage_guild=True)
    async def edit(self, ctx, message_id: int = None):
        if not message_id:
            return await ctx.invoke(self.reactionrole)

        exists = await self.check_rr_exists(ctx, message_id)
        if not exists:
            return await self.no_message(ctx)

        is_author = await self.check_rr_author(message_id, ctx.author.id)
        if not is_author:
            not_author = discord.Embed(title="Not Panel Author",
                                       description=f"{ctx.author.mention}, you must be the author of that reaction "
                                                   f"roles panel to edit the panel",
                                       color=discord.Color.dark_red())
            return await ctx.channel.send(embed=not_author)

        panel_embed = discord.Embed(title="Reaction Role Setup Menu",
                                    description=f"{ctx.author.mention}, welcome to UconnSmashBot's reaction role setup "
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
            result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await self.timeout(ctx, timeout, panel)
        else:
            if result.content == "cancel":
                return await self.user_cancelled(ctx, panel_message)
            elif result.content == "skip":
                title = old_embed.title
            else:
                title = result.content
        await gcmds.smart_delete(result)

        # User provides the panel's new description
        try:
            panel_message = await self.check_panel(panel)
            if not panel_message:
                return await self.no_panel(ctx)
            await self.edit_panel(panel_embed, panel_message, title=None,
                                  description=f"{ctx.author.mention}, please enter the new description of the "
                                              f"embed, or enter *\"skip\"* to keep the current "
                                              f"description\n\n**Current Description:**\n{old_embed.description}")
            result = await self.bot.wait_for("message", check=from_user,
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
        await gcmds.smart_delete(result)

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
                result = await self.bot.wait_for("message", check=from_user,
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
                break
        await gcmds.smart_delete(result)

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
                                          description=f"{ctx.author.mention}, please tag the role you would like the "
                                          "reaction role panel to have, type *finish* to finish setup, "
                                          "or type *skip* to keep the current roles and reactions\n\n**Specifying a "
                                          "role will not add it to the current list. You must specify all the roles "
                                          "that this panel should have (including already added roles)**")
                    result = await self.bot.wait_for("message", check=from_user,
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

            await gcmds.smart_delete(result)
            if result.content == "finish" or result.content == "skip":
                break

            role = result.content[3:21]

            while True:
                try:
                    panel_message = await self.check_panel(panel)
                    if not panel_message:
                        return await self.no_panel(ctx)
                    await self.edit_panel(panel_embed, panel_message, title=None,
                                          description=f"{ctx.author.mention}, please react to this panel with the emoji"
                                                      f" you want the user to react with to get the role <@&{role}>")
                    result = await self.bot.wait_for("reaction_add",
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

        if result.content == "skip" or (result.content == "finish" and not emoji_list and not emoji_role_list):
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
                result = await self.bot.wait_for("message", check=from_user,
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
        await gcmds.smart_delete(result)

        if result.content == "skip":
            type_name = None
        else:
            type_name = type_name

        await panel.delete()

        await self.success(ctx, "edited")

        return await self.edit_rr_message(ctx, message_id, ctx.guild.id, title, description,
                                          color, emoji_role_list, type_name)

    @reactionrole.command(aliases=['-d', '-rm', 'del'])
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True)
    @commands.has_permissions(manage_guild=True)
    async def delete(self, ctx, message_id: int = None):
        if not message_id:
            return await ctx.invoke(self.reactionrole)

        exists = await self.check_rr_exists(ctx, message_id)
        if not exists:
            return await self.no_message(ctx)

        is_author = await self.check_rr_author(message_id, ctx.author.id)
        if not is_author:
            not_author = discord.Embed(title="Not Panel Author",
                                       description=f"{ctx.author.mention}, you must be the author of that reaction "
                                                   f"roles panel to edit the panel",
                                       color=discord.Color.dark_red())
            return await ctx.channel.send(embed=not_author)

        reactions = ["✅", "❌"]

        panel_embed = discord.Embed(title="Confirmation",
                                    description=f"{ctx.author.mention}, deleting a reaction roles panel is a destructive"
                                    f" action that cannot be undone. React with {reactions[0]} to confirm or {reactions[1]} to cancel",
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)
        for reaction in reactions:
            try:
                await panel.add_reaction(reaction)
            except Exception:
                pass

        def user_reacted(reaction: discord.Reaction, user: discord.User):
            return reaction.emoji in reactions and reaction.message.id == panel.id and user.id == ctx.author.id

        try:
            result = await self.bot.wait_for("reaction_add", check=user_reacted, timeout=30)
        except asyncio.TimeoutError:
            return await self.timeout(ctx, 30, panel)
        if result[0].emoji == reactions[0]:
            await gcmds.smart_delete(panel)
            return await self.delete_rr_message(ctx, message_id)
        else:
            return await self.user_cancelled(ctx, panel)


def setup(bot):
    bot.add_cog(Roles(bot))
