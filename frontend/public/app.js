// Home page. Loaded from the bottom of index.html.

const spiritToggle = document.querySelector("#spirit-toggle");
const spiritOptions = document.querySelector("#spirit-options");
const ingredientsInput = document.querySelector("#ingredients");
const seasonSelect = document.querySelector("#season");
const knownRecipe = document.querySelector("#known-recipe");
const findDrink = document.querySelector("#find-drink");
const alcoholFree = document.querySelector("#alcohol-free");
const surprise = document.querySelector("#surprise");
const surpriseStatus = document.querySelector("#surprise-status");
const searchStatus = document.querySelector("#search-status");

let recipes = [];

loadSpiritNames();
loadRecipeTitles();
loadSeasons();

spiritToggle.addEventListener("click", () => {
  setSpiritMenuOpen(spiritToggle.getAttribute("aria-expanded") !== "true");
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".combo")) {
    setSpiritMenuOpen(false);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    setSpiritMenuOpen(false);
  }
});

findDrink.addEventListener("submit", (event) => {
  event.preventDefault();
  const params = new URLSearchParams();

  for (const box of spiritOptions.querySelectorAll('input[name="spirit"]:checked')) {
    params.append("spirit", box.value);
  }

  const ingredients = ingredientsInput.value.trim();
  if (ingredients !== "") {
    params.append("ingredients", ingredients);
  }

  if (seasonSelect.value !== "") {
    params.append("season", seasonSelect.value);
  }

  const query = params.toString();
  if (query === "") {
    searchStatus.textContent = "Choose a spirit, an ingredient, or a season.";
    return;
  }

  searchStatus.textContent = "";
  location.assign(`/search/?${query}`);
});

alcoholFree.addEventListener("click", () => {
  location.assign("/search/?alcohol-free=1");
});

knownRecipe.addEventListener("change", () => {
  if (knownRecipe.value !== "") {
    location.assign(`/recipes/${knownRecipe.value}`);
  }
});

surprise.addEventListener("click", () => {
  if (recipes.length === 0) {
    surpriseStatus.textContent = "No recipes loaded yet.";
    return;
  }
  const index = Math.floor(Math.random() * recipes.length);
  location.assign(`/recipes/${recipes[index].path}`);
});

function setSpiritMenuOpen(open) {
  spiritToggle.setAttribute("aria-expanded", String(open));
  spiritOptions.hidden = !open;
}

function loadSpiritNames() {
  fetch("/api/spirits")
    .then((response) => (response.ok ? response.json() : []))
    .then((names) => renderSpiritOptions(names))
    .catch(() => renderSpiritOptions([]));
}

function loadRecipeTitles() {
  fetch("/api/recipe-titles")
    .then((response) => (response.ok ? response.json() : []))
    .then((loaded) => {
      recipes = loaded;
      renderRecipeTitles(recipes);
    })
    .catch(() => renderRecipeTitles([]));
}

function loadSeasons() {
  fetch("/api/seasons")
    .then((response) => (response.ok ? response.json() : []))
    .then((rows) => {
      for (const row of rows) {
        const option = document.createElement("option");
        option.value = row.name;
        option.textContent = `${row.emoji} ${row.label}`;
        seasonSelect.append(option);
      }
    })
    .catch(() => {});
}

function renderSpiritOptions(names) {
  spiritOptions.replaceChildren();

  if (names.length === 0) {
    const empty = document.createElement("li");
    empty.className = "combo-empty";
    empty.textContent = "No spirits yet";
    spiritOptions.append(empty);
    return;
  }

  for (const name of names) {
    const item = document.createElement("li");
    item.setAttribute("role", "option");
    const label = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.name = "spirit";
    box.value = name;
    label.append(box, document.createTextNode(name));
    item.append(label);
    spiritOptions.append(item);
  }
}

function renderRecipeTitles(menu) {
  knownRecipe.replaceChildren();

  const prompt = document.createElement("option");
  prompt.value = "";
  prompt.selected = true;

  if (menu.length === 0) {
    prompt.textContent = "No recipes yet";
    prompt.disabled = true;
    knownRecipe.append(prompt);
    return;
  }

  // Stays selected so the first real title is not chosen for the visitor.
  prompt.textContent = "Choose a recipe";
  knownRecipe.append(prompt);

  for (const recipe of menu) {
    const option = document.createElement("option");
    option.value = recipe.path;
    option.textContent = recipe.title;
    knownRecipe.append(option);
  }
}
