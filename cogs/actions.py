import json
import random
import aiohttp
import discord
from discord.ext import commands
from globalcommands import GlobalCMDS

gcmds = GlobalCMDS()
converter = commands.MemberConverter()


class Actions(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Cog "{self.qualified_name}" has been loaded')

    async def get_count_user(self, ctx, user):
        try:
            user = await converter.convert(ctx, user)
            if user != ctx.author:
                user_specified = True
            else:
                user_specified = False
        except (commands.BadArgument, TypeError):
            user = ctx.author
            user_specified = False

        cmdNameQuery = ctx.command.name

        init = {f"{cmdNameQuery}": {'give': {}, 'receive': {}}}
        gcmds.json_load('db/actionstats.json', init)
        with open('db/actionstats.json', 'r') as f:
            file = json.load(f)

            try:
                file[str(cmdNameQuery)]
            except KeyError:
                file[str(cmdNameQuery)] = {'give': {}, 'receive': {}}

            if user_specified:
                try:
                    file[str(cmdNameQuery)]['give'][str(ctx.author.id)] += 1
                except KeyError:
                    file[str(cmdNameQuery)]['give'][str(ctx.author.id)] = 1

                try:
                    give_exec_count = file[str(cmdNameQuery)]['give'][str(user.id)]
                except KeyError:
                    give_exec_count = 0

                try:
                    file[str(cmdNameQuery)]['receive'][str(user.id)] += 1
                except KeyError:
                    file[str(cmdNameQuery)]['receive'][str(user.id)] = 1
                receive_exec_count = file[str(cmdNameQuery)]['receive'][str(user.id)]
                with open('db/actionstats.json', 'w') as g:
                    json.dump(file, g, indent=4)
                    
            else:
                try:
                    file[str(cmdNameQuery)]['give'][str(self.client.user.id)] += 1
                except KeyError:
                    file[str(cmdNameQuery)]['give'][str(self.client.user.id)] = 1

                try:
                    give_exec_count = file[str(cmdNameQuery)]['give'][str(ctx.author.id)]
                except KeyError:
                    give_exec_count = 0

                try:
                    file[str(cmdNameQuery)]['receive'][str(ctx.author.id)] += 1
                except KeyError:
                    file[str(cmdNameQuery)]['receive'][str(ctx.author.id)] = 1
                receive_exec_count = file[str(cmdNameQuery)]['receive'][str(ctx.author.id)]
                with open('db/actionstats.json', 'w') as g:
                    json.dump(file, g, indent=4)

            return [give_exec_count, receive_exec_count, user, user_specified]

    async def embed_template(self, ctx, title: str, footer: str):
        api_key = gcmds.env_check("TENOR_API")
        if not api_key:
            no_api = discord.Embed(title="Missing API Key",
                                   description="Insert your Tenor API Key in the `.env` file",
                                   color=discord.Color.dark_red())
            return await ctx.channel.send(embed=no_api, delete_after=10)
        cmdNameQuery = ctx.command.name
        query = f"anime {cmdNameQuery}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    "https://api.tenor.com/v1/search?q=%s&key=%s&limit=%s" % (query, api_key, 6)) as image:
                response = await image.json()
                getURL = []
                for i in range(len(response['results'])):
                    for j in range(len(response['results'][i]['media'])):
                        getURL.append(response['results'][i]['media'][j]['gif']['url'])
                url = random.choice(getURL)
                await session.close()

        embed = discord.Embed(title=title,
                              color=discord.Color.blue())
        embed.set_image(url=url)
        embed.set_footer(text=footer)

        await ctx.channel.send(embed=embed)

    @commands.command(aliases=['action'])
    async def actions(self, ctx, cmdName=None):

        CMDLIST = self.get_commands()
        del CMDLIST[0]
        CMDNAMES = [i.name for i in CMDLIST]
        description = f"Do `?actions (action_name)` to get the usage of that particular " \
                      f"command.\n\n**List of all {len(CMDLIST)} actions:**\n\n `{'` `'.join(sorted(CMDNAMES))}` "
        if cmdName is None or cmdName == "actions":
            helpEmbed = discord.Embed(title="Actions Help",
                                      description=description,
                                      color=discord.Color.blue())
        else:
            if cmdName in CMDNAMES:
                action = cmdName.capitalize()
                helpEmbed = discord.Embed(title=f"Action - {action}",
                                          color=discord.Color.blue())
                helpEmbed.add_field(name="Usage",
                                    value=f"`?{cmdName} [optional user @mention]`",
                                    inline=False)
                pot_alias = self.client.get_command(name=cmdName)
                aliases = [g for g in pot_alias.aliases]
                if aliases:
                    value = "`" + "` `".join(sorted(aliases)) + "`"
                    helpEmbed.add_field(name="Aliases",
                                        value=value,
                                        inline=False)
                helpEmbed.add_field(name="Recipient",
                                    value=f"\nIf the argument `[optional user @mention]` is specified, "
                                          f"it will direct the action towards that user. Otherwise, {ctx.me.mention} "
                                          "will direct the action to you if specified as `me` `myself` or unspecified",
                                    inline=False)
            else:
                helpEmbed = discord.Embed(title="Action Not Found",
                                          description=f"{ctx.author.mention}, {cmdName} is not a valid action",
                                          color=discord.Color.blue())
        await ctx.channel.send(embed=helpEmbed)

    @commands.command(aliases=['BITE'])
    async def bite(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} bit {action_to}"
        footer = f"{action_to} was bitten {receive} times and bit others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['BLUSH'])
    async def blush(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} blushed at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is blushing"

        footer = f"{action_to} was blushed at {receive} times and blushed at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['BONK'])
    async def bonk(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} bonked {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} bonked themself"

        footer = f"{action_to} was bonked {receive} times and bonked others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['BOOP'])
    async def boop(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} boop {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} booped themself"

        footer = f"{action_to} was booped {receive} times and booped others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['BORED'])
    async def bored(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} bored {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is bored"

        footer = f"{action_to} was bored {receive} times and bored others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['CHASE'])
    async def chase(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} chased {action_to}"
        footer = f"{action_to} was chased {receive} times and chased others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['CHEER'])
    async def cheer(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} cheered for {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is cheering"

        footer = f"{action_to} was cheered for {receive} times and cheered for others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['COMFORT'])
    async def comfort(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} comforted {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} comforted themself"

        footer = f"{action_to} was comforted {receive} times and comforted others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['CRINGE'])
    async def cringe(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} cringed at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is cringing"

        footer = f"{action_to} was cringed at {receive} times and cringed at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['CRY'])
    async def cry(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} cried at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is crying"

        footer = f"{action_to} was cried at {receive} times and cried at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['CUDDLE'])
    async def cuddle(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} cuddled {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} cuddled themself"

        footer = f"{action_to} was cuddled {receive} times and cuddled others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['CUT'])
    async def cut(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} cut {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} cut themself"

        footer = f"{action_to} was cut {receive} times and cut others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['DAB'])
    async def dab(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} dabbed on {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is dabbing"

        footer = f"{action_to} was dabbed on {receive} times and dabbed on others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['DANCE'])
    async def dance(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} danced with {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is dancing"

        footer = f"{action_to} was danced with {receive} times and danced with others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['DESTROY'])
    async def destroy(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} destroyed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} destroyed themself"

        footer = f"{action_to} was destroyed {receive} times and destroyed others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['DIE'])
    async def die(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} made {action_to} die"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} died"

        footer = f"{action_to} died {receive} times and made others die {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['DROWN'])
    async def drown(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} drowned {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is drowning"

        footer = f"{action_to} was drowned {receive} times and drowned others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['EAT'])
    async def eat(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} ate {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is eating"

        footer = f"{action_to} was eaten {receive} times and ate others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['FACEPALM'])
    async def facepalm(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_to} made {action_by} facepalm"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is facepalming"

        footer = f"{action_to} facepalmed {receive} times and made others facepalm {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['FEED'])
    async def feed(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} fed {action_to}"
        footer = f"{action_to} was fed {receive} times and fed others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['FLIP'])
    async def flip(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} flipped {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} did a flip"

        footer = f"{action_to} was flipped {receive} times and flipped others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['FLIRT'])
    async def flirt(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} flirted with {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is flirting"

        footer = f"{action_to} was flirted with {receive} times and flirted with others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['FORGET'])
    async def forget(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} forgot about {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} forgot something..."

        footer = f"{action_to} was forgotten {receive} times and forgot others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['FRIEND'])
    async def friend(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} friended {action_to}"
        footer = f"{action_to} was friended {receive} times and friended others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['GLOMP'])
    async def glomp(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} glomped {action_to}"
        footer = f"{action_to} was glomped {receive} times and glomped others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['HANDHOLD'])
    async def handhold(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} held hands with {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is holding hands"

        footer = f"{action_to} was held hands with {receive} times and held hands with others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['HAPPY'])
    async def happy(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_to} made {action_by} happy"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is happy"

        footer = f"{action_to} was happy {receive} times and made others happy {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['HATE'])
    async def hate(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} hated {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} hated themself"

        footer = f"{action_to} was hated {receive} times and hated others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['HIGHFIVE'])
    async def highfive(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} highfived {action_to}"
        footer = f"{action_to} was highfived {receive} times and highfived others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['HUG'])
    async def hug(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} hugged {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} hugged themself"

        footer = f"{action_to} was hugged {receive} times and hugged others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['KILL'])
    async def kill(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} killed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} killed themself"

        footer = f"{action_to} was killed {receive} times and killed others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['KISS'])
    async def kiss(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} kissed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} wants a kiss"

        footer = f"{action_to} was kissed {receive} times and kissed others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['LAUGH'])
    async def laugh(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} laughed at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is laughing"

        footer = f"{action_to} was laughed at {receive} times and laughed at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['LICK'])
    async def lick(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} licked {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} licked themself"

        footer = f"{action_to} was licked {receive} times and licked others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['LOVE'])
    async def love(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} loved {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} loved themself"

        footer = f"{action_to} was loved {receive} times and loved others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['LURK'])
    async def lurk(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} lurked at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is lurking"

        footer = f"{action_to} was lurked at {receive} times and lurked at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['MARRY'])
    async def marry(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} married {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} wants to tie the knot"

        footer = f"{action_to} was married {receive} times and married others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['MISS'])
    async def miss(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} missed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} misses their friends"

        footer = f"{action_to} was missed {receive} times and missed others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['NERVOUS'])
    async def nervous(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_to} made {action_by} nervous"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is nervous"

        footer = f"{action_to} was nervous {receive} times and made others nervous {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['NO'])
    async def no(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]
        no_list = ['disagreed', 'no likey', "doesn't like that", "didn't vibe with that"]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} said no to {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} {random.choice(no_list)}"

        footer = f"{action_to} was said no to {receive} times and said no to others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['NOM'])
    async def nom(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} nommed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} nommed themself"

        footer = f"{action_to} was nommed {receive} times and nommed others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['NUZZLE'])
    async def nuzzle(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} nuzzled {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} nuzzled themself"

        footer = f"{action_to} was nuzzled {receive} times and nuzzled others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['PANIC'])
    async def panic(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} panicked {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is panicking"

        footer = f"{action_to} was panicked {receive} times and panicked others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['PAT'])
    async def pat(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} pat {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} pat themself"

        footer = f"{action_to} was pat {receive} times and pat others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['PECK'])
    async def peck(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} pecked {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} pecked themself"

        footer = f"{action_to} was pecked {receive} times and pecked others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['POKE'])
    async def poke(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} poked {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} poked themself"

        footer = f"{action_to} was poked {receive} times and poked others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['POUT'])
    async def pout(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} pouted at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is pouting"

        footer = f"{action_to} was pouted at {receive} times and pouted at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['PUNT'])
    async def punt(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} punted {action_to}"
        footer = f"{action_to} was punted {receive} times and punted others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['RUN'])
    async def run(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} ran from {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is running"

        footer = f"{action_to} was ran from {receive} times and ran from others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['RACE'])
    async def race(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} raced with {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} wants to race"

        footer = f"{action_to} was raced with {receive} times and raced with others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['SAD'])
    async def sad(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} saddened {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is sad"

        footer = f"{action_to} was saddened {receive} times and saddened others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['SHOOT'])
    async def shoot(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} shot {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is shooting aimlessly"

        footer = f"{action_to} was shot {receive} times and shot others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['SHRUG'])
    async def shrug(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} shrugged at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is shrugging"

        footer = f"{action_to} was shrugged at {receive} times and shrugged at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['SIP'])
    async def sip(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} sipped {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is sipping"

        footer = f"{action_to} was sipped {receive} times and sipped others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['SLAP'])
    async def slap(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} slapped {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} slapped themself"

        footer = f"{action_to} was slapped {receive} times and slapped others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['SLEEP'])
    async def sleep(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} made {action_to} fall asleep"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is sleeping"

        footer = f"{action_to} was made to sleep {receive} times and made others sleep {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['SLICE'])
    async def slice(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} sliced {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} sliced themself"

        footer = f"{action_to} was sliced {receive} times and sliced others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['SMUG'])
    async def smug(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} was smug to {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} has a smug face on"

        footer = f"{action_to} was smug {receive} times and was smug to others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['STAB'])
    async def stab(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} stabbed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} stabbed themself"

        footer = f"{action_to} was stabbed {receive} times and stabbed others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['STARE'])
    async def stare(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} stared at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is staring"

        footer = f"{action_to} was stared at {receive} times and stared at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['TACKLE'])
    async def tackle(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} tackled {action_to}"
        footer = f"{action_to} was tackled {receive} times and tackled others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['TAP'])
    async def tap(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        parts = ['head', 'neck', 'face', 'nose', 'forehead', 'shoulder', 'chest', 'arm', 'elbow', 'hand', 'stomach',
                 'leg', 'knee', 'foot', 'toe', 'ankle']

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            body = random.choice(parts)
            title = f"{action_by} tapped {action_to} on their {body}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} tapped themself"

        footer = f"{action_to} was flirted with {receive} times and flirted with others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['TASTE'])
    async def taste(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} tasted {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} tasted themself"

        footer = f"{action_to} was tasted {receive} times and tasted others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['TALK'])
    async def talk(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} talked to {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is talking"

        footer = f"{action_to} was talked with {receive} times and talked with others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['TAUNT'])
    async def taunt(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} taunted at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is taunting"

        footer = f"{action_to} was taunted at {receive} times and taunted at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['TEASE'])
    async def tease(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} teased {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is teasing"

        footer = f"{action_to} was teased {receive} times and teased others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['THANK'])
    async def thank(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        adjlist = ['thankful', 'grateful', 'appreciative']

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} thanked {action_to}"
        else:
            action_to = ctx.author.display_name
            adj = random.choice(adjlist)
            title = f"{action_to} is feeling {adj}"

        footer = f"{action_to} was thanked {receive} times and thanked others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['THINK'])
    async def think(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} thought about {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is thinking"

        footer = f"{action_to} was thought about {receive} times and thought about others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['THROW'])
    async def throw(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        objlist = ['an apple', 'an orange', 'a banana', 'a singular grape', 'a bunch of grapes', 'some hands',
                   'a spear', 'a trident', 'some water balloons', 'some eggs', 'a stuffed toad plushie',
                   'a computer out the window', 'a fridge at their neighbor', 'away the trash',
                   'a loaded gun instead of shooting it', 'their last brain cell out the window', 'a paper airplane',
                   'a plate', 'a blanket', 'a couch', 'a frustratingly long book', 'a knife', 'a samurai sword',
                   'a baseball', 'a football', 'a water polo ball', 'a pool ball', 'a beach ball', 'some poop',
                   'an exception', 'an error', 'their phone at the wall', 'a sharp stone', 'a shot put', 'a discus',
                   'away their chances at a relationship']

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} threw {action_to}"
        else:
            action_to = ctx.author.display_name
            obj = random.choice(objlist)
            title = f"{action_to} is throwing {obj}"

        footer = f"{action_to} was flirted with {receive} times and flirted with others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['THUMBSDOWN'])
    async def thumbsdown(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} gave {action_to} a thumbs down"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is giving a thumbs down"

        footer = f"{action_to} was given a thumbs down {receive} times and gave others a thumbs down {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['THUMBSUP'])
    async def thumbsup(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} gave {action_to} a thumbs up"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is giving a thumbs up"

        footer = f"{action_to} was given a thumbs up {receive} times and gave others a thumbs up {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['TICKLE'])
    async def tickle(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} tickled {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} tickled themself"

        footer = f"{action_to} was tickled {receive} times and tickled others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['TOUCH'])
    async def touch(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} touched {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} touched themself"

        footer = f"{action_to} was touched {receive} times and touched others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['TRASH'])
    async def trash(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} trashed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} trashed themself"

        footer = f"{action_to} was trashed {receive} times and trashed others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['triggered'])
    async def trigger(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} triggered {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is triggered"

        footer = f"{action_to} was triggered {receive} times and triggered others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['UPSET'])
    async def upset(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} upset {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is upset"

        footer = f"{action_to} was upset {receive} times and upset others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['WAG'])
    async def wag(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} wagged at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is wagging their tail"

        footer = f"{action_to} was wagged at {receive} times and wagged at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['WAIT'])
    async def wait(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} waited for {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is waiting"

        footer = f"{action_to} was waited for {receive} times and waited for others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['WAKEUP'])
    async def wakeup(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} woke {action_to} up"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} woke up"

        footer = f"{action_to} was woken up {receive} times and woke up others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['WASH'])
    async def wash(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} washed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} washed themself"

        footer = f"{action_to} was washed {receive} times and washed others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['WAVE'])
    async def wave(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} waved at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is waving"

        footer = f"{action_to} was waved at {receive} times and waved at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['WHINE'])
    async def whine(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} whined at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is whining"

        footer = f"{action_to} was whined at {receive} times and whined at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['WHISPER'])
    async def whisper(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} whispered to {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is whispering"

        footer = f"{action_to} was whispered to {receive} times and whispered to others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['WINK'])
    async def wink(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} winked at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is winking"

        footer = f"{action_to} was winked at {receive} times and winked at others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['WORRY'])
    async def worry(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} worried about {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is worrying"

        footer = f"{action_to} was worried about {receive} times and worried about others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return

    @commands.command(aliases=['YES'])
    async def yes(self, ctx, user=None):
        info = await self.get_count_user(ctx, user)
        give = info[0]
        receive = info[1]
        user = info[2]
        no_list = ['agreed', 'likey', "likes that", "vibed with that"]

        if info[3]:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} said yes to {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} {random.choice(no_list)}"

        footer = f"{action_to} was said yes to {receive} times and said yes to others {give} times"

        await self.embed_template(ctx,
                                  title=title,
                                  footer=footer)
        return


def setup(client):
    client.add_cog(Actions(client))
