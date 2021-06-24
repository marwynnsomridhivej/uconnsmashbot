import asyncio
from asyncio.exceptions import CancelledError
from datetime import datetime
from typing import Any, List, NamedTuple, Tuple, Union

import discord
from discord.errors import Forbidden
from discord.ext import commands

from utils import GlobalCMDS, customerrors
from utils.enums import LogLevel

__all__ = (
    "LogDispatcher",
    "GuildDispatcher",
    "MemberDispatcher",
)


YES = "✅"
NO = "❌"
NONE = "⬜"
_TOO_LONG = lambda e, n, v: len(e) + len(n) + len(v) > 6000 or len(e.fields) == 25


class GuildDiff(NamedTuple):
    type: str
    before: Any
    after: Any


class ChannelDiff(NamedTuple):
    type: str
    before: Any
    after: Any


class OverwriteDiff(NamedTuple):
    perm: str
    before: bool
    after: bool


class ChannelOverwriteDiff(NamedTuple):
    type: str
    target: Union[discord.Role, discord.Member]
    diffs: List[OverwriteDiff]


class EmojiAttrDiff(NamedTuple):
    attr: str
    emoji: discord.Emoji
    before: Any
    after: Any


class MemberDiff(NamedTuple):
    type: str
    before: Any
    after: Any


class MemberRoleDiff(NamedTuple):
    type: str
    role: discord.Role


class UserDiff(NamedTuple):
    type: str
    before: Any
    after: Any


class GuildRoleDiff(NamedTuple):
    attr: str
    before: Any
    after: Any


class RolePermissionDiff(NamedTuple):
    attr: str
    before: bool
    after: bool


def enabled(func):
    async def checker(*args, **kwargs):
        try:
            await func(*args, **kwargs)
        except Exception as e:
            if isinstance(e, customerrors.LoggingError) or isinstance(e, discord.DiscordException):
                pass
            else:
                raise e
    return checker


def _handle_task_result(task: asyncio.Task):
    try:
        task.result()
    except (Exception, CancelledError):
        pass


class LogDispatcher():
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.min_level = LogLevel.BASIC
        self.gcmds = GlobalCMDS(self.bot)

    async def check_logging_enabled(self, guild, min_level: LogLevel):
        if not guild:
            raise customerrors.LoggingNotEnabled()
        async with self.bot.db.acquire() as con:
            log_channel = await con.fetchval(f"SELECT log_channel FROM guild WHERE guild_id={guild.id}")
            log_level = await con.fetchval(f"SELECT log_level FROM guild WHERE guild_id={guild.id}")

        if not log_channel or log_channel == "DISABLED":
            raise customerrors.LoggingNotEnabled()
        elif log_level < min_level.value:
            raise customerrors.LoggingLevelInsufficient()
        else:
            return self.bot.get_channel(log_channel)

    async def dispatch_embed(self, channel: discord.TextChannel, embed: discord.Embed = None, embeds: List[discord.Embed] = None):
        try:
            webhooks = await channel.webhooks()
            async with self.bot.db.acquire() as con:
                webhook_id = await con.fetchval(f"SELECT webhook_id FROM logging WHERE guild_id={channel.guild.id}")
                webhook = discord.utils.get(webhooks, id=webhook_id)
                if not webhook:
                    webhook = await channel.create_webhook(
                        name="UconnSmashBot Logging",
                        avatar=await self.bot.user.avatar_url_as().read()
                    )
                    await con.execute(f"UPDATE logging SET webhook_id={webhook.id} WHERE guild_id={channel.guild.id}")
            current_timestamp = "{:%m/%d/%Y %H:%M:%S}".format(datetime.now())
            if embeds:
                for embed in embeds:
                    embed.set_footer(
                        text=current_timestamp,
                        icon_url=self.bot.user.avatar_url,
                    )
                embed = None
            if embed:
                embed.set_footer(
                    text=current_timestamp,
                    icon_url=self.bot.user.avatar_url,
                )
                embeds = None
            coro = webhook.send(
                embed=embed,
                embeds=embeds,
            )
        except (Forbidden, AttributeError) as e:
            coro = channel.send(
                embed=embed,
                embeds=embeds,
            )
        task = self.bot.loop.create_task(coro)
        task.add_done_callback(_handle_task_result)


class GuildDispatcher(LogDispatcher):
    def __init__(self, bot: commands.AutoShardedBot):
        super().__init__(bot)
        self.min_level = LogLevel.GUILD

    async def check_command_logging_enabled(self, guild: discord.Guild, min_level: LogLevel, name: str):
        log_channel = await super().check_logging_enabled(guild, min_level)
        async with self.bot.db.acquire() as con:
            command_enabled = await con.fetchval(f"SELECT {name} FROM logging WHERE guild_id={guild.id}")
        if command_enabled:
            return log_channel
        else:
            raise customerrors.LoggingNotEnabled()

    @enabled
    async def guild_command_completed(self, ctx, name: str):
        log_channel = await self.check_command_logging_enabled(ctx.guild, LogLevel.BASIC, name)
        embed = discord.Embed(
            color=discord.Color.blue(),
        ).add_field(
            name="Invoker",
            value=ctx.author.mention,
        ).add_field(
            name="Channel",
            value=ctx.channel.mention,
        ).add_field(
            name="Invoked With",
            value=f"```{ctx.message.content}```",
            inline=False,
        ).set_author(
            name=f"Command Used: {name}",
        ).set_thumbnail(
            url=ctx.author.avatar_url,
        )
        return await self.dispatch_embed(log_channel, embed=embed)

    @staticmethod
    def _parse_guild_update_diff(item: GuildDiff) -> dict:
        name, val = None, None
        template = "{} ⟶ {}"
        get_diff = lambda: [_ for _ in item.before if not _ in item.after] if len(item.before) > len(item.after) else [
            _ for _ in item.after if not _ in item.before]
        if item.type == "afk_channel":
            val = template.format(item.before.name if item.before else 'None',
                                  item.after.name if item.after else 'None')
        elif item.type == "bitrate_limit":
            val = template.format(f"{int(item.before / 1000)}kbps", f"{int(item.after / 1000)}kbps")
        elif item.type == "categories":
            diff = get_diff()
            name = f"Categories {'Added' if len(item.before) < len(item.after) else 'Deleted'}"
            val = ", ".join(cat.name for cat in diff)
        elif item.type == "channels":
            diff = get_diff()
            name = f"Channels {'Added' if len(item.before) < len(item.after) else 'Deleted'}"
            val = ", ".join(chnl.name for chnl in diff)
        elif item.type == "default_notifications":
            name = "Default Notification Level"
            convert = lambda o: str(o).replace('NotificationLevel.', '').replace('_', ' ').title()
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "emojis":
            diff = get_diff()
            name = f"Emojis {'Added' if len(item.before) < len(item.after) else 'Deleted'}"
            val = ", ".join(str(emj) for emj in diff)
        elif item.type == "explicit_content_filter":
            name = "Explicit Content Filter Level"
            convert = lambda o: str(o).replace("_", " ").title()
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "features":
            diff = get_diff()
            name = f"Special Properties {'Added' if len(item.before) < len(item.after) else 'Deleted'}"
            val = ", ".join(prop.title() for prop in diff)
        elif item.type == "filesize_limit":
            name = "Maximum Upload Size"
            convert = lambda o: f"{o / 1000000}MB"
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "mfa_level":
            name = "Moderator 2 Factor Authentication Required"
            convert = lambda o: 'True' if o else 'False'
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "premium_subscriber_role":
            name = "Nitro Booster Role"
            convert = lambda o: o.mention if isinstance(o, discord.Role) else None
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "premium_subscribers":
            diff = get_diff()
            name = "New Nitro Boosters" if len(item.before) < len(item.after) else "Stopped Nitro Boosting"
            val = ", ".join(member.mention for member in diff)
        elif item.type == "premium_subscription_count":
            name = "Nitro Booster Count"
        elif item.type == "premium_tier":
            name = "Nitro Boost Level"
            convert = lambda o: f"Level {o}"
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "public_updates_channel":
            convert = lambda o: o.mention if o else None
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "region":
            convert = lambda o: str(o).replace("-", " ").title()
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "roles":
            diff = get_diff()
            name = f"Roles {'Created' if len(item.after) > len(item.before) else 'Deleted'}"
            val = ", ".join(role.mention for role in diff)
        elif item.type == "rules_channel":
            convert = lambda o: o.mention if o else None
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "system_channel":
            convert = lambda o: o.mention if o else None
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "text_channels":
            diff = get_diff()
            name = f"Text Channels {'Created' if len(item.after) > len(item.before) else 'Deleted'}"
            val = ", ".join(chnl.mention for chnl in diff)
        elif item.type == "verification_level":
            convert = lambda o: str(o).title() if str(o) != "extreme" else "Highest"
            val = template.format(convert(item.before), convert(item.after))
        elif item.type == "voice_channels":
            diff = get_diff()
            name = f"Voice Channels {'Created' if len(item.after) > len(item.before) else 'Deleted'}"
            val = ", ".join(chnl.name for chnl in diff)
        else:
            pass

        return {
            "name": name or item.type.replace("_", " ").title(),
            "value": val or template.format(item.before, item.after),
        }

    @enabled
    async def guild_update(self, guild: discord.Guild, diff: List[GuildDiff]):
        if diff:
            log_channel = await self.check_logging_enabled(guild, self.min_level)
            embeds = []
            embed = discord.Embed(
                title="Server Updated",
                color=discord.Color.blue(),
            )
            for item in diff:
                if len(embeds) == 10:
                    await self.dispatch_embed(log_channel, embeds=embeds)
                    embeds = []
                data = self._parse_guild_update_diff(item)
                name = data["name"]
                value = data["value"]
                if _TOO_LONG(embed, name, value):
                    embeds.append(embed)
                    embed = discord.Embed(color=discord.Color.blue())
                embed.add_field(
                    name=name,
                    value=value,
                    inline=False,
                )
            embeds.append(embed)
            return await self.dispatch_embed(log_channel, embeds=embeds)

    @enabled
    async def guild_integrations_update(self, guild: discord.Guild):
        log_channel = await self.check_logging_enabled(guild, self.min_level)
        embed = discord.Embed(title="Server Integrations Updated",
                              description=f"The integrations for {guild.name} were updated",
                              color=discord.Color.blue())
        return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def guild_channel_attr_update(self, channel: discord.abc.GuildChannel, channel_type: str, main_diff: List[ChannelDiff], overwrite_diff: List[ChannelOverwriteDiff]):
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        title = f"{channel_type.title()} Channel \"{channel.name}\" Modified"
        embeds = []
        embed = discord.Embed(
            title=title if len(title) <= 256 else f"{channel_type.title()} Channel Modified",
            color=discord.Color.blue(),
        )
        for item in main_diff:
            if len(embeds) == 10:
                await self.dispatch_embed(log_channel, embeds=embeds)
                embeds = []
            name = item.type.replace("_", " ").title() if item.type != "NSFW Flag" else item.type
            if name == "Overwrites":
                if len(item.before) == len(item.after):
                    continue
                _diff = [
                    key for key in item.before if not key in item.after
                ] if len(item.before) > len(item.after) else [
                    key for key in item.after if not key in item.before
                ]
                op = "Removed" if len(item.before) > len(item.after) else "Added"
                name += f" {op}"
                value = f"{op} " + ", ".join(
                    key.mention for key in _diff
                )
            elif name == "Bitrate":
                value = f"{int(item.before / 1000)}kbps ⟶ {int(item.after / 1000)}kbps"
            elif isinstance(item.before, bool) and isinstance(item.after, bool):
                value = f"{YES if item.before else NO} ⟶ {YES if item.after else NO}"
            else:
                value = f"{item.before} ⟶ {item.after}"
            if _TOO_LONG(embed, name, value):
                embeds.append(embed)
                embed = discord.Embed(color=discord.Color.blue())
            embed.add_field(
                name=name,
                value=value,
                inline=False,
            )
        for item in overwrite_diff:
            if len(embeds) == 10:
                await self.dispatch_embed(log_channel, embeds=embeds)
                embeds = []
            name = f"Overwrites for {item.target.name if isinstance(item.target, discord.Role) else item.target}"
            value = "\n".join(
                f"**{diff.perm.replace('_', ' ').title()}**\n" +
                f"> {YES if diff.before else NONE if diff.before is None else NO} ⟶ {YES if diff.after else NONE if diff.after is None else NO}"
                for diff in item.diffs
            )
            if _TOO_LONG(embed, name, value):
                embeds.append(embed)
                embed = discord.Embed(color=discord.Color.blue())
            embed.add_field(
                name=name,
                value=value,
                inline=False,
            )
        embeds.append(embed)
        return await self.dispatch_embed(log_channel, embeds=embeds)

    @enabled
    async def guild_channels_update(self, channel: discord.abc.GuildChannel, event_type: str):
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        embed = discord.Embed(
            title=f"Channel {event_type.title()}",
            color=discord.Color.blue() if event_type == "created" else discord.Color.dark_red(),
        )
        channel_type = "Text" if isinstance(
            channel, discord.TextChannel
        ) else "Voice" if isinstance(
            channel, discord.VoiceChannel
        ) else "Category"
        if event_type == "created":
            embed.add_field(
                name="Type",
                value=channel_type,
                inline=False,
            ).add_field(
                name="Name",
                value=channel.name,
                inline=False,
            ).add_field(
                name="Created At",
                value=channel.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                inline=False,
            ).add_field(
                name="Position",
                value=channel.position,
                inline=False,
            ).add_field(
                name="Category",
                value=channel.category.name if channel.category else 'None',
                inline=False,
            )
        else:
            embed.description = f"{channel_type} Channel `{channel.name}` was deleted"
        return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def channel_pins_update(self, channel: discord.abc.GuildChannel):
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        pins = await channel.pins()
        last_pin = f"[Click Here]({pins[0].jump_url})" if pins else "`no pins`"
        embed = discord.Embed(title=f"Channel Pins Updated",
                              description=f"The pins for {channel.mention} were updated\n\n**Most Recent Pin:** {last_pin}",
                              color=discord.Color.blue())
        return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def channel_webhooks_update(self, channel: discord.abc.GuildChannel):
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        embed = discord.Embed(
            title=f"Channel Webhooks Updated",
            description=f"The webhooks in {channel.mention} were updated",
            color=discord.Color.blue()
        )
        return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def guild_role_update(self, role: discord.Role, event_type: str):
        log_channel = await self.check_logging_enabled(role.guild, self.min_level)
        embed = discord.Embed(
            title=f"Role {event_type.title()}",
            color=role.color if event_type == "created" else discord.Color.dark_red(),
        )
        if event_type == "created":
            embed.add_field(
                name="Name",
                value=role.name,
                inline=False,
            ).add_field(
                name="Created At",
                value=role.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                inline=False,
            ).add_field(
                name="Managed",
                value=role.managed,
                inline=False,
            ).add_field(
                name="Mentionable",
                value=role.mentionable,
                inline=False,
            ).add_field(
                name="ID",
                value=role.id,
                inline=False,
            )
        else:
            embed.description = f"The role `{role.name}` was deleted"
        return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def guild_role_attr_update(self, role: discord.Role, main_diff: List[GuildRoleDiff], perm_diff: List[RolePermissionDiff]):
        log_channel = await self.check_logging_enabled(role.guild, self.min_level)
        embeds = []
        embed = discord.Embed(
            title="Role Updated",
            description=f"Role: {role.mention}",
            color=role.color,
        )
        if main_diff:
            for item in main_diff:
                if not isinstance(item.after, bool):
                    value = f"{item.before} ⟶ {item.after}"
                else:
                    value = f"{YES if item.before else NO} ⟶ {YES if item.after else NO}"
                embed.add_field(
                    name=item.attr.replace("_", " ").title(),
                    value=value,
                    inline=False,
                )
        if perm_diff:
            for item in perm_diff:
                name = item.attr.replace("_", " ").title()
                value = f"{YES if item.before else NO} ⟶ {YES if item.after else NO}"
                if _TOO_LONG(embed, name, value):
                    embeds.append(embed)
                    embed = discord.Embed(color=role.color)
                embed.add_field(
                    name=name,
                    value=value,
                    inline=False,
                )
        embeds.append(embed)
        return await self.dispatch_embed(log_channel, embeds=embeds)

    @enabled
    async def guild_emoji_update(self, guild, event_type: str, diff: List[discord.Emoji]):
        log_channel = await self.check_logging_enabled(guild, self.min_level)
        embeds = []
        embed = discord.Embed(title=f"Emojis {event_type.title()}", color=discord.Color.blue()
                              if event_type != "removed" else discord.Color.dark_red())
        if event_type == "added":
            for emoji in diff:
                embed.add_field(
                    name=f"{emoji.name} - {str(emoji)}",
                    value="\n".join([
                        f"> **Created At:** {emoji.created_at.strftime('%d/%m/%Y %H:%M:%S')}",
                        f"> **Available:** {YES if emoji.available else NO}",
                        f"> **Animated:** {YES if emoji.animated else NO}",
                        f"> **Managed:** {YES if emoji.managed else NO}",
                        f"> **ID:** {emoji.id}",
                    ]),
                    inline=False,
                )
        elif event_type == "removed":
            embed.description = "\n".join(emoji.name for emoji in diff)
        else:
            for item in diff:
                if len(embeds) == 10:
                    await self.dispatch_embed(log_channel, embeds=embeds)
                    embeds = []
                name = f"Name Changed: {str(item.emoji)}"
                value = f"{item.before} ⟶ {item.after}"
                if _TOO_LONG(embed, name, value):
                    embeds.append(embed)
                    embed = discord.Embed(color=discord.Color.blue())
                embed.add_field(
                    name=name,
                    value=value,
                    inline=False,
                )
        embeds.append(embed)
        return await self.dispatch_embed(log_channel, embeds=embeds)

    @enabled
    async def guild_invite_update(self, invite: discord.Invite, event_type: str):
        if invite.guild:
            log_channel = await self.check_logging_enabled(invite.guild, self.min_level)
            embed = discord.Embed(
                title=f"Instant Invite {event_type.title()}",
                color=discord.Color.blue() if event_type == "created" else discord.Color.dark_red(),
            )
            if event_type == "created":
                embed.add_field(
                    name="Created By",
                    value=invite.inviter.mention if invite.inviter else "N/A",
                    inline=False,
                ).add_field(
                    name="Channel",
                    value=invite.channel.mention,
                    inline=False,
                ).add_field(
                    name="URL",
                    value=invite.url,
                    inline=False,
                ).add_field(
                    name="Maximum Uses",
                    value=f"{invite.max_uses if invite.max_uses else 'Unlimited'}",
                    inline=False,
                ).add_field(
                    name="Permanent",
                    value=YES if not invite.temporary else NO,
                    inline=False,
                ).add_field(
                    name="Invite Code",
                    value=f"{invite.code}",
                    inline=False,
                ).add_field(
                    name="Expiration",
                    value="{:%m/%d/%Y %H:%M:%S}".format(
                        datetime.fromtimestamp(
                            int(datetime.now().timestamp()) + invite.max_age
                        )
                    ),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Channel",
                    value=invite.channel.mention,
                    inline=False,
                ).add_field(
                    name="Invite Code",
                    value=f"{invite.code}",
                    inline=False,
                ).add_field(
                    name="URL",
                    value=invite.url,
                    inline=False,
                )
            return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def message_raw_edit(self, message_id: int, channel_id: int, data: dict):
        channel = await self.bot.fetch_channel(channel_id)
        if hasattr(channel, "guild"):
            try:
                message: discord.Message = await channel.fetch_message(message_id)
                if message.author.bot:
                    raise TypeError
            except Exception:
                return
            log_channel = await self.check_logging_enabled(message.guild, self.min_level)
            embed = discord.Embed(
                title=f"Message Edited: {message.author.display_name}",
                color=message.author.color,
            ).add_field(
                name="Editor",
                value=message.author.mention,
                inline=False,
            ).add_field(
                name="Edited Content",
                value=message.content if len(message.content) < 1024 else "Message is too long to display",
                inline=False,
            )
            embed.add_field(
                name="Channel",
                value=channel.mention,
                inline=False,
            ).add_field(
                name="Jump To Message",
                value=f"[Click Here]({message.jump_url})",
                inline=False,
            )
            return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def message_raw_delete(self, message_id: int, channel_id: int, cached_message: discord.Message):
        channel = await self.bot.fetch_channel(channel_id)
        if hasattr(channel, "guild"):
            log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
            embed = discord.Embed(
                title="Message Deleted",
                color=discord.Color.dark_red()
            ).add_field(
                name="Message ID",
                value=message_id,
                inline=False,
            ).add_field(
                name="Channel",
                value=channel.mention,
                inline=False,
            )
            if cached_message:
                embed.add_field(
                    name="Message Author",
                    value=cached_message.author.mention,
                    inline=False
                ).add_field(
                    name="Message Content",
                    value=f"```{cached_message.content}```"
                )
            return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def message_raw_bulk_delete(self, message_ids: set, channel_id: int):
        channel = await self.bot.fetch_channel(channel_id)
        if hasattr(channel, "guild"):
            log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
            embed = discord.Embed(
                title="Bulk Message Delete",
                color=discord.Color.blue(),
            ).add_field(
                name="Amount Deleted",
                value=len(message_ids),
                inline=False,
            ).add_field(
                name="Channel",
                value=channel.mention,
                inline=False,
            )
            return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def reaction_raw_update(self, message_id: int, emoji: discord.PartialEmoji, user_id: int, channel_id: int, event_type: str):
        channel = await self.bot.fetch_channel(channel_id)
        if hasattr(channel, "guild"):
            log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
            message = await channel.fetch_message(message_id)
            user = await self.bot.fetch_user(user_id)
            if not user.bot:
                embed = discord.Embed(
                    title=event_type.title(),
                    color=discord.Color.blue() if event_type == "reaction added" else discord.Color.dark_red(),
                ).add_field(
                    name="Emoji",
                    value=emoji,
                    inline=False,
                ).add_field(
                    name="Message",
                    value=f"[Click Here]({message.jump_url})",
                    inline=False,
                ).add_field(
                    name="Channel",
                    value=channel.mention,
                    inline=False,
                ).add_field(
                    name="User",
                    value=user.mention,
                    inline=False,
                ).set_thumbnail(
                    url=user.avatar_url,
                )
                return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def reaction_raw_clear(self, message_id: int, channel_id: int):
        channel = await self.bot.fetch_channel(channel_id)
        if hasattr(channel, "guild"):
            log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
            message = await channel.fetch_message(message_id)
            embed = discord.Embed(
                title="Reactions Cleared",
                color=discord.Color.dark_red()
            ).add_field(
                name="Channel",
                value=channel.mention,
            ).add_field(
                name="Message",
                value=f"[Click Here]({message.jump_url})",
            )
            return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def reaction_raw_clear_emoji(self, message_id: int, channel_id: int, emoji: discord.PartialEmoji):
        channel = await self.bot.fetch_channel(channel_id)
        if hasattr(channel, "guild"):
            log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
            message = await channel.fetch_message(message_id)
            embed = discord.Embed(
                title="Reaction Emoji Cleared",
                description=f"[This message]({message.jump_url}) had all of its reactions with the emoji {emoji} removed",
                color=discord.Color.dark_red()
            ).add_field(
                name="Emoji",
                value=emoji,
            ).add_field(
                name="Channel",
                value=channel.mention,
            ).add_field(
                name="Message",
                value=f"[Click Here]({message.jump_url})",
            )
            return await self.dispatch_embed(log_channel, embed=embed)


class MemberDispatcher(LogDispatcher):
    def __init__(self, bot: commands.AutoShardedBot):
        super().__init__(bot)
        self.min_level = LogLevel.GUILD
        self._statuses = {
            "online": "🟢 Online",
            "offline": "⚪ Offline",
            "idle": "🟡 Idle",
            "dnd": "🔴 Do Not Disturb",
            "do_not_disturb": "🔴 Do Not Disturb",
            "invisible": "⚪ Offline",
        }

    async def check_logging_enabled(self, member: discord.Member, min_level: LogLevel, guild: discord.Guild = None):
        if not member.bot:
            return await super().check_logging_enabled(member.guild if hasattr(member, "guild") else guild, min_level)
        else:
            raise customerrors.LoggingNotEnabled()

    def update_parser(self, member: discord.Member, item: MemberDiff) -> Tuple[str, str]:
        if item.type == "activities":
            before = set(before.name for before in item.before)
            after = set(after.name for after in item.after)
            if before ^ after:
                return item.type.replace('_', ' ').title(), f"{item.before[0].name if item.before else 'None'} ⟶ {item.after[0].name if item.after else 'None'}"
            else:
                return "Status", self._statuses[member.raw_status]
        elif item.type == "premium_since":
            return item.type.replace('_', ' ').title(), "Nitro Boosted this server"
        elif "role" in item.type:
            return f"{'Acquired Role' if 'add' in item.type else 'Lost Role'}", item.role.mention
        else:
            return item.type.replace('_', ' ').title(), f"{item.before} ⟶ {item.after}"

    @staticmethod
    def voice_update_parser(item: MemberDiff) -> Tuple[str, str]:
        _YN = [YES, NO]
        items = {
            "deaf": ("Server Deafened", _YN),
            "mute": ("Server Muted", _YN),
            "self_mute": ("Self Muted", _YN),
            "self_deaf": ("Self Deafened", _YN),
            "self_stream": ("Streaming", _YN),
            "self_video": ("Video", _YN),
            "afk": ("AFK", _YN),
            "channel": ("Connected To", [None, 'None']),
        }
        if item.type in items:
            ret = items.get(item.type)
            return ret[0], ret[1][0 if item.after else 1] if not item.type == "channel" else item.after.name if item.after else 'None'

    @enabled
    async def member_membership_update(self, member: discord.Member, event_type: str):
        log_channel = await self.check_logging_enabled(member, self.min_level)
        embed = discord.Embed(
            title=f"Member {event_type.title()}",
            description=f"{member.mention} has {event_type} {member.guild.name}",
            color=discord.Color.blue() if event_type == "joined" else discord.Color.dark_red()
        ).set_thumbnail(
            url=member.avatar_url,
        )
        return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def member_update(self, member: discord.Member, diff: List[MemberDiff]):
        if not member.bot:
            log_channel = await self.check_logging_enabled(member, self.min_level)
            nv = []
            for item in diff:
                res = self.update_parser(member, item)
                if res and item.type == "activities":
                    try:
                        await self.check_logging_enabled(member, LogLevel.HIDEF)
                        nv.append(res)
                    except customerrors.LoggingNotEnabled:
                        pass
                else:
                    nv.append(res)
            if nv:
                embeds = []
                embed = discord.Embed(
                    title=f"Member Updated: {member.display_name}",
                    color=member.color
                ).set_thumbnail(
                    url=member.avatar_url,
                )
                for name, value in nv:
                    if _TOO_LONG(embed, name, value):
                        embeds.append(embed)
                        embed = discord.Embed(color=member.color).set_thumbnail(url=member.avatar_url)
                    embed.add_field(
                        name=name,
                        value=value,
                        inline=False,
                    )
                embeds.append(embed)
                return await self.dispatch_embed(log_channel, embeds=embeds)

    @enabled
    async def member_ban_update(self, guild: discord.Guild, member: Union[discord.User, discord.Member], event_type: str):
        if not member.bot:
            log_channel = await self.check_logging_enabled(member, self.min_level, guild=guild)
            embed = discord.Embed(
                title=f"User {event_type.title()}",
                color=discord.Color.blue() if event_type == "unbanned" else discord.Color.dark_red()
            ).add_field(
                name="User",
                value=member.mention,
            ).set_thumbnail(
                url=member.avatar_url,
            )
            return await self.dispatch_embed(log_channel, embed=embed)

    @enabled
    async def member_voice_state_update(self, member: discord.Member, diff: list):
        if not member.bot:
            log_channel = await self.check_logging_enabled(member, self.min_level)
            nvs = [self.voice_update_parser(item) for item in diff]
            if nvs:
                embeds = []
                embed = discord.Embed(
                    title=f"Voice Status: {member.display_name}",
                    color=member.color,
                ).set_thumbnail(
                    url=member.avatar_url,
                )
                for name, value in nvs:
                    if _TOO_LONG(embed, name, value):
                        embeds.append(embed)
                        embed = discord.Embed(color=member.color).set_thumbnail(url=member.avatar_url)
                    embed.add_field(
                        name=name,
                        value=f"{value}",
                        inline=False,
                    )
                embeds.append(embed)
                return await self.dispatch_embed(log_channel, embeds=embeds)
