# Chez Émilienne 🥃

This personal project is a full-stack, containerized cocktail recipe book and AI mixology assistant.

## 🏗️ Architecture & Stack

**Frontend** HTML5, Vanilla JavaScript, CSS (Served via Nginx)

**Backend** Python (FastAPI), packaged with Poetry

**Database** SQLite

**AI Assistant** Gemini 3.5 Flash-Lite on Google's free tier. The backend calls it over HTTPS.

**Deployment** Containerized with Docker Compose, designed for local hosting (TODO) on a Beelink Mini PC via Cloudflare Tunnels.

## 🚀 Local Development Setup

### Prerequisites

- Docker Desktop
- Git

### Running the App

To spin up the frontend (Nginx) and the backend locally:

`docker compose up`

Frontend accessible at: `http://localhost:8080` 

Backend API is accessible at: `http://localhost:8000`

### Using the AI Assistant via the Get Creative chat

Get Creative asks Gemini 3.5 Flash-Lite how to change the recipe on the page. The FastAPI container sends the saved recipe, the portion count, the measurement system, and the question to Google, and shows the reply. The reply is not saved.

This is a short suggestion about one drink, so the free tier is enough. Google runs the model. The containers stay nginx, the API, and SQLite. Google may use these free-tier requests to improve its models.

Create a key in [Google AI Studio](https://aistudio.google.com/apikey) and choose **Default Gemini Project**. The project name and project number stay with that key.

Put the key in a `.env` file next to `docker-compose.yml`:

```
GEMINI_API_KEY=your-key
```

`.env` is gitignored. Restart the backend after saving it:

```
docker compose up -d backend
```

### Recipes database

Recipe files in `database/recipes/` are the committed copy. `database/mixology.db` is built from them and is not committed. Build that database before starting the app. The backend mounts the file read-only, and the pages read it through the API.

Build the full database from all committed recipe files:

```
docker run --rm -v "$PWD":/work -w /work python:3 python database/build_database.py
```

Add a new recipe to the existing database:

```
docker run --rm -v "$PWD":/work -w /work python:3 python database/add_recipe.py database/recipes/earl-grey-martini.json
```

### Testing

Three checks cover loader rules that building the database does not: the recipe path, a conflicting cup weight, and a spirit family inferred from the name.

```
docker run --rm -v "$PWD":/work -w /work python:3 python -m unittest database/test_recipe_rules.py
```