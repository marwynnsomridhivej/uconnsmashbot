import asyncio
import re
from typing import Any, Awaitable, Callable, List, NamedTuple, Tuple, Union

import discord
from discord.embeds import EmptyEmbed
from discord.ext.commands import AutoShardedBot, Bot, Context

_MAP = {
    "content": "_get_message_content",
    "message": "_get_message_content",
    "channel": "_get_channel",
    "role": "_get_role",
    "emoji": "_get_emoji",
    "reaction": "_get_emoji",
    "member": "_get_member",
    "integer": "_get_integer",
    "float": "_get_float",
    "title": "_get_title",
    "description": "_get_description",
    "color": "_get_color",
    "author": "_get_author",
    "footer": "_get_footer",
    "url": "_get_url",
}
_HEX_COLOR_RX = re.compile(r'#[A-Fa-f0-9]{6}')
_URL_RX = re.compile(r'https?://(?:www\.)?.+')


class _Timeout(Exception):
    timeout: int


class _Cancel(Exception):
    pass


class _BreakCheck(Exception):
    pass


class _CoroStep(NamedTuple):
    name: str
    coro: Awaitable
    conditional: bool = False
    loop: bool = False
    group_loop: bool = False


class SetupPanel(object):
    """Intuitive and flexible configuration of interactive embed-based setup panels for discord.py

    Parameters
    ------
    bot :class:Union[`Bot`, `AutoShardedBot`]
        - The instance of a discord bot

    ctx :class:`Context`
        - The command's invocation context

    title :class:`str`
        - The title of this setup panel

    duplicate_roles Optional[:class:`bool`]
        - Whether or not this setup panel allows duplicate roles to be specified in any given looping step
        - Defaults to `False`

    duplicate_role_embed Optional[:class:`discord.Embed`]
        - The embed to send if a duplicate role is received and :param:`duplicate_roles` is `False`
        - Defaults to `None`

    duplicate_emojis Optional[:class:`bool`]
        - Whether or not this setup panel allows duplicate emojis to be specified in any given looping step
        - Defaults to `False`

    duplicate_emoji_embed Optional[:class:`discord.Embed`]
        - The embed to send if a duplicate emoji is received and :param:`duplicate_emojis` is `False`
        - Defaults to `None`

    error_color Optional[:class:Union[`discord.Color, int`]]
        - The color to use as the color of the embed that will be sent upon user canceling or setup timing out
        - Defaults to `discord.Color.dark_red()`
        - Supports int, but prefer discord.Color to be safe
    """
    __slots__ = [
        "bot",
        "ctx",
        "title",
        "intro",
        "error_color",
        "duplicate_roles",
        "duplicate_role_embed",
        "duplicate_emojis",
        "duplicate_emoji_embed",
        "_coros",
        "_emojis",
        "_ret",
        "_roles",
        "_used",
    ]

    def __init__(self, *,
                 bot: Union[Bot, AutoShardedBot],
                 ctx: Context,
                 title: str,
                 duplicate_roles: bool = False,
                 duplicate_role_embed: discord.Embed = None,
                 duplicate_emojis: bool = False,
                 duplicate_emoji_embed: discord.Embed = None,
                 error_color: Union[discord.Color, int] = discord.Color.dark_red()) -> None:
        self.bot = bot
        self.ctx = ctx
        self.title = f"{title.title()} Setup" if title else "Setup"
        self.intro: Tuple[discord.Embed, Union[int, float]] = ()
        self.error_color = error_color
        self.duplicate_roles = duplicate_roles
        self.duplicate_role_embed = duplicate_role_embed or discord.Embed(
            title="Role Already Entered",
            description=f"{self.ctx.author.mention}, that role has already been entered. Please mention a different role",
            color=self.error_color,
        )
        self.duplicate_emojis = duplicate_emojis
        self.duplicate_emoji_embed = duplicate_emoji_embed or discord.Embed(
            title="Emoji Already Entered",
            description=f"{self.ctx.author.mention}, that emoji has already been entered. Please specify a different emoji",
            color=self.error_color,
        ).set_footer(
            text="React to the original message"
        )
        self._coros: List[_CoroStep] = []
        self._emojis: List[str] = []
        self._ret = []
        self._roles: List[discord.Role] = []
        self._used = False

    async def __call__(self) -> Union[List[Any], None]:
        return await self.start()

    def __len__(self) -> int:
        return len(self._coros)

    async def _wait_for_message(self, timeout: int, predicate: Callable = None, break_check: Callable = None) -> discord.Message:
        try:
            message = await self.bot.wait_for(
                "message",
                check=predicate if predicate else lambda m: m.author == self.ctx.author and m.channel == self.ctx.channel,
                timeout=timeout,
            )
        except asyncio.TimeoutError as e:
            raise _Timeout(timeout=timeout) from e

        if message.content == "cancel":
            raise _Cancel()
        elif break_check and break_check(message):
            raise _BreakCheck()
        return message

    async def _wait_for_reaction(self, message: discord.Message, timeout: int, predicate: Callable = None, break_check: Callable = None) -> discord.Reaction:
        try:
            reaction, _ = await self.bot.wait_for(
                "reaction_add",
                check=predicate if predicate else lambda r, u: r.message.id == message.id and u.id == self.ctx.author.id,
                timeout=timeout,
            )
        except asyncio.TimeoutError as e:
            raise _Timeout(timeout=timeout) from e

        if break_check and break_check(reaction, _):
            raise _BreakCheck()
        return reaction

    async def _get_message_content(self, embed: discord.Embed, timeout: int = 120, *, predicate, break_check) -> str:
        await self.ctx.channel.send(embed=embed)
        message = await self._wait_for_message(timeout, predicate=predicate, break_check=break_check)
        return message.content

    async def _get_channel(self, embed: discord.Embed, timeout: int = 120, *, predicate, break_check) -> discord.TextChannel:
        await self.ctx.channel.send(embed=embed)
        channel: discord.TextChannel = None
        while not channel:
            message = await self._wait_for_message(timeout, predicate=predicate, break_check=break_check)
            try:
                channel = self.bot.get_channel(int(message.content[2:20]))
            except (ValueError, TypeError):
                pass
        return channel

    async def _get_role(self, embed: discord.Embed, timeout: int = 120, *, predicate, break_check) -> discord.Role:
        await self.ctx.channel.send(embed=embed)
        role: discord.Role = None
        while not role:
            message = await self._wait_for_message(timeout, predicate=predicate, break_check=break_check)
            try:
                role = self.ctx.guild.get_role(int(message.content[3:21]))
                if not self.duplicate_roles and role in self._roles:
                    role = None
                    await self.ctx.channel.send(embed=self.duplicate_role_embed)
            except (ValueError, TypeError):
                pass
            else:
                self._roles.append(role)
        return role

    async def _get_emoji(self, embed: discord.Embed, timeout: int = 120, *, predicate: Callable, break_check: Callable) -> str:
        message = await self.ctx.channel.send(embed=embed)
        reaction: discord.Reaction = None
        while not reaction:
            reaction = await self._wait_for_reaction(message, timeout, predicate=predicate, break_check=break_check)
            if not self.duplicate_emojis and reaction.emoji in self._emojis:
                reaction = None
                await self.ctx.channel.send(embed=self.duplicate_emoji_embed)
            else:
                self._emojis.append(reaction.emoji)
        return reaction.emoji

    async def _get_member(self, embed: discord.Embed, timeout: int = 120, *, predicate: Callable, break_check: Callable) -> discord.Member:
        await self.ctx.channel.send(embed=embed)
        member = 0
        while member is 0:
            message = await self._wait_for_message(timeout, predicate=predicate, break_check=break_check)
            try:
                member = self.ctx.guild.get_member(int(message.content[3:21]))
            except (ValueError, TypeError):
                pass
        return member

    async def _get_integer(self, embed: discord.Embed, timeout: int = 120, *, predicate: Callable, break_check: Callable) -> int:
        await self.ctx.channel.send(embed=embed)
        _int = None
        while _int is None:
            message = await self._wait_for_message(timeout, predicate=predicate, break_check=break_check)
            try:
                _int = int(message.content)
            except (ValueError, TypeError):
                pass
        return _int

    async def _get_float(self, embed: discord.Embed, timeout: int = 120, *, predicate: Callable, break_check: Callable) -> float:
        await self.ctx.channel.send(embed=embed)
        _float = None
        while _float is None:
            message = await self._wait_for_message(timeout, predicate=predicate, break_check=break_check)
            try:
                _float = float(message.content)
            except (ValueError, TypeError):
                pass
        return _float

    async def _get_title(self, embed: discord.Embed, timeout: int = 120, *, predicate: Callable, break_check: Callable) -> Union[str, "EmptyEmbed"]:
        await self.ctx.channel.send(embed=embed)
        message = None
        while not message:
            try:
                message = await self._wait_for_message(timeout, predicate=predicate, break_check=break_check)
                if len(message.content) > 256:
                    raise ValueError
            except ValueError:
                _embed = embed.copy()
                _embed.description += f"\nThe title may be at most 256 characters long"
                await self.ctx.channel.send(embed=_embed)
        return message.content if message.content != "none" else EmptyEmbed

    async def _get_description(self, *args, **kwargs) -> Union[str, "EmptyEmbed"]:
        ret = await self._get_message_content(*args, **kwargs)
        return ret if ret != "none" else EmptyEmbed

    async def _get_color(self, embed: discord.Embed, timeout: int = 120, *, predicate: Callable, break_check: Callable) -> discord.Color:
        await self.ctx.channel.send(embed=embed)
        color = None
        while not color:
            try:
                message = await self._wait_for_message(timeout, predicate=predicate, break_check=break_check)
                if _HEX_COLOR_RX.match(message.content):
                    color = int(message.content[1:], 16)
            except ValueError:
                await self.ctx.channel.send(embed=embed)
        return discord.Color(value=color)

    async def _get_author(self, *args, **kwargs) -> Union[str, None]:
        ret = await self._get_title(*args, **kwargs)
        return ret if ret is not EmptyEmbed else None

    async def _get_footer(self, *args, **kwargs) -> Union[str, None]:
        ret = await self._get_description(*args, **kwargs)
        return ret if ret is not EmptyEmbed else None

    async def _get_url(self, *args, **kwargs) -> Union[str, None]:
        ret = await self._get_message_content(*args, **kwargs)
        return ret if _URL_RX.match(ret) else None

    async def _looper(self, coro: Callable, embed: discord.Embed, timeout: int, predicate: Callable, break_check: Callable) -> List[Any]:
        ret = []
        while True:
            try:
                res = await coro(embed, timeout, predicate=predicate, break_check=break_check)
            except _BreakCheck:
                break
            else:
                ret.append(res)
        return ret

    async def _grouper(self, coros: List[Callable], embeds: List[discord.Embed], timeouts: List[int], predicates: List[Callable], break_checks: List[Callable]) -> List[List[Any]]:
        ret = []
        broken = False
        while not broken:
            intermediate = []
            for coro, embed, timeout, predicate, break_check in zip(coros, embeds, timeouts, predicates, break_checks):
                try:
                    res = await coro(embed=embed, timeout=timeout, predicate=predicate, break_check=break_check)
                except _BreakCheck:
                    broken = True
                    break
                else:
                    intermediate.append(res)
            else:
                ret.append(intermediate)
        return ret

    async def _conditional_wrapper(self, coro: Callable, embed: discord.Embed, timeout: int, condition: Callable = lambda _: True, **kwargs) -> Any:
        try:
            res = await coro(embed, timeout, **kwargs) if condition(self._ret[-1]) else None
        except _BreakCheck:
            return None
        return res

    @property
    def info(self) -> Union[List[Tuple[str, bool, bool, bool]], None]:
        r"""Get information about the steps in a `SetupPanel` instance

        Returns
        ------
        :class:Union[`List[Tuple[str, bool, bool, bool]], None`]
            - If steps are added, a list containing the tuple of name, conditional flag, loop flag, and group_loop flag for each step
            - If no steps have been added, :type:`None`
        """
        if not self._coros:
            return None
        return [(step.name, step.conditional, step.loop, step.group_loop) for step in self._coros]

    @property
    def is_used(self) -> bool:
        r"""Check to see if setup panel has been used before
        """
        return self._used

    def add_intro(self, *, embed: discord.Embed, wait_time: Union[int, float]) -> "SetupPanel":
        r"""Adds an intro embed to be sent, followed by a pause before the setup begins processing input

        Parameters
        ------
        embed :class:`discord.Embed`
            - The embed to be sent as the intro message

        wait_time :class:`Union[int, float]`
            - The amount of time to pause for before processing all added steps

        Raises
        ------
        :exc:`ValueError`
            - :param:`embed` must be an instance of discord.Embed
            - :param:`wait_time` must be either an int or a float greater than or equal to 0

        Returns
        ------
        :class:`SetupPanel`
            - Returns its own instance for fluid chaining
        """
        if not isinstance(embed, discord.Embed):
            raise ValueError("embed argument must be an instance of discord.Embed")
        if not isinstance(wait_time, (int, float)):
            raise ValueError("wait_time argument must be either an int or a float")
        if not wait_time >= 0:
            raise ValueError("wait_time argument must be greater than or equal to 0")
        self.intro = (embed, wait_time)
        return self

    def add_step(self, *, name: str, embed: discord.Embed, timeout: int = 120, predicate: Callable = None, break_check: Callable = None) -> "SetupPanel":
        r"""Add one sequential step in the setup tasks

        Parameters
        ------
        name :class:`str`
            - The setup operation name
            - Names include
                - content :class:`str`
                - message :class:`str` (alias for content)
                - channel :class:`discord.TextChannel`
                - role :class:`discord.Role`
                - emoji :class:`str`
                - reaction :class:`str` (alias for emoji)
                - member :class:`discord.Member`
                - integer :class:`int`
                - float :class:`float`
                - title :class:`Union[str, EmptyEmbed]`
                - description :class:`Union[str, EmptyEmbed]`
                - color :class:`discord.Color`
                - author :class:`Union[str, None]`
                - footer :class:`Union[str, None]`
                - url :class:`Union[str, None]`

        embed :class:`discord.Embed`
            - The embed to display during the step

        timeout Optional[:class:`int`]
            - The time in seconds to wait for a user to reply with an option that satisfies :param:`predicate`
            - Defaults to 120

        predicate Optional[:class:`Callable`]
            - A custom predicate returning a :type:`bool` for input validation
            - Must accept one argument of type :class:`discord.Message`
                - For `emoji`, must accept two arguments of types :class:`discord.Reaction` :class:`discord.User`

        Raises
        ------
        :exc:`ValueError`
            - :param:`name` must be one of the above names

        Returns
        ------
        :class:`SetupPanel`
            - Returns its own instance for fluid chaining
        """
        try:
            coro = getattr(self, _MAP[name])
        except KeyError as e:
            raise ValueError(f"{name} is not a supported operation") from e
        else:
            self._coros.append(
                _CoroStep(
                    name=name,
                    coro=coro(
                        embed, timeout=timeout, predicate=predicate, break_check=break_check
                    ),
                )
            )
        finally:
            return self

    def add_conditional_step(self, *, name: str, embed: discord.Embed, condition: Callable, timeout: int = 120, predicate: Callable = None, break_check: Callable = None) -> "SetupPanel":
        r"""Add one sequential conditional step in the setup tasks

        Parameters
        ------
        name :class:`str`
            - The setup operation name
            - Names include
                - content :class:`str`
                - message :class:`str` (alias for content)
                - channel :class:`discord.TextChannel`
                - role :class:`discord.Role`
                - emoji :class:`str`
                - reaction :class:`str` (alias for emoji)
                - member :class:`discord.Member`
                - integer :class:`int`
                - float :class:`float`
                - title :class:`Union[str, EmptyEmbed]`
                - description :class:`Union[str, EmptyEmbed]`
                - color :class:`discord.Color`
                - author :class:`Union[str, None]`
                - footer :class:`Union[str, None]`
                - url :class:`Union[str, None]`

        embed :class:`discord.Embed`
            - The embed to display during the step

        condition :class:`Callable`
            - A condition that accepts the result of the last step, returning a :type:`bool`
            - This step's execution is dependent on the result of :param:`condition`

        timeout Optional[:class:`int`]
            - The time in seconds to wait for a user to reply with an option that satisfies :param:`predicate`
            - Defaults to 120

        predicate Optional[:class:`Callable`]
            - A custom predicate returning a :type:`bool` for input validation
            - Must accept one argument of type :class:`discord.Message`
                - For `emoji`, must accept two arguments of types :class:`discord.Reaction` :class:`discord.User`

        Raises
        ------
        :exc:`ValueError`
            - :param:`name` must be one of the above names

        Returns
        ------
        :class:`SetupPanel`
            - Returns its own instance for fluid chaining
        """
        try:
            coro = getattr(self, _MAP[name])
        except KeyError as e:
            raise ValueError(f"{name} is not a supported operation") from e
        else:
            self._coros.append(
                _CoroStep(
                    name=name,
                    coro=self._conditional_wrapper(
                        coro, embed, timeout, condition=condition, predicate=predicate, break_check=break_check
                    ),
                    conditional=True,
                )
            )
        finally:
            return self

    def add_until_finish(self, *, name: str, embed: discord.Embed, break_check: Callable, timeout: int = 120, predicate: Callable = None) -> "SetupPanel":
        r"""Add one sequential looping step in the setup tasks

        Parameters
        ------
        name :class:`str`
            - The setup operation name
            - Names include
                - content :class:`str`
                - message :class:`str` (alias for content)
                - channel :class:`discord.TextChannel`
                - role :class:`discord.Role`
                - emoji :class:`str`
                - reaction :class:`str` (alias for emoji)
                - member :class:`discord.Member`
                - integer :class:`int`
                - float :class:`float`
                - title :class:`Union[str, EmptyEmbed]`
                - description :class:`Union[str, EmptyEmbed]`
                - color :class:`discord.Color`
                - author :class:`Union[str, None]`
                - footer :class:`Union[str, None]`
                - url :class:`Union[str, None]`

        embed :class:`discord.Embed`
            - The embed to display during the step

        break_check `Callable`
            - A custom check that accept the same arguments as :param:`predicate`, returning a :type:`bool`
                - If a :param:`break_check` returns `True`, it will break out of the loop and proceed to the next step

        timeout Optional[:class:`int`]
            - The time in seconds to wait for a user to reply with an option that satisfies :param:`predicate`
            - Defaults to 120

        predicate Optional[:class:`Callable`]
            - A custom predicate returning a :type:`bool` for input validation
            - Must accept one argument of type :class:`discord.Message`
                - For `emoji`, must accept two arguments of types :class:`discord.Reaction` :class:`discord.User`


        Raises
        ------
        :exc:`ValueError`
            - :param:`name` must be one of the above names

        Returns
        ------
        :class:`SetupPanel`
            - Returns its own instance for fluid chaining
        """
        try:
            coro = getattr(self, _MAP[name])
        except KeyError as e:
            raise ValueError(f"{name} is not a supported operation") from e
        else:
            self._coros.append(
                _CoroStep(
                    name=name,
                    coro=self._looper(
                        coro, embed, timeout, predicate=predicate, break_check=break_check
                    ),
                    loop=True,
                )
            )
        finally:
            return self

    def add_group_loop(self, *, names: List[str], embeds: List[discord.Embed], timeouts: List[int], break_checks: List[Callable], predicates: List[Callable] = None) -> "SetupPanel":
        r"""Add one sequential grouped looping step in the setup tasks

        Parameters
        ------
        names List[:class:`str`]
            - The setup operation name
            - Names include
                - content :class:`str`
                - message :class:`str` (alias for content)
                - channel :class:`discord.TextChannel`
                - role :class:`discord.Role`
                - emoji :class:`str`
                - reaction :class:`str` (alias for emoji)
                - member :class:`discord.Member`
                - integer :class:`int`
                - float :class:`float`
                - title :class:`Union[str, EmptyEmbed]`
                - description :class:`Union[str, EmptyEmbed]`
                - color :class:`discord.Color`
                - author :class:`Union[str, None]`
                - footer :class:`Union[str, None]`
                - url :class:`Union[str, None]`

        embeds :class:`List[discord.Embed]`
            - Embeds to display during the step

        break_checks `List[Callable]`
            - Custom checks that accept the same arguments as :param:`predicates`, returning a :type:`bool`
                - If a :param:`break_check` returns `True`, it will break out of the loop and proceed to the next step

        timeouts `List[int]`
            - Times in seconds to wait for a user to reply with an option that satisfies :param:`predicate`

        predicates Optional[:class:`List[Callable]`]
            - Custom predicates returning a :type:`bool` for input validation
            - Must accept one argument of type :class:`discord.Message`
                - For `emoji`, must accept two arguments of types :class:`discord.Reaction` :class:`discord.User`

        Raises
        ------
        :exc:`ValueError`
            - :param:`names` must be one of the above names

        Returns
        ------
        :class:`SetupPanel`
            - Returns its own instance for fluid chaining
        """
        try:
            if not all(name in _MAP for name in names):
                raise ValueError
            coros = [getattr(self, _MAP[name]) for name in names]
            if not predicates:
                predicates = [None for _ in range(len(coros))]
            if not len(coros) == len(embeds) == len(timeouts) == len(predicates) == len(break_checks):
                raise ValueError
        except ValueError as e:
            raise ValueError(
                "Please ensure that you provide valid names and the same amount of arguments in each iterable") from e
        else:
            self._coros.append(
                _CoroStep(
                    name=" | ".join(names),
                    coro=self._grouper(
                        coros, embeds, timeouts, predicates, break_checks
                    ),
                    loop=True,
                    group_loop=True,
                )
            )
        finally:
            return self

    async def start(self) -> Union[List[Any], None]:
        """Starts the setup steps in sequential order

        Returns
        ------
        :class:Union[`List[Any], None`]
            - Returns an aggregate list of the results of the setup steps
            - If setup is canceled or times out, returns :type:`None`
        """
        if self._used:
            raise RuntimeError("Cannot re-use an already used setup panel")
        self._used = True
        if self.intro:
            embed, wait_time = self.intro
            await self.ctx.channel.send(embed=embed)
            await asyncio.sleep(wait_time)
        for step in self._coros:
            try:
                res = await step.coro
                self._ret.append(res)
            except _Cancel:
                await self.ctx.channel.send(
                    embed=discord.Embed(
                        title=f"{self.title.title()} Canceled",
                        description=f"{self.ctx.author.mention}, the {self.title.lower()} was canceled",
                        color=self.error_color,
                    )
                )
                return None
            except _Timeout as t:
                await self.ctx.channel.send(
                    embed=discord.Embed(
                        title=f"{self.title.title()} Timed Out",
                        description=f"{self.ctx.author.mention}, the {self.title.lower()} timed out after {t.timeout} seconds of inactivity",
                        color=self.error_color,
                    )
                )
                return None
            except _BreakCheck:
                self._ret.append(None)
            self._roles.clear()
            self._emojis.clear()
        return self._ret
