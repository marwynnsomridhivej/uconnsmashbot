import json
import os
import discord
from discord.ext import commands

env_write = ["TOKEN=YOUR_BOT_TOKEN",
             "OWNER_ID=YOUR_ID_HERE",
             "UPDATES_CHANNEL=CHANNEL_ID_HERE",
             "LAVALINK_IP=IP_ADDR",
             "LAVALINK_PORT=PORT",
             "LAVALINK_PASSWORD=DEFAULT_STRING"
             "TENOR_API=API_KEY_FROM_TENOR"]
default_env = ["YOUR_BOT_TOKEN",
               "YOUR_ID_HERE",
               "CHANNEL_ID_HERE",
               "IP_ADDR",
               "PORT",
               "DEFAULT_STRING",
               "API_KEY_FROM_TENOR"]


class GlobalCMDS:

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

    def file_check(self, filenamepath: str, init):
        if not os.path.exists(filenamepath):
            with open(filenamepath, 'w') as f:
                for string in init:
                    f.write(string)

    async def invkDelete(self, ctx):
        if isinstance(ctx.channel, discord.TextChannel) and ctx.guild.me.guild_permissions.manage_messages:
            await ctx.message.delete()

    async def msgDelete(self, message: discord.Message):
        if isinstance(message.channel, discord.TextChannel) and message.guild.me.guild_permissions.manage_messages:
            await message.delete()

    async def timeout(self, ctx: commands.Context, title: str, timeout: int) -> discord.Message:
        embed = discord.Embed(title=f"{title.title()} Timed Out",
                              description=f"{ctx.author.mention}, your {title} timed out after {timeout} seconds"
                              " due to inactivity",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed, delete_after=10)

    async def cancelled(self, ctx: commands.Context, title: str) -> discord.Message:
        embed = discord.Embed(title=f"{title.title()} Cancelled",
                              description=f"{ctx.author.mention}, your {title} was cancelled",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed, delete_after=10)

    async def panel_deleted(self, ctx: commands.Context, title: str) -> discord.Message:
        embed = discord.Embed(title=f"{title.title()} Cancelled",
                              description=f"{ctx.author.mention}, your {title} was cancelled because the panel was "
                              "deleted or could not be found",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed, delete_after=10)

    def isGuild(self, ctx):
        if ctx.guild:
            return True
        else:
            return False

    def json_load(self, filenamepath: str, init: dict):
        if not os.path.exists(filenamepath):
            with open(filenamepath, 'w') as f:
                json.dump(init, f, indent=4)

    def prefix(self, ctx):
        if not self.isGuild(self, ctx):
            return "m!"

        with open('prefixes.json', 'r') as f:
            prefixes = json.load(f)

        return prefixes[str(ctx.guild.id)]
