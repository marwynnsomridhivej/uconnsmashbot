import asyncio
import re
from contextlib import suppress
from typing import List, Tuple

import discord
from asyncpg.exceptions import UniqueViolationError
from discord.ext import commands
from discord.ext.commands.context import Context
from setuppanel import SetupPanel
from utils import EmbedPaginator, GlobalCMDS, SubcommandHelp, customerrors

channel_tag_rx = re.compile(r'<#[0-9]{18}>')
channel_id_rx = re.compile(r'[0-9]{18}')
role_tag_rx = re.compile(r'<@&[0-9]{18}>')
hex_color_rx = re.compile(r'#[A-Fa-f0-9]{6}')
url_rx = re.compile(r'https?://(?:www\.)?.+')
timeout = 180
TYPE_NAME = {
    1: "normal",
    2: "reverse",
    3: "single_normal",
    4: "limit",
    5: "perma",
}


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_roles())

    async def init_roles(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS base_rr(message_id bigint PRIMARY KEY, channel_id bigint, "
                              "type text, author_id bigint, guild_id bigint, jump_url text, _limit smallint DEFAULT 0)")
            await con.execute("CREATE TABLE IF NOT EXISTS emoji_rr(message_id bigint, role_id bigint PRIMARY KEY, emoji text)")
            await con.execute("CREATE TABLE IF NOT EXISTS autoroles(role_id bigint, type text, guild_id bigint, author_id bigint)")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            type = await con.fetchval(f"SELECT type FROM base_rr WHERE message_id={int(payload.message_id)}")
            role_id = await con.fetchval(f"SELECT role_id FROM emoji_rr WHERE message_id={payload.message_id} "
                                         f"AND emoji=$tag${str(payload.emoji)}$tag$")
        if type and role_id:
            member: discord.Member = payload.member
            if member and not member.bot:
                with suppress(discord.Forbidden, discord.NotFound):
                    async with self.bot.db.acquire() as con:
                        role_emoji = await con.fetch(f"SELECT role_id, emoji FROM emoji_rr WHERE message_id={payload.message_id} "
                                                     f"AND role_id!={role_id}")
                        limit = await con.fetchval(f"SELECT _limit FROM base_rr WHERE message_id={payload.message_id}")
                    role = discord.utils.get(member.roles, id=int(role_id))
                    if "normal" in type and not role:
                        await member.add_roles(member.guild.get_role(int(role_id)))
                    elif type == "reverse" and role:
                        await member.remove_roles(role)
                    elif type == 'single_normal':
                        channel = await self.bot.fetch_channel(payload.channel_id)
                        message: discord.Message = await channel.fetch_message(payload.message_id)
                        roles = []
                        for role_id, emoji in role_emoji:
                            await asyncio.sleep(0)
                            role = discord.utils.get(member.roles, id=role_id)
                            if not role:
                                continue
                            roles.append(role)
                            await message.remove_reaction(emoji, member)
                        await member.remove_roles(*roles)
                    elif type == 'limit':
                        channel = await self.bot.fetch_channel(payload.channel_id)
                        message = await channel.fetch_message(payload.message_id)
                        reacted = len(
                            [user for reaction in message.reactions for user in await reaction.users().flatten() if user.id == member.id]
                        )
                        if reacted <= limit:
                            await member.add_roles(member.guild.get_role(int(role_id)))
                    elif type == "perma":
                        await member.add_roles(member.guild.get_role(int(role_id)))
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

        with suppress(discord.Forbidden, discord.NotFound):
            async with self.bot.db.acquire() as con:
                role_id = await con.fetchval(f"SELECT role_id FROM emoji_rr WHERE message_id={payload.message_id} "
                                             f"AND emoji=$tag${str(payload.emoji)}$tag$")
            if role_id:
                role = discord.utils.get(member.roles, id=int(role_id))
                if "normal" in type and role:
                    await member.remove_roles(role)
                elif type == "reverse" and not role:
                    await member.add_roles(guild.get_role(int(role_id)))
                elif type == "limit":
                    with suppress(Exception):
                        await member.remove_roles(guild.get_role(int(role_id)))
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
        embed = discord.Embed(title="ReactionRoles Setup Canceled",
                              description=f"{ctx.author.mention}, the reactionroles setup was canceled because the "
                                          f"setup panel was deleted or could not be found",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def no_message(self, ctx) -> discord.Message:
        embed = discord.Embed(title="No Message Found",
                              description=f"{ctx.author.mention}, no reactionroles panel was found for that message ID",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def user_canceled(self, ctx, panel: discord.Message) -> discord.Message:
        embed = discord.Embed(title="ReactionRoles Setup Canceled",
                              description=f"{ctx.author.mention}, you have canceled reactionroles setup",
                              color=discord.Color.dark_red())
        panel_message = await self.check_panel(panel)
        if not panel_message:
            return await ctx.channel.send(embed=embed)
        else:
            return await panel_message.edit(embed=embed)

    async def timeout(self, ctx, timeout: int, panel: discord.Message) -> discord.Message:
        embed = discord.Embed(title="ReactionRoles Setup Canceled",
                              description=f"{ctx.author.mention}, the reactionroles setup was canelled because you "
                                          f"did not provide a valid action within {timeout} seconds",
                              color=discord.Color.dark_red())
        panel_message = await self.check_panel(panel)
        if not panel_message:
            return await ctx.channel.send(embed=embed)
        else:
            return await panel_message.edit(embed=embed)

    async def success(self, ctx, success_str: str) -> discord.Message:
        embed = discord.Embed(title=f"Successfully {success_str.title()} Reactionroles Panel",
                              description=f"{ctx.author.mention}, your reactionroles panel was successfully"
                                          f" {success_str}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    async def failure(self, ctx, success_str: str) -> discord.Message:
        embed = discord.Embed(title=f"Failed to {success_str.title()} Reactionroles Panel",
                              description=f"{ctx.author.mention}, your reactionroles panel could not be"
                                          f" {success_str}ed",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def rr_help(self, ctx):
        pfx = f"{await self.gcmds.prefix(ctx)}reactionroles"
        return await SubcommandHelp(
            pfx=pfx,
            title="Reactionroles Help",
            description=f"{ctx.author.mention}, UconnSmashBot's reactionroles feature provides painless configuration of a "
            f"user friendly role self-assignment system. The base command is `{pfx}`. Here are all "
            "valid subcommands",
        ).from_config("reactionroles").show_help(ctx)

    async def send_rr_message(self, ctx, channel: discord.TextChannel, send_embed: discord.Embed,
                              roles_emojis: List[Tuple[discord.Role, str]], type_name: str, limit: int) -> discord.Message:
        rr_message = await channel.send(embed=send_embed)
        async with self.bot.db.acquire() as con:
            await con.execute(f"INSERT INTO base_rr(message_id, channel_id, type, author_id, guild_id, jump_url{', _limit' if limit else ''}) VALUES "
                              f"({rr_message.id}, {channel.id}, $tag${type_name}$tag$, {ctx.author.id}, {ctx.guild.id},"
                              f" '{rr_message.jump_url}'{f', {limit}' if limit else ''})")
            succeeded = []
            try:
                for role, emoji in roles_emojis:
                    await rr_message.add_reaction(emoji)
                    await con.execute(f"INSERT INTO emoji_rr(message_id, role_id, emoji) VALUES ({rr_message.id}, {role.id}, '{emoji}')")
                    succeeded.append((role, emoji))
            except UniqueViolationError:
                for role, emoji in succeeded:
                    await con.execute(f"DELETE FROM emoji_rr WHERE message_id={rr_message.id} AND role_id={role.id} AND emoji='{emoji}'")
                await self.gcmds.smart_delete(rr_message)
                return await ctx.channel.send(
                    embed=discord.Embed(
                        title="Unable to Create Reactionroles Panel",
                        description=f"{ctx.author.mention}, a specified role already exists as a reactionroles entry",
                        color=discord.Color.dark_red(),
                    )
                )
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Reactionroles Panel Created",
                description=f"{ctx.author.mention}, your reactionroles panel was successfully created",
                color=discord.Color.blue(),
            )
        )

    async def edit_rr_message(self, ctx: Context, message: discord.Message, new_embed: discord.Embed,
                              roles_emojis: List[Tuple[discord.Role, str]], type_name: str, limit: int) -> discord.Message:
        async with self.bot.db.acquire() as con:
            if roles_emojis:
                await self.gcmds.smart_clear(message)
                await con.execute(f"DELETE FROM emoji_rr WHERE message_id={message.id}")
                for role, emoji in roles_emojis:
                    await message.add_reaction(emoji)
                    await con.execute(f"INSERT INTO emoji_rr(message_id, role_id, emoji) VALUES ({message.id}, {role.id}, $tag${emoji}$tag$)")
            if type_name:
                await con.execute(f"UPDATE base_rr SET type=$tag${type_name}$tag$ WHERE message_id={message.id}")
            if limit:
                await con.execute(f"UPDATE base_rr SET limit={limit} WHERE message_id={message.id}")
        await message.edit(embed=new_embed)
        return await ctx.channel.send(embed=discord.Embed(
            title="Reactionroles Successfully Edited",
            description=f"{ctx.author.mention}, your reactionroles panel was successfully edited",
            color=discord.Color.blue(),
        ))

    async def check_rr_author(self, message_id: int, user_id: int) -> bool:
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT * FROM base_rr WHERE message_id={message_id} AND author_id={user_id}")
        return result

    async def check_rr_exists(self, ctx, message_id: int):
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT * FROM base_rr WHERE message_id={message_id}")
        return result

    async def get_guild_rr(self, ctx, flag: str = None):
        async with self.bot.db.acquire() as con:
            result = await con.fetch(
                f"SELECT * FROM base_rr WHERE author_id={ctx.author.id} AND guild_id={ctx.guild.id}" if not flag else
                f"SELECT * FROM base_rr WHERE guild_id = {ctx.guild.id}"
            )
        if result:
            messages = []
            async with self.bot.db.acquire() as con:
                for item in result:
                    messages.append(((int(item['message_id'])), int(item['author_id']), item['jump_url'],
                                     await con.fetchval(f"SELECT count(*) FROM emoji_rr WHERE message_id={int(item['message_id'])}")))
            return messages

    async def get_rr_info(self, ctx, message_id: int) -> discord.Embed:
        for text_channel in ctx.guild.text_channels:
            try:
                message = await text_channel.fetch_message(message_id)
                return message.embeds[0]
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        else:
            return None

    async def delete_rr_message(self, ctx, message_id: int):
        async with self.bot.db.acquire() as con:
            channel_id = await con.fetchval(f"DELETE FROM base_rr WHERE message_id={message_id} RETURNING channel_id")
            await con.execute(f"DELETE FROM emoji_rr WHERE message_id={message_id}")

        with suppress(Exception):
            channel = await self.bot.get_channel(int(channel_id))
            message = await channel.fetch_message(message_id)
            await self.gcmds.smart_delete(message)

        embed = discord.Embed(title="Successfully Deleted Reactionroles",
                              description=f"{ctx.author.mention}, I have deleted the reactionroles panel and cleared the record from "
                              f"my database ",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    async def get_rr_type(self, message_id: int) -> str:
        async with self.bot.db.acquire() as con:
            type = await con.fetchval(f"SELECT type FROM base_rr WHERE message_id={message_id}")
        return type.replace("_", " ").title()

    async def ar_help(self, ctx):
        pfx = f"{await self.gcmds.prefix(ctx)}autoroles [user/bot]"
        description = (
            f"{ctx.author.mention}, here is some important info about the `autoroles` commands",
            "> - Alias: `ar`",
            "> - You can set autoroles for users and bots. The subcommands are `user` and `bot` respectively",
            "> - The subcommands below, with the exception of list, apply for both users and bots and assume that"
            " you have selected either `user` or `bot` already\n",
            "Here are the supported autorole subcommands"
        )
        return await SubcommandHelp(
            pfx=pfx,
            title="Autorole Help",
            description="\n".join(description),
        ).from_config("autorole").show_help(ctx)

    @commands.group(invoke_without_command=True,
                    aliases=['ar', 'autorole'],
                    desc="Displays the help command for autorole",
                    usage="autorole")
    async def autoroles(self, ctx):
        return await self.ar_help(ctx)

    @autoroles.command(aliases=['list', 'ls', 'show'])
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
        pag = EmbedPaginator(ctx, entries=entries, per_page=10, show_entry_count=True)
        pag.embed.title = f"{flag.title()} Autoroles"
        await pag.paginate()

    @autoroles.group(invoke_without_command=True, aliases=['user', 'users', '-u'])
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

    @autorole_user.command(aliases=['remove', 'rm', 'delete', 'cancel'])
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
            return await self.gcmds.timeout(ctx, "autoroles remove", 30)
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
            return await self.gcmds.canceled(ctx, "autoroles remove")
        if not roles:
            description = f"{ctx.author.mention}, no roles will be given to new members when they join this server anymore"
        else:
            description = f"{ctx.author.mention}, the roles\n\n" + \
                "\n".join(role_list) + "\n\nwill no longer be given to new members when they join this server"

        embed = discord.Embed(title="Autoroles Remove Success",
                              description=description,
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @autoroles.group(invoke_without_command=True, aliases=['bot', 'bots', '-b'])
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

    @autorole_bot.command(aliases=['remove', 'rm', 'delete', 'cancel'])
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
            return await self.gcmds.timeout(ctx, "autoroles remove", 30)
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
            return await self.gcmds.canceled(ctx, "autoroles remove")
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
                    desc="Displays the help command for reactionroles",
                    usage="reactionroles")
    async def reactionroles(self, ctx):
        return await self.rr_help(ctx)

    @reactionroles.command(aliases=['ls'])
    async def list(self, ctx, flag: str = None):
        messages = await self.get_guild_rr(ctx, flag) if flag == "all" else await self.get_guild_rr(ctx, None)
        if not messages:
            if flag == "all":
                description = f"{ctx.author.mention}, this server does not have any reactionroles panels"
            else:
                description = f"{ctx.author.mention}, you do not own any reactionroles panels in this server"
            embed = discord.Embed(title="No ReactionRoles Panel",
                                  description=description,
                                  color=discord.Color.dark_red())
            return await ctx.channel.send(embed=embed)
        else:
            if flag == "all":
                title = "All ReactionRoles Panels"
            else:
                title = f"{ctx.author.display_name}'s ReactionRoles Panels"
            entries = [
                f"Message ID: [{item[0]}]({item[2]}) *[Emojis: {item[3]}]*\n> Owner: <@{item[1]}>" for item in messages]
            pag = EmbedPaginator(ctx, entries=entries, per_page=5, show_entry_count=True)
            pag.embed.title = title
            return await pag.paginate()

    @reactionroles.command(aliases=['-c', 'start', 'make'])
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True)
    @commands.has_permissions(manage_guild=True)
    async def create(self, ctx):
        _ET = "Reactionroles Setup"
        _BLUE = discord.Color.blue()

        def strict_int_check(m: discord.Message) -> bool:
            try:
                return m.author == ctx.author and m.channel == ctx.channel and (1 <= int(m.content) <= 5)
            except (ValueError, TypeError):
                return False

        def loose_int_check(m: discord.Message) -> bool:
            try:
                return m.author == ctx.author and m.channel == ctx.channel and int(m.content) >= 1
            except (ValueError, TypeError):
                return False

        sp = SetupPanel(
            bot=self.bot,
            ctx=ctx,
            title="Reactionroles",
        ).add_step(
            name="channel",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please mention the channel you would like this reactionroles panel to be sent in",
                color=_BLUE,
            ),
            timeout=120
        ).add_step(
            name="title",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the title of the reactionroles panel",
                color=_BLUE,
            ),
            timeout=300,
            predicate=lambda m: m.author == ctx.author and m.channel == ctx.channel and len(m.content) <= 256,
        ).add_step(
            name="description",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the description of the reactionroles panel",
                color=_BLUE,
            ),
            timeout=300,
        ).add_step(
            name="color",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the hex color of the reactionroles panel",
                color=_BLUE,
            ),
            timeout=300,
        ).add_step(
            name="content",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please input a URL to an image you would like to use as "
                "this embed's thumbnail image (small image that appears on the top right)",
                color=_BLUE,
            ).set_footer(
                text="Enter \"none\" if you would not like to have a thumbnail image",
            ),
            timeout=300,
            break_check=lambda m: not url_rx.match(m.content),
        ).add_step(
            name="content",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please input a URL to an image you would like to use as "
                "this embed's main image (large image that appears on the bottom)",
                color=_BLUE,
            ).set_footer(
                text="Enter \"none\" if you would not like to have a main image",
            ),
            timeout=300,
            break_check=lambda m: not url_rx.match(m.content),
        ).add_group_loop(
            names=[
                "role",
                "emoji",
            ],
            embeds=[
                discord.Embed(
                    title=_ET,
                    description=f"{ctx.author.mention}, please tag a role you would like to have available on the reactionroles",
                    color=_BLUE,
                ).set_footer(
                    text="Enter \"finish\" to complete finish this section"
                ),
                discord.Embed(
                    title=_ET,
                    description=f"{ctx.author.mention}, please react to this message with the reaction to be used to obtain the previously mentioned role",
                    color=_BLUE,
                ),
            ],
            timeouts=[300, 300],
            break_checks=[
                lambda m: m.content == "finish",
                None,
            ],
        ).add_step(
            name="integer",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the index of the reactionroles type you would like your panel to be. "
                "Here are all available types:\n\n" +
                "\n".join([
                    "**1:** Normal *(react to add, unreact to remove, as many reactions as there are options)*",
                    "**2:**, Reverse *(react to remove, unreact to add, as many reactions are there are options)*",
                    "**3:** Single Normal *(same as normal, limit 1 reaction)*",
                    "**4:** Limit *(same as normal, user defined limit)*",
                    "**5:** Permanent *(same as normal, does not remove on unreact)*",
                ]),
                color=_BLUE,
            ).set_footer(
                text="If you wanted to pick \"normal\", you would enter \"1\"",
            ),
            timeout=300,
            predicate=strict_int_check,
        ).add_conditional_step(
            name="integer",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the reaction limit for the reactionroles panel",
                color=_BLUE,
            ),
            timeout=300,
            predicate=loose_int_check,
            condition=lambda prev: prev == 4,
        )

        channel, title, description, color, thumbnail_url, image_url, roles_emojis, type_int, limit = await sp.start()

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
        )
        if thumbnail_url:
            embed.set_thumbnail(
                url=thumbnail_url,
            )
        if image_url:
            embed.set_image(
                url=image_url,
            )
        type_name = TYPE_NAME.get(type_int)
        return await self.send_rr_message(ctx, channel, embed, roles_emojis, type_name, limit)

    @reactionroles.command(aliases=['adjust', '-e'])
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True)
    @commands.has_permissions(manage_guild=True)
    async def edit(self, ctx, channel: discord.TextChannel, message_id: int = None):
        if not message_id:
            return await ctx.invoke(self.reactionroles)

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

        _ET = "Reactionroles Edit"
        _BLUE = discord.Color.blue()
        _FT = "Enter \"skip\" to keep the current {}"
        _SKIP = lambda m: m.content == "skip"

        def strict_int_check(m: discord.Message) -> bool:
            try:
                return m.author == ctx.author and m.channel == ctx.channel and (m.content == "skip" or 1 <= int(m.content) <= 5)
            except (ValueError, TypeError):
                return False

        def loose_int_check(m: discord.Message) -> bool:
            try:
                return m.author == ctx.author and m.channel == ctx.channel and (m.content == "skip" or int(m.content) >= 1)
            except (ValueError, TypeError):
                return False

        sp = SetupPanel(
            bot=self.bot,
            ctx=ctx,
            title="Reactionroles",
        ).add_step(
            name="title",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the new title of the embed",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("title"),
            ),
            timeout=300,
            predicate=lambda m: m.author == ctx.author and m.channel == ctx.channel and len(m.content) <= 256,
            break_check=_SKIP,
        ).add_step(
            name="description",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the new description of the embed",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("description"),
            ),
            timeout=300,
            break_check=_SKIP,
        ).add_step(
            name="color",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the new hex color of the embed",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("hex color"),
            ),
            timeout=300,
            predicate=lambda m: m.author == ctx.author and m.channel == ctx.channel and (
                m.content == "skip" or hex_color_rx.match(m.content)),
            break_check=_SKIP,
        ).add_step(
            name="content",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please input a URL to an image you would like to use as "
                "this embed's new thumbnail image (small image that appears on the top right)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("thumbnail image. ") + "Enter \"none\" if you would not like to have a thumbnail image",
            ),
            timeout=300,
            break_check=lambda m: not url_rx.match(m.content),
        ).add_step(
            name="content",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please input a URL to an image you would like to use as "
                "this embed's new main image (large image that appears on the bottom)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("main image. ") + "Enter \"none\" if you would not like to have a main image",
            ),
            timeout=300,
            break_check=lambda m: not url_rx.match(m.content),
        ).add_group_loop(
            names=[
                "role",
                "emoji",
            ],
            embeds=[
                discord.Embed(
                    title=_ET,
                    description=f"{ctx.author.mention}, please mention the new roles this reactionroles panel should contain",
                    color=_BLUE,
                ).set_footer(
                    text="Enter \"finish\" to finish adding roles. " +
                    _FT.format(
                        "roles. Mentioning a role and then doing \"skip\" will override the current roles with ones you've mentioned here"),
                ),
                discord.Embed(
                    title=_ET,
                    description=f"{ctx.author.mention}, please react to this message with the emoji that should be used for this reactionroles panel",
                    color=_BLUE,
                )
            ],
            timeouts=[300, 300],
            break_checks=[
                lambda m: m.content in ["skip", "finish"],
                None
            ]
        ).add_step(
            name="integer",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the index of the new reactionroles type you would like your panel to be. "
                "Here are all available types:\n\n" +
                "\n".join([
                    "**1:** Normal *(react to add, unreact to remove, as many reactions as there are options)*",
                    "**2:**, Reverse *(react to remove, unreact to add, as many reactions are there are options)*",
                    "**3:** Single Normal *(same as normal, limit 1 reaction)*",
                    "**4:** Limit *(same as normal, user defined limit)*",
                    "**5:** Permanent *(same as normal, does not remove on unreact)*",
                ]),
                color=_BLUE,
            ).set_footer(
                text="If you wanted to pick \"normal\", you would enter \"1\". " + _FT.format("behavior"),
            ),
            timeout=300,
            predicate=strict_int_check,
            break_check=_SKIP,
        ).add_conditional_step(
            name="integer",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the new reaction limit for your reactionroles panel",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("limit"),
            ),
            timeout=300,
            condition=lambda prev: prev == 5,
            predicate=loose_int_check,
            break_check=_SKIP,
        )

        title, description, color, thumbnail_url, image_url, roles_emojis, type_int, limit = await sp.start()
        old_message: discord.Message = await channel.fetch_message(message_id)
        old_embed: discord.Embed = old_message.embeds[0]
        embed: discord.Embed = old_embed.copy()
        if title:
            embed.title = title
        if description:
            embed.description = description
        if color:
            embed.color = color
        if thumbnail_url:
            embed.set_thumbnail(
                url=thumbnail_url
            )
        if image_url:
            embed.set_image(
                url=image_url
            )
        type_name = TYPE_NAME.get(type_int)

        return await self.edit_rr_message(
            ctx, old_message, embed, roles_emojis, type_name, limit
        )

    @reactionroles.command(aliases=['-d', 'rm', 'del'])
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True)
    @commands.has_permissions(manage_guild=True)
    async def delete(self, ctx, message_id: int = None):
        if not message_id:
            return await ctx.invoke(self.reactionroles)

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
                                    description=f"{ctx.author.mention}, deleting a reactionroles panel is a destructive"
                                    f" action that cannot be undone. React with {reactions[0]} to confirm or {reactions[1]} to cancel",
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)
        for reaction in reactions:
            try:
                await panel.add_reaction(reaction)
            except Exception:
                pass

        try:
            reaction, _ = await self.bot.wait_for(
                "reaction_add",
                check=lambda r, u: r.emoji in reactions and r.message == panel and u.id == ctx.author.id,
                timeout=30
            )
        except asyncio.TimeoutError:
            return await self.timeout(ctx, 30, panel)
        if reaction.emoji == reactions[0]:
            await self.gcmds.smart_delete(panel)
            return await self.delete_rr_message(ctx, message_id)
        else:
            return await self.user_canceled(ctx, panel)

    @reactionroles.command(aliase=["wipe"],)
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True)
    async def clear(self, ctx: Context):
        owner = ctx.guild.owner
        embed = discord.Embed(
            title="Reactionroles Successfully Cleared",
            description=f"{ctx.author.mention}, the reactionroles for this server have been deleted from the database",
            color=discord.Color.blue(),
        )
        if ctx.author.id != owner.id:
            embed.title = "Insufficient Permissions"
            embed.description = f"{ctx.author.mention}, you must be the server's owner in order to do this operation"
            embed.color = discord.Color.dark_red()
        else:
            async with self.bot.db.acquire() as con:
                messages = await con.fetch(f"SELECT message_id FROM base_rr WHERE guild_id={ctx.guild.id}")
                if messages:
                    for msg in messages:
                        await con.execute(f"DELETE FROM emoji_rr WHERE message_id={msg['message_id']}")
        return await ctx.channel.send(embed=embed)

    @commands.cooldown(1, 300, type=commands.BucketType.guild)
    @commands.command(aliases=['mr'],
                      desc="Gives specified roles to every user in the server",
                      usage="massrole [operation] [type] [@role]*va",
                      uperms=['Manage Server'],
                      bperms=['Manage Roles'],
                      note="This command can be used once per 15 minutes. "
                      "Valid options for `[operation]` are \"give\" or \"remove\". "
                      "Valid options for `(type)` are \"members\" and \"bots\"")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_guild=True)
    async def massrole(self, ctx, op: str, user_type: str, roles: commands.Greedy[discord.Role]):
        op, user_type = op.lower(), user_type.lower()
        if not user_type in ['member', 'members', 'bot', 'bots']:
            raise customerrors.MassroleInvalidType(user_type)
        elif not op in ['give', 'remove']:
            raise customerrors.MassroleInvalidOperation(op)
        else:
            async with ctx.channel.typing():
                if user_type in ['member', 'members']:
                    members = (member for member in ctx.guild.members if not member.bot and member != ctx.guild.me)
                else:
                    members = (member for member in ctx.guild.members if member.bot and member != ctx.guild.me)
                for member in members:
                    if op == "give":
                        func = member.add_roles
                    else:
                        func = member.remove_roles
                    with suppress(Exception):
                        await func(roles, reason=f"Given by {ctx.author} using massrole")
            if op == "give":
                title = "Roles Successfully Given"
                description = (f"{ctx.author.mention}, I've given all the roles you've specified "
                               f"to every {user_type.replace('s', '')} that I have permissions to give roles to")
            else:
                title = "Roles Successfully Removed"
                description = (f"{ctx.author.mention}, I've removed all the roles you've specified "
                               f"from every {user_type.replace('s', '')} that I have permissions to remove roles from")
            embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Roles(bot))
