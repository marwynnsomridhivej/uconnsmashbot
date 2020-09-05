import asyncio
import json
import os
import base64
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
from dateparser.search import search_dates
from globalcommands import GlobalCMDS
import re


gcmds = GlobalCMDS()
timeout = 30
reactions = ["🔁", "✅", "🛑"]
channel_tag_rx = re.compile(r'<#[0-9]{18}>')
channel_id_rx = re.compile(r'[0-9]{18}')


class Reminders(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.check_single.start()
        self.check_loop.start()

    def cog_unload(self):
        self.check_single.cancel()
        self.check_loop.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Cog "{self.qualified_name}" has been loaded')

    @tasks.loop(seconds=15)
    async def check_single(self):
        with open('db/reminders.json', 'r') as f:
            file = json.load(f)
            f.close()
        for guild in file:
            for user in file[str(guild)]:
                index = 0
                for reminder in file[str(guild)][str(user)]:
                    if reminder['type'] == "single":
                        if reminder['time'] - datetime.now().timestamp() <= 15.0:
                            message_content_ascii = base64.urlsafe_b64decode(
                                str.encode(reminder['message_content']))
                            message_content = message_content_ascii.decode(
                                "ascii")
                            user_id = int(user)
                            sleep_time = reminder['time'] - \
                                datetime.now().timestamp()
                            if sleep_time <= 0:
                                sleep_time = 0
                            await asyncio.create_task(self.send_single(sleep_time, user_id, reminder['channel_id'],
                                                                       message_content, int(guild), index, file))
                    index += 1

    async def send_single(self, sleep_time: float, user_id: int, channel_id: int, message_content: str, guild_id: int,
                          index: int, file: dict):
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        try:
            channel = await commands.AutoShardedBot.fetch_channel(self.client, channel_id)
            user = await channel.guild.fetch_member(user_id)
            embed = discord.Embed(title=f"Reminder for {user.display_name}",
                                  description=message_content,
                                  color=discord.Color.blue())
            await channel.send(f"{user.mention}")
            await channel.send(embed=embed)
            del file[str(guild_id)][str(user_id)][index]
            if len(file[str(guild_id)][str(user_id)]) == 0:
                del file[str(guild_id)][str(user_id)]
            if len(file[str(guild_id)]) == 0:
                del file[str(guild_id)]
            with open('db/reminders.json', 'w') as f:
                json.dump(file, f, indent=4)
        except (discord.Forbidden, discord.HTTPException, discord.InvalidData, discord.NotFound):
            pass

    @tasks.loop(seconds=1, count=1)
    async def check_loop(self):
        with open('db/reminders.json', 'r') as f:
            file = json.load(f)
            f.close()
        for guild in file:
            for user in file[str(guild)]:
                for reminder in file[str(guild)][str(user)]:
                    if reminder['type'] == "loop":
                        message_content_ascii = base64.urlsafe_b64decode(
                            str.encode(reminder['message_content']))
                        message_content = message_content_ascii.decode("ascii")
                        await asyncio.create_task(self.send_loop(reminder['time'], int(user), reminder['channel_id'],
                                                                 message_content, int(guild)))

    async def send_loop(self, loop_interval: int, user_id: int, channel_id: int, message_content: str, guild_id: int):
        while True:
            await asyncio.sleep(1.0)
            if int(datetime.now().timestamp()) % int(loop_interval) == 0:
                try:
                    channel = await commands.AutoShardedBot.fetch_channel(self.client, channel_id)
                    user = await channel.guild.fetch_member(user_id)
                    embed = discord.Embed(title=f"Reminder for {user.display_name}",
                                          description=message_content,
                                          color=discord.Color.blue())
                    await channel.send(f"{user.mention}")
                    await channel.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException, discord.InvalidData, discord.NotFound):
                    pass
            else:
                continue

    async def send_remind_help(self, ctx) -> discord.Message:
        embed = discord.Embed(title="Reminders Help",
                              description=f"To use reminder commands, just do `?remind ["
                                          f"option]`. Here is a list of valid options",
                              color=discord.Color.blue())
        embed.add_field(name="Create",
                        value=f"Usage: `?remind [message_with_time]`\n"
                              f"Returns: Your reminder message at the specified time\n"
                              f"Aliases: `reminder`\n"
                              f"Special Cases: You must specify a time within your message, whether it be exact or "
                              f"relative",
                        inline=False)
        embed.add_field(name="Edit",
                        value=f"Usage: `?remind edit`\n"
                              f"Returns: An interactive reminder edit panel\n"
                              f"Aliases: `-e`\n"
                              f"Special Cases: You must have at least one reminder queued\n\n*An error may occur if the " \
                              f"reminder fires while you are in the middle of editing it. It may also end up firing " \
                              f"twice if you edit it within 15 seconds of it's firing time*",
                        inline=False)
        embed.add_field(name="Delete",
                        value=f"Usage: `?remind delete`\n"
                        f"Returns: An interactive reminder delete panel\n"
                        f"Aliases: `-rm` `trash`\n"
                        f"Special Cases: You must have at least one reminder queued in that server\n\n*An error may " \
                        f"occur if the reminder fires while you are in the middle of deleting it. If you proceed, it " \
                        f"may display that the deletion was unsuccessful. It's entry has already been deleted from " \
                        f"the database after it was fired*")
        return await ctx.channel.send(embed=embed)

    async def timeout(self, ctx) -> discord.Message:
        embed = discord.Embed(title="Reminder Setup Timed Out",
                              description=f"{ctx.author.mention}, your reminder setup timed out due to inactivity",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed, delete_after=10)

    async def check_panel_exists(self, panel: discord.Message) -> bool:
        try:
            if panel.id:
                return True
        except discord.NotFound:
            return False

    async def edit_panel(self, panel_embed: discord.Embed, panel: discord.Message,
                         title: str = None, description: str = None, color: discord.Color = None) -> bool:
        panel_exists = await self.check_panel_exists(panel)
        if not panel_exists:
            return False

        if not title:
            title = panel_embed.title
        if not description:
            description = panel_embed.description
        if not color:
            color = discord.Color.blue()
            
        panel_embed_edited = discord.Embed(title=title,
                                           description=description,
                                           color=color)

        await panel.edit(embed=panel_embed_edited)
        return True

    async def no_panel(self, ctx) -> discord.Message:
        embed = discord.Embed(title="Reminder Setup Cancelled",
                              description=f"{ctx.author.mention}, the reminder setup panel was either deleted or could "
                                          f"not be found",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed, delete_after=10)

    async def cancelled(self, ctx, panel: discord.Message) -> discord.Message:
        embed = discord.Embed(title="Reminder Setup Cancelled",
                              description=f"{ctx.author.mention}, the reminder setup was cancelled",
                              color=discord.Color.blue())
        if await self.check_panel_exists(panel):
            return await panel.edit(embed=embed, delete_after=10)
        else:
            return await ctx.channel.send(embed=embed, delete_after=10)

    async def not_valid_time(self, ctx) -> discord.Message:
        embed = discord.Embed(title="Invalid Time",
                              description=f"{ctx.author.mention}, you did not provide a valid time",
                              color=discord.Color.dark_red())
        return await ctx.channel.send(embed=embed, delete_after=10)

    async def create_reminder(self, user_id: int, channel_id: int, guild_id: int,
                              send_time: int, message_content: str, remind_type: str):
        init = {
            str(guild_id): {
                str(user_id): [
                    {
                        "type": remind_type,
                        "time": send_time,
                        "channel_id": channel_id,
                        "message_content": str(base64.urlsafe_b64encode(message_content.encode("ascii")), encoding="utf-8")
                    }
                ]
            }
        }

        info = {
            "type": remind_type,
            "time": send_time,
            "channel_id": channel_id,
            "message_content": str(base64.urlsafe_b64encode(message_content.encode("ascii")), encoding="utf-8")
        }

        gcmds.json_load('db/reminders.json', init)
        with open('db/reminders.json', 'r') as f:
            file = json.load(f)
            f.close()
        while True:
            try:
                file[str(guild_id)][str(user_id)].append(info)
                break
            except KeyError:
                file.update({str(guild_id): {}})
                file[str(guild_id)].update({str(user_id): []})
                continue
        with open('db/reminders.json', 'w') as g:
            json.dump(file, g, indent=4)

        await asyncio.create_task(self.send_loop(send_time, user_id, channel_id, message_content, guild_id))

    async def get_reminders(self, guild_id: int, user_id: int) -> str:
        if not os.path.exists('db/reminders.json'):
            return None

        with open('db/reminders.json', 'r') as f:
            file = json.load(f)
            f.close()

        index = 1
        string = ""
        user_info = file[str(guild_id)][str(user_id)]
        if len(user_info) == 0 or not user_info:
            return None
        for entry in user_info:
            message_content_ascii = base64.urlsafe_b64decode(
                str.encode(entry['message_content']))
            message_content = message_content_ascii.decode("ascii")
            if entry['type'] == "single":
                string += f"**{index}:** {entry['type']}, fires in <#{entry['channel_id']}> at " \
                    f"{datetime.fromtimestamp(entry['time'])}, {message_content}\n\n"
            elif entry['type'] == "loop":
                td = entry['time']
                time_formatted = ""
                skip = False
                days = divmod(td, 86400)
                if days[0] != 0:
                    time_formatted += f"{days[0]} days, "
                rem_sec = days[1]
                if rem_sec == 0:
                    return string
                hours = divmod(rem_sec, 3600)
                if hours[0] != 0:
                    time_formatted += f"{hours[0]} hours, "
                rem_sec = hours[1]
                if rem_sec == 0:
                    return string
                minutes = divmod(rem_sec, 60)
                if minutes[0] != 0:
                    time_formatted += f"{minutes[0]} minutes, "
                seconds = rem_sec
                if seconds != 0:
                    time_formatted += f"{seconds} seconds"
                string += f"**{index}:** {entry['type']}, fires in <#{entry['channel_id']}> every {time_formatted}, " \
                    f"{message_content}\n\n"
            index += 1
        return string

    async def get_reminder_time(self, guild_id: int, user_id: int, index: int) -> str:
        with open('db/reminders.json', 'r') as f:
            file = json.load(f)
            f.close()

        if file[str(guild_id)][str(user_id)][index]['type'] == "single":
            return datetime.fromtimestamp(file[str(guild_id)][str(user_id)][index]['time']).strftime("%m/%d/%Y %H:%M:%S UTC")
        else:
            td = timedelta(seconds=file[str(guild_id)]
                           [str(user_id)][index]['time'])
            time_formatted = ""
            days = divmod(86400, td.seconds)
            if days[0] != 0:
                time_formatted += f"{days[0]} days, "
            rem_sec = days[1]
            hours = divmod(3600, rem_sec)
            if hours[0] != 0:
                time_formatted += f"{hours[0]} hours, "
            rem_sec = hours[1]
            minutes = divmod(60, rem_sec)
            if minutes[0] != 0:
                time_formatted += f"{minutes[0]} minutes, "
            seconds = rem_sec
            if seconds != 0:
                time_formatted += f"{seconds} seconds"
            return time_formatted

    async def no_reminders(self, ctx) -> discord.Message:
        embed = discord.Embed(title="No Reminders",
                              description=f"{ctx.author.mention}, you currently have no reminders scheduled",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed, delete_after=10)

    async def get_reminder_type(self, guild_id: int, user_id: int, index: int) -> str:
        with open('db/reminders.json', 'r') as f:
            file = json.load(f)
            f.close()

        return file[str(guild_id)][str(user_id)][index]['type']

    async def get_reminder_content(self, guild_id: int, user_id: int, index: int) -> str:
        with open('db/reminders.json', 'r') as f:
            file = json.load(f)
            f.close()

        content_ascii = base64.urlsafe_b64decode(str.encode(
            file[str(guild_id)][str(user_id)][index]['message_content']))
        content = content_ascii.decode("ascii")

        return content

    async def get_reminder_channel(self, guild_id: int, user_id: int, index: int) -> int:
        with open('db/reminders.json', 'r') as f:
            file = json.load(f)
            f.close()

        return int(file[str(guild_id)][str(user_id)][index]['channel_id'])

    async def edit_reminder(self, guild_id: int, user_id: int, index: int,
                            channel_id, time_to_send, edited_content) -> bool:
        try:
            with open('db/reminders.json', 'r') as f:
                file = json.load(f)
                f.close()
            info = file[str(guild_id)][str(user_id)][index]
            if channel_id:
                info['channel_id'] = channel_id
            if time_to_send:
                info['time'] = time_to_send
            if edited_content:
                info['message_content'] = str(base64.urlsafe_b64encode(
                    edited_content.encode("ascii")), encoding="utf-8")
            with open('db/reminders.json', 'w') as g:
                json.dump(file, g, indent=4)
                g.close()
            return True
        except KeyError:
            return False

    async def delete_reminder(self, guild_id: int, user_id: int, index=None) -> bool:
        try:
            with open('db/reminders.json', 'r') as f:
                file = json.load(f)
                f.close()
            if index:
                del file[str(guild_id)][str(user_id)][index]
                if len(file[str(guild_id)][str(user_id)]) == 0:
                    del file[str(guild_id)][str(user_id)]
            else:
                del file[str(guild_id)][str(user_id)]
                    
            if len(file[str(guild_id)]) == 0:
                    del file[str(guild_id)]
                    
            with open('db/reminders.json', 'w') as g:
                json.dump(file, g, indent=4)
            return True
        except KeyError:
            return False

    @commands.group(aliases=['reminder'])
    async def remind(self, ctx, *, message_with_time: str = None):
        if not message_with_time:
            return await self.send_remind_help(ctx)

        if message_with_time in ["-e", 'edit']:
            await ctx.invoke(self.edit)
            return
        elif message_with_time in ["-rm", "trash", "delete"]:
            await ctx.invoke(self.delete)
            return

        
        dates = search_dates(text=message_with_time, settings={
                             'PREFER_DATES_FROM': "future"})
        current_time = datetime.now().timestamp()
        if not dates:
            return await self.not_valid_time(ctx)
        time_to_send = dates[0][1].timestamp()
        remind_message_rem_time = message_with_time.replace(
            f"{dates[0][0]}", "")
        if remind_message_rem_time.startswith(" "):
            remind_message = remind_message_rem_time[1:]
        else:
            remind_message = remind_message_rem_time

        panel_embed = discord.Embed(title="Reminder Setup Panel",
                                    description=f"{ctx.author.mention}, would you like this reminder to loop?\n\n"
                                                f"*React with* 🔁 *to loop,* ✅ *to have it send once, or* 🛑 "
                                                f"*to cancel",
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)
        for reaction in reactions:
            await panel.add_reaction(reaction)

        def reacted_user(reaction: discord.Reaction, user: discord.User) -> bool:
            if reaction.message.id == panel.id and user.id == ctx.author.id and (reaction.emoji in reactions):
                return True
            else:
                return False

        try:
            result = await self.client.wait_for("reaction_add", check=reacted_user,
                                                            timeout=timeout)
        except asyncio.TimeoutError:
            return await self.timeout(ctx)
        reaction = result[0].emoji
        await panel.clear_reactions()
        if reaction == "🛑":
            return await self.cancelled(ctx, panel)
        if reaction == "✅":
            remind_type = "single"
        elif reaction == "🔁":
            remind_type = "loop"

        if remind_type == "single":
            if str(dates[0][0]).startswith("in ") or str(dates[0][0]).startswith("at "):
                str_time = str(dates[0][0])
            else:
                str_time = "in " + str(dates[0][0])
            panel_new_title = "Reminder Successfully Created"
            panel_new_description = f"{ctx.author.mention}, your reminder has been created and will be dispatched to " \
                                    f"this channel {str_time}"
            finished = await self.edit_panel(panel_embed, panel, panel_new_title, panel_new_description)
            if not finished:
                return await self.cancelled(ctx, panel)
            await self.create_reminder(ctx.author.id, ctx.channel.id, ctx.guild.id, time_to_send,
                                       remind_message, remind_type)
        elif remind_type == "loop":
            str_time = "every" + \
                str(dates[0][0]).replace("in ", "").replace("at ", "")
            panel_new_title = "Reminder Successfully Created"
            panel_new_description = f"{ctx.author.mention}, your reminder has been created and will be dispatched to " \
                                    f"this channel {str_time}"
            finished = await self.edit_panel(panel_embed, panel, panel_new_title, panel_new_description)
            if not finished:
                return await self.cancelled(ctx, panel)
            loop_interval = time_to_send - current_time
            await self.create_reminder(ctx.author.id, ctx.channel.id, ctx.guild.id, loop_interval,
                                       remind_message, remind_type)

    @remind.command(aliases=['-e'])
    async def edit(self, ctx):
        reminders_list = await self.get_reminders(ctx.guild.id, ctx.author.id)
        if not reminders_list:
            return await self.no_reminders(ctx)
        panel_embed = discord.Embed(title="Edit Reminders",
                                    description=f"{ctx.author.mention}, please type the number of the reminder that "
                                    f"you would like to edit, or type *\"cancel\"* to cancel\n\n{reminders_list}",
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)

        def from_user(message: discord.Message) -> bool:
            if message.author.id == ctx.author.id:
                return True
            else:
                return False

        # User inputs index of reminder they want to edit
        while True:
            try:
                if not await self.check_panel_exists(panel):
                    return await self.cancelled(ctx, panel)
                result = await self.client.wait_for("message", check=from_user, timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx)
            if result.content == "cancel":
                return await self.cancelled(ctx, panel)
            try:
                index = int(result.content) - 1
                break
            except (ValueError, TypeError):
                continue
        await result.delete()

        reminder_type = await self.get_reminder_type(ctx.guild.id, ctx.author.id, index)
        if reminder_type == "single":
            description = f"{ctx.author.mention}, please enter the time you would like this reminder to fire, type " \
                f"*\"skip\"* to keep the current time or type *\"cancel\"* to cancel\n\n" \
                f"Current Time: {await self.get_reminder_time(ctx.guild.id, ctx.author.id, index)}"
        elif reminder_type == "loop":
            description = f"{ctx.author.mention}, please enter the interval you would like this reminder to loop or" \
                f"type *\"cancel\"* to cancel\n\n" \
                f"Loops Every: {await self.get_reminder_time(ctx.guild.id, ctx.author.id, index)}"

        await self.edit_panel(panel_embed, panel, title=None, description=description)

        # User inputs time they want the reminder to fire at
        while True:
            try:
                if not await self.check_panel_exists(panel):
                    return await self.cancelled(ctx, panel)
                result = await self.client.wait_for("message", check=from_user, timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx)
            if result.content == "cancel":
                return await self.cancelled(ctx, panel)
            if result.content == "skip":
                time_to_send = None
                break

            current_time = datetime.now().timestamp()
            dates = search_dates(text=result.content, settings={
                                 'PREFER_DATES_FROM': "future"})
            if not dates:
                continue
            if reminder_type == "single":
                time_to_send = dates[0][1].timestamp()
            elif reminder_type == "loop":
                time_to_send = dates[0][1].timestamp() - current_time
            break
        await result.delete()

        description = f"{ctx.author.mention}, please type what you would like the reminder content to be if you would "\
            "like to change it, otherwise, type *\"skip\"* to keep the current content or type *\"cancel\"* to cancel" \
            f"\n\nCurrent Content: {await self.get_reminder_content(ctx.guild.id, ctx.author.id, index)}"
        await self.edit_panel(panel_embed, panel, title=None, description=description)

        # User inputs reminder content they want to be displayed
        while True:
            try:
                if not await self.check_panel_exists(panel):
                    return await self.cancelled(ctx, panel)
                result = await self.client.wait_for("message", check=from_user, timeout=timeout)
            except asyncio.TimeoutError:
                return await self.timeout(ctx)
            if result.content == "cancel":
                return await self.cancelled(ctx, panel)
            elif result.content == "skip":
                edited_content = None
            else:
                edited_content = result.content
            break
        await result.delete()

        description = f"{ctx.author.mention}, please tag or enter the ID of the channel you would like this reminder " \
            f"to fire in\n\nCurrent channel: <#{await self.get_reminder_channel(ctx.guild.id, ctx.author.id, index)}>"
        await self.edit_panel(panel_embed, panel, title=None, description=description)

        # User inputs reminder channel they want the reminder to fire in
        while True:
            try:
                if not await self.check_panel_exists(panel):
                    return await self.cancelled(ctx, panel)
                result = await self.client.wait_for("message", check=from_user, timeout=30)
            except asyncio.TimeoutError:
                return await self.timeout(ctx)
            if result.content == "cancel":
                return await self.cancelled(ctx, panel)
            if result.content == "skip":
                channel_id = None
                break
            if re.match(channel_tag_rx, result.content):
                channel_id = int(result.content[2:20])
                break
            elif re.match(channel_id_rx, result.content):
                channel_id = int(result.content)
                break
            else:
                continue
        await result.delete()

        succeeded = await self.edit_reminder(ctx.guild.id, ctx.author.id, index, channel_id, time_to_send, edited_content)
        if succeeded:
            await self.edit_panel(panel_embed, panel, title="Reminder Successfully Edited",
                                  description=f"{ctx.author.mention}, your reminder was successfully edited")
        else:
            await self.edit_panel(panel_embed, panel, title="Reminder Edit Failed",
                                  description=f"{ctx.author.mention}, your reminder could not be edited")
        return

    @remind.command(aliases=['-rm', 'trash'])
    async def delete(self, ctx):
        reminders_list = await self.get_reminders(ctx.guild.id, ctx.author.id)
        if not reminders_list:
            return await self.no_reminders(ctx)
        panel_embed = discord.Embed(title="Edit Reminders",
                                    description=f"{ctx.author.mention}, please type the number of the reminder that "
                                    f"you would like to delete, *\"all\"* to delete all reminders, or type *\"cancel\"*"
                                    f" to cancel\n\n{reminders_list}",
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)

        def from_user(message: discord.Message) -> bool:
            if message.author.id == ctx.author.id:
                return True
            else:
                return False

        while True:
            try:
                if not await self.check_panel_exists(panel):
                    return await self.cancelled(ctx, panel)
                result = await self.client.wait_for("message", check=from_user, timeout=30)
            except asyncio.TimeoutError:
                return await self.timeout(ctx)
            if result.content == "cancel":
                return await self.cancelled(ctx, panel)
            elif result.content == "all":
                index = None
                break
            try:
                index = int(result.content) - 1
                break
            except ValueError:
                continue
        await result.delete()

        succeeded = await self.delete_reminder(ctx.guild.id, ctx.author.id, index)
        if not succeeded:
            await self.edit_panel(panel_embed, panel, title="Reminder Delete Failed",
                                  description=f"{ctx.author.mention}, your reminder could not be deleted",
                                  color=discord.Color.dark_red())
        else:
            await self.edit_panel(panel_embed, panel, title="Reminder Successfully Deleted",
                                  description=f"{ctx.author.mention}, your reminder was successfully deleted")

        return


def setup(client):
    client.add_cog(Reminders(client))
