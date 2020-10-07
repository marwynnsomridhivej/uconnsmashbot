import os
import subprocess
import sys
from datetime import datetime
from io import BytesIO, StringIO

import discord
from asyncpg.exceptions import UniqueViolationError
from discord.ext import commands
from discord.ext.commands.errors import CommandInvokeError
from utils import customerrors, globalcommands, paginator

gcmds = globalcommands.GlobalCMDS()
OWNER_PERM = ["Bot Owner Only"]


class Owner(commands.Cog):

    def __init__(self, bot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_blacklist())
        self.bot.loop.create_task(self.init_balance())

    async def get_owner(self):
        await self.bot.wait_until_ready()
        owner = self.bot.get_user(self.bot.owner_id)
        return owner

    async def init_blacklist(self):
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS blacklist (type text, id bigint PRIMARY KEY)")

    async def init_balance(self):
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS balance (user_id bigint PRIMARY KEY, amount bigint)")

    async def get_premium_users(self, guild, op):
        async with self.bot.db.acquire() as con:
            result = await con.fetch("SELECT user_id FROM premium WHERE user_id IS NOT NULL ORDER BY id")
        if not result:
            raise customerrors.NoGlobalPremiumUsers() if op != "guild" else customerrors.NoPremiumUsers()
        else:
            if op != "guild":
                return [self.bot.get_user(int(user['user_id'])) for user in result]
            else:
                return [self.bot.get_user(int(user['user_id'])) for user in result if int(user['user_id']) in [member.id for member in guild.members]]

    async def get_premium_guilds(self):
        async with self.bot.db.acquire() as con:
            result = await con.fetch("SELECT guild_id FROM premium WHERE guild_id IS NOT NULL ORDER BY id")
        if not result:
            raise customerrors.NoPremiumGuilds()
        else:
            return [self.bot.get_guild(int(guild['guild_id'])) for guild in result]

    async def op_user_premium(self, op: str, user: discord.User) -> bool:
        try:
            async with self.bot.db.acquire() as con:
                if op == "set":
                    await con.execute(f"INSERT INTO premium(user_id) VALUES ({user.id})")
                elif op == "remove":
                    await con.execute(f"DELETE FROM premium WHERE user_id = {user.id}")
            return True
        except UniqueViolationError:
            raise customerrors.UserAlreadyPremium(user)
        except Exception:
            raise customerrors.UserPremiumException(user)

    async def op_guild_premium(self, op: str, guild: discord.Guild) -> bool:
        try:
            owner = await self.get_owner()
            async with self.bot.db.acquire() as con:
                if op == "set":
                    await con.execute(f"INSERT INTO premium(guild_id) VALUES ({guild.id})")
                    embed = discord.Embed(title=f"{guild.name} is now a UconnSmashBot Premium Server",
                                          description=f"{guild.owner.mention}, {owner.mention} has granted {guild.name} a "
                                          f"never expiring UconnSmashBot Premium subscription. Thank you for being a supporter of UconnSmashBot!",
                                          color=discord.Color.blue())
                    embed.set_footer(text=f"Although this version of UconnSmashBot Premium will never expire, it can be "
                                     f"revoked at any time at the discretion of {owner.name}")
                elif op == "remove":
                    await con.execute(f"DELETE FROM premium WHERE guild_id = {guild.id}")
                    embed = discord.Embed(title=f"{guild.name} is no longer a UconnSmashBot Premium Server",
                                          description=f"{guild.owner.mention}, the UconnSmashBot Premium subscription for "
                                          f"{guild.name} has been revoked. Please contact {owner.mention} if you "
                                          "believe this was a mistake",
                                          color=discord.Color.dark_red())
            try:
                await guild.owner.send(embed=embed)
            except Exception:
                pass
            return True
        except UniqueViolationError:
            raise customerrors.GuildAlreadyPremium(guild)
        except Exception:
            raise customerrors.GuildPremiumException(guild)
        return

    @commands.group(invoke_without_command=True,
                    aliases=['g'],
                    desc="Git operations",
                    usage="git [command]",
                    uperms=OWNER_PERM)
    @commands.is_owner()
    async def git(self, ctx, *, args: str):
        embed = discord.Embed(title="Git Output")
        try:
            output = subprocess.check_output(f"git {args}", stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            output = e.output
            embed.color = discord.Color.dark_red()
        else:
            embed.color = discord.Color.blue()

        if len(output) <= 2048:
            embed.description = f"```{output.decode('utf-8') if output else f'{args} executed successfully'}```"
            return await ctx.channel.send(embed=embed)
        else:
            embed.description = "```\nSTDOUT longer than 2048 characters. See the file below:\n```"
            stdout_file = discord.File(
                BytesIO(output), filename=f"{ctx.author.display_name.upper()}{datetime.now()}.txt")
            await ctx.channel.send(embed=embed)
            return await ctx.channel.send(file=stdout_file)

    @git.command(aliases=['gpod'])
    @commands.is_owner()
    async def git_gpod(self, ctx):
        return await self.git(ctx, args="pull origin development")

    @git.command(aliases=['gpom'])
    @commands.is_owner()
    async def git_gpom(self, ctx):
        return await self.git(ctx, args="pull origin master")

    @commands.command(aliases=['l', 'ld'],
                      desc="Loads cogs",
                      usage="load [extension]",
                      uperms=OWNER_PERM)
    @commands.is_owner()
    async def load(self, ctx, extension):
        try:
            self.bot.load_extension(f'cogs.{extension}')
        except CommandInvokeError:
            title = "Cog Load Fail"
            description = f"Failed to load cog {extension}, it is already loaded"
            color = discord.Color.blue()
        else:
            print(f'Cog "{extension}" has been loaded')
            title = "Cog Load Success"
            description = f"Successfully loaded cog {extension}"
            color = discord.Color.blue()
        loadEmbed = discord.Embed(title=title,
                                  description=description,
                                  color=color)
        await ctx.channel.send(embed=loadEmbed)

    @commands.command(aliases=['ul', 'uld'],
                      desc="Unloads cogs",
                      usage="unload [extension]",
                      uperms=OWNER_PERM)
    @commands.is_owner()
    async def unload(self, ctx, extension):
        try:
            self.bot.unload_extension(f'cogs.{extension}')
        except CommandInvokeError:
            title = "Cog Unoad Fail"
            description = f"Failed to unload cog {extension}, it is already unloaded"
            color = discord.Color.blue()
        else:
            print(f'Cog "{extension}" has been unloaded')
            title = "Cog Unload Success"
            description = f"Successfully unloaded cog {extension}"
            color = discord.Color.blue()
        unloadEmbed = discord.Embed(title=title,
                                    description=description,
                                    color=color)
        await ctx.channel.send(embed=unloadEmbed)

    @commands.command(aliases=['r', 'rl'],
                      desc="Reloads cogs",
                      usage="reload (extension)",
                      uperms=OWNER_PERM)
    @commands.is_owner()
    async def reload(self, ctx, *, extension=None):
        if extension is None:
            print("==========================")
            for filenameReload in os.listdir('./cogs'):
                if filenameReload.endswith('.py'):
                    try:
                        self.bot.reload_extension(f'cogs.{filenameReload[:-3]}')
                        print(f'Cog "{filenameReload[:-3]}" has been reloaded')
                    except commands.ExtensionError:
                        self.bot.load_extension(f'cogs.{filenameReload[:-3]}')
                        print(f'Cog "{filenameReload[:-3]}" has been loaded')
            reloadEmbed = discord.Embed(title="Reload Success",
                                        description="Successfully reloaded all cogs",
                                        color=discord.Color.blue())
            await ctx.channel.send(embed=reloadEmbed)
            print("==========================")
        else:
            print("==========================")
            try:
                self.bot.reload_extension(f'cogs.{extension}')
                print(f'Cog "{extension}" has been reloaded')
            except commands.ExtensionError:
                self.bot.load_extension(f'cogs.{extension}')
                print(f'Cog "{extension}" has been loaded')
            reloadEmbed = discord.Embed(title="Reload Success",
                                        description=f"Successfully reloaded cog `{extension}`",
                                        color=discord.Color.blue())
            await ctx.channel.send(embed=reloadEmbed)
            print("==========================")

    @commands.command(aliases=['taskkill', 'sd'],
                      desc="Shuts the bot down",
                      usage="shutdown",
                      uperms=OWNER_PERM)
    @commands.is_owner()
    async def shutdown(self, ctx):
        shutdownEmbed = discord.Embed(title="Bot Shutdown Successful",
                                      description="Bot is logging out",
                                      color=discord.Color.blue())
        await ctx.channel.send(embed=shutdownEmbed)
        await self.bot.close()

    @commands.group(aliases=['balanceadmin', 'baladmin', 'balop'],
                    desc="Manages all user balances",
                    usage="balanceadmin (subcommand)",
                    uperms=OWNER_PERM)
    @commands.is_owner()
    async def balanceAdmin(self, ctx):
        return

    @balanceAdmin.command()
    @commands.is_owner()
    async def set(self, ctx, user: discord.Member, amount):
        try:
            user.id
        except AttributeError:
            invalid = discord.Embed(title="Invalid User",
                                    description=f"{ctx.author.mention}, please specify a valid user",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        try:
            amount = int(amount)
        except (TypeError, ValueError):
            invalid = discord.Embed(title="Invalid Amount",
                                    description=f"{ctx.author.mention}, please specify a valid credit amount",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        op = (f"INSERT INTO balance(user_id, amount) VALUES ({user.id}, {amount}) ON CONFLICT (user_id) "
              f"DO UPDATE SET amount = {amount} WHERE balance.user_id = {user.id}")
        await gcmds.balance_db(op)

        if amount != 1:
            spell = "credits"
        else:
            spell = "credit"

        setEmbed = discord.Embed(title="Balance Set",
                                 description=f"The balance for {user.mention} is now set to ```{amount} {spell}```",
                                 color=discord.Color.blue())
        return await ctx.channel.send(embed=setEmbed)

    @balanceAdmin.command()
    @commands.is_owner()
    async def give(self, ctx, user: discord.Member, amount):
        try:
            user.id
        except AttributeError:
            invalid = discord.Embed(title="Invalid User",
                                    description=f"{ctx.author.mention}, please specify a valid user",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        try:
            amount = int(amount)
        except (TypeError, ValueError):
            invalid = discord.Embed(title="Invalid Amount",
                                    description=f"{ctx.author.mention}, please specify a valid credit amount",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        op = (f"UPDATE balance SET amount = amount + {amount} WHERE user_id = {user.id}")
        await gcmds.balance_db(op)
        balance = await gcmds.balance_db(f"SELECT amount FROM balance WHERE user_id = {user.id}", ret_val=True)

        if balance != 1:
            spell = "credits"
        else:
            spell = "credit"

        if amount != 1:
            spell_amt = "credits"
        else:
            spell_amt = "credit"

        giveEmbed = discord.Embed(title="Balance Set",
                                  description=f"{user.mention} has been given `{amount} {spell_amt}`. \nTheir balance "
                                              f"is now ```{balance} {spell}```",
                                  color=discord.Color.blue())
        return await ctx.channel.send(embed=giveEmbed)

    @balanceAdmin.command()
    @commands.is_owner()
    async def remove(self, ctx, user: discord.Member, amount):
        try:
            user.id
        except AttributeError:
            invalid = discord.Embed(title="Invalid User",
                                    description=f"{ctx.author.mention}, please specify a valid user",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        try:
            amount = int(amount)
        except (TypeError, ValueError):
            invalid = discord.Embed(title="Invalid Amount",
                                    description=f"{ctx.author.mention}, please specify a valid credit amount",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        op = (f"UPDATE balance SET amount = amount - {amount} WHERE user_id = {user.id}")
        await gcmds.balance_db(op)
        balance = await gcmds.balance_db(f"SELECT amount FROM balance WHERE user_id = {user.id}", ret_val=True)
        if balance < 0:
            await gcmds.balance_db(f"UPDATE balance set amount = 0 WHERE user_id = {user.id}")
            balance = 0

        if balance != 1:
            spell = "credits"
        else:
            spell = "credit"

        if amount != 1:
            spell_amt = "credits"
        else:
            spell_amt = "credit"

        removeEmbed = discord.Embed(title="Balance Set",
                                    description=f"{user.mention} has had `{amount} {spell_amt}` removed. \nTheir "
                                                f"balance is now ```{balance} {spell}```",
                                    color=discord.Color.blue())
        return await ctx.channel.send(embed=removeEmbed)

    @commands.group(invoke_without_command=True,
                    aliases=['blist'],
                    desc="Sets the blacklists for users and/or servers",
                    usage="blacklist (subcommand)",
                    uperms=OWNER_PERM)
    @commands.is_owner()
    async def blacklist(self, ctx):
        return

    @blacklist.command(aliases=['member', 'user'])
    @commands.is_owner()
    async def _user(self, ctx, operation, user: discord.Member = None):
        if not user:
            invalid = discord.Embed(title="Invalid User",
                                    description=f"{ctx.author.mention}, please specify a valid user",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        try:
            user_id = user.id
        except (TypeError, AttributeError):
            invalid = discord.Embed(title="Invalid User",
                                    description=f"{ctx.author.mention}, please specify a valid user",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)
        if operation == "add":
            op = f"INSERT INTO blacklist(type, id) VALUES('user', {user.id}) ON CONFLICT DO NOTHING"
            await gcmds.blacklist_db(op)
            b_add = discord.Embed(title="Blacklist Entry Added",
                                  description=f"{ctx.author.mention}, {user.mention} has been added to the "
                                              f"blacklist",
                                  color=discord.Color.blue())
            await ctx.channel.send(embed=b_add)
        elif operation == "remove":
            op = f"DELETE FROM blacklist WHERE type = 'user' AND id = {user.id}"
            await gcmds.blacklist_db(op)
            b_remove = discord.Embed(title="Blacklist Entry Removed",
                                     description=f"{ctx.author.mention}, {user.mention} has been removed from "
                                                 f"the blacklist",
                                     color=discord.Color.blue())
            await ctx.channel.send(embed=b_remove)
        else:
            invalid = discord.Embed(title="Invalid Operation",
                                    description=f"{ctx.author.mention}, `{operation}` is an invalid operation",
                                    color=discord.Color.dark_red())
            await ctx.channel.send(embed=invalid)

    @blacklist.command(aliases=['server', 'guild'])
    @commands.is_owner()
    async def _guild(self, ctx, operation, *, server_id: int = None):
        if server_id is None:
            invalid = discord.Embed(title="Invalid Guild ID",
                                    description=f"{ctx.author.mention}, please provide a valid guild ID",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        try:
            guild = await self.bot.fetch_guild(int(server_id))
        except (TypeError, AttributeError):
            invalid = discord.Embed(title="Invalid Guild ID",
                                    description=f"{ctx.author.mention}, please specify a valid guild ID",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)
        if operation == "add":
            op = f"INSERT INTO blacklist(type, id) VALUES('guild', {guild.id}) ON CONFLICT DO NOTHING"
            await gcmds.blacklist_db(op)
            b_add = discord.Embed(title="Blacklist Entry Added",
                                  description=f"{ctx.author.mention}, {guild.name} `ID:{guild.id}` has been added "
                                              f"to the blacklist",
                                  color=discord.Color.blue())
            await ctx.channel.send(embed=b_add)
        elif operation == "remove":
            op = f"DELETE FROM blacklist WHERE id = {guild.id} AND type = 'guild'"
            await gcmds.blacklist_db(op)
            b_remove = discord.Embed(title="Blacklist Entry Removed",
                                     description=f"{ctx.author.mention}, {guild.name} `ID:{guild.id}` has been "
                                                 f"removed from the blacklist",
                                     color=discord.Color.blue())
            await ctx.channel.send(embed=b_remove)
        else:
            invalid = discord.Embed(title="Invalid Operation",
                                    description=f"{ctx.author.mention}, `{operation}` is an invalid operation",
                                    color=discord.Color.dark_red())
            await ctx.channel.send(embed=invalid)

    @commands.command(aliases=['fleave'],
                      desc="Forces the bot to leave a server",
                      usage="forceleave (server_id)",
                      uperms=OWNER_PERM,
                      note="If `(server_id)` is unspecified, the bot will leave the current "
                      "server the invocation context is in")
    @commands.is_owner()
    async def forceleave(self, ctx, guild_id=None):
        if guild_id is None:
            guild_id = ctx.guild.id
        await self.bot.get_guild(guild_id).leave()
        leaveEmbed = discord.Embed(title="Successfully Left Server",
                                   description=f"Left guild id: {id}",
                                   color=discord.Color.blue())
        await ctx.author.send(embed=leaveEmbed)

    @commands.group(invoke_without_command=True,
                    desc="Displays the premium message",
                    usage="premium")
    async def premium(self, ctx):
        description = ("UconnSmashBot Premium is an optional, subscription based plan that will grant the subscriber complete, unrestricted "
                       "access to all of UconnSmashBot's \"premium locked\" features, such as creating and saving playlists, receiving special monthly"
                       "balance crates, public tags, unlimited number of tags, a special role in the UconnSmashBot Support Server, and more!\n\n"
                       "**UconnSmashBot Premium is currently unavailable. This message will update when it becomes available, most likely after UconnSmashBot's"
                       "v1.0.0-rc.1 release**")
        embed = discord.Embed(title="UconnSmashBot Premium",
                              description=description,
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.is_owner()
    @premium.group(invoke_without_command=True, aliases=['set', '-s'])
    async def set_premium(self, ctx):
        return

    @set_premium.command(aliases=['user', '-u'])
    @commands.is_owner()
    async def users(self, ctx, user: discord.User, pm: bool = False):
        op = "set" if pm else "remove"
        title = f"{user} is now UconnSmashBot Premium!" if pm else f"{user} is no longer UconnSmashBot Premium"
        description = (f"{ctx.author.mention} set {user.mention} to UconnSmashBot Premium" if pm
                       else f"{ctx.author.mention} removed {user.mention}'s UconnSmashBot Premium")
        color = discord.Color.blue() if pm else discord.Color.dark_red()
        await self.op_user_premium(op, user)
        embed = discord.Embed(title=title, description=description, color=color)
        return await ctx.channel.send(embed=embed)

    @set_premium.command(aliases=['guild', '-g'])
    @commands.is_owner()
    async def guilds(self, ctx, pm: bool = False):
        op = "set" if pm else "remove"
        title = f"{ctx.guild.name} is now UconnSmashBot Premium!" if pm else f"{ctx.guild.name} is no longer UconnSmashBot Premium"
        description = (f"{ctx.author.mention} set {ctx.guild.name} to UconnSmashBot Premium" if pm
                       else f"{ctx.author.mention} removed {ctx.guild.name}'s UconnSmashBot Premium")
        color = discord.Color.blue() if pm else discord.Color.dark_red()
        await self.op_guild_premium(op, ctx.guild)
        embed = discord.Embed(title=title, description=description, color=color)
        return await ctx.channel.send(embed=embed)

    @premium.group(invoke_without_command=True, aliases=['list', '-l', '-ls'])
    @commands.is_owner()
    async def list_premium(self, ctx):
        return

    @list_premium.command(aliases=['users', '-u'])
    @commands.is_owner()
    async def user(self, ctx, source: str = "guild"):
        op = source if source == "guild" else "global"
        entries = [f"{user.mention} - {user.name}" for user in await self.get_premium_users(ctx.guild, op)]
        pag = paginator.EmbedPaginator(ctx, entries=entries, per_page=10, show_entry_count=True)
        pag.embed.title = f"UconnSmashBot Premium Users in {ctx.guild.name}" if op == "guild" else "UconnSmashBot Premium Users"
        return await pag.paginate()

    @list_premium.command(aliases=['guilds', '-g'])
    @commands.is_owner()
    async def guild(self, ctx):
        entries = [f"{guild.name}" for guild in await self.get_premium_guilds()]
        pag = paginator.EmbedPaginator(ctx, entries=entries, per_page=10, show_entry_count=True)
        pag.embed.title = "UconnSmashBot Premium Servers"
        return await pag.paginate()

    @commands.command(aliases=['dm', 'privatemessage'],
                      desc="Sends a user a DM",
                      usage="privatemessage [user] [message]")
    @commands.is_owner()
    async def privateMessage(self, ctx, user: discord.User, *, message):
        dmEmbed = discord.Embed(title="UconnSmashBot",
                                description=message,
                                color=discord.Color.blue())
        await user.send(embed=dmEmbed)
        dmEmbed.set_footer(text=f"Copy of DM sent to {user}")
        await ctx.author.send(embed=dmEmbed)


def setup(bot):
    bot.add_cog(Owner(bot))
