import os
from typing import List
from urllib.parse import urlencode

import aiohttp
import discord
from bs4 import BeautifulSoup
from discord.ext.commands import Context


_API_BASE = "https://api.genius.com"
_TOO_LONG = lambda e, n, v: len(e) + len(n) + len(v) > 6000 or len(e.fields) == 25


async def _get_lyrics_url(title: str) -> str:
    query_string = urlencode({"q": title})
    async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {os.getenv('GENIUS_TOKEN')}"}) as sesh:
        async with sesh.get(url=f"{_API_BASE}/search?{query_string}") as res:
            data = await res.json()
    if data.get("meta", None) and data["meta"]["status"] == 200:
        for entry in data["response"]["hits"]:
            try:
                if entry["type"] == "song":
                    return entry["result"]["url"]
            except KeyError:
                pass
    else:
        return None


async def get_lyrics(title: str) -> List[str]:
    url = await _get_lyrics_url(title)
    try:
        if url:
            async with aiohttp.ClientSession() as sesh:
                async with sesh.get(url) as res:
                    page = await res.read()
            res: str = BeautifulSoup(page, "html.parser").find("div", class_="lyrics").get_text()
            if res.startswith("\n\n"):
                res = res[2:]
            if res.endswith("\n\n"):
                res = res[:-2]
            lyrics = res.split("\n\n")
        else:
            lyrics = None
    except AttributeError:
        lyrics = None
    return lyrics


async def get_lyrics_embed(ctx: Context, title: str) -> None:
    lyrics = await get_lyrics(title)
    embeds: List[discord.Embed] = []
    _NONE_FOUND = discord.Embed(
        title="No Lyrics Found",
        description=f"{ctx.author.mention}, I could not find any lyrics for `{title}`",
        color=discord.Color.dark_red(),
    )
    embed = discord.Embed(
        title=f"Lyrics for: {title.title()}",
        color=discord.Color.blue(),
    )
    if lyrics:
        try:
            for section in lyrics:
                _, value = [_ for _ in section.split("]\n", maxsplit=1)]
                name = _ + "]"
                if _TOO_LONG(embed, name, value):
                    embeds.append(embed)
                    embed = discord.Embed(
                        color=discord.Color.blue(),
                    )
                embed.add_field(
                    name=name,
                    value=value,
                    inline=False,
                )
            embeds.append(embed)
        except ValueError:
            embeds.append(_NONE_FOUND)
    else:
        embeds.append(_NONE_FOUND)
    for index, embed in enumerate(embeds, 1):
        embed.set_footer(
            text=f"{index} / {len(embeds)}\nRequested by {ctx.author.display_name}",
            icon_url=ctx.author.avatar_url,
        )
        await ctx.channel.send(embed=embed)
