# deployment/ — Scout

## Local (Docker)
```bash
# From repo root
docker build -f deployment/Dockerfile -t scout-backend .
docker run -p 8000:8000 --env-file .env scout-backend
```
API at http://localhost:8000 (`/health`, `/research`, `/research/stream`).

The frontend (Vite) is served separately during dev (`npm run dev`). For a single
container, build the frontend and serve the static `dist/` from FastAPI, or add an Nginx
service via `docker compose` (TODO).

## Azure (bonus)
- Push the image to Azure Container Registry.
- Deploy as an Azure Container App or App Service.
- Set the same env vars (`AZURE_OPENAI_*`, `TAVILY_API_KEY`) as app settings.
