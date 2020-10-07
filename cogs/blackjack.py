import asyncio
import random
import discord
from discord.ext import commands
from utils import cards, globalcommands

gcmds = globalcommands.GlobalCMDS()
suits = {'Hearts', 'Diamonds', 'Spades', 'Clubs'}
ranks = {'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Jack', 'Queen', 'King', 'Ace'}
values = {'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5, 'Six': 6, 'Seven': 7, 'Eight': 8, 'Nine': 9, 'Ten': 10,
          'Jack': 10, 'Queen': 10, 'King': 10, 'Ace': 11}


class Card:

    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    def __str__(self):
        return self.rank + ' of ' + self.suit


class Deck:

    def __init__(self):
        self.deck = [Card(suit, rank) for rank in ranks for suit in suits]

    def __str__(self):
        return "The deck has:\n" + "\n".join([card.__str__() for card in self.deck])

    def shuffle(self):
        random.shuffle(self.deck)

    def deal(self):
        return self.deck.pop()


class Hand:

    def __init__(self):
        self.cards = []
        self.value = 0
        self.aces = 0
        self.acecount = 0
        self.iter = 0

    def add_card(self, card):
        self.cards.append(card)
        self.value += values[card.rank]
        if card.rank == 'Ace':
            self.aces += 1

    def adjust_for_ace(self):
        while self.value > 21 and self.aces:
            self.value -= 10
            self.aces -= 1

    def list_hand(self, isDealer=False, gameEnd=False):
        string = ""
        if not isDealer:
            for card in self.cards:
                if self.value > 21:
                    if card.rank == "Ace" and (self.aces >= 1 or self.acecount >= 1):
                        string += "1+"
                        if self.aces >= 1:
                            self.adjust_for_ace()
                            self.acecount += 1
                    elif gameEnd:
                        if card.rank == "Ace" and self.acecount >= 1:
                            string += "1+"
                            self.acecount -= 1
                        else:
                            string += f"{values[card.rank]}+"
                    else:
                        string += f"{values[card.rank]}+"
                else:
                    if card.rank == "Ace" and self.acecount >= 1:
                        string += "1+"
                    else:
                        string += f"{values[card.rank]}+"
        else:
            cardlist = []
            for card in self.cards:
                cardlist.append(card.rank)
            cardlist.pop(0)
            for card in cardlist:
                if self.value > 21:
                    if card == 'Ace' and (self.aces >= 1 or self.acecount >= 1):
                        string += "1+"
                        if self.aces >= 1:
                            self.adjust_for_ace()
                            self.acecount += 1
                    else:
                        string += f"{values[card]}"
                else:
                    if card == "Ace" and self.acecount >= 1:
                        string += "1+"
                    else:
                        string += f"{values[card]}+"
        self.iter += 1
        return string

    def added(self):
        return self.value


class Chips:

    def __init__(self, balance, bet, ctx, bot):
        self.total = balance
        self.bet = bet
        self.ctx = ctx
        self.bot = bot

    def win_bet(self):
        self.total += self.bet
        op = (f"UPDATE balance SET amount = amount + {self.bet} WHERE user_id = {self.ctx.author.id}")
        self.bot.loop.create_task(gcmds.balance_db(op))

    def lose_bet(self):
        self.total -= self.bet
        op = (f"UPDATE balance SET amount = amount - {self.bet} WHERE user_id = {self.ctx.author.id}")
        self.bot.loop.create_task(gcmds.balance_db(op))


def take_bet(chips):
    while True:
        try:
            bet = chips.bet
        except ValueError:
            print("NonInt passed into bet")
            break
        else:
            if bet > chips.total:
                return False
            else:
                return True


def hit(deck, hand):
    hand.add_card(deck.deal())


def hit_or_stand(deck, hand, choice):
    if choice == 'hit':
        hit(deck, hand)
        return True
    else:
        return False


async def win(ctx: commands.Context, bot: commands.AutoShardedBot, blackjack=False):
    async with bot.db.acquire() as con:
        result = await con.fetch(f"SELECT * FROM blackjack WHERE user_id={ctx.author.id}")
        if not result:
            if blackjack:
                await con.execute(f"INSERT INTO blackjack(user_id, win, blackjack) VALUES ({ctx.author.id}, 1, 1)")
            else:
                await con.execute(f"INSERT INTO blackjack(user_id, win) VALUES ({ctx.author.id}, 1)")
        else:
            if blackjack:
                await con.execute(f"UPDATE blackjack SET win = win + 1, blackjack = blackjack + 1 WHERE user_id = {ctx.author.id}")
            else:
                await con.execute(f"UPDATE blackjack SET win = win + 1 WHERE user_id = {ctx.author.id}")
    return


async def lose(ctx: commands.Context, bot: commands.AutoShardedBot):
    async with bot.db.acquire() as con:
        result = await con.fetch(f"SELECT * FROM blackjack WHERE user_id={ctx.author.id}")
        if not result:
            await con.execute(f"INSERT INTO blackjack(user_id, lose) VALUES ({ctx.author.id}, 1)")
        else:
            await con.execute(f"UPDATE blackjack SET lose = lose + 1 WHERE user_id = {ctx.author.id}")
    return


async def player_busts(player, dealer, chips: Chips, ctx):
    chips.lose_bet()
    await lose(ctx, chips.bot)
    await gcmds.ratio(ctx.author, 'blackjack')


async def player_wins(player, dealer, chips, ctx):
    chips.win_bet()
    await win(ctx, chips.bot)
    await gcmds.ratio(ctx.author, 'blackjack')


async def dealer_busts(player, dealer, chips, ctx):
    chips.win_bet()
    await win(ctx, chips.bot)
    await gcmds.ratio(ctx.author, 'blackjack')


async def dealer_wins(player, dealer, chips, ctx):
    chips.lose_bet()
    await lose(ctx, chips.bot)
    await gcmds.ratio(ctx.author, 'blackjack')


async def _blackjack(player, dealer, chips, ctx):
    chips.win_bet()
    chips.win_bet()
    await win(ctx, chips.bot)
    await gcmds.ratio(ctx.author, 'blackjack')


def show_dealer(dealer, won):
    if won:
        return "".join(emoji(card) for card in dealer.cards)
    else:
        return "<:cardback:738063418832978070>" + \
            "".join(emoji(dealer.cards[index + 1]) for index in range(len(dealer.cards) - 1))


def show_player(player):
    return "".join(emoji(card) for card in player.cards)


def emoji(card):
    return cards.playing_cards[card.rank][card.suit]


class Blackjack(commands.Cog):

    def __init__(self, bot):
        global gcmds
        self.bot = bot
        gcmds = globalcommands.GlobalCMDS(self.bot)
        self.bot.loop.create_task(self.init_blacklist())

    async def init_blacklist(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS blackjack(user_id bigint PRIMARY KEY, win NUMERIC DEFAULT 0, "
                              "lose NUMERIC DEFAULT 0, tie NUMERIC DEFAULT 0, blackjack NUMERIC DEFAULT 0, ratio NUMERIC DEFAULT 0)")

    @commands.command(aliases=['bj', 'Blackjack'],
                      desc="Blackjack in Discord!",
                      usage="blackjack (bet)",
                      note="If `(bet)` is not specified, it defaults to 1. "
                      "You may only bet up to your balance amount")
    async def blackjack(self, ctx, bet=1):
        won = False
        bet = bet
        deck = Deck()
        deck.shuffle()
        if bet != 1:
            spell = 'credits'
        else:
            spell = 'credit'

        player_hand = Hand()
        player_hand.add_card((deck.deal()))
        player_hand.add_card((deck.deal()))
        player_value = player_hand.list_hand()
        pv_int = player_hand.added()

        dealer_hand = Hand()
        dealer_hand.add_card((deck.deal()))
        dealer_hand.add_card((deck.deal()))
        dealer_value = dealer_hand.list_hand(True)

        balance = await gcmds.get_balance(ctx.author)
        if not balance:
            await gcmds.balance_db(f"INSERT INTO balance(user_id, amount) VALUES ({ctx.author.id}, 1000)")
            balance = 1000
            initEmbed = discord.Embed(title="Initialised Credit Balance",
                                      description=f"{ctx.author.mention}, you have been credited `1000` credits "
                                      f"to start!\n\nCheck your current"
                                      f" balance using `{await gcmds.prefix(ctx)}balance`",
                                      color=discord.Color.blue())
            initEmbed.set_thumbnail(url="https://cdn.discordapp.com/attachments/734962101432615006"
                                        "/738390147514499163/chips.png")
            await ctx.channel.send(embed=initEmbed)

        player_chips = Chips(balance, bet, ctx, self.bot)
        if not take_bet(player_chips):
            insuf = discord.Embed(title="Insufficient Credit Balance",
                                  description=f"{ctx.author.mention}, you have `{balance}` credits"
                                              f"\nYour bet of `{bet}` credits exceeds your current balance",
                                  color=discord.Color.dark_red())
            await ctx.channel.send(embed=insuf)
            return

        hitEmoji = '✅'
        standEmoji = '❌'
        cancelEmoji = '🛑'

        bjEmbed = discord.Embed(title="Blackjack",
                                description=f"To hit, react to {hitEmoji}, to stand, react to {standEmoji}, to cancel "
                                            f"the game, react to {cancelEmoji} (only before first turn)",
                                color=discord.Color.blue())
        bjEmbed.set_author(name=f"{ctx.author.name} bet {bet} {spell} to play Blackjack",
                           icon_url=ctx.author.avatar_url)
        bjEmbed.add_field(name=f"Dealer `[?+{dealer_value[:-1]}=?]`",
                          value=show_dealer(dealer_hand, won))
        bjEmbed.add_field(name=f"{ctx.author.name} `[{player_value[:-1]}={pv_int}]`",
                          value=show_player(player_hand))
        message = await ctx.channel.send(embed=bjEmbed)
        await message.add_reaction(hitEmoji)
        await message.add_reaction(standEmoji)
        await message.add_reaction(cancelEmoji)

        def check(reaction, user):
            if ctx.author == user and str(reaction.emoji) == '✅':
                return True
            elif ctx.author == user and str(reaction.emoji) == '❌':
                return True
            elif ctx.author == user and str(reaction.emoji) == '🛑':
                return True
            else:
                return False

        while True:
            await message.add_reaction(hitEmoji)
            await message.add_reaction(standEmoji)
            try:
                choice = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                for item in choice:
                    if str(item) == '✅':
                        choice = 'hit'
                        break
                    if str(item) == '❌':
                        choice = 'stand'
                        break
                    if str(item) == '🛑':
                        await message.clear_reactions()
                        bjEmbed = discord.Embed(title="Blackjack Game Canceled",
                                                description=f"{ctx.author.mention}, your game was cancelled",
                                                color=discord.Color.dark_red())
                        await message.edit(embed=bjEmbed)
                        return
                stopiter = hit_or_stand(deck, player_hand, choice)

                player_value = player_hand.list_hand()
                pv_int = player_hand.added()
                dealer_value = dealer_hand.list_hand(True)

                await message.clear_reactions()
                bjEmbed = discord.Embed(title="Blackjack",
                                        description=f"To hit, react to {hitEmoji}, to stand, react to {standEmoji}, "
                                                    f"to cancel the game, react to {cancelEmoji}",
                                        color=discord.Color.blue())
                bjEmbed.set_author(name=f"{ctx.author.name} bet {bet} {spell} to play Blackjack",
                                   icon_url=ctx.author.avatar_url)
                bjEmbed.add_field(name=f"Dealer `[?+{dealer_value[:-1]}=?]`",
                                  value=show_dealer(dealer_hand, won))
                bjEmbed.add_field(name=f"{ctx.author.name} `[{player_value[:-1]}={pv_int}]`",
                                  value=show_player(player_hand))
                await message.edit(embed=bjEmbed)
            except asyncio.TimeoutError:
                if won:
                    return
                else:
                    await message.clear_reactions()
                    canceled = discord.Embed(title="Game Timeout",
                                             description=f"{ctx.author.mention}, game canceled due to inactivity, "
                                                         f"create a new game",
                                             color=discord.Color.dark_red())
                    canceled.set_thumbnail(url='https://cdn.discordapp.com/attachments/734962101432615006'
                                               '/738083697726849034/nocap.jpg')
                    canceled.set_footer(text=f"{ctx.author.name} did not provide a valid reaction within 60 seconds")
                    await message.edit(embed=canceled)
                    return

            if player_hand.value > 21:
                await player_busts(player_hand, dealer_hand, player_chips, ctx)
                won = True

                player_value = player_hand.list_hand(gameEnd=won)
                pv_int = player_hand.added()
                dealer_value = dealer_hand.list_hand(gameEnd=won)
                dr_int = dealer_hand.added()

                await message.clear_reactions()
                bjEmbedEdit = discord.Embed(title="Blackjack",
                                            description=f"{ctx.author.mention}, you busted! Lost **{bet}** {spell}",
                                            color=discord.Color.blue())
                bjEmbedEdit.set_author(name="Results",
                                       icon_url=ctx.author.avatar_url)
                bjEmbedEdit.add_field(name=f"Dealer `[{dealer_value[:-1]}={dr_int}]`",
                                      value=show_dealer(dealer_hand, won))
                bjEmbedEdit.add_field(name=f"{ctx.author.name} `[{player_value[:-1]}={pv_int}]`",
                                      value=show_player(player_hand))
                await message.edit(embed=bjEmbedEdit)

                return

            if player_hand.value <= 21 and not stopiter:
                while dealer_hand.value < 17:
                    hit(deck, dealer_hand)

                player_value = player_hand.list_hand(gameEnd=won)
                pv_int = player_hand.added()
                dealer_value = dealer_hand.list_hand(gameEnd=won)
                dr_int = dealer_hand.added()

                won = True

                large_bet_win = False

                if (player_hand.iter - 3) == 0 and player_hand.value == 21:
                    await _blackjack(player_hand, dealer_hand, player_chips, ctx)
                    description = f"Blackjack! {ctx.author.mention} wins **{bet * 2}** credits"
                    if bet >= 1000:
                        large_bet_win = True
                elif dealer_hand.value > 21:
                    await dealer_busts(player_hand, dealer_hand, player_chips, ctx)
                    description = f"Dealer busts! {ctx.author.mention} wins **{bet}** {spell}"
                    if bet >= 1000:
                        large_bet_win = True
                elif dealer_hand.value > player_hand.value:
                    await dealer_wins(player_hand, dealer_hand, player_chips, ctx)
                    description = f"Dealer wins! {ctx.author.mention} lost **{bet}** {spell}"
                elif player_hand.value > dealer_hand.value:
                    await player_wins(player_hand, dealer_hand, player_chips, ctx)
                    description = f"{ctx.author.mention} wins **{bet}** {spell}"
                    if bet >= 1000:
                        large_bet_win = True
                else:
                    async with self.bot.db.acquire() as con:
                        _ = await con.fetch(f"SELECT * FROM blackjack WHERE user_id = {ctx.author.id}")
                        if not _:
                            await con.execute(f"INSERT INTO blackjack(user_id, tie) VALUES ({ctx.author.id}, 1)")
                        else:
                            await con.execute(f"UPDATE blackjack SET tie = tie + 1 WHERE user_id = {ctx.author.id}")
                    description = "Its a tie! No credits lost or gained"

                await message.clear_reactions()
                bjEmbedEdit = discord.Embed(title="Blackjack",
                                            description=description,
                                            color=discord.Color.blue())
                bjEmbedEdit.set_author(name="Results",
                                       icon_url=ctx.author.avatar_url)
                bjEmbedEdit.add_field(name=f"Dealer `[{dealer_value[:-1]}={dr_int}]`",
                                      value=show_dealer(dealer_hand, won))
                bjEmbedEdit.add_field(name=f"{ctx.author.name} `[{player_value[:-1]}={pv_int}]`",
                                      value=show_player(player_hand))
                await message.edit(embed=bjEmbedEdit)

                if ((player_hand.iter - 3) == 0 and player_hand.value == 21) or large_bet_win:
                    await message.add_reaction("📌")
                    await message.add_reaction("🛑")

                    bjEmbedEdit.set_footer(text="To pin, react with 📌, otherwise, react with 🛑")
                    await message.edit(embed=bjEmbedEdit)

                    def check_pin(reaction, user):
                        if ctx.author == user and str(reaction.emoji) == '📌':
                            return True
                        elif ctx.author == user and str(reaction.emoji) == '🛑':
                            return True
                        else:
                            return False

                    try:
                        pin_choice = await self.bot.wait_for('reaction_add', timeout=20.0,
                                                             check=check_pin)
                    except asyncio.TimeoutError:
                        await message.clear_reactions()
                        bjEmbedEdit.set_footer(text="Not pinned 🛑")
                        await message.edit(embed=bjEmbedEdit)
                        return
                    else:
                        for item in pin_choice:
                            if str(item) == '📌':
                                await message.clear_reactions()
                                await message.pin()
                                bjEmbedEdit.set_footer(text="Pinned 📌")
                                break
                            if str(item) == '🛑':
                                await message.clear_reactions()
                                bjEmbedEdit.set_footer(text="Not pinned 🛑")
                                return

                        await message.edit(embed=bjEmbedEdit)

                return


def setup(bot):
    bot.add_cog(Blackjack(bot))
