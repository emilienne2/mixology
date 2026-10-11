-- Initial tables for the recipe book.
-- SQLite checks foreign keys only when this is on for the connection.
PRAGMA foreign_keys = ON;

-- Seasons this book stores. name is the stored value. label and emoji are what the page shows.
CREATE TABLE seasons (
    name TEXT PRIMARY KEY CHECK (length(name) > 0),
    label TEXT NOT NULL CHECK (length(label) > 0),
    emoji TEXT NOT NULL CHECK (length(emoji) > 0)
);

INSERT INTO seasons (name, label, emoji) VALUES
    ('spring', 'Spring', '🌸'),
    ('summer', 'Summer', '😎'),
    ('autumn', 'Autumn', '🎃'),
    ('winter', 'Winter', '☃️');

-- One drink. path is the URL piece: /recipes/ plus path.
-- Amounts live on recipe_ingredients in US units. (Conversion to metric units available in the frontend.)
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE CHECK (length(path) > 0 AND path = lower(path) AND path NOT LIKE '% %'),
    title TEXT NOT NULL CHECK (length(title) > 0),
    portions INTEGER NOT NULL CHECK (portions >= 1),
    season TEXT NOT NULL REFERENCES seasons (name),
    photo TEXT CHECK (photo IS NULL OR length(photo) > 0)
);

-- Search groups for spirits. A family term matches every spirit in that family.
-- rum and rhum are the rum family, so either word matches white rum and every other rum.
-- whiskey and whisky are the whiskey family, so either word matches Scotch, Irish, bourbon, and every other whiskey.
-- amaro matches Amaro Montenegro and the spirit named amaro.
-- wine matches a spirit whose name contains wine, and also zinfandel, primitivo, tawny port, ruby port, and late-bottled vintage port.
-- A specific name, such as bourbon, matches that spirit only.
CREATE TABLE spirit_families (
    name TEXT PRIMARY KEY CHECK (length(name) > 0)
);

CREATE TABLE spirit_aliases (
    alias TEXT PRIMARY KEY CHECK (length(alias) > 0 AND alias = lower(alias)),
    family TEXT NOT NULL REFERENCES spirit_families (name)
);

INSERT INTO spirit_families (name) VALUES ('rum'), ('whiskey'), ('amaro'), ('wine');
INSERT INTO spirit_aliases (alias, family) VALUES
    ('rum', 'rum'),
    ('rhum', 'rum'),
    ('whiskey', 'whiskey'),
    ('whisky', 'whiskey'),
    ('amaro', 'amaro'),
    ('wine', 'wine');

-- Shared pantry. The spirit menu lists these names, plus a family name such as wine when no spirit uses that name.
-- A name is unique regardless of case, so gin and Gin are one ingredient.
-- family is set on a rum, whiskey, amaro, or wine spirit. Other spirits match their own name only.
-- grams_per_cup is the weight of one cup. A teaspoon, tablespoon, cup, or pint of that ingredient is shown in grams.
-- Empty means those volumes are shown in milliliters. fl oz stays milliliters, and oz stays grams.
CREATE TABLE ingredients (
    id INTEGER PRIMARY KEY,
    name TEXT COLLATE NOCASE NOT NULL UNIQUE CHECK (length(name) > 0),
    is_spirit INTEGER NOT NULL DEFAULT 0 CHECK (is_spirit IN (0, 1)),
    family TEXT REFERENCES spirit_families (name),
    grams_per_cup REAL CHECK (grams_per_cup IS NULL OR grams_per_cup > 0),
    CHECK (family IS NULL OR is_spirit = 1)
);

-- One row per search word that should find this spirit.
CREATE VIEW spirit_search AS
SELECT i.id AS ingredient_id, i.name AS name, a.alias AS term
FROM ingredients i
JOIN spirit_aliases a ON a.family = i.family
UNION
SELECT i.id, i.name, lower(i.name)
FROM ingredients i
WHERE i.is_spirit = 1;

-- Units this book stores. dash, pinch, drop, wedge, and count are left as written.
CREATE TABLE units (
    name TEXT PRIMARY KEY CHECK (length(name) > 0)
);

INSERT INTO units (name) VALUES
    ('fl oz'),
    ('cup'),
    ('pint'),
    ('tbsp'),
    ('tsp'),
    ('oz'),
    ('dash'),
    ('pinch'),
    ('drop'),
    ('wedge'),
    ('count');

-- One ingredient line, in page order.
-- choice_group marks one slot: only one of those lines is used.
-- optional means the ingredient can be left out.
CREATE TABLE recipe_ingredients (
    id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipes (id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients (id),
    position INTEGER NOT NULL CHECK (position >= 1),
    choice_group INTEGER CHECK (choice_group IS NULL OR choice_group >= 1),
    quantity REAL CHECK (quantity IS NULL OR quantity > 0),
    unit TEXT REFERENCES units (name),
    note TEXT CHECK (note IS NULL OR length(note) > 0),
    optional INTEGER NOT NULL DEFAULT 0 CHECK (optional IN (0, 1)),
    -- Both an amount and a unit, or neither.
    CHECK (
        (quantity IS NULL AND unit IS NULL)
        OR (quantity IS NOT NULL AND unit IS NOT NULL)
    ),
    -- No amount: a note, a choice option, or an optional line.
    CHECK (
        quantity IS NOT NULL
        OR note IS NOT NULL
        OR choice_group IS NOT NULL
        OR optional = 1
    ),
    UNIQUE (recipe_id, position)
);

CREATE INDEX recipe_ingredients_ingredient_id ON recipe_ingredients (ingredient_id);

-- One instruction, in page order.
CREATE TABLE steps (
    id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipes (id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position >= 1),
    instruction TEXT NOT NULL CHECK (length(instruction) > 0),
    UNIQUE (recipe_id, position)
);
