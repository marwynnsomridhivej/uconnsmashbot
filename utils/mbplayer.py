import asyncio
import json
import os
import pickle
import re
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Union

import discord
from aiofile import async_open
from discord.ext.commands.bot import AutoShardedBot
from lavalink.events import QueueEndEvent, TrackStartEvent
from lavalink.models import AudioTrack, DefaultPlayer

url_rx = re.compile(r'https?://(?:www\.)?.+')

BLUE = discord.Color.blue()
RED = discord.Color.dark_red()


class MBPlayer(DefaultPlayer):
    def __init__(self, guild_id, node):
        super(MBPlayer, self).__init__(guild_id, node)
        self.bot = None
        self._bot_future = asyncio.get_running_loop().create_future()
        self.queue: Deque[AudioTrack] = deque()
        self.session_queue: Deque[AudioTrack] = deque()
        self.current: AudioTrack = None
        self.voice_channel_id: int
        self.text_channel: discord.TextChannel
        self.votes: dict = {
            "pause": [],
            "unpause": [],
            "rewind": [],
            "skip": [],
            "stop": [],
            "leave": [],
        }
        self._loop = 0
        self.loop_count = 0
        self._queue_loop = 0
        self._queue_loop_index = 0
        self.queue_loop_count = 0
        self._rewind = False
        self._index = 0

    def set_bot(self, bot: AutoShardedBot) -> None:
        if self.bot is None:
            self.bot = bot
            self._bot_future.set_result(True)

    def reset_votes(self) -> None:
        self.votes: dict = {
            "pause": [],
            "unpause": [],
            "rewind": [],
            "skip": [],
            "stop": [],
            "leave": [],
        }

    async def close_session(self) -> None:
        self.queue.clear()
        self.session_queue.clear()
        self.reset_votes()
        await self.stop()
        await self.reset_equalizer()
        self._loop = 0
        self.loop_count = 0
        self._queue_loop = 0
        self._queue_loop_index = 0
        self.queue_loop_count = 0
        self._rewind = False

    def enable_rewind(self) -> Union[discord.Embed, None]:
        if len(self.session_queue) == 1:
            return discord.Embed(
                title="Cannot Rewind",
                description=f"There are no tracks to rewind to",
                color=RED
            )
        self._rewind = True
        return None

    def set_loop_times(self, times: str) -> discord.Embed:
        self._queue_loop = 0
        try:
            times = int(times)
            if not 0 <= times:
                return discord.Embed(
                    title="Invalid Loop Number",
                    description=f"The loop number must be a positive integer, not {times}",
                    color=RED,
                )
            self._loop = times
            description_fragment = f"loop {self._loop} time{'s' if self._loop != 1 else ''}" if self._loop != 0 else "not loop and play the next queued track once the current track finishes"
        except ValueError:
            self._loop = -1 if times.lower() == "forever" else 0
            description_fragment = "loop forever" if self._loop == -1 else "not loop"
        return discord.Embed(
            title="Track Loop Status",
            description=f"The current track will **{description_fragment}**\n\nTo loop forever, do `m!loop forever`\nTo stop looping, do `m!loop stop`",
            color=BLUE
        )

    def set_queue_loop_times(self, times: str) -> discord.Embed:
        self._loop = 0
        _previous = self._queue_loop
        try:
            times = int(times)
            if not 0 <= times:
                return discord.Embed(
                    title="Invalid Loop Number",
                    description=f"The loop number must be a positive integer, not {times}",
                    color=RED,
                )
            self._queue_loop = times
            description_fragment = f"loop {self._queue_loop} time{'s' if self._queue_loop != 1 else ''}" if self._queue_loop != 0 else "not loop and process the queue normally"
        except ValueError:
            self._queue_loop = -1 if times.lower() == "forever" else 0
            description_fragment = "loop forever" if self._queue_loop == -1 else "not loop"

        if _previous == 0 and self._queue_loop != 0 and self.current and self.current == self.session_queue[0]:
            self.queue.appendleft(self.session_queue.popleft())
        elif self._queue_loop == 0:
            print(self._queue_loop_index)
            for _ in range(self._queue_loop_index + 1):
                self.session_queue.appendleft(self.queue.popleft())
        return discord.Embed(
            title="Queue Loop Status",
            description=f"The current queue will **{description_fragment}**\n\nTo loop the queue forever, do `m!queueloop forever`\nTo stop queue looping, do `m!queueloop stop`",
            color=BLUE
        )

    @property
    def loop_status(self) -> str:
        return f"loop {self._loop} time{'s' if self._loop != 1 else ''}" if self._loop >= 1 else "loop forever" if self._loop == -1 else "not loop"

    @property
    def queue_loop_status(self) -> str:
        return f"queue loop {self._queue_loop} time{'s' if self._queue_loop != 1 else ''}" if self._queue_loop >= 1 else "loop forever" if self._queue_loop == -1 else "not loop"

    async def get_tracks(self, query: str, force_recache: bool = False) -> Dict:
        await self._bot_future
        current_timestamp = int(datetime.now().timestamp())
        async with self.bot.mbdb.acquire() as con:
            data = await con.fetchval(f"SELECT data FROM music_cache WHERE query=$query${query}$query$")
            if force_recache or data is None:
                res = await self.node.get_tracks(query)
                res_present = res and res.get("tracks")
                if res_present and res.get("loadType") != "PLAYLIST_LOADED":
                    res["tracks"] = [res["tracks"][0]]
                data = json.dumps({
                    "data": res if res_present else None,
                    "timestamp": current_timestamp,
                    "cached_in": self.guild_id,
                    "expire_at": -1 if res_present else current_timestamp + 86400
                })
                if not "https://www.twitch.tv/" in query:
                    await con.execute(f"INSERT INTO music_cache(query, data) VALUES ($query${query}$query$, $dt${data}$dt$) ON CONFLICT (query) DO NOTHING")
        return json.loads(data)["data"]

    async def get_all_tracks(self, query: str) -> Union[Dict, None]:
        await self._bot_future
        res = await self.node.get_tracks(query)
        return res if res and res.get("tracks") else None

    @staticmethod
    async def export_cache(bot: AutoShardedBot, query: str = None, format: str = "json") -> discord.Embed:
        embed = discord.Embed(title=f"Cache Export - {format.upper()}", color=BLUE)
        async with bot.mbdb.acquire() as con:
            if query is None:
                entries = await con.fetch("SELECT * FROM music_cache")
            else:
                entries = await con.fetchrow(f"SELECT * FROM music_cache WHERE query=$query${query if url_rx.match(query) else f'ytsearch:{query}'}$query$")
        base = os.getenv("MBC_LOCATION")
        filename = f"MBC_{f'query:{query}_' if query else ''}{int(datetime.now().timestamp())}"
        if not entries:
            embed.description = f"The query `{query}` is not in cache" if query is not None else "The cache has not been built"
            embed.color = RED
            return embed
        elif not isinstance(entries, List):
            entries = [entries]

        export_cache = {_query: data for _query, data in [(entry["query"], entry["data"]) for entry in entries]}

        if not os.path.exists(os.path.abspath(base)):
            os.mkdir(os.path.abspath(base))

        files = os.listdir(os.path.abspath(f"{base}"))
        while len(files) >= 20:
            file = [name for name in sorted([name.replace(".json", "").replace(".mbcache", "") for name in files])][0]
            if os.path.exists(f"{base}{file}.json"):
                os.remove(f"{base}{file}.json")
            else:
                os.remove(f"{base}{file}.mbcache")
            files = os.listdir(os.path.abspath(f"{base}"))

        if format == "json":
            async with async_open(os.path.abspath(f"{base}{filename}.json"), "wb") as jsonfile:
                await jsonfile.write(json.dumps(export_cache).encode())
            embed.description = f"The cache for `{query}` has been exported" if query is not None else "The cache has been exported"
            embed.description += f" as ```{filename}.json```"
        elif format == "pickle":
            async with async_open(os.path.abspath(f"{base}{filename}.mbcache"), "wb") as picklefile:
                await picklefile.write(pickle.dumps(export_cache, protocol=pickle.HIGHEST_PROTOCOL))
            embed.description = f"The cache for `{query}` has been exported" if query is not None else "The cache has been exported"
            embed.description += f" as ```{filename}.mbcache```"
        else:
            embed.description = f"`{format}` is an unsupported format"
            embed.color = RED
        return embed

    @staticmethod
    async def restore_cache(bot: AutoShardedBot, filename: str, type: str = "restore") -> discord.Embed:
        embed = discord.Embed(title=f"Cache {type.title()} ", color=BLUE)
        cache_path = os.getenv("MBC_LOCATION")
        try:
            async with async_open(os.path.abspath(f"{cache_path}/{filename}"), "rb") as backup:
                if filename.lower().endswith(".json"):
                    bak: dict = json.loads(await backup.read())
                elif filename.lower().endswith(".mbcache"):
                    bak: dict = pickle.loads(await backup.read())
                else:
                    raise FileNotFoundError

                async with bot.mbdb.acquire() as con:
                    if type.lower() == "restore":
                        await con.execute("TRUNCATE music_cache")
                    elif type.lower() == "merge":
                        pass
                    else:
                        raise ValueError(f"{type} is an invalid type")

                    values = ", ".join([f"($query${query}$query$, $dt${data}$dt$)" for query, data in bak.items()])
                    await con.execute(f"INSERT INTO music_cache(query, data) VALUES {values} ON CONFLICT (query) DO NOTHING")
            embed.description = f"The cache's state was successfully {type}d from the file ```{filename}```"
        except FileNotFoundError:
            embed.description = f"The cache's state was not {type}d. No cache export exists in the musiccache folder with the filename ```{filename}```"
            embed.color = RED
        except ValueError:
            embed.description = f"{type} is an invalid type"
            embed.color = RED
        return embed

    @staticmethod
    async def evict_cache(bot: AutoShardedBot, query: str, clear_all: bool = False) -> discord.Embed:
        embed = discord.Embed(title="Query ", color=BLUE)
        new_query = f"ytsearch:{query}" if not url_rx.match(query) else query
        async with bot.mbdb.acquire() as con:
            if clear_all:
                await con.execute("TRUNCATE music_cache")
                embed.title = "Cache Cleared"
                embed.description = "The cache has been cleared. A backup has been made in PICKLE format"
            else:
                entry = await con.fetchval(f"SELECT query FROM music_cache WHERE query=$query${new_query}$query$")
                if entry:
                    embed.title += "Evicted"
                    embed.description = f"The query `{query}` has been evicted from UconnSmashBot's global cache"
                    await con.execute(f"DELETE FROM music_cache WHERE query=$query${new_query}$query$")
                else:
                    embed.title += "Not Found"
                    embed.description = f"The query `{query}` could not be found in the cache"
                    embed.color = RED
        return embed

    @staticmethod
    async def get_cache_info(bot: AutoShardedBot, query: str = None) -> discord.Embed:
        embed = discord.Embed(title="Lavalink Cache Info", color=BLUE)
        current_timestamp = int(datetime.now().timestamp())
        async with bot.mbdb.acquire() as con:
            if query is None:
                entries = await con.fetch("SELECT * FROM music_cache")
                if len(entries) == 0:
                    embed.description = "The cache has not been built"
                    embed.color = RED
                else:
                    cache_size = len(entries)
                    data = {
                        key: json.loads(value) for key, value in [(entry["query"], entry["data"]) for entry in entries]
                    }
                    none_queries = [entry for _, entry in data.items() if entry.get("data", None) is None]
                    valid_size = cache_size - len(none_queries)
                    expired_size = len([entry for entry in none_queries if entry["expire_at"] <= current_timestamp])
                    embed.description = "\n".join([
                        f"**Size:** {cache_size} quer{'ies' if cache_size != 1 else 'y'}",
                        f"**Valid Queries:** {valid_size} quer{'ies' if valid_size != 1 else 'y'} ≈ {(100 * valid_size / cache_size):.2f}%",
                        f"**Expired:** {expired_size} quer{'ies' if expired_size != 1 else 'y'} ≈ {(100 * expired_size / cache_size):.2f}%",
                    ])
            else:
                new_query = "ytsearch:" + query if not url_rx.match(query) else query
                entry = await con.fetchrow(f"SELECT * FROM music_cache WHERE query=$query${new_query}$query$")
                if entry is None:
                    embed.title = "Invalid Query"
                    embed.description = f"The query `{query}` could not be found in the cache"
                    embed.color = RED
                else:
                    data = json.loads(entry["data"])
                    load_type = data.get("loadType") if data else "NO_MATCHES"
                    query_type = {
                        "TRACK_LOADED": "Direct Track URL",
                        "PLAYLIST_LOADED": "Direct Playlist URL",
                        "SEARCH_RESULT": "Successful YouTube / SoundCloud Query",
                        "NO_MATCHES": "Failed YouTube / SoundCloud Query",
                        "LOAD_FAILED": "Error Occurred During Loading",
                    }.get(load_type, "No Info")
                    timestamp = datetime.fromtimestamp(entry["timestamp"]).strftime('%m/%d/%Y %H:%M:%S')
                    expire_at = "Never" if entry["expire_at"] == - \
                        1 else datetime.fromtimestamp(entry["expire_at"]).strftime('%m/%d/%Y %H:%M:%S')
                    embed.title += f" - {query}"
                    embed.description = "\n".join([
                        f"**Result:** {query_type}",
                        f"**Cached On:** {timestamp}",
                        f"**Expires:** {expire_at}",
                    ])
                    if data is not None and load_type in ["TRACK_LOADED", "SEARCH_RESULT"]:
                        from .musicutils import (_get_track_thumbnail,
                                                 track_duration)
                        track = AudioTrack(data["tracks"][0], 0)
                        embed.description += "\n\n" + "\n".join([
                            f"**Video:** [{track.title}]({track.uri})",
                            f"**Author:** {track.author}",
                            f"**Duration:** {track_duration(track.duration)}",
                            f"**Seek Compatible:** {'Yes' if track.is_seekable else 'No'}"
                        ])
                        embed.set_image(
                            url=_get_track_thumbnail(track)
                        )
        return embed

    async def seek(self, millisecond_amount: int, sign: str = None) -> Union[int, str]:
        if sign == "+":
            position = self.position + millisecond_amount
        elif sign == "-":
            position = self.position - millisecond_amount
        else:
            position = millisecond_amount

        if not 0 <= position:
            position = 0
        if not position <= self.current.duration:
            position = self.current.duration

        await super().seek(position)
        return int(position)

    async def play(self) -> AudioTrack:
        await self._bot_future
        self.reset_votes()
        self._last_update = 0
        self._last_position = 0
        self.position_timestamp = 0
        self.paused = False

        if not self._rewind and self._loop == self._queue_loop == 0:
            self.loop_count = self.queue_loop_count = 0
            try:
                # FIFO pop
                track = self.queue.popleft()
                self.session_queue.appendleft(track)
            except IndexError:
                # If no track available to skip
                await self.node._dispatch_event(QueueEndEvent(self))
                self.current = None
                await self.stop()
                await self.close_session()
                return None
        elif not self._rewind:
            if self._loop:
                self.loop_count += 1
                track = self.current
                if self._loop != -1:
                    self._loop -= 1
            elif self._queue_loop:
                try:
                    self._queue_loop_index = self.queue.index(self.current) + 1
                    track = self.queue[self._queue_loop_index]
                except (ValueError, IndexError):
                    self._queue_loop_index = 1
                    if self.current in self.queue:
                        self.queue_loop_count += 1
                    track = self.queue[0]
                if track == self.queue[-1] and self._queue_loop != -1:
                    self._queue_loop -= 1
                elif self._queue_loop == 0:
                    for _ in range(len(self.queue)):
                        self.session_queue.appendleft(self.queue.popleft())
        else:
            self._rewind = False
            # State of self.current has not been incremented to previous track
            # Therefore append current track to queue because we will need to play
            # The current song after the rewind has finished
            self.queue.appendleft(self.current)
            # Set track equal to index (starts at 1), because index 0 is the currently playing one
            # self._index >= 1 will pick previously played tracks in the reverse order they were
            # played
            self.session_queue.popleft()
            track = self.session_queue[0]

        self.current = track

        await self.node._send(op="play", guildId=self.guild_id, track=track.track)
        await self.node._dispatch_event(TrackStartEvent(self, self.current))
        return self.current

    async def process_eq(self, band: Union[List[int], int] = None, gain: Union[List[float], float] = None, op: str = None) -> discord.Embed:
        if op == "reset":
            await self.reset_equalizer()
            return discord.Embed(
                title="Equaliser Reset",
                description=f"All equaliser bands have been reset to the default gain (0)",
                color=BLUE
            )
        elif op == "adjust":
            if isinstance(band, int):
                band = [band]
            if isinstance(gain, float):
                gain = [gain]
            await self.set_gains(*[(b, g) for b, g in zip(band, gain)])
            adjusted = f"band{'s' if len(band) != 1 else ''} " + ", ".join([
                str(b + 1) for b in band
            ]) if len(band) < 15 else "all bands"
            return discord.Embed(
                title="Equaliser Settings Changed",
                description=f"Equaliser settings for {adjusted} have been changed",
                color=BLUE
            )
        elif op == "display":
            band_gain_render = "\n".join([
                f"Band {str(index).zfill(2)} [{gain:.2f}] {round(((gain + 0.25) / 1.25) * 30) * '|'}" for index, gain in enumerate(self.equalizer, 1)
            ])
            return discord.Embed(
                title="Current Equaliser Setting",
                description=f"```{band_gain_render}```",
                color=BLUE
            )
