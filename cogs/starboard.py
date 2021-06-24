import asyncio
from math import ceil, floor, log

import discord
from discord.embeds import EmptyEmbed
from discord.ext import commands
from discord.ext.commands import Context
from setuppanel import SetupPanel
from utils import FieldPaginator, GlobalCMDS, SubcommandHelp

levels = ['⭐', '✨', '🌟', '💫']
_CONF = ['✅', '❌']
_THRESHOLD = lambda g, c, t: c >= int(t) if t else (
    c >= int(ceil(log(len([member for member in g.members if not member.bot]), 4)) or 1)
)
_GET_EMOJI = lambda c: levels[floor(c / 5) if floor(c / 5) < 3 else 3]


class Starboard(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_starboard())

    async def init_starboard(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute(
                "CREATE TABLE IF NOT EXISTS starboard(orig_message_id bigint, message_id bigint PRIMARY KEY, guild_id bigint, channel_id bigint, emoji TEXT)"
            )
            await con.execute(
                "CREATE TABLE IF NOT EXISTS starboard_config(guild_id bigint, channel_id bigint PRIMARY KEY, emoji TEXT, threshold NUMERIC DEFAULT NULL)"
            )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        member: discord.Member = payload.member
        if member and not member.bot:
            emoji: discord.Emoji = payload.emoji
            async with self.bot.db.acquire() as con:
                dispatch_channel_id: int = await con.fetchval(
                    f"SELECT channel_id FROM starboard_config WHERE guild_id={member.guild.id} AND emoji=$emj${emoji}$emj$"
                )
                sb_message_id = await con.fetchval(
                    f"SELECT message_id FROM starboard WHERE orig_message_id={payload.message_id}"
                )
                threshold = await con.fetchval(
                    f"SELECT threshold FROM starboard_config WHERE guild_id={member.guild.id} AND emoji=$emj${emoji}$emj$"
                )
            if dispatch_channel_id:
                dispatch_channel: discord.TextChannel = self.bot.get_channel(int(dispatch_channel_id))
                channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
                message: discord.Message = await channel.fetch_message(payload.message_id)
                reaction: discord.Reaction = [r for r in message.reactions if str(r.emoji) == str(emoji)][0]
                count = len([user for user in await reaction.users().flatten() if not user.bot])
                if not sb_message_id and _THRESHOLD(message.guild, count, threshold):
                    await self._dispatch(dispatch_channel, message, emoji, count)
                elif sb_message_id:
                    sb_message = await dispatch_channel.fetch_message(int(sb_message_id))
                    await self._update(sb_message, count, threshold)
        return

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        guild: discord.Guild = self.bot.get_guild(int(payload.guild_id))
        member: discord.Member = guild.get_member(int(payload.user_id))
        if member and not member.bot:
            emoji: discord.Emoji = payload.emoji
            async with self.bot.db.acquire() as con:
                dispatch_channel_id: int = await con.fetchval(
                    f"SELECT channel_id FROM starboard_config WHERE guild_id={member.guild.id} AND emoji=$emj${emoji}$emj$"
                )
                sb_message_id = await con.fetchval(
                    f"SELECT message_id FROM starboard WHERE orig_message_id={payload.message_id} and emoji=$emj${emoji}$emj$"
                )
                threshold = await con.fetchval(
                    f"SELECT threshold FROM starboard_config WHERE guild_id={member.guild.id} AND emoji=$emj${emoji}$emj$"
                )
            if sb_message_id:
                channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
                message: discord.Message = await channel.fetch_message(payload.message_id)
                try:
                    reaction: discord.Reaction = [r for r in message.reactions if str(r.emoji) == str(emoji)][0]
                except IndexError:
                    count = 0
                else:
                    count = len([user for user in await reaction.users().flatten() if not user.bot])
                sb_channel: discord.TextChannel = self.bot.get_channel(int(dispatch_channel_id))
                sb_message = await sb_channel.fetch_message(int(sb_message_id))
                await self._update(sb_message, count, threshold)
        return

    async def _dispatch(self, channel: discord.TextChannel, orig_message: discord.Message, emoji: str, count: int) -> discord.Message:
        embed = discord.Embed(
            description=orig_message.content if orig_message.content else
            orig_message.embeds[0].description if orig_message.embeds else
            EmptyEmbed,
            color=discord.Color.blue(),
        ).add_field(
            name="Original Message",
            value=f"[Click Here]({orig_message.jump_url})",
            inline=False,
        ).set_author(
            name=orig_message.author.display_name,
            icon_url=orig_message.author.avatar_url,
        ).set_footer(
            text=f"{_GET_EMOJI(count)} Upvoted {count} time{'s' if count != 1 else ''}!"
        )
        if orig_message.attachments:
            attachment = orig_message.attachments[0]
            if not attachment.is_spoiler() and attachment.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                embed.set_image(url=attachment.url)
        message = await channel.send(embed=embed)
        async with self.bot.db.acquire() as con:
            await con.execute(
                f"INSERT INTO starboard(orig_message_id, message_id, guild_id, channel_id, emoji) "
                f"VALUES({orig_message.id}, {message.id}, {message.guild.id}, {channel.id}, $emj${emoji}$emj$)"
            )
        return

    async def _update(self, message: discord.Message, count: int, threshold: int):
        if not _THRESHOLD(message.guild, count, threshold):
            async with self.bot.db.acquire() as con:
                await con.execute(
                    f"DELETE FROM starboard WHERE message_id={message.id} AND guild_id={message.guild.id}"
                )
            await self.gcmds.smart_delete(message)
        elif message.embeds:
            embed: discord.Embed = message.embeds[0].copy()
            embed.set_footer(
                text=f"{_GET_EMOJI(count)} Upvoted {count} time{'s' if count != 1 else ''}!"
            )
            await message.edit(embed=embed)

    async def starboard_help(self, ctx) -> discord.Message:
        pfx = f"{await self.gcmds.prefix(ctx)}starboard"
        return await SubcommandHelp(
            pfx=pfx,
            title="Starboard Help",
            description=(
                f"{ctx.author.mention}, the base command is `{pfx}` *alias=`sb`*. The starboard is a function of UconnSmashBot "
                "that will allow you to create a \"gallery\" of funny messages just by reacting to it with a "
                "specified starboard reaction. Here are all the subcommands"
            ),
            per_page=4,
        ).from_config("starboard").show_help(ctx)

    async def _check_exists(self, ctx: Context, **options) -> bool:
        async with self.bot.db.acquire() as con:
            for key, value in options.items():
                res = await con.fetchval(f"SELECT guild_id FROM starboard_config WHERE guild_id={ctx.guild.id} AND {key}={value}")
                if bool(res):
                    break
            else:
                return False
        return True

    async def register_starboard(self, ctx: Context, channel: discord.TextChannel, emoji: str, threshold: int) -> discord.Message:
        embed = discord.Embed(
            title="Starboard Registered",
            description=f"{ctx.author.mention}, you may now push messages to the starboard at {channel.mention} by reacting with the emoji {emoji}",
            color=discord.Color.dark_red(),
        )
        if await self._check_exists(ctx, channel_id=channel.id, emoji=f"$emj${emoji}$emj$"):
            embed.title = "Starboard Already Registered"
            embed.description = f"{ctx.author.mention}, a starboard with the specified channel or emoji already exists"
        else:
            perms = channel.permissions_for(ctx.guild.me)
            if perms.send_messages:
                async with self.bot.db.acquire() as con:
                    await con.execute(
                        f"INSERT INTO starboard_config(guild_id, channel_id, emoji, threshold) VALUES ({ctx.guild.id}, "
                        f"{channel.id}, $emj${str(emoji)}$emj$, {threshold if threshold else 'NULL'})"
                    )
                embed.color = discord.Color.blue()
            else:
                embed.title = "Insufficient Bot Permissions"
                embed.description = f"{ctx.author.mention}, I do not have permissions to send messages in {channel.mention}"
        return await ctx.channel.send(embed=embed)

    async def unregister_starboard(self, ctx: Context, channel: discord.TextChannel) -> discord.Message:
        embed = discord.Embed(
            title="Starboard Unregistered",
            description=f"{ctx.author.mention}, the starboard for the channel {channel.mention} and its corresponding "
            "emoji have been unregistered",
            color=discord.Color.blue(),
        )
        if not await self._check_exists(ctx, channel_id=channel.id):
            embed.title = "No Starboard Registered"
            embed.description = f"{ctx.author.mention}, there is already no starboard registered for the channel {channel.mention}"
            embed.color = discord.Color.dark_red()
        else:
            async with self.bot.db.acquire() as con:
                await con.execute(f"DELETE FROM starboard_config WHERE guild_id={ctx.guild.id} AND channel_id={channel.id}")
                await con.execute(f"DELETE FROM starboard WHERE channel_id={channel.id} AND guild_id={channel.guild.id}")
        return await ctx.channel.send(embed=embed)

    async def list_starboard_details(self, ctx: Context) -> discord.Message:
        async with self.bot.db.acquire() as con:
            data = await con.fetch(f"SELECT channel_id, emoji, threshold FROM starboard_config WHERE guild_id={ctx.guild.id}")
        if data:
            entries = []
            for entry in data:
                channel = ctx.guild.get_channel(int(entry["channel_id"]))
                entries.append((
                    f"Channel: {channel.name}",
                    "\n".join([
                        f"Channel Tag: {channel.mention}",
                        f"Emoji: {entry['emoji']}",
                        f"Custom Threshold: {int(entry['threshold']) if entry['threshold'] else 'N/A'}",
                    ]),
                    False,
                ))
            return await FieldPaginator(
                ctx,
                entries=entries,
                per_page=4,
                embed=discord.Embed(
                    title="Starboards",
                    description="Below are a list of all registered starboards in this server with their channel and emoji bindings",
                    color=discord.Color.blue(),
                )
            ).paginate()
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Starboards",
                description="This server has no registered starboards",
                color=discord.Color.blue(),
            )
        )

    @commands.group(invoke_without_command=True,
                    aliases=['sb'],
                    desc="Displays the help command for starboard",
                    usage="starboard")
    async def starboard(self, ctx: Context):
        return await self.starboard_help(ctx)

    @starboard.command(name="list",
                       aliases=["ls", "show"],)
    async def starboard_list(self, ctx: Context):
        return await self.list_starboard_details(ctx)

    @starboard.command(name="register",
                       aliases=["reg", "create"],)
    @commands.has_permissions(manage_guild=True)
    async def starboard_register(self, ctx: Context):
        def _require_positive(message: discord.Message) -> bool:
            try:
                ret = int(message.content)
                if ret >= 1:
                    return False
            except (TypeError, ValueError):
                pass
            return True

        sp = SetupPanel(
            bot=self.bot,
            ctx=ctx,
            title="Register Starboard",
        ).add_step(
            name="channel",
            embed=discord.Embed(
                title="Register Starboard",
                description=f"{ctx.author.mention}, please tag the channel you would like to make a starboard channel",
                color=discord.Color.blue(),
            ),
            timeout=300,
        ).add_step(
            name="emoji",
            embed=discord.Embed(
                title="Register Starboard",
                description=f"{ctx.author.mention}, please react to this embed with the emoji that will add this message to the starboard",
                color=discord.Color.blue(),
            ),
            timeout=300,
        ).add_step(
            name="integer",
            embed=discord.Embed(
                title="Register Starboard",
                description=f"{ctx.author.mention}, please specify how many reactions a given message needs to have in order "
                "to be pushed to the starboard, or 'none' to use the default threshold",
                color=discord.Color.blue(),
            ),
            timeout=300,
            break_check=_require_positive,
        )
        res = await sp.start()
        if res:
            return await self.register_starboard(ctx, *res)

    @starboard.command(name="unregister",
                       aliases=["unreg", "delete"],)
    @commands.has_permissions(manage_guild=True,)
    async def starboard_unregister(self, ctx: Context, channel: discord.TextChannel):
        message = await ctx.channel.send(
            embed=discord.Embed(
                title="Confirm Unregister",
                description=f"{ctx.author.mention}, this action is destructive and irreversible. To unregister the starboard "
                f"for the channel {channel.mention}, react with {_CONF[0]} to confirm or {_CONF[1]} to cancel",
                color=discord.Color.blue(),
            ),
        )
        for reaction in _CONF:
            await message.add_reaction(reaction)
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", check=lambda r, u: r.message == message and u.id == ctx.author.id and str(r.emoji) in _CONF, timeout=300)
        except asyncio.TimeoutError:
            return await self.gcmds.timeout(ctx, "Starboard Unregister", 300)
        if str(reaction.emoji) == _CONF[0]:
            return await self.unregister_starboard(ctx, channel)
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Unregister Canceled",
                description=f"{ctx.author.mention}, the unregister was canceled",
                color=discord.Color.dark_red(),
            ),
        )


def setup(bot):
    bot.add_cog(Starboard(bot))
