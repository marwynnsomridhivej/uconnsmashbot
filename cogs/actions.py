import json
import random

import aiohttp
import discord
from discord.ext import commands
from utils import customerrors, GlobalCMDS, objects

converter = commands.MemberConverter()


class Actions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_actions())

    async def init_actions(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS actions(action text PRIMARY KEY, give jsonb, receive jsonb)")
            await con.execute("CREATE TABLE IF NOT EXISTS action_blocks(blocked_id bigint, author_id bigint)")
            values = "('" + "'), ('".join(command.name for command in self.get_commands() if command.name != "actions") + "')"
            await con.execute(f"INSERT INTO actions(action) VALUES {values} ON CONFLICT DO NOTHING")

    async def get_count_user(self, ctx, user):
        try:
            user = await converter.convert(ctx, user)
            user_specified = True if user != ctx.author else False
        except (commands.BadArgument, TypeError):
            user = ctx.author
            user_specified = False

        async with self.bot.db.acquire() as con:
            result = (await con.fetch(f"SELECT give->>'{user.id}' AS give, receive->>'{user.id}' AS receive FROM actions WHERE action = '{ctx.command.name}'"))[0]
        give_exec_count = int(result['give']) + 1 if result['give'] else 0
        receive_exec_count = int(result['receive']) + 1 if result['receive'] else 1
        if user_specified:
            async with self.bot.db.acquire() as con:
                blocked = await con.fetchval(f"SELECT * FROM action_blocks WHERE blocked_id={ctx.author.id} AND author_id={user.id}")
                if blocked:
                    raise customerrors.SilentActionError(ctx.command.name, user)
                old_author = (await con.fetch(f"SELECT give FROM actions WHERE action = '{ctx.command.name}'"))[0]['give']
                old_recip = (await con.fetch(f"SELECT receive FROM actions WHERE action = '{ctx.command.name}'"))[0]['receive']
            if not old_author:
                new_author_val = "'{" + f'"{ctx.author.id}": 1' + "}'"
                new_author_op = f"UPDATE actions SET give = {new_author_val} WHERE action = '{ctx.command.name}'"
            else:
                old_author_dict = json.loads(old_author)
                try:
                    old_author_val = int(old_author_dict[str(ctx.author.id)])
                    author_cond = f"WHERE give->>'{ctx.author.id}' = '{old_author_val}' AND action = '{ctx.command.name}'"
                except KeyError:
                    old_author_val = 0
                    author_cond = f"WHERE action = '{ctx.command.name}'"
                new_author_dict = "'{" + f'"{ctx.author.id}" : {old_author_val + 1}' + "}'"
                new_author_op = (
                    f"UPDATE actions SET give = give::jsonb - '{ctx.author.id}' || {new_author_dict} {author_cond}")
            if not old_recip:
                new_recip_val = "'{" + f'"{user.id}": 1' + "}'"
                new_recip_op = f"UPDATE actions SET receive = {new_recip_val} WHERE action = '{ctx.command.name}'"
            else:
                old_recip_dict = json.loads(old_recip)
                try:
                    old_recip_val = int(old_recip_dict[str(user.id)])
                    recip_cond = f"WHERE receive->>'{user.id}' = '{old_recip_val}' AND action = '{ctx.command.name}'"
                except KeyError:
                    old_recip_val = 0
                    recip_cond = f"WHERE action = '{ctx.command.name}'"
                new_recip_dict = "'{" + f'"{user.id}" : {old_recip_val + 1}' + "}'"
                new_recip_op = (
                    f"UPDATE actions SET receive = receive::jsonb - '{user.id}' || {new_recip_dict} {recip_cond}")
            ops = [new_author_op, new_recip_op]
        else:
            async with self.bot.db.acquire() as con:
                old_author = (await con.fetch(f"SELECT give FROM actions WHERE action = '{ctx.command.name}'"))[0]['give']
                old_recip = (await con.fetch(f"SELECT receive FROM actions WHERE action = '{ctx.command.name}'"))[0]['receive']
            if not old_author:
                new_author_val = "'{" + f'"{self.bot.user.id}": 1' + "}'"
                new_author_op = f"UPDATE actions SET give = {new_author_val} WHERE action = '{ctx.command.name}'"
            else:
                old_author_dict = json.loads(old_author)
                try:
                    old_author_val = int(old_author_dict[str(self.bot.user.id)])
                    author_cond = f"WHERE give->>'{self.bot.user.id}' = '{old_author_val}' AND action = '{ctx.command.name}'"
                except KeyError:
                    old_author_val = 0
                    author_cond = f"WHERE action = '{ctx.command.name}'"
                new_author_dict = "'{" + f'"{self.bot.user.id}" : {old_author_val + 1}' + "}'"
                new_author_op = (
                    f"UPDATE actions SET give = give::jsonb - '{self.bot.user.id}' || {new_author_dict} {author_cond}")
            if not old_recip:
                new_recip_val = "'{" + f'"{ctx.author.id}": 1' + "}'"
                new_recip_op = f"UPDATE actions SET receive = {new_recip_val} WHERE action = '{ctx.command.name}'"
            else:
                old_recip_dict = json.loads(old_recip)
                try:
                    old_recip_val = int(old_recip_dict[str(ctx.author.id)])
                    recip_cond = f"WHERE receive->>'{ctx.author.id}' = '{old_recip_val}' AND action = '{ctx.command.name}'"
                except KeyError:
                    old_recip_val = 0
                    recip_cond = f"WHERE action = '{ctx.command.name}'"
                new_recip_dict = "'{" + f'"{ctx.author.id}" : {old_recip_val + 1}' + "}'"
                new_recip_op = (
                    f"UPDATE actions SET receive = receive::jsonb - '{ctx.author.id}' || {new_recip_dict} {recip_cond}")
            ops = [new_author_op, new_recip_op]
        async with self.bot.db.acquire() as con:
            for op in ops:
                await con.execute(op)
        return give_exec_count, receive_exec_count, user, user_specified

    async def embed_template(self, ctx, title: str, footer: str):
        api_key = self.gcmds.env_check("TENOR_API")
        if not api_key:
            no_api = discord.Embed(
                title="Missing API Key",
                description="Insert your Tenor API Key in the `.env` file",
                color=discord.Color.dark_red()
            )
            return await ctx.channel.send(embed=no_api)

        query = f"anime {ctx.command.name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    "https://g.tenor.com/v1/search?q=%s&key=%s&limit=%s&contentfilter=%s" % (query, api_key, 6, "medium")) as image:
                response = await image.json()
        embed = discord.Embed(
            title=title,
            color=discord.Color.blue()
        ).set_image(
            url=random.choice(
                [response['results'][i]['media'][j]['gif']['url']
                 for i in range(len(response['results']))
                 for j in range(len(response['results'][i]['media']))]
            )
        ).set_footer(
            text=footer
        )
        return await ctx.channel.send(embed=embed)

    @commands.group(invoke_without_command=True,
                    aliases=["action"],
                    desc="Displays the help command for all actions UconnSmashBot supports",
                    usage="actions (action_name)")
    async def actions(self, ctx, name: str = None):
        cmd_names = [command.name for command in self.get_commands() if command.name != "actions"]
        description = f"Do `{await self.gcmds.prefix(ctx)}actions [name]` to get the usage of that particular " \
                      f"command.\n\n**List of all {len(cmd_names)} actions:**\n\n `{'` `'.join(sorted(cmd_names))}`"
        embed = discord.Embed(
            title="Actions Help",
            description=description,
            color=discord.Color.blue()
        )
        if not name or name == "actions":
            embed.add_field(
                name="Blocking/Unblocking Users",
                value=f"Do `{await self.gcmds.prefix(ctx)}actions block/unblock [@user]*va (flag)` *`(flag)` "
                "can be \"all\" to block everyone in the server*",
                inline=False
            )
        elif name in cmd_names:
            embed.title = f"Action - {name.capitalize()}"
            embed.description = ""
            embed.color = discord.Color.blue()
            embed.add_field(
                name="Usage",
                value=f"`{await self.gcmds.prefix(ctx)}{name} (@user)`",
                inline=False
            ).add_field(
                name="Recipient",
                value=f"\nIf the argument `(@user)` is specified, "
                f"it will direct the action towards that user. Otherwise, {ctx.me.mention} "
                "will direct the action to you if specified as `me` `myself` or unspecified",
                inline=False
            )
            aliases = self.bot.get_command(name=name).aliases
            if aliases:
                value = "`" + "` `".join(sorted(aliases)) + "`"
                embed.add_field(
                    name="Aliases",
                    value=value,
                    inline=False,
                )
        else:
            embed.title = "Action Not Found",
            embed.description = f"{ctx.author.mention}, {name} is not a valid action"
            embed.color = discord.Color.dark_red()
        return await ctx.channel.send(embed=embed)

    @actions.command(aliases=['b', 'block'])
    async def actions_block(self, ctx, members: commands.Greedy[discord.Member] = None, flag: str = None):
        if not members and flag == "all":
            members = (member for member in ctx.guild.members if (
                member.id != ctx.author.id and member.id != self.bot.user.id))
            description = f"{ctx.author.mention}, you blocked everyone. You're gonna be a bit lonely now \:("
        elif len(members) == 1 and members[0].bot or members[0].id == ctx.author.id:
            embed = discord.Embed(title="Block Error",
                                  description=f"{ctx.author.mention}, you can't block {members[0].mention}",
                                  color=discord.Color.dark_red())
            return await ctx.channel.send(embed=embed)
        else:
            description = f"{ctx.author.mention}, you blocked {','.join(member.mention for member in members)}"

        async with self.bot.db.acquire() as con:
            for member in members:
                check = await con.fetch(f"SELECT blocked_id FROM action_blocks WHERE blocked_id={member.id} "
                                        f"AND author_id={ctx.author.id}")
                if not check:
                    await con.execute(f"INSERT INTO action_blocks(blocked_id, author_id) VALUES ({member.id}, {ctx.author.id})")

        embed = discord.Embed(title="Members Blocked", description=description, color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @actions.command(aliases=['ub', 'unblock'])
    async def actions_unblock(self, ctx, members: commands.Greedy[discord.Member] = None, flag: str = None):
        if not members and flag == "all":
            members = (member for member in ctx.guild.members if (
                member.id != ctx.author.id and member.id != self.bot.user.id))
            description = f"{ctx.author.mention}, you unblocked everyone. Welcome to the party \:)"
        elif len(members) == 1 and members[0].id == self.bot.user.id:
            embed = discord.Embed(title="Unblock Error",
                                  description=f"{ctx.author.mention}, you didn't block {members[0].mention}",
                                  color=discord.Color.dark_red())
            return await ctx.channel.send(embed=embed)
        else:
            description = f"{ctx.author.mention}, you unblocked {','.join(member.mention for member in members)}"

        for member in members:
            async with self.bot.db.acquire() as con:
                check = await con.fetch(f"SELECT blocked_id FROM action_blocks WHERE blocked_id={member.id} "
                                        f"AND author_id={ctx.author.id}")
                if check:
                    await con.execute(f"DELETE FROM action_blocks WHERE blocked_id={member.id} AND author_id={ctx.author.id}")

        embed = discord.Embed(title="Members Blocked", description=description, color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["BITE"],
                      desc="Bites someone",
                      usage="bite (@user)",)
    async def bite(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} bit {action_to}"
        footer = f"{action_to} was bitten {receive} times and bit others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["BLUSH"],
                      desc="Blushes at someone",
                      usage="blush (@user)",)
    async def blush(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} blushed at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is blushing"

        footer = f"{action_to} was blushed at {receive} times and blushed at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["BONK"],
                      desc="Bonks someone",
                      usage="bonk (@user)",)
    async def bonk(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} bonked {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} bonked themself"

        footer = f"{action_to} was bonked {receive} times and bonked others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["BOOP"],
                      desc="Boops someone",
                      usage="boop (@user)",)
    async def boop(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} boop {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} booped themself"

        footer = f"{action_to} was booped {receive} times and booped others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["BORED"],
                      desc="You're bored",
                      usage="bored (@user)",)
    async def bored(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} bored {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is bored"

        footer = f"{action_to} was bored {receive} times and bored others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["CHASE"],
                      desc="Chase someone",
                      usage="chase (@user)",)
    async def chase(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} chased {action_to}"
        footer = f"{action_to} was chased {receive} times and chased others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["CHEER"],
                      desc="cheers at someone",
                      usage="cheer (@user)",)
    async def cheer(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} cheered for {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is cheering"

        footer = f"{action_to} was cheered for {receive} times and cheered for others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["COMFORT"],
                      desc="comfort's someone",
                      usage="comfort (@user)",)
    async def comfort(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} comforted {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} comforted themself"

        footer = f"{action_to} was comforted {receive} times and comforted others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["CRINGE"],
                      desc="Cringes at someone",
                      usage="cringe (@user)",)
    async def cringe(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} cringed at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is cringing"

        footer = f"{action_to} was cringed at {receive} times and cringed at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["CRY"],
                      desc="Cries at someone",
                      usage="cry (@user)",)
    async def cry(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} cried at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is crying"

        footer = f"{action_to} was cried at {receive} times and cried at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["CUDDLE"],
                      desc="Cuddles someone",
                      usage="cuddle (@user)",)
    async def cuddle(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} cuddled {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} cuddled themself"

        footer = f"{action_to} was cuddled {receive} times and cuddled others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["CUT"],
                      desc="Cuts someone",
                      usage="cut (@user)",)
    async def cut(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} cut {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} cut themself"

        footer = f"{action_to} was cut {receive} times and cut others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["DAB"],
                      desc="Dabs at someone",
                      usage="dab (@user)",)
    async def dab(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} dabbed on {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is dabbing"

        footer = f"{action_to} was dabbed on {receive} times and dabbed on others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["DANCE"],
                      desc="Dances with someone",
                      usage="dance (@user)",)
    async def dance(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} danced with {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is dancing"

        footer = f"{action_to} was danced with {receive} times and danced with others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["DESTROY"],
                      desc="Destroys someone",
                      usage="destroy (@user)",)
    async def destroy(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} destroyed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} destroyed themself"

        footer = f"{action_to} was destroyed {receive} times and destroyed others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["DIE"],
                      desc="Dead",
                      usage="die (@user)",)
    async def die(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} made {action_to} die"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} died"

        footer = f"{action_to} died {receive} times and made others die {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["DROWN"],
                      desc="Drowns someone",
                      usage="drown (@user)",)
    async def drown(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} drowned {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is drowning"

        footer = f"{action_to} was drowned {receive} times and drowned others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["EAT"],
                      desc="You're eating!",
                      usage="eat (@user)",)
    async def eat(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} ate {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is eating"

        footer = f"{action_to} was eaten {receive} times and ate others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["FACEPALM"],
                      desc="Facepalms",
                      usage="facepalm (@user)",)
    async def facepalm(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_to} made {action_by} facepalm"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is facepalming"

        footer = f"{action_to} facepalmed {receive} times and made others facepalm {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["FEED"],
                      desc="Feeds someone",
                      usage="feed (@user)",)
    async def feed(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} fed {action_to}"
        footer = f"{action_to} was fed {receive} times and fed others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["FLIP"],
                      desc="Do a flip",
                      usage="flip (@user)",)
    async def flip(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} flipped {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} did a flip"

        footer = f"{action_to} was flipped {receive} times and flipped others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["FLIRT"],
                      desc="Flirts with someone",
                      usage="flirt (@user)",)
    async def flirt(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} flirted with {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is flirting"

        footer = f"{action_to} was flirted with {receive} times and flirted with others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["FORGET"],
                      desc="I don't remember...",
                      usage="forget (@user)",)
    async def forget(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} forgot about {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} forgot something..."

        footer = f"{action_to} was forgotten {receive} times and forgot others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["FRIEND"],
                      desc="Be a friend",
                      usage="friend (@user)",)
    async def friend(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} friended {action_to}"
        footer = f"{action_to} was friended {receive} times and friended others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["GLOMP"],
                      desc="Glomps someone",
                      usage="glomp (@user)",)
    async def glomp(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} glomped {action_to}"
        footer = f"{action_to} was glomped {receive} times and glomped others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["HANDHOLD"],
                      desc="Hold hands with someone",
                      usage="handhold (@user)",)
    async def handhold(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} held hands with {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is holding hands"

        footer = f"{action_to} was held hands with {receive} times and held hands with others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["HAPPY"],
                      desc="You're happy",
                      usage="happy (@user)",)
    async def happy(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_to} made {action_by} happy"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is happy"

        footer = f"{action_to} was happy {receive} times and made others happy {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["HATE"],
                      desc="Hate someone",
                      usage="hate (@user)",)
    async def hate(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} hated {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} hated themself"

        footer = f"{action_to} was hated {receive} times and hated others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["HIGHFIVE"],
                      desc="High fives someone",
                      usage="highfive (@user)",)
    async def highfive(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} highfived {action_to}"
        footer = f"{action_to} was highfived {receive} times and highfived others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["HUG"],
                      desc="Hugs someone",
                      usage="hug (@user)",)
    async def hug(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} hugged {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} hugged themself"

        footer = f"{action_to} was hugged {receive} times and hugged others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["KILL"],
                      desc="Kills someone",
                      usage="kill (@user)",)
    async def kill(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name
        title = f"{action_by} killed {action_to}"

        footer = f"{action_to} was killed {receive} times and killed others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["KISS"],
                      desc="Kisses someone",
                      usage="kiss (@user)",)
    async def kiss(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} kissed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} wants a kiss"

        footer = f"{action_to} was kissed {receive} times and kissed others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["LAUGH"],
                      desc="Laughs at someone",
                      usage="laugh (@user)",)
    async def laugh(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} laughed at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is laughing"

        footer = f"{action_to} was laughed at {receive} times and laughed at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["LICK"],
                      desc="Licks someone",
                      usage="lick (@user)",)
    async def lick(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} licked {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} licked themself"

        footer = f"{action_to} was licked {receive} times and licked others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["LOVE"],
                      desc="Loves someone",
                      usage="love (@user)",)
    async def love(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} loved {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} loved themself"

        footer = f"{action_to} was loved {receive} times and loved others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["LURK"],
                      desc="Just lurking around...",
                      usage="lurk (@user)",)
    async def lurk(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} lurked at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is lurking"

        footer = f"{action_to} was lurked at {receive} times and lurked at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["MARRY"],
                      desc="Marries someone",
                      usage="marry (@user)",)
    async def marry(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} married {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} wants to tie the knot"

        footer = f"{action_to} was married {receive} times and married others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["MISS"],
                      desc="You miss someone",
                      usage="miss (@user)",)
    async def miss(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} missed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} misses their friends"

        footer = f"{action_to} was missed {receive} times and missed others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["NERVOUS"],
                      desc="You're nervous",
                      usage="nervous (@user)",)
    async def nervous(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_to} made {action_by} nervous"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is nervous"

        footer = f"{action_to} was nervous {receive} times and made others nervous {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["NO"],
                      desc="No",
                      usage="no (@user)",)
    async def no(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)
        no_list = ['disagreed', 'no likey', "doesn't like that", "didn't vibe with that"]

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} said no to {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} {random.choice(no_list)}"

        footer = f"{action_to} was said no to {receive} times and said no to others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["NOM"],
                      desc="Nom nom nom",
                      usage="nom (@user)",)
    async def nom(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} nommed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} nommed themself"

        footer = f"{action_to} was nommed {receive} times and nommed others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["NUZZLE"],
                      desc="Nuzzles someone",
                      usage="nuzzle (@user)",)
    async def nuzzle(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} nuzzled {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} nuzzled themself"

        footer = f"{action_to} was nuzzled {receive} times and nuzzled others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["PANIC"],
                      desc="You're panicking!!!!!!!!!1",
                      usage="panic (@user)",)
    async def panic(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} panicked {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is panicking"

        footer = f"{action_to} was panicked {receive} times and panicked others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["PAT"],
                      desc="Pats someone",
                      usage="pat (@user)",)
    async def pat(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} pat {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} pat themself"

        footer = f"{action_to} was pat {receive} times and pat others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["PECK"],
                      desc="Pecks someone",
                      usage="peck (@user)",)
    async def peck(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} pecked {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} pecked themself"

        footer = f"{action_to} was pecked {receive} times and pecked others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["POKE"],
                      desc="Pokes someone",
                      usage="poke (@user)",)
    async def poke(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} poked {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} poked themself"

        footer = f"{action_to} was poked {receive} times and poked others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["POUT"],
                      desc="Pouts at someone",
                      usage="pout (@user)",)
    async def pout(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} pouted at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is pouting"

        footer = f"{action_to} was pouted at {receive} times and pouted at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["PUNT"],
                      desc="Punts someone",
                      usage="punt (@user)",)
    async def punt(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} punted {action_to}"
        footer = f"{action_to} was punted {receive} times and punted others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["RUN"],
                      desc="Runs from someone",
                      usage="run (@user)",)
    async def run(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} ran from {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is running"

        footer = f"{action_to} was ran from {receive} times and ran from others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["RACE"],
                      desc="Race someone",
                      usage="race (@user)",)
    async def race(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} raced with {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} wants to race"

        footer = f"{action_to} was raced with {receive} times and raced with others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["SAD"],
                      desc="You're sad :(",
                      usage="sad (@user)",)
    async def sad(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} saddened {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is sad"

        footer = f"{action_to} was saddened {receive} times and saddened others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["SHOOT"],
                      desc="Shoots someone",
                      usage="shoot (@user)",)
    async def shoot(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} shot {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is shooting aimlessly"

        footer = f"{action_to} was shot {receive} times and shot others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["SHRUG"],
                      desc="Shrugs at someone",
                      usage="shrug (@user)",)
    async def shrug(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} shrugged at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is shrugging"

        footer = f"{action_to} was shrugged at {receive} times and shrugged at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["SIP"],
                      desc="Take a sip",
                      usage="sip (@user)",)
    async def sip(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} sipped {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is sipping"

        footer = f"{action_to} was sipped {receive} times and sipped others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["SLAP"],
                      desc="Slaps someone",
                      usage="slap (@user)",)
    async def slap(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} slapped {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} slapped themself"

        footer = f"{action_to} was slapped {receive} times and slapped others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["SLEEP"],
                      desc="Counting sheep...",
                      usage="sleep (@user)",)
    async def sleep(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} made {action_to} fall asleep"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is sleeping"

        footer = f"{action_to} was made to sleep {receive} times and made others sleep {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["SLICE"],
                      desc="Slices someone",
                      usage="slice (@user)",)
    async def slice(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} sliced {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} sliced themself"

        footer = f"{action_to} was sliced {receive} times and sliced others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["SMUG"],
                      desc="You think you're cool, huh?",
                      usage="smug (@user)",)
    async def smug(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} was smug to {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} has a smug face on"

        footer = f"{action_to} was smug {receive} times and was smug to others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["STAB"],
                      desc="Stabs someone",
                      usage="stab (@user)",)
    async def stab(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} stabbed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} stabbed themself"

        footer = f"{action_to} was stabbed {receive} times and stabbed others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["STARE"],
                      desc="Stares at someone",
                      usage="stare (@user)",)
    async def stare(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} stared at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is staring"

        footer = f"{action_to} was stared at {receive} times and stared at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["TACKLE"],
                      desc="Tackles someone",
                      usage="tackle (@user)",)
    async def tackle(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
        else:
            action_by = ctx.me.display_name
            action_to = ctx.author.display_name

        title = f"{action_by} tackled {action_to}"
        footer = f"{action_to} was tackled {receive} times and tackled others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["TAP"],
                      desc="Taps someone",
                      usage="tap (@user)",)
    async def tap(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            body = objects.get_random_body_part()
            title = f"{action_by} tapped {action_to} on their {body}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} tapped themself"

        footer = f"{action_to} was tapped {receive} times and tapped others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["TASTE"],
                      desc="Test taster",
                      usage="taste (@user)",)
    async def taste(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} tasted {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} tasted themself"

        footer = f"{action_to} was tasted {receive} times and tasted others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["TALK"],
                      desc="Talks to someone",
                      usage="talk (@user)",)
    async def talk(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} talked to {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is talking"

        footer = f"{action_to} was talked with {receive} times and talked with others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["TAUNT"],
                      desc="Show me your moves",
                      usage="taunt (@user)",)
    async def taunt(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} taunted at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is taunting"

        footer = f"{action_to} was taunted at {receive} times and taunted at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["TEASE"],
                      desc="Teases someone",
                      usage="tease (@user)",)
    async def tease(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} teased {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is teasing"

        footer = f"{action_to} was teased {receive} times and teased others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["THANK"],
                      desc="Thanks someone",
                      usage="thank (@user)",)
    async def thank(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        adjlist = ['thankful', 'grateful', 'appreciative']

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} thanked {action_to}"
        else:
            action_to = ctx.author.display_name
            adj = random.choice(adjlist)
            title = f"{action_to} is feeling {adj}"

        footer = f"{action_to} was thanked {receive} times and thanked others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["THINK"],
                      desc="You're thinking...",
                      usage="think (@user)",)
    async def think(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} thought about {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is thinking"

        footer = f"{action_to} was thought about {receive} times and thought about others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["THROW"],
                      desc="Throws random stuff at someone",
                      usage="throw (@user)",)
    async def throw(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} threw {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is throwing {objects.get_random_object()}"

        footer = f"{action_to} had stuff thrown at them {receive} times and threw stuff at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["THUMBSDOWN"],
                      desc="Gives someone a thumbs down",
                      usage="thumbsdown (@user)",)
    async def thumbsdown(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} gave {action_to} a thumbs down"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is giving a thumbs down"

        footer = f"{action_to} was given a thumbs down {receive} times and gave others a thumbs down {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["THUMBSUP"],
                      desc="Gives someone a thumbs up",
                      usage="thumbsup (@user)",)
    async def thumbsup(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} gave {action_to} a thumbs up"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is giving a thumbs up"

        footer = f"{action_to} was given a thumbs up {receive} times and gave others a thumbs up {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["TICKLE"],
                      desc="Tickles someone",
                      usage="tickle (@user)",)
    async def tickle(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} tickled {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} tickled themself"

        footer = f"{action_to} was tickled {receive} times and tickled others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["TOUCH"],
                      desc="Touches someone",
                      usage="touch (@user)",)
    async def touch(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} touched {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} touched themself"

        footer = f"{action_to} was touched {receive} times and touched others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["TRASH"],
                      desc="Absolutely dumpster someone",
                      usage="trash (@user)",)
    async def trash(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} trashed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} trashed themself"

        footer = f"{action_to} was trashed {receive} times and trashed others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["UPSET"],
                      desc="You're upset",
                      usage="upset (@user)",)
    async def upset(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} upset {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is upset"

        footer = f"{action_to} was upset {receive} times and upset others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["WAG"],
                      desc="No furries",
                      usage="wag (@user)",)
    async def wag(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} wagged at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is wagging their tail"

        footer = f"{action_to} was wagged at {receive} times and wagged at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["WAIT"],
                      desc="Give me a minute...",
                      usage="wait (@user)",)
    async def wait(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} waited for {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is waiting"

        footer = f"{action_to} was waited for {receive} times and waited for others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["WAKEUP"],
                      desc="Wakes someone up",
                      usage="wakeup (@user)",)
    async def wakeup(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} woke {action_to} up"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} woke up"

        footer = f"{action_to} was woken up {receive} times and woke up others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["WASH"],
                      desc="Washes someone",
                      usage="wash (@user)",)
    async def wash(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} washed {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} washed themself"

        footer = f"{action_to} was washed {receive} times and washed others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["WAVE"],
                      desc="Waves at someone",
                      usage="wave (@user)",)
    async def wave(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} waved at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is waving"

        footer = f"{action_to} was waved at {receive} times and waved at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["WHINE"],
                      desc="I don't wanna eat my vegetables",
                      usage="whine (@user)",)
    async def whine(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} whined at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is whining"

        footer = f"{action_to} was whined at {receive} times and whined at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["WHISPER"],
                      desc="Whisper to someone",
                      usage="whisper (@user)",)
    async def whisper(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} whispered to {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is whispering"

        footer = f"{action_to} was whispered to {receive} times and whispered to others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["WINK"],
                      desc="Wink at someone",
                      usage="wink (@user)",)
    async def wink(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} winked at {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is winking"

        footer = f"{action_to} was winked at {receive} times and winked at others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["WORRY"],
                      desc="Worry about someone",
                      usage="worry (@user)",)
    async def worry(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} worried about {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} is worrying"

        footer = f"{action_to} was worried about {receive} times and worried about others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)

    @commands.command(aliases=["YES"],
                      desc="Yes",
                      usage="yes (@user)",)
    async def yes(self, ctx, user=None):
        give, receive, user, info = await self.get_count_user(ctx, user)
        no_list = ['agreed', 'likey', "likes that", "vibed with that"]

        if info:
            action_by = ctx.author.display_name
            action_to = user.display_name
            title = f"{action_by} said yes to {action_to}"
        else:
            action_to = ctx.author.display_name
            title = f"{action_to} {random.choice(no_list)}"

        footer = f"{action_to} was said yes to {receive} times and said yes to others {give} times"

        return await self.embed_template(ctx, title=title, footer=footer)


def setup(bot):
    bot.add_cog(Actions(bot))
