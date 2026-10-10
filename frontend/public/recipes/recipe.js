// Recipe page. Loaded from recipes/index.html. The address is /recipes/<slug>.

const seasons = {
  spring: "🌸 Spring",
  summer: "😎 Summer",
  autumn: "🎃 Autumn",
  winter: "☃️ Winter",
};

// TODO: Replace this stand-in with the recipe from the database for this address.
// A loaded recipe includes portions: the default batch, an integer of at least 1.
const recipesBySlug = {
  "earl-grey-martini": {
    title: "Earl Grey Martini",
    season: "spring",
    portions: 4,
    ingredients: [
      {
        name: "Earl Grey tea leaves",
        amounts: [
          { quantity: 2, unit: "g", system: "metric" },
          { quantity: 2, unit: "tsp", system: "us" },
        ],
      },
      {
        name: "gin",
        amounts: [
          { quantity: 180, unit: "ml", system: "metric" },
          { quantity: 6, unit: "fl. oz.", system: "us" },
        ],
      },
      { name: "White sugar", note: "for glass rim" },
      { name: "lemon", amounts: [{ quantity: 2, unit: "wedge" }] },
      {
        name: "freshly squeezed lemon juice",
        amounts: [
          { quantity: 90, unit: "ml", system: "metric" },
          { quantity: 3, unit: "fl. oz.", system: "us" },
        ],
      },
      {
        name: "simple syrup",
        amounts: [
          { quantity: 115, unit: "ml", system: "metric" },
          { quantity: 0.5, unit: "cup", system: "us" },
        ],
      },
    ],
    steps: [
      "Sprinkle tea leaves over gin and set aside to steep for 2 hours.",
      "Pour white sugar onto a small, shallow plate. Moisten the rims of the martini glasses with a wedge of lemon and dip into sugar.",
      "Strain the infused gin.",
      "Combine the gin, lemon juice, and simple syrup in a shaker with ice. Shake and strain into a martini glass.",
    ],
  },
  "the-bitter-end": { title: "The Bitter End" },
  "orange-creamsicle": { title: "Orange Creamsicle" },
  "spicy-cocoa": { title: "Spicy Cocoa" },
  "knob-kriek": { title: "Knob Kriek" },
  "brown-derby": { title: "Brown Derby" },
  "grapefruit-collins": { title: "Grapefruit Collins" },
};

const title = document.querySelector("#recipe-title");
const photo = document.querySelector("#recipe-photo");
const ingredientsBlock = document.querySelector("#recipe-ingredients-block");
const ingredientsList = document.querySelector("#recipe-ingredients");
const portionsControl = document.querySelector("#portions-control");
const portionsInput = document.querySelector("#portions");
const portionsLess = document.querySelector("#portions-less");
const portionsMore = document.querySelector("#portions-more");
const measureMetric = document.querySelector("#measure-metric");
const measureUs = document.querySelector("#measure-us");
const chatLog = document.querySelector("#recipe-chat-log");
const chatForm = document.querySelector("#recipe-chat-form");
const chatInput = document.querySelector("#recipe-chat-input");
const stepsBlock = document.querySelector("#recipe-steps-block");
const stepsList = document.querySelector("#recipe-steps");
const season = document.querySelector("#recipe-season");
const waiting = document.querySelector("#recipe-waiting");

let shownRecipe = null;
let measureSystem = "metric";
let chosenPortions = null;

portionsInput.addEventListener("input", () => {
  const count = portionCount();
  if (!shownRecipe || count === null) {
    return;
  }
  chosenPortions = count;
  renderIngredients(shownRecipe, count);
});

portionsInput.addEventListener("blur", () => {
  if (chosenPortions !== null) {
    portionsInput.value = String(chosenPortions);
  }
});

portionsLess.addEventListener("click", () => {
  changePortions(-1);
});

portionsMore.addEventListener("click", () => {
  changePortions(1);
});

measureMetric.addEventListener("click", () => {
  setMeasureSystem("metric");
});

measureUs.addEventListener("click", () => {
  setMeasureSystem("us");
});

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = chatInput.value.trim();
  if (!shownRecipe || question === "") {
    return;
  }
  appendChatMessage("You", question);
  chatInput.value = "";
  appendChatMessage("Assistant", discussModification(question));
});

showRecipe(recipesBySlug[recipeSlug()]);

function recipeSlug() {
  const path = location.pathname.replace(/\/+$/, "");
  const prefix = "/recipes/";
  if (!path.startsWith(prefix)) {
    return "";
  }
  return decodeURIComponent(path.slice(prefix.length));
}

function showRecipe(recipe) {
  if (!recipe) {
    title.textContent = "This recipe isn't loaded yet.";
    document.title = "Recipe — Chez Émilienne";
    return;
  }

  shownRecipe = recipe;
  chosenPortions = null;
  setMeasureSystem("metric");
  chatLog.replaceChildren();
  title.textContent = recipe.title;
  document.title = `${recipe.title} — Chez Émilienne`;

  if (recipe.photo) {
    photo.src = recipe.photo;
    photo.alt = recipe.title;
    photo.hidden = false;
  }

  if (recipe.ingredients) {
    const portions = defaultPortions(recipe);
    if (portions === null) {
      waiting.textContent = "This recipe needs a default portion count of at least 1.";
      waiting.hidden = false;
    } else {
      ingredientsBlock.hidden = false;
      portionsControl.hidden = false;
      chosenPortions = portions;
      portionsInput.value = String(portions);
      renderIngredients(recipe, portions);
    }
  }

  if (recipe.steps) {
    fillList(stepsList, recipe.steps);
    stepsBlock.hidden = false;
  }

  if (recipe.season && seasons[recipe.season]) {
    season.textContent = seasons[recipe.season];
    season.hidden = false;
  }

  if (!recipe.ingredients && !recipe.steps) {
    waiting.textContent = "Ingredients and steps wait on the recipes database.";
    waiting.hidden = false;
  }
}

function fillList(list, lines) {
  for (const line of lines) {
    const item = document.createElement("li");
    item.textContent = line;
    list.append(item);
  }
}

function changePortions(delta) {
  if (!shownRecipe || chosenPortions === null) {
    return;
  }
  const next = Math.max(1, chosenPortions + delta);
  chosenPortions = next;
  portionsInput.value = String(next);
  renderIngredients(shownRecipe, next);
}

function portionCount() {
  const value = Number(portionsInput.value);
  if (!Number.isInteger(value) || value < 1) {
    return null;
  }
  return value;
}

function defaultPortions(recipe) {
  const count = recipe.portions;
  if (!Number.isInteger(count) || count < 1) {
    return null;
  }
  return count;
}

function setMeasureSystem(system) {
  measureSystem = system;
  measureMetric.setAttribute("aria-pressed", String(system === "metric"));
  measureUs.setAttribute("aria-pressed", String(system === "us"));
  if (shownRecipe?.ingredients && chosenPortions !== null) {
    renderIngredients(shownRecipe, chosenPortions);
  }
}

function renderIngredients(recipe, portions) {
  const scale = portions / recipe.portions;
  ingredientsList.replaceChildren();
  for (const ingredient of recipe.ingredients) {
    const item = document.createElement("li");
    item.textContent = formatIngredient(ingredient, scale);
    ingredientsList.append(item);
  }
}

function formatIngredient(ingredient, scale) {
  const amounts = amountsForSystem(ingredient);
  if (amounts.length === 0) {
    return ingredient.note ? `${ingredient.name} (${ingredient.note})` : ingredient.name;
  }

  const scaled = amounts.map((amount) => ({
    quantity: amount.quantity * scale,
    unit: amount.unit,
  }));

  if (scaled[0].unit === "wedge") {
    const amount = scaled[0];
    return `${formatQuantity(amount.quantity)} ${ingredient.name} ${pluralUnit(amount.unit, amount.quantity)}`;
  }

  const [primary, ...rest] = scaled.map((amount) => formatMeasure(amount.quantity, amount.unit));
  const extra = rest.length > 0 ? ` (${rest.join(" or ")})` : "";
  return `${primary}${extra} ${ingredient.name}`;
}

function amountsForSystem(ingredient) {
  if (!ingredient.amounts) {
    return [];
  }
  const inSystem = ingredient.amounts.filter((amount) => amount.system === measureSystem);
  if (inSystem.length > 0) {
    return inSystem;
  }
  return ingredient.amounts.filter((amount) => !amount.system);
}

function formatMeasure(quantity, unit) {
  return `${formatQuantity(quantity)} ${pluralUnit(unit, quantity)}`;
}

function appendChatMessage(who, text) {
  const item = document.createElement("li");
  const role = document.createElement("span");
  role.className = "chat-role";
  role.textContent = who;
  const body = document.createElement("p");
  body.textContent = text;
  item.append(role, body);
  chatLog.append(item);
}

// TODO: Send the recipe, portion count, measurement system, and question to the mixology assistant.
function discussModification(question) {
  return "The assistant that answers recipe changes is not connected yet.";
}

function pluralUnit(unit, quantity) {
  const plurals = { jigger: "jiggers", cup: "cups", wedge: "wedges" };
  if (!plurals[unit] || quantity <= 1) {
    return unit;
  }
  return plurals[unit];
}

function formatQuantity(value) {
  const rounded = Math.round((value + Number.EPSILON) * 1000) / 1000;
  const whole = Math.floor(rounded + 1e-9);
  const fraction = rounded - whole;
  const glyphs = [
    [1 / 8, "⅛"],
    [1 / 4, "¼"],
    [1 / 3, "⅓"],
    [3 / 8, "⅜"],
    [1 / 2, "½"],
    [5 / 8, "⅝"],
    [2 / 3, "⅔"],
    [3 / 4, "¾"],
    [7 / 8, "⅞"],
  ];

  for (const [amount, glyph] of glyphs) {
    if (Math.abs(fraction - amount) < 0.01) {
      return whole > 0 ? `${whole}${glyph}` : glyph;
    }
  }

  if (Math.abs(rounded - Math.round(rounded)) < 0.001) {
    return String(Math.round(rounded));
  }
  return String(rounded);
}
