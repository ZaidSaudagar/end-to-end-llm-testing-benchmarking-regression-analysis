# Deployment

The supported release path is Docker Compose on one Linux host. It runs the FastAPI backend and Streamlit dashboard in separate non-root containers built from the same image. SQLite data and the Sentence Transformers cache use named volumes.

## Prepare the host

Install Docker Engine and the Docker Compose plugin. In the project directory, create the local deployment environment file and generate a unique API key:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set the generated value as `BACKEND_API_KEY` in `.env`, set `DEBUG=false`, and add at least one provider key (`GEMINI_API_KEY` or `OPENROUTER_API_KEY`). For API-key protected local requests, also set `DASHBOARD_API_KEY` to the same value. Compose passes the backend key to the dashboard automatically. Keep `.env` private; it is excluded from Git and the container build context.

Start the release:

```bash
docker compose -f compose.yaml up --build -d
docker compose -f compose.yaml ps
```

By default, the dashboard is at `http://127.0.0.1:8501`; the backend is bound to `http://127.0.0.1:8000`. Backend API routes require `X-API-Key`. The health and readiness endpoints stay unauthenticated for container health checks. Readiness checks the database connection. Production mode disables the interactive API documentation.

To stop the services while preserving data:

```bash
docker compose -f compose.yaml down
```

The `app-data` volume stores SQLite history; `model-cache` stores downloaded embedding weights. Back up the `app-data` volume before upgrades or host maintenance. The SQLite deployment is intended for one backend instance and one host. Do not scale the backend service horizontally or place the database on a shared network filesystem.

## Public access

The Compose file binds both ports to loopback by default. Keep them there and place a TLS reverse proxy with user authentication in front of the dashboard when remote access is needed. The dashboard grants access to start provider-backed runs, which can incur API costs. Do not expose the dashboard directly to the public internet. If the proxy runs in a separate container or host, configure the bind addresses and `ALLOWED_HOSTS` deliberately, retain the backend API key, and restrict network access to the proxy. The application API key does not authenticate dashboard users.

Use a persistent secret manager instead of a checked-in file when running this on a managed server. Rotate the backend key by updating both backend and dashboard configuration, then recreate the services:

```bash
docker compose -f compose.yaml up -d --force-recreate backend dashboard
```

CI builds the same container image on pushes and pull requests. It does not publish images or deploy to a host. For a release, review the commit, tag it in Git, and build the image from that tag. Publishing to a registry or deploying to a hosting account remains an operator-controlled step.
