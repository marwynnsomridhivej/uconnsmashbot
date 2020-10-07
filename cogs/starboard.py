import asyncio

import discord
from discord.ext import commands
from utils import customerrors, globalcommands

gcmds = globalcommands.GlobalCMDS()
levels = ['⭐', '✨', '🌟', '💫']


class Starboard(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_starboard())

    async def init_starboard(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS starboard(orig_message_id bigint, message_id bigint PRIMARY KEY, guild_id bigint, "
                              "jump_url text, counter int DEFAULT 1)")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.bot.wait_until_ready()

        user = await self.bot.fetch_user(payload.user_id)
        if user.bot:
            return

        channel = await self.bot.fetch_channel(payload.channel_id)
        if not channel.guild:
            return

        emoji = payload.emoji
        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        async with self.bot.db.acquire() as con:
            sbc = await con.fetchval(f"SELECT starboard_channel FROM guild WHERE guild_id={message.guild.id}")
            registered_emoji = await con.fetchval(f"SELECT starboard_emoji FROM guild WHERE guild_id={channel.guild.id}")
            orig = await con.fetchval(f"SELECT orig_message_id FROM starboard WHERE orig_message_id={message.id}")
            on_sb = await con.fetchval(f"SELECT message_id FROM starboard WHERE message_id={message.id} OR orig_message_id={message.id}")

        if str(emoji) != registered_emoji:
            return
        elif not (orig or on_sb):
            sbc = await self.bot.fetch_channel(sbc)
            return (await self.push_starboard(message, sbc, emoji=emoji) if sbc
                    else await self.push_starboard(message, emoji=emoji))
        else:
            sbc = await self.bot.fetch_channel(sbc)
            on_sb = await sbc.fetch_message(on_sb)
            return await self.update_starboard(on_sb, sbc, "add", emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.bot.wait_until_ready()

        user = await self.bot.fetch_user(payload.user_id)
        if user.bot:
            return

        channel = await self.bot.fetch_channel(payload.channel_id)
        if not channel.guild:
            return

        emoji = payload.emoji
        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        async with self.bot.db.acquire() as con:
            sbc = await con.fetchval(f"SELECT starboard_channel FROM guild WHERE guild_id={message.guild.id}")
            registered_emoji = await con.fetchval(f"SELECT starboard_emoji FROM guild WHERE guild_id={channel.guild.id}")
            on_sb = await con.fetchval(f"SELECT message_id FROM starboard WHERE message_id={message.id} OR orig_message_id={message.id}")

        if not emoji != registered_emoji or not on_sb:
            return
        else:
            if sbc:
                sbc = await self.bot.fetch_channel(sbc)
                on_sb = await sbc.fetch_message(on_sb)
            return await self.update_starboard(on_sb, sbc, "remove", emoji)

    async def push_starboard(self, message: discord.Message, sbc: discord.TextChannel = None, emoji=None):
        if not sbc:
            for text_channel in message.guild.text_channels:
                if 'starboard' in text_channel.name.lower():
                    sbc = text_channel
                    break
            else:
                overwrites = {
                    message.guild.default_role: discord.PermissionOverwrite(send_messages=False),
                    message.guild.me: discord.PermissionOverwrite(send_messages=True)
                }
                sbc = await message.guild.create_text_channel(name="starboard", overwrites=overwrites)

        if not message.embeds:
            description = message.content
        else:
            description = message.embeds[0].description
        embed = discord.Embed(title="Original Message",
                              description=description + f"\n\n> Click on the [Jump URL]({message.jump_url}) to see me!",
                              color=discord.Color.blue())
        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
        embed.set_footer(text=f"{levels[0]} Upvoted 1 time. React with {emoji} to upvote!")

        if message.attachments:
            attachment = message.attachments[0]
            if not attachment.is_spoiler() and attachment.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                embed.set_image(url=attachment.url)
            else:
                if attachment.is_spoiler():
                    value = f"||[{attachment.filename}]({attachment.url})||"
                else:
                    value = f"[{attachment.filename}]({attachment.url})"
                embed.add_field(name="Attachments", value=value, inline=False)
        sb_message = await sbc.send(embed=embed)
        await sb_message.add_reaction(emoji)

        async with self.bot.db.acquire() as con:
            values = f"({message.id}, {sb_message.id}, {message.guild.id}, '{sb_message.jump_url}')"
            await con.execute(f"INSERT INTO starboard VALUES {values}")
            await con.execute(f"UPDATE guild SET starboard_channel={sbc.id} WHERE guild_id={message.guild.id}")
        return

    async def update_starboard(self, sb_message: discord.Message, sb_channel: discord.TextChannel, mode, emoji):
        if mode == "add":
            async with self.bot.db.acquire() as con:
                counter = await con.fetchval(f"UPDATE starboard SET counter=counter+1 WHERE message_id={sb_message.id} RETURNING counter")
        else:
            async with self.bot.db.acquire() as con:
                counter = await con.fetchval(f"UPDATE starboard SET counter=counter-1 WHERE message_id={sb_message.id} RETURNING counter")

        if counter != 0:
            embed_copy = sb_message.embeds[0]
            counter_emoji = levels[counter // 10 if counter // 10 <= 4 else 4]
            embed_copy.set_footer(text=f"{counter_emoji} Upvoted {counter} {'times' if counter != 1 else 'time'}. React with {emoji} to upvote!")
            return await sb_message.edit(embed=embed_copy)
        else:
            async with self.bot.db.acquire() as con:
                await con.execute(f"DELETE FROM starboard WHERE message_id={sb_message.id}")
            await gcmds.smart_delete(sb_message)

    async def starboard_help(self, ctx) -> discord.Message:
        pfx = f"{await gcmds.prefix(ctx)}starboard"
        description = (f"{ctx.author.mention}, the base command is `{pfx}` *alias=`sb`*. The starboard is a functino of UconnSmashBot "
                       "that will allow you to create a \"gallery\" of funny messages just by reacting to it with a "
                       "specified starboard reaction. Here are all the subcommands")
        schannel = (f"**Usage:** `{pfx} channel [#channel]`",
                    "**Returns:** An embed that confirms your starboard channel was successfully bound",
                    "**Aliases:** `cn`",
                    "**Special Cases:** If this command has not been called or a channel has not been specified, UconnSmashBot "
                    "will automatically create a new channel called \"starboard\" if such a channel doesn't already exist")
        sset = (f"**Usage:** `{pfx} set [emoji]`",
                "**Returns:** An embed that confirms your emoji binding was successful",
                "**Aliases:** `-s` `bind` `use`",
                "**Note:** `[emoji]` must be an emoji. Do not escape markdown")
        slist = (f"**Usage:** `{pfx} list`",
                 "**Returns:** Your current emoji that when used to react to a message, will trigger a starboard post, "
                 "as well as the starboard channel tag",
                 "**Aliases:** `-ls` `show`")
        sremove = (f"**Usage:** `{pfx} remove`",
                   "**Returns:** An embed that confirms your emoji was unbound from starboard trigger",
                   "**Aliases:** `-rm` `clear` `reset` `delete`")
        nv = [("Channel", schannel), ("Set", sset), ("List", slist), ("Remove", sremove)]
        embed = discord.Embed(title="Starboard Help", description=description, color=discord.Color.blue())
        for name, value in nv:
            embed.add_field(name=name, value="> " + "\n> ".join(value), inline=False)
        embed.set_footer(text="Note that you can disable the starboard just by unbinding the emoji")
        return await ctx.channel.send(embed=embed)

    async def migrate_starboard(self, ctx, channel_id):
        try:
            channel = await self.bot.fetch_channel(int(channel_id))
        except Exception:
            return

        async with self.bot.db.acquire() as con:
            prev_entries = await con.fetch(f"SELECT * FROM starboard WHERE guild_id={ctx.guild.id} ORDER BY message_id ASC")
            if not prev_entries:
                return

            status_embed = discord.Embed(title="Migration Status",
                                         description=f"Finished migrating starboard entry 0 / {len(prev_entries)}",
                                         color=discord.Color.blue())
            status = await ctx.channel.send(embed=status_embed)

            for entry in prev_entries:
                asyncio.sleep(2.0)
                try:
                    prev_message = await channel.fetch_message(int(entry['message_id']))
                except Exception:
                    continue
                embed = prev_message.embeds[0]
                new_message = await channel.send(embed=embed)
                await con.execute(f"UPDATE starboard SET message_id={new_message.id} WHERE message_id={int(entry['message_id'])}")
                status_embed.description = f"Finished migrating starboard entry {prev_entries.index(entry) + 1} / {len(prev_entries)}"
                await status.edit(embed=status)

            await asyncio.sleep(2.0)
            await gcmds.smart_delete(status)
            return

    async def set_starboard_emoji(self, ctx, emoji):
        async with self.bot.db.acquire() as con:
            await con.execute(f"UPDATE guild SET starboard_emoji=$emoji${emoji}$emoji$ WHERE guild_id={ctx.guild.id}")
        return

    async def get_starboard(self, ctx):
        async with self.bot.db.acquire() as con:
            channel_id = await con.fetchval(f"SELECT starboard_channel FROM guild WHERE guild_id={ctx.guild.id}")
            emoji_id = await con.fetchval(f"SELECT starboard_emoji FROM guild WHERE guild_id={ctx.guild.id}")
        if not channel_id and not emoji_id:
            raise customerrors.NoStarboard()
        description = ""
        if channel_id:
            description += f"Channel: <#{channel_id}>"
        if emoji_id:
            emoji = [emoji for emoji in ctx.guild.emojis if emoji.id == int(emoji_id)]
            description += f"Emoji: {''.join(emoji)}"
        embed = discord.Embed(title="Starboard Info", description=description, color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    async def remove_starboard_emoji(self, ctx):
        async with self.bot.db.acquire() as con:
            await con.execute(f"UPDATE guild SET starboard_emoji=NULL WHERE guild_id={ctx.guild.id}")
        return

    @commands.group(invoke_without_command=True,
                    aliases=['sb'],
                    desc="Displays the help command for starboard",
                    usage="starboard")
    async def starboard(self, ctx):
        return await self.starboard_help(ctx)

    @starboard.command(aliases=['cn', 'channel'])
    @commands.has_permissions(manage_guild=True)
    async def starboard_channel(self, ctx, channel: discord.TextChannel):
        async with self.bot.db.acquire() as con:
            prev_channel_id = await con.fetchval(f"SELECT starboard_channel FROM guild WHERE guild_id={ctx.guild.id}")
            await con.execute(f"UPDATE guild SET starboard_channel={channel.id} WHERE guild_id={ctx.guild.id}")
        if prev_channel_id:
            await self.migrate_starboard(ctx, prev_channel_id)
        embed = discord.Embed(title="Starboard Channel Bound",
                              description=f"{ctx.author.mention}, the starboard channel has been bound to {channel.mention}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @starboard.command(aliases=['-s', 'bind', 'use', 'set'])
    @commands.has_permissions(manage_guild=True)
    async def starboard_set(self, ctx, emoji):
        await self.set_starboard_emoji(ctx, emoji)
        embed = discord.Embed(title="Startboard Emoji Bound",
                              description=f"{ctx.author.mention}, the bound emoji is {emoji}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @starboard.command(aliases=['-ls', 'show', 'list'])
    async def starboard_list(self, ctx):
        return await self.get_starboard(ctx)

    @starboard.command(aliases=['-rm', 'clear', 'reset', 'delete', 'remove'])
    @commands.has_permissions(manage_guild=True)
    async def starboard_remove(self, ctx):
        await self.remove_starboard_emoji(ctx)
        embed = discord.Embed(title="Starboard Emoji Unbound",
                              description=f"{ctx.author.mention}, the starboard emoji was unbound. Starboard will be "
                              "disabled until an emoji is rebound",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Starboard(bot))
