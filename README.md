# Chez Émilienne 🥃

This personal project (WIP) will be a full-stack, containerized cocktail recipe book and AI mixology assistant.

## 🏗️ Architecture & Stack

**Frontend** HTML5, Vanilla JavaScript, CSS (Served via Nginx)

**Backend** (TODO) Python (FastAPI), packaged with Poetry

**Database** SQLite

**Deployment** Containerized with Docker Compose, designed for local hosting (TODO) on a Beelink Mini PC via Cloudflare Tunnels.

## 🚀 Local Development Setup

### Prerequisites

- Docker Desktop
- Git

### Running the App

To spin up the frontend (Nginx) and (once implemented - TODO) the backend locally:

`docker compose up`

Frontend accessible at: `http://localhost:8080` 

Backend API will be accessible at: `http://localhost:8000`

### Recipes database

Recipe files in `database/recipes/` are the committed copy. `database/mixology.db` is built from them and is not committed. The site does not read this database yet.

Build the full database from all committed recipe files:

```
docker run --rm -v "$PWD":/work -w /work python:3 python database/build_database.py
```

Add a new recipe to the existing database:

```
docker run --rm -v "$PWD":/work -w /work python:3 python database/add_recipe.py database/recipes/earl-grey-martini.json
```