import json
import os
from typing import List, Tuple, Union

import discord
from discord.ext.commands import Context

from .paginator import SubcommandPaginator

with open(os.path.abspath("./subcommands/subcommandhelp.json"), "r") as file:
    _HELPDATA = json.loads(file.read())


class EntryData(object):
    __slots__ = [
        "desc",
        "usage",
        "returns",
        "aliases",
        "uperms",
        "bperms",
        "note",
    ]

    def __init__(self, *, desc: str = None,
                 usage: str = None, returns: str = None,
                 aliases: List[str] = [], uperms: List[str] = [],
                 bperms: List[str] = [], note: str = None) -> None:
        self.desc = desc
        self.usage = usage
        self.returns = returns
        self.aliases = aliases
        self.uperms = uperms
        self.bperms = bperms
        self.note = note


class SubCommandEntry(object):
    __slots__ = [
        "name",
        "pfx",
        "_desc",
        "_usage",
        "_returns",
        "_aliases",
        "_uperms",
        "_bperms",
        "_note",
        "inline",
        "nospaced",
    ]

    def __init__(self, name: str, pfx: str, data: EntryData,
                 inline: bool = False, nospaced: bool = False, **kwargs) -> None:
        self.name = name
        self.pfx = pfx
        self._desc = data.desc
        self._usage = data.usage
        self._returns = data.returns
        self._aliases = " ".join(f"`{alias}`" for alias in data.aliases)
        self._uperms = " ".join(f"`{perm}`" for perm in data.uperms)
        self._bperms = " ".join(f"`{perm}`" for perm in data.bperms)
        self._note = data.note
        self.inline = inline
        self.nospaced = nospaced

    @property
    def desc(self) -> str:
        return f"**Description:** {self._desc}"

    @property
    def usage(self) -> str:
        return f"**Usage:** `{self.pfx}{'' if self.nospaced else ' '}{self._usage}`"

    @property
    def returns(self) -> str:
        return f"**Returns:** {self._returns}"

    @property
    def aliases(self) -> str:
        return f"**Aliases:** {self._aliases}"

    @property
    def uperms(self) -> str:
        return f"**User Permissions:** {self._uperms}"

    @property
    def bperms(self) -> str:
        return f"**Bot Permissions:** {self._bperms}"

    @property
    def note(self) -> str:
        return f"**Note:** {self._note}"

    @property
    def all(self) -> Tuple[str, List[str], bool]:
        return self.name, [
            getattr(self, attr) for attr in [
                "desc", "usage", "returns", "aliases", "uperms", "bperms", "note"
            ] if getattr(self, f"_{attr}")
        ], self.inline


class SubcommandHelp(object):
    __slots__ = [
        "pfx",
        "nospaced",
        "title",
        "description",
        "per_page",
        "entries",
        "show_entry_count",
        "embed",
    ]

    def __init__(self, pfx: str, nospaced=False, title: str = None,
                 description: str = None, per_page: int = 3,
                 show_entry_count: bool = False, embed: discord.Embed = None) -> None:
        self.pfx = str(pfx)
        self.nospaced = nospaced
        self.title = str(title)
        self.description = str(description)
        self.per_page = per_page
        self.entries: List[SubCommandEntry] = []
        self.show_entry_count = show_entry_count
        self.embed = embed

    def add_entry(self, name: str, data: Union[EntryData, dict], inline: bool = False) -> "SubcommandHelp":
        self.entries.append(
            SubCommandEntry(
                name,
                self.pfx,
                data if isinstance(data, EntryData) else EntryData(**data),
                inline,
                self.nospaced,
            )
        )
        return self

    def from_config(self, base_command: str) -> "SubcommandHelp":
        for entry in _HELPDATA[base_command]:
            self.add_entry(entry, data=_HELPDATA[base_command][entry])
        return self

    def _prepare_embed(self, embed: discord.Embed) -> discord.Embed:
        if not embed:
            return discord.Embed(title=self.title,
                                 description=self.description,
                                 color=discord.Color.blue())
        return self.embed

    async def show_help(self, ctx: Context) -> discord.Message:
        self.embed = self._prepare_embed(self.embed)
        return await SubcommandPaginator(
            ctx,
            entries=[entry.all for entry in self.entries],
            per_page=self.per_page,
            show_entry_count=self.show_entry_count,
            embed=self.embed,
        ).paginate()
