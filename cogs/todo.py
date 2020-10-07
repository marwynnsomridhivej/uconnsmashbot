import asyncio
import base64
from datetime import datetime

import discord
from discord.ext import commands
from utils import customerrors, globalcommands, paginator

gcmds = globalcommands.GlobalCMDS()


class Todo(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_todo())

    async def init_todo(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS todos(id SERIAL, message_content text, status text, timestamp NUMERIC, author_id bigint)")

    async def todo_help(self, ctx):
        pfx = f"{await gcmds.prefix(ctx)}todo"
        description = (f"{ctx.author.mention}, the base command is `{pfx}` *alias = `td` `todos`*. The `todo` commands "
                       "serve as an alternative to `reminders`, which are scheduled to fire at a specific point in time,"
                       " or on a defined interval. If you just want an organised list of tasks to complete, or are not "
                       "sure when you want to complete that task, then use `todo`\n\nHere are all the subcommands for `todo`")
        tset = (f"**Usage:** `{pfx} create [item]`",
                "**Returns:** An embed that confirms your todo was successfully created, or added to the current todo list",
                "**Aliaes:** `-s` `add`",
                "**Special Cases:** `[item]` is what you want your todo message to be")
        tedit = (f"**Usage:** `{pfx}edit [ID]`",
                 "**Returns:** An interactive panel that will guide you through editing a created todo",
                 "**Aliases:** `-e` `modify` `adjust`",
                 "**Special Cases:** The ID passed into `[ID]` must be an ID of a todo that you own. You cannot edit another "
                 "user's todos")
        tlist = (f"**Usage:** `{pfx}list` (flag)",
                 "**Returns:** A paginated list of all your active and completed todos",
                 "**Aliases:** `-ls` `show`",
                 "**Special Cases:** Valid arguments for `(flag)` are \"active\" (shows active only) and \"done\" or "
                 "\"complete\" (shows completed only)")
        tcomplete = (f"**Usage:** `{pfx} complete [ID]*va`",
                     "**Returns:** An embed that confirms your todo was successfully marked as completed",
                     "**Aliases:** `-c` `finish` `done`",
                     "**Special Cases:** Marking as complete does not truly delete the todo from your history. "
                     "If `[ID]` is \"all\", it will mark all currently active todos as complete. `[ID]` accepts a single ID "
                     "or comma separated IDs")
        treset = (f"**Usage:** `{pfx} reset [ID]*va`",
                  "**Returns:** An embed that confirms your todo was successfully reset (marked as active)",
                  "**Aliases:** `-r` `incomplete`",
                  "**Special Cases:** If `[ID]` is \"all\", it will mark all your todos, both active and completed, as active. "
                  "`[ID]` accepts a single ID or comma separated IDs")
        tremove = (f"**Usage:** `{pfx}remove [ID]*va`",
                   "**Returns:** A confirmation embed that upon confirmation, will delete the specified IDs"
                   "**Aliases:** `-rm` `cancel` `delete`",
                   "**Special Cases:** Removing a todo will remove it from your history, therefore, you will not be able to "
                   "access that todo anymore. It will no longer show up when you list all your todos. `[ID]` accepts a single ID "
                   "or comma separated IDs")
        nv = [("Set", tset), ("Edit", tedit), ("List", tlist),
              ("Complete", tcomplete), ("Reset", treset), ("Remove", tremove)]
        embed = discord.Embed(title="Todo Help", description=description, color=discord.Color.blue())
        for name, value in nv:
            embed.add_field(name=name, value="> " + "\n> ".join(value), inline=False)
        return await ctx.channel.send(embed=embed)

    async def check_todos(self, ctx, ids):
        async with self.bot.db.acquire() as con:
            if isinstance(ids, list):
                for item in ids:
                    result = await con.fetch(f"SELECT * FROM todos WHERE id={item}")
                    if not result:
                        raise customerrors.ToDoCheckError()
            else:
                result = await con.fetch(f"SELECT * FROM todos WHERE id={ids}")
                if not result:
                    raise customerrors.ToDoCheckError()
        return

    async def get_todos(self, ctx, req_active=False, req_complete=False, list=False, detailed=False) -> bool:
        async with self.bot.db.acquire() as con:
            if req_active:
                op = f"SELECT * FROM todos WHERE status='active' AND author_id={ctx.author.id} ORDER BY id asc"
            elif req_complete:
                op = f"SELECT * FROM todos WHERE status='complete' AND author_id={ctx.author.id} ORDER BY id asc"
            else:
                op = f"SELECT * FROM todos WHERE author_id={ctx.author.id} ORDER BY status asc, id asc"
            result = await con.fetch(op)
        if not result:
            if req_active:
                status = "active"
            elif req_complete:
                status = "completed"
            if list and (req_active or req_complete):
                raise customerrors.ToDoEmptyError(ctx.author, status=status)
            else:
                raise customerrors.ToDoEmptyError(ctx.author)
        if detailed:
            if list and not (req_active or req_complete):
                return [f"**{(base64.urlsafe_b64decode(str.encode(item['message_content']))).decode('ascii')}**"
                        f"\n*> Created: {'{:%m/%d/%Y %H:%M:%S}'.format(datetime.fromtimestamp(int(item['timestamp'])))}"
                        f"\n> ID: `{item['id']}`\n> Status: {'◻️' if item['status'] == 'active' else '☑️'}*" for item in result]
            else:
                return [f"**{(base64.urlsafe_b64decode(str.encode(item['message_content']))).decode('ascii')}**"
                        f"\n*> Created: {'{:%m/%d/%Y %H:%M:%S}'.format(datetime.fromtimestamp(int(item['timestamp'])))}"
                        f"\n> ID: `{item['id']}`*" for item in result]
        else:
            return [f"◻️ {(base64.urlsafe_b64decode(str.encode(item['message_content']))).decode('ascii')}" for item in result]

    async def get_specified_todo(self, todo_id: int):
        try:
            async with self.bot.db.acquire() as con:
                message_content = base64.urlsafe_b64decode(str(await con.fetchval(f"SELECT message_content FROM todos WHERE id={todo_id}"))).decode("ascii")
            return message_content
        except Exception:
            raise customerrors.ToDoSearchError()

    async def set_todo(self, ctx, entry: str):
        try:
            async with self.bot.db.acquire() as con:
                message_content_64 = str(base64.urlsafe_b64encode(entry.encode('ascii')), encoding='utf-8')
                values = f"($tag${message_content_64}$tag$, 'active', {int(datetime.now().timestamp())}, {ctx.author.id})"
                await con.execute(f"INSERT INTO todos(message_content, status, timestamp, author_id) VALUES {values}")
        except Exception:
            raise customerrors.ToDoSetError()
        return

    async def edit_todo(self, ctx, todo_id: int, message_content: str):
        try:
            async with self.bot.db.acquire() as con:
                message_content_64 = str(base64.urlsafe_b64encode(message_content.encode('ascii')), encoding='utf-8')
                await con.execute(f"UPDATE todos SET message_content=$tag${message_content_64}$tag$ WHERE id={todo_id}")
        except Exception:
            raise customerrors.ToDoUpdateError()
        return

    async def update_todos(self, ctx, todo_ids, status):
        try:
            async with self.bot.db.acquire() as con:
                if isinstance(todo_ids, list):
                    for item in todo_ids:
                        await con.execute(f"UPDATE todos SET status='{status}' WHERE id={int(item)}")
                else:
                    await con.execute(f"UPDATE todos SET status='{status}' WHERE id={int(todo_ids)}")
        except Exception:
            raise customerrors.ToDoUpdateError()
        return

    async def remove_todos(self, ctx, todo_ids):
        try:
            async with self.bot.db.acquire() as con:
                if isinstance(todo_ids, list):
                    for item in todo_ids:
                        await con.execute(f"DELETE FROM todos WHERE id={int(item)}")
                else:
                    await con.execute(f"DELETE FROM todos WHERE id={int(todo_ids)}")
        except Exception:
            raise customerrors.ToDoRemoveError()

    @commands.group(invoke_without_command=True,
                    aliases=['td', 'todos'],
                    desc="Displays the help command for todo",
                    usage="todo")
    async def todo(self, ctx):
        return await self.todo_help(ctx)

    @todo.command(aliases=['-s', 'create', 'add'])
    async def todo_create(self, ctx, *, entry: str):
        await self.set_todo(ctx, entry)
        embed = discord.Embed(title="Todo Set Successfully",
                              description=f"{ctx.author.mention}, `{entry}` was added to your todo list",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @todo.command(aliases=['-e', 'modify', 'adjust', 'edit'])
    async def todo_edit(self, ctx, ids: int):
        await self.check_todos(ctx, ids)

        def from_user(message: discord.Message) -> bool:
            return message.author.id == ctx.author.id and message.channel.id == ctx.channel.id

        content = await self.get_specified_todo(ids)
        panel_embed = discord.Embed(title="Edit Todo",
                                    description=f"{ctx.author.mention}, what would you like your todo's content to be?"
                                    f"\n\nCurrent Content: ```{content}```",
                                    color=discord.Color.blue())
        panel = await ctx.channel.send(embed=panel_embed)

        try:
            result = await self.bot.wait_for("message", check=from_user, timeout=240)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, "edit todo")
        new_content = result.content
        await gcmds.smart_delete(result)
        await gcmds.smart_delete(panel)

        await self.edit_todo(ctx, ids, new_content)
        embed = discord.Embed(title="Todo Successfully Edited",
                              description=f"{ctx.author.mention}, your todo was successfully edited",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @todo.command(aliases=['-ls', 'show', 'list'])
    async def todo_list(self, ctx, *, flag: str = None):
        if not flag in ["active", "done", "complete"]:
            entries = await self.get_todos(ctx, list=True, detailed=True)
            title = f"All Todos Created"
        elif flag == "active":
            entries = await self.get_todos(ctx, req_active=True, list=True, detailed=True)
            title = "Your Active Todos"
        elif flag in ["done", "complete", "completed", "finished"]:
            title = "Your Completed Todos"
            entries = await self.get_todos(ctx, req_complete=True, list=True, detailed=True)
        pag = paginator.EmbedPaginator(ctx, entries=entries, per_page=10, show_entry_count=True)
        pag.embed.title = title
        return await pag.paginate()

    @todo.command(aliases=['-c', 'finish', 'done', 'complete'])
    async def todo_complete(self, ctx, *, ids):
        ids = ids.replace(" ", "").split(",")
        await self.check_todos(ctx, ids)
        await self.update_todos(ctx, ids, 'complete')
        embed = discord.Embed(title="Todos Marked as Complete",
                              description=f"{ctx.author.mention}, the specified todos were marked as complete. This means "
                              f"that they will no longer show as active, but can still be accessed through `{await gcmds.prefix(ctx)}"
                              f"todo list`. Any completed todos can still be remarked as active",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @todo.command(aliases=['-r', 'incomplete', 'reset'])
    async def todo_reset(self, ctx, *, ids):
        ids = ids.replace(" ", "").split(",")
        await self.check_todos(ctx, ids)
        await self.update_todos(ctx, ids, 'active')
        embed = discord.Embed(title="Todos Marked as Active",
                              description=f"{ctx.author.mention}, the specified todos were marked as active. They will "
                              "now appear on your todo list",
                              color=discord.Color.blue())
        return await ctx.channel.send(embed=embed)

    @todo.command(aliases=['-rm', 'cancel', 'delete', 'remove'])
    async def todo_remove(self, ctx, *, ids):
        ids = ids.replace(" ", "").split(",")
        await self.check_todos(ctx, ids)

        reactions = ['✅', '🛑']
        description = f"{ctx.author.mention}, this action is destructive and irreversible."
        panel = await gcmds.confirmation(ctx, description)
        try:
            for reaction in reactions:
                await panel.add_reaction(reaction)
        except Exception:
            raise customerrors.ToDoUpdateError()

        def reacted(reaction: discord.Reaction, user: discord.User):
            return reaction.emoji in reactions and reaction.message.id == panel.id and user.id == ctx.author.id

        try:
            result = await self.bot.wait_for("reaction_add", check=reacted, timeout=30)
        except asyncio.TimeoutError:
            return await gcmds.timeout(ctx, "todo remove", 30)
        await gcmds.smart_delete(panel)
        if result[0].emoji == reactions[0]:
            await self.remove_todos(ctx, ids)
            embed = discord.Embed(title="Deleted Todos",
                                  description=f"{ctx.author.mention}, the specified todos were deleted",
                                  color=discord.Color.blue())
            return await ctx.channel.send(embed=embed)
        else:
            return await gcmds.cancelled(ctx, "todo remove")


def setup(bot):
    bot.add_cog(Todo(bot))
