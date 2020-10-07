import asyncio
import os
import random
import typing

import aiohttp
import discord
from discord.ext import commands
from discord.ext.commands import CommandInvokeError
from utils import globalcommands

gcmds = globalcommands.GlobalCMDS()
SLEEP_TIME = 1.2
FUNNY_URL = "https://thumbs.gfycat.com/MisguidedPreciousIguanodon-size_restricted.gif"
FUNNY_FOOTER = "Taken directly from Hubble"


class Fun(commands.Cog):

    def __init__(self, bot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)

    async def imageSend(self, ctx, path, url=None, toSend: str = ""):
        if not url:
            with open(f"{path}/{random.choice(os.listdir(path))}", "rb") as bin_file:
                picture = discord.File(bin_file, filename="image.png")
            embed = discord.Embed(title=f"{path[2:].title()} {toSend}", color=discord.Color.blue())
            embed.set_image(url=f"attachment://image.png")
            return await ctx.channel.send(file=picture, embed=embed)
        else:
            embed = discord.Embed(title=f"{path} {toSend}", color=discord.Color.blue())
            embed.set_image(url=url)
            return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['dailyastro'],
                      desc="Shows today's NASA Astronomy Photo of the Day",
                      usage="apod")
    async def apod(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY") as returned:
                result = await returned.json()
        embed = discord.Embed(title=result.get('title', ''), color=discord.Color.blue())
        embed.set_author(name=f"NASA Astronomy Photo of the Day {result.get('date', '').replace('-', '/')}")
        embed.set_footer(text=result.get('explanation', FUNNY_FOOTER))
        embed.set_image(url=result.get('hdurl', FUNNY_URL))
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['dad', 'father'],
                      desc="Makes MarwynnBot say a super funny dad joke",
                      usage="dadjoke",)
    async def dadjoke(self, ctx):
        async with aiohttp.ClientSession(headers={"Accept": "application/json"}) as session:
            async with session.get("https://icanhazdadjoke.com/") as returned:
                result = await returned.json()
        embed = discord.Embed(description=result['joke'],
                              color=discord.Color.blue())
        embed.set_author(name=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['8ball', '8b'],
                      desc="MarwynnBot predicts the future with a Magic 8 Ball!",
                      usage="eightball [question]")
    async def eightball(self, ctx, *, question):
        with open('responses', 'r') as f:
            responses = f.readlines()
        embed = discord.Embed(title='Magic 8 Ball 🎱', color=discord.colour.Color.blue())
        embed.set_thumbnail(url="https://www.horoscope.com/images-US/games/game-magic-8-ball-no-text.png")
        embed.add_field(name='Question', value=f"{ctx.message.author.mention}: " + question, inline=True)
        embed.add_field(name='Answer', value=f'{random.choice(responses)}', inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=['affirm'],
                      desc="MarwynnBot delivers some words of encouragement!",
                      usage="encourage")
    async def encourage(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.affirmations.dev/") as returned:
                result = await returned.json()
        embed = discord.Embed(title="Affirmation",
                              description=f"{ctx.author.mention}\n```\n{result['affirmation']}\n```",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="MarwynnBot chooses between some choices",
                      usage="choose [choices]",
                      note="`[choices]` must be separated by \" or \"")
    async def choose(self, ctx, *, choices: str):
        chooseEmbed = discord.Embed(title='Choose One',
                                    color=discord.Color.blue())
        chooseEmbed.add_field(name=f'{ctx.author} asked: {choices}',
                              value=random.choice(choices.replace("?", "").split(" or ")))
        await ctx.channel.send(embed=chooseEmbed)

    @commands.command(aliases=['gifsearch', 'searchgif', 'searchgifs', 'gif', 'gifs', 'tenor'],
                      desc="Fetches gifs from Tenor",
                      usage="gifsearch (amount) [query]",)
    async def gifSearch(self, ctx, toSend: typing.Optional[int] = 1, *, query: str):
        api_key = gcmds.env_check("TENOR_API")
        if not api_key:
            title = "Missing API Key"
            description = "Insert your Tenor API Key in the `.env` file"
            color = discord.Color.red()
            embed = discord.Embed(title=title,
                                  description=description,
                                  color=color)
            return await ctx.channel.send(embed=embed)

        url = "https://api.tenor.com/v1/random?q=%s&key=%s&limit=%s" % (query, api_key, toSend if toSend <= 50 else 50)
        path = f"{query} from Tenor"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                results = await r.json()
        if r.status == 200 or r.status == 202:
            getURL = [results['results'][i]['media'][0]['gif']['url'] for i in range(len(results['results']))]
            for counter in range(toSend):
                url = random.choice(getURL)
                await self.imageSend(ctx, path, url=url, toSend=f"[{counter + 1}/{toSend}]" if toSend != 1 else "")
                await asyncio.sleep(SLEEP_TIME)
            return
        elif r.status == 429:
            title = "Error Code 429"
            description = "**HTTP ERROR:** Rate limit exceeded. Please try again in about 30 seconds"
            color = discord.Color.dark_red()
        elif 300 <= r.status < 400:
            title = f"Error Code {r.status}"
            description = "**HTTP ERROR:** Redirect"
            color = discord.Color.dark_red()
        elif r.status == 404:
            title = "Error Code 404"
            description = "**HTTP ERROR:** Not found - bad resource"
            color = discord.Color.dark_red()
        elif 500 <= r.status < 600:
            title = f"Error Code {r.status}"
            description = "**HTTP ERROR:** Unexpected server error"
            color = discord.Color.dark_red()

        embed = discord.Embed(title=title,
                              description=description,
                              color=color)

        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['imgur', 'imgursearch'],
                      desc="Fetches images from Imgur",
                      usage="imgursearch (amount) [query]")
    async def imgurSearch(self, ctx, toSend: typing.Optional[int] = None, *, query: str):
        bot_id = gcmds.env_check("IMGUR_API")
        if not bot_id:
            title = "Missing Client ID"
            description = "Insert your Imgur Client ID in the `.env` file"
            color = discord.Color.red()
            embed = discord.Embed(title=title,
                                  description=description,
                                  color=color)
            return await ctx.channel.send(embed=embed)

        path = f"{query} from Imgur"
        reqURL = f"https://api.imgur.com/3/gallery/search/?q_all={query}"
        headers = {'Authorization': f'Client-ID {bot_id}'}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(reqURL) as result:
                results = await result.json()

        images = []
        data = int(len(results['data']))

        if result.status == 200:
            for i in range(data):
                if "false" != str(results['data'][i]['nsfw']):
                    try:
                        for j in range(len(results['data'][i]['images'])):
                            if ".mp4" not in str(results['data'][i]['images'][j]['link']):
                                images.append(str(results['data'][i]['images'][j]['link']))
                    except KeyError:
                        images.append(str(results['data'][i]['link']))
        if not images:
            none = discord.Embed(title="No Images Found",
                                 description=f"{ctx.author.mention},there were no images that matched your query: `{query}`",
                                 color=discord.Color.dark_red())
            return await ctx.channel.send(embed=none)
        for counter in range(toSend):
            url = random.choice(images)
            await self.imageSend(ctx, path, url=url, toSend=f"[{counter + 1}/{toSend}]" if toSend != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['isabellepic', 'isabelleemote', 'belle', 'bellepic', 'belleemote'],
                      desc="Fetches pictures of Isabelle from Animal Crossing",
                      usage="isabelle (amount)")
    async def isabelle(self, ctx, toSend: typing.Optional[int] = 1):
        path = "./isabelle"
        for counter in range(toSend):
            await self.imageSend(ctx, path, toSend=f"[{counter + 1}/{toSend}]" if toSend != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['peppapic', 'ppic', 'ppig'],
                      desc="Fetches pictures of Peppa Pig",
                      usage="peppa (amount)")
    async def peppa(self, ctx, toSend: typing.Optional[int] = 1):
        path = "./peppa"
        for counter in range(toSend):
            await self.imageSend(ctx, path, toSend=f"[{counter + 1}/{toSend}]" if toSend != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['randomcat', 'cat'],
                      desc="Fetches pictures of cats!",
                      usage="randomcat (amount)")
    async def randomCat(self, ctx, toSend: typing.Optional[int] = 1):
        api_key = gcmds.env_check("CAT_API")
        if not api_key:
            title = "Missing API Key"
            description = "Insert your TheCatAPI Key in the `.env` file"
            color = discord.Color.red()
            embed = discord.Embed(title=title,
                                  description=description,
                                  color=color)
            return await ctx.channel.send(embed=embed)

        path = "cat"
        headers = {"x-api-key": api_key}
        if toSend > 50:
            toSend = 50
        for counter in range(toSend):
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get("https://api.thecatapi.com/v1/images/search") as image:
                    response = await image.json()
                    url = response[0]['url']
            await self.imageSend(ctx, path, url=url, toSend=f"[{counter + 1}/{toSend}]" if toSend != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['woof', 'dog', 'doggo', 'randomdog'],
                      desc="Fetches pictures of dogs!",
                      usage="randomdog (amount)")
    async def randomDog(self, ctx, toSend: typing.Optional[int] = 1):
        req_url = f"https://dog.ceo/api/breeds/image/random/{toSend}"
        path = "dog"

        for counter in range(toSend):
            async with aiohttp.ClientSession() as session:
                async with session.get(req_url) as image:
                    response = await image.json()
                    url = response["message"]
            await self.imageSend(ctx, path, url=url, toSend=f"[{counter + 1}/{toSend}]" if toSend != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(desc="Make MarwynnBot say anything",
                      usage="say [message]")
    async def say(self, ctx, *, args):
        sayEmbed = discord.Embed(description=args,
                                 color=discord.Color.blue())
        await ctx.channel.send(embed=sayEmbed)

    @commands.command(aliases=['toadpic', 'toademote'],
                      desc="Fetches picture of Toad from Super Mario",
                      usage="toad (amount)")
    async def toad(self, ctx, toSend: typing.Optional[int] = 1):
        path = "./toad"
        for counter in range(toSend):
            await self.imageSend(ctx, path, toSend=f"[{counter + 1}/{toSend}]" if toSend != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(desc="Make MarwynnBot say anything, but in text to speech",
                      usage="tts [message]")
    async def tts(self, ctx, *, args):
        return await ctx.channel.send(content=args, tts=True)


def setup(bot):
    bot.add_cog(Fun(bot))
