import asyncio
from contextlib import suppress

import discord
from discord.ext import commands

from utils import customerrors, GlobalCMDS


__all__ = (
    "EmbedPaginator",
    "FieldPaginator",
    "SubcommandPaginator",
)


gcmds = GlobalCMDS()


class EmbedPaginator:
    def __init__(self, ctx, *, entries, per_page=10, show_entry_count=True, **kwargs):
        self.bot = ctx.bot
        self.ctx = ctx
        self.entries = entries
        self.provided_message = kwargs.get("provided_message", None)
        self.edit_provided_message = self.provided_message is not None
        self.message = self.provided_message or ctx.message
        self.channel = ctx.channel
        self.author = ctx.author
        self.per_page = per_page
        pages, left_over = divmod(len(self.entries), self.per_page)
        if left_over:
            pages += 1
        self.maximum_pages = pages
        self.embed = kwargs.get("embed", discord.Embed(color=discord.Color.blue()))
        self.paginating = len(entries) > per_page
        self.show_entry_count = show_entry_count
        self.emojis = [
            ('⏮️', self.first_page),
            ('◀️', self.previous_page),
            ('▶️', self.next_page),
            ('⏭️', self.last_page),
            ('🔢', self.numbered_page),
            ('⏹️', self.stop_pages),
            ('ℹ️', self.show_help)
        ]
        self.in_help = False
        self.show_index = kwargs.get("show_index", True)
        self.description = kwargs.get("description", None)

        if ctx.guild:
            self.permissions = self.channel.permissions_for(ctx.guild.me)
        else:
            self.permissions = self.channel.permissions_for(ctx.bot.user)

        if not self.permissions.embed_links:
            raise customerrors.CannotPaginate("UconnSmashBot missing embed links permission")

        if not self.permissions.send_messages:
            raise customerrors.CannotPaginate("UconnSmashBot cannot send messages")

        if self.paginating:
            if not self.permissions.add_reactions:
                raise customerrors.CannotPaginate("UconnSmashBot missing add reactions permission")
            if not self.permissions.read_message_history:
                raise customerrors.CannotPaginate("UconnSmashBot missing read message history permission")

    def get_page(self, page):
        base = (page - 1) * self.per_page
        return self.entries[base:base + self.per_page]

    def get_content(self, entries, page, *, first=False):
        return None

    def get_embed(self, entries, page, *, first=False):
        self.prepare_embed(entries, page, first=first)
        return self.embed

    def prepare_embed(self, entries, page, *, first=False):
        desc_list = [f'{f"**{index}.** " if self.show_index else ""}{entry}'
                     for index, entry in enumerate(entries, 1 + ((page - 1) * self.per_page))]
        if self.maximum_pages > 1:
            if self.show_entry_count:
                text = f'Page {page}/{self.maximum_pages} ({len(self.entries)} entries)'
            else:
                text = f'Page {page}/{self.maximum_pages}'
            self.embed.set_footer(text=text)

        if self.paginating and first:
            desc_list.append('')
            desc_list.append('React with ℹ️ for help')

        if self.description:
            self.embed.description = self.description + '\n'.join(desc_list)
        else:
            self.embed.description = '\n'.join(desc_list)

    async def show_page(self, page, *, first=False):
        self.current_page = page
        entries = self.get_page(page)
        content = self.get_content(entries, page, first=first)
        embed = self.get_embed(entries, page, first=first)

        if not self.paginating:
            if self.edit_provided_message:
                await self.provided_message.edit(content=content, embed=embed)
            else:
                return await self.channel.send(content=content, embed=embed)

        if not first:
            return await self.message.edit(content=content, embed=embed)

        if self.edit_provided_message and first:
            await self.message.edit(content=content, embed=embed)
        elif not self.edit_provided_message and first:
            self.message = await self.channel.send(content=content, embed=embed)
        if not self.maximum_pages <= 1:
            for reaction, _ in self.emojis:
                if self.maximum_pages <= 2 and reaction in ('⏮️', '⏭️'):
                    continue
                await self.message.add_reaction(reaction)

    async def checked_show_page(self, page):
        if page != 0 and page <= self.maximum_pages:
            await self.show_page(page)
            return True
        return False

    async def first_page(self):
        await self.show_page(1)

    async def last_page(self):
        await self.show_page(self.maximum_pages)

    async def next_page(self):
        await self.checked_show_page(self.current_page + 1)

    async def previous_page(self):
        await self.checked_show_page(self.current_page - 1)

    async def show_current_page(self):
        if self.paginating:
            await self.show_page(self.current_page)

    async def numbered_page(self):
        del_msgs = []
        embed = discord.Embed(title="Input Page Number",
                              description=f"{self.author.mention}, please type the page number you would like to go to",
                              color=discord.Color.blue())
        del_msgs.append(await self.channel.send(embed=embed))

        def from_user(message: discord.Message) -> bool:
            return message.author == self.author and message.channel == self.channel and message.content.isdigit()

        try:
            result = await self.bot.wait_for('message', check=from_user, timeout=30)
        except asyncio.TimeoutError:
            timeout = discord.Embed(title="Page Input Timed Out",
                                    description=f"{self.author.mention}, you did not input a valid page number within "
                                    "30 seconds",
                                    color=discord.Color.dark_red())
            try:
                await del_msgs[0].edit(embed=timeout)
            except Exception:
                del_msgs.append(await self.channel.send(embed=timeout))
            await asyncio.sleep(5)
        else:
            page = int(result.content)
            del_msgs.append(result)
            success = await self.checked_show_page(page)
            if not success:
                invalid = discord.Embed(title="Invalid Page Number",
                                        description=f"{self.author.mention}, `{result.content}` is not a valid page number",
                                        color=discord.Color.dark_red())
                del_msgs.append(await self.channel.send(embed=invalid))
                await asyncio.sleep(5)

        for message in del_msgs:
            await gcmds.smart_delete(message)

    async def show_help(self):
        desc = (
            "⏮️ - go to first page",
            "◀️ - go to previous page",
            "▶️ - go to next page",
            "⏭️ - go to last page",
            "🔢 - input a page number to go to that page",
            "⏹️ - stop paginating",
            "ℹ️ - show this help menu"
        )
        embed = self.embed.copy()
        embed.clear_fields()
        embed.title = "Paginator Help"
        embed.description = (f"{self.author.mention}, here are the controls for the paginator:\n\n" +
                             '\n'.join(desc))
        embed.set_footer(
            text=f"Original paginator left on page {self.current_page}. Press ⏹️ to return to original paginator")
        await self.message.edit(embed=embed)
        self.in_help = True

    async def stop_pages(self):
        with suppress(Exception):
            await self.message.clear_reactions()
        self.paginating = False

    async def rem_reaction(self, payload):
        if not self.message.id == payload.message_id:
            return
        member_converter = commands.MemberConverter()
        member_converted = await member_converter.convert(self.ctx, str(payload.user_id))
        if member_converted.bot:
            return

        with suppress(Exception):
            await self.message.remove_reaction(payload.emoji, member_converted)

    def react_check(self, payload):
        self.bot.loop.create_task(self.rem_reaction(payload))
        if payload.user_id != self.author.id:
            return False

        if payload.message_id != self.message.id:
            return False

        reacted_emoji = str(payload.emoji)
        if reacted_emoji == "⏹️" and self.in_help:
            self.match = self.show_current_page
            self.in_help = False
            return True

        for (emoji, func) in self.emojis:
            if reacted_emoji == emoji and not self.in_help:
                self.match = func
                return True
        return False

    async def paginate(self):
        first_page = self.show_page(1, first=True)
        if not self.paginating:
            await first_page
        else:
            self.bot.loop.create_task(first_page)

        while self.paginating:
            try:
                payload = await self.bot.wait_for('raw_reaction_add', check=self.react_check, timeout=120.0)
            except asyncio.TimeoutError:
                self.paginating = False
                try:
                    await self.message.clear_reactions()
                except:
                    pass
                finally:
                    break

            await self.match()


class FieldPaginator(EmbedPaginator):
    def __init__(self, ctx, *, entries, per_page=10, show_entry_count=True, **kwargs):
        super().__init__(ctx, entries=entries, per_page=per_page,
                         show_entry_count=show_entry_count, **kwargs)
        self.footer = kwargs.get("footer", None)
        self.icon_url = kwargs.get("icon_url", None)
        if kwargs.get('embed', None):
            self.embed = kwargs.get("embed")

    def prepare_embed(self, entries, page, *, first=False):
        self.embed.clear_fields()

        for key, value, inline in entries:
            self.embed.add_field(name=key, value=value, inline=inline)

        if self.footer:
            if self.icon_url:
                self.embed.set_footer(text=self.footer, icon_url=self.icon_url)
            else:
                self.embed.set_footer(text=self.footer)
        else:
            if self.maximum_pages > 1:
                if self.show_entry_count:
                    text = f'Page {page}/{self.maximum_pages} ({len(self.entries)} entries)'
                else:
                    text = f'Page {page}/{self.maximum_pages}'

                if not self.footer and not self.icon_url:
                    self.embed.set_footer(text=text)
                elif not self.footer and self.icon_url:
                    self.embed.set_footer(text=text, icon_url=self.icon_url)
                elif self.icon_url:
                    self.embed.set_footer(text=self.footer, icon_url=self.icon_url)
                else:
                    self.embed.set_footer(text=self.footer)


class SubcommandPaginator(FieldPaginator):
    def __init__(self, ctx, *, entries, per_page=10, show_entry_count=True, **kwargs):
        super().__init__(ctx, entries=entries, per_page=per_page,
                         show_entry_count=show_entry_count, **kwargs)

    def prepare_embed(self, entries, page, *, first=False):
        self.embed.clear_fields()

        for key, value, inline in entries:
            self.embed.add_field(name=key, value="> " + "\n> ".join(value), inline=inline)

        if self.footer:
            if self.icon_url:
                self.embed.set_footer(text=self.footer, icon_url=self.icon_url)
            else:
                self.embed.set_footer(text=self.footer)
        else:
            if self.maximum_pages > 1:
                if self.show_entry_count:
                    text = f'Page {page}/{self.maximum_pages} ({len(self.entries)} entries)'
                else:
                    text = f'Page {page}/{self.maximum_pages}'

                if not self.footer and not self.icon_url:
                    self.embed.set_footer(text=text)
                elif not self.footer and self.icon_url:
                    self.embed.set_footer(text=text, icon_url=self.icon_url)
                elif self.icon_url:
                    self.embed.set_footer(text=self.footer, icon_url=self.icon_url)
                else:
                    self.embed.set_footer(text=self.footer)
