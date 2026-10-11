// Recipe page. Loaded from recipes/index.html. The address is /recipes/<path>.

// Filled from the seasons table. The key is the stored name, such as autumn.
const seasonLabels = new Map();

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
let measureSystem = "us";
let chosenPortions = null;

// US volume units. The metric toggle converts these to ml.
// Under 20 ml, nearest 1. From 20 up to 100, nearest 5. From 100 up, nearest 10.
// oz is weight. The metric toggle converts it to grams, nearest 1.
// A cup weight converts tsp, tbsp, cup, and pint of that ingredient to grams, nearest 1.
const gramsPerOunce = 28.349523125;
const cupsPerUsUnit = {
  cup: 1,
  tbsp: 1 / 16,
  tsp: 1 / 48,
  pint: 2,
};
const mlPerUsUnit = {
  "fl oz": 29.5735295625,
  cup: 236.5882365,
  pint: 473.176473,
  tbsp: 14.78676478125,
  tsp: 4.92892159375,
};

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

const recipePath = recipeSlug();
Promise.all([loadSeasons(), loadRecipe(recipePath)]).then(([, loadedRecipe]) => {
  showRecipe(loadedRecipe);
});

function loadRecipe(path) {
  if (path === "") {
    return Promise.resolve(null);
  }
  return fetch(`/api/recipes/${encodeURIComponent(path)}`)
    .then((response) => (response.ok ? response.json() : null))
    .catch(() => null);
}

function loadSeasons() {
  return fetch("/api/seasons")
    .then((response) => (response.ok ? response.json() : []))
    .then((rows) => {
      for (const row of rows) {
        seasonLabels.set(row.name, `${row.emoji} ${row.label}`);
      }
    })
    .catch(() => {});
}

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
  setMeasureSystem("us");
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

  const seasonLabel = seasonLabels.get(recipe.season);
  if (seasonLabel) {
    season.textContent = seasonLabel;
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
  for (const group of ingredientGroups(recipe.ingredients)) {
    const item = document.createElement("li");
    item.textContent = formatGroup(group, scale);
    ingredientsList.append(item);
  }
}

// Lines that share a choiceGroup are one slot. The cook uses one of them.
function ingredientGroups(ingredients) {
  const groups = [];
  for (const ingredient of ingredients) {
    const group = groups.at(-1);
    if (ingredient.choiceGroup != null && group?.[0].choiceGroup === ingredient.choiceGroup) {
      group.push(ingredient);
    } else {
      groups.push([ingredient]);
    }
  }
  return groups;
}

function formatGroup(group, scale) {
  const text = group.length > 1 ? formatChoice(group, scale) : formatIngredient(group[0], scale);
  return group.every((ingredient) => ingredient.optional) ? `${text}, optional` : text;
}

function formatChoice(options, scale) {
  const first = options[0];
  const sharedMeasure = options.every(
    (option) => option.quantity === first.quantity && option.unit === first.unit && option.quantity != null,
  );
  if (!sharedMeasure) {
    return options.map((option) => formatIngredient(option, scale)).join(" or ");
  }

  const lead = formatIngredient(first, scale);
  const firstName = displayedName(first, scale);
  if (!lead.endsWith(firstName)) {
    return options.map((option) => formatIngredient(option, scale)).join(" or ");
  }
  const measure = lead.slice(0, -firstName.length);
  const sameMeasure = options.every(
    (option) => formatIngredient(option, scale) === `${measure}${displayedName(option, scale)}`,
  );
  if (!sameMeasure) {
    return options.map((option) => formatIngredient(option, scale)).join(" or ");
  }
  const names = options.map((option) => displayedName(option, scale)).join(" or ");
  return `${measure}${names}`;
}

function displayedName(ingredient, scale) {
  return ingredient.unit === "count" ? pluralName(ingredient.name, ingredient.quantity * scale) : ingredient.name;
}

function formatIngredient(ingredient, scale) {
  if (ingredient.quantity == null || ingredient.unit == null) {
    return ingredient.note ? `${ingredient.name} (${ingredient.note})` : ingredient.name;
  }

  const quantity = ingredient.quantity * scale;
  if (ingredient.unit === "count") {
    return `${formatQuantity(quantity)} ${pluralName(ingredient.name, quantity)}`;
  }

  if (ingredient.unit === "wedge") {
    return `${formatQuantity(quantity)} ${ingredient.name} ${pluralUnit(ingredient.unit, quantity)}`;
  }

  if (measureSystem === "metric" && ingredient.unit === "oz") {
    const grams = Math.max(1, Math.round(quantity * gramsPerOunce));
    return `${formatQuantity(grams)} g ${ingredient.name}`;
  }

  if (measureSystem === "metric" && ingredient.gramsPerCup != null && cupsPerUsUnit[ingredient.unit]) {
    const grams = Math.max(1, Math.round(quantity * cupsPerUsUnit[ingredient.unit] * ingredient.gramsPerCup));
    return `${formatQuantity(grams)} g ${ingredient.name}`;
  }

  if (measureSystem === "metric" && mlPerUsUnit[ingredient.unit]) {
    return `${formatQuantity(metricMilliliters(quantity, ingredient.unit))} ml ${ingredient.name}`;
  }

  return `${formatMeasure(quantity, ingredient.unit)} ${ingredient.name}`;
}

function metricMilliliters(quantity, unit) {
  const ml = quantity * mlPerUsUnit[unit];
  if (ml < 20) {
    return Math.max(1, Math.round(ml));
  }
  if (ml < 100) {
    return Math.round(ml / 5) * 5;
  }
  return Math.round(ml / 10) * 10;
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

function pluralName(name, quantity) {
  if (quantity <= 1) {
    return name;
  }

  // Ordered endings. leaf becomes leaves. ch, sh, s, x, and z gain es. A consonant plus y becomes ies.
  const pluralEndings = [
    [/leaf$/i, "leaves"],
    [/(ch|sh|s|x|z)$/i, "$1es"],
    [/([^aeiou])y$/i, "$1ies"],
  ];
  for (const [ending, plural] of pluralEndings) {
    if (ending.test(name)) {
      return name.replace(ending, plural);
    }
  }
  return `${name}s`;
}

function pluralUnit(unit, quantity) {
  const plurals = { cup: "cups", dash: "dashes", drop: "drops", pinch: "pinches", pint: "pints", wedge: "wedges" };
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
    [1 / 6, "⅙"],
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
