import json
import os
import discord
from discord.ext import commands

env_write = ["TOKEN=YOUR_BOT_TOKEN",
             "OWNER_ID=YOUR_ID_HERE",
             "UPDATES_CHANNEL=CHANNEL_ID_HERE",
             "LAVALINK_IP=IP_ADDR",
             "LAVALINK_PORT=PORT",
             "LAVALINK_PASSWORD=DEFAULT_STRING",
             "TENOR_API=API_KEY_FROM_TENOR"]
default_env = ["YOUR_BOT_TOKEN",
               "YOUR_ID_HERE",
               "CHANNEL_ID_HERE",
               "IP_ADDR",
               "PORT",
               "DEFAULT_STRING",
               "API_KEY_FROM_TENOR"]


class GlobalCMDS:
    
    def __init__(self):
        pass

    def init_env(self):
        if not os.path.exists('.env'):
            with open('./.env', 'w') as f:
                f.write("\n".join(env_write))
                return False
        return True

    def env_check(self, key: str):
        if not self.init_env(self) or os.getenv(key) in default_env:
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
