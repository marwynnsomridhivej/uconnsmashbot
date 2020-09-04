import discord
from discord.ext import commands
from datetime import datetime


class Help(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Cog "{self.qualified_name}" has been loaded')

    async def send_help(self, ctx, syntax: str, perms: list = None,
                        example: str = None, spec: str = None) -> discord.Message:
        timestamp = f"Executed by {ctx.author.display_name} " + "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now())
        name = ctx.command.name
        cmd = self.client.get_command(ctx.command.name)
        aliases = cmd.aliases

        embed = discord.Embed(title=f"{name.title()} Help",
                              color=discord.Color.blue(),
                              url=f"https://github.com/marwynnsomridhivej/uconnsmashbot/tree/master/cogs#{name.lower()}")
        embed.add_field(name="Syntax",
                        value=syntax,
                        inline=False)
        if aliases:
            embed.add_field(name="Aliases",
                            value=f"`{'` `'.join(aliases)}`")
        if example:
            embed.add_field(name="Examples",
                            value=example,
                            inline=False)
        if perms:
            if perms[0]:
                embed.add_field(name="User Perms",
                                value=f"`{perms[0].title()}`",
                                inline=False)
            if perms[1]:
                embed.add_field(name="Bot Perms",
                                value=f"`{perms[1].title()}`",
                                inline=False)
        if spec:
            embed.add_field(name="Special Cases",
                            value=spec,
                            inline=False)

        embed.set_footer(text=timestamp,
                         icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url="https://www.jing.fm/clipimg/full/71-716621_transparent-clip-art-open-book-frame-line-art.png")

        return await ctx.channel.send(embed=embed)

    @commands.group(aliases=['h', 'help'])
    async def _help(self, ctx):
        if not ctx.invoked_subcommand:
            timestamp = f"Executed by {ctx.author.display_name} " + "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now())
            cogNames = [i for i in self.client.cogs]
            cogs = [self.client.get_cog(j) for j in cogNames]
            strings = {}
            for name in cogNames:
                cog_commands = self.client.get_cog(name).get_commands()
                strings.update({name.lower(): [command.name.lower() for command in cog_commands]})
            actionCmds = "`?actions` *for a full list*"
            funCmds = f"`{'` `'.join(strings['fun'])}`"
            helpCmds = "`help`"
            moderationCmds = f"`{'` `'.join(strings['moderation'])}`"
            musicCmds = f"`{'` `'.join(strings['music'])}`"
            ownerCmds = f"`{'` `'.join(strings['owner'])}`"
            pokedexCmds = "`?pokedex` *for a full list*"
            rolesCmds = f"`{'` `'.join(strings['roles'])}`"

            cog_list = [("Actions", actionCmds), ("Help", helpCmds), ("Moderation", moderationCmds),
                        ("Music", musicCmds), ("Owner", ownerCmds), ("Pokédex", pokedexCmds), ("Roles", rolesCmds)]

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
            embed.set_thumbnail(url="https://www.jing.fm/clipimg/full/71-716621_transparent-clip-art-open-book-frame-line-art.png")

            return await ctx.channel.send(embed=embed)

    # Fun
    @_help.command(aliases=['8ball', '8b'])
    async def eightball(self, ctx):
        syntax = '?eightball [question]'
        return await self.send_help(ctx, syntax)
    
    @_help.command()
    async def choose(self, ctx):
        syntax = '`?choose [options]'
        spec = "`options` must be delimited by \"or\""
        return await self.send_help(ctx, syntax, spec=spec)
    
    @_help.command()
    async def say(self, ctx):
        syntax = "`?say [message]`"
        return await self.send_help(ctx, syntax)

    # Help
    @_help.command(aliases=['h'])
    async def help(self, ctx):
        syntax = "`?help (command_name)`"
        spec = ("If `command_name` is not explicitly specified, it defaults to showing all commands the bot currently "
                "supports")
        return await self.send_help(ctx, syntax, spec=spec)

    # Moderation
    @_help.command(aliases=['clear', 'clean', 'chatclear', 'cleanchat', 'clearchat', 'purge'])
    async def chatclean(self, ctx):
        syntax = "`?chatclean (amount) (@mention)-amount`"
        perms = ['manage messages', 'manage messages']
        spec = ("`amount` defaults to 1 and argument represents the number of messages to be processed. There will be "
                "some cases where this does not equal the number of deleted messages. The bot is not allowed to delete "
                "messages older than 2 weeks. This is a built in Discord API restriction\n\nIf `@mention` is specified,"
                " it will delete messages only from that user")
        return await self.send_help(ctx, syntax, perms=perms, spec=spec)

    @_help.command(aliases=['silence', 'stfu', 'shut', 'shush', 'shh', 'shhh', 'shhhh', 'quiet'])
    async def mute(self, ctx):
        syntax = "`?mute [@mention]*va (reason)(dt)`"
        perms = ['manage roles', 'manage roles']
        spec = ("You cannot mute an already muted person. This is determined by if the user has the \"Muted\" role, "
                "which is automatically generated by the bot\n\n`reason` defaults to \"Unspecified\" if not explicitly "
                "provided")
        return await self.send_help(ctx, syntax, perms=perms, spec=spec)

    @_help.command(aliases=['unsilence', 'unstfu', 'unshut', 'unshush', 'unshh', 'unshhh', 'unshhhh', 'unquiet'])
    async def unmute(self, ctx):
        syntax = "`?unmute [@mention]*va (reason)(dt)`"
        perms = ['manage roles', 'manage roles']
        spec = ("You cannot unmute an already unmuted person. This is determined by if the user has the \"Muted\" role, "
                "which is automatically generated by the bot\n\n`reason` defaults to \"Unspecified\" if not explicitly "
                "provided")
        return await self.send_help(ctx, syntax, perms=perms, spec=spec)

    @_help.command()
    async def kick(self, ctx):
        syntax = "`?kick [@mention]*va (reason)`"
        perms = ['kick members', 'kick members']
        spec = '`reason` defaults to "Unspecified" if not explicitly provided'
        return await self.send_help(ctx, syntax, perms=perms, spec=spec)

    @_help.command()
    async def ban(self, ctx):
        syntax = "`?ban [@mention]*va (msg_del_days) (reason)`"
        perms = ['ban members', 'ban members']
        spec = ("`msg_del_days` will delete the user's messages from the past `msg_del_days` days. `msg_del_days` "
                "defaults to 0 if not explicitly provided\n\n`reason` defaults to \"Unspecified\" if not explicitly "
                "provided")
        return await self.send_help(ctx, syntax, perms=perms, spec=spec)

    @_help.command()
    async def unban(self, ctx):
        syntax = "`?unban [user]*va`"
        perms = ['ban members', 'ban members']
        spec = ("`user` can be one of the following (in order of reliability)"
                "\n- User ID"
                "\n- User mention"
                "\n- User name#discriminator"
                "\n- User name")
        return await self.send_help(ctx, syntax, perms=perms, spec=spec)

    @_help.command()
    async def warn(self, ctx):
        syntax = "`?warn [@mention]*va (reason)`"
        perms = ['ban members', 'ban members']
        spec = ("- 1st Warn - Nothing"
                "\n- 2nd Warn - Mute for 10 minutes"
                "\n- 3rd Warn - Kicked from the server"
                "\n- 4th Warn - Banned from the server")
        return await self.send_help(ctx, syntax, perms=perms, spec=spec)

    @_help.command(aliases=['offenses'])
    async def offense(self, ctx):
        syntax = "`?offense (@mention)`"
        spec = ("This command searches for all warnings that you have given. If you haven't given that user any "
                "warnings, offense will return nothing, even if that user has warnings from other moderators")
        return await self.send_help(ctx, syntax, spec=spec)

    @_help.command()
    async def expunge(self, ctx):
        syntax = "`?expunge [@mention]`"
        perms = ['ban members', 'ban members']
        spec = ("Instructions on how to expunge warn records will be given on an interactive panel")
        return await self.send_help(ctx, syntax, perms=perms, spec=spec)

    @_help.command(aliases=['mod', 'mods', 'modsonline', 'mo'])
    async def modsOnline(self, ctx):
        syntax = "`?modsonline`"
        spec = ("This command searches for a role that contains the substring \"moderator\" (case insensitive)"
                "\n- Will only detect statuses `Online`, `Away`, and `DND`"
                "\n- Will not count any bots")
        return await self.send_help(ctx, syntax, spec=spec)

    # Music
    @_help.command()
    async def join(self, ctx):
        syntax = "`?join`"
        spec = ("This command will move the bot from its current connected channel to the one you are currently "
                "connected in if you execute this command while in a different voice channel as the bot")
        return await self.send_help(ctx, syntax, spec=spec)

    @_help.command()
    async def play(self, ctx):
        syntax = "`?play (query_URL)`"
        spec = ("`query_URL` can be the following types:"
                "\n- YouTube Video URL"
                "\n- YouTube Playlist URL"
                "\n- YouTube Livestream URL"
                "\n- A search term"
                "\n\n**ONLY IF** a song is loaded in queue, then you can execute play without specifying `query_URL`")
        return await self.send_help(ctx, syntax, spec=spec)

    @_help.command()
    async def queue(self, ctx):
        syntax = "`?queue (query_URL)`"
        spec = ("`query_URL` can be the following types:"
                "\n- YouTube Video URL"
                "\n- YouTube Playlist URL"
                "\n- YouTube Livestream URL"
                "\n- A search term"
                "\n- Nothing"
                "\nIf `query_URL` is not explicitly specified, it will display the current queue"
                "\n\nYou must be in the same voice channel as the bot to use this command")
        return await self.send_help(ctx, syntax, spec=spec)

    @_help.command(aliases=['clearqueue', 'qc'])
    async def queueclear(self, ctx):
        syntax = "`?queueclear`"
        spec = ("You must be in the same voice channel as the bot to use this command."
                " Nothing will be cleared if there is nothing queued")
        return await self.send_help(ctx, syntax, spec=spec)

    @_help.command()
    async def stop(self, ctx):
        syntax = "`?stop`"
        perms = ['server owner', 'server owner']
        spec = ("Only the server owner is authorised to use this command."
                " You must be in the same voice channel as the bot to use this command."
                " For ordinary users, click the stop icon on the play control panel.")
        return await self.send_help(ctx, syntax, perms=perms, spec=spec)

    @_help.command()
    async def leave(self, ctx):
        syntax = "`?leave`"
        spec = "You must be in the same voice channel as the bot to use this command"
        return await self.send_help(ctx, syntax, spec=spec)

    @_help.command()
    async def volume(self, ctx):
        syntax = "`?volume [amount]`"
        spec = "`amount` must be an integer between 1 - 100, otherwise it will display the current volume"
        return await self.send_help(ctx, syntax, spec=spec)

    @_help.command(aliases=['playlists'])
    async def playlist(self, ctx):
        syntax = "`?playlist (sub_command) (sub_command_args)`"
        spec = ("The playlist commands use interactive panels to allow for easy user input of values required for the "
                "commands to work\n\n**Subcommands:**\n"
                "**Load:**\n `?playlist load [playlist_name]` - loads a saved playlist\n\n"
                "**Save:**\n `?playlist save` *alias=`edit` - save curent queue as playlist*\n\n"
                "**Add:**\n `?playlist add` - add tracks to saved playlist\n\n"
                "**Remove:**\n `?playlist remove` *alias=`delete`* - remove saved playlist")
        return await self.send_help(ctx, syntax, spec=spec)

    # Owner
    @_help.command(aliases=['l', 'ld'])
    async def load(self, ctx):
        syntax = "`?load [extension]`"
        perms = ['bot owner', None]
        return await self.send_help(ctx, syntax, perms=perms)

    @_help.command(aliases=['ul', 'uld'])
    async def unload(self, ctx):
        syntax = "`?unload [extension]`"
        perms = ['bot owner', None]
        return await self.send_help(ctx, syntax, perms=perms)

    @_help.command(aliases=['r', 'rl'])
    async def reload(self, ctx):
        syntax = "`?reload`"
        perms = ['bot owner', None]
        return await self.send_help(ctx, syntax, perms=perms)

    @_help.command(aliases=['taskkill'])
    async def shutdown(self, ctx):
        syntax = "`?shutdown`"
        perms = ['bot owner', None]
        return await self.send_help(ctx, syntax, perms=perms)

    # Roles
    @_help.command(aliases=['rr'])
    async def reactionrole(self, ctx):
        syntax = "`?reactionrole (sub_command)`"
        perms = ['manage guild', 'manage roles` `add reactions']
        spec = ('Executing any reaction roles command will automatically start a setup panel that will guide you '
                'through inputting the required information for that command\n\n'
                "**Subcommands:**\n\n"
                "**Create:**\n`?reactionrole create` *aliases=`-c` `start` `make`* - creates a reaction roles panel\n\n"
                "**Edit:**\n`?reactionrole edit` *aliases=`-e` `adjust`* - edits an existing reaction roles panel\n\n"
                "**Delete:**\n`?reactionrole delete` *aliases=`-d` `-rm` `del`* - deletes an existing reaction roles panel")
        return await self.send_help(ctx, syntax, perms=perms, spec=spec)

    @_help.command()
    async def rank(self, ctx):
        syntax = "`?rank (role_name)`"
        spec = ("If `role_name` is not specified, it will return an embed with all the possible `role_name` arguments."
                " `role_name` is case sensitive\n\n"
                " Doing this command when you already have the role will remove the role from you")
        return await self.send_help(ctx, syntax, spec=spec)


def setup(client):
    client.add_cog(Help(client))
