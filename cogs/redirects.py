import asyncio

import discord
from discord.ext import commands
from utils import EmbedPaginator, GlobalCMDS, SubcommandHelp, customerrors

reactions = ["✅", "🛑"]


class Redirects(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_redirects())

    async def init_redirects(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS redirects(type text, command text, channel_id bigint, "
                              "guild_id bigint, author_id bigint)")

    async def get_redirect_help(self, ctx):
        pfx = f"{await self.gcmds.prefix(ctx)}redirect"
        embed = discord.Embed(
            title="Redirect Help",
            description=(
                f"{ctx.author.mention}, the base command for redirects is `{pfx}`. This command is used to instruct "
                "UconnSmashBot to redirect the output of a command to a specific channel. Redirects will only work "
                "for UconnSmashBot since UconnSmashBot cannot truly redirect other bots' outputs without causing some features "
                "to break.\n\nHere are the available subcommands for redirect"
            ),
            color=discord.Color.blue()
        ).set_footer(
            text=(
                "An important thing to note is that when setting the redirect for all commands at once, it will "
                "be assigned the type `all`, and when setting the redirect for specific commands or a list of commands, "
                "it will be assigned the type `override`. Essentially this means that when you set the redirect "
                "for a specific command, it will use that redirect, even if a global redirect was set. This is "
                "useful for when you want to redirect UconnSmashBot's output for all commmands to a specific channel "
                "EXCEPT for a couple commands. This is achieved by assigning their redirects seperately as stated above. "
                "Subcommand redirects are not supported, so the redirect will apply to all commands within the "
                "command group if the base command is a group"
            )
        )
        return await SubcommandHelp(
            pfx=pfx,
            embed=embed
        ).from_config("redirect").show_help(ctx)

    @commands.group(invoke_without_command=True,
                    aliases=['rd', "redirects"],
                    desc="Displays the help command for redirect",
                    usage="redirect")
    async def redirect(self, ctx):
        await self.get_redirect_help(ctx)

    @redirect.command(aliases=['-s', 'set', 'apply'])
    @commands.has_permissions(manage_guild=True)
    async def redirect_set(self, ctx, channel: discord.TextChannel, *, cmds: str):
        if cmds != "all":
            cmds = cmds.replace(" ", "").split(",")
            realcmds = [name.lower() for name in cmds if name in [command.name.lower()
                                                                  for command in self.bot.commands]]
            if not realcmds:
                raise customerrors.InvalidCommandSpecified()
            description = f"{ctx.author.mention}, the commands `{'` `'.join(realcmds)}` will be redirected to {channel.mention}."
            rtype = 'override'
        else:
            description = f"{ctx.author.mention}, all commands will be redirected to {channel.mention}."
            realcmds = None
            rtype = 'all'

        panel = await self.gcmds.confirmation(ctx, description)
        try:
            for reaction in reactions:
                await panel.add_reaction(reaction)
        except Exception:
            return await self.gcmds.canceled(ctx, "set redirect")

        def reacted(reaction: discord.Reaction, user: discord.User):
            return reaction.emoji in reactions and user.id == ctx.author.id and reaction.message.id == panel.id

        try:
            result = await self.bot.wait_for("reaction_add", check=reacted, timeout=30)
        except asyncio.TimeoutError:
            return await self.gcmds.timeout(ctx, "set redirect", 30)
        await self.gcmds.smart_delete(panel)
        if result[0].emoji == reactions[0]:
            try:
                async with self.bot.db.acquire() as con:
                    if realcmds:
                        for name in realcmds:
                            result = await con.fetchval(f"SELECT type FROM redirects WHERE guild_id={ctx.guild.id} AND command='{name}'")
                            if not result:
                                values = f"($tag${rtype}$tag$, '{name}', {channel.id}, {ctx.guild.id}, {ctx.author.id})"
                                await con.execute(f"INSERT INTO redirects(type, command, channel_id, guild_id, author_id) VALUES {values}")
                            else:
                                await con.execute(f"UPDATE redirects SET type='override', channel_id={channel.id}, "
                                                  f"author_id={ctx.author.id} WHERE command='{name}' AND guild_id={ctx.guild.id}")
                    else:
                        for command in self.bot.commands:
                            result = await con.fetchval(f"SELECT type FROM redirects WHERE guild_id={ctx.guild.id} AND command='{command.name.lower()}'")
                            if not result:
                                values = f"($tag${rtype}$tag$, '{command.name.lower()}', {channel.id}, {ctx.guild.id}, {ctx.author.id})"
                                await con.execute(f"INSERT INTO redirects(type, command, channel_id, guild_id, author_id) VALUES {values}")
                            else:
                                await con.execute(f"UPDATE redirects SET type='all', channel_id={channel.id}, "
                                                  f"author_id={ctx.author.id} WHERE command='{command.name.lower()}' AND guild_id={ctx.guild.id}")
            except Exception:
                raise customerrors.RedirectSetError()
            embed = discord.Embed(title="Redirects Set Successfully",
                                  description=f"{ctx.author.mention}, the redirects were set successfully",
                                  color=discord.Color.blue())
            return await ctx.channel.send(embed=embed)
        else:
            return await self.gcmds.canceled(ctx, "set redirect")

    @redirect.command(aliases=['ls', 'show', 'list'])
    async def redirect_list(self, ctx):
        try:
            async with self.bot.db.acquire() as con:
                overrides = await con.fetch(f"SELECT * FROM redirects WHERE guild_id={ctx.guild.id} AND type='override'")
                rglobal = await con.fetch(f"SELECT * FROM redirects WHERE guild_id={ctx.guild.id} AND type='all'")
        except Exception:
            raise customerrors.RedirectSearchError()

        or_count = [f"`{ovr['command']}` ⟶ <#{ovr['channel_id']}> [*set by <@{ovr['author_id']}>*]" for ovr in overrides] if overrides else [
            "No overriding redirects exist"]
        rg_count = f"{len(rglobal)} commands are globally redirected" if rglobal else "No global redirects exist"

        pag = EmbedPaginator(ctx, entries=or_count, per_page=10, show_entry_count=False)
        pag.embed.title = "Command Redirects"
        pag.embed.set_footer(text=rg_count)
        return await pag.paginate()

    @redirect.command(aliases=['rm', 'delete', 'cancel', 'remove'])
    @commands.has_permissions(manage_guild=True)
    async def redirect_remove(self, ctx, *, cmds: str):
        if cmds != "all":
            cmds = cmds.replace(" ", "").split(",")
            realcmds = [name.lower() for name in cmds if name in [command.name.lower()
                                                                  for command in self.bot.commands]]
            if not realcmds:
                raise customerrors.InvalidCommandSpecified()
            description = f"{ctx.author.mention}, the commands `{'` `'.join(realcmds)}` will no longer be redirected."
            rtype = 'override'
        else:
            description = f"{ctx.author.mention}, all commands will no longer be redirected."
            realcmds = None
            rtype = 'all'

        panel = await self.gcmds.confirmation(ctx, description)
        try:
            for reaction in reactions:
                await panel.add_reaction(reaction)
        except Exception:
            return await self.gcmds.canceled(ctx, "remove redirect")

        def reacted(reaction: discord.Reaction, user: discord.User):
            return reaction.emoji in reactions and user.id == ctx.author.id and reaction.message.id == panel.id

        try:
            result = await self.bot.wait_for("reaction_add", check=reacted, timeout=30)
        except asyncio.TimeoutError:
            return await self.gcmds.timeout(ctx, "remove redirect", 30)
        await self.gcmds.smart_delete(panel)
        if result[0].emoji == reactions[0]:
            try:
                async with self.bot.db.acquire() as con:
                    if realcmds:
                        for name in realcmds:
                            await con.execute(f"DELETE FROM redirects WHERE command='{name}' AND guild_id={ctx.guild.id}")
                    else:
                        for command in self.bot.commands:
                            await con.execute(f"DELETE FROM redirects WHERE command='{command.name.lower()}' AND guild_id={ctx.guild.id}")
            except Exception:
                raise customerrors.RedirectRemoveError()
            embed = discord.Embed(title="Redirects Removed Successfully",
                                  description=f"{ctx.author.mention}, the redirects were removed successfully",
                                  color=discord.Color.blue())
            return await ctx.channel.send(embed=embed)
        else:
            return await self.gcmds.canceled(ctx, "remove redirect")


def setup(bot):
    bot.add_cog(Redirects(bot))
