import functools
import math
from contextlib import suppress
from datetime import datetime
from io import BytesIO
from random import randint
from typing import Any, List, Tuple, Union

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from PIL.Image import NEAREST
from discord.ext.commands.bot import AutoShardedBot

from utils import customerrors


__all__ = (
    "calculate_level",
    "gen_guild_profile",
)


def check_entry_exists(entry: str = "enabled", db_name: str = "level_config"):
    def actual_decorator(func):
        @functools.wraps(func)
        async def checker(*args, **kwargs):
            bot = args[0].bot
            guild_id = args[1].guild.id
            if not guild_id:
                raise customerrors.LevelNoConfig()
            async with bot.db.acquire() as con:
                exists = await con.fetchval(f"SELECT {entry} FROM {db_name} WHERE guild_id={guild_id}")
            if not exists:
                raise customerrors.LevelNotEnabled()
            return await func(*args, **kwargs)
        return checker
    return actual_decorator


def _calc_req_xp(level: int) -> int:
    return int(-2000 + (2000.69420 * math.exp(0.069420 * level))) if level != 0 else 100


async def _get_guild_config(bot: commands.AutoShardedBot, message: discord.Message) -> Tuple[bool, bool, int, int, int, bool, bool]:
    async with bot.db.acquire() as con:
        config = await con.fetch(f"SELECT * FROM level_config WHERE guild_id={message.guild.id}")
        disabled = await con.fetchval(f"SELECT channel_id FROM level_disabled WHERE "
                                      f"channel_id={message.channel.id} AND guild_id={message.guild.id}")
    if not config:
        return (False, True, None, 1, 20, False, False)
    config = config[0]
    return (
        bool(config['enabled']),
        bool(disabled),
        int(config['route_channel_id']) if config['route_channel_id'] else None,
        int(config['freq']),
        int(config['per_min']),
        bool(config['server_notif']),
        bool(config['global_notif'])
    )


async def _get_user_global_level(bot: commands.AutoShardedBot, user: discord.User) -> Tuple[int, int, int]:
    async with bot.db.acquire() as con:
        details = await con.fetch(f"SELECT last_msg, xp, level FROM level_global WHERE "
                                  f"user_id={user.id}")
        if not details:
            details = await con.fetch("INSERT INTO level_global(user_id, last_msg, xp) VALUES"
                                      f"({user.id}, 0, 0) ON CONFLICT DO NOTHING RETURNING last_msg, xp, level")
    details = details[0]
    return int(details['last_msg']), int(details['xp']), int(details['level'])


async def _get_user_guild_level(bot: commands.AutoShardedBot, member: discord.Member) -> Tuple[int, int, int]:
    async with bot.db.acquire() as con:
        details = await con.fetch(f"SELECT last_msg, xp, level FROM level_users WHERE "
                                  f"user_id={member.id} AND guild_id={member.guild.id}")
        if not details:
            details = await con.fetch("INSERT INTO level_users(user_id, guild_id, xp, last_msg) VALUES"
                                      f"({member.id}, {member.guild.id}, 0, 0) "
                                      "ON CONFLICT DO NOTHING RETURNING last_msg, xp, level")
    details = details[0]
    return int(details['last_msg']), int(details['xp']), int(details['level'])


async def _dispatch_level_up(message: discord.Message, level: int, mode: str, **options) -> discord.Message:
    embed = discord.Embed(title="Level Up!",
                          description=f"{message.author.mention}, you leveled up to "
                          f"level **{level}**",
                          color=discord.Color.blue())
    if mode == "global":
        text = ("This level up notifier is for the global level. "
                "Your server level may differ")
    else:
        text = ("This level up notifier is for the server level. "
                "Your global level may differ")
    embed.set_footer(text=text)
    with suppress(Exception):
        route = options.get("route", None)
        if route:
            channel = message.guild.get_channel(route)
        else:
            channel = message.channel
        return await channel.send(embed=embed)


async def _calculate_global_level(bot: commands.AutoShardedBot, message: discord.Message,
                                  current_timestamp: int, route_channel_id: int, notify: bool):
    last_timestamp, xp, current_level = await _get_user_global_level(bot, message.author)
    if not current_timestamp - last_timestamp >= 60:
        return
    xp += int(20 * (randint(5, 20) / 10))
    req_xp = _calc_req_xp(current_level)
    async with bot.db.acquire() as con:
        await con.execute(f"UPDATE level_global SET last_msg={int(datetime.now().timestamp())} "
                          f"WHERE user_id={message.author.id}")
        if xp >= req_xp:
            await con.execute(f"UPDATE level_global SET level=level+1, xp={xp - req_xp} "
                              f"WHERE user_id={message.author.id}")
            current_level += 1
            if notify:
                await _dispatch_level_up(message, current_level, "global", route=route_channel_id)
        else:
            await con.execute(f"UPDATE level_global SET xp={xp} WHERE "
                              f"user_id={message.author.id}")
    return


async def _manage_roles(bot: commands.AutoShardedBot, message: discord.Message, current_level: int,
                        current_role, other_roles: Union[List[discord.Role], None]):
    role = message.guild.get_role(int(current_role['role_id']))
    await message.author.add_roles(role, reason=f"level up to level {current_level}")
    if not current_role['type'] == "replace":
        return

    to_remove = []
    if other_roles:
        async with bot.db.acquire() as con:
            for entry in other_roles:
                try:
                    to_remove.append(message.guild.get_role(int(entry['role_id'])))
                except Exception:
                    await con.execute(f"DELETE FROM level_roles WHERE role_id={int(entry['role_id'])}")
    if to_remove:
        with suppress(Exception):
            await message.author.remove_roles(*to_remove)
    return


async def _calculate_guild_level(bot: commands.AutoShardedBot, message: discord.Message,
                                 current_timestamp: int, route_channel_id: int,
                                 freq: int, per_min: int, notify: bool):
    last_timestamp, xp, current_level = await _get_user_guild_level(bot, message.author)
    if not current_timestamp - last_timestamp >= freq * 60:
        return
    xp += int((per_min * freq) * (randint(5, 20) / 10))
    req_xp = _calc_req_xp(current_level)
    async with bot.db.acquire() as con:
        await con.execute(f"UPDATE level_users SET last_msg={int(datetime.now().timestamp())} "
                          f"WHERE user_id={message.author.id} AND guild_id={message.guild.id}")
        if xp >= req_xp:
            await con.execute(f"UPDATE level_users SET level=level+1, xp={xp - req_xp} "
                              f"WHERE user_id={message.author.id} AND guild_id={message.guild.id}")
            current_level += 1
            current_role = await con.fetch(f"SELECT * FROM level_roles WHERE guild_id={message.guild.id} AND "
                                           f"obtain_at = {current_level}")
            other_roles = await con.fetch(f"SELECT * from level_roles WHERE guild_id={message.guild.id} AND "
                                          f"obtain_at < {current_level}")
            if current_role:
                current_role = current_role[0]
                await _manage_roles(bot, message, current_level, current_role, other_roles)
            if notify:
                await _dispatch_level_up(message, current_level, "guild", route=route_channel_id)
        else:
            await con.execute(f"UPDATE level_users SET xp={xp} WHERE "
                              f"user_id={message.author.id} AND guild_id={message.guild.id}")
    return


async def calculate_level(bot: commands.AutoShardedBot, message: discord.Message):
    current_timestamp = int(datetime.now().timestamp())
    enabled, channel_disabled, route_channel_id, freq, per_min, snotif, gnotif = await _get_guild_config(bot, message)
    await _calculate_global_level(bot, message, current_timestamp, route_channel_id, gnotif)
    if enabled and not channel_disabled:
        await _calculate_guild_level(bot, message, current_timestamp, route_channel_id, freq, per_min, snotif)
    return


async def _get_progress_bar(bot: commands.AutoShardedBot, member: discord.Member, mode: str = None) -> Tuple[Any, int, int, int]:
    # Left progress bar = (295, 247)
    # Right progress bar = (1003, 247)
    # Height = 65 px
    # Center level = (808, 247)
    max_length = 1003 - 295
    _, xp, level = await _get_user_guild_level(bot, member) if mode == "guild" else await _get_user_global_level(bot, member)
    req_xp = _calc_req_xp(level)
    length = int(max_length * (xp / req_xp))
    return Image.new("RGBA", (length, 65), (196, 176, 245)), level, xp, req_xp


def _executor_gen(bot: AutoShardedBot, member: discord.Member, mode: str,
                  progress_bar, level, xp, req_xp, pfp_asset_bytes) -> Any:
    name_font = ImageFont.truetype("./utils/src/NotoSans-CondensedBold.ttf", 69)
    level_font = ImageFont.truetype("./utils/src/NotoSans-CondensedBold.ttf", 42)
    pfp_mask = Image.new("L", (256, 256), 0)
    draw = ImageDraw.Draw(pfp_mask)
    draw.ellipse((0, 0, 256, 256), fill=255)

    image = Image.new("RGBA", (1050, 300), (115, 115, 115))
    if progress_bar:
        image.paste(progress_bar, (295, 215))

    overlay = Image.open("./utils/src/mbprofile.png")
    image.paste(overlay, (0, 0), overlay)
    name_length = ImageDraw.ImageDraw(image).textlength(str(member), font=name_font)
    xp_length = ImageDraw.ImageDraw(image).textlength(f"{xp}/{req_xp}", font=level_font) / 2
    lvl_length = ImageDraw.ImageDraw(image).textlength(f"Level {level}", font=level_font) / 2
    text_draw = ImageDraw.Draw(image)
    text_draw.text((1030 - name_length, 10), str(member), (0, 0, 0), font=name_font)
    text_draw.text((649 - xp_length, 216), f"{xp}/{req_xp}", (0, 0, 0), font=level_font)
    text_draw.text((960 - lvl_length, 100), f"Level {level}", (0, 0, 0), font=level_font)

    pfp_overlay = Image.open(BytesIO(pfp_asset_bytes))
    if not pfp_overlay.size[0] == pfp_overlay.size[1] == 256:
        pfp_overlay = pfp_overlay.resize((256, 256), NEAREST, reducing_gap=3.0)
    image.paste(pfp_overlay, (24, 20), pfp_mask)

    b_io = BytesIO()
    image.save(b_io, format="png")
    export = discord.File(fp=BytesIO(b_io.getvalue()), filename="profile.jpg")
    embed = discord.Embed(title=f"{member.display_name}'s Profile",
                          color=discord.Color.blue())
    embed.set_image(url="attachment://profile.jpg")
    return export, embed


async def gen_profile(bot: commands.AutoShardedBot, member: discord.Member, mode: str = "guild") -> Tuple[discord.File, discord.Embed]:
    progress_bar, level, xp, req_xp = await _get_progress_bar(bot, member, mode=mode)
    pfp_asset_bytes = await member.avatar_url_as(format="png", static_format="png", size=256).read()

    return await bot.loop.run_in_executor(
        None,
        functools.partial(_executor_gen, bot, member, mode, progress_bar, level, xp, req_xp, pfp_asset_bytes)
    )
