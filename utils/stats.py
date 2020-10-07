import discord
from discord.ext import commands


class Stats:
    def __init__(self, bot=None):
        self.bot = bot

    @property
    def bot(self):
        return self.bot

    @bot.setter
    def bot(self, bot):
        if isinstance(bot, commands.AutoShardedBot):
            self.bot = bot
        else:
            raise TypeError(f"The passed bot is of type {type(bot)}, requires type commands.AutoShardedBot")

    @bot.deleter
    def bot(self):
        del self.bot
