import json
import os
import discord
from discord.ext import commands
import aiohttp
import asyncio

env_write = ["TOKEN=YOUR_BOT_TOKEN",
             "OWNER_ID=YOUR_ID_HERE",
             "UPDATES_CHANNEL=CHANNEL_ID_HERE",
             "LAVALINK_IP=IP_ADDR",
             "LAVALINK_PORT=PORT",
             "LAVALINK_PASSWORD=DEFAULT_STRING",
             "TENOR_API=API_KEY_FROM_TENOR",
             "GITHUB_TOKEN=PERSONAL_ACCESS_TOKEN"]
default_env = ["YOUR_BOT_TOKEN",
               "YOUR_ID_HERE",
               "CHANNEL_ID_HERE",
               "IP_ADDR",
               "PORT",
               "DEFAULT_STRING",
               "API_KEY_FROM_TENOR",
               "PERSONAL_ACCESS_TOKEN"]


class GlobalCMDS:
    
    def __init__(self):
        self.version = "v1.2.4"

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

    async def msgDelete(self, message: discord.Message):
        try:
            await message.delete()
        except Exception:
            pass

    def json_load(self, filenamepath: str, init: dict):
        if not os.path.exists(filenamepath):
            with open(filenamepath, 'w') as f:
                json.dump(init, f, indent=4)
    
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


class GithubError(commands.CommandError):
    pass
