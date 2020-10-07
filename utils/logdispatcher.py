import json
from collections import namedtuple, ChainMap
from datetime import datetime
from typing import Optional, Union

import discord
from discord.ext import commands

from utils import customerrors, globalcommands, premium
from utils.enums import ChannelEmoji as CE
from utils.enums import LogLevel


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


class LogDispatcher():
    def __init__(self, bot: commands.AutoShardedBot):
        super().__init__()
        self.bot = bot
        self.min_level = LogLevel.BASIC
        self.gcmds = globalcommands.GlobalCMDS(self.bot)

    async def check_logging_enabled(self, guild, min_level: LogLevel):
        async with self.bot.db.acquire() as con:
            log_channel = await con.fetchval(f"SELECT log_channel FROM guild WHERE guild_id={guild.id}")
            log_level = await con.fetchval(f"SELECT log_level FROM guild WHERE guild_id={guild.id}")

        if not log_channel or log_channel == "DISABLED":
            raise customerrors.LoggingNotEnabled()
        elif log_level < min_level.value:
            raise customerrors.LoggingLevelInsufficient()
        else:
            return self.bot.get_channel(log_channel)

    async def dispatch_embed(self, channel: discord.TextChannel, embed: discord.Embed):
        embed.set_footer(text="{:%m/%d/%Y %H:%M:%S}".format(datetime.now()), icon_url=self.bot.user.avatar_url)
        return await channel.send(embed=embed)


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
        description = (f"Executed by: {ctx.author.mention}",
                       f"Channel: {ctx.channel.mention}",
                       f"Invoked with: `{ctx.message.content}`")
        embed = discord.Embed(title=f"Command Used: {name}",
                              description="> " + "\n> ".join(description),
                              color=discord.Color.blue())
        embed.set_thumbnail(url=ctx.author.avatar_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def guild_update(self, guild: discord.Guild, diff: list):
        if not diff:
            return
        log_channel = await self.check_logging_enabled(guild, self.min_level)
        embed = discord.Embed(title="Server Updated", color=discord.Color.blue())
        description = ["{}\n> Server {} changed from `{}` ⟶ `{}`\n"
                       .format(
                           item.type.replace('_', ' ').title(),
                           item.type.replace('_', ' '),
                           item.before,
                           item.after
                       )
                       for item in diff if diff]
        embed.description = "\n".join(description)
        embed.set_thumbnail(url=guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def guild_integrations_update(self, guild: discord.Guild):
        log_channel = await self.check_logging_enabled(guild, self.min_level)
        embed = discord.Embed(title="Server Integrations Updated",
                              description=f"The integrations for {guild.name} were updated",
                              color=discord.Color.blue())
        embed.set_thumbnail(url=guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    def get_channel_string(self, channel: discord.abc.GuildChannel, event_type: str = "none"):
        return (f"Channel {CE[str(channel.type)]}"
                f"{channel.mention if event_type != 'deleted' and str(channel.type) == 'text' else f'`{channel.name}`'}")

    @enabled
    async def guild_channel_attr_update(self, channel: discord.abc.GuildChannel, diff: list):
        if not diff:
            return
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        embed = discord.Embed(title="Channel Updated", color=discord.Color.blue())
        description = ["{}\n> Channel {} changed from `{}` ⟶ `{}`\n"
                       .format(
                           item.type.replace('_', ' ').title(),
                           item.type.replace('_', ' '),
                           item.before,
                           item.after
                       )
                       for item in diff if diff]
        embed.description = f"{self.get_channel_string(channel)}\n\n" + "\n".join(description)
        embed.set_thumbnail(url=channel.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def guild_channels_update(self, channel: discord.abc.GuildChannel, event_type: str):
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        embed = discord.Embed(title=f"Channel {event_type.title()}",
                              description=f"{self.get_channel_string(channel, event_type)} was {event_type.lower()}",
                              color=discord.Color.blue() if event_type == "created" else discord.Color.dark_red())
        embed.set_thumbnail(url=channel.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def channel_pins_update(self, channel: discord.abc.GuildChannel):
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        pins = await channel.pins()
        last_pin = f"[Click Here]({pins[0].jump_url})" if pins else "`no pins`"
        embed = discord.Embed(title=f"Channel Pins Updated",
                              description=f"The pins for {channel.mention} were updated\n\n**Most Recent Pin:** {last_pin}",
                              color=discord.Color.blue())
        embed.set_thumbnail(url=channel.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def channel_webhooks_update(self, channel: discord.abc.GuildChannel):
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        embed = discord.Embed(title=f"Channel Webhooks Updated",
                              description=f"The webhooks in {channel.mention} were updated",
                              color=discord.Color.blue())
        embed.set_thumbnail(url=channel.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def guild_role_update(self, role: discord.Role, event_type: str):
        log_channel = await self.check_logging_enabled(role.guild, self.min_level)
        embed = discord.Embed(title=f"Role {event_type.title()}",
                              description=f"Created role {role.mention}" if event_type == "created" else f"Role Name: `{role.name}`",
                              color=role.color if event_type == "created" else discord.Color.dark_red())
        embed.set_thumbnail(url=role.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def guild_role_attr_update(self, role: discord.Role, diff: list):
        if not diff:
            return
        log_channel = await self.check_logging_enabled(role.guild, self.min_level)
        embed = discord.Embed(title="Role Updated", color=role.color)
        description = ["{}\n> Role {} changed from `{}` ⟶ `{}`\n"
                       .format(
                           item.type.replace('_', ' ').title(),
                           item.type.replace('_', ' '),
                           item.before,
                           item.after
                       )
                       for item in diff if diff]
        embed.description = f"{role.mention}\n\n" + "\n".join(description)
        embed.set_thumbnail(url=role.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def guild_emoji_update(self, guild, event_type: str, diff: list):
        log_channel = await self.check_logging_enabled(guild, self.min_level)
        embed = discord.Embed(title=f"Emojis {event_type.title()}", color=discord.Color.blue()
                              if event_type == "added" else discord.Color.dark_red())
        embed.description = "\n".join([f"> {str(emoji)} `<:{emoji.name}:{emoji.id}>`" for emoji in diff])
        embed.set_thumbnail(url=guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def guild_invite_update(self, invite: discord.Invite, event_type: str):
        if not invite.guild:
            return
        log_channel = await self.check_logging_enabled(invite.guild, self.min_level)
        if event_type == "created":
            description = "\n> ".join((f"**Details:**",
                                       f"Created by: {invite.inviter.mention}",
                                       "Expiration: {}".format(
                                           datetime.fromtimestamp(int(datetime.now().timestamp()) + invite.max_age)
                                           if invite.max_age != 0 else '`never`'
                                       ),
                                       "Max Uses: {}".format(invite.max_uses if invite.max_uses !=
                                                             0 else '`unlimited`'),
                                       f"Channel: {invite.channel.mention}",
                                       f"URL: {invite.url}"))
        else:
            description = f"The invite {invite.url} was revoked and can no longer be used"
        embed = discord.Embed(title=f"Instant Invite {event_type.title()}",
                              description=description,
                              color=discord.Color.blue() if event_type == "created" else discord.Color.dark_red(),
                              url=invite.url if event_type == "created" else None)
        embed.set_thumbnail(url=invite.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def message_raw_edit(self, message_id: int, channel_id: int, data: dict):
        channel = await self.bot.fetch_channel(channel_id)
        if not hasattr(channel, "guild"):
            return
        try:
            message = await channel.fetch_message(message_id)
        except Exception:
            return
        if message.author.bot:
            return
        log_channel = await self.check_logging_enabled(message.guild, self.min_level)
        description = (f"**Edited Content:**\n> {message.content if len(message.content) < 1000 else f'[Click Here]({message.jump_url})'}",
                       "\n> ".join(("**Message Details:**",
                                    f"Channel: {channel.mention}",
                                    f"Jump URL: [Click Here]({message.jump_url})")))
        embed = discord.Embed(title=f"{message.author} Edited a Message",
                              description="\n\n".join(description),
                              color=message.author.color)
        embed.set_thumbnail(url=message.author.avatar_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def message_raw_delete(self, message_id: int, channel_id: int):
        channel = await self.bot.fetch_channel(channel_id)
        if not hasattr(channel, "guild"):
            return
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        embed = discord.Embed(title="Message Deleted",
                              description=f"A message was deleted in {channel.mention}",
                              color=discord.Color.dark_red())
        embed.set_thumbnail(url=channel.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def message_raw_bulk_delete(self, message_ids: set, channel_id: int):
        channel = await self.bot.fetch_channel(channel_id)
        if not hasattr(channel, "guild"):
            return
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        embed = discord.Embed(title="Bulk Message Delete",
                              description=f"{len(message_ids)} {'messages were' if len(message_ids) != 0 else 'message was'} deleted in {channel.mention}",
                              color=discord.Color.dark_red())
        embed.set_thumbnail(url=channel.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def reaction_raw_update(self, message_id: int, emoji: discord.PartialEmoji, user_id: int, channel_id: int, event_type: str):
        channel = await self.bot.fetch_channel(channel_id)
        if not hasattr(channel, "guild"):
            return
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        message = await channel.fetch_message(message_id)
        user = await self.bot.fetch_user(user_id)
        description = (f"Emoji: {emoji}",
                       f"Message: [Click Here]({message.jump_url})",
                       f"Channel: {channel.mention}",
                       f"User: {user.mention}")
        embed = discord.Embed(title=event_type.title(),
                              description="> " + "\n> ".join(description),
                              color=discord.Color.blue() if event_type == "reaction added" else discord.Color.dark_red())
        embed.set_thumbnail(url=user.avatar_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def reaction_raw_clear(self, message_id: int, channel_id: int):
        channel = await self.bot.fetch_channel(channel_id)
        if not hasattr(channel, "guild"):
            return
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        message = await channel.fetch_message(message_id)
        embed = discord.Embed(title="Reactions Cleared",
                              description=f"[This message]({message.jump_url}) had all of its reactions removed",
                              color=discord.Color.dark_red())
        embed.set_thumbnail(url=channel.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def reaction_raw_clear_emoji(self, message_id: int, channel_id: int, emoji: discord.PartialEmoji):
        channel = await self.bot.fetch_channel(channel_id)
        if not hasattr(channel, "guild"):
            return
        log_channel = await self.check_logging_enabled(channel.guild, self.min_level)
        message = await channel.fetch_message(message_id)
        embed = discord.Embed(title="Reaction Emoji Cleared",
                              description=f"[This message]({message.jump_url}) had all of its reactions with the emoji {emoji} removed",
                              color=discord.Color.dark_red())
        embed.set_thumbnail(url=channel.guild.icon_url)
        return await self.dispatch_embed(log_channel, embed)


class MemberDispatcher(LogDispatcher):
    def __init__(self, bot: commands.AutoShardedBot):
        super().__init__(bot)
        self.min_level = LogLevel.GUILD

    async def check_logging_enabled(self, member: discord.Member, min_level: LogLevel, guild: discord.Guild = None):
        if not member.bot:
            return await super().check_logging_enabled(member.guild if hasattr(member, "guild") else guild, min_level)
        else:
            raise customerrors.LoggingNotEnabled()

    def update_parser(self, member, item: namedtuple) -> str:
        if item.type == "activities":
            before = set(before.name for before in item.before)
            after = set(after.name for after in item.after)
            if before ^ after:
                return f"{item.type.replace('_', ' ').title()}\n> Changed to ```{item.after[0].name}```"
            else:
                pass
        elif item.type == "premium_since":
            return f"{item.type.replace('_', ' ').title()}\n> Nitro Boosted this server"
        elif "role" in item.type:
            return f"{'Acquired Role' if 'add' in item.type else 'Lost Role'}: {item.role.mention}"
        elif "status" in item.type or item.type == "voice":
            pass
        else:
            return f"{item.type.replace('_', ' ').title()}\n> Changed from `{item.before}` ⟶ `{item.after}`"

    def voice_update_parser(self, member: discord.Member, item: namedtuple) -> str:
        if item.type == "deaf":
            return "Server Deafened: `True`" if item.after else "Server Deafened: `False`"
        elif item.type == "mute":
            return "Server Muted: `True`" if item.after else "Server Muted: `False`"
        elif item.type == "self_mute":
            return "Self Muted: `True`" if item.after else "Self Muted: `False`"
        elif item.type == "self_deaf":
            return "Self Deafened: `True`" if item.after else "Self Deafened: `False`"
        elif item.type == "self_stream":
            return "Stream Status: `Streaming Live`" if item.after else "Stream Status: `Offline`"
        elif item.type == "self_video":
            return "Video Status: `Video On`" if item.after else "Video Status: `No Video`"
        elif item.type == "afk":
            return "In AFK Channel: `True`" if item.after else "In AFK Channel: `False`"
        elif item.type == "channel":
            return f"Connected To: `{item.after.name}`" if item.after else "Connected To: `None`"
        else:
            pass

    @enabled
    async def member_membership_update(self, member: discord.Member, event_type: str):
        log_channel = await self.check_logging_enabled(member, self.min_level)
        embed = discord.Embed(title=f"Member {event_type.title()}",
                              description=f"{member.mention} has {event_type} {member.guild.name}",
                              color=discord.Color.blue() if event_type == "joined" else discord.Color.dark_red())
        embed.set_thumbnail(url=member.avatar_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def member_update(self, member: discord.Member, diff: list):
        if member.bot:
            return
        log_channel = await self.check_logging_enabled(member, LogLevel.HIDEF)
        description = [self.update_parser(member, item) for item in diff if self.update_parser(member, item)]
        if not description:
            return
        embed = discord.Embed(title="Member Updated",
                              description=f"{member.mention} changed:\n\n" + "\n".join(description),
                              color=member.color)
        embed.set_thumbnail(url=member.avatar_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def member_ban_update(self, guild: discord.Guild, member: Union[discord.User, discord.Member], event_type: str):
        if member.bot:
            return
        log_channel = await self.check_logging_enabled(member, self.min_level, guild=guild)
        embed = discord.Embed(title=f"User {event_type.title()}",
                              description=f"The user {member.mention} was {event_type} from {guild.name}",
                              color=discord.Color.blue() if event_type == "unbanned" else discord.Color.dark_red())
        embed.set_thumbnail(url=member.avatar_url)
        return await self.dispatch_embed(log_channel, embed)

    @enabled
    async def member_voice_state_update(self, member: discord.Member, diff: list):
        if member.bot:
            return
        log_channel = await self.check_logging_enabled(member, self.min_level)
        description = [self.voice_update_parser(member, item) for item in diff]
        if not description:
            return
        embed = discord.Embed(title="Member Voice State Update",
                              description=f"{member.mention} updated their voice status:\n\n> " +
                              "\n> ".join(description),
                              color=discord.Color.blue())
        embed.set_thumbnail(url=member.avatar_url)
        return await self.dispatch_embed(log_channel, embed)
