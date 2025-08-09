# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This is a Slack bot that integrates Claude Code CLI with Slack workspaces to answer questions about GitHub repositories. The architecture follows a distributed task processing pattern:

### Core Components
- **FastAPI Server** (`main.py`) - Handles Slack webhooks, OAuth flows, and status dashboard
- **Celery Worker** (`tasks.py`) - Processes Slack messages asynchronously using Claude Code CLI
- **Redis** - Message broker for Celery task queue
- **Credentials Manager** (`credentials.py`) - Stores encrypted OAuth tokens locally
- **Git Workspace Management** (`tasks.py:create_workspace`) - Uses `git worktree` for concurrent repository access

### Message Flow
1. Slack webhook receives message/mention → FastAPI endpoint
2. Message queued to Celery with reaction acknowledgment
3. Celery worker creates git worktree, downloads attachments, gathers thread context
4. Worker runs `claude -p "<prompt>"` with thread history and file attachments
5. Response sent back to Slack with completion reaction

### Key Architecture Decisions
- **Git Worktrees**: Multiple concurrent requests create isolated workspaces under `~/.claude-bot/repos/{owner-repo}/workspace-{timestamp}`
- **Thread Context**: Slack thread history is passed to Claude Code as conversation context
- **Async Processing**: All Claude Code execution happens in background Celery tasks
- **OAuth Integration**: Handles both Slack app installation and GitHub repository access

## Commands

### Development
- `make dev` - Start all services (Redis, FastAPI server, Celery worker)
- `make dev-debug` - Start with verbose Celery logging
- `make dev-docker` - Use Docker for Redis instead of local installation

### Individual Services  
- `make server` - Start only FastAPI server on port 8000
- `make worker` - Start only Celery worker
- `make worker-debug` - Start Celery worker with debug logging
- `make redis` - Start Redis server (port 6379)

### Setup
- `make install` or `uv sync` - Install dependencies
- `make clean` - Remove Python cache files and old workspaces

### Required Environment Variables
- `ANTHROPIC_API_KEY` - Claude API key
- `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET` - Slack app OAuth
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` - GitHub app OAuth (optional)

## Integration Points

The bot expects Claude Code CLI (`claude`) to be available in PATH. Commands are executed as:
```bash
claude -p "<prompt>" --append-system-prompt "<thread context instructions>"
```

Workspace operations use git worktree for safe concurrent access to the same repository.