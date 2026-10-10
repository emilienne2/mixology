// Home page. Loaded from the bottom of index.html.

// TODO: Replace this placeholder with spirit names from the recipes database.
// Each name is a checkbox. Search sends the checked names.
const spiritsFromRecipes = [];

// TODO: Replace this placeholder with drink titles from the recipes database.
const recipeTitles = [];

const spiritToggle = document.querySelector("#spirit-toggle");
const spiritOptions = document.querySelector("#spirit-options");
const ingredientsInput = document.querySelector("#ingredients");
const seasonSelect = document.querySelector("#season");
const knownRecipe = document.querySelector("#known-recipe");
const findDrink = document.querySelector("#find-drink");
const surprise = document.querySelector("#surprise");
const surpriseStatus = document.querySelector("#surprise-status");

renderSpiritOptions(spiritsFromRecipes);
renderRecipeTitles(recipeTitles);

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
  location.assign(query === "" ? "/search/" : `/search/?${query}`);
});

surprise.addEventListener("click", () => {
  surpriseStatus.textContent =
    recipeTitles.length === 0 ? "No recipes loaded yet." : "";
});

function setSpiritMenuOpen(open) {
  spiritToggle.setAttribute("aria-expanded", String(open));
  spiritOptions.hidden = !open;
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
    label.append(box, document.createTextNode(` ${name}`));
    item.append(label);
    spiritOptions.append(item);
  }
}

function renderRecipeTitles(titles) {
  knownRecipe.replaceChildren();

  const prompt = document.createElement("option");
  prompt.value = "";
  prompt.selected = true;

  if (titles.length === 0) {
    prompt.textContent = "No recipes yet";
    prompt.disabled = true;
    knownRecipe.append(prompt);
    return;
  }

  // Stays selected so the first real title is not chosen for the visitor.
  prompt.textContent = "Choose a recipe";
  knownRecipe.append(prompt);

  for (const title of titles) {
    const option = document.createElement("option");
    option.value = title;
    option.textContent = title;
    knownRecipe.append(option);
  }
}
