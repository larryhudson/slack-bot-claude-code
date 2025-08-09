# Claude Code Slack Bot

A Slack bot that integrates Claude Code CLI with Slack workspaces to answer questions about GitHub repositories. Users can mention the bot in channels or send direct messages to get AI-powered assistance with their codebase.

## Architecture

The bot follows a distributed task processing pattern:

- **FastAPI Server** - Handles Slack webhooks, OAuth flows, and status dashboard
- **Celery Worker** - Processes Slack messages asynchronously using Claude Code CLI
- **Redis** - Message broker for Celery task queue
- **Git Workspace Management** - Uses `git worktree` for concurrent repository access

### Message Flow

1. Slack webhook receives message/mention → FastAPI endpoint
2. Message queued to Celery with reaction acknowledgment
3. Celery worker creates git worktree, downloads attachments, gathers thread context
4. Worker runs `claude -p "<prompt>"` with thread history and file attachments
5. Response sent back to Slack with completion reaction

## Prerequisites

### Required Software

- **Python 3.12+** - The project requires Python 3.12 or higher
- **UV Package Manager** - For dependency management (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Redis** - Message broker for background tasks
- **Claude Code CLI** - Must be available in PATH (`npm install -g @anthropic-ai/claude-code`)
- **Git** - For repository operations

### Redis Installation

**macOS (Homebrew):**

```bash
brew install redis
```

**Ubuntu/Debian:**

```bash
sudo apt install redis-server
```

**Docker Alternative:**

```bash
docker run -d --name redis -p 6379:6379 redis:alpine
```

### Required Environment Variables

Copy the example environment file and adapt it:

```bash
cp .env.example .env
```

Then edit `.env` with your actual values:

```env
# Claude API
ANTHROPIC_API_KEY=your_claude_api_key

# Slack App OAuth (required)
SLACK_CLIENT_ID=your_slack_client_id
SLACK_CLIENT_SECRET=your_slack_client_secret

# GitHub App OAuth (optional - for private repos)
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Install UV if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
make install
# or: uv sync
```

### 2. Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
```

### 3. Create Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click "Create New App" → "From an app manifest"
3. Select your workspace
4. Copy the contents of `slack-app-manifest.json` and paste it
5. Update the URLs in the manifest to match your development environment:
   - Replace `https://your-ngrok-url.ngrok.io` with your actual ngrok URL
6. Install the app to your workspace
7. Copy the Client ID and Client Secret to your `.env` file

### 4. Set Up Public URL (Development)

For local development, you need a public URL. Use ngrok:

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/

# Start ngrok tunnel
ngrok http 8000
```

Update your Slack app's request URLs with the ngrok URL.

### 5. GitHub Integration (Optional)

For private repository access:

1. Create a GitHub App at https://github.com/settings/apps
2. Set the callback URL to `https://your-ngrok-url.ngrok.io/github/callback`
3. Add the Client ID and Secret to your `.env` file

## Development Commands

### Start All Services

```bash
# Start Redis, FastAPI server, and Celery worker
make dev

# With debug logging
make dev-debug

# Using Docker for Redis
make dev-docker
```

### Individual Services

```bash
# Start only FastAPI server (port 8000)
make server

# Start only Celery worker
make worker

# Start Celery worker with debug logging
make worker-debug

# Start Redis server
make redis
```

### Maintenance

```bash
# Clean up temporary files and old workspaces
make clean

# Install/update dependencies
make install
```

## Project Structure

```
slack-bot-claude-code/
├── claude_bot/              # Main application package
│   ├── main.py              # FastAPI server with Slack webhooks
│   ├── tasks.py             # Celery worker tasks
│   ├── celery_app.py        # Celery configuration
│   ├── credentials.py       # Encrypted OAuth token storage
│   ├── slack_auth.py        # Slack OAuth flow
│   ├── github_auth.py       # GitHub OAuth flow
│   ├── slack_client.py      # Slack API client
│   └── markdown_converter.py # Convert Slack markup to markdown
├── Makefile                 # Development commands
├── pyproject.toml          # Python dependencies
├── slack-app-manifest.json # Slack app configuration
├── CLAUDE.md               # Claude Code instructions
└── README.md               # This file
```

## Usage

### In Slack Channels

Mention the bot with your question:

```
@Claude Code Bot what does the login function do?
@Claude Code Bot help me debug this error
```

### Direct Messages

Send a direct message to the bot:

```
explain the authentication flow
show me how to add a new API endpoint
```

### File Attachments

You can attach files or screenshots to your messages for context.

### Thread Conversations

The bot maintains context within Slack threads for follow-up questions.

## Configuration

The bot stores OAuth credentials in `credentials.json` (encrypted). Workspace management creates isolated git worktrees under `~/.claude-bot/repos/{owner-repo}/workspace-{timestamp}` for concurrent access.

## Troubleshooting

### Common Issues

**Redis Connection Error:**

- Ensure Redis is running: `redis-cli ping` should return "PONG"
- Check if Redis is on the correct port (6379)

**Claude Code CLI Not Found:**

- Verify installation: `which claude`
- Ensure it's in your PATH

**Slack App Not Responding:**

- Check that your ngrok URL is up to date in the Slack app settings
- Verify webhook URLs are correct
- Check server logs for errors

**Permission Errors:**

- Ensure the Slack app has the required scopes
- Check that the bot is invited to channels where it should respond

### Debug Mode

Use debug mode for detailed logging:

```bash
make dev-debug
```

This provides verbose Celery logging to help diagnose issues.

## Contributing

1. Follow the existing code style
2. Test your changes with `make dev`
3. Update documentation if needed
4. Ensure all services start without errors

## License

MIT