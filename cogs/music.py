import itertools
import os
import random
import re
from asyncio.tasks import Task
from collections import deque
from datetime import datetime
from typing import List, Union

import discord
from discord.ext import commands
from utils import (EmbedPaginator, EntryData, FieldPaginator, GlobalCMDS,
                   SubcommandHelp, context, customerrors, get_lyrics_embed,)
from utils.mbclient import MBClient
from utils.musicutils import *

VALID_TS = re.compile(r"([\d]*:[\d]{1,2}:[\d]{1,2})|([\d]{1,2}:[\d]{1,2})|([\d]*)")
_TITLE_CLEANUP = re.compile(r"(\(.*\))|(\[.*\])|({.*})")
_DEMOJIFY = re.compile("["
                       u"\U0001F600-\U0001F64F"  # emoticons
                       u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                       u"\U0001F680-\U0001F6FF"  # transport & map symbols
                       u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                       "]+", flags=re.UNICODE)
_PASS_CHECK = [
    "bind",
    "lyrics",
    "search",
]
SCARED_IDS: List[int]


class Music(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot) -> None:
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_music(bot))
        self.track_hook: function
        self.tasks: List[Task] = []
        self.lavalink: MBClient = None

    async def init_music(self, bot: commands.AutoShardedBot):
        global SCARED_IDS
        await self.bot.wait_until_ready()
        async with self.bot.mbdb.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS music(guild_id bigint PRIMARY KEY, channel_id bigint, dj_id bigint)")
            await con.execute("CREATE TABLE IF NOT EXISTS playlists(id SERIAL, user_id bigint, playlist_name text PRIMARY KEY, urls text[])")
            await con.execute("CREATE TABLE IF NOT EXISTS music_cache(query text PRIMARY KEY, data JSONB)")
        if not hasattr(bot, 'lavalink'):
            bot.lavalink = MBClient(self.bot, self.bot.user.id)
            data = [self.gcmds.env_check(key) for key in [f"LAVALINK_{info}" for info in "IP PORT PASSWORD".split()]]
            if not all(data):
                raise ValueError("Make sure your server IP, port, and password are in the .env file")
            ports = [int(port) for port in os.getenv("LAVALINK_PORT").split(",")]
            for port in ports:
                bot.lavalink.add_node(data[0], port, data[2], 'na', 'default-node',
                                      name=f"lavalink-{port}", reconnect_attempts=-1)
            self.bot.add_listener(bot.lavalink.voice_update_handler, 'on_socket_response')
        self.bot.lavalink = bot.lavalink
        self.bot.lavalink.add_event_hook(self.track_hook)
        self.lavalink = self.bot.lavalink
        SCARED_IDS = [int(id) for id in os.getenv("SCARED_IDS").split(",")]

    def cog_unload(self) -> None:
        for task in self.tasks:
            task.cancel()
        self.bot.lavalink._event_hooks.clear()

    async def cog_check(self, ctx):
        return True if ctx.command.name in _PASS_CHECK else True if "musiccache" in ctx.command.name else await context.music_bind(ctx)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not member.bot:
            player = get_player(self.bot, None, guild=member.guild)
            channel: discord.VoiceChannel = before.channel if before.channel else after.channel
            if player.is_connected and player.voice_channel_id == channel.id:
                if len([m for m in channel.members if not m.bot]) == 0:
                    await player.close_session()
                    await self.connect_to(member.guild, None)

    async def connect_to(self, guild: Union[discord.Guild, int], channel: Union[discord.VoiceChannel, int, None]) -> None:
        if isinstance(guild, int):
            guild = self.bot.get_guild(guild)
        if isinstance(channel, int):
            channel = guild.get_channel(channel)
        if channel and any([member.id in SCARED_IDS for member in channel.members if member.bot]):
            raise customerrors.OtherMBConnectedError()
        await guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)
        player = get_player(self.bot, None, guild=guild)
        player.voice_channel_id = channel.id if channel is not None else None

    @commands.command(aliases=["music", "mh"],
                      desc="Get basic help for all of UconnSmashBot's music commands",
                      usage="musichelp",)
    async def musichelp(self, ctx):
        pfx = await self.gcmds.prefix(ctx)
        _ONLY_VC = "This command only works when you are in a voice channel"
        _VOTE = "Acts as a vote toggle"
        return await SubcommandHelp(
            pfx=pfx,
            nospaced=True,
            title="Music Help",
            description="This is a general overview of UconnSmashBot's music commands. For more detailed help, "
            f"do {pfx}help [music_command]",
            per_page=20,
        ).add_entry(
            name="Bind",
            data=EntryData(
                usage="bind (#channel)",
                returns="An embed confirming the music channel has successfully been bound",
                note="The music channel must be bound before using most other music commands",
            )
        ).add_entry(
            name="DJ",
            data=EntryData(
                usage="dj (@role)",
                returns="An embed with variable contents",
                note="Specify `(@role)` to set the DJ role, otherwise it displays the currently set DJ role",
            )
        ).add_entry(
            name="Join",
            data=EntryData(
                usage="join",
                returns="An embed that shows the status of UconnSmashBot's voice channel connectivity",
                note=_ONLY_VC,
            )
        ).add_entry(
            name="Play",
            data=EntryData(
                usage="play (query | url)",
                returns="An embed that shows the status of UconnSmashBot's player",
                note=f"UconnSmashBot will begin playing if tracks are queued. {_ONLY_VC}",
            )
        ).add_entry(
            name="Now Playing",
            data=EntryData(
                usage="nowplaying",
                returns="An embed that shows the currently playing track (if any)",
                note=_ONLY_VC,
            )
        ).add_entry(
            name="Queue",
            data=EntryData(
                usage="queue (query | url)",
                returns="An embed that shows the player's queue status",
                note=_ONLY_VC,
            )
        ).add_entry(
            name="Pause",
            data=EntryData(
                usage="pause",
                returns="An embed that details the player's pause vote status",
                note=f"{_VOTE}. {_ONLY_VC}",
            )
        ).add_entry(
            name="Unpause",
            data=EntryData(
                usage="unpause",
                returns="An embed that details the player's unpause vote status",
                note=f"{_VOTE}. {_ONLY_VC}",
            )
        ).add_entry(
            name="Rewind",
            data=EntryData(
                usage="rewind",
                returns="An embed that details the player's rewind vote status",
                note=f"{_VOTE}. {_ONLY_VC}",
            )
        ).add_entry(
            name="Skip",
            data=EntryData(
                usage="skip",
                returns="An embed that details the player's skip vote status",
                note=f"{_VOTE}. {_ONLY_VC}",
            )
        ).add_entry(
            name="Stop",
            data=EntryData(
                usage="stop",
                returns="An embed that details the player's stop vote status",
                note=f"{_VOTE}. {_ONLY_VC}",
            )
        ).add_entry(
            name="Leave",
            data=EntryData(
                usage="leave",
                returns="An embed that details the player's leave vote status",
                note=f"{_VOTE}. {_ONLY_VC}",
            )
        ).show_help(ctx)

    @commands.command(aliases=["mc", "mci"],
                      desc="Get UconnSmashBot's lavalink cache details",
                      usage="musiccacheinfo (query)",
                      note="If `(query)` is unspecified, it will display general cache details")
    async def musiccacheinfo(self, ctx, *, query: str = None):
        return await ctx.channel.send(embed=await MBPlayer.get_cache_info(self.bot, query=query))

    @commands.command(aliases=["mcl"],
                      desc="List all cache files stored in cache directory",
                      usage="musiccachelist",
                      uperms=["Bot Owner Only"])
    @commands.is_owner()
    async def musiccachelist(self, ctx):
        cache_path = os.getenv("MBC_LOCATION")
        files = [name for name in reversed(sorted(os.listdir(os.path.abspath(cache_path))))]
        embed = discord.Embed(
            title="Cache Files",
            description="\n".join(
                [f"**{index}:** `{filename}` - {(os.path.getsize(os.path.abspath(f'{cache_path}/{filename}')) / 1024):.2f}KB" for index, filename in enumerate(files, 1)]),
            color=discord.Color.blue()
        )
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["mcexp"],
                      desc="Exports UconnSmashBot's lavalink cache",
                      usage="musiccacheexport [format] (query)",
                      uperms=["Bot Owner Only"],
                      note="Supported formats are JSON and PICKLE")
    @commands.is_owner()
    async def musiccacheexport(self, ctx, format: str = None, *, query: str = None):
        if not format or not format.lower() in ["json", "pickle"]:
            embed = discord.Embed(title="Invalid Format",
                                  description=f"{ctx.author.mention}, please pick a either JSON or PICKLE as the export format",
                                  color=discord.Color.dark_red())
        else:
            embed = await MBPlayer.export_cache(self.bot, query=query, format=format.lower())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["mcev"],
                      desc="Evict a query from UconnSmashBot's lavalink cache",
                      usage="musiccacheevict [query]",
                      uperms=["Bot Owner Only"])
    @commands.is_owner()
    async def musiccacheevict(self, ctx, *, query: str):
        return await ctx.channel.send(embed=await MBPlayer.evict_cache(self.bot, query))

    @commands.command(aliases=["mcc"],
                      desc="Clears the music cache",
                      usage="musiccacheclear",
                      uperms=["Bot Owner Only"],
                      note="A backup of the current cache will be made in JSON format")
    @commands.is_owner()
    async def musiccacheclear(self, ctx):
        await MBPlayer.export_cache(self.bot, format="pickle")
        return await ctx.channel.send(embed=await MBPlayer.evict_cache(self.bot, "", clear_all=True))

    @commands.command(aliases=["mcr"],
                      desc="Restore an exported lavalink cache state",
                      usage="musiccacherestore [filename]",
                      uperms=["Bot Owner Only"],
                      note="Incluce the extension")
    @commands.is_owner()
    async def musiccacherestore(self, ctx, filename: str):
        return await ctx.channel.send(embed=await MBPlayer.restore_cache(self.bot, filename, type="restore"))

    @commands.command(aliases=["mcm"],
                      desc="Merges current music cache with another cache file",
                      usage="musiccachemerge [filename]",
                      uperms=["Bot Owner Only"],
                      note="Merging will not overwrite already present queries")
    @commands.is_owner()
    async def musiccachemerge(self, ctx, filename: str):
        return await ctx.channel.send(embed=await MBPlayer.restore_cache(self.bot, filename, type="merge"))

    @commands.command(aliases=["mcrl"],
                      desc="Reloads the cache for specified entries",
                      usage="musiccachereload (query)",
                      uperms=["Bot Owner Only"],
                      note="If `(query)` is unspecified, it will reload the cache for all entries with no data")
    @commands.is_owner()
    async def musiccachereload(self, ctx, *, query: str = None):
        embed = discord.Embed(title="Reloading Cache...",
                              description=f"{ctx.author.mention}, depending on how many entries are found, this may take a while. Please be patient...",
                              color=discord.Color.blue())
        await ctx.channel.send(embed=embed)
        embed = discord.Embed(title="Cache Reloaded",
                              description=f"{ctx.author.mention}, the cache has been reloaded ",
                              color=discord.Color.blue())
        embed.description += f"for query ```{query}```" if query else "for all entries without data"
        player = get_player(self.bot, ctx)
        async with self.bot.mbdb.acquire() as con:
            if query is None:
                entries = await con.fetch("SELECT query FROM music_cache WHERE data=NULL")
                for entry in entries:
                    task = self.bot.loop.create_task(player.get_tracks(entry["query"], force_recache=True))
                    task.add_done_callback(self._handle_task_result)
            else:
                _query = await con.fetchval(
                    f"SELECT query FROM music_cache WHERE query=$query${query}$query$ OR query=$query$ytsearch:{query}$query$ OR query=$query$scsearch:{query}$query$ LIMIT 1"
                )
                if _query:
                    await player.get_tracks(f"ytsearch:{query}", force_recache=True)
                else:
                    embed.description = f"{ctx.author.mention}, I could not find an entry for ```{query}```"
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["mcrb"],
                      desc="Rebuilds the cache",
                      usage="musiccacherebuild",
                      uperms=["Bot Owner Only"])
    @commands.is_owner()
    async def musiccacherebuild(self, ctx):
        embed = discord.Embed(
            title="Queuing Recache...",
            description=f"{ctx.author.mention}, I am submitting all queries in cache for recache. Depending on the size of the cache, this may take a while. Please be patient...",
            color=discord.Color.blue()
        )
        start_time = int(datetime.now().timestamp())
        loading = await ctx.channel.send(embed=embed)
        fut = self.bot.loop.create_future()
        embed.title = "Rebuilding Cache..."
        embed.description = f"{ctx.author.mention}, I've queued all queries in cache for recache. Depending on the size of the cache, this may take a long while. Please be extremely patient..."
        now = int(datetime.now().timestamp())
        await loading.edit(embed=embed) if now - start_time <= 30 else await ctx.channel.send(embed=embed)
        await self.lavalink.efficient_cache_rebuild(ctx.guild.id, fut)
        await fut
        embed.title = "Cache Rebuild Completed"
        embed.description = f"{ctx.author.mention}, the cache has been successfully rebuilt"
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Binds the music commands to a channel",
                      usage="bind (channel)",
                      uperms=["Manage Server"],
                      note="If `(channel)` is not specified, the current channel will be used")
    @commands.has_permissions(manage_guild=True)
    async def bind(self, ctx, channel: discord.TextChannel = None):
        if not channel:
            channel = ctx.channel
        if not isinstance(channel, discord.TextChannel):
            converter = commands.TextChannelConverter()
            channel = await converter.convert(ctx, channel)
        if not isinstance(channel, discord.TextChannel):
            embed = discord.Embed(title="Invalid Channel",
                                  description=f"{ctx.author.mention}, please specify a valid channel",
                                  color=discord.Color.dark_red())
        else:
            async with self.bot.mbdb.acquire() as con:
                entry = await con.fetchval(f"SELECT guild_id FROM music WHERE guild_id={ctx.guild.id}")
                if not entry:
                    op = f"INSERT INTO music(guild_id, channel_id) VALUES ({ctx.guild.id}, {channel.id})"
                else:
                    op = f"UPDATE music SET channel_id={channel.id} WHERE guild_id={ctx.guild.id}"
                await con.execute(op)
            embed = discord.Embed(title="Music Channel Bound",
                                  description=f"The music channel was bound to {channel.mention}",
                                  color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["lyric"],
                      desc="Get song lyrics",
                      usage="lyrics (name | url)",
                      note="If `(name | url)` is unspecified, it will automatically search for the lyrics of "
                      "the currently playing song, if it exists")
    async def lyrics(self, ctx, *, title: str = None):
        player = get_player(self.bot, ctx)
        if not title and not player.current:
            return await ctx.channel.send(embed=discord.Embed(
                title="No Current Track",
                description=f"{ctx.author.mention}, you did not provide a name or url to search for, and there is "
                "no currently playing track",
                color=discord.Color.dark_red(),
            ))
        return await get_lyrics_embed(ctx, title if title else _TITLE_CLEANUP.sub("", _DEMOJIFY.sub("", player.current.title)))

    @commands.command(desc="Sets the DJ role",
                      usage="dj (@role)",
                      uperms=["Manage Server"],
                      note="If `(@role)` is unspecified, it will display the currently set DJ role. If `(@role)` is \"reset\", it will unregister the current DJ role")
    async def dj(self, ctx, *, role: str = None):
        embed = discord.Embed(description=f"{ctx.author.mention}, ", color=discord.Color.blue())
        perms = ctx.channel.permissions_for(ctx.author)
        if role and not perms.manage_guild:
            embed.title = "Insufficient Permissions"
            embed.description += "you require the `Manage Server` permissions to perform operations on the DJ role"
            embed.color = discord.Color.dark_red()
            return await ctx.channel.send(embed=embed)
        async with self.bot.mbdb.acquire() as con:
            if role == "reset":
                await con.execute(f"UPDATE music SET dj_id=NULL WHERE guild_id={ctx.guild.id}")
                embed.title = "DJ Role Unregistered"
                embed.description += "the DJ role for this server has been unregistered"
            elif role is None:
                dj_id = await con.fetchval(f"SELECT dj_id FROM music WHERE guild_id={ctx.guild.id}")
                embed.title = "Current DJ Role"
                embed.description += f"the currently registered DJ role is <@&{dj_id}>" if dj_id else "there is no currently registered DJ role"
            else:
                converter = commands.RoleConverter()
                role = await converter.convert(ctx, role)
                await con.execute(f"UPDATE music SET dj_id={role.id} WHERE guild_id={ctx.guild.id}")
                embed.title = "DJ Role Registered"
                embed.description += f"the DJ role for this server has been set to {role.mention}. Those who have it will be able to bypass the vote system"
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Makes UconnSmashBot join the same voice channel you're in",
                      usage="join",
                      note="You may only use this when you are connected to a voice channel")
    @ensure_voice()
    async def join(self, ctx):
        player = get_player(self.bot, ctx)
        embed = discord.Embed(
            title=f"Successfully {'Joined' if not player.is_connected else 'Moved to'} Voice Channel",
            description=f"{ctx.author.mention}, I have {'joined' if not player.is_connected else 'moved to'} {ctx.author.voice.channel.name}",
            color=discord.Color.blue()
        ).set_thumbnail(
            url="https://vignette.wikia.nocookie.net/mario/images/0/04/Music_Toad.jpg/revision/latest/top-crop/width/500/height/500?cb=20180812231020"
        )
        await self.connect_to(ctx.guild, ctx.author.voice.channel)
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["p"],
                      desc="Makes UconnSmashBot play a song or the current queue",
                      usage="play (query)",
                      note="If there are any songs in queue, `(query)` can be unspecified to start playing the first song in queue")
    @ensure_voice(should_connect=True)
    async def play(self, ctx, *, query: str = None):
        player = get_player(self.bot, ctx)
        if not query:
            if player.queue:
                if not player.is_playing:
                    return await player.play()
                else:
                    embed = discord.Embed(
                        title="No Query",
                        description=f"{ctx.author.mention}, you didn't specify a query. Please do so if you wish to queue a track. "
                        "If you wish to skip the current track, vote by executing `m!skip`",
                        color=discord.Color.dark_red()
                    )
                    return await ctx.channel.send(embed=embed)
            else:
                return await no_queue(ctx)

        return await play_or_queue_tracks(self.bot, ctx, player, query, send_embeds=bool(player.current))

    @commands.command(aliases=["np"],
                      desc="Shows the currently playing song, if any",
                      usage="nowplaying")
    @ensure_voice()
    async def nowplaying(self, ctx):
        return await ctx.channel.send(embed=get_now_playing_embed(self.bot, get_player(self.bot, ctx)))

    @commands.command(aliases=["q"],
                      desc="List the current queue or queue a song or playlist",
                      usage="queue (query)",
                      note="You must be in the same voice channel as UconnSmashBot")
    @ensure_voice(should_connect=True)
    async def queue(self, ctx, *, query: str = None):
        player = get_player(self.bot, ctx)
        if query is not None:
            return await play_or_queue_tracks(self.bot, ctx, player, query)

        embed = discord.Embed(color=discord.Color.blue())
        embed.title = f"Current Queue"
        total_duration_millis = sum(trk.duration for trk in player.queue) + \
            int(player.current.duration if player.current else 0) - player.position

        description = "\n".join([
            f"**Songs:** {len(player.queue)}",
            f"**Estimated Playtime Remaining:** {track_duration(total_duration_millis)}\n\n",
        ])
        entries = [
            "\n".join([
                f"**[{track.title}]({track.uri})**",
                f"**Channel:** {track.author}",
                f"**Song Duration:** {track_duration(track.duration)}",
                f"**Requester:** {self.bot.get_user(track.requester).mention if self.bot.get_user(track.requester) else 'Unknown'}\n",
            ]) for track in player.queue
        ] if player.queue else ["Nothing Queued"]
        embed.set_image(url=get_track_thumbnail(player.queue))
        return await EmbedPaginator(
            ctx,
            entries=entries,
            per_page=5,
            show_entry_count=True,
            embed=embed,
            description=description,
        ).paginate()

    @commands.command(aliases=["uq"],
                      desc="Remove specified items or ranges from queue",
                      usage="unqueue (index | range)",
                      note="Do `m!queue` to view the index of queued tracks.\n\nWhen specifying an index, you may specify only one number or comma "
                      "separated values, so long as there is a corresponding item in queue for that number. For example, `1` and `1,2,4,8` are valid "
                      "indeces, so long as the queue has at least `index` or `last value` songs queued."
                      "\n\nWhen specifying a range, please separate the items with a dash character `-`, and make sure that the first number is less "
                      "than the second. For example, `10 - 15` and `1-100` are valid ranges (given there are at least `second number` tracks queued), "
                      "but `15 - 10` is not. Ranges are **INCLUSIVE ON BOTH ENDS**")
    @ensure_voice()
    @require_dj()
    async def unqueue(self, ctx, *, index_or_range):
        embed = discord.Embed(title="Invalid Index or Range",
                              description=f"{ctx.author.mention}, `{index_or_range}` is not a valid index or range",
                              color=discord.Color.dark_red())
        player = get_player(self.bot, ctx)
        queue_length = len(player.queue)
        try:
            if "," in index_or_range:
                index = [int(num) for num in index_or_range.replace(" ", "").split(",")]
                if not all([1 <= num <= queue_length for num in index]):
                    raise ValueError
            else:
                index = int(index_or_range)
                if not 1 <= index <= queue_length:
                    raise ValueError
            spec_range = None
        except ValueError:
            try:
                index = None
                spec_range = [int(num) for num in index_or_range.replace(" ", "").split("-")]
                if len(spec_range) != 2 or not all([1 <= val <= len(player.queue) for val in spec_range]) or spec_range[0] >= spec_range[1]:
                    raise ValueError
            except ValueError:
                return await ctx.channel.send(embed=embed)

        if index is not None and type(index) == int:
            del player.queue[index - 1]
            desc = f"queue item {index}"
        elif index is not None and type(index) == list:
            count = 0
            desc = f"queue items {', '.join(str(num) for num in index)}"
            for num in (_ - 1 for _ in index):
                del player.queue[num - count]
                count += 1
        elif spec_range:
            orig_range = spec_range
            desc = f"queue items {orig_range[0]} through {orig_range[1]}"
            if spec_range[1] == queue_length:
                player.queue = deque(itertools.islice(player.queue, spec_range[0]))
            else:
                if spec_range[0] == 1:
                    front_half = deque()
                else:
                    front_half = deque(itertools.islice(player.queue, 0, spec_range[0] - 1))
                back_half = deque(itertools.islice(player.queue, spec_range[1] + 1, None))
                player.queue = front_half + back_half
        embed.title = f"Removed Queue {'Item' if index is not None else 'Range'}"
        embed.description = f"{ctx.author.mention}, I've removed {desc}"
        embed.color = discord.Color.blue()
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["qc", "clearqueue", "cq"],
                      desc="Clears the current queue",
                      usage="clearqueue")
    @ensure_voice()
    @require_dj()
    async def queueclear(self, ctx):
        player = get_player(self.bot, ctx)
        if not player.queue:
            embed = discord.Embed(title="Nothing in Queue",
                                  description=f"{ctx.author.mention}, the queue is already empty",
                                  color=discord.Color.blue())
        else:
            player.queue.clear()
            embed = discord.Embed(title="Queue Cleared",
                                  description=f"{ctx.author.mention}, I have cleared the queue",
                                  color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Searches YouTube for results matching a given query",
                      usage="search [query | url]",
                      note="You do not need to be in a voice channel to use this command")
    async def search(self, ctx, *, query: str):
        player = get_player(self.bot, ctx)
        return await get_search_results(ctx, player, query)

    @commands.command(aliases=["vol"],
                      desc="Adjusts the music player volume",
                      usage="volume (0 - 100)",
                      uperms=["DJ` or `Manage Server` or `Mute Members` or `Deafen Members` or `Move Members"],
                      note="Any volume adjustment will affect the relative volume for everyone currently connected in the voice channel")
    @ensure_voice()
    @require_dj(req_perms={
        "manage_guild": True,
        "mute_members": True,
        "deafen_members": True,
        "move_members": True,
    }, mode="any")
    async def volume(self, ctx, amount: int = None):
        player = get_player(self.bot, ctx)
        embed = discord.Embed(title="Current Player Volume",
                              color=discord.Color.blue())
        if amount is None:
            embed.description = f"Player volume is currently {player.volume}%{'. Nice' if player.volume == 69 else ''}```{str('|' * (player.volume // 4)) or ' '}```"
        elif 0 <= amount <= 100:
            await player.set_volume(amount)
            embed.description = f"Player volume has been set to {player.volume}%{'. Nice' if player.volume == 69 else ''}```{str('|' * (player.volume // 4)) or ' '}```"
            embed.set_footer(
                text=f"Requested by: {ctx.author.display_name}",
                icon_url=ctx.author.avatar_url
            )
        else:
            embed.title = "Invalid Volume Setting"
            embed.description = f"{ctx.author.mention}, the volume must be between 0 and 100"
            embed.color = discord.Color.dark_red()
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['eq', 'equalizer'],
                      desc="Adjusts the music player's equaliser",
                      usage="equaliser (band) (gain)",
                      uperms=["DJ` or `Manage Server` or `Mute Members` or `Deafen Members` or `Move Members"],
                      note="To adjust gain on specific bands, you must specify both `(band)` and `(gain)`. "
                      "`(band)` may be between 1 and 15 inclusive, comma separated integers between 1 and 15 inclusive, or \"all\" to modify all bands at once. "
                      "`(gain)` may be a decimal between -0.25 and 1.00 inclusive, comma separated decimals between -0.25 and 1.00 inclusive. "
                      "You can set multiple bands to one gain by specifying comma separated `(band)` values and only one `(gain)` value"
                      "Doing `m!equaliser reset` will reset the gain for all bands to default (0). "
                      "The amount of comma separated `(band)` and `(gain)` arguments must be the same, otherwise, an error message will be returned.\n\n"
                      "To view the equaliser bands, omit both the `(band)` and `(gain)` arguments. To view the gain for a specific band, "
                      "you must specify `(band)`, but not `(gain)`")
    @ensure_voice()
    @require_dj(req_perms={
        "manage_guild": True,
        "mute_members": True,
        "deafen_members": True,
        "move_members": True,
    }, mode="any")
    async def equaliser(self, ctx, band: str = None, gain: str = None):
        player = get_player(self.bot, ctx)
        op = "adjust"
        if band is None:
            band = gain = None
            op = "display"
        elif band.lower() == "reset":
            band = gain = None
            op = "reset"
        elif band.lower() == "all":
            if gain is None:
                raise customerrors.EQGainError(ctx, f"you must provide a valid gain value. To reset the equaliser, do `{await self.gcmds.prefix(ctx)}equaliser reset`")
            band = [num for num in range(15)]
            try:
                if not -0.25 <= float(gain) <= 1.00:
                    raise customerrors.EQGainError(ctx, f"{gain} is not between -0.25 and 1.00 inclusive")
                gain = [float(gain) for _ in range(15)]
            except ValueError as e:
                raise customerrors.EQGainError(ctx, f"{gain} is not a valid gain value")
        else:
            try:
                if not "," in band:
                    band = int(band) - 1
                    if not 0 <= band <= 14:
                        raise customerrors.EQBandError(ctx, f"{band} is not between 1 and 15 inclusive")
                else:
                    band = [int(b) - 1 for b in band.split(",")]
                    if not all([0 <= b <= 14 for b in band]):
                        raise customerrors.EQBandError(
                            ctx, f"all supplied band numbers must be between 1 and 15 inclusive"
                        )
            except ValueError as e:
                raise customerrors.EQBandError(ctx) from e
            finally:
                gain = check_gain(ctx, band, gain)
        embed = (await player.process_eq(band=band, gain=gain, op=op)).set_footer(
            text=f"Requested by: {ctx.author.display_name}\nChanges may not be applied immediately. Please wait around 2 - 10 seconds.",
            icon_url=ctx.author.avatar_url
        )
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["shfl"],
                      desc="Shuffle the current queue",
                      usage="shuffle (times)",
                      uperms=["DJ"],
                      note="If `(times)` is unspecified, it defaults to 1. "
                      "You must have items in queue for this command to work",)
    @ensure_voice()
    @require_dj(req_perms={
        "manage_guild": True,
        "mute_members": True,
        "deafen_members": True,
        "move_members": True,
    }, mode="any")
    async def shuffle(self, ctx, times: int = 1):
        player = get_player(self.bot, ctx)
        if player.queue:
            times = times if times >= 1 else 1
            for _ in range(times):
                random.shuffle(player.queue)
            embed = discord.Embed(
                title="Queue Shuffled",
                description=f"{ctx.author.mention}, the current queue has been shuffled {times} time{'s' if times != 1 else ''}",
                color=discord.Color.blue(),
            )
        else:
            embed = discord.Embed(
                title="Shuffle Failed",
                description=f"{ctx.author.mention}, I cannot shuffle an empty queue",
                color=discord.Color.dark_red(),
            )
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Toggle your vote to pause the player",
                      usage="pause",
                      note="The player will pause once the vote threshold has been crossed.")
    @ensure_voice()
    async def pause(self, ctx):
        return await ctx.channel.send(embed=await process_votes(self, self.bot, ctx, "pause"))

    @commands.command(desc="Toggle your vote to pause the player",
                      usage="fpause",
                      uperms=["DJ"],
                      note="The player will pause once the vote threshold has been crossed.")
    @ensure_voice()
    @require_dj()
    async def fpause(self, ctx):
        return await ctx.channel.send(embed=await process_votes(self, self.bot, ctx, "pause", dj=True))

    @commands.command(desc="Toggle your vote to unpause the player",
                      usage="unpause",
                      note="The player will unpause once the vote threshold has been crossed.")
    @ensure_voice()
    async def unpause(self, ctx):
        return await ctx.channel.send(embed=await process_votes(self, self.bot, ctx, "unpause"))

    @commands.command(desc="Toggle your vote to unpause the player",
                      usage="funpause",
                      uperms=["DJ"],
                      note="The player will unpause once the vote threshold has been crossed.")
    @ensure_voice()
    @require_dj()
    async def funpause(self, ctx):
        return await ctx.channel.send(embed=await process_votes(self, self.bot, ctx, "unpause", dj=True))

    @commands.command(desc="Toggle your vote to rewind to the previous track",
                      usage="rewind",
                      note="The player will rewind to the previous track once the vote threshold has been crossed.")
    @ensure_voice()
    async def rewind(self, ctx):
        return await ctx.channel.send(embed=await process_votes(self, self.bot, ctx, "rewind"))

    @commands.command(desc="Toggle your vote to rewind to the previous track",
                      usage="frewind",
                      uperms=["DJ"],
                      note="The player will rewind to the previous track once the vote threshold has been crossed.")
    @ensure_voice()
    @require_dj()
    async def frewind(self, ctx):
        return await ctx.channel.send(embed=await process_votes(self, self.bot, ctx, "rewind", dj=True))

    @commands.command(desc="Toggle your vote to skip to the next track",
                      usage="skip",
                      note="The player will skip to the next track once the vote threshold has been crossed.")
    @ensure_voice()
    async def skip(self, ctx):
        embed = await process_votes(self, self.bot, ctx, "skip")
        if embed:
            return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["fs"],
                      desc="Toggle your vote to skip to the next track",
                      usage="fskip",
                      uperms=["DJ"],
                      note="The player will skip to the next track once the vote threshold has been crossed.")
    @ensure_voice()
    @require_dj()
    async def fskip(self, ctx):
        embed = await process_votes(self, self.bot, ctx, "skip", dj=True)
        if embed:
            return await ctx.channel.send(embed=embed)

    @commands.command(desc="Toggle your vote to stop the player",
                      usage="stop",
                      note="The player will stop once the vote threshold has been crossed.")
    @ensure_voice()
    async def stop(self, ctx):
        return await ctx.channel.send(embed=await process_votes(self, self.bot, ctx, "stop"))

    @commands.command(desc="Toggle your vote to stop the player",
                      usage="fstop",
                      uperms=["DJ"],
                      note="The player will stop once the vote threshold has been crossed.")
    @ensure_voice()
    @require_dj()
    async def fstop(self, ctx):
        return await ctx.channel.send(embed=await process_votes(self, self.bot, ctx, "stop", dj=True))

    @commands.command(desc="Toggle your vote to make UconnSmashBot leave the current voice channel",
                      usage="leave",
                      note="The player will leave once the vote threshold has been crossed, regardless of whether or not it is currently playing a track")
    @ensure_voice()
    async def leave(self, ctx):
        return await ctx.channel.send(embed=await process_votes(self, self.bot, ctx, "leave"))

    @commands.command(desc="Toggle your vote to make UconnSmashBot leave the current voice channel",
                      usage="fleave",
                      uperms=["DJ"],
                      note="The player will leave once the vote threshold has been crossed, regardless of whether or not it is currently playing a track")
    @ensure_voice()
    @require_dj()
    async def fleave(self, ctx):
        return await ctx.channel.send(embed=await process_votes(self, self.bot, ctx, "leave", dj=True))

    @commands.command(desc="Set the player's track loop status",
                      usage="loop (times)",
                      uperms=["DJ"],
                      note="`(times)` can be a positive integer value, \"forever\" to loop indefinitely, or \"stop\" to stop looping")
    @ensure_voice()
    @require_dj()
    async def loop(self, ctx, *, amount: str = None):
        player = get_player(self.bot, ctx)
        if amount is None:
            embed = discord.Embed(
                title="Track Loop Status",
                description=f"{ctx.author.mention}, the current track is set to {player.loop_status}",
                color=discord.Color.blue()
            )
        else:
            embed = player.set_loop_times(amount).set_footer(
                text=f"Requested by: {ctx.author.display_name}",
                icon_url=ctx.author.avatar_url
            )
        return await ctx.channel.send(embed=embed)

    @commands.command(aliases=["qloop", "ql"],
                      desc="Set the player's queue loop status",
                      usage="queueloop (times)",
                      uperms=["DJ"],
                      note="`(times)` can be a positive integer value, \"forever\" to queue loop indefinitely, or \"stop\" to stop looping")
    @ensure_voice()
    @require_dj()
    async def queueloop(self, ctx, *, amount: str = None):
        player = get_player(self.bot, ctx)
        if amount is None:
            embed = discord.Embed(
                title="Queue Loop Status",
                description=f"The current queue is set to {player.queue_loop_status}",
                color=discord.Color.blue()
            )
        else:
            embed = player.set_queue_loop_times(amount).set_footer(
                text=f"Requested by: {ctx.author.display_name}",
                icon_url=ctx.author.avatar_url
            )
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Seek to a specific timestamp in the current track",
                      usage="seek ( (+ | -) hours:minutes:seconds|minutes:seconds|seconds)",
                      uperms=["DJ"],
                      note="There is no need to zero pad values. Please separate intervals with a colon \":\" character. "
                      "0 hours may be omitted, but 0 minutes or seconds must be specified (no need for padding). "
                      "Specifying plus (+) or minus (-) will add or subtract time from the current timestamp "
                      "(i.e, `m!seek -60` to seek back 60 seconds)")
    @ensure_voice()
    @require_dj()
    async def seek(self, ctx, *, timestamp: str = None):
        if timestamp.lower() in ["shortcuts", "sc", "help", "h"]:
            embed = discord.Embed(
                title="Seek Shortcuts",
                description=f"{ctx.author.mention}, here are valid seek shortcut words that can be used as time arguments:\n\n" +
                "\n".join([
                    "`start`, `s` - seek to the start of the current track",
                    "`middle`, `m` - seek to the middle of the current track",
                    "`end`, `e` - seek to the end of the current track (analogous to `m!skip`)"
                ]),
                color=discord.Color.blue()
            )
            return await ctx.channel.send(embed=embed)
        player = get_player(self.bot, ctx)
        if timestamp.lower() in ["start", "s", "middle", "m", "end", "e"]:
            if player.current:
                timestamp = {
                    "start": "0",
                    "s": "0",
                    "middle": f"{player.current.duration // 2000}",
                    "m": f"{player.current.duration // 2000}",
                    "end": f"{player.current.duration // 1000}",
                    "e": f"{player.current.duration // 1000}",
                }.get(timestamp.lower(), timestamp)
        timestamp = timestamp.replace(" ", "")
        sign = timestamp[0] if timestamp[0] in "+-" else None
        if sign:
            timestamp = timestamp[1:]
        embed = discord.Embed(title="Seek ", description=f"{ctx.author.mention}, ")
        failed = True
        if player.current and player.current.is_seekable and VALID_TS.fullmatch(timestamp):
            try:
                milliseconds = int(timestamp) * 1000
            except ValueError:
                try:
                    tokens = [int(value) for value in timestamp.split(":", 2)]
                    if len(tokens) > 3:
                        raise ValueError("Invalid seek timestamp format")
                except ValueError:
                    embed.description += f"`{timestamp}` is an invalid timestamp format"
                    return await ctx.channel.send(embed=embed)

                if len(tokens) == 2:
                    milliseconds = (tokens[0] * 60 + tokens[1]) * 1000
                else:
                    milliseconds = (tokens[0] * 3600 + tokens[1] * 60 + tokens[2]) * 1000

            seek_timestamp = await player.seek(milliseconds, sign=sign)
            failed = not isinstance(seek_timestamp, int)
            embed.description += str(
                f"I have successfully seeked {'to' if not sign else 'back by' if sign == '-' else 'forward by'} {track_duration(milliseconds)}" if not failed
                else seek_timestamp
            )
        else:
            embed.description += str(
                "I cannot seek when I am not currently playing any track" if not player.is_playing
                else "this track doesn't support seeking" if not player.current.is_seekable
                else f"`{timestamp}` is an invalid timestamp format"
            )
        embed.title += "Failed" if failed else "Successful"
        embed.color = discord.Color.dark_red() if failed else discord.Color.blue()
        if not failed:
            embed.set_footer(
                text=f"Requested by: {ctx.author.display_name}",
                icon_url=ctx.author.avatar_url
            )
        return await ctx.channel.send(embed=embed)

    @commands.group(invoke_without_command=True,
                    aliases=["playlists", "pl"],
                    desc="Shows help for the playlist command and subcommands",
                    usage="playlist (subcommand)",)
    async def playlist(self, ctx):
        return await get_playlist_help(self, ctx)

    @playlist.command(name="help",
                      aliases=["h"])
    async def playlist_help(self, ctx):
        return await get_playlist_help(self, ctx)

    @playlist.command(name="list",
                      aliases=["ls"])
    async def playlist_list(self, ctx, *, identifier: str = None):
        embed = discord.Embed(title="Your Playlists" if not identifier else "Playlist Details",
                              color=discord.Color.blue())
        loading_msg: discord.Message = await ctx.channel.send(embed=discord.Embed(
            title="Loading Playlist Details...",
            description=f"{ctx.author.mention}, depending on the size of your playlist and if it is in cache, this may take a while. Please be patient...",
            color=discord.Color.blue()
        )) if identifier is not None else None
        playlists = await get_playlist(self, ctx, identifier=identifier, ret="all")
        if not playlists:
            embed.description = f"{ctx.author.mention}, you don't have any saved playlists" if not identifier else f"{ctx.author.mention}, I could not find anything for the identifier ```{identifier}```"
            if loading_msg:
                return await loading_msg.edit(embed=embed)
            return await ctx.channel.send(embed=embed)

        if identifier:
            playlist = playlists[0]
            valid_tracks = [track for track in playlist.tracks if track]
            description = "\n".join([
                f"**ID:** {playlist.id}",
                f"**Name:** {playlist.name}",
                f"**Playlist by:** <@{playlist.user_id}>",
                f"**Songs:** {len(valid_tracks)}",
                f"**Duration:** {total_queue_duration(valid_tracks)}"
            ]) + "\n\n"
            entries = [
                "\n".join([
                    f"**[{track.title}]({track.uri})**",
                    f"**Channel:** {track.author}",
                    f"**Song Duration:** {track_duration(track.duration)}\n",
                ]) for track in valid_tracks
            ]
            embed.set_image(url=get_track_thumbnail(valid_tracks))
            pag = EmbedPaginator(
                ctx,
                entries=entries,
                per_page=5,
                show_entry_count=True,
                embed=embed,
                description=description,
                provided_message=loading_msg
            )
        else:
            embed.description = "\n".join([
                f"Amount: `{len(playlists)}`",
                f"Combined Duration: `{total_queue_duration([track for playlist in playlists for track in playlist.tracks])}`"
            ])
            entries = [
                (
                    playlist.name,
                    "\n".join([
                        f"ID: `{playlist.id}`",
                        f"Songs: `{len([track for track in playlist.tracks if track])}`",
                        f"Duration: `{total_queue_duration(playlist.tracks)}`",
                    ]),
                    True,
                ) for playlist in playlists
            ]
            embed.set_thumbnail(url=ctx.author.avatar_url)
            pag = FieldPaginator(
                ctx,
                entries=entries,
                per_page=6,
                show_entry_count=True,
                embed=embed
            )
        await pag.paginate()

    @playlist.command(name="queue",
                      aliases=["q"])
    @ensure_voice(should_connect=True)
    async def playlist_queue(self, ctx, *, identifier: str):
        playlist = await prep_play_queue_playlist(self, ctx, identifier)
        if playlist:
            return await play_or_queue_playlist(self.bot, ctx, get_player(self.bot, ctx), playlist)

    @playlist.command(name="play",
                      aliases=["p"])
    @ensure_voice(should_connect=True)
    async def playlist_play(self, ctx, *, identifier: str):
        playlist = await prep_play_queue_playlist(self, ctx, identifier)
        if playlist:
            return await play_or_queue_playlist(self.bot, ctx, get_player(self.bot, ctx), playlist, play=True)

    @playlist.command(name="save",
                      aliases=["s"])
    async def playlist_save(self, ctx, *, urls: str = None):
        embed = discord.Embed(title="Fetching Playlist Details...",
                              description=f"Depending on the size of {'the queue' if urls is None else 'the specified playlist'}, this may take a while. Please be patient...",
                              color=discord.Color.blue())
        message = await ctx.channel.send(embed=embed)
        player = get_player(self.bot, ctx)
        if urls is None and not player.queue:
            embed.title = "Playlist Save Failed"
            embed.description = f"{ctx.author.mention}, there are no tracks in queue to save"
            embed.color = discord.Color.dark_red()
            return await message.edit(embed=embed)
        return await save_playlist(self, ctx, urls.split(",") if urls else [track.uri for track in player.queue], message)

    @playlist.command(name="append",
                      aliases=["add", "a"])
    async def playlist_append(self, ctx, id: int, *, urls: str = None):
        player = get_player(self.bot, ctx)
        return await modify_playlist(self, ctx, id, urls=urls.split(",") if urls else [track.uri for track in player.queue], op_type="append")

    @playlist.command(name="replace",
                      aliases=["repl", "rp"])
    async def playlist_replace(self, ctx, id: int, *, urls: str = None):
        player = get_player(self.bot, ctx)
        return await modify_playlist(self, ctx, id, urls=urls.split(",") if urls else [track.uri for track in player.queue], op_type="replace")

    @playlist.command(name="rename",
                      aliases=["ren", "rn"])
    async def playlist_rename(self, ctx, id: int, *, new_name: str = None):
        return await modify_playlist(self, ctx, id, name=new_name, op_type="rename")

    @playlist.command(name="delete",
                      aliases=["del", "d"])
    async def playlist_delete(self, ctx, *, identifier: str):
        return await delete_playlist(self, ctx, identifier)


def setup(bot: commands.AutoShardedBot):
    bot.add_cog(Music(bot))


Music.track_hook = track_hook
