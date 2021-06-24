import re

import discord
from discord.embeds import EmptyEmbed
from discord.ext import commands
from discord.ext.commands import AutoShardedBot, Context
from utils import GlobalCMDS, SetupPanel

_BLUE = discord.Color.blue()
_HEX_COLOR_RX = re.compile(r'#[A-Fa-f0-9]{6}')
_URL_RX = re.compile(r'https?://(?:www\.)?.+')


class Embeds(commands.Cog):
    def __init__(self, bot: AutoShardedBot) -> None:
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)

    @staticmethod
    def _parse_url(url: str, old: discord.Embed) -> str:
        if url and url == "current":
            url = old.author.icon_url
        elif not _URL_RX.match(url):
            url = ""
        return url

    @commands.command(desc="Edits an embed's attributes",
                      usage="embededit [channelID] [messageID]",)
    async def embededit(self, ctx: Context, channel_id: int, message_id: int):
        channel = self.bot.get_channel(channel_id)
        message: discord.Message = await channel.fetch_message(message_id)
        if not message.author.id == ctx.guild.me.id or not message.embeds:
            return await ctx.channel.send(
                embed=discord.Embed(
                    title="Invalid Message",
                    description=f"{ctx.author.mention}, make sure I am the author of the message "
                    "and that it contains embeds",
                    color=discord.Color.dark_red(),
                )
            )
        old: discord.Embed = message.embeds[0]
        embed = old.copy()
        _ET = "Embed Edit"
        _FT = "Enter \"none\" to use the existing {}"
        _ALT_URL = lambda m: _URL_RX.match(m.content) or m.content == "current" or m.content == "none"
        sp = SetupPanel(
            bot=self.bot,
            ctx=ctx,
            title=_ET
        ).add_step(
            name="title",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the embed's title",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("title")
            ),
            timeout=300,
        ).add_step(
            name="description",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the embed's description",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("description"),
            ),
            timeout=300,
        ).add_step(
            name="color",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the embed's hex color",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("color")
            ),
            timeout=300,
            predicate=lambda m: (_HEX_COLOR_RX.match(m.content) or m.content == "none") and m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
        ).add_step(
            name="author",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the embed author's name (appears above title)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("author name, or current to use the current author name")),
            timeout=300,
        ).add_conditional_step(
            name="message",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter an icon URL for the embed author (appears before author's names)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("icon url, or current to use the current URL"),
            ),
            timeout=300,
            predicate=_ALT_URL,
            condition=lambda prev: bool(prev),
        ).add_step(
            name="footer",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the embed's footer text (appears below the description and main image)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("footer text, or current to use the current footer text"),
            ),
            timeout=300,
        ).add_conditional_step(
            name="message",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter an icon URL for the embed footer (appears before footer text)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("icon url, or current to use the current URL"),
            ),
            timeout=300,
            predicate=_ALT_URL,
            condition=lambda prev: bool(prev),
        ).add_step(
            name="message",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter a URL for the embed's thumbnail (small image to the top right)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("thumbnail image URL, or current to use the current URL"),
            ),
            timeout=300,
            predicate=_ALT_URL,
        ).add_step(
            name="message",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter a URL for the embed's main image (large image after description)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("main image URL, or current to use the current URL"),
            ),
            timeout=30,
            predicate=_ALT_URL,
        )

        title, description, color, author_name, author_icon_url, footer_text, footer_icon_url, thumbnail_url, image_url = [
            None if isinstance(item, str) and item == "none" else item for item in await sp.start()
        ]
        embed = discord.Embed(
            title=title if title else old.title,
            description=description if description else old.description,
            color=color if color else old.color,
        )
        if author_name:
            author_icon_url = self._parse_url(author_icon_url, old)
            embed.set_author(
                name=author_name if author_name != "current" else old.author.name,
                icon_url=author_icon_url,
            )
        if footer_text:
            footer_icon_url = self._parse_url(footer_icon_url, old)
            embed.set_footer(
                text=footer_text if footer_text != "current" else old.footer.text,
                icon_url=footer_icon_url,
            )
        if thumbnail_url:
            embed.set_thumbnail(
                url=self._parse_url(thumbnail_url, old)
            )
        if image_url:
            embed.set_image(
                url=self._parse_url(image_url, old)
            )
        return await message.edit(embed=embed)

    @commands.command(aliases=["emcf"],
                      desc="Sends an embed",
                      usage="embedconfig")
    async def embedconfig(self, ctx: commands.Context):
        _ET = "Embed Configuration"
        _FT = "Enter \"none\" to provide no {}"

        sp = SetupPanel(
            bot=self.bot,
            ctx=ctx,
            title=_ET
        ).add_step(
            name="channel",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please tag the channel you would like this embed to be sent in",
                color=_BLUE,
            ),
            timeout=300,
        ).add_step(
            name="title",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the embed's title",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("title")
            ),
            timeout=300,
        ).add_step(
            name="description",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the embed's description",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("description"),
            ),
            timeout=300,
        ).add_step(
            name="color",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the embed's hex color",
                color=_BLUE,
            ),
            timeout=300,
        ).add_step(
            name="author",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the embed author's name (appears above title)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("author name")),
            timeout=300,
        ).add_conditional_step(
            name="url",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter an icon URL for the embed author (appears before author's names)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("icon url"),
            ),
            timeout=300,
            condition=lambda prev: bool(prev),
        ).add_step(
            name="footer",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter the embed's footer text (appears below the description and main image)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("footer text"),
            ),
            timeout=300,
        ).add_conditional_step(
            name="url",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter an icon URL for the embed footer (appears before footer text)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("icon url"),
            ),
            timeout=300,
            condition=lambda prev: bool(prev),
        ).add_step(
            name="url",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter a URL for the embed's thumbnail (small image to the top right)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("thumbnail image URL"),
            ),
            timeout=300,
        ).add_step(
            name="url",
            embed=discord.Embed(
                title=_ET,
                description=f"{ctx.author.mention}, please enter a URL for the embed's main image (large image after description)",
                color=_BLUE,
            ).set_footer(
                text=_FT.format("main image URL"),
            ),
            timeout=300,
        )

        channel, title, description, color, author_name, author_icon_url, footer_text, footer_icon_url, thumbnail_url, image_url = await sp.start()

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
        )
        if author_name:
            embed.set_author(
                name=author_name,
                icon_url=author_icon_url or EmptyEmbed,
            )
        if footer_text:
            embed.set_footer(
                text=footer_text,
                icon_url=footer_icon_url or EmptyEmbed,
            )
        if thumbnail_url:
            embed.set_thumbnail(
                url=thumbnail_url,
            )
        if image_url:
            embed.set_image(
                url=image_url
            )

        return await channel.send(embed=embed)

    @commands.command(aliases=["rt"],
                      desc="Reacts to a message using an emoji template",
                      usage="reactto [channel_id] [message_id] [template_channel_id] [template_message_id]",
                      note="It will react to the message with all reactions present in the template")
    async def reactto(self, ctx: Context, channel_id: int, message_id: int,
                      template_channel_id: int, template_message_id: int):
        try:
            channel: discord.TextChannel = self.bot.get_channel(channel_id)
            template_channel: discord.TextChannel = self.bot.get_channel(template_channel_id)
            message: discord.Message = await channel.fetch_message(message_id)
            template_message: discord.Message = await template_channel.fetch_message(template_message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            message = template_message = None
        if message:
            success = []
            failed = []
            for reaction in template_message.reactions:
                try:
                    await message.add_reaction(reaction.emoji)
                    success.append(reaction.emoji)
                except Exception:
                    failed.append(reaction.emoji)
            else:
                embed = discord.Embed(
                    title="Reactions Added",
                    description=f"{ctx.author.mention}, I've reacted to the specified messages with "
                    "these emojis:\n" + "\n".join(f"> {emoji}" for emoji in success) +
                    (
                        "\n\nThese emojis were unable to be added:\n\n" +
                        "\n".join(f"> {emoji}" for emoji in failed) if failed else ""
                    ),
                    color=discord.Color.blue(),
                )
        else:
            embed = discord.Embed(
                title="No Message Found",
                description=f"{ctx.author.mention}, I was unable to find a message from the specified ID",
                color=discord.Color.dark_red(),
            )
        return await ctx.channel.send(embed=embed)


def setup(bot: AutoShardedBot) -> None:
    bot.add_cog(Embeds(bot))
