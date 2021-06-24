import asyncio
import os
import random
import typing
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands, tasks
from discord.ext.commands import AutoShardedBot, Context
from utils import GlobalCMDS

gcmds = GlobalCMDS()
SLEEP_TIME = 1.2
FUNNY_URL = "https://thumbs.gfycat.com/MisguidedPreciousIguanodon-size_restricted.gif"
FUNNY_FOOTER = "Taken directly from Hubble"


def fix_to_send(to_send: int):
    return 1 if to_send < 1 else 50 if to_send > 50 else to_send


class Fun(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        global gcmds
        self.bot = bot
        self.bot.loop.create_task(self._init_delay_tables())
        self.bot.loop.create_task(self._schedule_send())
        self._tasks: typing.List[asyncio.Task] = []
        self._delay_fut = self.bot.loop.create_future()
        gcmds = GlobalCMDS(self.bot)

    async def _init_delay_tables(self) -> None:
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute(
                "CREATE TABLE IF NOT EXISTS delays(channel_id bigint, content TEXT, tts BOOLEAN DEFAULT FALSE, send_at NUMERIC)"
            )
        self._delay_fut.set_result(True)

    async def _get_delay(self, ctx: Context) -> int:
        await ctx.channel.send(
            embed=discord.Embed(
                title="Delay",
                description=f"{ctx.author.mention}, what should the delay be? Please specify in either "
                "HH:MM:SS, MM:SS, or SS format",
                color=discord.Color.blue(),
            )
        )
        try:
            message: discord.Message = await self.bot.wait_for("message", check=lambda m: m.channel == ctx.channel and m.author.id == ctx.author.id, timeout=300)
            _split = [int(_) for _ in str(message.content).split(":", maxsplit=2)]
            if len(_split) == 3:
                delay = 3600 * _split[0] + 60 * _split[1] + _split[2]
            elif len(_split) == 2:
                delay = 60 * _split[0] + _split[1]
            else:
                delay = _split[0]
        except (asyncio.TimeoutError, Exception):
            delay = 0
        if delay < 0:
            delay = 0
        return delay

    async def _send_in(self, channel: discord.TextChannel, content: str, delay: int, tts: bool = False) -> None:
        delay = int(datetime.now().timestamp()) + delay
        async with self.bot.db.acquire() as con:
            await con.execute(
                "INSERT INTO delays(channel_id, content, tts, send_at) VALUES "
                f"({channel.id}, $text${content}$text$, {tts}, {delay})"
            )
        task = self.bot.loop.create_task(
            self._wrapper(
                channel, content, tts, delay
            )
        )
        task.add_done_callback(self._handle_task)
        self._tasks.append(task)

    async def _schedule_send(self) -> None:
        await self._delay_fut
        async with self.bot.db.acquire() as con:
            entries = await con.fetch(f"SELECT * FROM delays")
            await con.execute(f"DELETE FROM delays WHERE send_at<{int(datetime.now().timestamp())}")
        for entry in entries:
            channel: discord.TextChannel = self.bot.get_channel(int(entry["channel_id"]))
            if channel:
                task = self.bot.loop.create_task(self._wrapper(
                    channel, entry["content"], entry["tts"], int(entry["send_at"])))
                task.add_done_callback(self._handle_task)
                self._tasks.append(task)

    async def _wrapper(self, channel: discord.TextChannel, content: str, tts: bool, delay: int) -> discord.Message:
        await asyncio.sleep(delay - int(datetime.now().timestamp()))
        async with self.bot.db.acquire() as con:
            await con.execute(
                f"DELETE FROM delays WHERE channel_id={channel.id} AND content=$text${content}$text$ AND tts={tts} AND send_at={delay}"
            )
        return await channel.send(
            embed=discord.Embed(description=content, color=discord.Color.blue()),
            tts=tts,
        )

    @staticmethod
    def _handle_task(task: asyncio.Task) -> None:
        try:
            task.result()
        except (asyncio.CancelledError, Exception):
            pass

    @staticmethod
    def _get_delta(delay: int) -> str:
        delta = []
        hours, seconds = divmod(delay, 3600)
        if hours:
            delta.append(f"{hours} hour{'s' if hours != 1 else ''}")
        minutes, seconds = divmod(seconds, 60)
        if minutes:
            delta.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds:
            delta.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        if not delta:
            delta.append("0 seconds")
        return " ".join(delta)

    def cog_unload(self):
        for task in self._tasks:
            task.cancel()

    async def send_image(self, ctx: Context, path, url=None, to_send: str = ""):
        if not url:
            with open(f"./assets/{path}/{random.choice(os.listdir(f'./assets/{path}'))}", "rb") as bin_file:
                picture = discord.File(bin_file, filename="image.png")
            embed = discord.Embed(title=f"{path.title()} {to_send}", color=discord.Color.blue())
            embed.set_image(url=f"attachment://image.png")
            return await ctx.channel.send(file=picture, embed=embed)
        else:
            embed = discord.Embed(title=f"{path.title()} {to_send}", color=discord.Color.blue())
            embed.set_image(url=url)
            return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['dailyastro'],
                      desc="Shows today's NASA Astronomy Photo of the Day",
                      usage="apod")
    async def apod(self, ctx: Context):
        api_key = gcmds.env_check("NASA_API") or "DEMO_KEY"
        today = datetime.today().strftime("%Y-%m-%d")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.nasa.gov/planetary/apod?api_key={api_key}&date={today}") as returned:
                result = await returned.json()
        embed = discord.Embed(title=result.get('title', ''), color=discord.Color.blue())
        embed.set_author(name=f"NASA Astronomy Photo of the Day {result.get('date', '').replace('-', '/')}")
        embed.set_footer(text=result.get('explanation', FUNNY_FOOTER))
        embed.set_image(url=result.get('hdurl', FUNNY_URL))
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['dad', 'father'],
                      desc="Makes UconnSmashBot say a super funny dad joke",
                      usage="dadjoke",)
    async def dadjoke(self, ctx: Context):
        async with aiohttp.ClientSession(headers={"Accept": "application/json"}) as session:
            async with session.get("https://icanhazdadjoke.com/") as returned:
                result = await returned.json()
        embed = discord.Embed(description=result['joke'],
                              color=discord.Color.blue())
        embed.set_author(name=f"Requested by: {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['8ball', '8b'],
                      desc="UconnSmashBot predicts the future with a Magic 8 Ball!",
                      usage="eightball [question]")
    async def eightball(self, ctx: Context, *, question):
        with open('responses', 'r') as f:
            responses = f.readlines()
        embed = discord.Embed(title='Magic 8 Ball 🎱', color=discord.colour.Color.blue())
        embed.set_thumbnail(url="https://www.horoscope.com/images-US/games/game-magic-8-ball-no-text.png")
        embed.add_field(name='Question', value=f"{ctx.message.author.mention}: " + question, inline=True)
        embed.add_field(name='Answer', value=f'{random.choice(responses)}', inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=['affirm'],
                      desc="UconnSmashBot delivers some words of encouragement!",
                      usage="encourage")
    async def encourage(self, ctx: Context):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.affirmations.dev/") as returned:
                result = await returned.json()
        embed = discord.Embed(title="Affirmation",
                              description=f"{ctx.author.mention}\n```\n{result['affirmation']}\n```",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="UconnSmashBot chooses between some choices",
                      usage="choose [choices]",
                      note="`[choices]` must be separated by \" or \"")
    async def choose(self, ctx: Context, *, choices: str):
        chooseEmbed = discord.Embed(title='Choose One',
                                    color=discord.Color.blue())
        chooseEmbed.add_field(name=f'{ctx.author} asked: {choices}',
                              value=random.choice(choices.replace("?", "").split(" or ")))
        await ctx.channel.send(embed=chooseEmbed)

    @commands.command(aliases=['gifsearch', 'searchgif', 'searchgifs', 'gif', 'gifs', 'tenor'],
                      desc="Fetches gifs from Tenor",
                      usage="gifsearch (amount) [query]",)
    async def gifSearch(self, ctx: Context, to_send: typing.Optional[int] = 1, *, query: str):
        api_key = gcmds.env_check("TENOR_API")
        if not api_key:
            title = "Missing API Key"
            description = "Insert your Tenor API Key in the `.env` file"
            color = discord.Color.dark_red()
            embed = discord.Embed(title=title, description=description, color=color)
            return await ctx.channel.send(embed=embed)

        to_send = fix_to_send(to_send)
        url = "https://api.tenor.com/v1/random?q=%s&key=%s&limit=%s" % (
            query, api_key, to_send if to_send <= 50 else 50)
        path = f"{query} from Tenor"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                results = await r.json()
        if r.status == 200 or r.status == 202:
            getURL = [results['results'][i]['media'][0]['gif']['url'] for i in range(len(results['results']))]
            for counter in range(to_send):
                url = random.choice(getURL)
                await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
                await asyncio.sleep(SLEEP_TIME)
            return
        elif r.status == 429:
            title = "Error Code 429"
            description = "**HTTP ERROR:** Rate limit exceeded. Please try again in about 30 seconds"
        elif 300 <= r.status < 400:
            title = f"Error Code {r.status}"
            description = "**HTTP ERROR:** Redirect"
        elif r.status == 404:
            title = "Error Code 404"
            description = "**HTTP ERROR:** Not found - bad resource"
        elif 500 <= r.status < 600:
            title = f"Error Code {r.status}"
            description = "**HTTP ERROR:** Unexpected server error"
        else:
            title = f"Error Code {r.status}"
            description = f"**HTTP ERROR:** An error occurred with code {r.status}"

        embed = discord.Embed(title=title, description=description, color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['imgur', 'imgursearch'],
                      desc="Fetches images from Imgur",
                      usage="imgursearch (amount) [query]")
    async def imgurSearch(self, ctx: Context, to_send: typing.Optional[int] = 1, *, query: str):
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
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            url = random.choice(images)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['isabellepic', 'isabelleemote', 'belle', 'bellepic', 'belleemote'],
                      desc="Fetches pictures of Isabelle from Animal Crossing",
                      usage="isabelle (amount)")
    async def isabelle(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "isabelle"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            await self.send_image(ctx, path, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['peppapic', 'ppic', 'ppig'],
                      desc="Fetches pictures of Peppa Pig",
                      usage="peppa (amount)")
    async def peppa(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "peppa"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            await self.send_image(ctx, path, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['pika'],
                      desc="Fetches pictures of Pikachu",
                      usage="pikachu (amount)")
    async def pikachu(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "pikachu"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            async with aiohttp.ClientSession() as session:
                async with session.get("https://some-random-api.ml/img/pikachu") as image:
                    response = await image.json()
                    url = response.get('link', FUNNY_URL)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['randombird', 'bird', 'birb'],
                      desc="Fetches random bird pics",
                      usage="randombird (amount)")
    async def randomBird(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "bird"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            async with aiohttp.ClientSession() as session:
                async with session.get("https://some-random-api.ml/img/birb") as image:
                    response = await image.json()
                    url = response.get('link', FUNNY_URL)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['randomcat', 'cat'],
                      desc="Fetches pictures of cats!",
                      usage="randomcat (amount)")
    async def randomCat(self, ctx: Context, to_send: typing.Optional[int] = 1):
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
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get("https://api.thecatapi.com/v1/images/search") as image:
                    response = await image.json()
                    url = response[0].get('url', FUNNY_URL)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['woof', 'dog', 'doggo', 'randomdog'],
                      desc="Fetches pictures of dogs!",
                      usage="randomdog (amount)")
    async def randomDog(self, ctx: Context, to_send: typing.Optional[int] = 1):
        to_send = fix_to_send(to_send)
        req_url = f"https://dog.ceo/api/breeds/image/random/{to_send}"
        path = "dog"
        async with aiohttp.ClientSession() as session:
            async with session.get(req_url) as image:
                response = await image.json()
                urls = response.get('message', FUNNY_URL)
        for counter, url in enumerate(urls):
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['randomfox', 'fox'],
                      desc="Fetches random fox pics",
                      usage="randomfox (amount)")
    async def randomFox(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "fox"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            async with aiohttp.ClientSession() as session:
                async with session.get("https://some-random-api.ml/img/fox") as image:
                    response = await image.json()
                    url = response.get('link', FUNNY_URL)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['randomkangaroo', 'kangaroo'],
                      desc="Fetches random kangaroo pics",
                      usage="randomkangaroo (amount)")
    async def randomKangaroo(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "kangaroo"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            async with aiohttp.ClientSession() as session:
                async with session.get("https://some-random-api.ml/img/kangaroo") as image:
                    response = await image.json()
                    url = response.get('link', FUNNY_URL)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['randomkoala', 'koala'],
                      desc="Fetches random koala pics",
                      usage="randomkoala (amount)")
    async def randomKoala(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "koala"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            async with aiohttp.ClientSession() as session:
                async with session.get("https://some-random-api.ml/img/koala") as image:
                    response = await image.json()
                    url = response.get('link', FUNNY_URL)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['randompanda', 'panda'],
                      desc="Fetches random panda pics",
                      usage="randompanda (amount)")
    async def randomPanda(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "panda"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            async with aiohttp.ClientSession() as session:
                async with session.get("https://some-random-api.ml/img/panda") as image:
                    response = await image.json()
                    url = response.get('link', FUNNY_URL)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['randomredpanda', 'redpanda'],
                      desc="Fetches random red panda pics",
                      usage="randomredpanda (amount)")
    async def randomRedPanda(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "red panda"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            async with aiohttp.ClientSession() as session:
                async with session.get("https://some-random-api.ml/img/red_panda") as image:
                    response = await image.json()
                    url = response.get('link', FUNNY_URL)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['randomracoon', 'racoon'],
                      desc="Fetches random racoon pics",
                      usage="randomracoon (amount)")
    async def randomRacoon(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "racoon"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            async with aiohttp.ClientSession() as session:
                async with session.get("https://some-random-api.ml/img/racoon") as image:
                    response = await image.json()
                    url = response.get('link', FUNNY_URL)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(aliases=['randomwhale', 'whale'],
                      desc="Fetches random whale pics",
                      usage="randomwhale (amount)")
    async def randomWhale(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "whale"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            async with aiohttp.ClientSession() as session:
                async with session.get("https://some-random-api.ml/img/whale") as image:
                    response = await image.json()
                    url = response.get('link', FUNNY_URL)
            await self.send_image(ctx, path, url=url, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(desc="Make UconnSmashBot say anything",
                      usage="say [message]")
    async def say(self, ctx: Context, *, args):
        sayEmbed = discord.Embed(description=args,
                                 color=discord.Color.blue())
        await ctx.channel.send(embed=sayEmbed)

    @commands.command(aliases=["dsay", "sayd"],
                      desc="Make UconnSmashBot say anything after a set delay",
                      usage="saydelay [message]",
                      note="You will be asked for a delay")
    async def saydelay(self, ctx: Context, *, message: str):
        delay = await self._get_delay(ctx)
        await self._send_in(ctx.channel, message, delay)
        delta = self._get_delta(delay)
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Message Scheduled",
                description=f"{ctx.author.mention}, your message will be sent in this channel in {delta}",
                color=discord.Color.blue(),
            )
        )

    @commands.command(aliases=['toadpic', 'toademote'],
                      desc="Fetches picture of Toad from Super Mario",
                      usage="toad (amount)")
    async def toad(self, ctx: Context, to_send: typing.Optional[int] = 1):
        path = "toad"
        to_send = fix_to_send(to_send)
        for counter in range(to_send):
            await self.send_image(ctx, path, to_send=f"[{counter + 1}/{to_send}]" if to_send != 1 else "")
            await asyncio.sleep(SLEEP_TIME)
        return

    @commands.command(desc="Make UconnSmashBot say anything, but in text to speech",
                      usage="tts [message]",
                      uperms=["Send TTS Messages"])
    @commands.has_permissions(send_tts_messages=True)
    async def tts(self, ctx: Context, *, args):
        return await ctx.channel.send(content=args, tts=True)

    @commands.command(aliases=["dtts", "ttsd"],
                      desc="Make UconnSmashBot say anything after a set delay, but in text to speech",
                      usage="ttsdelay [message]",
                      uperms=["Send TTS Messages"],
                      note="You will be asked for a delay")
    @commands.has_permissions(send_tts_messages=True)
    async def ttsdelay(self, ctx: Context, *, message: str):
        delay = await self._get_delay(ctx)
        await self._send_in(ctx.channel, message, delay, tts=True)
        delta = self._get_delta(delay)
        return await ctx.channel.send(
            embed=discord.Embed(
                title="Message Scheduled",
                description=f"{ctx.author.mention}, your message will be sent in this channel in {delta}",
                color=discord.Color.blue(),
            )
        )


def setup(bot):
    bot.add_cog(Fun(bot))
