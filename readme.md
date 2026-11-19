# RepoLens

RepoLens is an evidence-first codebase intelligence workspace. It analyzes a public GitHub repository or ZIP archive, stores a persistent source snapshot, maps supported files and dependencies, indexes source chunks, runs code-quality and optional security checks, and provides repository-aware chat grounded in retrieved evidence.

## Table of contents

- [Core capabilities](#core-capabilities)
- [Application architecture](#application-architecture)
- [Technology stack](#technology-stack)
- [Repository structure](#repository-structure)
- [Local development](#local-development)
- [Environment variables](#environment-variables)
- [Docker deployment](#docker-deployment)
- [Analysis workflow](#analysis-workflow)
- [API reference](#api-reference)
- [Frontend views](#frontend-views)
- [GitHub App integration](#github-app-integration)
- [Security and coverage scanning](#security-and-coverage-scanning)
- [Redis workers](#redis-workers)
- [Tests and CI](#tests-and-ci)
- [Deployment checks](#deployment-checks)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)

## Core capabilities

- Analyze GitHub repositories and ZIP uploads
- Track ingestion jobs and analysis phases
- Persist source snapshots and graph metadata
- Semantic search over code chunks
- Repository-aware LLM chat with source citations
- Architecture and project-structure overview
- Import and inferred symbol-call relationship analysis
- Entry-point and central-file detection
- Code-health scoring and prioritized findings
- Test-framework and coverage-report discovery
- LCOV, Cobertura XML, and Istanbul JSON parsing
- Semgrep, Gitleaks, and pip-audit integration
- Git branch and recent commit metadata
- GitHub pull-request reading and review publishing
- Markdown, PDF, and shared-workspace reports
- Multi-repository side-by-side comparison
- Optional API-key authentication
- Redis-backed queues or local FastAPI background tasks

## Application architecture

```text
Browser
  |
  | HTTP
  v
React + Vite frontend
  |
  | /api requests
  v
FastAPI backend
  |
  +--> Job tracker
  +--> Git/ZIP ingestion
  +--> Tree-sitter parsing
  +--> NetworkX graph
  +--> Sentence Transformers embeddings
  +--> Chroma vector collection
  +--> Groq repository chat
  +--> Static and optional security scanners
  |
  +--> Persistent workspace JSON and source files
  +--> Redis queue in distributed deployments
```

The backend creates a unique repository workspace for each completed analysis. The workspace contains analysis metadata and stored source files. Chroma stores semantic code chunks separately.

## Technology stack

### Frontend

- React 18
- Vite
- React Router
- Axios
- React Markdown and remark-gfm
- React Syntax Highlighter

### Backend

- Python 3.11
- FastAPI
- Pydantic settings
- GitPython
- NetworkX
- ChromaDB
- Sentence Transformers
- Groq SDK
- Tree-sitter
- ReportLab
- Redis Python client
- PyJWT

## Repository structure

```text
backend/
  app/
    main.py                 FastAPI application and middleware
    core/config.py          Environment-backed settings
    routes/                 API route modules
    services/
      ingestion.py          Git/ZIP intake and repository limits
      parser.py             Tree-sitter parsing
      chunker.py            Source chunk generation
      graph.py              Import and call graph creation
      coverage.py           Test and coverage analysis
      scanner.py            Semgrep, Gitleaks, pip-audit integration
      llm.py                Groq prompts and repository chat
      jobs.py               File/Redis job state
      queue.py              Redis/local queue dispatch
      workers.py            Redis worker entry point
      repository_store.py   Workspace persistence and sharing
      github_integration.py GitHub App/PAT operations
      comparison.py         Multi-repository calculations
  tests/                    Backend tests
  Dockerfile
  requirements.txt

frontend/
  src/
    pages/                  Home, chat, compare, shared workspace
    components/             Overview, source, graph, chat, bugs
    api/client.js           Axios configuration
  Dockerfile
  nginx.conf
  package.json

docker-compose.yml
.github/workflows/ci.yml
```

## Local development

### Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- Git
- A Groq API key for repository chat

Optional:

- Docker with Docker Compose
- Redis
- Semgrep
- Gitleaks
- pip-audit

### 1. Create a Python environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

### 2. Configure the backend

```powershell
Copy-Item backend\.env.example backend\.env
```

Set at least:

```dotenv
GROQ_API_KEY=your_groq_api_key
```

### 3. Start the API

```powershell
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health endpoints:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/ready`
- `http://127.0.0.1:8000/deployment`

OpenAPI documentation:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

### 4. Start the frontend

Open another terminal:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`.

## Environment variables

### Backend

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | empty | Enables repository chat and architecture summaries |
| `APP_NAME` | `RepoLens API` | API title |
| `ENVIRONMENT` | `development` | Environment name and production validation mode |
| `CORS_ORIGINS` | localhost frontend origins | Comma-separated allowed browser origins |
| `DATA_DIR` | `./data` | Workspaces and jobs storage |
| `CHROMA_PATH` | `./data/chroma` | Chroma vector database location |
| `MAX_UPLOAD_BYTES` | `104857600` | Maximum ZIP upload size |
| `MAX_ZIP_MEMBERS` | `10000` | Maximum ZIP entries |
| `MAX_ZIP_UNCOMPRESSED_BYTES` | `524288000` | Maximum uncompressed ZIP size |
| `MAX_FILES_PER_REPO` | `5000` | Maximum supported source files |
| `MAX_FILE_BYTES` | `1000000` | Maximum parsed file size |
| `ALLOWED_GIT_HOSTS` | GitHub hosts | Allowed Git hostnames |
| `API_KEYS` | empty | Optional comma-separated API keys |
| `REDIS_URL` | empty | Redis queue connection |
| `GITHUB_TOKEN` | empty | Optional PAT for GitHub pull requests |
| `GITHUB_APP_ID` | empty | GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY` | empty | GitHub App PEM private key |
| `GITHUB_APP_INSTALLATION_ID` | empty | GitHub App installation ID |
| `GITHUB_WEBHOOK_SECRET` | empty | GitHub webhook signing secret |
| `ENABLE_REAL_SCANNERS` | `false` | Enables Semgrep, Gitleaks, and pip-audit |

### Frontend

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | Backend API prefix |
| `VITE_API_KEY` | empty | Optional `X-API-Key` value |

Do not expose private keys or API secrets through `VITE_*` variables. Vite variables are delivered to the browser.

## Docker deployment

Copy the backend environment file:

```powershell
Copy-Item backend\.env.example backend\.env
```

Add at least `GROQ_API_KEY`, then run:

```powershell
docker compose up --build
```

Docker Compose starts:

- Redis
- FastAPI backend
- Redis worker
- Production Nginx frontend

Open:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

Stop the stack:

```powershell
docker compose down
```

The data and Redis volumes can be retained or removed explicitly:

```powershell
docker compose down -v
```

Production deployments should:

- Set `ENVIRONMENT=production`
- Set explicit `CORS_ORIGINS`
- Set `API_KEYS`
- Store secrets in Docker secrets or an external secret manager
- Terminate TLS at a reverse proxy
- Give Redis authentication and private-network isolation
- Mount persistent storage for `/app/data`
- Use multiple workers only with Redis enabled

## Analysis workflow

1. The user submits a GitHub URL or ZIP archive.
2. The API creates a job and queues or starts a background task.
3. The repository is cloned or extracted.
4. Supported files are discovered and subject to size limits.
5. Tree-sitter extracts functions, classes, imports, and calls.
6. Source snapshots are persisted.
7. NetworkX creates file and symbol relationships.
8. Source chunks are embedded and stored in Chroma.
9. Static findings and optional external scanners run.
10. Test and coverage reports are discovered.
11. Git history and overview metadata are stored.
12. Groq produces an architecture summary when configured.
13. The client polls job state and opens the repository workspace.

## API reference

### Health and configuration

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Process liveness |
| `GET` | `/ready` | Data, Chroma, and Redis readiness |
| `GET` | `/deployment` | Deployment configuration status |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/redoc` | ReDoc documentation |

### Ingestion

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/ingest/url` | Start URL analysis |
| `POST` | `/api/ingest/zip` | Start ZIP analysis |
| `POST` | `/api/ingest/debug` | Inspect files found before analysis |
| `GET` | `/api/ingest/jobs/{job_id}` | Read analysis status and result |

### Repository workspaces

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/repositories?limit=20&offset=0` | Paginate saved workspaces |
| `GET` | `/api/repositories/{repo_id}` | Get complete analysis metadata |
| `GET` | `/api/repositories/{repo_id}/overview` | Get AI summary, health, and structure |
| `GET` | `/api/repositories/{repo_id}/source?path=...` | Read a stored source file |
| `GET` | `/api/repositories/{repo_id}/coverage` | Get test and coverage analysis |
| `GET` | `/api/repositories/{repo_id}/git` | Get branch and commit metadata |
| `GET` | `/api/repositories/{repo_id}/report` | Download Markdown report |
| `GET` | `/api/repositories/{repo_id}/report.pdf` | Download PDF report |
| `POST` | `/api/repositories/{repo_id}/scan` | Run enabled external scanners |
| `DELETE` | `/api/repositories/{repo_id}` | Delete workspace and vector collection |

### Chat

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/ask` | Ask a repository-aware question |
| `POST` | `/api/bugs/explain` | Summarize static findings with the LLM |

Example:

```json
{
  "repo_id": "workspace-id",
  "question": "Explain the data flow through the ingestion pipeline",
  "summary": {}
}
```

### Comparison

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/repositories/compare` | Compare two to five workspaces |
| `POST` | `/api/repositories/compare/report` | Download comparison Markdown |

Example:

```json
{
  "repo_ids": ["repo-a", "repo-b"]
}
```

### Sharing

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/repositories/{repo_id}/share` | Create a read-only share token |
| `DELETE` | `/api/repositories/{repo_id}/share` | Revoke sharing |
| `GET` | `/api/shared/{token}` | Read a shared analysis |

Shared workspaces expose repository metadata but do not expose source-edit operations or private chat.

## Frontend views

### Home

- GitHub URL ingestion
- ZIP upload
- Recent workspace history
- Multi-repository comparison entry

### Repository overview

- AI architecture summary
- Health score
- Language and framework breakdown
- Dependency metrics
- Symbol-call metrics
- Entry points
- Central files
- Test and coverage details
- Prioritized findings
- Git history
- Pull requests
- Sharing and report actions

### Chat

- Repository-wide questions
- Retrieved source chunks
- Markdown-formatted answers
- Syntax-highlighted source citations
- Open-source navigation

### Architecture

- Technology breakdown
- Folder distribution
- Entry points
- Central files
- Import and call relationships
- Confidence labels for inferred edges

### Source

- Searchable file list
- Syntax-highlighted source
- Line highlighting
- Ask-AI about the selected file

### Issues

- Severity filtering
- Finding details
- Snippets
- AI issue explanations

## GitHub App integration

Create a GitHub App and set:

- `GITHUB_APP_ID`
- `GITHUB_APP_PRIVATE_KEY`
- `GITHUB_APP_INSTALLATION_ID`
- `GITHUB_WEBHOOK_SECRET`

Configure the webhook URL:

```text
https://your-host/api/github/webhooks/github
```

Recommended permissions:

- Pull requests: Read and write
- Contents: Read-only
- Metadata: Read-only

Recommended events:

- `pull_request`
- `pull_request_review`
- `installation`

GitHub App endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/repositories/{repo_id}/pulls` | List pull requests |
| `GET` | `/api/repositories/{repo_id}/pulls/{pull_number}` | Read PR diff metadata |
| `POST` | `/api/github/pull-requests/review` | Publish a review |
| `POST` | `/api/github/webhooks/github` | Receive signed webhooks |

Review events:

- `COMMENT`
- `APPROVE`
- `REQUEST_CHANGES`

For live review publishing, a real GitHub App private key and installation token must be configured.

## Security and coverage scanning

Set:

```dotenv
ENABLE_REAL_SCANNERS=true
```

Available scanners:

| Tool | Purpose |
| --- | --- |
| Semgrep | Source-code vulnerability patterns |
| Gitleaks | Secret and credential detection |
| pip-audit | Python dependency vulnerabilities |

Gitleaks and pip-audit are included in supported environment setups. Semgrep must be available on `PATH` or installed through a deployment-specific package.

All scanner findings are normalized to:

- File
- Line
- Severity
- Rule
- Message
- Redacted snippet
- Scanner source

### Coverage support

RepoLens discovers test frameworks and test files, then accepts:

- LCOV: `lcov.info` or `.lcov`
- Cobertura: `coverage.xml` or `cobertura.xml`
- Istanbul: `coverage-final.json`

Coverage is evidence-based. If no report is present, the UI reports that coverage is unavailable rather than estimating an unsupported percentage.

## Redis workers

Set:

```dotenv
REDIS_URL=redis://redis:6379/0
```

When Redis is configured:

- API requests place analysis tasks in `repolens:queue`
- Workers consume tasks from Redis
- Job state is persisted in Redis
- Failed tasks are retried up to three attempts
- Interrupted processing records are requeued by the worker at startup

Without Redis, the API uses FastAPI background tasks. This is suitable for local development but not multi-process horizontal scaling.

Run a worker locally:

```powershell
Set-Location backend
python -m app.workers
```

## Tests and CI

### Backend

```powershell
Set-Location backend
python -m pytest -q
python -m compileall -q app tests
python -m pip check
```

### Frontend

```powershell
Set-Location frontend
npm run lint
npm test
npm run build
```

GitHub Actions runs frontend lint/tests/build and backend compile/tests/dependency/smoke validation.

## Deployment checks

| Endpoint | Purpose |
| --- | --- |
| `/health` | Process liveness |
| `/ready` | Data directory, Chroma, and Redis readiness |
| `/deployment` | Production configuration status |

Example smoke test:

```powershell
curl.exe --fail http://127.0.0.1:8000/health
curl.exe --fail http://127.0.0.1:8000/ready
curl.exe --fail http://127.0.0.1:8000/deployment
```

The backend container runs as a non-root user. The frontend production image uses Nginx and serves the Vite SPA with API proxying.

## Limitations

- Redis worker state does not replace all process restart recovery; stale processing records are requeued at worker startup.
- Import resolution is conservative and does not model every language runtime.
- Symbol-call matching is evidence-based and may produce inferred rather than type-correct edges.
- Static findings and heuristics are not a replacement for specialized security review.
- Coverage discovery is report-based; tests are not executed inside the backend.
- Repository chat quality depends on Groq availability and retrieved context.
- GitHub App publishing requires valid credentials and permissions.
- The API key mechanism is suitable for simple deployments, not a complete identity platform.
- The public sharing mechanism is token-based and should not be used for confidential repositories.
- Large repositories remain subject to configured file, upload, and token limits.

## Troubleshooting

### Backend cannot import GitPython

Reinstall dependencies:

```powershell
python -m pip install -r backend\requirements.txt
```

### Chat returns a missing-key error

Set `GROQ_API_KEY` in `backend/.env`, restart the backend, and confirm the value is not the placeholder `your_groq_api_key_here`.

### Frontend cannot reach the backend

Confirm `VITE_API_BASE_URL=http://localhost:8000/api` and the backend is running on port `8000`.

### 401 responses

Set `VITE_API_KEY` to the same value included in backend `API_KEYS`.

### 404 after an API restart

Redis or file-backed jobs should persist, but old jobs created before persistence changes cannot be recovered.

### Port 8000 or 5173 is occupied

Identify and stop only the process listening on that port:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
Stop-Process -Id <OwningProcess>
```

### Docker is unavailable

Run the backend and frontend directly:

```powershell
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then start the frontend in another terminal.

### Markdown is rendering incorrectly

Ensure `react-markdown` and `remark-gfm` are installed:

```powershell
Set-Location frontend
npm ci
npm run dev
```
