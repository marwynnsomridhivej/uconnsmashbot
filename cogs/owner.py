import asyncio
import copy
import os
import subprocess
import typing
from contextlib import suppress
from datetime import datetime
from io import BytesIO

from aiohttp import ClientSession
import discord
from asyncpg.exceptions import UniqueViolationError
from discord.ext import commands
from discord.ext.commands import AutoShardedBot, Context
from discord.ext.commands.errors import CommandInvokeError
from utils import EmbedPaginator, GlobalCMDS, customerrors

OWNER_PERM = ["Bot Owner Only"]


class Owner(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self.bot.loop.create_task(self._init_tables())

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> discord.Message:
        owner = await self.get_owner()
        return await owner.send(
            embed=discord.Embed(
                title="New Guild Joined!",
                description=f"{owner.mention}, I just joined {guild.name}!",
                color=discord.Color.blue(),
            ).add_field(
                name="Info",
                value="\n".join([
                    f"ID: `{guild.id}`",
                    f"Owner: `{guild.owner or 'Unknown'}`",
                    f"Members: `{guild.member_count}`",
                ]),
                inline=False,
            ).set_thumbnail(
                url=guild.icon_url,
            )
        )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> discord.Message:
        owner = await self.get_owner()
        return await owner.send(
            embed=discord.Embed(
                title="Left Guild",
                description=f"{owner.mention}, I just left {guild.name}",
                color=discord.Color.dark_red(),
            ).set_thumbnail(
                url=guild.icon_url,
            )
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> discord.Message:
        owner = await self.get_owner()
        users = len(self.bot.users)
        if users % 1000 == 0:
            return await owner.send(
                embed=discord.Embed(
                    title="Milestone Reached!",
                    description=f"{owner.mention}, UconnSmashBot is now serving {users} users!",
                    color=discord.Color.blue(),
                )
            )

    async def get_owner(self) -> discord.User:
        await self.bot.wait_until_ready()
        owner = self.bot.get_user(self.bot.owner_id)
        return owner

    async def _init_tables(self):
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS balance (user_id bigint PRIMARY KEY, amount NUMERIC)")

    @staticmethod
    def _handle_task(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass

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

        async def close():
            await asyncio.sleep(1.0)
            await self.bot.close()
        self.bot.loop.create_task(close())

    @commands.command(desc="Runs a command as a different user",
                      usage="sudo [@member] (#channel) [invocation]",
                      uperms=OWNER_PERM,
                      note="This is only authorised for debugging purposes, such "
                      "as testing permissions. Always obtain consent to sudo invoke "
                      "as another member")
    @commands.is_owner()
    async def sudo(self, ctx: commands.Context, member: discord.Member, channel: typing.Optional[discord.TextChannel], *, invocation: str):
        message = copy.copy(ctx.message)
        channel = channel or ctx.channel
        message.channel = channel
        message.author = channel.guild.get_member(member.id) or member
        message.content = f"m!{invocation}"
        new_context = await self.bot.get_context(message, cls=type(ctx))
        reactions = ["✅", "❌"]
        embed = discord.Embed(title="Confirm Grant Sudo Privileges",
                              description=f"{member.mention}, in order to allow {ctx.author.mention} "
                              f"to invoke `{invocation}` under your name, react with ✅, to deny react with ❌",
                              color=discord.Color.blue())
        panel = await ctx.channel.send(embed=embed)
        for reaction in reactions:
            with suppress(Exception):
                await panel.add_reaction(reaction)

        def other_reacted(reaction: discord.Reaction, user: discord.User):
            return reaction.message.id == panel.id and user.id == member.id and str(reaction.emoji) in reactions

        try:
            reaction, user = await self.bot.wait_for("reaction_add", check=other_reacted, timeout=30)
        except asyncio.TimeoutError:
            return await self.gcmds.canceled(ctx, "sudo invoke")
        else:
            if reaction.emoji == reactions[0]:
                await new_context.channel.send(content=f"**{ctx.author}** invoked "
                                               f"`{invocation}` with sudo as **{member}**")
                await self.bot.invoke(new_context)
            else:
                embed = discord.Embed(title="Sudo Privileges Denied",
                                      description=f"{ctx.author.mention}, you were not give "
                                      "sudo privileges, and the command invocation was canceled",
                                      color=discord.Color.dark_red())
                return await ctx.channel.send(embed=embed)
        finally:
            await self.gcmds.smart_delete(panel)

    @commands.command(desc="Runs all commands in a cog",
                      usage="cogexec [cog]",
                      uperms=OWNER_PERM)
    @commands.is_owner()
    async def cogexec(self, ctx, cog_name: str):
        cog = self.bot.get_cog(f"{cog_name}")
        if not cog:
            embed = discord.Embed(title="No Cog Found",
                                  description=f"{ctx.author.mention}, there was no cog named `{cog_name}`",
                                  color=discord.Color.dark_red())
        else:
            try:
                for command in cog.walk_commands():
                    message = copy.copy(ctx.message)
                    message.content = f"m!{command.name}"
                    new_context = await self.bot.get_context(message, cls=type(ctx))
                    await new_context.reinvoke()
                    await asyncio.sleep(1.5)
            except Exception as e:
                embed = discord.Embed(title="Error Occurred",
                                      description=f"```Command: {command.name}\n\n{e}```",
                                      color=discord.Color.dark_red())
            else:
                embed = discord.Embed(title="Cog Commands Executed Successfully",
                                      description=f'{ctx.author.mention}, all commands in this cog were '
                                      'successfully executed',
                                      color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Runs a command multiple times",
                      usage="multexec (amount) [invocation]",
                      uperms=OWNER_PERM,
                      note="`(amount)` is how many times a command is to be run")
    @commands.is_owner()
    async def multexec(self, ctx, amount: int = 1, *, invocation: str):
        for _ in range(amount):
            message = copy.copy(ctx.message)
            message.content = f"m!{invocation}"
            new_context = await self.bot.get_context(message, cls=type(ctx))
            task = self.bot.loop.create_task(self.bot.invoke(new_context))
            task.add_done_callback(self._handle_task)
        embed = discord.Embed(
            title="Command Invoked Successfully",
            description=f"{ctx.author.mention}, `{message.content}` was "
            f"successfully invoked {amount} times",
            color=discord.Color.blue()
        )
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Runs a commands multiple times, but awaits each command",
                      usage="multexecawait (amount) [invocation]",
                      uperms=OWNER_PERM,
                      note="`(amount)` is how many times a command is to be run")
    @commands.is_owner()
    async def multexecawait(self, ctx: Context, amount: int = 1, *, invocation: str):
        message = copy.copy(ctx.message)
        message.content = f"m!{invocation}"
        new_context = await self.bot.get_context(message, cls=type(ctx))
        for _ in range(amount):
            await new_context.reinvoke()
        embed = discord.Embed(
            title="Command Invoked Successfully",
            description=f"{ctx.author.mention}, `{message.content}` was "
            f"successfully invoked {amount} times",
            color=discord.Color.blue()
        )
        return await ctx.channel.send(embed=embed)

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
        await self.gcmds.balance_db(op)

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
        await self.gcmds.balance_db(op)
        balance = await self.gcmds.balance_db(f"SELECT amount FROM balance WHERE user_id = {user.id}", ret_val=True)

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
        await self.gcmds.balance_db(op)
        balance = await self.gcmds.balance_db(f"SELECT amount FROM balance WHERE user_id = {user.id}", ret_val=True)
        if balance < 0:
            await self.gcmds.balance_db(f"UPDATE balance set amount = 0 WHERE user_id = {user.id}")
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


def setup(bot):
    bot.add_cog(Owner(bot))
