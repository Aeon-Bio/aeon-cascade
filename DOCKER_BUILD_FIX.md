# Docker Build Context Fix

## Problem
Docker couldn't access `../indra_agent` because the build context was set to `healthos_bot/` directory.

## Solution
Changed the Docker build context to the parent directory (`digitalme/`) so it can access both `healthos_bot/` and `indra_agent/`.

## Changes Made

### 1. docker-compose.yml (healthos_bot/)
**Before:**
```yaml
build:
  context: "."
  dockerfile: Dockerfile
```

**After:**
```yaml
build:
  context: ".."
  dockerfile: healthos_bot/Dockerfile
```

### 2. Dockerfile (healthos_bot/)
**Before:**
```dockerfile
COPY ./requirements.txt /tmp/requirements.txt
COPY ../indra_agent /tmp/indra_agent
COPY ../pyproject.toml /tmp/pyproject.toml
COPY . /code
```

**After:**
```dockerfile
COPY healthos_bot/requirements.txt /tmp/requirements.txt
COPY indra_agent /tmp/indra_agent
COPY pyproject.toml /tmp/pyproject.toml
COPY healthos_bot /code
```

## Directory Structure
```
digitalme/                    <- Build context starts here
├── healthos_bot/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── bot/bot.py
├── indra_agent/             <- Now accessible!
│   └── (agent code)
└── pyproject.toml           <- Now accessible!
```

## Usage
```bash
cd healthos_bot/

# This command now works because build context is parent directory
docker-compose --env-file config/config.env up --build
```

The docker-compose.yml is still in `healthos_bot/` but the build context is `..` (parent), giving Docker access to both subdirectories.

## Why This Works
- `docker-compose` runs from `healthos_bot/`
- Build context is set to `..` (parent = `digitalme/`)
- Dockerfile is at `healthos_bot/Dockerfile`
- COPY commands use paths relative to build context (`digitalme/`)
- Result: Docker can access both `healthos_bot/` and `indra_agent/`
