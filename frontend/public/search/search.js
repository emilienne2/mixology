const params = new URLSearchParams(location.search);
const criteria = {
  spirits: params.getAll("spirit"),
  ingredients: params.get("ingredients") ?? "",
  season: params.get("season") ?? "",
};

// TODO: Replace this stand-in list with titles from the recipes database that match criteria.
// A rum or rhum term matches every rum. A whiskey or whisky term matches every whiskey.
function titlesForCriteria(criteria) {
  return [
    "Earl Grey Martini",
    "The Bitter End",
    "Orange Creamsicle",
    "Spicy Cocoa",
    "Knob Kriek",
    "Brown Derby",
    "Grapefruit Collins",
  ];
}

const recipeTitles = titlesForCriteria(criteria);

const resultsLeft = document.querySelector("#results-left");
const resultsRight = document.querySelector("#results-right");

const sortedTitles = recipeTitles.toSorted((a, b) => a.localeCompare(b));
const midpoint = Math.ceil(sortedTitles.length / 2);

fillRecipeList(resultsLeft, sortedTitles.slice(0, midpoint));
fillRecipeList(resultsRight, sortedTitles.slice(midpoint));

function fillRecipeList(list, titles) {
  for (const title of titles) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = recipePath(title);
    link.textContent = title;
    item.append(link);
    list.append(item);
  }
}

function recipePath(title) {
  const slug = title
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `/recipes/${slug}`;
}
