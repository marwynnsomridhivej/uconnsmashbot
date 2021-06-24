import discord

from utils import customerrors, globalcommands


__all__ = (
    "redirect",
    "music_bind",
)


async def redirect(ctx):
    if not ctx.guild:
        return True
    bot = globalcommands._bot
    db = globalcommands._db
    cmd = ctx.command.root_parent.name if ctx.command.root_parent else ctx.command.name
    async with db.acquire() as con:
        result = await con.fetchval(f"SELECT channel_id FROM redirects WHERE guild_id={ctx.guild.id} AND command='{cmd}' AND type='override'")
        if not result:
            result = await con.fetchval(f"SELECT channel_id FROM redirects WHERE guild_id={ctx.guild.id} AND command='{cmd}' AND type='all'")
    if result:
        ctx.channel = await bot.fetch_channel(int(result))
    return True


async def music_bind(ctx, message: discord.Message = None):
    if not ctx:
        ctx = message
    db = globalcommands._db
    async with db.acquire() as con:
        result = await con.fetchval(f"SELECT channel_id FROM music WHERE guild_id={ctx.guild.id}")
    if not result:
        raise customerrors.NoBoundChannel()
    if not ctx.channel.id == result:
        raise customerrors.NotBoundChannel(result)
    return True
