import enum


class LogLevel(enum.IntEnum):
    NULL = 0
    BASIC = 1
    GUILD = 2
    HIDEF = 3

    def __str__(self):
        return self.name.lower() if self.name != "GUILD" else "server"


class ConfirmReactions(enum.Enum):
    YES = '✅'
    NO = '🛑'

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"<ConfirmationReactions name = {self.name}, value = {self.value}>"


class ChannelEmoji(enum.Enum):
    text = '📑'
    voice = '🔊'
    category = '📂'

    @property
    def emoji(self):
        return self.value

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"<ChannelEmoji name = {self.name}, emoji = {self.value}"
