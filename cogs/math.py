from io import BytesIO
from urllib.parse import quote

import aiohttp
import discord
import sympy
from discord.ext import commands
from utils import customerrors, globalcommands, paginator

gcmds = globalcommands.GlobalCMDS()
LATEX_URL = "https://latex.codecogs.com/gif.download?%5Cbg_white%20%5Clarge%20"


class Math(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)

    @commands.command(desc="Renders image given a latex string",
                      usage="latex [equation]",
                      note="Most, but not all latex formatting is supported")
    async def latex(self, ctx, *, eq: str):
        cleaned = await commands.clean_content().convert(ctx, eq)
        raw_eq = r"{}".format(cleaned)
        url_eq = quote(raw_eq)

        async with aiohttp.ClientSession() as session:
            async with session.get(LATEX_URL + url_eq) as result:
                img = await result.read()

        if not 200 <= result.status < 300:
            raise customerrors.InvalidExpression(eq)

        output_img = discord.File(fp=BytesIO(img), filename="latex_eq.png")
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_author(name=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        embed.set_image(url="attachment://latex_eq.png")
        return await ctx.channel.send(file=output_img, embed=embed)


def setup(bot):
    bot.add_cog(Math(bot))
