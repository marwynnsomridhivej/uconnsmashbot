import discord
from discord.ext import commands


class CommandNotFound(commands.CommandError):
    def __init__(self, name: str):
        self.embed = discord.Embed(title="Command Not Found",
                                   description=f"`{name}` is not a valid command",
                                   color=discord.Color.dark_red())


class CommandHelpDirectlyCalled(CommandNotFound):
    def __init__(self, name):
        super().__init__(name)
        self.embed.title = "Use Parent Help"
        self.embed.description = ("The help for this command cannot be accessed directly. "
                                  "Please use the help command for the category this command is in")


class LoggingError(commands.CommandError):
    pass


class LoggingNotEnabled(LoggingError):
    def __init__(self):
        self.embed = discord.Embed(title="Logging Not Enabled",
                                   description="Logging is not enabled on this server",
                                   color=discord.Color.dark_red())


class LoggingBlacklisted(LoggingError):
    def __init__(self, guild: discord.Guild):
        self.embed = discord.Embed(title=f"{guild.name} Blacklisted",
                                   description="This server is blacklisted from using any logging functionality",
                                   color=discord.Color.dark_red())
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
                                   color=discord.Color.dark_red())


class LoggingCommandNameInvalid(LoggingError):
    def __init__(self, name: str):
        self.embed = discord.Embed(title="Invalid Command Name",
                                   description=f"No command is registered under the name `{name}`",
                                   color=discord.Color.dark_red())


class PostgreSQLError(commands.CommandError):
    pass


class NoPostgreSQL(PostgreSQLError):
    """Error raised when no valid db is specified
    """

    def __init__(self):
        self.embed = discord.Embed(title="No Valid DB Connection",
                                   description="No valid DB connection was passed as an argument",
                                   color=discord.Color.dark_red())


class NoBoundChannel(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="No Music Channel Bound",
                                   description="You must bind MarwynnBot's music commands to a channel",
                                   color=discord.Color.dark_red())


class NotBoundChannel(PostgreSQLError):
    def __init__(self, channel_id):
        self.embed = discord.Embed(title="Not Bound Channel",
                                   description=f"Execute music commands in <#{channel_id}>",
                                   color=discord.Color.dark_red())


class AutoroleInsertError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Autoroles Error",
                                   description="An error occured while setting this server's autoroles",
                                   color=discord.Color.dark_red())


class AutoroleDeleteError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Autoroles Error",
                                   description="An error occured while removing this server's autoroles. Please check "
                                   "if the role you provided is a valid autorole",
                                   color=discord.Color.dark_red())


class AutoroleSearchError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Autoroles Error",
                                   description="An error occured while retrieving this server's autoroles",
                                   color=discord.Color.dark_red())


class LockException(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Invalid Lock Operation",
                                   description="An error occurred due to an invalid lock oepration",
                                   color=discord.Color.dark_red())


class LockAllExcept(LockException):
    def __init__(self):
        super().__init__()
        self.embed.description = "You cannot lock all channels, otherwise, MarwynnBot won't be able to respond to any commands!"


class NoLocksExist(LockException):
    def __init__(self):
        super().__init__()
        self.embed.description = "No need to unlock anything! No channels are currently locked."


class ServerLinkException(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="An Error Occurred",
                                   description="An error occurred while processing ServerLink data",
                                   color=discord.Color.dark_red())


class ServerLinkChannelLimitExceeded(ServerLinkException):
    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.embed.title = "ServerLink Channel Limit Reached"
        self.embed.description = (f"{guild.name} can only register one ServerLink channel. To remove this restriction, "
                                  "upgrade to a MarwynnBot Premium Server subscription")


class ServerLinkNoRegisteredChannels(ServerLinkException):
    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.embed.title = "No Registered Channels"
        self.embed.description = f"{guild.name} does not have any registered ServerLink channels"


class ServerLinkInvalidGuild(ServerLinkException):
    def __init__(self, name: str):
        super().__init__()
        self.embed.title = "Invalid Server Name"
        self.embed.description = f"No server was found with the name `{name}`"


class StarboardException(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Starboard Error",
                                   description="An error occurred while performing an operation on the starboard",
                                   color=discord.Color.dark_red())


class NoStarboardSet(StarboardException):
    def __init__(self):
        super().__init__()
        self.embed.description = "There is no starboard currently set in this server"


class RedirectSetError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Redirect Set Error",
                                   description="An error occured while setting this server's redirects",
                                   color=discord.Color.dark_red())


class RedirectSearchError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Redirect Retrieve Error",
                                   description="An error occured while retrieving this server's redirects",
                                   color=discord.Color.dark_red())


class RedirectRemoveError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="Redirect Remove Error",
                                   description="An error occured while removing this server's redirects",
                                   color=discord.Color.dark_red())


class InvalidCommandSpecified(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="No Valid Commands Specified",
                                   description="An error occured while searching for valid commands",
                                   color=discord.Color.dark_red())


class ToDoError(PostgreSQLError):
    def __init__(self):
        self.embed = discord.Embed(title="An Error Occurred",
                                   description="An error occurred while performing operations on todo lists",
                                   color=discord.Color.dark_red())


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


class SilentActionError(commands.CommandError):
    pass


class TagError(commands.CommandError):
    def __init__(self, message=None, error=None, *args):
        super().__init__(message=message, *args)
        self.embed = discord.Embed(title="An Error Occurred",
                                   description=f"An error occurred while processing a tag command:\n```{error}\n```",
                                   color=discord.Color.dark_red())


class TagNotFound(TagError):
    """Error raised when user tries to invoke a tag that does not currently exist in the current guild

    Args:
        tag (str): name of the tag
    """

    def __init__(self, tag: str):
        self.embed = discord.Embed(title="Tag Not Found",
                                   description=f"The tag `{tag}` does not exist in this server",
                                   color=discord.Color.dark_red())


class TagAlreadyExists(TagError):
    """Error raised when user tries to create a tag that already exists

    Args:
        tag (str): name of the tag
    """

    def __init__(self, tag: str):
        self.embed = discord.Embed(title="Tag Already Exists",
                                   description=f"The tag `{tag}` already exists in this server",
                                   color=discord.Color.dark_red())


class NotTagOwner(TagError):
    """Error raised when the user tries to edit or delete a tag they do not own

    Args:
        tag (str): name of the tag
    """

    def __init__(self, tag: str):
        self.embed = discord.Embed(title="Illegal Tag Operation",
                                   description=f"You do not own the tag `{tag}`. Modifying or destructive actions can only be performed by the tag's owner",
                                   color=discord.Color.dark_red())


class UserNoTags(TagError):
    """Error raised when the user tries to list a tag but doesn't own any tags

    Args:
        member (discord.Member): the discord.Member instance
    """

    def __init__(self, member: discord.Member):
        self.embed = discord.Embed(title="No Tags Owned",
                                   description=f"{member.mention}, you do not own any tags",
                                   color=discord.Color.dark_red())


class NoSimilarTags(TagError):
    """Error raised when the user searches a tag but no similar or exact results were returned

    Args:
        query (str): the query that the user searched for
    """

    def __init__(self, query: str):
        self.embed = discord.Embed(title="No Results",
                                   description=f"There were no results for any tag named `{query}` in this server",
                                   color=discord.Color.dark_red())


class InvalidTagName(TagError):
    def __init__(self, tag: str):
        self.embed = discord.Embed(title="Invalid Tag Name",
                                   description=f"You cannot create a tag with the name `{tag}`",
                                   color=discord.Color.dark_red())


class TagLimitReached(TagError):
    def __init__(self, user: discord.User):
        self.embed = discord.Embed(title="Tag Limit Reached",
                                   description=f"{user.mention}, you must be a MarwynnBot Premium subscriber in order to "
                                   "create more than 100 tags",
                                   color=discord.Color.dark_red())


class CannotPaginate(commands.CommandError):
    """Error raised when the paginator cannot paginate

    Args:
        message (str): message that will be sent in traceback
    """

    def __init__(self, message):
        self.message = message


class PremiumError(commands.CommandError):
    pass


class NoPremiumGuilds(PremiumError):
    """Error raised when there are no guilds that are MarwynnBot Premium guilds
    """

    def __init__(self):
        self.embed = discord.Embed(title="No MarwynnBot Premium Members",
                                   description="There are no servers registered as MarwynnBot Premium servers \:(",
                                   color=discord.Color.dark_red())


class NoPremiumUsers(PremiumError):
    """Error raised when the current guild contains no MarwynnBot Premium users
    """

    def __init__(self):
        self.embed = discord.Embed(title="No MarwynnBot Premium Members",
                                   description="This server does not have any MarwynnBot Premium members \:(",
                                   color=discord.Color.dark_red())


class NoGlobalPremiumUsers(NoPremiumUsers):
    """Error raised when no user is MarwynnBot Premium
    """

    def __init__(self):
        super().__init__()
        self.embed.description = "There are currently MarwynnBot Premium users"


class NotPremiumGuild(PremiumError):
    """Error raised when the current guild is not a MarwynnBot Premium guild

    Args:
        guild (discord.Guild): the current guild
    """

    def __init__(self, guild: discord.Guild):
        self.embed = discord.Embed(title="Not MarwynnBot Premium",
                                   description=f"This guild, {guild.name}, must have a MarwynnBot Premium Server Subscription"
                                   " to use this command",
                                   color=discord.Color.dark_red())


class NotPremiumUser(PremiumError):
    """Error raised when the current user is not a MarwynnBot Premium user

    Args:
        user (discord.User): the current user
    """

    def __init__(self, user: discord.User):
        self.embed = discord.Embed(title="Not MarwynnBot Premium",
                                   description=f"{user.mention}, you must have a MarwynnBot Premium User Subscription to use this command",
                                   color=discord.Color.dark_red())


class NotPremiumUserOrGuild(PremiumError):
    """Error raised when the current user and guild are both not MarwynnBot Premium

    Args:
        user (discord.User): the current user
        guild (discord.Guild): the current guild
    """

    def __init__(self, user: discord.User, guild: discord.Guild):
        self.embed = discord.Embed(title="Not MarwynnBot Premium",
                                   description=f"{user.mention}, you or this server, {guild.name}, must have a "
                                   "MarwynnBot Premium Server Subscription to use this command",
                                   color=discord.Color.dark_red())


class UserPremiumException(PremiumError):
    """Error raised when there is an exception while performing a premium operation on a user

    Args:
        user (discord.User): the user the error occured with
    """

    def __init__(self, user: discord.User):
        self.embed = discord.Embed(title="Set Premium Error",
                                   description=f"An error occured when trying to operate on {user.display_name}",
                                   color=discord.Color.dark_red())


class UserAlreadyPremium(UserPremiumException):
    """Error raised when the user already has MarwynnBot Premium

    Args:
        user (discord.User): the user the error occured with
    """

    def __init__(self, user: discord.User):
        super().__init__(user)
        self.embed.description = f"{user.display_name} already has a MarwynnBot Premium subscription"


class GuildPremiumException(PremiumError):
    """Error raised when there is an exception while performing a premium operation on a guild

    Args:
        guild (discord.Guild): the guild the error occured with
    """

    def __init__(self, guild: discord.Guild):
        self.embed = discord.Embed(title="Set Premium Error",
                                   description=f"An error occured when trying to operate on {guild.name}",
                                   color=discord.Color.dark_red())


class GuildAlreadyPremium(GuildPremiumException):
    """Error raised when the guild already has MarwynnBot Premium

    Args:
        guild (discord.Guild): the guild the error occured with
    """

    def __init__(self, guild: discord.Guild):
        super().__init__(guild)
        self.embed.description = f"{guild.name} already has a MarwynnBot Premium subscription"


class GameStatsError(commands.CommandError):
    def __init__(self):
        self.embed = discord.Embed(title="GameStats Error",
                                   description="An error occurred while executing a gamestats query",
                                   color=discord.Color.dark_red())


class NoStatsAll(GameStatsError):
    def __init__(self, user: discord.User):
        super().__init__()
        self.embed.description = f"{user.mention}, you do not have any stats for any of MarwynnBot's games. Start playing to see your stats update!"


class NoStatsGame(GameStatsError):
    def __init__(self, user: discord.User, game: str):
        super().__init__()
        self.embed.description = f"{user.mention}, you do not have any stats for the game {game.title()}. Start playing to see your stats update!"


class BlacklistOperationError(commands.CommandError):
    def __init__(self):
        self.embed = discord.Embed(title="A Blacklist Operation Error Occurred",
                                   description="An error occurred while trying to operate on the blacklist. Please check "
                                   "to see if the user was already blacklisted or if any table constraints were violated",
                                   color=discord.Color.dark_red())


class MathError(commands.CommandError):
    def __init__(self):
        self.embed = discord.Embed(title="Math Error",
                                   description="An error occurred while trying to parse or solve an equation or expression input",
                                   color=discord.Color.dark_red())


class InvalidExpression(MathError):
    def __init__(self, eq: str):
        super().__init__()
        self.embed.title = "Invalid Expression"
        self.embed.description = f"```{eq}``` is not a valid expression or equation"
