import math
import discord
from discord.ext import commands
import pokepy


poke_client = pokepy.V2Client(cache='in_disk', cache_location="./pokepy_cache")
move_status_icon_urls = ["https://oyster.ignimgs.com/mediawiki/apis.ign.com/pokemon-switch/e/ef/Physical.png?width=325",
                         "https://oyster.ignimgs.com/mediawiki/apis.ign.com/pokemon-switch/2/24/Special.png?width=325",
                         "https://oyster.ignimgs.com/mediawiki/apis.ign.com/pokemon-switch/d/d0/Status.png?width=325"]

"""
German Translation for the ability command is thanks to Isabelle. Thank you so much. I wouldn't have been able to make
high quality translations that are actually grammatically correct.
"""


class Pokedex(commands.Cog):

    def __init__(self, client):
        self.client = client

    def truncate(self, number: float, decimal_places: int) -> float:
        stepper = 10.0 ** decimal_places
        return math.trunc(stepper * number) / stepper

    async def check_pokemon(self, name: str) -> pokepy.api.rv2.PokemonResource:
        try:
            return poke_client.get_pokemon(name)
        except Exception:
            return None

    async def get_dex_entry(self, name: str) -> tuple:
        value = await self.check_pokemon(name)
        if not value:
            return None

        pokemon_name = f"Name: `{value.name.capitalize()}`"
        type_list = [types.type.name.capitalize() for types in value.types]
        if not type_list:
            type = "Type: `Unknown`"
        else:
            type = "Type: `" + "` `".join(type_list) + "`"
        nat_dex_num = f"National Dex Number: `{value.id}`"
        ability_list = [(ability.ability.name.capitalize().replace("-", " "), ability.is_hidden) for ability in
                        value.abilities]
        abilities = "Abilities: "
        for ability_name, is_hidden in ability_list:
            if is_hidden:
                abilities += f"*`{ability_name} (hidden)`* "
            else:
                abilities += f"`{ability_name}` "
        base_xp = f"Base XP: `{value.base_experience}`"
        if value.height / 10 >= 1:
            height = f"Height: `{self.truncate((value.height / 10), 2)} m`"
        else:
            height = f"Height: `{self.truncate((value.height * 10), 3)} m`"
        items_list = [item.item.name.capitalize().replace("-", " ") for item in value.held_items]
        if not items_list:
            items = "Wild Held Items: `None`"
        else:
            items = "Wild Held Items: `" + "` `".join(items_list) + "`"
        weight = f"Weight: `{value.weight / 10} kg`"
        return pokemon_name, nat_dex_num, type, abilities, items, weight, height, base_xp

    async def get_dex_sprite(self, name: str) -> tuple:
        value = await self.check_pokemon(name)
        return value.sprites.front_default, value.sprites.front_shiny

    async def check_move(self, name: str) -> pokepy.api.rv2.MoveResource:
        try:
            return poke_client.get_move(name)
        except Exception:
            return None

    async def get_move_entry(self, name: str) -> tuple:
        value = await self.check_move(name)
        if not value:
            return None

        if value.accuracy:
            move_accuracy = f"Accuracy: `{value.accuracy}`"
        else:
            move_accuracy = f"Accuracy: `N/A`"
        move_effect_entry = f"Description: ```{value.effect_entries[0].effect}```"
        move_type = f"Type: `{value.type.name.capitalize()}`"
        move_damage_class = f"Move Class: `{value.damage_class.name.capitalize()}`"
        if value.power:
            move_power = f"Power: `{value.power}`"
        else:
            move_power = "Power: `N/A`"
        move_pp = f"PP: `{value.pp}`"
        move_max_pp = f"Max PP: `{math.ceil(float(value.pp) * 8.0 / 5.0)}`"
        move_priority = f"Priority: `{value.priority}`"
        move_target = f"Target: `{value.target.name.replace('-', ' ').capitalize()}`"
        return (move_effect_entry, move_type, move_damage_class, move_power, move_accuracy,
                move_target, move_pp, move_max_pp, move_priority)

    async def get_move_status_icon(self, name: str) -> str:
        value = await self.get_move_entry(name)
        if "physical" in value[2].lower():
            return move_status_icon_urls[0]
        elif "special" in value[2].lower():
            return move_status_icon_urls[1]
        elif "status" in value[2].lower():
            return move_status_icon_urls[2]

    async def check_ability(self, name: str) -> pokepy.api.rv2.AbilityResource:
        try:
            return poke_client.get_ability(name)
        except Exception:
            return None

    async def get_ability_entry(self, name: str, flag: str) -> tuple:
        value = await self.check_ability(name)
        if not value:
            return None

        ability_pokemon_list = [name.pokemon.name.capitalize() for name in value.pokemon]
        if flag == "-de":
            ability_name_temp = [locale.name for locale in value.names if locale.language.name == "de"]
            ability_effect_entry = f"Beschreibung: ```{value.effect_entries[0].effect}```"
            ability_pokemon = "Pokémon mit dieser Fähigkeit: \n`" + "` `".join(ability_pokemon_list) + "`"
        else:
            ability_name_temp = [locale.name for locale in value.names if locale.language.name == "en"]
            ability_effect_entry = f"Description: ```{value.effect_entries[1].effect}```"
            ability_pokemon = "Pokémon with this Ability: \n`" + "` `".join(ability_pokemon_list) + "`"
        ability_name = ability_name_temp[0]

        return ability_name, ability_effect_entry, ability_pokemon

    async def check_item(self, name) -> pokepy.api.rv2.ItemResource:
        try:
            return poke_client.get_item(name)
        except Exception:
            return None

    async def get_item_entry(self, name: str) -> tuple:
        value = await self.check_item(name)
        if not value:
            return None

        item_name = f"Name: `{value.name.replace('-', ' ').capitalize()}`"
        if value.cost == 0:
            item_purchase_cost = "Purchase Price: `N/A`"
        else:
            item_purchase_cost = f"Purchase Price: `{value.cost} Pokédollars`"
        item_description = f"Description: ```{value.effect_entries[0].short_effect}```"
        item_fling_power = f"Fling Power: `{value.fling_power}`"
        if not value.fling_effect:
            item_fling_effect = "Fling Effect: `N/A`"
        else:
            item_fling_effect = f"Fling Effect: `{value.fling_effect}`"
        if value.held_by_pokemon:
            item_held_by_list = [pokemon.pokemon.name.capitalize() for pokemon in value.held_by_pokemon]
            item_held_by = "Items Held in Wild By: `" + "` `".join(item_held_by_list) + '`'
        else:
            item_held_by = "Items Held in Wild By: `N/A`"
        if value.attributes:
            item_attributes_list = [item.name.capitalize() for item in value.attributes]
            item_attributes = "Attributes: `" + "` `".join(item_attributes_list) + "`"
        else:
            item_attributes = "Attributes: `N/A`"
        item_category = f"Category: `{value.category.name.replace('-', ' ').capitalize()}`"

        return (item_name, item_category, item_description, item_attributes, item_purchase_cost, item_fling_power,
                item_fling_effect, item_held_by)

    async def get_item_sprite(self, name):
        value = await self.check_item(name)
        return value.sprites.default

    async def check_type(self, name: str) -> pokepy.api.rv2.TypeResource:
        try:
            return poke_client.get_type(name)
        except Exception:
            return None

    async def get_type_interactions(self, name: str) -> str:
        value = await self.check_type(name)
        dr = value.damage_relations
        key_names = ["Double Damage From: ", "Double Damage To: ", "Half Damage From: ", "Half Damage To: ",
                     "No Damage From: ", "No Damage To: "]
        damage = [dr.double_damage_from, dr.double_damage_to, dr.half_damage_from, dr.half_damage_to,
                  dr.no_damage_from, dr.no_damage_to]

        index = 0
        string = ""
        non = "`N/A`"

        for relation in damage:
            string += key_names[index]
            if relation:
                for item in relation:
                    string += f"`{item.name.capitalize()}` "
            else:
                string += non
            index += 1
            if index != 6:
                string += "\n"
        return string

    async def get_type_moves(self, name: str) -> str:
        value = await self.check_type(name)
        key = value.moves
        move_list = [item.name.replace("-", " ").title() for item in key]
        return "Moves:\n`" + "` `".join(sorted(move_list)) + "`"

    async def get_type_pokemon(self, name: str) -> str:
        value = await self.check_type(name)
        key = value.pokemon
        pokemon_list = [item.pokemon.name.replace("-", " ").title() for item in key]
        return "Pokemon:\n`" + "` `".join(sorted(pokemon_list)) + "`"

    async def get_type_entry(self, name: str) -> tuple:
        value = await self.check_type(name)
        if not value:
            return None

        type_name = f"Name: `{value.name}`"
        type_interactions = await self.get_type_interactions(name)
        if not value.move_damage_class:
            type_move_damage_class = f"Damage Class: `N/A`"
        else:
            type_move_damage_class = f"Damage Class: `{value.move_damage_class.name.capitalize()}`"
        return type_name, type_interactions, type_move_damage_class

    @commands.group(aliases=['dex'])
    async def pokedex(self, ctx):
        if not ctx.invoked_subcommand:
            panel = discord.Embed(title="Pokedex Commands",
                                  description=f"Access MarwynnBot's Pokédex using `?pokedex "
                                              f"(option)`. Please note that in order to avoid discrepancies in "
                                              f"versions, I have not included many of the game specific data.\n Here "
                                              f"is a list of all available `pokedex` options",
                                  color=discord.Color.blue())
            panel.add_field(name="Pokémon",
                            value=f"Usage: `?pokedex pokemon [name]`\n"
                                  f"Returns: Details about the specified Pokémon\n"
                                  f"Aliases: `-p`",
                            inline=False)
            panel.add_field(name="Move",
                            value=f"Usage: `?pokedex move [name]`\n"
                                  f"Returns: Details about the move\n"
                                  f"Aliases: `moves` `-m`",
                            inline=False)
            panel.add_field(name="Ability",
                            value=f"Usage: `?pokedex ability [name] [optional flag]`\n"
                                  f"Returns: Details about the specified ability\n"
                                  f"Flag: `-de` `-en` or blank *(defaults to english)*\n"
                                  f"Aliases: `-a`",
                            inline=False)
            panel.add_field(name="Item",
                            value=f"Usage: `? pokedex item [name]`\n"
                                  f"Returns: Details about the item"
                                  f"Aliases: `-i`",
                            inline=False)
            panel.add_field(name="Type",
                            value=f"Usage: `?pokedex type [name]`\n"
                                  f"Returns: Details about that type"
                                  f"Flag: `-p` `-m` or blank *(defaults to none)*"
                                  f"Aliases: `-t`",
                            inline=False)
            return await ctx.channel.send(embed=panel)

    @pokedex.command(aliases=['-p'])
    async def pokemon(self, ctx, *, pokemon_name: str):
        value = await self.get_dex_entry(pokemon_name)
        if value:
            embed = discord.Embed(title=pokemon_name.capitalize(),
                                  description=f"{ctx.author.mention}, here is {pokemon_name.capitalize()}'s "
                                              f"Pokédex entry\n\n",
                                  color=discord.Color.blue())
            embed.description += "\n".join(value)
            sprites = await self.get_dex_sprite(pokemon_name)
            if sprites[0]:
                embed.set_image(url=sprites[0])
            if sprites[1]:
                embed.set_thumbnail(url=sprites[1])
            return await ctx.channel.send(embed=embed)
        else:
            invalid = discord.Embed(title="Invalid Pokémon Name",
                                    description=f"{ctx.author.mention}, `{pokemon_name.capitalize()}` is not a valid "
                                                f"Pokémon",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid, delete_after=5)

    @pokedex.command(aliases=['-m', 'moves'])
    async def move(self, ctx, *, move_name: str):
        move_name_sent = move_name.replace(" ", "-").lower()
        value = await self.get_move_entry(move_name_sent)
        if value:
            embed = discord.Embed(title=move_name.capitalize(),
                                  description=f"{ctx.author.mention}, here is {move_name.capitalize()}'s move entry\n\n",
                                  color=discord.Color.blue())
            embed.description += "\n".join(value)
            embed.set_thumbnail(url=await self.get_move_status_icon(move_name_sent))
            return await ctx.channel.send(embed=embed)
        else:
            invalid = discord.Embed(title="Invalid Move Name",
                                    description=f"{ctx.author.mention}, `{move_name}` is not a valid move",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid, delete_after=5)

    @pokedex.command(aliases=['-a'])
    async def ability(self, ctx, *, ability_name_with_flag: str):
        flag = ability_name_with_flag[-4:]
        if flag == " -de" or flag == " -en":
            ability_name = ability_name_with_flag[:-4].replace(" ", "-")
            ability_name_sent = ability_name.lower()
            value = await self.get_ability_entry(ability_name_sent, flag[-3:])
        else:
            if flag == " -en":
                ability_name = ability_name_with_flag[:-4].replace(" ", "-")
            else:
                ability_name = ability_name_with_flag.replace(" ", "-")
            ability_name_sent = ability_name.lower()
            value = await self.get_ability_entry(ability_name_sent, "-en")
        if value:
            embed = discord.Embed(title=value[0],
                                  color=discord.Color.blue())
            if flag == " -de":
                embed.description = f"{ctx.author.mention}, hier ist die Info für {value[0]}\n\n"
            else:
                embed.description = f"{ctx.author.mention}, here is the info for {value[0]}\n\n"
            fields = (value[1], value[2])
            embed.description += "\n".join(fields)

            await ctx.channel.send(embed=embed)
        else:
            if flag == "-de":
                invalid = discord.Embed(title="Ungültiger Fähigkeitsname",
                                        description=f"{ctx.author.mention}, `{ability_name}` ist keine gültige Fähigkeit",
                                        color=discord.Color.dark_red())

            else:
                invalid = discord.Embed(title="Invalid Ability Name",
                                        description=f"{ctx.author.mention}, `{ability_name}` is not a valid ability",
                                        color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid, delete_after=5)

    @pokedex.command(aliases=['-i'])
    async def item(self, ctx, *, item_name: str):
        item_name_sent = item_name.replace(" ", "-").lower()
        value = await self.get_item_entry(item_name_sent)
        if value:
            embed = discord.Embed(title=item_name.capitalize(),
                                  description=f"{ctx.author.mention}, here is the info for {item_name}\n\n",
                                  color=discord.Color.blue())
            embed.description += "\n".join(value)
            embed.set_thumbnail(url=await self.get_item_sprite(item_name_sent))
            return await ctx.channel.send(embed=embed)
        else:
            invalid = discord.Embed(title="Invalid Item Name",
                                    description=f"{ctx.author.mention}, `{item_name}` is not a valid item",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid, delete_after=5)

    @pokedex.command(aliases=['-t'])
    async def type(self, ctx, *, type_name_flag: str):
        flag = type_name_flag[-3:]
        if flag == " -p" or flag == " -m":
            type_name = type_name_flag[:-3]
        else:
            flag = None
            type_name = type_name_flag
        type_name_sent = type_name.lower()
        value = await self.get_type_entry(type_name_sent)
        if value:
            embed = discord.Embed(title=type_name_sent.title(),
                                  description=f"{ctx.author.mention}, here is the info for type {type_name_sent}\n\n",
                                  color=discord.Color.blue())
            if flag:
                if flag == " -p":
                    embed.description = f"{ctx.author.mention}, here are all the Pokémon of type {type_name_sent}\n\n" \
                                        f"{await self.get_type_pokemon(type_name_sent)}"
                elif flag == " -m":
                    embed.description = f"{ctx.author.mention}, here are all the moves of type {type_name_sent}\n\n" \
                                        f"{await self.get_type_moves(type_name_sent)}"
            else:
                embed.description += "\n\n".join(value)
                embed.description += f"\n\n*For information on what Pokémon or moves are {type_name_sent} type, add " \
                                     f"the flag `-p` or `-m` respectively to the command*"
            return await ctx.channel.send(embed=embed)
        else:
            invalid = discord.Embed(title="Invalid Type Name",
                                    description=f"{ctx.author.mention}, `{type_name}` is not a valid type",
                                    color=discord.Color.dark_red())
            return await ctx.channel.send(embed=invalid, delete_after=5)


def setup(client):
    client.add_cog(Pokedex(client))
