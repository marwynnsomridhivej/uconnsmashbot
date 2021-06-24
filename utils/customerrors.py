import discord
from discord.ext.commands import Context, CommandError


_EC = discord.Color.dark_red()


class SilentButDeadly(CommandError):
    pass


class CommandNotFound(CommandError):
    def __init__(self, name: str):
        self.embed = discord.Embed(title="Command Not Found",
                                   description=f"`{name}` is not a valid command",
                                   color=_EC)


class CommandHelpDirectlyCalled(CommandNotFound):
    def __init__(self, name):
        super().__init__(name)
        self.embed.title = "Use Parent Help"
        self.embed.description = ("The help for this command cannot be accessed directly. "
                                  "Please use the help command for the category this command is in")


class EQBandError(CommandError):
    def __init__(self, ctx: Context, reason: str = "please specify a valid band value"):
        super().__init__()
        self.embed = discord.Embed(title="Invalid Band",
                                   description=f"{ctx.author.mention}, {reason}",
                                   color=_EC)


class EQGainError(CommandError):
    def __init__(self, ctx: Context, reason: str = "please specify a valid gain value"):
        super().__init__()
        self.embed = discord.Embed(title="Invalid Gain",
                                   description=f"{ctx.author.mention}, {reason}",
                                   color=_EC)


class EQGainMismatch(CommandError):
    def __init__(self, ctx: Context, expected: int, actual: int):
        super().__init__()
        self.embed = discord.Embed(title="Gain Mismatch",
                                   description=f"{ctx.author.mention}, the amount of gain values specified "
                                   f"does not match the amount of bands specified (expected: {expected}, received: {actual})",
                                   color=_EC)


class MassroleInvalidType(CommandError):
    def __init__(self, user_type: str):
        self.embed = discord.Embed(title="Invalid Type",
                                   description=f"The specified type `{user_type}` is not a valid type",
                                   color=_EC)


class MassroleInvalidOperation(CommandError):
    def __init__(self, op: str):
        self.embed = discord.Embed(title="Invalid Operation",
                                   description=f"The specified operation `{op}` is not a valid operation",
                                   color=_EC)


class OtherMBConnectedError(CommandError):
    def __init__(self):
        super().__init__()
        self.embed = discord.Embed(title="UconnSmashBot Music Already Connected",
                                   description="UconnSmashBot Music is already connected to this voice channel",
                                   color=_EC)


class LoggingError(CommandError):
    pass


class CannotMessageChannel(CommandError):
    def __init__(self, channel: discord.TextChannel):
        self.embed = discord.Embed(title="Insufficient Permissions",
                                   description=f"I cannot send messages in {channel.mention}",
                                   color=_EC)


class LoggingNotEnabled(LoggingError):
    def __init__(self):
        self.embed = discord.Embed(title="Logging Not Enabled",
                                   description="Logging is not enabled on this server",
                                   color=_EC)


class LoggingBlacklisted(LoggingError):
    def __init__(self, guild: discord.Guild):
        self.embed = discord.Embed(title=f"{guild.name} Blacklisted",
                                   description="This server is blacklisted from using any logging functionality",
                                   color=_EC)
        self.embed.set_footer(text="Please contact MS Arranges#3060 if you think this is a mistake")


class LoggingLevelInsufficient(LoggingError):
    pass


class LoggingChannelUnspecified(LoggingError):
    pass


class LoggingLevelInvalid(LoggingError):
    def __init__(self, level):
        self.embed = discord.Embed(title="Invalid Logging Level",
                                   description=f"The logging level `{level}` is not a valid logging level. Please enter "
                                   "either `basic`, `server`, or `hidef`",
                                   color=_EC)


class LoggingCommandNameInvalid(LoggingError):
    def __init__(self, name: str):
        self.embed = discord.Embed(title="Invalid Command Name",
                                   description=f"No command is registered under the name `{name}`",
                                   color=_EC)


class PostgreSQLError(CommandError):
    pass


class NoPostgreSQL(PostgreSQLError):
    """Error raised when no valid db is specified
    """

    def __init__(self):
        self.embed = discord.Embed(title="No Valid DB Connection",
                                   description="No valid DB connection was passed as an argument",
                                   color=_EC)


class NoBoundChannel(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="No Music Channel Bound",
                                   description="You must bind UconnSmashBot's music commands to a channel",
                                   color=_EC)


class NotBoundChannel(PostgreSQLError):
    def __init__(self, channel_id):
        self.embed = discord.Embed(title="Not Bound Channel",
                                   description=f"Execute music commands in <#{channel_id}>",
                                   color=_EC)


class AutoroleInsertError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Autoroles Error",
                                   description="An error occured while setting this server's autoroles",
                                   color=_EC)


class AutoroleDeleteError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Autoroles Error",
                                   description="An error occured while removing this server's autoroles. Please check "
                                   "if the role you provided is a valid autorole",
                                   color=_EC)


class AutoroleSearchError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Autoroles Error",
                                   description="An error occurred while retrieving this server's autoroles",
                                   color=_EC)


class LevelError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Leveling Error",
                                   description="An error occurred while retrieving this server's leveling configuration",
                                   color=_EC)


class LevelNoConfig(LevelError):
    def __init__(self):
        super().__init__()


class LevelNotEnabled(LevelError):
    def __init__(self):
        super().__init__()
        self.embed.title = "Leveling Not Enabled"
        self.embed.description = "Leveling is not enabled on this server. Enable it with `m!level enable`"


class LevelInvalidNotifyMode(LevelError):
    def __init__(self, mode: str):
        super().__init__()
        self.embed.title = "Invalid Notify Mode"
        self.embed.description = f"`{mode}` is not a valid mode"


class LevelInvalidRange(LevelError):
    def __init__(self, level: int):
        super().__init__()
        self.embed.title = "Invalid Level"
        self.embed.description = f"`{level}` is not between 1 and 100"


class LevelInvalidType(LevelError):
    def __init__(self, level_type: str):
        super().__init__()
        self.embed.title = "Invalid Type"
        self.embed.description = f"`{level_type}` is not a valid type"


class LevelRolesExists(LevelError):
    def __init__(self):
        super().__init__()
        self.embed.title = "Invalid Roles"
        self.embed.description = "One of the roles is already registered for another level"


class LockException(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Invalid Lock Operation",
                                   description="An error occurred due to an invalid lock oepration",
                                   color=_EC)


class LockAllExcept(LockException):
    def __init__(self):
        super().__init__()
        self.embed.description = "You cannot lock all channels, otherwise, UconnSmashBot won't be able to respond to any commands!"


class NoLocksExist(LockException):
    def __init__(self):
        super().__init__()
        self.embed.description = "No need to unlock anything! No channels are currently locked."


class ServerLinkException(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="An Error Occurred",
                                   description="An error occurred while processing ServerLink data",
                                   color=_EC)


class ServerLinkChannelLimitExceeded(ServerLinkException):
    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.embed.title = "ServerLink Channel Limit Reached"
        self.embed.description = (f"{guild.name} can only register one ServerLink channel. To remove this restriction, "
                                  "upgrade to a UconnSmashBot Premium Server subscription")


class ServerLinkNoRegisteredChannels(ServerLinkException):
    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.embed.title = "No Registered Channels"
        self.embed.description = f"{guild.name} does not have any registered ServerLink channels"


class ServerLinkNotRegisteredChannel(ServerLinkException):
    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.embed.title = "Channel Not Registered"
        self.embed.description = f"{channel.mention} is not a registered channel"


class ServerLinkNoAvailableChannels(ServerLinkException):
    def __init__(self, other_guild: discord.Guild):
        super().__init__()
        self.embed.title = "No Available Channels"
        self.embed.description = f"{other_guild.name} does not have any available ServerLink channels"


class ServerLinkInvalidGuild(ServerLinkException):
    def __init__(self, name: str):
        super().__init__()
        self.embed.title = "Invalid Server Name"
        self.embed.description = f"No server was found with the name `{name}`"


class ServerLinkNoRequestFound(ServerLinkException):
    def __init__(self, initiator_id: int):
        super().__init__()
        self.embed.title = "No Request Found"
        self.embed.description = f"No request was found for channel <#{initiator_id}>"


class ServerLinkChannelUnavailable(ServerLinkException):
    def __init__(self):
        super().__init__()
        self.embed.title = "Channel Unavailable"


class ServerLinkNoActiveSession(ServerLinkException):
    def __init__(self, ctx: Context):
        super().__init__()
        self.embed.title = "No Active ServerLink Session"
        self.embed.description = (f"There is currently no active ServerLink session associtaed with "
                                  f"{ctx.channel.mention}")


class ServerLinkNoSelf(ServerLinkException):
    def __init__(self):
        super().__init__()
        self.embed.title = "Invalid Server"
        self.embed.description = "You cannot send a request to the server you are currently in. Please " \
            "send a request to another server"


class ServerLinkBlocked(ServerLinkException):
    def __init__(self, other_guild: discord.Guild):
        super().__init__()
        self.embed.title = "Request Failed"
        self.embed.description = f"I could not send a ServerLink request to {other_guild.name}"


class ServerLinkSelfBlocked(ServerLinkException):
    def __init__(self, action):
        super().__init__()
        self.embed.title = "Invalid Server Name"
        self.embed.description = f"You cannot {action} your own server"


class StarboardException(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Starboard Error",
                                   description="An error occurred while performing an operation on the starboard",
                                   color=_EC)


class NoStarboardSet(StarboardException):
    def __init__(self):
        super().__init__()
        self.embed.description = "There is no starboard currently set in this server"


class RedirectSetError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Redirect Set Error",
                                   description="An error occured while setting this server's redirects",
                                   color=_EC)


class RedirectSearchError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Redirect Retrieve Error",
                                   description="An error occured while retrieving this server's redirects",
                                   color=_EC)


class RedirectRemoveError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Redirect Remove Error",
                                   description="An error occured while removing this server's redirects",
                                   color=_EC)


class InvalidCommandSpecified(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="No Valid Commands Specified",
                                   description="An error occured while searching for valid commands",
                                   color=_EC)


class ToDoError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="An Error Occurred",
                                   description="An error occurred while performing operations on todo lists",
                                   color=_EC)


class ToDoSetError(ToDoError):
    def __init__(self):
        super().__init__()
        self.embed.title = "Todo Set Error"
        self.embed.description = "An error occurred while setting the todo list"


class ToDoUpdateError(ToDoError):
    def __init__(self):
        super().__init__()
        self.embed.title = "Todo Update Error"
        self.embed.description = "An error occurred while updating the todo list"


class ToDoSearchError(ToDoError):
    def __init__(self):
        super().__init__()
        self.embed.title = "Todo Retrieve Error"
        self.embed.description = "An error occurred while retrieving the todo list"


class ToDoRemoveError(ToDoError):
    def __init__(self):
        super().__init__()
        self.embed.title = "Todo Remove Error"
        self.embed.description = "An error occurred while removing items from the todo list"


class ToDoEmptyError(ToDoError):
    def __init__(self, user: discord.User, status: str = "set"):
        super().__init__()
        self.embed.title = "No Todos Set"
        self.embed.description = f"{user.mention}, you currently do not have any todos that are {status}"


class ToDoCheckError(ToDoError):
    def __init__(self):
        super().__init__()
        self.embed.title = "Todo Verification Error"
        self.embed.description = "The IDs that were passed could not be verified, or were invalid"


class SilentActionError(CommandError):
    def __init__(self, action: str, user: discord.User):
        super().__init__()
        self.embed = discord.Embed(title=f"Unable to {action.title()}",
                                   description=f"You can't perform any actions on {user.mention}",
                                   color=_EC)


class TagError(CommandError):
    def __init__(self, message=None, error=None, *args):
        super().__init__(message=message, *args)
        self.embed = discord.Embed(title="An Error Occurred",
                                   description=f"An error occurred while processing a tag command:\n```{error}\n```",
                                   color=_EC)


class TagNotFound(TagError):
    """Error raised when user tries to invoke a tag that does not currently exist in the current guild

    Args:
        tag (str): name of the tag
    """

    def __init__(self, tag: str):
        self.embed = discord.Embed(title="Tag Not Found",
                                   description=f"The tag `{tag}` does not exist in this server",
                                   color=_EC)


class TagAlreadyExists(TagError):
    """Error raised when user tries to create a tag that already exists

    Args:
        tag (str): name of the tag
    """

    def __init__(self, tag: str):
        self.embed = discord.Embed(title="Tag Already Exists",
                                   description=f"The tag `{tag}` already exists in this server",
                                   color=_EC)


class NotTagOwner(TagError):
    """Error raised when the user tries to edit or delete a tag they do not own

    Args:
        tag (str): name of the tag
    """

    def __init__(self, tag: str):
        self.embed = discord.Embed(title="Illegal Tag Operation",
                                   description=f"You do not own the tag `{tag}`. Modifying or destructive actions can only be performed by the tag's owner",
                                   color=_EC)


class UserNoTags(TagError):
    """Error raised when the user tries to list a tag but doesn't own any tags

    Args:
        member (discord.Member): the discord.Member instance
    """

    def __init__(self, member: discord.Member):
        self.embed = discord.Embed(title="No Tags Owned",
                                   description=f"{member.mention}, you do not own any tags",
                                   color=_EC)


class NoSimilarTags(TagError):
    """Error raised when the user searches a tag but no similar or exact results were returned

    Args:
        query (str): the query that the user searched for
    """

    def __init__(self, query: str):
        self.embed = discord.Embed(title="No Results",
                                   description=f"There were no results for any tag named `{query}` in this server",
                                   color=_EC)


class InvalidTagName(TagError):
    def __init__(self, tag: str):
        self.embed = discord.Embed(title="Invalid Tag Name",
                                   description=f"You cannot create a tag with the name `{tag}`",
                                   color=_EC)


class InvalidTagLength(TagError):
    def __init__(self):
        self.embed = discord.Embed(title="Tag Too Long",
                                   description="Please keep tag names no longer "
                                   "than 128 characters (including whitespace)",
                                   color=_EC)


class TagLimitReached(TagError):
    def __init__(self, user: discord.User):
        self.embed = discord.Embed(title="Tag Limit Reached",
                                   description=f"{user.mention}, you must be a UconnSmashBot Premium subscriber in order to "
                                   "create more than 100 tags",
                                   color=_EC)


class CannotPaginate(CommandError):
    """Error raised when the paginator cannot paginate

    Args:
        message (str): message that will be sent in traceback
    """

    def __init__(self, message):
        self.message = message


class PremiumError(CommandError):
    pass


class NoPremiumGuilds(PremiumError):
    """Error raised when there are no guilds that are UconnSmashBot Premium guilds
    """

    def __init__(self):
        self.embed = discord.Embed(title="No UconnSmashBot Premium Members",
                                   description="There are no servers registered as UconnSmashBot Premium servers \:(",
                                   color=_EC)


class NoPremiumUsers(PremiumError):
    """Error raised when the current guild contains no UconnSmashBot Premium users
    """

    def __init__(self):
        self.embed = discord.Embed(title="No UconnSmashBot Premium Members",
                                   description="This server does not have any UconnSmashBot Premium members \:(",
                                   color=_EC)


class NoGlobalPremiumUsers(NoPremiumUsers):
    """Error raised when no user is UconnSmashBot Premium
    """

    def __init__(self):
        super().__init__()
        self.embed.description = "There are currently UconnSmashBot Premium users"


class NotPremiumGuild(PremiumError):
    """Error raised when the current guild is not a UconnSmashBot Premium guild

    Args:
        guild (discord.Guild): the current guild
    """

    def __init__(self, guild: discord.Guild):
        self.embed = discord.Embed(title="Not UconnSmashBot Premium",
                                   description=f"This guild, {guild.name}, must have a UconnSmashBot Premium Server Subscription"
                                   " to use this command",
                                   color=_EC)


class NotPremiumUser(PremiumError):
    """Error raised when the current user is not a UconnSmashBot Premium user

    Args:
        user (discord.User): the current user
    """

    def __init__(self, user: discord.User):
        self.embed = discord.Embed(title="Not UconnSmashBot Premium",
                                   description=f"{user.mention}, you must have a UconnSmashBot Premium User Subscription to use this command",
                                   color=_EC)


class NotPremiumUserOrGuild(PremiumError):
    """Error raised when the current user and guild are both not UconnSmashBot Premium

    Args:
        user (discord.User): the current user
        guild (discord.Guild): the current guild
    """

    def __init__(self, user: discord.User, guild: discord.Guild):
        self.embed = discord.Embed(title="Not UconnSmashBot Premium",
                                   description=f"{user.mention}, you or this server, {guild.name}, must have a "
                                   "UconnSmashBot Premium Server Subscription to use this command",
                                   color=_EC)


class UserPremiumException(PremiumError):
    """Error raised when there is an exception while performing a premium operation on a user

    Args:
        user (discord.User): the user the error occured with
    """

    def __init__(self, user: discord.User):
        self.embed = discord.Embed(title="Set Premium Error",
                                   description=f"An error occured when trying to operate on {user.display_name}",
                                   color=_EC)


class UserAlreadyPremium(UserPremiumException):
    """Error raised when the user already has UconnSmashBot Premium

    Args:
        user (discord.User): the user the error occured with
    """

    def __init__(self, user: discord.User):
        super().__init__(user)
        self.embed.description = f"{user.display_name} already has a UconnSmashBot Premium subscription"


class GuildPremiumException(PremiumError):
    """Error raised when there is an exception while performing a premium operation on a guild

    Args:
        guild (discord.Guild): the guild the error occured with
    """

    def __init__(self, guild: discord.Guild):
        self.embed = discord.Embed(title="Set Premium Error",
                                   description=f"An error occured when trying to operate on {guild.name}",
                                   color=_EC)


class GuildAlreadyPremium(GuildPremiumException):
    """Error raised when the guild already has UconnSmashBot Premium

    Args:
        guild (discord.Guild): the guild the error occured with
    """

    def __init__(self, guild: discord.Guild):
        super().__init__(guild)
        self.embed.description = f"{guild.name} already has a UconnSmashBot Premium subscription"


class GameStatsError(CommandError):
    def __init__(self):
        self.embed = discord.Embed(title="GameStats Error",
                                   description="An error occurred while executing a gamestats query",
                                   color=_EC)


class NoStatsAll(GameStatsError):
    def __init__(self, user: discord.User):
        super().__init__()
        self.embed.description = f"{user.mention}, you do not have any stats for any of UconnSmashBot's games. Start playing to see your stats update!"


class NoStatsGame(GameStatsError):
    def __init__(self, user: discord.User, game: str):
        super().__init__()
        self.embed.description = f"{user.mention}, you do not have any stats for the game {game.title()}. Start playing to see your stats update!"


class BlacklistOperationError(CommandError):
    def __init__(self):
        self.embed = discord.Embed(title="A Blacklist Operation Error Occurred",
                                   description="An error occurred while trying to operate on the blacklist. Please check "
                                   "to see if the user was already blacklisted or if any table constraints were violated",
                                   color=_EC)


class MathError(CommandError):
    def __init__(self):
        self.embed = discord.Embed(title="Math Error",
                                   description="An error occurred while trying to parse or solve an equation or expression input",
                                   color=_EC)


class InvalidExpression(MathError):
    def __init__(self, eq: str):
        super().__init__()
        self.embed.title = "Invalid Expression"
        self.embed.description = f"```{eq}``` is not a valid expression or equation"


class UnoCannotDM(CommandError):
    def __init__(self, member: discord.Member):
        self.embed = discord.Embed(title="Cannot Initiate DM",
                                   description=f"I don't have the permissions to DM {member.mention}. The "
                                   "current Uno game has been canceled",
                                   color=_EC)


class InvalidBetAmount(CommandError):
    def __init__(self, member: discord.Member, amount: str, reason: str):
        self.embed = discord.Embed(
            title="Invalid Bet",
            description=f"{member.mention}, `{amount}` is not a valid bet amount, as it {reason}",
            color=_EC,
        )


class BlackjackCanceled(CommandError):
    def __init__(self, member: discord.Member):
        self.embed = discord.Embed(
            title="Blackjack Game Canceled",
            description=f"{member.mention}, the blackjack game has been canceled",
            color=_EC,
        )
