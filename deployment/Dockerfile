# Scout backend (FastAPI + LangGraph). Build from repo root:
#   docker build -f deployment/Dockerfile -t scout-backend .
#   docker run -p 8000:8000 --env-file .env scout-backend
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY prompts/ ./prompts/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
