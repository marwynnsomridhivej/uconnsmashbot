import discord
from discord.ext import commands

from utils import customerrors, globalcommands


def is_premium(*args, **kwargs):

    async def predicate(ctx, *args, **kwargs):
        db = globalcommands._db
        if not db:
            raise customerrors.NoPostgreSQL()
        async with db.acquire() as con:
            if kwargs.get('req_guild', False):
                result = await con.fetch(f"SELECT guild_id FROM premium WHERE guild_id = {ctx.guild.id}")
                if not result:
                    raise customerrors.NotPremiumGuild(ctx.guild)
            elif kwargs.get('req_user', False):
                result = await con.fetch(f"SELECT user_id FROM premium WHERE user_id = {ctx.author.id}")
                if not result:
                    raise customerrors.NotPremiumUser(ctx.author)
            else:
                result = await con.fetch(f"SELECT * FROM premium WHERE user_id = {ctx.author.id} OR guild_id = {ctx.guild.id}")
                if not result:
                    raise customerrors.NotPremiumUserOrGuild(ctx.author, ctx.guild)
        return True

    return commands.check(predicate)


async def check_user_premium(user: discord.User) -> bool:
    db = globalcommands._db
    if not db:
        raise customerrors.NoPostgreSQL()
    async with db.acquire() as con:
        result = await con.fetchval(f"SELECT user_id FROM premium WHERE user_id = {user.id}")
    return True if result else False


async def check_guild_premium(guild: discord.Guild) -> bool:
    db = globalcommands._db
    if not db:
        raise customerrors.NoPostgreSQL()
    async with db.acquire() as con:
        result = await con.fetchval(f"SELECT guild_id FROM premium WHERE guild_id = {guild.id}")
    return True if result else False
