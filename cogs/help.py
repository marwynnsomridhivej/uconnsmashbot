import discord
from discord.ext import commands
from datetime import datetime


class Help(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Cog "{self.qualified_name}" has been loaded')

    async def send_help(self, ctx, name: str, syntax: str, perms: list = None,
                        example: str = None, spec: str = None) -> discord.Message:
        timestamp = f"Executed by {ctx.author.display_name} " + "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now())
        cmd_name = self.client.get_command(ctx.command.name)
        aliases = cmd_name.aliases

        embed = discord.Embed(title=f"{name.title()} Help",
                              color=discord.Color.blue(),
                              url=f"https://github.com/marwynnsomridhivej/uconnsmashbot/tree/master/cogs#{name.lower()}")
        embed.add_field(name="Syntax",
                        value=syntax,
                        inline=False)
        if perms[0]:
            embed.add_field(name="User Perms",
                            value=perms[0],
                            inline=False)
        if perms[1]:
            embed.add_field(name="Bot Perms",
                            value=perms[1],
                            inline=False)
        if example:
            embed.add_field(name="Examples",
                            value=example,
                            inline=False)
        if spec:
            embed.add_field(name="Special Cases",
                            value=spec,
                            inline=False)

        embed.set_footer(text=timestamp,
                         icon_url=ctx.author.avatar_url)

        return await ctx.channel.send(embed=embed)

    @commands.group(aliases=['h'])
    async def help(self, ctx):
        if not ctx.invoked_subcommand:
            timestamp = f"Executed by {ctx.author.display_name} " + "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now())
            cogNames = [i for i in self.client.cogs]
            cogs = [self.client.get_cog(j) for j in cogNames]
            strings = {}
            for name in cogNames:
                cog_commands = self.client.get_cog(name).get_commands()
                strings.update({name.lower(): [command.name.lower() for command in cog_commands]})
            actionCmds = "`?actions` *for a full list*"
            helpCmds = f"`{'` `'.join(strings['help'])}`"
            moderationCmds = f"`{'` `'.join(strings['moderation'])}`"
            musicCmds = f"`{'` `'.join(strings['music'])}`"
            ownerCmds = f"`{'` `'.join(strings['owner'])}`"
            pokedexCmds = "`?pokedex` *for a full list*"
            rolesCmds = f"`{'` `'.join(strings['roles'])}`"
            welcomeCmds = f"`{'` `'.join(strings['welcome'])}`"

            cog_list = [("Actions", actionCmds), ("Help", helpCmds), ("Moderation", moderationCmds),
                        ("Music", musicCmds), ("Owner", ownerCmds), ("Pokédex", pokedexCmds), ("Roles", rolesCmds),
                        ("Welcomer", welcomeCmds)]

            embed = discord.Embed(title="Help Menu",
                                  description=f"{ctx.author.mention}, here are all the commands I support:",
                                  color=discord.Color.blue(),
                                  url="https://github.com/marwynnsomridhivej/uconnsmashbot/tree/master/cogs")

            for name, value in cog_list:
                embed.add_field(name=name,
                                value=value,
                                inline=False)

            embed.set_footer(text=timestamp,
                             icon_url=ctx.author.avatar_url)

            return await ctx.channel.send(embed=embed)


def setup(client):
    client.add_cog(Help(client))
