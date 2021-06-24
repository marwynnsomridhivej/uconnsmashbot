from io import BytesIO
from typing import NamedTuple
from urllib.parse import quote

import discord
from aiohttp.client import ClientSession
from discord.ext import commands
from utils import GlobalCMDS, customerrors

LATEX_URL = "https://latex.codecogs.com/gif.download?%5Cbg_white%20%5Clarge%20"
NEWTON_URL = "https://newton.now.sh/api/v2/{}/{}"


class NewtonResult(NamedTuple):
    operation: str
    expression: str
    result: str


class Math(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.client_session: ClientSession = ClientSession()
        self.gcmds = GlobalCMDS(self.bot)

    def cog_unload(self):
        self.bot.loop.create_task(self.client_session.close())

    @commands.command(desc="Renders image given a latex string",
                      usage="latex [equation]",
                      note="Most, but not all latex formatting is supported")
    async def latex(self, ctx, *, eq: str):
        cleaned = await commands.clean_content().convert(ctx, eq)
        raw_eq = r"{}".format(cleaned)
        url_eq = quote(raw_eq)

        result = await self.client_session.get(LATEX_URL + url_eq)
        img = await result.read()

        if not 200 <= result.status < 300:
            raise customerrors.InvalidExpression(eq)

        output_img = discord.File(fp=BytesIO(img), filename="latex_eq.png")
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_author(name=f"Requested by: {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        embed.set_image(url="attachment://latex_eq.png")
        return await ctx.channel.send(file=output_img, embed=embed)


def setup(bot):
    bot.add_cog(Math(bot))
