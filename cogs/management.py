import discord
from discord.ext import commands
from discord.ext.commands.errors import MemberNotFound


class Management(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(aliases=['cinv', 'makeinvite'],
                      desc="Creates an instant invite link for the specified channel",
                      usage="createinvite [#channel]",
                      uperms=['Create Instant Invite'],
                      bperms=['Create Instant Invite'])
    @commands.has_permissions(create_instant_invite=True)
    @commands.bot_has_permissions(create_instant_invite=True)
    async def createinvite(self, ctx, channel: discord.TextChannel):
        invite = await channel.create_invite(unique=True, reason=f"{ctx.author} user createinvite")
        embed = discord.Embed(title="Instant Invite Created",
                              description=f"{ctx.author.mention}, here is your newly created instant invite:\n"
                              f"{invite.url}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['dinv', 'rinv', 'removeinvite'],
                      desc="Removes an instant invite, or expires it",
                      usage="delinvite [invite]",
                      uperms=['Manage Channels'],
                      bperms=['Manage Channels'],
                      note="`[invite]` can be an invite URL or an invite code")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def delinvite(self, ctx, invite: discord.Invite):
        await invite.delete(reason=f"{ctx.author} used delinvite")
        embed = discord.Embed(title="Instant Invite Deleted",
                              description=f"{ctx.author}, the instant invite {invite.url} has been deleted. "
                              "It can no longer be used",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['ctc', 'maketextchannel'],
                      desc="Creates a text channel with the specified name",
                      usage="createtextchannel [channel_name]",
                      uperms=['Manage Channels'],
                      bperms=['Manage Channels'],
                      note="`[channel_name]` must not conflict with existing channel names. "
                      "Whitespace will be converted to dashes  and everything "
                      "will be lowercased as required by Discord's naming rules")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def createtextchannel(self, ctx, *, name: str):
        channel = await ctx.guild.create_text_channel(name.lower().replace(" ", "-"))
        embed = discord.Embed(title="Channel Created",
                              description=f"{ctx.author.mention}, you created {channel.mention}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['dtc', 'removetextchannel'],
                      desc="Deletes the specified text channel",
                      usage="deltextchannel [#channel]",
                      uperms=['Manage Channels'],
                      bperms=['Manage Channels'])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def deltextchannel(self, ctx, channel: discord.TextChannel):
        await channel.delete(reason=f"{ctx.author} used deltextchannel")
        embed = discord.Embed(title="Channel Deleted",
                              description=f"{ctx.author.mention}, you deleted {channel.name}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['cvc', 'makevoicechannel'],
                      desc="Creates a voice channel with the specified name",
                      usage="createvoicechannel [channel_name]",
                      uperms=['Manage Channels'],
                      bperms=['Manage Channels'],
                      note="`[channel_name]` must not conflict with existing channel names")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def createvoicechannel(self, ctx, *, name: str):
        await ctx.guild.create_voice_channel(name)
        embed = discord.Embed(title="Channel Created",
                              description=f"{ctx.author.mention}, you created `{name}`",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['dvc', 'removevoicechannel'],
                      desc="Deletes the specified voice channel",
                      usage="delvoicechannel [#channel]",
                      uperms=['Manage Channels'],
                      bperms=['Manage Channels'])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def delvoicechannel(self, ctx, channel: discord.VoiceChannel):
        await channel.delete(reason=f"{ctx.author} used delvoicechannel")
        embed = discord.Embed(title="Channel Deleted",
                              description=f"{ctx.author.mention}, you deleted {channel.name}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['ccc', 'makecategory'],
                      desc="Creates a category with the specified name",
                      usage="createcategory [category_name]",
                      uperms=['Manage Channels'],
                      bperms=['Manage Channels'],
                      note="`[category_name]` must not conflict with existing channel names")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def createcategory(self, ctx, *, name: str):
        await ctx.guild.create_category(name)
        embed = discord.Embed(title="Channel Created",
                              description=f"{ctx.author.mention}, you created the category `{name}`",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['dcc', 'removecategory'],
                      desc="Deletes the specified category and its channels",
                      usage="delcategory [category_name]",
                      uperms=['Manage Channels'],
                      bperms=['Manage Channels'])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def delcategory(self, ctx, cat_channel: discord.CategoryChannel):
        for channel in cat_channel.channels:
            await channel.delete(reason=f"{ctx.author} user delcategory")
        await cat_channel.delete(reason=f"{ctx.author} used deltextchannel")
        embed = discord.Embed(title="Channel Deleted",
                              description=f"{ctx.author.mention}, you deleted the category {cat_channel.name}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['cnick', 'editnick'],
                      desc="Edits a member's nickname",
                      usage="changenick [@member] (new_nickname)",
                      uperms=['Manage Nicknames'],
                      bperms=['Manage Nicknames'],
                      note="If `(new_nickname)` is unspecified, it will reset the member's nickname "
                      "to their Discord username. Equivalent to removing their nickname")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def changenick(self, ctx, member: discord.Member, *, nickname: str = None):
        old_name = member.display_name
        await member.edit(nick=nickname)
        new_name = member.display_name
        embed = discord.Embed(title="Changed Nickname",
                              description=f"{ctx.author.mention}, {member.mention}'s nickname changed "
                              f"from `{old_name}` to `{new_name}`",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['arole', 'aroles'],
                      desc="Adds the specified roles to the specified members",
                      usage="addroles [@member]*va [@role]*va",
                      uperms=['Manage Roles'],
                      bperms=['Manage Roles'])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def addroles(self, ctx, members: str, roles: commands.Greedy[discord.Role]):
        if members == "all":
            members = [member for member in ctx.guild.members if not member.bot]
        elif members == "bots":
            members = [member for member in ctx.guild.members if member.bot]
        else:
            converter = commands.MemberConverter()
            members = []
            for substr in members.split(","):
                try:
                    members.append(await converter.convert(ctx, substr))
                except MemberNotFound:
                    pass
        for member in members:
            await member.add_roles(*roles, reason=f"{ctx.author} user addroles", atomic=True)
        embed = discord.Embed(title="Added Roles",
                              description=f"{ctx.author.mention}, all specified members received their roles",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['rrole', 'rroles'],
                      desc="Removes the specified roles from the specified members",
                      usage="removeroles [@member]*va [@role]*va",
                      uperms=['Manage Roles'],
                      bperms=['Manage Roles'])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def removeroles(self, ctx, members: commands.Greedy[discord.Member], roles: commands.Greedy[discord.Role]):
        for member in members:
            await member.remove_roles(roles, reason=f"{ctx.author} user removeroles", atomic=True)
        embed = discord.Embed(title="Removed Roles",
                              description=f"{ctx.author.mention}, the specified roles were removed from "
                              "all specified members",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Management(bot))
