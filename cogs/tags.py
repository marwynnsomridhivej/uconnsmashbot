import asyncio
import os
from datetime import datetime

import discord
from discord.ext import commands
from utils import customerrors, globalcommands, paginator, premium

gcmds = globalcommands.GlobalCMDS()
PROHIB_NAMES = []
reactions = ["✅", "🛑"]
timeout = 600


class Tags(commands.Cog):

    def __init__(self, bot):
        global gcmds, PROHIB_NAMES
        self.bot = bot
        PROHIB_NAMES = [command.name.lower() for command in self.bot.commands]
        for command in self.bot.commands:
            if command.aliases:
                for alias in command.aliases:
                    if not alias.lower() in PROHIB_NAMES:
                        PROHIB_NAMES.append(alias.lower())
        gcmds = globalcommands.GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_tags())

    async def init_tags(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS tags(guild_id bigint, author_id bigint, name text PRIMARY KEY,"
                              " message_content text, created_at NUMERIC, modified_at NUMERIC, global boolean DEFAULT FALSE, uuid uuid DEFAULT uuid_generate_v4())")

    async def tag_help(self, ctx) -> discord.Message:
        timestamp = f"Executed by {ctx.author.display_name} " + "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now())
        pfx = await gcmds.prefix(ctx)
        tag = (f"**Usage:** `{pfx}tag`\n"
               "**Returns:** This help menu\n"
               "**Aliases:** `tags`")
        list = (f"**Usage:** `{pfx}tag list`\n"
                "**Returns:** A list of all the tags you own, if any")
        search = (f"**Usage:** `{pfx}tag search`\n"
                  "**Returns:** A list of the top 20 tags that contain the query substring in the order of most used\n"
                  "**Special Cases:** If no tag is found, it will return an error message")
        create = (f"**Usage:** `{pfx}tag create (name)`\n"
                  "**Returns:** An interactive tag creation panel\n"
                  "**Aliases:** `make`\n"
                  "**Special Cases:** If the tag `name` already exists and you own it, you can choose to edit or delete it")
        edit = (f"**Usage:** `{pfx}tag edit (name)`\n"
                "**Returns:** An interactive tag edit panel\n"
                "**Special Cases:** If the tag does not exist, you will have the option to create it. You can only "
                "edit tags you own")
        delete = (f"**Usage:** `{pfx}tag delete`\n"
                  "**Returns:** A tag delete confirmation panel\n"
                  "**Aliases:** `remove`\n"
                  "**Special Cases:** The tag must exist and you must own the tag in order to delete it")
        cmds = [("Help", tag), ("List", list), ("Search", search),
                ("Create", create), ("Edit", edit), ("Delete", delete)]

        embed = discord.Embed(title="Tag Commands",
                              description=f"{ctx.author.mention}, tags are an easy way to create your own custom "
                              "command! Here are all the tag commands UconnSmashBot supports",
                              color=discord.Color.blue())
        embed.set_footer(text=timestamp, icon_url=ctx.author.avatar_url)
        for name, value in cmds:
            embed.add_field(name=name,
                            value=value,
                            inline=False)
        return await ctx.channel.send(embed=embed)

    async def check_tag(self, ctx, name) -> bool:
        if not name:
            raise customerrors.TagNotFound(name)

        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT uuid FROM tags WHERE name = $tag${name}$tag$ AND (guild_id = {ctx.guild.id} OR global=TRUE)")

        if not result:
            raise customerrors.TagNotFound(name)
        else:
            return True

    async def check_tag_exists(self, ctx, tag) -> bool:
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT uuid FROM tags WHERE name=$tag${tag}$tag$")
        return True if not result else False

    async def check_tag_owner(self, ctx, tag) -> bool:
        await self.check_tag(ctx, tag)
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT author_id FROM tags WHERE name = $tag${tag}$tag$")

        if not result or int(result[0]['author_id']) != ctx.author.id:
            raise customerrors.NotTagOwner(tag)
        else:
            return True

    async def create_tag(self, ctx, name, content) -> discord.Message:
        async with self.bot.db.acquire() as con:
            values = f"({ctx.guild.id}, {ctx.author.id}, $tag${name}$tag$, $tag${content}$tag$, {int(datetime.now().timestamp())})"
            await con.execute(f"INSERT INTO tags(guild_id, author_id, name, message_content, created_at) VALUES {values}")

        embed = discord.Embed(title="Tag Created",
                              description=f"{ctx.author.mention}, your tag `{name}` was created and can be accessed "
                              f"using `{await gcmds.prefix(ctx)}tag {name}`",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    async def send_tag(self, ctx, name: str) -> discord.Message:
        timestamp = "{:%m/%d/%Y %H:%M:%S}".format(datetime.now())
        async with self.bot.db.acquire() as con:
            info = (await con.fetch(f"SELECT message_content FROM tags WHERE name = $tag${name}$tag$ and (guild_id = {ctx.guild.id} OR global=TRUE)"))[0]
        content = info['message_content']
        embed = discord.Embed(description=content,
                              color=discord.Color.blue())
        embed.set_author(name=name, icon_url=ctx.author.avatar_url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name} at {timestamp}")
        await ctx.channel.send(embed=embed)

    async def list_user_tags(self, ctx) -> list:
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT * from tags WHERE (guild_id = {ctx.guild.id} OR global=TRUE) AND author_id = {ctx.author.id}")

        if not result:
            raise customerrors.UserNoTags(ctx.author)

        desc_list = [f"**{tag['name']}** [UUID: {tag['uuid']}]\n*created at "
                     f"{datetime.fromtimestamp(int(tag['created_at'])).strftime('%m/%d/%Y %H:%M:%S')}* {'(global)' if tag['global'] else ''}\n" for tag in result]
        return sorted(desc_list)

    async def get_user_tag_amount(self, ctx):
        try:
            tags = await self.list_user_tags(ctx)
        except customerrors.UserNoTags:
            tags = []
        if len(tags) >= 100 and not premium.check_user_premium(ctx.author):
            raise customerrors.TagLimitReached(ctx.author)

    async def search_tags(self, ctx, keyword) -> list:
        async with self.bot.db.acquire() as con:
            await con.execute("SELECT set_limit(0.1)")
            result = await con.fetch(f"SELECT name, uuid, global FROM tags WHERE name % $tag${keyword}$tag$ AND (guild_id = {ctx.guild.id} OR global=TRUE) LIMIT 100")
        if not result:
            raise customerrors.NoSimilarTags(keyword)
        else:
            return [f"**{tag['name']}** [UUID: {tag['uuid']}]\n{'(global)' if tag['global'] else ''}" for tag in result]

    async def edit_tag(self, ctx, orig_name, tag, content) -> bool:
        ts = int(datetime.now().timestamp())
        try:
            async with self.bot.db.acquire() as con:
                if not content and tag:
                    op = f"UPDATE tags SET name=$tag${tag}$tag$, modified_at={ts} WHERE name=$tag${orig_name}$tag$ AND author_id = {ctx.author.id}"
                elif content and tag:
                    op = f"UPDATE tags SET name=$tag${tag}$tag$, message_content=$tag${content}$tag$, modified_at={ts} WHERE name=$tag${orig_name}$tag$ AND author_id = {ctx.author.id}"
                elif not tag and content:
                    op = f"UPDATE tags set message_content=$tag${content}$tag$, modified_at={ts} WHERE name={orig_name} AND author_id = {ctx.author.id}"
                else:
                    return False
                await con.execute(op)
            return True
        except Exception:
            return False

    async def delete_tag(self, ctx, tag) -> discord.Message:
        try:
            async with self.bot.db.acquire() as con:
                await con.execute(f"DELETE FROM tags WHERE name=$tag${tag}$tag$ AND author_id={ctx.author.id}")
            embed = discord.Embed(title="Successfully Deleted Tag",
                                  description=f"{ctx.author.mention}, your tag `{tag}` was deleted",
                                  color=discord.Color.blue())
        except Exception:
            embed = discord.Embed(title="Delete Tag Failed",
                                  description=f"{ctx.author.mention}, your tag `{tag}` could not be deleted",
                                  color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def check_tag_name_taken(self, ctx, tag) -> bool:
        async with self.bot.db.acquire() as con:
            result = await con.fetch(f"SELECT uuid from tags WHERE name = $tag${tag}$tag$")
        return True if result else False

    async def get_global(self, ctx, tag) -> bool:
        try:
            async with self.bot.db.acquire() as con:
                status = (await con.fetch(f"SELECT global FROM tags WHERE name=$tag${tag}$tag$ AND author_id={ctx.author.id}"))[0]['global']
            return bool(status)
        except Exception as e:
            raise customerrors.TagError(error=e)

    async def edit_global(self, ctx, tag, status: bool) -> discord.Message:
        try:
            async with self.bot.db.acquire() as con:
                await con.execute(f"UPDATE tags SET global={status} WHERE name=$tag${tag}$tag$ AND author_id = {ctx.author.id}")
            title = "Global Tag Update Success"
            color = discord.Color.blue()
            if status:
                description = (f"{ctx.author.mention}, your tag `{tag}` is now global, meaning you can access it from "
                               "anywhere, as long as I am in that server")
            else:
                description = (f"{ctx.author.mention}, your tag `{tag}` is no longer global, meaning that you can access "
                               "it only in the server it was originally created")
        except Exception:
            title = "Global Tag Update Failed"
            description = f"{ctx.author.mention}, your tag `{tag}` could not be edited"
            color = discord.Color.dark_red()

        embed = discord.Embed(title=title, description=description, color=color)
        return await ctx.channel.send(embed=embed)

    async def check_panel(self, ctx, panel):
        try:
            if panel.id:
                return True
        except (discord.NotFound, discord.Forbidden):
            return False

    @commands.group(invoke_without_command=True,
                    aliases=['tags'],
                    desc="Calls a registered tag's set response",
                    usage="tag (name)",
                    note="If `(name)` is unspecified, the help command for tag will be displayed")
    async def tag(self, ctx, *, tag: str = None):
        if not tag:
            return await self.tag_help(ctx)
        if await self.check_tag(ctx, tag):
            return await self.send_tag(ctx, tag)

    @tag.command()
    async def list(self, ctx):
        desc_list = await self.list_user_tags(ctx)
        pag = paginator.EmbedPaginator(ctx, entries=desc_list, per_page=10)
        pag.embed.title = "Your Tags"
        return await pag.paginate()

    @tag.command()
    async def search(self, ctx, *, keyword):
        entries = await self.search_tags(ctx, keyword)
        pag = paginator.EmbedPaginator(ctx, entries=entries, per_page=10, show_entry_count=True)
        pag.embed.title = "Search Results"
        return await pag.paginate()

    @tag.command(aliases=['make'])
    async def create(self, ctx, *, tag):
        if tag.lower() in PROHIB_NAMES:
            raise customerrors.InvalidTagName(tag)
        await self.check_tag_exists(ctx, tag)
        embed = discord.Embed(title=f"Create Tag \"{tag}\"",
                              description=f"{ctx.author.mention}, within 2 minutes, please enter what you would like the tag to return\n\n"
                              f"ex. *If you enter \"test\", doing `{await gcmds.prefix(ctx)}tag {tag}` will return \"test\"*",
                              color=discord.Color.blue())
        embed.set_footer(text="Enter \"cancel\" to cancel this setup")
        panel = await ctx.channel.send(embed=embed)

        def from_user(message: discord.Message) -> bool:
            return message.author.id == ctx.author.id and message.channel == ctx.channel

        try:
            result = await self.bot.wait_for("message", check=from_user, timeout=timeout)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, "tag creation", timeout)
        if result.content == "cancel":
            return gcmds.cancelled(ctx, "tag creation")
        await gcmds.smart_delete(result)

        try:
            await panel.delete()
        except Exception:
            pass

        return await self.create_tag(ctx, tag, result.content)

    @tag.command()
    async def edit(self, ctx, *, tag):
        await self.check_tag_owner(ctx, tag)

        async def from_user(message: discord.Message):
            return message.author.id == ctx.author.id and not await self.check_tag_name_taken(ctx, message.content)

        def from_user_content_only(message: discord.Message):
            return message.author.id == ctx.author.id and message.channel.id == ctx.channel.id

        default = "or enter *\"skip\"* to keep the current value"

        panel_embed = discord.Embed(title="Edit Tag",
                                    description=f"{ctx.author.mention}, please enter the tag's new name {default}\n\nCurrent Name: {tag}",
                                    color=discord.Color.blue())
        panel_embed.set_footer(text="Enter \"cancel\" to cancel at any time")
        panel = await ctx.channel.send(embed=panel_embed)

        # User can edit tag name
        while True:
            try:
                if not await self.check_panel(ctx, panel):
                    return await gcmds.panel_deleted(ctx, "tag edit")
                result = await self.bot.wait_for("message", check=from_user, timeout=30)
            except asyncio.TimeoutError:
                return await gcmds.timeout(ctx, "tag edit", 30)
            if result.content == "cancel":
                return await gcmds.cancelled(ctx, "tag edit")
            else:
                if result.content.lower() in PROHIB_NAMES:
                    raise customerrors.InvalidTagName(tag)
                else:
                    new_name = result.content if result.content != "skip" else tag
                    break
        await gcmds.smart_delete(result)

        async with self.bot.db.acquire() as con:
            orig_content = (await con.fetch(f"SELECT message_content FROM tags WHERE author_id = {ctx.author.id} AND name = $tag${tag}$tag$"))[0]['message_content']

        panel_embed.description = f"{ctx.author.mention}, please enter the tag's new content {default}\n\nCurrent Content: {orig_content}"

        try:
            await panel.edit(embed=panel_embed)
        except (discord.Forbidden, discord.NotFound):
            return await gcmds.panel_deleted(ctx, "tag edit")

        # User can edit tag content
        try:
            if not await self.check_panel(ctx, panel):
                return await gcmds.panel_deleted(ctx, "tag edit")
            result = await self.bot.wait_for("message", check=from_user_content_only, timeout=240)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, "tag edit", 240)
        if result.content == "cancel":
            return await gcmds.cancelled(ctx, "tag edit")
        else:
            new_content = result.content if result.content != "skip" else None

        succeeded = await self.edit_tag(ctx, tag, new_name, new_content)
        if succeeded:
            title = "Successfully Edited Tag"
            description_list = []
            if new_name != tag:
                description_list.append(f"`{tag}` ⟶ `{new_name}`")
            if new_content and new_content != orig_content:
                description_list.append(f"New Tag Content:\n```{new_content}\n```")
            description = (f"{ctx.author.mention}, your tag was successfully edited\n\n" + "\n\n".join(description_list)
                           ) if description_list else f"{ctx.author.mention}, your tag was not edited"
            color = discord.Color.blue()
        else:
            title = "Unable to Edit Tag"
            description = f"{ctx.author.mention}, your tag could not be edited"
            color = discord.Color.dark_red()

        embed = discord.Embed(title=title,
                              description=description,
                              color=color)
        try:
            await panel.edit(embed=embed)
        except Exception:
            await ctx.channel.send(embed=embed)

    @tag.command(aliaes=['remove'])
    async def delete(self, ctx, *, tag):
        await self.check_tag_owner(ctx, tag)

        panel_embed = discord.Embed(title="Confirm Tag Deletion",
                                    description=f"{ctx.author.mention}, you are about to delete the tag `{tag}`. "
                                    f"This action is destructive and cannot be undone. React with {reactions[0]} to "
                                    f"confirm or {reactions[1]} to cancel",
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)
        for reaction in reactions:
            await panel.add_reaction(reaction)

        def reacted(reaction: discord.Reaction, user: discord.User) -> bool:
            return reaction.emoji in reactions and user.id == ctx.author.id and reaction.message.id == panel.id

        try:
            result = await self.bot.wait_for("reaction_add", check=reacted, timeout=30)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, "tag delete", 30)
        try:
            await panel.delete()
        except Exception:
            pass
        if result[0].emoji == reactions[0]:
            return await self.delete_tag(ctx, tag)
        else:
            return await gcmds.cancelled(ctx, "tag delete")

    @premium.is_premium(req_user=True)
    @tag.command(aliases=['mg'])
    async def makeGlobal(self, ctx, tag):
        await self.check_tag_owner(ctx, tag)
        status = not (await self.get_global(ctx, tag))
        description = (f"{ctx.author.mention}, you are about to make the tag `{tag}` {'global' if status else 'not global anymore'}. "
                       f"React with {reactions[0]} to confirm or {reactions[1]} to cancel.")

        def reacted(reaction: discord.Reaction, user: discord.User) -> bool:
            return reaction.emoji in reactions and user.id == ctx.author.id and reaction.message.id == panel.id

        panel_embed = discord.Embed(title="Confirm Changing Tag Global Status",
                                    description=description,
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)
        for reaction in reactions:
            await panel.add_reaction(reaction)

        try:
            result = await self.bot.wait_for("reaction_add", check=reacted, timeout=30)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, "tag edit global status", 30)
        try:
            await panel.delete()
        except Exception:
            pass
        if result[0].emoji == reactions[0]:
            return await self.edit_global(ctx, tag, status)
        else:
            return await gcmds.cancelled(ctx, "tag edit global status")

def setup(bot):
    bot.add_cog(Tags(bot))
