"""Stable constants for the first TOMANAP ruleset."""

from enum import StrEnum
from types import MappingProxyType


class Category(StrEnum):
    """The seven answer categories in their TOMANAP display order."""

    COUNTRIES = "countries"
    CITIES = "cities"
    BRANDS = "brands"
    ACTIVITIES = "activities"
    NAMES = "names"
    ANIMALS = "animals"
    PLANTS = "plants"


CATEGORIES: tuple[Category, ...] = (
    Category.COUNTRIES,
    Category.CITIES,
    Category.BRANDS,
    Category.ACTIVITIES,
    Category.NAMES,
    Category.ANIMALS,
    Category.PLANTS,
)

CATEGORY_LABELS = MappingProxyType(
    {
        Category.COUNTRIES: "Țări",
        Category.CITIES: "Orașe",
        Category.BRANDS: "Mărci",
        Category.ACTIVITIES: "Activități",
        Category.NAMES: "Nume",
        Category.ANIMALS: "Animale",
        Category.PLANTS: "Plante",
    }
)

# Version one selects uniformly from the basic Latin alphabet. Romanian
# diacritics are folded to their basic equivalents during comparison.
ALPHABET: tuple[str, ...] = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

MIN_PLAYERS = 2
MAX_PLAYERS = 6
MIN_ROUNDS = 1
MAX_ROUNDS = len(ALPHABET)
DEFAULT_ROUND_DURATION_SECONDS = 60
MAX_ANSWER_LENGTH = 80

UNIQUE_ANSWER_POINTS = 10
DUPLICATE_ANSWER_POINTS = 5
INVALID_ANSWER_POINTS = 0
