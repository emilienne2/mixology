const params = new URLSearchParams(location.search);
const criteria = {
  spirits: params.getAll("spirit").filter((name) => name.trim() !== ""),
  ingredients: (params.get("ingredients") ?? "").trim(),
  season: (params.get("season") ?? "").trim(),
  alcoholFree: params.get("alcohol-free") === "1",
};

const resultsLeft = document.querySelector("#results-left");
const resultsRight = document.querySelector("#results-right");
const searchStatus = document.querySelector("#search-status");

if (
  criteria.spirits.length === 0 &&
  criteria.ingredients === "" &&
  criteria.season === "" &&
  !criteria.alcoholFree
) {
  showStatus("Choose a spirit, an ingredient, or a season.");
} else {
  loadMatchingTitles();
}

function loadMatchingTitles() {
  fetch(`/api/search${location.search}`)
    .then((response) => {
      if (response.ok) {
        return response.json();
      }
      return response
        .json()
        .then((body) => {
          showStatus(searchFailure(body));
          return null;
        })
        .catch(() => {
          showStatus("Unable to complete search.");
          return null;
        });
    })
    .then((recipes) => {
      if (recipes === null) {
        return;
      }
      if (recipes.length === 0) {
        showStatus("No recipes match.");
        return;
      }
      const midpoint = Math.ceil(recipes.length / 2);
      fillRecipeList(resultsLeft, recipes.slice(0, midpoint));
      fillRecipeList(resultsRight, recipes.slice(midpoint));
    })
    .catch(() => showStatus("Unable to complete search."));
}

function searchFailure(body) {
  const message = body && typeof body.detail === "string" ? body.detail.trim() : "";
  if (message === "") {
    return "Unable to complete search.";
  }
  return `Unable to complete search: ${message}`;
}

function showStatus(message) {
  searchStatus.hidden = false;
  searchStatus.textContent = message;
}

function fillRecipeList(list, recipes) {
  for (const recipe of recipes) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = `/recipes/${recipe.path}`;
    link.textContent = recipe.title;
    item.append(link);
    list.append(item);
  }
}
