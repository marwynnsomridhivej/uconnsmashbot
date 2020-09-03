# UCONN Smash Discord Bot
This is a bot created by [@marwynnsomridhivej](https://github.com/marwynnsomridhivej) to be used **ONLY** in the UCONN Smash Discord server. This bot is not authorised for public use. If you are confused as to what this means, kindly check the [LICENSE](https://github.com/marwynnsomridhivej/uconnsmashbot/blob/master/LICENSE) file.

## Prefix
The bot's global prefix is `?` and is not customisable, however, this may change at the E-Board's discretion. The bot currently does not support custom prefixes, but that can change at a moment's notice, as I can implement that code whenever it is needed.

## Features
The bot has some really neat features. Here is a complete list of them:

|Command|Details|
|:---:|:---:|
|`list is WIP`|`will receive update once commands are finalised`|

## Security Concerns and Privacy
As with everything, I understand that you may have some security concerns regarding this bot, as it is not verified by 
Discord. The reason I have made this source code public is so that anybody who has concerns can evaluate the source 
code for themselves and reach the conclusion that this bot is indeed safe to use.

I respect your privacy and take it very seriously. To be entirely transparent, here is everything that the bot collects and stores in its databases:

> - Server ID*
> - Channel IDs*
> - Role IDs*
> - User IDs*
> - Playlist URLs (YouTube URLs)
> - Message Content**
> - Timestamps***

Just to be clear, this bot does scan every message that is sent in the server it is in. This scan is conducted **ONLY TO CHECK IF A DISCORD TOKEN IS PRESENT IN THE MESSAGE**. Once the scan is complete, in most cases, the bot does not store the message**

>\**Storing this data does not pose a security risk. You can't really do anything with server, channel, role, and user IDs that would be harmful given that you are not a server member. Knowing the server ID, channel ID, role ID, and user ID is just as useful as knowing 18 random numbers. The bot stores this data when it explicitly requests for it. Examples include when the bot asks for a channel tag or ID during the reaction roles setup, recording which user was muted by which moderator, and what role should be fetched when giving roles through reaction role upon a specific reaction*

>\*\**I am aware that potentially sensitive information can be sent in messages. Therefore, the bot only stores message content that it explicitly requests for. For example, the bot does not log ordinary chat messages or keeps track of them in any way. However, something like the bot prompting you for which channel you would like this reminder to fire in and what the content of the reminder should be will be stored, since it is used to determine what the reminder embed's content will be. The bot will **NEVER** store any information that it has not explicitly asked for. The bot stores message content encoded in a non-human-readable format for extra security, although I must admit it is not as secure as something like end to end encryption*

>\*\*\**Timestamps are an exception to the above rule. The bot automatically generates UNIX timestamps that are stored only when needed, for example, in order to facilitate accurate reminder sending or calculating when a user's mute should expire. Timestamps are calculated, but not stored, in commands such as help, where a timestamp of when the command was executed appears in the footer. Timestamps provide no indication of anything other than the time of execution*

## Contact
**Discord:** MS Arranges#3060