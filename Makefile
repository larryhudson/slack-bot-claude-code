.PHONY: dev worker server redis clean help

# Default Python command
PYTHON := python3

# Default target
help:
	@echo "Available commands:"
	@echo "  make dev     - Start all services (Redis, FastAPI server, Celery worker)"
	@echo "  make server  - Start only the FastAPI server"
	@echo "  make worker  - Start only the Celery worker"
	@echo "  make redis   - Start Redis server"
	@echo "  make clean   - Clean up temporary files and workspaces"
	@echo "  make install - Install dependencies with uv"

# Install dependencies
install:
	uv sync

# Start Redis server
redis:
	@echo "Starting Redis server..."
	@if command -v redis-server >/dev/null 2>&1; then \
		redis-server --daemonize yes --port 6379; \
		echo "Redis started on port 6379"; \
	else \
		echo "Redis not found. Install with:"; \
		echo "  macOS: brew install redis"; \
		echo "  Ubuntu: sudo apt install redis-server"; \
		echo "  Or use Docker: docker run -d -p 6379:6379 redis:alpine"; \
		exit 1; \
	fi

# Start FastAPI server
server:
	@echo "Starting FastAPI server..."
	$(PYTHON) -m uvicorn claude_bot.main:app --host 0.0.0.0 --port 8000 --reload

# Start Celery worker
worker:
	@echo "Starting Celery worker..."
	$(PYTHON) -m celery -A claude_bot.celery_app worker --loglevel=info --concurrency=2

# Debug worker with more verbose output
worker-debug:
	@echo "Starting Celery worker with debug logging..."
	$(PYTHON) -m celery -A claude_bot.celery_app worker --loglevel=debug --concurrency=1

# Start all services for development
dev:
	@echo "Starting development environment..."
	@echo "This will start Redis, FastAPI server, and Celery worker"
	@echo "Press Ctrl+C to stop all services"
	@make redis
	@sleep 2
	@echo "Starting services in parallel..."
	@trap 'kill 0' SIGINT; \
	make server & \
	make worker & \
	wait

# Debug development with verbose logging
dev-debug:
	@echo "Starting development environment with debug logging..."
	@echo "This will start Redis, FastAPI server, and Celery worker (debug mode)"
	@echo "Press Ctrl+C to stop all services"
	@make redis
	@sleep 2
	@echo "Starting services in parallel..."
	@trap 'kill 0' SIGINT; \
	make server & \
	make worker-debug & \
	wait

# Alternative dev mode without Redis dependency check
dev-docker:
	@echo "Starting with Docker Redis..."
	@docker run -d --name claude-bot-redis -p 6379:6379 redis:alpine || echo "Redis container already running"
	@sleep 2
	@echo "Starting services in parallel..."
	@trap 'kill 0' SIGINT; \
	make server & \
	make worker & \
	wait

# Clean up temporary files and workspaces
clean:
	@echo "Cleaning up..."
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	rm -rf ~/.claude-bot/repos/*/workspace-* 2>/dev/null || true
	@echo "Cleanup complete"

# Stop Redis
stop-redis:
	@echo "Stopping Redis..."
	redis-cli shutdown 2>/dev/null || echo "Redis was not running"