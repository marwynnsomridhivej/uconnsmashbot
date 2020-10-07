import asyncio
import math
import re
from contextlib import suppress
from datetime import datetime

import discord
import lavalink
from discord.ext import commands, tasks
from utils import context, customerrors, globalcommands, premium

gcmds = globalcommands.GlobalCMDS()
url_rx = re.compile(r'https?://(?:www\.)?.+')
reactions = ["⏪", "⏯", "⏩", "⏹"]
plist_reactions = ["💾", "📝"]
plist_delete_reactions = ["✅", "🛑"]


class Music(commands.Cog):
    def __init__(self, bot):
        global gcmds
        self.bot = bot
        for func in [self.lavalink_setup, self.init_playlist, self.init_music]:
            self.bot.loop.create_task(func())
        gcmds = globalcommands.GlobalCMDS(self.bot)

    async def lavalink_setup(self):
        await self.bot.wait_until_ready()
        if not hasattr(self.bot, 'lavalink'):
            ip = gcmds.env_check("LAVALINK_IP")
            port = gcmds.env_check("LAVALINK_PORT")
            password = gcmds.env_check("LAVALINK_PASSWORD")
            if not all([ip, port, password]):
                print("Make sure your server IP, port, and password are in the .env file")
            else:
                self.bot.lavalink = lavalink.Client(self.bot.user.id)
                self.bot.lavalink.add_node(ip, port, password, 'na', 'default-node', name="lavalink")
                self.bot.add_listener(self.bot.lavalink.voice_update_handler, 'on_socket_response')

        lavalink.add_event_hook(self.track_hook)
        lavalink.add_event_hook(self.update_play)

    def cog_unload(self):
        self.bot.lavalink._event_hooks.clear()

    async def cog_check(self, ctx):
        if ctx.command.name.lower() == "bind":
            return True
        return await context.music_bind(ctx)

    async def init_music(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS music(guild_id bigint PRIMARY KEY, "
                              "channel_id bigint, panel_id bigint, counter_id bigint)")
        return

    async def init_playlist(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS playlists(id SERIAL, user_id bigint, playlist_name text PRIMARY KEY, urls text[])")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot or not reaction.message.guild or not user.voice or reaction.emoji not in reactions:
            return

        player = self.bot.lavalink.player_manager.get(reaction.message.guild.id)
        if not player or not user.voice.channel.id == int(player.fetch('channel')):
            return

        guild_id = reaction.message.guild.id

        if reaction.message.channel.id != await self.fetch_stored(guild_id, 'channel_id'):
            return

        if reaction.message.id != await self.fetch_stored(guild_id, 'panel_id'):
            return

        with suppress(Exception):
            message = reaction.message
            channel = message.channel
            voice_channel = user.voice.channel
            if await self.check_reaction(reaction, voice_channel):
                if reaction.emoji == "⏹":
                    await self.reacted_stop(guild_id, player, channel, user)
                    with suppress(Exception):
                        await message.delete()
                elif reaction.emoji == "⏪":
                    queue = player.fetch("queue", [])
                    await self.reacted_rewind(guild_id, player, queue, channel, user)
                elif reaction.emoji == "⏯":
                    paused = player.fetch("paused", False)
                    await self.reacted_paused(guild_id, player, message, paused, channel, user)
                elif reaction.emoji == "⏩":
                    await self.reacted_fowards(guild_id, player, channel, user)
                    with suppress(Exception):
                        await message.delete()
            return await self.adjust_counter(message, voice_channel)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        if user.bot or not reaction.message.guild or not user.voice or reaction.emoji not in reactions:
            return

        player = self.bot.lavalink.player_manager.get(reaction.message.guild.id)
        if not player or not user.voice.channel.id == int(player.fetch('channel')):
            return

        guild_id = reaction.message.guild.id

        if reaction.message.channel.id != await self.fetch_stored(guild_id, "channel_id"):
            return

        if reaction.message.id != await self.fetch_stored(guild_id, 'panel_id'):
            return

        with suppress(Exception):
            message = reaction.message
            return await self.adjust_counter(message, user.voice.channel)

    async def adjust_counter(self, message: discord.Message, voice_channel: discord.VoiceChannel):
        description = "\n".join(["{} ⟶ {} / {} required votes".format(
            reaction.emoji, reaction.count - 1, int(math.ceil((len(voice_channel.members) - 1) / 2)))
            for reaction in message.reactions])
        counter_message_id = await self.fetch_stored(message.guild.id, 'counter_id')
        counter_message = await message.channel.fetch_message(counter_message_id)
        embed = counter_message.embeds[0]
        embed.description = description
        return await counter_message.edit(embed=embed)

    async def check_reaction(self, reaction: discord.Reaction, channel: discord.VoiceChannel):
        raw_count = int(reaction.count) - 1
        min_count = (len(channel.members) - 1) / 2
        if raw_count >= math.ceil(min_count):
            async for user in reaction.users():
                if user.id != self.bot.user.id:
                    await reaction.message.remove_reaction(reaction.emoji, user)
            return True
        else:
            return False

    async def reacted_stop(self, guild_id: int, player, channel: discord.TextChannel, user: discord.User):
        await self.del_temp_msgs(guild_id)
        stopped = discord.Embed(title="Player Stopped",
                                description=f"{user.mention}, I have stoppped the music player and "
                                f"cleared the queue",
                                color=discord.Color.blue())
        stopped.set_footer(text=f"Executed by {user.display_name} " +
                           "at: {:%m/%d/%Y %H:%M:%S}".format(datetime.now()))
        return await channel.send(embed=stopped)

    async def reacted_rewind(self, guild_id: int, player, queue: list,
                             channel: discord.TextChannel, user: discord.User):
        if not queue:
            rewind = discord.Embed(title="No Tracks to Rewind",
                                   description=f"{user.mention}, there are no tracks to rewind to",
                                   color=discord.Color.dark_red())
            return await channel.send(embed=rewind, delete_after=10)
        else:
            index = len(queue) - len(player.queue) - 1
            if index - 1 < 0:
                rewind = discord.Embed(title="Rewind Failed",
                                       description=f"{user.mention}, this is the first song in queue",
                                       color=discord.Color.dark_red())
                return await channel.send(embed=rewind, delete_after=10)
            track = queue[index - 1]
            player.add(requester=user.id, track=player.current, index=0)
            player.add(requester=user.id, track=track, index=0)
            await player.stop()
            await player.play()

    async def reacted_paused(self, guild_id: int, player, message: discord.Message, paused: bool,
                             channel: discord.TextChannel):
        player.store("paused", not paused)
        await player.set_pause(not paused)
        embed = message.embeds[0]
        embed.title = "Player is Paused" if not paused else "Now Playing"
        return await message.edit(embed=embed)

    async def reacted_fowards(self, guild_id: int, player, channel: discord.TextChannel, user: discord.User):
        await player.skip()
        if not player.current:
            embed = discord.Embed(title="Ended Previous Track",
                                  description=f"{user.mention}, I have finished playing all songs "
                                  f"in queue",
                                  color=discord.Color.blue())
            return await channel.send(embed=embed)

    async def save_playlist(self, ctx, name: str, urls: list):
        async with self.bot.db.acquire() as con:
            if not urls:
                await con.execute(f"UPDATE playlists SET playlist_name = '{name}' WHERE name = '{(await self.get_playlist(ctx, name))[0][0]}'")
            else:
                values = f"({ctx.author.id}, '{name}', ARRAY['{', '.join(urls)}'])"
                await con.execute(f"INSERT INTO playlists(user_id, playlist_name, urls) VALUES {values}")

    async def append_playlist(self, ctx, name: str, url):
        async with self.bot.db.acquire() as con:
            if isinstance(url, list):
                for elem in list:
                    await con.execute(f"UPDATE playlists SET urls = array_append(urls, '{elem}') WHERE playlist_name = '{name}'")
            else:
                await con.execute(f"UPDATE playlists SET urls = array_append(urls, '{url}') WHERE playlist_name = '{name}'")

    async def get_playlist(self, ctx, key: str = None):
        async with self.bot.db.acquire() as con:
            if not key:
                result = await con.fetch(f"SELECT id, playlist_name, urls FROM playlists WHERE user_id = {ctx.author.id}")
            else:
                result = await con.fetch(f"SELECT id, playlist_name, urls FROM playlists WHERE user_id = {ctx.author.id} AND playlist_name = '{key}'")
            return [(record['playlist_name'], record['urls'], record['id']) for record in result] if result else None

    async def check_playlist(self, ctx, key: str, get_name=False):
        if get_name:
            playlist = await self.get_playlist(ctx, key)
            return (playlist[0], playlist[1]) if playlist else None
        else:
            return True if await self.get_playlist(ctx, key) else False

    async def remove_playlist(self, ctx, name: str):
        async with self.bot.db.acquire() as con:
            await con.execute(f"DELETE FROM playlists WHERE playlist_name = '{name}'")

    async def ensure_voice(self, ctx):
        player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
        should_connect = ctx.command.name == "play"

        if not ctx.author.voice or not ctx.author.voice.channel:
            not_conn = discord.Embed(title="Not In Voice Channel",
                                     description=f"{ctx.author.mention}, you must first join a voice channel",
                                     color=discord.Color.dark_red())
            await ctx.channel.send(embed=not_conn)
            return False

        if not player.is_connected:
            if should_connect:
                permissions = ctx.author.voice.channel.permissions_for(ctx.me)
                if not permissions.connect or not permissions.speak:
                    insuf = discord.Embed(title="Insufficient Bot Permissions",
                                          description=f"{ctx.author.mention}, please make sure I have the `connect` and "
                                                      f"`speak` permissions for that voice channel",
                                          color=discord.Color.dark_red())
                    await ctx.channel.send(embed=insuf)
                    return False
                player.store('channel', ctx.author.voice.channel.id)
                await self.connect_to(ctx.guild.id, str(ctx.author.voice.channel.id))
        else:
            if int(player.fetch('channel')) != ctx.author.voice.channel.id:
                diff = discord.Embed(title="Different Voice Channels",
                                     description=f"{ctx.author.mention}, make sure we're both in the same voice channel",
                                     color=discord.Color.dark_red())
                await ctx.channel.send(embed=diff)
                return False

        return True

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.QueueEndEvent):
            await self.connect_to(int(event.player.guild_id), None)
        elif isinstance(event, lavalink.events.NodeConnectedEvent):
            print(f"Connected to Lavalink Node \"{event.node.name}\"@{event.node.host}:{event.node.port}")
        elif isinstance(event, lavalink.events.NodeDisconnectedEvent):
            print(f"Disconnected from Node \"{event.node.name}\" with code {str(event.code)} because of {event.reason}")
        else:
            pass

    async def update_play(self, event):
        if isinstance(event, lavalink.events.TrackStartEvent):
            track = event.track
            embed = discord.Embed(title="Now Playing",
                                  color=discord.Color.blue())
            embed.description = f'[{track["title"]}](https://www.youtube.com/watch?v={track["identifier"]})'
            embed.set_image(url=f"http://img.youtube.com/vi/{track['identifier']}/maxresdefault.jpg")
            channel = await self.get_bound_channel(event.player.guild_id)
            voice_channel = await self.bot.fetch_channel(event.player.fetch("channel"))
            counter_desc = "\n".join(
                [f"{reaction} ⟶ 0 / {int(math.ceil((len(voice_channel.members) - 1) / 2))} required votes"
                 for reaction in reactions])
            counter = discord.Embed(description=counter_desc, color=discord.Color.blue())
            try:
                message = await channel.fetch_message(await self.fetch_stored(event.player.guild_id, "panel_id"))
                counter_message = await channel.fetch_message(await self.fetch_stored(message.guild.id, "counter_id"))
                await message.edit(embed=embed)
                await counter_message.edit(embed=counter)
            except Exception:
                message = await channel.send(embed=embed)
                counter_message = await channel.send(embed=counter)
                await self.set_value(message.guild.id, 'panel_id', message.id)
                await self.set_value(message.guild.id, 'counter_id', counter_message.id)
            await self.add_reaction_panel(message)
        if isinstance(event, lavalink.events.QueueEndEvent) or isinstance(event, lavalink.events.WebSocketClosedEvent):
            with suppress(Exception):
                await self.del_temp_msgs(event.player.guild_id)

    async def connect_to(self, guild_id: int, channel_id: str):
        ws = self.bot._connection._get_websocket(guild_id)
        await ws.voice_state(str(guild_id), channel_id)

    async def add_reaction_panel(self, message):
        with suppress(Exception):
            await message.clear_reactions()
            for reaction in reactions:
                await message.add_reaction(reaction)

    async def no_player(self, ctx):
        invalid = discord.Embed(title="No Music Player Instance",
                                description=f"{ctx.author.mention}, I don't have a music player instance started",
                                color=discord.Color.dark_red())
        return await ctx.channel.send(embed=invalid)

    async def not_owner(self, ctx):
        embed = discord.Embed(title="Not Server Owner",
                              description=f"{ctx.author.mention}, you must be the owner of this server to use this "
                                          f"command",
                              color=discord.Color.dark_red())
        await ctx.channel.send(embed=embed)

    async def set_value(self, guild_id: int, key: str, value=None):
        async with self.bot.db.acquire() as con:
            if key == "all":
                await con.execute(f"UPDATE music SET panel_id=NULL, counter_id=NULL WHERE guild_id={guild_id}")
            else:
                await con.execute(f"UPDATE music SET {key}={value} WHERE guild_id={guild_id}")

    async def fetch_stored(self, guild_id: int, key: str):
        async with self.bot.db.acquire() as con:
            if key == "all":
                results = await con.fetch(f"SELECT * FROM music where guild_id={guild_id}")
            else:
                results = await con.fetchval(f"SELECT {key} from music WHERE guild_id={guild_id}")
        return results

    async def set_bind_channel(self, guild_id: int, value: int):
        async with self.bot.db.acquire() as con:
            entry = await con.fetchval(f"SELECT guild_id FROM music WHERE guild_id={guild_id}")
            if not entry:
                op = f"INSERT INTO music(guild_id, channel_id) VALUES ({guild_id}, {value})"
            else:
                op = f"UPDATE music SET channel_id={value} WHERE guild_id={guild_id}"
            await con.execute(op)
        return

    async def get_bound_channel(self, guild_id):
        async with self.bot.db.acquire() as con:
            channel_id = await con.fetchval(f"SELECT channel_id FROM music WHERE guild_id={guild_id}")
        if not channel_id:
            raise customerrors.NoBoundChannel()
        return await self.bot.fetch_channel(channel_id)

    async def del_temp_msgs(self, guild_id: int):
        channel = await self.get_bound_channel(guild_id)
        with suppress(Exception):
            message = await channel.fetch_message(await self.fetch_stored(guild_id, "panel_id"))
            counter = await channel.fetch_message(await self.fetch_stored(guild_id, "counter_id"))
            await message.delete()
            await counter.delete()
        await self.set_value(guild_id, "all")
        player = self.bot.lavalink.player_manager.get(guild_id)
        player.queue.clear()
        player.store("paused", False)
        player.store("queue", [])
        await player.stop()

    @commands.command(desc="Binds the music commands to a channel",
                      usage="bind (channel)",
                      uperms=["Manage Server"],
                      note="If `(channel)` is not specified, the current channel will be used")
    async def bind(self, ctx, channel: discord.TextChannel = None):
        if not channel:
            channel = ctx.channel
        await self.set_bind_channel(ctx.guild.id, channel.id)
        embed = discord.Embed(title="Music Channel Bound",
                              description=f"The music channel was bound to {channel.mention}",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @commands.command(desc="Makes MarwynnBot join the same voice channel you're in",
                      usage="join",
                      note="You may only use this when you are connected to a voice channel")
    async def join(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
        if ctx.author.voice:
            player.store("channel", ctx.author.voice.channel.id)
            if not player.is_connected:
                await self.connect_to(ctx.guild.id, ctx.author.voice.channel.id)
                joinEmbed = discord.Embed(title="Successfully Joined Voice Channel",
                                          description=f"{ctx.author.mention}, I have joined {ctx.author.voice.channel.name}",
                                          color=discord.Color.blue())
                joinEmbed.set_thumbnail(url="https://vignette.wikia.nocookie.net/mario/images/0/04/Music_Toad.jpg"
                                            "/revision/latest/top-crop/width/500/height/500?cb=20180812231020")
                joinEmbed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
                await ctx.channel.send(embed=joinEmbed)
                return
            elif ctx.author.voice.channel == ctx.guild.me.voice.channel:
                joinEmbed = discord.Embed(title="Already Connected to Voice Channel",
                                          description=f"{ctx.author.mention}, I'm already connected!",
                                          color=discord.Color.blue())
                joinEmbed.set_thumbnail(url="https://vignette.wikia.nocookie.net/mario/images/0/04/Music_Toad.jpg"
                                            "/revision/latest/top-crop/width/500/height/500?cb=20180812231020")
                joinEmbed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
                await ctx.channel.send(embed=joinEmbed)
                return
            else:
                await self.connect_to(ctx.guild.id, ctx.author.voice.channel.id)
                joinEmbed = discord.Embed(title="Successfully Moved Voice Channel",
                                          description=f"{ctx.author.mention}, I have moved to {ctx.author.voice.channel.name}",
                                          color=discord.Color.blue())
                joinEmbed.set_thumbnail(url="https://vignette.wikia.nocookie.net/mario/images/0/04/Music_Toad.jpg"
                                            "/revision/latest/top-crop/width/500/height/500?cb=20180812231020")
                joinEmbed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
                await ctx.channel.send(embed=joinEmbed)
                return
        else:
            joinError = discord.Embed(title="Error",
                                      description=f"{ctx.author.mention}, please join a voice channel to use this "
                                                  f"command",
                                      color=discord.Color.dark_red())
            await ctx.channel.send(embed=joinError)
            return

    @commands.command(desc="Makes MarwynnBot play a song or the current queue",
                      usage="play (query)",
                      note="If there are songs in queue, `(query)` can be unspecified to start playing "
                      "the first song in the queue")
    async def play(self, ctx, *, query: str = None):
        if not await self.ensure_voice(ctx):
            return
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if ctx.author.voice:
            if not player.is_connected:
                await self.connect_to(ctx.guild.id, ctx.author.voice.channel.id)
            if not query:
                if player.queue:
                    if not player.is_playing:
                        await player.play()
                        return
                else:
                    noqueue = discord.Embed(title="Nothing in Queue",
                                            description=f"{ctx.author.mention}, please add a song to the queue to "
                                                        f"start playing",
                                            color=discord.Color.dark_red())
                    await ctx.channel.send(embed=noqueue)
                    return

        query = query.strip('<>')

        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        results = await player.node.get_tracks(query)

        if not results or not results['tracks']:
            notFound = discord.Embed(title="Nothing Found",
                                     description=f"{ctx.author.mention}, I couldn't find anything for *{query}*",
                                     color=discord.Color.dark_red())
            await ctx.channel.send(embed=notFound)
            return

        embed = discord.Embed(color=discord.Color.blue())

        queue = player.fetch("queue", [])

        # Valid loadTypes are:
        #   TRACK_LOADED    - single video/direct URL)
        #   PLAYLIST_LOADED - direct URL to playlist)
        #   SEARCH_RESULT   - query prefixed with either ytsearch: or scsearch:.
        #   NO_MATCHES      - query yielded no results
        #   LOAD_FAILED     - most likely, the video encountered an exception during loading.
        if results['loadType'] == 'PLAYLIST_LOADED':
            tracks = results['tracks']
            tracklist = []
            for track in tracks:
                tracklist.append(f"**{len(tracklist) + 1}:** [{track['info']['title']}]({track['info']['uri']})")
                player.add(requester=ctx.author.id, track=track)
                queue.append(track)

            embed.title = 'Playlist Queued!'
            embed.description = f'**[{results["playlistInfo"]["name"]}]({query})** - {len(tracks)} tracks:\n\n' + \
                                "\n".join(tracklist)
            embed.set_image(url=f"http://img.youtube.com/vi/{tracks[0]['info']['identifier']}/maxresdefault.jpg")
            embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
        else:
            track = results['tracks'][0]
            embed.title = 'Track Queued'
            embed.description = f'[{track["info"]["title"]}]({track["info"]["uri"]})'
            embed.set_image(url=f"http://img.youtube.com/vi/{track['info']['identifier']}/maxresdefault.jpg")
            embed.set_footer(text=f"Author: {track['info']['author']}\nRequested by: {ctx.author.display_name}",
                             icon_url=ctx.author.avatar_url)

            track = lavalink.models.AudioTrack(track, ctx.author.id, recommended=True)
            player.add(requester=ctx.author.id, track=track)
            queue.append(track)

        if not player.is_playing:
            await player.play()
        else:
            await ctx.channel.send(embed=embed)

    @commands.command(desc="List the current queue or queue a song",
                      usage="queue (query)")
    async def queue(self, ctx, *, query: str = None):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await self.no_player(ctx)

        if query is not None:
            if ctx.author.voice:
                if not player.is_connected:
                    notConn = discord.Embed(title="Error",
                                            description=f"{ctx.author.mention}, I must be connected to a voice "
                                                        f"channel to be able to add songs to the queue",
                                            color=discord.Color.dark_red())
                    await ctx.channel.send(embed=notConn)
                    return
                else:
                    query = query.strip('<>')

                    if not url_rx.match(query):
                        query = f'ytsearch:{query}'

                    results = await player.node.get_tracks(query)

                    if not results or not results['tracks']:
                        notFound = discord.Embed(title="Nothing Found",
                                                 description=f"{ctx.author.mention}, I couldn't find anything for *{query}*",
                                                 color=discord.Color.dark_red())
                        await ctx.channel.send(embed=notFound)
                        return

                    embed = discord.Embed(color=discord.Color.blue())

                    queue = player.fetch("queue", [])

                    # Valid loadTypes are:
                    #   TRACK_LOADED    - single video/direct URL)
                    #   PLAYLIST_LOADED - direct URL to playlist)
                    #   SEARCH_RESULT   - query prefixed with either ytsearch: or scsearch:.
                    #   NO_MATCHES      - query yielded no results
                    #   LOAD_FAILED     - most likely, the video encountered an exception during loading.
                    if results['loadType'] == 'PLAYLIST_LOADED':
                        tracks = results['tracks']
                        tracklist = []
                        for track in tracks:
                            tracklist.append(
                                f"**{len(tracklist) + 1}:** [{track['info']['title']}]({track['info']['uri']})")
                            player.add(requester=ctx.author.id, track=track)
                            queue.append(track)

                        embed.title = 'Playlist Queued!'
                        embed.description = f'**[{results["playlistInfo"]["name"]}]({query})** - {len(tracks)} tracks' \
                                            f':\n\n' + "\n".join(tracklist)
                        embed.set_image(
                            url=f"http://img.youtube.com/vi/{tracks[0]['info']['identifier']}/maxresdefault.jpg")
                        embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
                    else:
                        track = results['tracks'][0]
                        embed.title = 'Track Queued'
                        embed.description = f'[{track["info"]["title"]}]({track["info"]["uri"]})'
                        embed.set_image(
                            url=f"http://img.youtube.com/vi/{track['info']['identifier']}/maxresdefault.jpg")
                        embed.set_footer(
                            text=f"Author: {track['info']['author']}\nRequested by: {ctx.author.display_name}",
                            icon_url=ctx.author.avatar_url)

                        track = lavalink.models.AudioTrack(track, ctx.author.id, recommended=True)
                        player.add(requester=ctx.author.id, track=track)
                        queue.append(track)

                    try:
                        message = await ctx.channel.fetch_message(await self.fetch_stored(ctx.guild.id, "panel_id"))
                        await message.edit(embed=embed)
                    except Exception:
                        message = await ctx.channel.send(embed=embed)
                        await self.set_value(ctx.guild.id, 'panel_id', message.id)
            else:
                notConn = discord.Embed(title="Error",
                                        description=f"{ctx.author.mention}, you must be connected to a voice channel "
                                                    f"to be able to add songs to the queue",
                                        color=discord.Color.dark_red())
                await ctx.channel.send(embed=notConn)
                return
        else:
            if player.is_playing:
                description = [
                    f"**Now Playing:** [{player.current['title']}](https://www.youtube.com/watch?=v{player.current['identifier']})\n\n**Queue"
                    ":**\n"]
            else:
                description = []
            index = 0
            q_amt = len(player.queue)
            if q_amt == 0:
                title_append = ""
            elif q_amt == 1:
                title_append = ": 1 Track"
            else:
                title_append = f": {q_amt} Tracks"
            embed = discord.Embed(title=f"Current Queue{title_append}",
                                  color=discord.Color.blue())

            if not player.queue:
                description.append("Nothing queued")
            for item in player.queue:
                description.append(f"**{index + 1}**: [{item['title']}]"
                                   f"(https://www.youtube.com/watch?v={item['identifier']})\n")
                index += 1

            embed.description = "".join(description)

            return await ctx.channel.send(embed=embed)

    @commands.command(aliases=['clearqueue', 'qc'],
                      desc="Clears the current queue",
                      usage="queueclear",
                      uperms=["Manage Server"])
    @commands.has_permissions(manage_guild=True)
    async def queueclear(self, ctx):
        if ctx.author != ctx.guild.owner:
            return await self.not_owner(ctx)

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await self.no_player(ctx)

        if not player.queue:
            no_queue = discord.Embed(title="Nothing in Queue",
                                     description=f"{ctx.author.mention}, there is already nothing in my queue",
                                     color=discord.Color.dark_red())
            return await ctx.channel.send(embed=no_queue)

        player.queue.clear()
        player.store("queue", [])

        cleared = discord.Embed(title="Queue Cleared",
                                description=f"{ctx.author.mention}, I have cleared the current queue",
                                color=discord.Color.blue())

        return await ctx.channel.send(embed=cleared)

    @commands.command(desc="Stops music playback",
                      usage="stop",
                      uperms=["Manage Server"])
    @commands.has_permissions(manage_guild=True)
    async def stop(self, ctx):
        if ctx.author != ctx.guild.owner:
            return await self.not_owner(ctx)

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await self.no_player(ctx)

        if not player.is_connected:
            invalid = discord.Embed(title="Error",
                                    description=f"{ctx.author.mention}, I am not currently in a voice channel",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            invalid = discord.Embed(title="Error",
                                    description=f"{ctx.author.mention}, you can only execute this command when you "
                                                f"are connected to the same voice channel as I am",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)
        if not player.queue and not player.is_playing:
            invalid = discord.Embed(title="Error",
                                    description=f"{ctx.author.mention}, my queue is empty",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        await self.del_temp_msgs(ctx.guild.id)

        stopped = discord.Embed(title="Player Stopped",
                                description=f"{ctx.author.mention}, I have stoppped the music player and cleared the "
                                            f"queue",
                                color=discord.Color.blue())
        return await ctx.channel.send(embed=stopped)

    @commands.command(desc="Makes MarwynnBot leave the voice channel it is currently in",
                      usage="leave")
    async def leave(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await self.no_player(ctx)

        if not player.is_connected:
            invalid = discord.Embed(title="Error",
                                    description=f"{ctx.author.mention}, I am not currently in a voice channel",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            invalid = discord.Embed(title="Error",
                                    description=f"{ctx.author.mention}, you can only execute this command when you "
                                                f"are connected to the same voice channel as I am",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        await self.connect_to(ctx.guild.id, None)
        await self.del_temp_msgs(ctx.guild.id)

        disconnected = discord.Embed(title="Disconnected",
                                     color=discord.Color.blue())
        disconnected.set_thumbnail(url="https://i.pinimg.com/originals/56/3d/72/563d72539bbd9fccfbb427cfefdee05a"
                                       ".png")
        disconnected.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        return await ctx.channel.send(embed=disconnected)

    @commands.command(desc="Adjusts the music player volume",
                      usage="volume (1-100)")
    async def volume(self, ctx, amount: int = None):
        if not await self.ensure_voice(ctx):
            return
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await self.no_player(ctx)

        if amount:
            if 1 <= amount <= 100:
                await player.set_volume(amount)
                embed = discord.Embed(title="Current Player Volume",
                                      description=f"Current player volume set to: {player.volume}/100",
                                      color=discord.Color.blue())
            else:
                embed = discord.Embed(title="Invalid Volume Setting",
                                      description=f"{ctx.author.mention}, the volume must be between 1 and 100",
                                      color=discord.Color.blue())
        else:
            embed = discord.Embed(title="Current Player Volume",
                                  description=f"Current player volume set to: {player.volume}/100",
                                  color=discord.Color.blue())

        return await ctx.channel.send(embed=embed)

    @premium.is_premium()
    @commands.group(invoke_without_command=True,
                    aliases=['playlists'],
                    desc="Shows all your saved playlists",
                    usage="playlist (subcommand)",
                    note="This is a premium only feature. Valid `(subcommand)` are "
                    "\"load\", \"save\", \"add\", and \"remove\"")
    async def playlist(self, ctx):
        playlists = await self.get_playlist(ctx, None)
        if not playlists:
            no_plist = discord.Embed(title="No Playlists",
                                     description=f"{ctx.author.mention}, you have not made any playlists yet.",
                                     color=discord.Color.dark_red())
            return await ctx.channel.send(embed=no_plist)

        details = await self.get_playlist(ctx, None)

        length = len(details)
        if length != 1:
            spell = "playlists"
        else:
            spell = "playlist"
        index = 0

        description = f"{ctx.author.mention}, you have 💽**{length}** {spell}:\n\n"
        for name, url, plist_id in details:
            index += 1
            if len(url) != 1:
                spell = "tracks"
            else:
                spell = "track"
            description += f"**{index}:** {name} ⟶ 🎶*{len(url)} {spell}* [ID: {plist_id}]\n"

        playlist_embed = discord.Embed(title=f"{ctx.author.display_name}'s Saved Playlists",
                                       description=description,
                                       color=discord.Color.blue())
        await ctx.channel.send(embed=playlist_embed)

    @playlist.command()
    async def load(self, ctx, *, playlist_name: str = None):
        if not playlist_name:
            no_name = discord.Embed(title="No Playlist Specified",
                                    description=f"{ctx.author.mention}, please specify a valid playlist name. Do `{await gcmds.prefix(ctx)}playlist` to get a list of your currently saved playlists",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=no_name)

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await self.no_player(ctx)

        if not player.is_connected:
            invalid = discord.Embed(title="Error",
                                    description=f"{ctx.author.mention}, I am not currently in a voice channel",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            invalid = discord.Embed(title="Error",
                                    description=f"{ctx.author.mention}, you can only execute this command when you "
                                                f"are connected to the same voice channel as I am",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid)

        if not await self.get_playlist(ctx, None):
            no_plist = discord.Embed(title="No Playlists",
                                     description=f"{ctx.author.mention}, you have not made any playlists yet.",
                                     color=discord.Color.dark_red())
            return await ctx.channel.send(embed=no_plist)

        details = await self.get_playlist(ctx, playlist_name)
        if not details:
            no_plist = discord.Embed(title="Invalid Playlist",
                                     description=f"{ctx.author.mention}, you don't have any playlists named **{playlist_name}**",
                                     color=discord.Color.dark_red())
            return await ctx.channel.send(embed=no_plist)

        for url in details[0][1]:
            results = await player.node.get_tracks(url)
            track = results['tracks'][0]
            track = lavalink.models.AudioTrack(track, ctx.author.id, recommended=True)
            player.add(requester=ctx.author.id, track=track)
            queue = player.fetch("queue", [])
            player.store("queue", queue.append(track))

        loaded = discord.Embed(title="Playlist Loaded",
                               description=f"{ctx.author.mention}, I have loaded all tracks to queue from **{playlist_name}**",
                               color=discord.Color.blue())
        return await ctx.channel.send(embed=loaded)

    @playlist.command(aliases=['edit'])
    async def save(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        queue = player.fetch("queue", [])

        if not queue:
            no_queue = discord.Embed(title="No Queue Available for Saving",
                                     description=f"{ctx.author.mention}, I cannot save an empty queue as a playlist",
                                     color=discord.Color.dark_red())
            return await ctx.channel.send(embed=no_queue)

        urls = [f"https://www.youtube.com/watch?v={item['identifier']}" for item in queue]

        panel = discord.Embed(title="Playlist Save Confirmation",
                              description=f"{ctx.author.mention}, do you want to save or edit a playlist?\n"
                                          f"React with {plist_reactions[0]} to save, or {plist_reactions[1]} to edit",
                              color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel)

        no_panel = discord.Embed(title="Playlist Setup Panel Not Found",
                                 description=f"{ctx.author.mention}, the playlist setup panel was deleted. Playlist "
                                             f"saving was cancelled",
                                 color=discord.Color.dark_red())

        for reaction in plist_reactions:
            await panel.add_reaction(reaction)

        def reaction_check(reaction, user):
            if user == ctx.author and reaction.emoji in plist_reactions and reaction.message.id == panel.id:
                return True
            else:
                return False

        def from_user(message):
            if message.author == ctx.author:
                return True
            else:
                return False

        while True:
            try:
                try:
                    panel_message = await ctx.channel.fetch_message(panel.id)
                except discord.NotFound:
                    return await ctx.channel.send(embed=no_panel)
                choice = await self.bot.wait_for("reaction_add", check=reaction_check,
                                                 timeout=30)
            except asyncio.TimeoutError:
                timeout = discord.Embed(title="Save Request Timed Out",
                                        description=f"{ctx.author.mention}, your save request timed out. Please try again",
                                        color=discord.Color.blue())
                return await panel.edit(embed=timeout)
            else:
                if str(choice[0].emoji) == plist_reactions[0]:
                    await panel.clear_reactions()
                    action = "save"
                    break
                elif str(choice[0].emoji) == plist_reactions[1]:
                    await panel.clear_reactions()
                    action = "edit"
                    break
                else:
                    continue

        details = await self.get_playlist(ctx, None)

        if not details or action == "save":
            try:
                embed = discord.Embed(title="Specify the Playlist Name",
                                      description=f"{ctx.author.mention}, please specify what the playlist name should be",
                                      color=discord.Color.blue())
                await panel.edit(embed=embed)
            except discord.NotFound:
                await ctx.channel.send(embed=no_panel)
            while True:
                try:
                    reply = await self.bot.wait_for("message", check=from_user, timeout=30)
                except asyncio.TimeoutError:
                    timeout = discord.Embed(title="Save Request Timed Out",
                                            description=f"{ctx.author.mention}, you did not specify a name within the "
                                                        f"time limit",
                                            color=discord.Color.blue())
                    return await panel.edit(embed=timeout)
                else:
                    break
            await gcmds.smart_delete(reply)

            embed = discord.Embed(color=discord.Color.blue())
            plist_name = reply.content
            embed.title = "Saved Playlist"
            embed.description = f"💽Playlist Name: {plist_name}\n🎶Tracks: {len(queue)}"
            try:
                await panel.edit(embed=embed)
                await self.save_playlist(ctx, plist_name, urls)
            except discord.NotFound:
                return await ctx.channel.send(embed=no_panel)
        else:
            edit_desc = "💽**Playlists:**\n\n"
            for counter, item in enumerate(details, 1):
                if len(item[1]) != 1:
                    spell = "tracks"
                else:
                    spell = "track"
                edit_desc += f"**{counter}**: {item[0]} ⟶ 🎶*{len(item[1])} {spell}* [ID: {item[2]}]\n"
            try:
                embed = discord.Embed(title="Specify the Playlist Name",
                                      description=f"{ctx.author.mention}, type the name of the playlist you want to "
                                      f"edit:\n\n{edit_desc}",
                                      color=discord.Color.blue())
                await panel.edit(embed=embed)
            except discord.NotFound:
                return await ctx.channel.send(embed=no_panel)
            while True:
                try:
                    reply = await self.bot.wait_for("message", check=from_user, timeout=30)
                except asyncio.TimeoutError:
                    timeout = discord.Embed(title="Save Request Timed Out",
                                            description=f"{ctx.author.mention}, you did not specify a name within the "
                                                        f"time limit",
                                            color=discord.Color.blue())
                    return await panel.edit(embed=timeout)
                else:
                    info = await self.check_playlist(ctx, reply.content, get_name=True)
                    if not info:
                        continue
                    break
            await gcmds.smart_delete(reply)
            try:
                embed = discord.Embed(title="Change Playlist Name",
                                      description=f"{ctx.author.mention}, please specify what the playlist name "
                                      f"should be *(enter \"skip\" to keep the playlist's current "
                                      f"name)*\n\n**Current Name:** {info[0]}",
                                      color=discord.Color.blue())
                await panel.edit(embed=embed)
            except discord.NotFound:
                await ctx.channel.send(embed=no_panel)
            while True:
                try:
                    name_reply = await self.bot.wait_for("message", check=from_user, timeout=30)
                except asyncio.TimeoutError:
                    timeout = discord.Embed(title="Save Request Timed Out",
                                            description=f"{ctx.author.mention}, you did not specify a name within the "
                                                        f"time limit",
                                            color=discord.Color.blue())
                    return await panel.edit(embed=timeout)
                else:
                    break
            await gcmds.smart_delete(name_reply)
            if name_reply.content != "skip":
                plist_name = name_reply.content
                await self.save_playlist(ctx, plist_name, urls)

            else:
                plist_name = info[0]

            info = await self.get_playlist(ctx, plist_name)

            if len(info[0][1]) != 1:
                spell = "tracks"
            else:
                spell = "track"
            edited_plist = discord.Embed(title="Successfully Edited Playlist",
                                         description=f"{ctx.author.mention}, your playlist has been "
                                                     f"edited:\n\n💽**Playlist Name:** {info[0][0]}\n"
                                                     f"🎶**Track Count:** {len(info[0][1])} {spell}\n"
                                                     f"**ID:** {info[0][2]}",
                                         color=discord.Color.blue())
            try:
                await panel.edit(embed=edited_plist)
            except discord.NotFound:
                await ctx.channel.send(embed=edited_plist)

    @playlist.command()
    async def add(self, ctx):

        def from_user(message):
            if message.author.id != ctx.author.id:
                return False
            else:
                return True

        playlists = ""
        index = 1
        details = await self.get_playlist(ctx, None)
        for name, url, playlist_id in details:
            if len(url) != 1:
                spell = "tracks"
            else:
                spell = "track"
            playlists += f"**{index}**: {name} ⟶ 🎶*{len(url)} {spell}* [ID: {playlist_id}]\n"
            index += 1

        panel_embed = discord.Embed(title="Add Tracks to Playlist",
                                    description=f"{ctx.author.mention}, type the name of the playlist you would like "
                                                f"to add tracks to *(or type \"cancel\" to cancel)*\n\n{playlists}",
                                    color=discord.Color.blue())
        timeout = discord.Embed(title="Playlist Edit Timed Out",
                                description=f"{ctx.author.mention}, your add tracks request timed out",
                                color=discord.Color.dark_red())
        cancelled = discord.Embed(title="Add Tracks Cancelled",
                                  description=f"{ctx.author.mention}, your add tracks request was cancelled",
                                  color=discord.Color.dark_red())
        invalid = discord.Embed(title="Invalid Link",
                                description=f"{ctx.author.mention}, your link was not a valid YouTube link",
                                color=discord.Color.dark_red())
        panel = await ctx.channel.send(embed=panel_embed)

        while True:
            try:
                message = await self.bot.wait_for("message", check=from_user, timeout=30)
            except asyncio.TimeoutError:
                try:
                    return await panel.edit(embed=timeout)
                except discord.NotFound:
                    return await ctx.channel.send(embed=timeout)
            else:
                if message.content == "cancel":
                    try:
                        return await panel.edit(embed=cancelled)
                    except discord.NotFound:
                        return await ctx.channel.send(embed=cancelled)
                elif not await self.check_playlist(ctx, message.content):
                    continue
                else:
                    name = message.content
                    break
        await gcmds.smart_delete(message)

        try:
            panel_embed.description = f"{ctx.author.mention}, please enter a YouTube video link or a YouTube playlist " \
                                      f"link that you would like to have added to {name} "
            await panel.edit(embed=panel_embed)
        except discord.NotFound:
            return await ctx.channel.send(embed=cancelled)

        try:
            message_link = await self.bot.wait_for("message", check=from_user, timeout=30)
        except asyncio.TimeoutError:
            try:
                return await panel.edit(embed=timeout)
            except discord.NotFound:
                return await ctx.channel.send(embed=timeout)
        else:
            yt_link = message_link.content
            await gcmds.smart_delete(message_link)

        if not url_rx.match(yt_link) or "youtube.com" not in yt_link:
            try:
                return await panel.edit(embed=invalid)
            except discord.NotFound:
                return await ctx.channel.send(embed=invalid)
        else:
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            if not player:
                player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
            results = await player.node.get_tracks(yt_link)
            tracks = results['tracks']
            if results['loadType'] == 'PLAYLIST_LOADED':
                info = [(track['info']['title'], track['info']['uri']) for track in tracks]
                urls = [track['info']['uri'] for track in tracks]
                await self.append_playlist(ctx, name, urls)
                tracks_added = ""
                index = 1
                for title, url in info:
                    tracks_added += f"**{index}:** [{title}]({url})\n"
                    index += 1
                panel_embed.description = f"Added the following tracks to {name}:\n{tracks_added}"
            else:
                url = tracks[0]['info']['uri']
                title = tracks[0]['info']['title']
                await self.append_playlist(ctx, name, url)
                panel_embed.description = f"Added the following track to {name}:\n**1:** [{title}]({url})"

            try:
                await panel.edit(embed=panel_embed)
            except discord.NotFound:
                await ctx.channel.send(embed=panel_embed)

    @playlist.command(aliases=['delete'])
    async def remove(self, ctx):

        def reaction_check(reaction, user):
            if user == ctx.author and reaction.emoji in plist_delete_reactions and reaction.message.id == panel.id:
                return True
            else:
                return False

        def from_user(message):
            if message.author == ctx.author:
                return True
            else:
                return False

        details = await self.get_playlist(ctx, None)

        if not details:
            no_plist = discord.Embed(title="No Playlists",
                                     description=f"{ctx.author.mention}, you have not made any playlists yet.",
                                     color=discord.Color.dark_red())
            return await ctx.channel.send(embed=no_plist)

        user_playlists = f"{ctx.author.mention}, type the name of the playlist you want to delete *(type \"cancel\" " \
                         f"to cancel)*:\n\n "
        for counter, item in enumerate(details, 1):
            if len(item[1]) != 1:
                spell = "tracks"
            else:
                spell = "track"
            user_playlists += f"**{counter}:** {item[0]} ⟶ 🎶*{len(item[1])} {spell}* [ID: {item[2]}]\n"

        embed = discord.Embed(title="Delete Playlist",
                              description=user_playlists,
                              color=discord.Color.blue())
        panel = await ctx.channel.send(embed=embed)

        no_panel = discord.Embed(title="Playlist Remove Panel Deleted",
                                 description=f"{ctx.author.mention}, the remove playlist panel was deleted",
                                 color=discord.Color.dark_red())

        while True:
            try:
                try:
                    panel_message = await ctx.channel.fetch_message(panel.id)
                except discord.NotFound:
                    return await ctx.channel.send(embed=no_panel)
                choice = await self.bot.wait_for("message", check=from_user, timeout=30)
            except asyncio.TimeoutError:
                timeout = discord.Embed(title="Remove Request Timed Out",
                                        description=f"{ctx.author.mention}, you did not specify a name within the "
                                                    f"time limit",
                                        color=discord.Color.blue())
                return await panel.edit(embed=timeout)
            else:
                if choice.content.lower() == "cancel":
                    cancelled = discord.Embed(title="Remove Request Cancelled",
                                              description=f"{ctx.author.mention}, you cancelled the remove request",
                                              color=discord.Color.blue())
                    return await panel.edit(embed=cancelled)
                valid = False
                for name, urls, playlist_id in details:
                    if choice.content == name:
                        name = choice.content
                        valid = True
                        break
                if valid:
                    break
                continue
        await gcmds.smart_delete(choice)

        embed.description = "React with ✅ to confirm or 🛑 to cancel playlist deletion"

        while True:
            try:
                try:
                    panel_message = await ctx.channel.fetch_message(panel.id)
                    await panel_message.edit(embed=embed)
                    for reaction in plist_delete_reactions:
                        await panel.add_reaction(reaction)
                except discord.NotFound:
                    return await ctx.channel.send(embed=no_panel)
                reacted = await self.bot.wait_for("reaction_add", check=reaction_check,
                                                  timeout=30)
            except asyncio.TimeoutError:
                timeout = discord.Embed(title="Remove Request Timed Out",
                                        description=f"{ctx.author.mention}, you did not react within the time limit",
                                        color=discord.Color.blue())
                return await panel.edit(embed=timeout)
            else:
                if str(reacted[0].emoji) == plist_delete_reactions[0]:
                    await panel.clear_reactions()
                    action = "confirm"
                    break
                elif str(reacted[0].emoji) == plist_delete_reactions[1]:
                    await panel.clear_reactions()
                    action = "cancel"
                    break
                else:
                    continue

        if action == "confirm":
            test = await self.remove_playlist(ctx, name)
            edited = discord.Embed(title="Deleted Playlist",
                                   description=f"{ctx.author.mention}, your playlist *\"{name}\"* was deleted",
                                   color=discord.Color.blue())
            try:
                return await panel.edit(embed=edited)
            except discord.NotFound:
                return await ctx.channel.send(embed=edited)
        try:
            await panel.edit(embed=no_panel)
        except discord.NotFound:
            await ctx.channel.send(embed=no_panel)


def setup(bot):
    bot.add_cog(Music(bot))
