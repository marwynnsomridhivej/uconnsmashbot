import asyncio
import datetime
import random
from collections import deque
from typing import Deque, Iterator, List, Tuple, Union

import discord
from discord.ext.commands import AutoShardedBot, Context

from .cards import uno_cards, uno_thumbnail

COLORS = ['red', 'yellow', 'green', 'blue']
ALL_COLORS = COLORS + ['black']
NUMBERS = list(range(10)) + list(range(1, 10))
SPECIAL_VALUES = ['block', 'reverse', '+2']
COLOR_VALUES = NUMBERS + SPECIAL_VALUES * 2
BLACK_VALUES = ['wild', '+4'] * 4
VALUES = NUMBERS + SPECIAL_VALUES + BLACK_VALUES


class _Canceled(Exception):
    pass


class _Reject(Exception):
    pass


class UnoCard(object):
    __slots__ = [
        "color",
        "value",
    ]

    def __init__(self, color: str, value: str) -> None:
        self.color = color
        self.value = value

    def __str__(self) -> str:
        return f"{uno_cards[str(self.value)][self.color]}"

    def __repr__(self) -> str:
        return f"<UnoCard {', '.join(f'{attr}={getattr(self, attr)}' for attr in self.__slots__)}>"

    def __eq__(self, other: "UnoCard") -> bool:
        return self.color == "black" or self.color == other.color or str(self.value) == str(other.value)

    def __ne__(self, other: "UnoCard") -> bool:
        return not self.__eq__(other)

    def set_color(self, color: str) -> None:
        self.color = color

    def strict_eq(self, other: "UnoCard") -> bool:
        if str(other.value) in ["wild", "+4"]:
            return str(self.value) == str(other.value)
        return str(self.value) == str(other.value) and self.color == other.color

    def nonstrict_eq(self, other: "UnoCard") -> bool:
        return str(self.value) == str(other.value)

    def defer_eq(self, other: "UnoCard") -> bool:
        return str(self.value) in ["+2", "+4"] and str(other.value) in ["+2", "+4"] and str(self.value) == str(other.value)


class DebugUnoCard(UnoCard):
    def __eq__(self, other: "UnoCard") -> bool:
        return True

    def strict_eq(self, other: "UnoCard") -> bool:
        return True

    def nonstrict_eq(self, other: "UnoCard") -> bool:
        return True

    def defer_eq(self, other: "UnoCard") -> bool:
        return True


class UnoPile(object):
    __slots__ = [
        "_cards",
    ]

    def __init__(self) -> None:
        self._cards: Deque = deque([])

    def __len__(self) -> int:
        return len(self._cards)

    def __iter__(self) -> Iterator[UnoCard]:
        for card in self._cards:
            yield card

    @property
    def top_card(self) -> UnoCard:
        return self._cards[0]

    @property
    def top_thumbnail(self) -> str:
        return uno_thumbnail[str(self.top_card.value)][self.top_card.color]

    @property
    def embed_color(self) -> discord.Color:
        if self.top_card.color in ["yellow", "black"]:
            _color = {"yellow": "gold", "black": "darker_grey"}.get(self.top_card.color)
        else:
            _color = self.top_card.color
        return getattr(discord.Color, _color)()

    def place(self, card: UnoCard) -> None:
        self._cards.appendleft(card)

    def set_top_color(self, color: str) -> None:
        self.top_card.set_color(color)

    def reset(self) -> None:
        while len(self._cards) != 1:
            self._cards.pop()


class UnoDeck(object):
    __slots__ = [
        "_cards",
    ]

    def __init__(self, _class: Union[UnoCard, DebugUnoCard]) -> None:
        self._cards: Deque[Union[UnoCard, DebugUnoCard]] = deque(
            [_class(color, value) for value in COLOR_VALUES for color in COLORS] +
            [_class("black", value) for value in BLACK_VALUES]
        )

    def __len__(self) -> int:
        return len(self._cards)

    def __iter__(self) -> Iterator[UnoCard]:
        for card in self._cards:
            yield card

    def shuffle(self):
        random.shuffle(self._cards)

    def deal(self, pile: UnoPile = None) -> UnoCard:
        self.shuffle()
        if not self._cards and pile:
            self.reset(pile)
        return self._cards.popleft()

    def starting_deal(self) -> List[UnoCard]:
        return [self.deal() for _ in range(7)]

    def reset(self, pile: UnoPile) -> None:
        for card in pile:
            self._cards.appendleft(card)
        self.shuffle()
        pile.reset()
        for card in self:
            if str(card.value) in ["+4", "wild"]:
                card.set_color("black")


class UnoPlayer(object):
    __slots__ = [
        "_hand",
        "_member",
        "_finished",
        "_first",
    ]

    def __init__(self, member: discord.Member, deck: UnoDeck) -> None:
        self._hand = deck.starting_deal()
        self._member = member
        self._finished = False
        self._first = True

    def __len__(self) -> int:
        return len(self._hand)

    def __iter__(self) -> Iterator[UnoCard]:
        for card in self._hand:
            yield card

    def __eq__(self, other: "UnoPlayer") -> bool:
        return self._member.id == other._member.id

    def __ne__(self, other: "UnoPlayer") -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return self.get_emoji_group()

    @property
    def hand(self) -> List[UnoCard]:
        return self._hand

    @property
    def member(self) -> discord.Member:
        return self._member

    @property
    def id(self) -> int:
        return self.member.id

    @property
    def mention(self) -> str:
        return self.member.mention

    @property
    def is_uno(self) -> bool:
        return len(self._hand) == 1

    @property
    def finished(self) -> bool:
        return len(self._hand) == 0

    @property
    def is_first_turn(self) -> bool:
        return self._first

    def get_emoji_dm(self, top_card: UnoCard) -> List[str]:
        return [
            str(f"**{index}.**" if card == top_card else f"{index}.") +
            f" {card} - " +
            str(f"***`[{card.color} {card.value}]`*** ⟵" if card == top_card else f"`[{card.color} {card.value}]`")
            for index, card in enumerate(self._hand, 1)
        ]

    def get_emoji_stack_dm(self, top_card: UnoCard, strict: bool = True) -> List[str]:
        return [
            str(f"**{index}.**" if card.strict_eq(top_card) else f"{index}.") +
            f" {card} - " +
            str(f"***`[{card.color} {card.value}]`*** ⟵" if card.strict_eq(top_card)
                else f"`[{card.color} {card.value}]`")
            for index, card in enumerate(self._hand, 1)
        ] if strict else [
            str(f"**{index}.**" if card.nonstrict_eq(top_card) else f"{index}.") +
            f" {card} - " +
            str(f"***`[{card.color} {card.value}]`*** ⟵" if card.nonstrict_eq(top_card)
                else f"`[{card.color} {card.value}]`")
            for index, card in enumerate(self._hand, 1)
        ]

    def get_emoji_defer_dm(self, top_card: UnoCard) -> List[str]:
        return [
            str(f"**{index}.**" if card.defer_eq(top_card) else f"{index}.") +
            f" {card} - " +
            str(f"***`[{card.color} {card.value}]`*** ⟵" if card.defer_eq(top_card)
                else f"`[{card.color} {card.value}]`")
            for index, card in enumerate(self._hand, 1)
        ]

    def get_emoji_group(self, minimal: bool = False) -> str:
        ret = uno_cards["back"] * len(self._hand)
        if len(ret) > 1024 or minimal:
            ret = f"{uno_cards['back']} × {len(self._hand)}"
        return ret

    def draw(self, deck: UnoDeck, pile: UnoPile) -> None:
        self._hand.append(deck.deal(pile=pile))

    def place(self, index: int, pile: UnoPile) -> UnoCard:
        card = self._hand.pop(index)
        pile.place(card)
        return card

    def skip(self, deck: UnoDeck, pile: UnoPile, subturn: int = None) -> None:
        if subturn == 0:
            self.draw(deck, pile)
        self._first = False

    def can_play(self, pile: UnoPile) -> bool:
        return any(card == pile.top_card for card in self)

    def can_stack(self, pile: UnoPile, strict: bool = True) -> bool:
        return any(
            card.strict_eq(pile.top_card) if strict else card.nonstrict_eq(pile.top_card) for card in self
        )

    def can_defer(self, pile: UnoPile) -> bool:
        return any(card.defer_eq(pile.top_card) for card in self)

    def validate(self, index: Union[str, int], pile: UnoPile) -> bool:
        try:
            index = int(index)
            if not 1 <= index <= len(self):
                raise ValueError
            return self._hand[index - 1] == pile.top_card
        except IndexError:
            return False
        except ValueError:
            if index == "cancel" and self._first:
                raise _Canceled
            return False

    def validate_stack(self, index: Union[str, int], pile: UnoPile, strict: bool = True) -> bool:
        try:
            index = int(index)
            if not 1 <= index <= len(self):
                raise ValueError
            return self._hand[index - 1].strict_eq(pile.top_card) if strict else self._hand[index - 1].nonstrict_eq(pile.top_card)
        except IndexError:
            return False
        except ValueError:
            if index == "cancel" and self._first:
                raise _Canceled
            return False

    def validate_defer(self, index: Union[str, int], pile: UnoPile) -> bool:
        try:
            index = int(index)
            if not 1 <= index <= len(self):
                raise ValueError
            return self._hand[index - 1].defer_eq(pile.top_card)
        except IndexError:
            return False
        except ValueError:
            if index == "cancel" and self._first:
                raise _Canceled
            return False

    def play(self, index: Union[str, int], pile: UnoPile) -> UnoCard:
        ret = self.place(index, pile)
        self._first = False
        return ret

    def auto_play(self, pile: UnoPile) -> UnoCard:
        cards = [(card, index) for index, card in enumerate(self) if card == pile.top_card]
        _, index = random.choice(cards)
        return self.play(index, pile)

    def auto_play_stack(self, pile: UnoPile, strict: bool = True) -> UnoCard:
        cards = [
            (card, index) for index, card in enumerate(self) if (
                card.strict_eq(pile.top_card) if strict else card.nonstrict_eq(pile.top_card)
            )
        ]
        _, index = random.choice(cards)
        return self.play(index, pile)

    def auto_play_defer(self, pile: UnoPile) -> UnoCard:
        cards = [(card, index) for index, card in enumerate(self) if card.defer_eq(pile.top_card)]
        _, index = random.choice(cards)
        return self.play(index, pile)

    @staticmethod
    def set_color(color: str, pile: UnoPile) -> None:
        pile.set_top_color(color)

    def auto_set_color(self, pile: UnoPile) -> None:
        _colors = {
            "red": 0,
            "blue": 0,
            "green": 0,
            "yellow": 0,
        }
        for card in self:
            if card.color in _colors:
                _colors[card.color] += 1
        _max = max(value for _, value in _colors.items())
        colors = [key for key, value in _colors.items() if value == _max]
        pile.set_top_color(random.choice(colors))

    async def send(self, timeout: int, embed: discord.Embed = None, cards: List[str] = None) -> discord.Message:
        val = []
        first = True
        for card in cards:
            name = "Your Hand" if first else "Continued..."
            if len("\n".join(val) + "\n" + card) > 1024:
                embed.add_field(
                    name=name,
                    value="\n".join(val),
                    inline=False,
                )
                await self.member.send(embed=embed)
                embed = discord.Embed(color=embed.color)
                first = False
                val = [card]
            else:
                val.append(card)
        embed.add_field(
            name="Your Hand" if first else "Continued...",
            value="\n".join(val),
            inline=False,
        )
        return await self.member.send(
            embed=embed.set_footer(
                text=f"You have {timeout} seconds to make your move, or a random valid card will be picked for you"
            ),
        )


class UnoGame(object):
    __slots__ = [
        "_ctx",
        "_bot",
        "_bet",
        "_deck",
        "_pile",
        "_players",
        "_orig_players",
        "_index",
        "_current_player",
        "_direction",
        "_reversed",
        "_blocked",
        "_plus",
        "_penalty",
        "_turns",
        "_res",
        "_res_fut",
        "_task",
        "_can_stack",
        "_can_skip",
        "_can_defer",
        "_can_forever",
        "_can_jump_in",
        "_default_stack_response",
        "_default_defer_response",
        "_strict_stack",
        "_timeout",
    ]

    def __init__(self, ctx: Context, bot: AutoShardedBot, bet: int,
                 members: List[discord.Member], card_mode: str = "normal",
                 stack: bool = False, skip: bool = False, defer: bool = False,
                 forever: bool = False, jump: bool = False,
                 default_stack: str = "n", default_defer: str = "n",
                 strict_stack: bool = True, timeout: int = 60) -> None:
        self._ctx = ctx
        self._bot = bot
        self._bet = bet
        self._deck: UnoDeck = UnoDeck(DebugUnoCard if card_mode == "debug" else UnoCard)
        self._pile: UnoPile = UnoPile()
        self._players: List[UnoPlayer] = [UnoPlayer(member, self._deck) for member in members]
        self._orig_players: List[discord.Member] = members.copy()
        self._index = 0
        self._current_player = self._players[self._index]
        self._direction = "forwards"
        self._reversed = False
        self._blocked = False
        self._plus = False
        self._penalty: List[int] = []
        self._turns = 1
        self._res: List[UnoPlayer] = []
        self._res_fut = self._bot.loop.create_future()
        self._task = None
        self._can_stack = stack
        self._can_skip = skip
        self._can_defer = defer
        self._can_forever = forever
        self._can_jump_in = jump
        self._default_stack_response = default_stack
        self._default_defer_response = default_defer
        self._strict_stack = strict_stack
        self._timeout = timeout

    @property
    def players(self) -> List[UnoPlayer]:
        return self._players

    @property
    def turns(self) -> int:
        return self._turns

    @property
    def finished(self) -> bool:
        return len(self.players) == 1

    @property
    def current_player(self) -> UnoPlayer:
        return self.players[self._index]

    @property
    def winner(self) -> Union[UnoPlayer, None]:
        return self._res[0] if self._res else None

    @staticmethod
    def _get_formatted_duration(start_timestamp) -> str:
        return str(datetime.timedelta(seconds=int(datetime.datetime.now().timestamp()) - start_timestamp))

    def _toggle_reverse(self) -> None:
        self._direction = "forwards" if self._direction != "forwards" else "backwards"
        self._reversed = True

    def _set_block(self) -> None:
        self._blocked = True

    def _toggle_plus(self) -> None:
        self._plus = True
        self._penalty.append(int(self._pile.top_card.value))

    def _set_next_player(self) -> None:
        if not self.finished:
            if not (self._reversed and len(self._players) == 2):
                if self._direction == "forwards":
                    self._index += 1
                else:
                    self._index -= 1
                self._index %= len(self.players)
            self._turns += 1
        else:
            self._index = 0

    async def _send_game_embed(self, deferred: bool = False) -> Tuple[bool, bool]:
        embed = discord.Embed(
            title="Uno",
            description="",
            color=self._pile.embed_color,
        ).set_author(
            name=f"{self.current_player.member.display_name}'s Turn",
            icon_url=self.current_player.member.avatar_url,
        ).set_thumbnail(
            url=self._pile.top_thumbnail,
        )
        blockstate = plusstate = False
        if deferred:
            embed.description += f"{self.current_player.mention} placed a card to defer the draw penalty"
        elif self._plus:
            plusstate = True
            embed.description += f"{self.current_player.mention} drew {sum(self._penalty)} cards"
            self._plus = False
        elif self._blocked:
            blockstate = True
            embed.description = f"{self.current_player.mention} was blocked! Skipping turn"
            self._blocked = False
        elif self._reversed:
            embed.description += "The player order was reversed"
            self._reversed = False
        nv = []
        players: List[UnoPlayer] = []
        for index in range(len(self.players)):
            _index = int(self._index + index) if self._direction == "forwards" else int(self._index - index)
            player = self.players[
                _index % len(self.players)
            ]
            name = player.member.display_name if player != self.current_player else f"⟶ {player.member.display_name}"
            if player.is_uno:
                name += " - Uno!"
            nv.append((name, str(player)))
            players.append(player)
        too_long = len(embed) + len("".join(n + v for n, v in nv)) > 6000
        for (name, value), player in zip(nv, players):
            embed.add_field(
                name=name,
                value=value if not too_long else player.get_emoji_group(minimal=True),
                inline=False,
            )
        await self._ctx.channel.send(embed=embed.set_footer(
            text=f"Turn {self._turns}" +
            str(f"\nEnter \"cancel\" to cancel the game" if self.current_player.is_first_turn else "") +
            f"\n{players[1].member.display_name} is up next",
        ))
        return blockstate, plusstate

    def _get_dm_embed(self, player: UnoPlayer, method: str = "can_play") -> discord.Embed:
        if not getattr(player, method)(self._pile):
            embed = discord.Embed(
                title="Unable to Place a Card",
                description=f"{player.mention}, you were unable to "
                "place a card, even after drawing another one. Skipping your turn",
                color=self._pile.embed_color,
            )
        else:
            embed = discord.Embed(
                title="Pick a Card",
                description=f"{player.mention}, pick a card to place on "
                "the pile. In the channel with the main uno game, type the index of "
                "the card you would like to place according to their indices listed below. "
                "Arrows denote placeable cards",
                color=self._pile.embed_color,
            )
        return embed.set_thumbnail(
            url=self._pile.top_thumbnail,
        )

    async def _send_dm(self) -> discord.Message:
        embed = self._get_dm_embed(self.current_player)
        cards = self.current_player.get_emoji_dm(self._pile.top_card)
        return await self.current_player.send(self._timeout, embed=embed, cards=cards)

    async def _send_jump_in_dm(self) -> None:
        if self._can_jump_in:
            for player in self.players:
                if player != self.current_player:
                    embed = self._get_dm_embed(player, method="can_stack")
                    cards = player.get_emoji_stack_dm(
                        self._pile.top_card,
                        strict=True,
                    )
                    await player.send(
                        self._timeout, embed=embed, cards=cards
                    )
        return

    async def _set_wild_color(self) -> None:
        await self._ctx.channel.send(
            embed=discord.Embed(
                title="Pick a Color",
                description=f"{self.current_player.mention}, what color should the card become? "
                "You may enter red, blue, green, or yellow"
            ).set_thumbnail(
                url=self._pile.top_thumbnail,
            )
        )
        try:
            message = await self._bot.wait_for(
                "message",
                check=lambda m: m.content.lower() in COLORS and m.channel == self._ctx.channel and m.author.id == self.current_player.id,
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            self.current_player.auto_set_color(self._pile)
        else:
            self.current_player.set_color(message.content.lower(), self._pile)

    async def _select_card(self, subturn: int) -> bool:
        if not self._can_jump_in:
            _CHECK = lambda m: m.channel == self._ctx.channel and m.author.id == self.current_player.id
        else:
            _CHECK = lambda m: m.channel == self._ctx.channel and m.author.id in [
                player.id for player in self.players
            ]
        while True:
            try:
                message = await self._bot.wait_for(
                    "message",
                    check=_CHECK,
                    timeout=self._timeout,
                )
                index = message.content
                if self._can_jump_in and message.author.id != self.current_player.id:
                    card = self._update_current_player(message)
                    break
            except asyncio.TimeoutError:
                card = self.current_player.auto_play(self._pile)
                break
            else:
                if index.lower() == "skip" and self._can_skip and message.author.id == self.current_player.id:
                    card = UnoCard("none", "none")
                    self.current_player.skip(self._deck, self._pile, subturn=subturn)
                    return True
                if self.current_player.validate(index, self._pile):
                    card = self.current_player.play(int(index) - 1, self._pile)
                    break
        if str(card.value) == "block":
            self._set_block()
        elif str(card.value) == "reverse":
            self._toggle_reverse()
        elif "+" in str(card.value):
            self._toggle_plus()
        if self._pile.top_card.color == "black":
            await self._set_wild_color()
        return False

    async def _process_turn(self) -> None:
        skipped = False
        for _subturn in range(2):
            if self.current_player.can_play(self._pile):
                await self._send_dm()
                await self._send_jump_in_dm()
                skipped = await self._select_card(_subturn)
                break
            elif _subturn == 0:
                if self._can_forever:
                    while not self.current_player.can_play(self._pile):
                        self.current_player.draw(self._deck, self._pile)
                else:
                    self.current_player.draw(self._deck, self._pile)
        else:
            await self._send_dm()

        while not skipped and self._can_stack and self.current_player.can_stack(self._pile, strict=self._strict_stack):
            try:
                await self._proceed_stack()
            except _Reject:
                break

    async def _proceed_stack(self) -> None:
        await self._ctx.channel.send(
            embed=discord.Embed(
                title="Stack Cards",
                description=f"{self.current_player.mention}, would you like to stack a card? Type \"yes\" or \"y\" "
                "to proceed, otherwise your turn will end",
                color=self._pile.embed_color,
            ).set_footer(
                text="You have 15 seconds to make your decision",
            )
        )
        try:
            message = await self._bot.wait_for(
                "message",
                check=lambda m: m.content.lower(
                ) in ["y", "yes", "n", "no"] and m.author.id == self.current_player.id and m.channel == self._ctx.channel,
                timeout=15,
            )
            conf = message.content.lower()
        except asyncio.TimeoutError:
            conf = self._default_stack_response
        if not conf in ["y", "yes"]:
            raise _Reject
        await self._process_stack()

    async def _process_stack(self) -> None:
        await self._ctx.send(
            embed=discord.Embed(
                title="Uno",
                description=f"{self.current_player.mention}, please pick a card to stack",
                color=self._pile.embed_color,
            ).set_author(
                name=f"{self.current_player.member.display_name} is Picking a Card...",
                icon_url=self.current_player.member.avatar_url,
            ).set_thumbnail(
                url=self._pile.top_thumbnail,
            )
        )
        await self._select_stack_card()

    async def _select_stack_card(self) -> None:
        embed = discord.Embed(
            title="Pick a Card",
            description=f"{self.current_player.mention}, pick a card to place on "
            "the pile. In the channel with the main uno game, type the index of "
            "the card you would like to place according to their indices listed below. "
            "Arrows denote placeable cards",
            color=self._pile.embed_color,
        ).set_thumbnail(
            url=self._pile.top_thumbnail,
        )
        cards = self.current_player.get_emoji_stack_dm(self._pile.top_card, strict=self._strict_stack)
        await self.current_player.send(self._timeout, embed=embed, cards=cards)
        while True:
            try:
                message = await self._bot.wait_for(
                    "message",
                    check=lambda m: m.channel == self._ctx.channel and m.author.id == self.current_player.id,
                    timeout=self._timeout,
                )
                index = message.content
            except asyncio.TimeoutError:
                card = self.current_player.auto_play_stack(self._pile, strict=self._strict_stack)
                break
            else:
                if self.current_player.validate_stack(index, self._pile, strict=self._strict_stack):
                    card = self.current_player.play(int(index) - 1, self._pile)
                    break
        if str(card.value) == "block":
            self._set_block()
        elif str(card.value) == "reverse":
            self._toggle_reverse()
        elif "+" in str(card.value):
            self._toggle_plus()
        if self._pile.top_card.color == "black":
            await self._set_wild_color()

    async def _defer(self) -> bool:
        try:
            ret = self._can_defer and self._penalty and self.current_player.can_defer(self._pile)
            if ret:
                await self._get_defer()
                self._plus = False
            elif self._penalty:
                self._plus = True
            return bool(ret)
        except _Reject:
            return False

    async def _get_defer(self) -> bool:
        await self._ctx.channel.send(
            embed=discord.Embed(
                title="Defer",
                description=f"{self.current_player.mention}, would you like to defer the draw penalty by placing down "
                "a valid deferrable card? Type \"yes\" or \"y\" to proceed, otherwise your turn will end",
                color=self._pile.embed_color,
            ).set_footer(
                text="You have 15 seconds to make your decision",
            )
        )
        try:
            message = await self._bot.wait_for(
                "message",
                check=lambda m: m.content.lower(
                ) in ["y", "yes", "n", "no"] and m.author.id == self.current_player.id and m.channel == self._ctx.channel,
                timeout=15,
            )
            conf = message.content.lower()
        except asyncio.TimeoutError:
            conf = self._default_defer_response
        if not conf in ["y", "yes"]:
            raise _Reject
        return await self._process_defer()

    async def _process_defer(self) -> bool:
        await self._ctx.send(
            embed=discord.Embed(
                title="Uno",
                description=f"{self.current_player.mention}, please pick a card to place to defer the draw penalty",
                color=self._pile.embed_color,
            ).set_author(
                name=f"{self.current_player.member.display_name} is Picking a Card...",
                icon_url=self.current_player.member.avatar_url,
            ).set_thumbnail(
                url=self._pile.top_thumbnail,
            )
        )
        return await self._select_defer_card()

    async def _select_defer_card(self) -> bool:
        embed = discord.Embed(
            title="Pick a Card",
            description=f"{self.current_player.mention}, pick a card to place on "
            "the pile. In the channel with the main uno game, type the index of "
            "the card you would like to place according to their indices listed below. "
            "Arrows denote placeable cards",
            color=self._pile.embed_color,
        ).set_thumbnail(
            url=self._pile.top_thumbnail,
        )
        cards = self.current_player.get_emoji_defer_dm(self._pile.top_card)
        await self.current_player.send(self._timeout, embed=embed, cards=cards)
        while True:
            try:
                message = await self._bot.wait_for(
                    "message",
                    check=lambda m: m.channel == self._ctx.channel and m.author.id == self.current_player.id,
                    timeout=self._timeout,
                )
                index = message.content
            except asyncio.TimeoutError:
                card = self.current_player.auto_play_defer(self._pile)
                break
            else:
                if self.current_player.validate_defer(index, self._pile):
                    card = self.current_player.play(int(index) - 1, self._pile)
                    break
        if str(card.value) == "block":
            self._set_block()
        elif str(card.value) == "reverse":
            self._toggle_reverse()
        elif "+" in str(card.value):
            self._toggle_plus()
        if self._pile.top_card.color == "black":
            await self._set_wild_color()

    def _update_current_player(self, message: discord.Message) -> Union[UnoCard, None]:
        players = [
            player for player in self._players if player.id == message.author.id
        ]
        if players:
            player = players[0]
            if player.validate_stack(message.content, self._pile, strict=True):
                card = player.play(int(message.content) - 1, self._pile)
                for _ in self.players:
                    if self.current_player == player:
                        break
                    self._index += 1
                    self._index %= len(self.players)
                return card

    def _finish_player(self) -> None:
        try:
            self._res_fut.set_result(self.current_player)
        except asyncio.InvalidStateError:
            pass
        self._res.append(self.current_player)
        self._players.remove(self.current_player)
        if self._direction == "forwards":
            self._index -= 1
        elif self._direction == "backwards":
            self._index += 1

    async def _distribute_rewards(self) -> None:
        await self._res_fut
        winner: UnoPlayer = self._res_fut.result()
        win_amount = self._bet * len(self._orig_players)
        async with self._bot.db.acquire() as con:
            await con.execute(
                f"INSERT INTO balance(user_id, amount) VALUES ({winner.id}, {1000 + win_amount}) "
                f"ON CONFLICT (user_id) DO UPDATE SET amount=balance.amount+{win_amount} "
                "WHERE balance.user_id=EXCLUDED.user_id"
            )
            await con.execute(
                f"INSERT INTO uno(user_id, played, win) VALUES ({winner.id}, 1, 1) ON CONFLICT "
                "(user_id) DO UPDATE SET played=uno.played+1, win=uno.win+1 WHERE uno.user_id=EXCLUDED.user_id"
            )
            self._orig_players.remove(winner.member)
            for player in self._orig_players:
                await con.execute(
                    f"INSERT INTO balance(user_id, amount) VALUES ({player.id}, {1000 - self._bet}) "
                    f"ON CONFLICT (user_id) DO UPDATE SET amount=balance.amount-{self._bet} "
                    "WHERE balance.user_id=EXCLUDED.user_id"
                )
                await con.execute(
                    f"INSERT INTO uno(user_id, played) VALUES ({player.id}, 1) ON CONFLICT "
                    "(user_id) DO UPDATE SET played=uno.played+1 WHERE uno.user_id=EXCLUDED.user_id"
                )
        await self._ctx.channel.send(
            embed=discord.Embed(
                title=f"{winner.member.display_name} Wins!",
                description=f"Congratulations {winner.mention} for winning this Uno game! Other "
                "players may still play to completion, but rewards have already been distributed",
                color=discord.Color.blue(),
            ).add_field(
                name="Winnings",
                value=f"```{win_amount} credits```",
            )
        )

    def _configure_discard(self) -> None:
        self._pile.place(self._deck.deal())
        while self._pile.top_card.color == "black":
            self._pile.place(self._deck.deal())

    async def _start(self) -> int:
        ret = int(datetime.datetime.now().timestamp())
        self._configure_discard()
        self._task = self._bot.loop.create_task(self._distribute_rewards())
        while not self.finished:
            deferred = await self._defer()
            if self._plus or (self._penalty and not deferred):
                for _ in range(sum(self._penalty)):
                    self.current_player.draw(self._deck, self._pile)
            blockstate, plusstate = await self._send_game_embed(deferred=deferred)
            if not deferred and self._penalty:
                self._penalty.clear()
            if not (blockstate or plusstate or deferred):
                await self._process_turn()
            if self.current_player.finished:
                self._finish_player()
            self._set_next_player()
        self._finish_player()
        return ret

    @staticmethod
    def _handle_task_exception(task: asyncio.Task) -> None:
        task.result()

    def _cancel_task(self) -> None:
        if not self._task.done():
            self._task.cancel()

    async def play(self) -> discord.Message:
        try:
            random.shuffle(self._players)
            start_time = await self._start()
            duration = self._get_formatted_duration(start_time)
            return await self._ctx.channel.send(
                embed=discord.Embed(
                    title="Uno",
                    description="Here are stats for the finished Uno game",
                    color=discord.Color.blue(),
                ).set_author(
                    name="Results",
                    icon_url=self._bot.user.avatar_url,
                ).add_field(
                    name="Standings",
                    value="\n".join(
                        f"**{index}:** {player.mention}" for index, player in enumerate(self._res, 1)
                    ),
                    inline=False,
                ).add_field(
                    name="Turns",
                    value=self._turns,
                    inline=False,
                ).add_field(
                    name="Duration",
                    value=duration,
                    inline=False,
                )
            )
        except discord.Forbidden:
            self._cancel_task()
            return await self._ctx.channel.send(
                embed=discord.Embed(
                    title="Unable to Send DM",
                    description=f"{self.current_player.mention}, I cannot send a DM to you that "
                    "contains your cards, therefore the game has been canceled",
                    color=discord.Color.dark_red(),
                ).set_footer(
                    text="In order to play Uno, please make sure UconnSmashBot is able to DM you"
                )
            )
        except _Canceled:
            self._cancel_task()
            return await self._ctx.channel.send(
                embed=discord.Embed(
                    title="Game Canceled",
                    description=f"{self.current_player.mention} canceled this game",
                    color=discord.Color.dark_red(),
                )
            )
        except Exception:
            self._cancel_task()
            raise
