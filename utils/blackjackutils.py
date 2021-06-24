import asyncio
import random
from collections import deque
from typing import Callable, Deque, List, NamedTuple

import discord
from discord.ext.commands import AutoShardedBot, Context

from .cards import playing_cards
from .customerrors import BlackjackCanceled

__all__ = (
    "Card",
    "Deck",
    "Hand",
    "Player",
    "Dealer",
    "BlackjackResult",
    "BlackjackGame",
)

_EMOJIS = ["✅", "❌", "🛑"]
_MAP = {
    _EMOJIS[0]: "_hit",
    _EMOJIS[1]: "_stand",
    _EMOJIS[2]: "_cancel",
}
_SUITS = frozenset([
    'Hearts',
    'Diamonds',
    'Spades',
    'Clubs',
])
_RANKS = frozenset([
    'Two',
    'Three',
    'Four',
    'Five',
    'Six',
    'Seven',
    'Eight',
    'Nine',
    'Ten',
    'Jack',
    'Queen',
    'King',
    'Ace',
])
_VALUES = {
    'Two': 2,
    'Three': 3,
    'Four': 4,
    'Five': 5,
    'Six': 6,
    'Seven': 7,
    'Eight': 8,
    'Nine': 9,
    'Ten': 10,
    'Jack': 10,
    'Queen': 10,
    'King': 10,
    'Ace': 11,
}


class Card(object):
    """Represents a Blackjack card

    Attributes:
    ------
    suit :class:`str`
        - The suit of the card

    rank :class:`str`
        - The rank of the card

    value :class:`int`
        - The value of the card

    emoji :class:`str`
        - The emoji of the card in <name:id> format rendered for Discord
    """
    __slots__ = [
        "_suit",
        "_rank",
        "_value",
        "_emoji",
    ]

    def __init__(self, *, suit: str, rank: str) -> None:
        self._suit: str = suit
        self._rank: str = rank
        self._value: int = _VALUES[rank]
        self._emoji: str = playing_cards[rank][suit]

    def __str__(self) -> str:
        return f"{self.rank} of {self.suit}"

    def __repr__(self) -> str:
        return f"<Card suit={self.suit}, rank={self.rank}, value={self.value}, emoji={self.emoji}>"

    @property
    def suit(self) -> str:
        return self._suit

    @property
    def rank(self) -> str:
        return self._rank

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, new_value: int) -> None:
        if not isinstance(new_value, int):
            raise TypeError(f"The new value must be of type int, not {type(new_value)}")
        elif new_value > self._value:
            raise ValueError("Attempted to set the new value of a card to be greater than its current value")
        elif new_value <= 0 and new_value != -10:
            raise ValueError("Attempted to set the new value of a card to be non-positive")
        else:
            self._value = new_value

    @property
    def emoji(self) -> str:
        return self._emoji


class Deck(object):
    """Represents a Blackjack card deck

    Attributes:
    ------
    cards Deque[:class:`Card`]
        - The cards in this deck
    """
    __slots__ = [
        "cards",
    ]

    def __init__(self) -> None:
        self.cards: Deque[Card] = deque([
            Card(suit=suit, rank=rank) for rank in _RANKS for suit in _SUITS
        ])

    def __len__(self) -> int:
        return len(self.cards)

    def shuffle(self, times: int = 1) -> None:
        for _ in range(times):
            random.shuffle(self.cards)

    def deal(self) -> Card:
        return self.cards.popleft()

    def starting_deal(self) -> List[Card]:
        self.shuffle()
        ret = [self.deal(), self.deal()]
        return ret


class Hand(object):
    """Represents a player or dealer's hand

    Attributes:
    ------
    cards List[:class:`Card`]
        - The cards in the player or dealer's hand

    value :class:`int`
        - The ace-adjusted value of the player or dealer's hand
    """
    __slots__ = [
        "_cards",
        "_is_dealer",
    ]

    def __init__(self, deck: Deck, is_dealer: bool = False) -> None:
        self._cards: List[Card] = deck.starting_deal()
        self._is_dealer = is_dealer

    def __str__(self) -> str:
        if not self._is_dealer:
            ret = "".join(card.emoji for card in self._cards)
        else:
            ret = playing_cards["_CardBack"] + "".join(card.emoji for card in self._cards[1:])
        return ret

    def __repr__(self) -> str:
        return f"<Hand value={self.value}, cards=[{', '.join(repr(card) for card in self._cards)}]>"

    def __eq__(self, other: "Hand") -> bool:
        return self.value == other.value

    def __ne__(self, other: "Hand") -> bool:
        return self.value != other.value

    def __lt__(self, other: "Hand") -> bool:
        return self.value < other.value

    def __le__(self, other: "Hand") -> bool:
        return self.value <= other.value

    def __gt__(self, other: "Hand") -> bool:
        return self.value > other.value

    def __ge__(self, other: "Hand") -> bool:
        return self.value >= other.value

    def __len__(self) -> int:
        return len(self._cards)

    @property
    def cards(self) -> List[Card]:
        return self._cards

    @property
    def value(self) -> int:
        ret = sum(card.value for card in self._cards)
        if ret > 21 and any(card.rank == "Ace" and card.value == 11 for card in self._cards):
            for card in self._cards:
                if card.rank == "Ace" and card.value == 11:
                    card.value -= 10
                ret = sum(card.value for card in self._cards)
                if ret <= 21:
                    break
        return ret

    @property
    def string_summation(self) -> str:
        if not self._is_dealer:
            ret = "+".join(str(card.value) for card in self._cards) + f"={self.value}"
        else:
            ret = "?+" + "+".join(str(card.value) for card in self._cards[1:]) + "=?"
        return f"`[{ret}]`"

    @property
    def full_string_summation(self) -> str:
        return f"`[{'+'.join(str(card.value) for card in self._cards)}={self.value}]`"

    @property
    def full_emoji(self) -> str:
        return "".join(card.emoji for card in self._cards)

    def place(self, card: Card) -> None:
        self._cards.append(card)


class _PlayerBase(object):
    __slots__ = [
        "hand",
    ]

    def __init__(self, deck: Deck) -> None:
        self.hand: Hand = Hand(deck)

    def __eq__(self, other: "_PlayerBase") -> bool:
        return self.value == other.value

    def __ne__(self, other: "_PlayerBase") -> bool:
        return self.value != other.value

    def __lt__(self, other: "_PlayerBase") -> bool:
        return self.value < other.value

    def __le__(self, other: "_PlayerBase") -> bool:
        return self.value <= other.value

    def __gt__(self, other: "_PlayerBase") -> bool:
        return self.value > other.value

    def __ge__(self, other: "_PlayerBase") -> bool:
        return self.value >= other.value

    def __len__(self) -> int:
        return len(self.hand)

    @property
    def value(self) -> int:
        return self.hand.value

    @property
    def is_bust(self) -> bool:
        return self.value > 21

    async def make_move(self) -> None:
        raise NotImplementedError("Please implement this method from the mixin")


class Player(_PlayerBase):
    __slots__ = [
        "hand",
        "bet",
        "_bot",
        "_ctx",
        "_first",
        "_standing",
        "_blackjack",
    ]

    def __init__(self, bot: AutoShardedBot, ctx: Context, bet: int, deck: Deck) -> None:
        self.hand: Hand = Hand(deck)
        self.bet = bet
        self._bot = bot
        self._ctx = ctx
        self._first = True
        self._standing = False
        self._blackjack = False

    @property
    def is_standing(self) -> bool:
        return self._standing

    @property
    def is_blackjack(self) -> bool:
        return self.value == 21

    @property
    def is_first(self) -> bool:
        return self._first

    def _hit(self, deck: Deck):
        self.hand.place(deck.deal())

    def _stand(self, *args):
        self._standing = True

    def _cancel(self, *args):
        raise BlackjackCanceled(self._ctx.author)

    async def _validate_reaction(self, message: discord.Message) -> str:
        while True:
            reaction, _ = await self._bot.wait_for(
                "reaction_add",
                check=lambda r, u: str(
                    r.emoji) in _EMOJIS and not u.bot and u.id == self._ctx.author.id and r.message == message,
                timeout=60
            )
            if str(reaction.emoji) == _EMOJIS[2] and not self._first:
                continue
            break
        return _MAP[str(reaction.emoji)]

    async def make_move(self, message: discord.Message, deck: Deck) -> None:
        if self._first:
            for reaction in _EMOJIS:
                await message.add_reaction(reaction)
        else:
            for reaction in _EMOJIS[:-1]:
                await message.add_reaction(reaction)
        getattr(self, await self._validate_reaction(message))(deck)
        self._first = False


class Dealer(_PlayerBase):
    def __init__(self, deck: Deck) -> None:
        self.hand: Hand = Hand(deck, is_dealer=True)

    async def make_move(self, deck: Deck) -> None:
        while self.value < 17:
            self.hand.place(deck.deal())


class BlackjackResult(NamedTuple):
    player_won: bool = False
    dealer_won: bool = False
    draw: bool = False
    blackjack: bool = False
    coro: Callable = None


class BlackjackGame(object):
    __slots__ = [
        "deck",
        "player",
        "dealer",
        "_bot",
        "_ctx",
        "_res",
        "_res_future",
    ]

    def __init__(self, bot: AutoShardedBot, ctx: Context, bet: int):
        self.deck = Deck()
        self.player = Player(bot, ctx, bet, self.deck)
        self.dealer = Dealer(self.deck)
        self._bot = bot
        self._ctx = ctx
        self._res: BlackjackResult = None
        self._res_future = self._bot.loop.create_future()

    @property
    def amount(self):
        if self._res.blackjack:
            return self.player.bet * 2
        return self.player.bet

    def _generate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Blackjack",
            description=f"React with {_EMOJIS[0]} to hit, {_EMOJIS[1]} to stand, or {_EMOJIS[2]} to cancel",
            color=discord.Color.blue(),
        ).set_author(
            name=f"{self._ctx.author.display_name} bet {self.player.bet} credit{'s' if self.player.bet != 1 else ''}",
            icon_url=self._ctx.author.avatar_url,
        ).add_field(
            name=f"Dealer {self.dealer.hand.string_summation}",
            value=self.dealer.hand,
            inline=True,
        ).add_field(
            name=f"{self._ctx.author.display_name} {self.player.hand.string_summation}",
            value=self.player.hand,
            inline=True,
        )
        if self.player.is_first:
            embed.set_footer(
                text="You may only cancel a game in the first turn",
            )
        return embed

    async def play(self) -> discord.Message:
        try:
            res = await self._start()
        except asyncio.TimeoutError:
            return await self._timed_out()
        except BlackjackCanceled:
            return await self._canceled()
        self._res = res
        self._res_future.set_result(True)
        return await self._ctx.send(
            embed=discord.Embed(
                title="Blackjack",
                description=await self._res.coro(),
                color=discord.Color.blue(),
            ).set_author(
                name="Results",
                icon_url=self._ctx.author.avatar_url,
            ).add_field(
                name=f"Dealer {self.dealer.hand.full_string_summation}",
                value=self.dealer.hand.full_emoji,
                inline=True,
            ).add_field(
                name=f"{self._ctx.author.display_name} {self.player.hand.string_summation}",
                value=self.player.hand,
                inline=True,
            )
        )

    async def _start(self) -> BlackjackResult:
        while not self.player.is_bust and not self.player.is_standing:
            message = await self._ctx.send(embed=self._generate_embed())
            await self.player.make_move(message, self.deck)
        await self.dealer.make_move(self.deck)
        if self.player.is_bust:
            return BlackjackResult(dealer_won=True, coro=self._lose)
        elif self.dealer.is_bust:
            return BlackjackResult(player_won=True, blackjack=self.player.is_blackjack, coro=self._win)
        elif self.player.value > self.dealer.value:
            return BlackjackResult(player_won=True, blackjack=self.player.is_blackjack, coro=self._win)
        elif self.player.value < self.dealer.value:
            return BlackjackResult(dealer_won=True, coro=self._lose)
        else:
            return BlackjackResult(draw=True, coro=self._draw)

    async def _draw(self) -> str:
        await self._res_future
        async with self._bot.db.acquire() as con:
            await con.execute(
                f"INSERT INTO blackjack(user_id, tie) VALUES ({self._ctx.author.id}, 1) ON CONFLICT "
                "(user_id) DO UPDATE SET tie=blackjack.tie+1 WHERE blackjack.user_id=EXCLUDED.user_id"
            )
        return f"{self._ctx.author.mention}, the blackjack game ended in a draw. No credits won or lost"

    async def _win(self) -> str:
        await self._res_future
        async with self._bot.db.acquire() as con:
            await con.execute(
                f"INSERT INTO blackjack(user_id, win) VALUES ({self._ctx.author.id}, 1) ON CONFLICT "
                "(user_id) DO UPDATE SET win=blackjack.win+1 WHERE blackjack.user_id=EXCLUDED.user_id"
            )
            await con.execute(
                f"INSERT INTO balance(user_id, amount) VALUES ({self._ctx.author.id}, {1000 + self.amount}) ON CONFLICT "
                f"(user_id) DO UPDATE SET amount=balance.amount+{self.amount} WHERE balance.user_id=EXCLUDED.user_id"
            )
            if self._res.blackjack:
                await con.execute(
                    f"INSERT INTO blackjack(user_id, blackjack) VALUES ({self._ctx.author.id}, 1) ON CONFLICT "
                    "(user_id) DO UPDATE SET blackjack=blackjack.blackjack+1 WHERE blackjack.user_id=EXCLUDED.user_id"
                )
        win_cond = "the dealer busted" if self.dealer.is_bust else "your card values are higher"
        if self._res.blackjack:
            win_cond += " and you got a blackjack"
        return f"{self._ctx.author.mention}, {win_cond}! You won {self.amount} credit{'s' if self.amount != 1 else ''}!"

    async def _lose(self) -> str:
        await self._res_future
        async with self._bot.db.acquire() as con:
            await con.execute(
                f"INSERT INTO blackjack(user_id, lose) VALUES ({self._ctx.author.id}, 1) ON CONFLICT "
                "(user_id) DO UPDATE SET lose=blackjack.lose+1 WHERE blackjack.user_id=EXCLUDED.user_id"
            )
            await con.execute(
                f"INSERT INTO balance(user_id, amount) VALUES ({self._ctx.author.id}, {1000 - self.amount}) ON CONFLICT "
                f"(user_id) DO UPDATE SET amount=balance.amount-{self.amount} WHERE balance.user_id=EXCLUDED.user_id"
            )
        lose_cond = "you busted" if self.player.is_bust else "the dealer's card values are higher"
        return f"{self._ctx.author.mention}, {lose_cond}! You lost {self.amount} credit{'s' if self.amount != 1 else ''}"

    async def _timed_out(self) -> discord.Message:
        return await self._ctx.send(embed=discord.Embed(
            title="Blackjack Game Timed Out",
            description=f"{self._ctx.author.mention}, you did not input a move within 60 seconds",
            color=discord.Color.dark_red(),
        ))

    async def _canceled(self) -> discord.Message:
        return await self._ctx.send(embed=discord.Embed(
            title="Blackjack Game Canceled",
            description=f"{self._ctx.author.mention}, the game was canceled",
            color=discord.Color.dark_red(),
        ))
