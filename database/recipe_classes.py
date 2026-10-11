from typing import NotRequired, TypedDict


class IngredientJson(TypedDict):
    name: str
    quantity: NotRequired[int | float]
    unit: NotRequired[str]
    note: NotRequired[str]
    is_spirit: NotRequired[bool]
    family: NotRequired[str]
    grams_per_cup: NotRequired[int | float]
    optional: NotRequired[bool]


class ChoiceJson(TypedDict):
    choice: list[IngredientJson]


class RecipeJson(TypedDict):
    title: str
    portions: int
    season: str
    photo: NotRequired[str]
    ingredients: list[IngredientJson | ChoiceJson]
    steps: list[str]


class Ingredient(TypedDict):
    name: str
    quantity: int | float | None
    unit: str | None
    note: str | None
    is_spirit: bool | None
    family: str | None
    grams_per_cup: float | None
    choice_group: int | None
    optional: bool
    position: int


class Step(TypedDict):
    position: int
    instruction: str


class Recipe(TypedDict):
    title: str
    path: str
    portions: int
    season: str
    photo: str | None
    ingredients: list[Ingredient]
    steps: list[Step]


class RecipeError(Exception):
    pass
