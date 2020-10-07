import asyncio
import math
import os
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils import customerrors

load_dotenv()
env_write = ["TOKEN=YOUR_BOT_TOKEN",
             "OWNER_ID=YOUR_ID_HERE",
             "PG_USER=POSTGRES_USERNAME",
             "PG_PASSWORD=POSTGRES_PASSWORD",
             "PG_DATABASE=POSTGRES_DATABASE",
             "PG_HOST=POSTGRES_HOST",
             "UPDATES_CHANNEL=CHANNEL_ID_HERE",
             "LAVALINK_IP=IP_ADDR",
             "LAVALINK_PORT=PORT",
             "LAVALINK_PASSWORD=DEFAULT_STRING",
             "CAT_API=API_KEY_FROM_CAT_API",
             "IMGUR_API=API_KEY_FROM_IMGUR",
             "REDDIT_CLIENT_ID=CLIENT_ID_FROM_REDDIT_API",
             "REDDIT_CLIENT_SECRET=CLIENT_SECRET_FROM_REDDIT_API",
             "USER_AGENT=YOUR_USER_AGENT",
             "TENOR_API=API_KEY_FROM_TENOR",
             "GITHUB_TOKEN=PERSONAL_ACCESS_TOKEN"]
default_env = ["YOUR_BOT_TOKEN",
               "YOUR_ID_HERE",
               "POSTGRES_USERNAME",
               "POSTGRES_PASSWORD",
               "POSTGRES_DATABASE",
               "POSTGRES_HOST",
               "CHANNEL_ID_HERE",
               "IP_ADDR",
               "PORT",
               "DEFAULT_STRING",
               "API_KEY_FROM_CAT_API",
               "API_KEY_FROM_IMGUR",
               "CLIENT_ID_FROM_REDDIT_API",
               "CLIENT_SECRET_FROM_REDDIT_API",
               "YOUR_USER_AGENT",
               "API_KEY_FROM_TENOR",
               "PERSONAL_ACCESS_TOKEN"]
_bot = None
_db = None


class GlobalCMDS:

    def __init__(self, bot: commands.AutoShardedBot = None):
        global _bot, _db
        self.version = "v0.7.0-alpha.1"
        self.bot = bot
        if bot:
            self.db = self.bot.db
            _bot = bot
            _db = self.db

    def init_env(self):
        if not os.path.exists('.env'):
            with open('./.env', 'w') as f:
                f.write("\n".join(env_write))
                return False
        return True

    def env_check(self, key: str):
        if not self.init_env() or os.getenv(key) in default_env:
            return False
        return os.getenv(key)

    async def smart_delete(self, message: discord.Message):
        if message.guild and message.guild.me.guild_permissions.manage_messages:
            try:
                await message.delete()
            except Exception:
                pass

    async def confirmation(self, ctx, description):
        embed = discord.Embed(title="Confirmation",
                              description=description + " React with ✅ to confirm or 🛑 to cancel",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    async def timeout(self, ctx: commands.Context, title: str, timeout: int) -> discord.Message:
        embed = discord.Embed(title=f"{title.title()} Timed Out",
                              description=f"{ctx.author.mention}, your {title} timed out after {timeout} seconds"
                              " due to inactivity",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def cancelled(self, ctx: commands.Context, title: str) -> discord.Message:
        embed = discord.Embed(title=f"{title.title()} Cancelled",
                              description=f"{ctx.author.mention}, your {title} was cancelled",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def panel_deleted(self, ctx: commands.Context, title: str) -> discord.Message:
        embed = discord.Embed(title=f"{title.title()} Cancelled",
                              description=f"{ctx.author.mention}, your {title} was cancelled because the panel was "
                              "deleted or could not be found",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed)

    async def prefix(self, ctx):
        if not ctx.guild:
            return "m!"

        async with self.db.acquire() as con:
            prefix = await con.fetchval(f"SELECT custom_prefix FROM guild WHERE guild_id = {ctx.guild.id}")
            return prefix

    async def blacklist_db(self, execute):
        try:
            async with self.db.acquire() as con:
                result = await con.execute(execute)
        except Exception:
            raise customerrors.BlacklistOperationError()

    async def balance_db(self, execute: str, ret_val: bool = False):
        async with self.db.acquire() as con:
            if ret_val:
                val = await con.fetch(execute)
                return val[0]['amount']
            else:
                await con.execute(execute)

    async def get_balance(self, member: discord.Member):
        async with self.db.acquire() as con:
            bal = await con.fetchval(f"SELECT amount FROM balance WHERE user_id = {member.id}")
            return int(bal) if bal else None

    async def ratio(self, user: discord.User, game: str):
        async with self.db.acquire() as con:
            result = (await con.fetch(f"SELECT win, lose FROM {game.lower()} WHERE user_id={user.id}"))[0]
        if int(result['lose']) == 0:
            op = f"UPDATE {game.lower()} SET ratio = 9999 WHERE user_id = {user.id}"
        else:
            op = f"UPDATE {game.lower()} SET ratio = {self.truncate((int(result['win']) / int(result['lose'])), 3)}"
            f" WHERE user_id = {user.id}"
        async with self.db.acquire() as con:
            await con.execute(op)

    async def github_request(self, method, url, *, params=None, data=None, headers=None):
        hdrs = {
            'Accept': 'application/vnd.github.inertia-preview+json',
            'User-Agent': 'MarwynnBot Discord Token Invalidator',
            'Authorization': f"token {self.env_check('GITHUB_TOKEN')}"
        }

        req_url = f"https://api.github.com/{url}"

        if isinstance(headers, dict):
            hdrs.update(headers)

        async with aiohttp.ClientSession() as session:
            async with session.request(method, req_url, params=params, json=data, headers=hdrs) as response:
                ratelimit_remaining = response.headers.get('X-Ratelimit-Remaining')
                js = await response.json()
                if response.status == 429 or ratelimit_remaining == '0':
                    sleep_time = discord.utils._parse_ratelimit_header(response)
                    await asyncio.sleep(sleep_time)
                    return await self.github_request(method, url, params=params, data=data, headers=headers)
                elif 300 > response.status >= 200:
                    return js
                else:
                    raise GithubError(js['message'])

    async def create_gist(self, content, *, description):
        headers = {
            'Accept': 'application/vnd.github.v3+json',
        }

        filename = 'tokens.txt'
        data = {
            'public': True,
            'files': {
                filename: {
                    'content': content
                }
            },
            'description': description
        }

        response = await self.github_request('POST', 'gists', data=data, headers=headers)
        return response['html_url']

    @staticmethod
    def truncate(number: float, decimal_places: int):
        stepper = 10.0 ** decimal_places
        return math.trunc(stepper * number) / stepper


class GithubError(commands.CommandError):
    pass
