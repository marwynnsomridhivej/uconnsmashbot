import asyncio
from collections.abc import Hashable
from datetime import datetime
from typing import Optional, Sequence, Union

import discord
from discord.ext import commands
from utils import GlobalCMDS, SubcommandHelp, customerrors, logdispatcher
from utils.enums import ConfirmReactions, LogLevel
from utils.logdispatcher import (ChannelDiff, ChannelOverwriteDiff,
                                 EmojiAttrDiff, GuildDiff, GuildRoleDiff,
                                 MemberDiff, MemberRoleDiff, OverwriteDiff,
                                 RolePermissionDiff)

_check = lambda __a, __o: not __a.startswith("_") and isinstance(
    getattr(__o, __a), Hashable) and not callable(getattr(__o, __a))
_PERM_ATTRS = frozenset(
    attr for attr in vars(discord.Permissions) if _check(attr, discord.Permissions)
)
_ROLE_ATTRS = frozenset([
    "color",
    "hoist",
    "mentionable",
    "name",
    "position",
])
_TEXTCHANNEL_ATTRS = frozenset([
    "name",
    "category",
    "overwrites",
    "permissions_synced",
    "position",
    "slowmode_delay",
    "topic",
])
_VOICECHANNEL_ATTRS = frozenset([
    "name",
    "category",
    "bitrate",
    "user_limit",
    "overwrites",
    "permissions_synced",
    "position",
])
_CATEGORYCHANNEL_ATTRS = frozenset([
    "name",
    "text_channels",
    "voice_channels",
    "overwrites",
    "position",
])
_GUILD_ATTRS = frozenset([
    attr for attr in discord.Guild.__slots__ if _check(attr, discord.Guild) and not attr in [
        "members",
        "self_role",
        "shard_id",
        "system_channel_flags",
        "unavailable",
        "voice_client",
    ]
])
_diff = lambda _a, _p, _c: getattr(_p, _a) != getattr(_c, _a)


class Logging(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_logging())
        self.guild_dispatch = logdispatcher.GuildDispatcher(self.bot)
        self.member_dispatch = logdispatcher.MemberDispatcher(self.bot)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        name = ctx.command.root_parent.name.lower() if ctx.command.root_parent else ctx.command.name.lower()
        await self.guild_dispatch.guild_command_completed(ctx, name)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        diff = [
            GuildDiff(
                type=attr,
                before=getattr(before, attr),
                after=getattr(after, attr),
            ) for attr in _GUILD_ATTRS if _diff(attr, before, after)
        ]
        await self.guild_dispatch.guild_update(after, diff)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        await self.guild_dispatch.guild_channels_update(channel, "created")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        await self.guild_dispatch.guild_channels_update(channel, "deleted")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        if isinstance(after, discord.TextChannel):
            main_diff = [
                ChannelDiff(attr, getattr(before, attr), getattr(after, attr)) for attr in _TEXTCHANNEL_ATTRS if _diff(attr, before, after)
            ]
            before_nsfw = before.is_nsfw()
            after_nsfw = after.is_nsfw()
            if before_nsfw != after_nsfw:
                main_diff.append(
                    ChannelDiff(
                        type="NSFW Flag",
                        before=before_nsfw,
                        after=after_nsfw,
                    )
                )
            channel_type = "text"
        elif isinstance(after, discord.VoiceChannel):
            main_diff = [
                ChannelDiff(attr, getattr(before, attr), getattr(after, attr)) for attr in _VOICECHANNEL_ATTRS if _diff(attr, before, after)
            ]
            channel_type = "voice"
        elif isinstance(after, discord.CategoryChannel):
            main_diff = [
                ChannelDiff(attr, getattr(before, attr), getattr(after, attr)) for attr in _CATEGORYCHANNEL_ATTRS if _diff(attr, before, after)
            ]
            channel_type = "cateogry"
        else:
            return

        overwrite_diff = []
        for _before, _after in zip(before.overwrites.items(), after.overwrites.items()):
            _, before_overwrite = _before
            target, after_overwrite = _after
            diff = []
            for before_state, after_state in zip(before_overwrite, after_overwrite):
                _, before_value = before_state
                perm, after_value = after_state
                if before_value != after_value:
                    diff.append(
                        OverwriteDiff(
                            perm=perm,
                            before=before_value,
                            after=after_value,
                        )
                    )
            if diff:
                overwrite_diff.append(
                    ChannelOverwriteDiff(
                        type="role" if isinstance(target, discord.Role) else "member",
                        target=target,
                        diffs=diff,
                    )
                )
        if main_diff or overwrite_diff:
            await self.guild_dispatch.guild_channel_attr_update(after, channel_type, main_diff, overwrite_diff)

    @commands.Cog.listener()
    async def on_guild_channel_pins_update(self, channel: discord.abc.GuildChannel, last_pin: Optional[datetime]):
        await self.guild_dispatch.channel_pins_update(channel)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        await self.guild_dispatch.guild_role_update(role, "created")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await self.guild_dispatch.guild_role_update(role, "deleted")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        main_diff = [
            GuildRoleDiff(attr, getattr(before, attr), getattr(after, attr)) for attr in _ROLE_ATTRS if _diff(attr, before, after)
        ]
        perm_diff = [
            RolePermissionDiff(attr, getattr(before.permissions, attr), getattr(after.permissions, attr)) for attr in _PERM_ATTRS if _diff(attr, before.permissions, after.permissions)
        ]
        main_diff.sort(key=lambda i: i.attr)
        perm_diff.sort(key=lambda i: i.attr)
        if main_diff or perm_diff:
            await self.guild_dispatch.guild_role_attr_update(after, main_diff, perm_diff)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: Sequence[discord.Emoji], after: Sequence[discord.Emoji]):
        event_type = "added" if len(before) < len(after) else "removed" if len(before) > len(after) else "updated"
        if event_type == "updated":
            diff = [
                EmojiAttrDiff(
                    attr="name",
                    emoji=after_state,
                    before=before_state.name,
                    after=after_state.name,
                )
                for before_state, after_state in zip(before, after)
                if _diff("name", before_state, after_state)
            ]
            if not diff:
                return
        else:
            diff = set(after) ^ set(before)
        await self.guild_dispatch.guild_emoji_update(guild, event_type, diff)

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild: discord.Guild):
        await self.guild_dispatch.guild_integrations_update(guild)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        await self.guild_dispatch.channel_webhooks_update(channel)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.member_dispatch.member_membership_update(member, "joined")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.member_dispatch.member_membership_update(member, "left")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        set_after = set([(attr, getattr(after, attr)) for attr in after.__slots__
                         if not attr.startswith("_")
                         and not attr == "system"
                         and not type(getattr(after, attr)) == list])
        set_before = set([(attr, getattr(before, attr)) for attr in before.__slots__
                          if not attr.startswith("_")
                          and not attr == "system"
                          and not type(getattr(before, attr)) == list])
        diff_list = [MemberDiff(attr, getattr(before, attr), value) for attr, value in set_after - set_before]
        if not diff_list:
            role_set_after = set([role for role in after.roles])
            role_set_before = set([role for role in before.roles])
            role_type = "role_add" if len(role_set_after) > len(role_set_before) else "role_remove"
            diff_list = [MemberRoleDiff(role_type, value) for value in role_set_after ^ role_set_before]
            if not diff_list:
                return
        await self.member_dispatch.member_update(after, diff_list)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.User, discord.Member]):
        await self.member_dispatch.member_ban_update(guild, user, "banned")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        await self.member_dispatch.member_ban_update(guild, user, "unbanned")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        set_after = set([(attr, getattr(after, attr)) for attr in after.__slots__
                         if not attr.startswith("_")
                         and not type(getattr(after, attr)) == list])
        set_before = set([(attr, getattr(before, attr)) for attr in before.__slots__
                          if not attr.startswith("_")
                          and not type(getattr(before, attr)) == list])
        diff_list = [MemberDiff(attr, getattr(before, attr), value) for attr, value in set_after - set_before]
        await self.member_dispatch.member_voice_state_update(member, diff_list)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        await self.guild_dispatch.guild_invite_update(invite, "created")

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        await self.guild_dispatch.guild_invite_update(invite, "deleted")

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        await self.guild_dispatch.message_raw_edit(
            payload.message_id,
            payload.channel_id,
            payload.data
        )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        await self.guild_dispatch.message_raw_delete(
            payload.message_id,
            payload.channel_id,
            payload.cached_message
        )

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        await self.guild_dispatch.message_raw_bulk_delete(
            payload.message_ids,
            payload.channel_id
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.guild_dispatch.reaction_raw_update(
            payload.message_id,
            payload.emoji,
            payload.user_id,
            payload.channel_id,
            "reaction added"
        )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.guild_dispatch.reaction_raw_update(
            payload.message_id,
            payload.emoji,
            payload.user_id,
            payload.channel_id,
            "reaction removed"
        )

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionClearEvent):
        await self.guild_dispatch.reaction_raw_clear(
            payload.message_id,
            payload.channel_id
        )

    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(self, payload: discord.RawReactionClearEmojiEvent):
        await self.guild_dispatch.reaction_raw_clear_emoji(
            payload.message_id,
            payload.channel_id,
            payload.emoji
        )

    async def init_logging(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            values = "(guild_id bigint PRIMARY KEY, webhook_id bigint, \"" + \
                '\" boolean DEFAULT FALSE, \"'.join(command.name.lower() for command in sorted(self.bot.commands,
                                                                                               key=lambda x: x.name)) + \
                "\" boolean DEFAULT FALSE)"
            await con.execute(f"CREATE TABLE IF NOT EXISTS logging{values}")
            for command in sorted(self.bot.commands, key=lambda x: x.name):
                await con.execute(f"ALTER TABLE logging ADD COLUMN IF NOT EXISTS \"{command.name.lower()}\" boolean DEFAULT FALSE ")
            for guild in self.bot.guilds:
                await con.execute(f"INSERT INTO logging(guild_id) VALUES ({guild.id}) ON CONFLICT DO NOTHING")
        return

    async def send_logging_help(self, ctx):
        pfx = f"{await self.gcmds.prefix(ctx)}logging"
        return await SubcommandHelp(
            pfx=pfx,
            title="Logging Help",
            description="\n".join(
                (
                    f"{ctx.author.mention}, the base command is `{pfx}` *aliases=`lg` `log`*. Logging is a powerful "
                    "tool that will allow you to track multiple things at a time:\n",
                    "**1. Command Execution**",
                    "> With logging level `basic`, UconnSmashBot can send a message in the specified logging channel "
                    "whenever a server member uses a command. Logging messages may vary depending on what command "
                    "was used. *For example, logging moderation commands may display the results of the moderation "
                    "action, or logging actions commands may display what action was done to which member*\n",
                    "**2. Server Modification Events**",
                    "> With logging level `server`, UconnSmashBot will be able to do anything in logging level `basic`, "
                    "but with the ability to log changes that happen to the server, such as moving voice regions, "
                    "renaming channels, changing channel permissions, anything that happens in audit log, etc\n",
                    "**3. Member Modification Events**",
                    "> With logging level `hidef`, UconnSmashBot will be able to do anything in logging level `server`, "
                    "but with the ability to log changes that happen to members in your server. This includes things "
                    "like status changes, nickname updates, username changes, etc. This can fall under a breach of "
                    "privacy, so this logging will only be reserved for those that have been pre-approved to access "
                    "this feature\n",
                    "Here are all the subcommands"
                )
            ),
            per_page=2,
        ).from_config("logging").show_help(ctx)

    async def check_loggable(self, ctx, channel: discord.TextChannel):
        async with self.bot.db.acquire() as con:
            on_blacklist = await con.fetch(f"SELECT * FROM guild WHERE guild_id={ctx.guild.id} AND log_channel=-1")
        if on_blacklist:
            raise customerrors.LoggingBlacklisted(ctx.guild)
        perms = ctx.guild.me.permissions_in(channel)
        if not perms.send_messages:
            raise customerrors.CannotMessageChannel(channel)

    async def set_logging_channel(self, ctx, channel: discord.TextChannel) -> discord.Message:
        embed = discord.Embed()
        await self.check_loggable(ctx, channel)
        try:
            async with self.bot.db.acquire() as con:
                await con.execute(f"UPDATE guild SET log_channel={channel.id} WHERE guild_id={ctx.guild.id}")
                await con.execute(f"UPDATE guild SET log_level={LogLevel.BASIC.value} WHERE guild_id={ctx.guild.id} AND log_level=0")
            embed.title = "Logging Channel Set!"
            embed.description = f"{ctx.author.mention}, this server's logging channel was set to {channel.mention}"
            embed.color = discord.Color.blue()
        except Exception:
            embed.title = "Set Logging Channel Failed"
            embed.description = f"{ctx.author.mention}, I could not set this server's logging channel"
            embed.color = discord.Color.dark_red()
        return await ctx.channel.send(embed=embed)

    async def remove_logging(self, ctx):
        embed = discord.Embed()
        try:
            async with self.bot.db.acquire() as con:
                await con.execute(f"UPDATE guild SET log_channel=NULL WHERE guild_id={ctx.guild.id}")
            embed.title = "Logging Disabled"
            embed.description = f"{ctx.author.mention}, logging is now disabled on this server"
            embed.color = discord.Color.blue()
        except Exception:
            embed.title = "Disable Logging Failed"
            embed.description = f"{ctx.author.mention}, logging could not be disabled on this server"
            embed.color = discord.Color.dark_red()
        return await ctx.channel.send(embed=embed)

    async def set_logging_level(self, ctx, level_int):
        embed = discord.Embed()
        try:
            async with self.bot.db.acquire() as con:
                await con.execute(f"UPDATE guild SET log_level={LogLevel(level_int).value} WHERE guild_id={ctx.guild.id}")
            embed.title = "Logging Level Successfully Updated"
            embed.description = f"{ctx.author.mention}, the server's logging level is now `{LogLevel(level_int).name.lower()}`"
            embed.color = discord.Color.blue()
        except Exception:
            embed.title = "Update Logging Level Failed"
            embed.description = f"{ctx.author.mention}, I couldn't update the logging level for this server"
            embed.color = discord.Color.dark_red()
        return await ctx.channel.send(embed=embed)

    async def toggle_logging_command(self, ctx, name: str):
        if not name in [command.name.lower() for command in self.bot.commands]:
            if not name == "all":
                raise customerrors.LoggingCommandNameInvalid(name)
        try:
            if not name == "all":
                async with self.bot.db.acquire() as con:
                    update_bool = await con.fetchval(f"UPDATE logging SET \"{name}\"=NOT \"{name}\" WHERE guild_id={ctx.guild.id} RETURNING \"{name}\"")
                embed = discord.Embed(title=f"{name.title()} Toggle Set",
                                      description=f"{ctx.author.mention}, logging for the command `{name}` is now "
                                      f"{'enabled' if update_bool else 'disabled'}",
                                      color=discord.Color.blue())
            else:
                async with self.bot.db.acquire() as con:
                    update_bool = await con.fetchval(f"SELECT help FROM logging WHERE guild_id={ctx.guild.id}")
                    for command in self.bot.commands:
                        await con.execute(f"UPDATE logging SET \"{command.name.lower()}\"={not update_bool} WHERE guild_id={ctx.guild.id}")
                embed = discord.Embed(title="Command Toggles Set",
                                      description=f"{ctx.author.mention}, logging for all commands were ""{}"
                                      .format("enabled" if not update_bool else "disabled"),
                                      color=discord.Color.blue())
        except Exception:
            embed = discord.Embed(title="Toggle Set Failed",
                                  description=f"{ctx.author.mention}, I could not toggle logging status for the command `{name}`",
                                  color=discord.Color.dark_red())
        finally:
            return await ctx.channel.send(embed=embed)

    @commands.group(invoke_without_command=True,
                    aliases=['lg', 'log'],
                    desc="Displays the help command for logging",
                    usage="logging",
                    uperms=["Manage Server"])
    async def logging(self, ctx):
        return await self.send_logging_help(ctx)

    @logging.command(aliases=['-s', 'use', 'set'])
    @commands.has_permissions(manage_guild=True)
    async def logging_set(self, ctx, channel: discord.TextChannel):
        return await self.set_logging_channel(ctx, channel)

    @logging.command(aliases=['toggle', 'cmd', 'command'])
    @commands.has_permissions(manage_guild=True)
    async def logging_command(self, ctx, name: str):
        return await self.toggle_logging_command(ctx, name.lower())

    @logging.group(invoke_without_command=True, aliases=['ls', 'show', 'display', 'list'])
    async def logging_list(self, ctx, *, name: str):
        if name:
            return await self.logging_list_command(ctx, name)
        async with self.bot.db.acquire() as con:
            log_channel = await con.fetchval(f"SELECT log_channel FROM guild WHERE guild_id={ctx.guild.id}")
            log_level = LogLevel(await con.fetchval(f"SELECT log_level FROM guild WHERE guild_id={ctx.guild.id}"))
        if not log_channel or not log_level:
            raise customerrors.LoggingNotEnabled()
        embed = discord.Embed(title="Logging Details",
                              description=f"**Logging Channel:** {f'<#{log_channel}>' if log_channel else '`None Set`'}\n"
                              f"**Logging Level:** `{log_level}`",
                              color=discord.Color.blue() if log_channel else discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    @logging_list.command(aliases=['command', 'cmd'])
    async def logging_list_command(self, ctx, name: str):
        if not name.lower() in [command.name.lower() for command in self.bot.commands]:
            raise customerrors.LoggingCommandNameInvalid(name)
        async with self.bot.db.acquire() as con:
            status = await con.fetchval(f"SELECT {name.lower()} FROM logging WHERE guild_id={ctx.guild.id}")
        embed = discord.Embed(title="Command Logging Details",
                              description=f"Logging for the command `{name.lower()}` is ""**{}**"
                              .format('enabled' if status else 'disabled'),
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @logging.command(aliases=['rm', 'delete', 'reset', 'clear', 'remove', 'disable'])
    @commands.has_permissions(manage_guild=True)
    async def logging_disable(self, ctx):
        reactions = [reaction.value for reaction in ConfirmReactions]

        def reacted(reaction: discord.Reaction, user: discord.User):
            return reaction.emoji in reactions and user.id == ctx.author.id and reaction.message.id == panel.id

        panel_embed = discord.Embed(title="Confirmation",
                                    description=f"{ctx.author.mention}, this server will not log events until it is reenabled. "
                                    f"React with {reactions[0]} to confirm or {reactions[1]} to cancel",
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)
        for reaction in reactions:
            try:
                await panel.add_reaction(reaction)
            except Exception:
                pass

        try:
            result = await self.bot.wait_for("reaction_add", check=reacted, timeout=30)
        except asyncio.TimeoutError:
            return await self.gcmds.timeout(ctx, "logging disable", 30)
        await self.gcmds.smart_delete(panel)
        if result[0].emoji == reactions[0]:
            return await self.remove_logging(ctx)
        else:
            return await self.gcmds.canceled(ctx, "logging disable")

    @logging.group(invoke_without_command=True, aliases=['lvl', 'level', 'levels'])
    @commands.has_permissions(manage_guild=True)
    async def logging_level(self, ctx, level):
        return

    @logging_level.command(aliases=['1'])
    @commands.has_permissions(manage_guild=True)
    async def basic(self, ctx):
        return await self.set_logging_level(ctx, 1)

    @logging_level.command(aliases=['server', '2'])
    @commands.has_permissions(manage_guild=True)
    async def guild(self, ctx):
        return await self.set_logging_level(ctx, 2)

    @logging_level.command(aliases=['3'])
    @commands.is_owner()
    async def hidef(self, ctx):
        return await self.set_logging_level(ctx, 3)

    @logging.command(aliases=['bl', 'blacklist'])
    @commands.is_owner()
    async def logging_blacklist(self, ctx, guild: discord.Guild = None):
        if not guild:
            guild = ctx.guild
        async with self.bot.db.acquire() as con:
            await con.execute(f"UPDATE guild SET log_channel=-1, log_level=-1 WHERE guild_id={guild.id}")
        embed = discord.Embed(title="Server Logging Blacklisted",
                              description=f"{ctx.author.mention}, the server {guild.name} can no longer utilise any "
                              "logging functionality",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Logging(bot))
