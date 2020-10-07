import asyncio

import discord
from discord.ext import commands
from utils import customerrors, globalcommands, paginator

gcmds = globalcommands.GlobalCMDS()
reactions = ['✅', '🛑']


class Locks(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_locks())

    async def init_locks(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS locks(channel_id bigint PRIMARY KEY, type text, guild_id bigint, author_id bigint)")

    async def locks_help(self, ctx):
        pfx = f"{await gcmds.prefix(ctx)}lock"
        description = (f"{ctx.author.mention}, the base command is `{pfx}` *alias=`lk`*. Locks are designed to prevent UconnSmashBot from "
                       "executing commands in channels where you don't want UconnSmashBot commands to be run. This can be "
                       "useful if you are having trouble specifying permissions in your server/channel settings, or "
                       "if you have a designated bots channel where you want users to be able to invoke UconnSmashBot from. "
                       "With UconnSmashBot, you can lock specific channels or lock every channel but specific channels. "
                       "\n\nHere are all the subcommands")
        lset = (f"**Usage:** `{pfx} set [#channel]*va`",
                "**Returns:** A confirmation panel that will let the user confirm they would like to lock the specified channels",
                "**Alaises:** `-s`, `apply` `create`",
                "**Special Cases:** [#channel] must be channel tags. Multiple channels can be specified by separating the tags "
                "by commas. After confirmation, UconnSmashBot will no longer respond to any commands invoked in those channels",
                "**Note:** *if `[#channel]` is \"all\", UconnSmashBot will lock all channels except for the current channel*")
        llist = (f"**Usage:** `{pfx} list (flag)`",
                 "**Returns:** A list of all channels that are locked or explicitly unlocked",
                 "**Aliases:** `-ls` `show`",
                 "**Special Cases:** Valid `(flag)` are \"lock\", \"unlock\", and \"all\"")
        lunlock = (f"**Usage:** `{pfx} unlock [#channel]*va`",
                   "**Returns:** A confirmation panel that will let the user confirm they would like to unlock the specified channels",
                   "**Aliases:** `ulk` `-rm` `remove` `delete` `cancel`",
                   "**Special Cases:** [#channel] must be channel tags. Multiple channels can be specified by separating the tags "
                   "by commas, or \"all\" to unlock all locked channels. After confirmation, UconnSmashBot will once again"
                   " respond to any commands invoked in those channels",
                   f"**Note:** *this command can also be invoked with `{await gcmds.prefix(ctx)}unlock [#channel]\*va`*")
        nv = [("Set", lset), ("List", llist), ("Unlock", lunlock)]
        embed = discord.Embed(title="Lock Help", description=description, color=discord.Color.blue())
        for name, value in nv:
            embed.add_field(name=name, value="> " + "\n> ".join(value), inline=False)
        return await ctx.channel.send(embed=embed)

    async def check_lock(self, ctx, flag: str = None):
        async with self.bot.db.acquire() as con:
            if not flag:
                result = await con.fetch(f"SELECT * FROM locks WHERE guild_id={ctx.guild.id}")
            else:
                result = await con.fetch(f"SELECT * FROM locks WHERE guild_id={ctx.guild.id} AND type='{flag}'")
        return True if result else False

    async def set_lock(self, ctx, channels: list = None, flag: str = None):
        async with self.bot.db.acquire() as con:
            if flag == "all":
                values = f'({ctx.channel.id}, \'all_except\', {ctx.guild.id}, {ctx.author.id})'
                await con.execute(f"DELETE FROM locks WHERE guild_id={ctx.guild.id}")
                await con.execute(f"INSERT INTO locks(channel_id, type, guild_id, author_id) VALUES {values}")
            else:
                for channel in channels:
                    result = await con.fetchval(f"SELECT type FROM locks WHERE channel_id = {channel.id}")
                    if not result:
                        values = f'({channel.id}, \'locked\', {ctx.guild.id}, {ctx.author.id})'
                        await con.execute(f"INSERT INTO locks(channel_id, type, guild_id, author_id) VALUES {values}")
                    elif result == "all_except":
                        raise customerrors.LockAllExcept()
                    else:
                        await con.execute(f"UPDATE locks SET type='locked', author_id={ctx.author.id} WHERE channel_id={channel.id}")
        return

    async def get_locks(self, ctx, flag):
        async with self.bot.db.acquire() as con:
            if flag == "all":
                locks = await con.fetch(f"SELECT * FROM locks WHERE guild_id={ctx.guild.id} ORDER BY type")
                return [f"<#{item['channel_id']}>\n> Status: `{item['type']}`\n> Set by: <@{item['author_id']}>" for item in locks] if locks else None
            else:
                locks = await con.fetch(f"SELECT * FROM locks WHERE guild_id={ctx.guild.id} AND type='{flag + 'ed'}'")
                return [f"<#{item['channel_id']}>\n> {flag.title() + 'ed'} by: <@{item['author_id']}>" for item in locks] if locks else None

    async def set_unlock(self, ctx, channels: list = None, flag: str = None):
        async with self.bot.db.acquire() as con:
            if flag == "all":
                await con.execute(f"DELETE FROM locks WHERE guild_id={ctx.guild.id}")
            else:
                for channel in channels:
                    result = await con.fetchval(f"SELECT type FROM locks WHERE channel_id = {channel.id}")
                    if not result:
                        values = f'({channel.id}, \'unlocked\', {ctx.guild.id}, {ctx.author.id})'
                        await con.execute(f"INSERT INTO locks(channel_id, type, guild_id, author_id) VALUES {values}")
                    elif result != "all_except":
                        await con.execute(f"UPDATE locks SET type='unlocked', author_id={ctx.author.id} WHERE channel_id={channel.id}")
        return

    @commands.group(invoke_without_command=True,
                    aliases=['lk'],
                    desc="Displays the help command for locks",
                    usage="lock",
                    uperms=["Manage Server"])
    async def lock(self, ctx):
        return await self.locks_help(ctx)

    @lock.command(aliases=['-s', 'apply', 'create', 'set'])
    @commands.has_permissions(manage_guild=True)
    async def lock_set(self, ctx, channels: commands.Greedy[discord.TextChannel] = None, *, flag: str = None):
        if not (channels or flag):
            return await self.locks_help(ctx)

        if flag == "all" or not channels:
            channel_list = [channel for channel in ctx.guild.text_channels if channel.id != ctx.channel.id]
            lock_msg = f"every channel except for {ctx.channel.mention}"
        else:
            channel_list = [channel for channel in channels]
            lock_msg = f"{len(channel_list)} {'channels' if len(channel_list) != 1 else 'channel'}"
            flag = None

        def reacted(reaction: discord.Reaction, user: discord.User):
            return reaction.emoji in reactions and reaction.message.id == panel.id and user.id == ctx.author.id

        description = f"{ctx.author.mention}, you are about to lock {lock_msg}. "
        panel = await gcmds.confirmation(ctx, description)
        for reaction in reactions:
            try:
                await panel.add_reaction(reaction)
            except Exception:
                pass

        try:
            result = await self.bot.wait_for("reaction_add", check=reacted, timeout=30)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, "set channel lock", 30)
        await gcmds.smart_delete(panel)
        if result[0].emoji == reactions[0]:
            await self.set_lock(ctx, channel_list, flag)
            embed = discord.Embed(title="Locks Successfully Set",
                                  description=f"{ctx.author.mention}, the locks were successfully set",
                                  color=discord.Color.blue())
            return await ctx.channel.send(embed=embed)
        else:
            return await gcmds.cancelled(ctx, "set channel lock")

    @lock.command(aliases=['-ls', 'show', 'list'])
    async def lock_list(self, ctx, *, flag: str = "all"):
        if flag not in ['all', 'lock', 'unlock']:
            flag == 'all'
        entries = await self.get_locks(ctx, flag)
        if not entries:
            embed = discord.Embed(title="No Locks Set",
                                  description=f"{ctx.author.mention}, this server does not have any {flag + 'ed' if flag != 'all' else 'locked'} channels",
                                  color=discord.Color.dark_red())
            return await ctx.channel.send(embed=embed)
        else:
            pag = paginator.EmbedPaginator(ctx, entries=entries, per_page=10, show_entry_count=True)
            pag.embed.title = f"{flag.title() if flag != 'all' else 'All Locked'} Channels"
            return await pag.paginate()

    @lock.command(aliases=['ulk', '-rm', 'remove', 'delete', 'cancel', 'unlock'])
    @commands.has_permissions(manage_guild=True)
    async def lock_unlock(self, ctx, channels: commands.Greedy[discord.TextChannel] = None, *, flag: str = None):
        return await ctx.invoke(self.unlock, channels=channels, flag=flag)

    @commands.command(aliases=['ulk', '-rm', 'remove', 'delete', 'cancel'],
                      desc="Unlock channels that are currently locked",
                      usage="unlock [#channel]*va",
                      uperms=["Manage Server"],
                      note="If `[#channel]*va` is \"all\", all channels will be unlocked")
    @commands.has_permissions(manage_guild=True)
    async def unlock(self, ctx, channels: commands.Greedy[discord.TextChannel] = None, *, flag: str = None):
        if not (channels or flag):
            return await self.locks_help(ctx)

        if flag != "all" and not await self.check_lock(ctx, "unlocked"):
            raise customerrors.NoLocksExist()

        if flag == "all" or not channels:
            channel_list = [channel for channel in ctx.guild.text_channels if channel.id != ctx.channel.id]
            lock_msg = "every channel"
        else:
            channel_list = [channel for channel in channels]
            lock_msg = f"{len(channel_list)} {'channels' if len(channel_list) != 1 else 'channel'}"
            flag = None

        def reacted(reaction: discord.Reaction, user: discord.User):
            return reaction.emoji in reactions and reaction.message.id == panel.id and user.id == ctx.author.id

        description = f"{ctx.author.mention}, you are about to unlock {lock_msg}. "
        panel = await gcmds.confirmation(ctx, description)
        for reaction in reactions:
            try:
                await panel.add_reaction(reaction)
            except Exception:
                pass

        try:
            result = await self.bot.wait_for("reaction_add", check=reacted, timeout=30)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, "unlock", 30)
        await gcmds.smart_delete(panel)
        if result[0].emoji == reactions[0]:
            await self.set_unlock(ctx, channel_list, flag)
            embed = discord.Embed(title="Successfully Unlocked Channels",
                                  description=f"{ctx.author.mention}, the channels were successfully unlocked",
                                  color=discord.Color.blue())
            return await ctx.channel.send(embed=embed)
        else:
            return await gcmds.cancelled(ctx, "unlock")


def setup(bot):
    bot.add_cog(Locks(bot))
