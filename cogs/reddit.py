import random
from datetime import datetime

import discord
import praw
from discord.ext import commands
from utils import globalcommands

gcmds = globalcommands.GlobalCMDS()


class Reddit(commands.Cog):

    def __init__(self, bot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)

    async def get_id_secret(self, ctx):
        client_id = gcmds.env_check("REDDIT_CLIENT_ID")
        client_secret = gcmds.env_check("REDDIT_CLIENT_SECRET")
        user_agent = gcmds.env_check("USER_AGENT")
        if not all([client_id, client_secret, user_agent]):
            title = "Missing Reddit Client ID or Client Secret or User Agent"
            description = "Insert your Reddit Client ID, Client Secret, and User Agent in the `.env` file"
            embed = discord.Embed(title=title,
                                  description=description,
                                  color=discord.Color.dark_red())
            await ctx.channel.send(embed=embed)
        return client_id, client_secret, user_agent

    async def embed_template(self, ctx):
        client_id, client_secret, user_agent = await self.get_id_secret(ctx)

        if not all([client_id, client_secret, user_agent]):
            return

        reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)
        picture_search = reddit.subreddit(ctx.command.name).hot()

        submissions = []

        for post in picture_search:
            if len(submissions) == 300:
                break
            elif (not post.stickied and not post.over_18) and not "https://v.redd.it/" in post.url:
                submissions.append(post)

        picture = random.choice(submissions)

        web_link = f"https://www.reddit.com/{picture.permalink}"
        author_url = f"https://www.reddit.com/user/{picture.author}/"
        author_icon_url = picture.author.icon_img
        real_timestamp = datetime.fromtimestamp(picture.created_utc).strftime("%d/%m/%Y %H:%M:%S")
        ratio = picture.upvote_ratio * 100
        sub_name = picture.subreddit_name_prefixed
        embed = discord.Embed(title=sub_name, url=web_link, color=discord.Color.blue())
        embed.set_author(name=picture.author, url=author_url, icon_url=author_icon_url)
        embed.set_image(url=picture.url)
        embed.set_footer(
            text=f"⬆️{picture.score}️ ({ratio}%)\n💬{picture.num_comments}\n🕑{real_timestamp}\n"
                 f"Copyrights belong to their respective owners")
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['reddithelp'],
                      desc="Displays the help command for reddit",
                      usage="reddit (subreddit)",
                      note="Valid subreddit names are listed in the help command")
    async def reddit(self, ctx, cmdName=None):
        CMDNAMES = [command.name for command in self.get_commands() if command.name != "reddit"]
        description = f"Do `{await gcmds.prefix(ctx)}reddit [cmdName]` to get the usage of that particular " \
                      f"command.\n\n**List of all {len(CMDNAMES)} reddit commands:**\n\n `{'` `'.join(sorted(CMDNAMES))}` "
        if not cmdName or cmdName == "reddit":
            helpEmbed = discord.Embed(title="Reddit Commands Help",
                                      description=description,
                                      color=discord.Color.blue())
        else:
            if cmdName in CMDNAMES:
                r_command = cmdName.capitalize()
                helpEmbed = discord.Embed(title=f"{r_command}",
                                          description=f"Returns a randomly selected image from the subreddit r/{cmdName}",
                                          color=discord.Color.blue())
                helpEmbed.add_field(name="Usage",
                                    value=f"`{await gcmds.prefix(ctx)}{cmdName}`",
                                    inline=False)
                aliases = self.bot.get_command(name=cmdName).aliases
                if aliases:
                    value = "`" + "` `".join(sorted(aliases)) + "`"
                    helpEmbed.add_field(name="Aliases", value=value, inline=False)
            else:
                helpEmbed = discord.Embed(title="Command Not Found",
                                          description=f"{ctx.author.mention}, {cmdName} is not a valid reddit command",
                                          color=discord.Color.blue())
        return await ctx.channel.send(embed=helpEmbed)

    @commands.command(aliases=['abj', 'meananimals'])
    async def animalsbeingjerks(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['anime'])
    async def awwnime(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['car', 'cars', 'carpics'])
    async def carporn(self, ctx):
        return await self.embed_template(ctx)

    @commands.command()
    async def cosplay(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['earth', 'earthpics'])
    async def earthporn(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['food', 'foodpics'])
    async def foodporn(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['animemes'])
    async def goodanimemes(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['history', 'historypics'])
    async def historyporn(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['pic', 'itap'])
    async def itookapicture(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['map', 'maps', 'mappics'])
    async def mapporn(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['interesting', 'mi'])
    async def mildlyinteresting(self, ctx):
        return await self.embed_template(ctx)

    @commands.command()
    async def pareidolia(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['ptiming'])
    async def perfecttiming(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['psbattle'])
    async def photoshopbattles(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['quotes'])
    async def quotesporn(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['room', 'rooms', 'roompics'])
    async def roomporn(self, ctx):
        return await self.embed_template(ctx)

    @commands.command()
    async def tumblr(self, ctx):
        return await self.embed_template(ctx)

    @commands.command()
    async def unexpected(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['wallpaper'])
    async def wallpapers(self, ctx):
        return await self.embed_template(ctx)

    @commands.command(aliases=['woah'])
    async def woahdude(self, ctx):
        return await self.embed_template(ctx)


def setup(bot):
    bot.add_cog(Reddit(bot))
