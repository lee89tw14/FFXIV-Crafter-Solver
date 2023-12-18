"""
Simple Python script to extract information from XIVAPI and save relevant data to .json files.
"""
import json
import math
import threading
import typing as t
from collections import defaultdict
from pathlib import Path

import requests

#########
# Globals
#########
# Buffs Endpoint
BUFFS_API_URL = "https://xivapi.com/search"
buff_types = ["Medicine", "Meal"]
RECIPE_API_URL = "https://xivapi.com/Recipe"
PARENT_DIR = Path(__file__).parents[1]


###########
# Type Defs
###########
class LocaleNames(t.TypedDict):
    en: t.NotRequired[str]
    de: t.NotRequired[str]
    fr: t.NotRequired[str]
    ja: t.NotRequired[str]


class RecipeType(t.TypedDict):
    id: int
    name: LocaleNames
    baseLevel: int
    level: int
    difficulty: int
    durability: int
    maxQuality: int
    suggestedCraftsmanship: int
    suggestedControl: int
    progressDivider: int
    progressModifier: int
    qualityDivider: int
    qualityModifier: int
    stars: t.NotRequired[int]


class RecipeJSONLevelTableType(t.TypedDict):
    ClassJobLevel: int
    Stars: int
    ID: int
    Difficulty: int | float
    Durability: int
    Quality: int
    SuggestedCraftsmanship: int
    SuggestedControl: int
    ProgressDivider: int
    ProgressModifier: int
    QualityDivider: int
    QualityModifier: int


class RecipeJSONType(t.TypedDict):
    ID: int
    Name_en: str
    Name_de: str
    Name_fr: str
    Name_ja: str
    ClassJob: t.Any
    DurabilityFactor: float
    QualityFactor: float
    DifficultyFactor: float
    RequiredControl: int
    RequiredCraftsmanship: int
    RecipeLevelTable: RecipeJSONLevelTableType | None


class Buffs(t.TypedDict):
    id: int
    cp_percent: int
    cp_value: int
    craft_percent: int
    craft_value: int
    control_percent: int
    control_value: int
    hq: bool
    name: LocaleNames


###############
# Function Defs
###############


def construct_recipe_json(original_recipe: RecipeJSONType) -> RecipeType | None:
    """Returns a recipe dictionary in the format desired by the FFXIV crafting solver.
    Rewriting how it handles all the data is a monumental task, so instead I'm just going to do this.

    Args:
        original_recipe (RecipeJSONType): The recipe as returned from xivapi in Python Dict.

    Returns:
        RecipeType | None: A formated output dict of the recipe, or None if the recipe level table is None.
    """
    if original_recipe["RecipeLevelTable"] is None:
        return
    recipe_name_dict: LocaleNames = {}
    recipe: RecipeType = {
        "id": original_recipe["ID"],
        "name": recipe_name_dict,
        "baseLevel": original_recipe["RecipeLevelTable"]["ClassJobLevel"],
        "level": original_recipe["RecipeLevelTable"]["ID"],
        "difficulty": math.floor(
            original_recipe["RecipeLevelTable"]["Difficulty"]
            * original_recipe["DifficultyFactor"]
            / 100
        ),
        "durability": math.floor(
            original_recipe["RecipeLevelTable"]["Durability"]
            * original_recipe["DurabilityFactor"]
            / 100
        ),
        "maxQuality": math.floor(
            original_recipe["RecipeLevelTable"]["Quality"]
            * original_recipe["QualityFactor"]
            / 100
        ),
        "suggestedCraftsmanship": original_recipe["RecipeLevelTable"][
            "SuggestedCraftsmanship"
        ],
        "suggestedControl": original_recipe["RecipeLevelTable"]["SuggestedControl"],
        "progressDivider": original_recipe["RecipeLevelTable"]["ProgressDivider"],
        "progressModifier": original_recipe["RecipeLevelTable"]["ProgressModifier"],
        "qualityDivider": original_recipe["RecipeLevelTable"]["QualityDivider"],
        "qualityModifier": original_recipe["RecipeLevelTable"]["QualityModifier"],
    }
    recipe["name"]["en"] = original_recipe["Name_en"]
    recipe["name"]["de"] = original_recipe["Name_de"]
    recipe["name"]["fr"] = original_recipe["Name_fr"]
    recipe["name"]["ja"] = original_recipe["Name_ja"]
    if original_recipe["RecipeLevelTable"]["Stars"] != 0:
        recipe["stars"] = original_recipe["RecipeLevelTable"]["Stars"]
    return recipe


def get_total_pages() -> int:
    """Gets the total amount of recipe pages that exist!

    Returns:
        int: Total number of recipe pages.
    """
    r = requests.get(RECIPE_API_URL)
    recipe_data = r.json()
    return int(recipe_data["Pagination"]["PageTotal"])


def api_call(page_id: int, recipes: defaultdict[t.Any, list[t.Any]]) -> None:
    """Handles the actual API calls.

    Args:
        page_id (int): Page number to request.
        recipes (defaultdict[t.Any, list[t.Any]]): Building list of recipes grabbed from XIVAPI. Modifies in place.
    """
    url_call = (
        f"https://xivapi.com/Recipe?page={page_id}&columns=ID,Name_en,Name_de,Name_fr,Name_ja,"
        f"ClassJob.NameEnglish,DurabilityFactor,QualityFactor,DifficultyFactor,RequiredControl,"
        f"RequiredCraftsmanship,RecipeLevelTable"
    )
    r = requests.get(url_call)
    page_data = r.json()
    if r.status_code == 429:
        print("Too many requests sent to XIVAPI!")

    for recipe in page_data["Results"]:
        key = recipe["ClassJob"]["NameEnglish"]
        constructed_recipe = construct_recipe_json(recipe)
        if constructed_recipe:
            recipes[key].append(constructed_recipe)


def handle_api_calls(pages_amount: int) -> dict[str, list[RecipeType]]:
    """Handle API calls with multi-threading, since XIVAPI is rate limited to 20.


    Args:
        pages_amount (int): Number of recipe pages to request on.

    Returns:
        dict[str, list[RecipeType]]: The raw python dict of recipes.
    """
    recipes: defaultdict[str, list[RecipeType]] = defaultdict(list)
    threads: list[threading.Thread] = []
    for i in range(1, pages_amount + 1):
        t = threading.Thread(target=api_call, args=(i, recipes))
        threads.append(t)
        t.start()
        if i % 20 == 0:
            for t in threads:
                t.join()
            threads = []
    for t in threads:
        t.join()
    return recipes


def save_data_to_json(recipes: dict[str, list[RecipeType]]) -> None:
    """Save recipes data to a .json file

    Args:
        recipes (dict[str, list[RecipeType]]): The formatted python dict to save of recipes.
    """
    Path(f"{PARENT_DIR}/app/data/recipedb/").mkdir(parents=True, exist_ok=True)
    for class_job, class_recipes in recipes.items():
        class_recipes = sorted(class_recipes, key=lambda x: x["id"])
        with open(
            f"{PARENT_DIR}/app/data/recipedb/{class_job}.json",
            mode="w",
            encoding="utf-8",
        ) as my_file:
            json.dump(
                class_recipes, my_file, indent=2, sort_keys=True, ensure_ascii=False
            )


def extract_buff_data(buff_name: str) -> list[Buffs]:
    """Extracts buff data for the given buff_name


    Args:
        buff_name (str): The target buff name to extract info on.

    Returns:
        list[Buffs]: The resulting extracted buff data.
    """
    params = {
        "indexes": "item",
        "columns": "ID,Name,Bonuses,Name_en,Name_de,Name_fr,Name_ja",
        "body": {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"Bonuses.CP.Relative": "true"}},
                        {"match": {"Bonuses.Control.Relative": "true"}},
                        {"match": {"Bonuses.Craftsmanship.Relative": "true"}},
                    ],
                    "must_not": [{"match": {"ItemSearchCategory.Name_en": buff_name}}],
                }
            },
            "from": 0,
            "size": 100,
        },
    }
    request = requests.post(BUFFS_API_URL, json=params)
    request.raise_for_status()

    buffs: list[Buffs] = []
    for item in request.json()["Results"]:
        # Extract both HQ and NQ buff data
        for hq in [False, True]:
            new_item: Buffs = {
                "id": item.get("ID"),
                "cp_percent": item.get("Bonuses", {}).get("CP", {}).get("Value"),
                "cp_value": item.get("Bonuses", {}).get("CP", {}).get("Max"),
                "craft_percent": item.get("Bonuses", {})
                .get("Craftsmanship", {})
                .get("Value"),
                "craft_value": item.get("Bonuses", {})
                .get("Craftsmanship", {})
                .get("Max"),
                "control_percent": item.get("Bonuses", {})
                .get("Control", {})
                .get("Value"),
                "control_value": item.get("Bonuses", {}).get("Control", {}).get("Max"),
                "hq": hq,
                "name": {
                    "en": item.get("Name_en"),
                    "de": item.get("Name_de"),
                    "fr": item.get("Name_fr"),
                    "ja": item.get("Name_ja"),
                },
            }

            # Remove None values from previous step
            buffs.append(
                t.cast(Buffs, {k: v for k, v in new_item.items() if v is not None})
            )
    return buffs


def save_buffs_to_file(buffs: list[Buffs], buff_name: str) -> None:
    """Save buffs data to a .json file

    Args:
        buffs (list[Buffs]): The list of buffs overall.
        buff_name (str): The specific buff name to save.
    """
    Path(f"{PARENT_DIR}/app/data/buffs").mkdir(parents=True, exist_ok=True)
    with open(
        f"{PARENT_DIR}/app/data/buffs/{buff_name}.json", mode="w", encoding="utf-8"
    ) as my_file:
        json.dump(buffs, my_file, indent=2, sort_keys=True, ensure_ascii=False)


if __name__ == "__main__":
    pages_amount = get_total_pages()
    recipes = handle_api_calls(pages_amount)
    save_data_to_json(recipes)

    for buff_name in buff_types:
        buffs = extract_buff_data(buff_name)
        buffs = sorted(buffs, key=lambda x: (x["id"], x["hq"]))
        save_buffs_to_file(buffs, buff_name)
