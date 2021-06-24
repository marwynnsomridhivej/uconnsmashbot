from discord.ext import commands
from discord.ext.commands import Context
from utils import GlobalCMDS
from utils.blackjackutils import *
from utils.customerrors import InvalidBetAmount


class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gcmds = GlobalCMDS(self.bot)
        self.bot.loop.create_task(self._init_table())

    async def _init_table(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.acquire() as con:
            await con.execute(
                "CREATE TABLE IF NOT EXISTS blackjack(user_id bigint PRIMARY KEY, win NUMERIC DEFAULT 0, "
                "lose NUMERIC DEFAULT 0, tie NUMERIC DEFAULT 0, blackjack NUMERIC DEFAULT 0)"
            )
        return

    async def _validate_bet(self, ctx: Context, bet: str) -> int:
        try:
            bet = int(bet)
            if not bet >= 1:
                raise ValueError
        except (TypeError, ValueError):
            raise InvalidBetAmount(ctx.author, bet, "is not an integer greater than or equal to 1")
        async with self.bot.db.acquire() as con:
            balance = await con.fetchval(
                f"SELECT amount FROM balance WHERE user_id={ctx.author.id}"
            )
        if balance is None:
            balance = 1000
        if bet > balance:
            raise InvalidBetAmount(ctx.author, bet, "exceeds your current balance")
        return bet

    @commands.command(aliases=['bj', 'Blackjack'],
                      desc="Blackjack in Discord!",
                      usage="blackjack (bet)",
                      note="If `(bet)` is not specified, it defaults to 1. "
                      "You may only bet up to your balance amount")
    async def blackjack(self, ctx, _bet: str = "1"):
        bet = await self._validate_bet(ctx, _bet)
        return await BlackjackGame(self.bot, ctx, bet).play()


def setup(bot):
    bot.add_cog(Blackjack(bot))
