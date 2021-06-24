import asyncio
from contextlib import suppress

import discord
from discord.ext import commands

from utils.globalcommands import GlobalCMDS

reactions = ['✅', '❌']

__all__ = (
    "confirm",
)


async def confirm(ctx: commands.Context, bot: commands.AutoShardedBot, user: discord.User = None,
                  success_func: callable = None, fail_func: callable = None, embed: discord.Embed = None,
                  timeout: int = 30, op: str = None) -> discord.Message:
    def reacted(reaction: discord.Reaction, r_user: discord.User):
        return reaction.emoji in reactions and reaction.message.id == message.id and r_user.id == user.id

    if not embed:
        embed = discord.Embed(title="Confirmation",
                              description=f"{user.mention}, this action is destructive and irreversible. ",
                              color=discord.Color.blue())
    embed.description += f"React with {reactions[0]} to confirm or {reactions[1]} to cancel"
    message = await ctx.channel.send(embed=embed)

    for reaction in reactions:
        with suppress(Exception):
            await message.add_reaction(reaction)

    try:
        reaction, user = await bot.wait_for("reaction_add", check=reacted, timeout=timeout)
    except asyncio.TimeoutError:
        return await GlobalCMDS(bot).timeout(ctx, op)
    finally:
        with suppress(Exception):
            await message.delete()

    if reaction.emoji == reactions[0]:
        return await success_func
    else:
        return await fail_func or await GlobalCMDS(bot).canceled(ctx, op)
