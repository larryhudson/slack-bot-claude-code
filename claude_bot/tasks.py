import asyncio
import shutil
import subprocess
import os
from pathlib import Path
from typing import Dict, Any
from .celery_app import celery_app
from .slack_client import slack_client
from .credentials import credentials_manager


@celery_app.task(bind=True)
def process_slack_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a Slack message with Claude Code CLI in the background"""
    workspace_dir = None

    try:
        # Update task status
        self.update_state(state="PROGRESS", meta={"status": "Starting processing"})

        # Validate inputs
        if not message_data.get("text", "").strip():
            raise Exception("No message text provided")

        # Get GitHub credentials
        github_creds = credentials_manager.get_github_credentials()
        if not github_creds:
            raise Exception(
                "GitHub repository not connected. Please connect a repository first."
            )

        # Create workspace
        self.update_state(state="PROGRESS", meta={"status": "Setting up workspace"})
        workspace_dir = create_workspace(github_creds["repository"])

        self.update_state(
            state="PROGRESS",
            meta={"status": f"Repository {github_creds['repository']} prepared"},
        )

        # Download attachments if any
        attachment_paths = []
        if message_data.get("files"):
            self.update_state(
                state="PROGRESS", meta={"status": "Downloading attachments"}
            )
            attachment_paths = asyncio.run(
                download_attachments(message_data["files"], workspace_dir)
            )
            if attachment_paths:
                self.update_state(
                    state="PROGRESS",
                    meta={"status": f"{len(attachment_paths)} attachments downloaded"},
                )

        # Get thread history for context if this is a follow-up
        thread_history = []
        if message_data.get("thread_ts"):
            # Always try to get thread history - let the slack client determine if there are previous messages
            self.update_state(
                state="PROGRESS", meta={"status": "Gathering thread context"}
            )
            thread_history = asyncio.run(
                slack_client.get_thread_history(
                    message_data["channel"], message_data["thread_ts"]
                )
            )
            print(f"DEBUG: Thread history: {len(thread_history)} messages found")
            for i, msg in enumerate(thread_history):
                speaker = "Bot" if msg.get("is_bot") else "User"
                print(f"DEBUG: Message {i + 1}: {speaker}: {msg['text'][:50]}...")

        # Run Claude Code CLI
        self.update_state(
            state="PROGRESS", meta={"status": "Running Claude Code analysis"}
        )

        claude_result = run_claude_code(
            workspace_dir, message_data["text"], attachment_paths, thread_history
        )

        # Send response back to Slack
        asyncio.run(send_slack_response(message_data, claude_result))

        # Add completion reaction
        asyncio.run(
            slack_client.add_reaction(
                message_data["channel"], message_data["timestamp"], "white_check_mark"
            )
        )

        return {
            "status": "completed",
            "result": claude_result[:500] + "..."
            if len(claude_result) > 500
            else claude_result,
        }

    except subprocess.CalledProcessError as e:
        error_msg = (
            f"❌ Git operation failed: {e.stderr.decode() if e.stderr else str(e)}"
        )
        asyncio.run(send_error_response(message_data, error_msg))

        self.update_state(
            state="FAILURE", meta={"status": "Git error", "error": str(e)}
        )
        raise

    except Exception as e:
        # Send error message to Slack
        error_msg = f"❌ I encountered an error: {str(e)}"
        asyncio.run(send_error_response(message_data, error_msg))

        self.update_state(state="FAILURE", meta={"status": "Failed", "error": str(e)})
        raise

    finally:
        # Always cleanup workspace
        if workspace_dir:
            try:
                cleanup_workspace(workspace_dir)
            except Exception as e:
                print(f"Cleanup error: {e}")


def create_workspace(repository: str) -> str:
    """Create a workspace using git worktree for concurrent requests"""
    import time

    # Base directory for all git operations
    base_git_dir = Path.home() / ".claude-bot" / "repos" / repository.replace("/", "-")
    base_git_dir.mkdir(parents=True, exist_ok=True)

    # Main repository path
    main_repo_path = base_git_dir / "main"

    # Clone or update the main repository
    if not main_repo_path.exists():
        clone_url = f"https://github.com/{repository}.git"
        subprocess.run(
            ["git", "clone", clone_url, str(main_repo_path)],
            check=True,
            capture_output=True,
        )
    else:
        # Update existing repo
        subprocess.run(
            ["git", "fetch", "--all"],
            cwd=main_repo_path,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "reset", "--hard", "origin/main"],
            cwd=main_repo_path,
            check=True,
            capture_output=True,
        )

    # Create a worktree for this request
    timestamp = int(time.time())
    branch_name = f"claude-request-{timestamp}"
    worktree_path = base_git_dir / f"workspace-{timestamp}"

    subprocess.run(
        ["git", "worktree", "add", "-b", branch_name, str(worktree_path), "HEAD"],
        cwd=main_repo_path,
        check=True,
        capture_output=True,
    )

    return str(worktree_path)


async def download_attachments(files: list, workspace_dir: str) -> list:
    """Download Slack message attachments to workspace"""
    attachment_paths = []

    for file_info in files:
        if file_info.get("url_private_download"):
            file_name = file_info.get("name", f"attachment_{file_info.get('id')}")
            file_path = os.path.join(workspace_dir, file_name)

            success = await slack_client.download_file(
                file_info["url_private_download"], file_path
            )
            if success:
                attachment_paths.append(file_path)

    return attachment_paths


CLAUDE_SYSTEM_PROMPT = "You have received a request in a Slack thread. You may be given a list of previous messages in the thread. Use the thread history to continue the conversation in a natural way."


def run_claude_code(
    workspace_dir: str, prompt: str, attachment_paths: list, thread_history: list = None
) -> str:
    """Run Claude Code CLI in the workspace directory"""
    # Change to workspace directory
    original_cwd = os.getcwd()
    os.chdir(workspace_dir)

    try:
        # Create full prompt with context and attachment references
        full_prompt = prompt

        # Add thread history context if this is a follow-up message
        if thread_history and len(thread_history) > 1:
            context = "\n\nPrevious conversation in this Slack thread:\n"
            for msg in thread_history[
                :-1
            ]:  # Exclude current message (which should be the last one)
                speaker = "Assistant" if msg.get("is_bot") else "User"
                context += f"{speaker}: {msg['text']}\n"
            full_prompt = context + "\nCurrent question: " + prompt

        # Add attachment references
        if attachment_paths:
            attachment_refs = "\n\nAttached files:\n" + "\n".join(
                [f"- {path}" for path in attachment_paths]
            )
            full_prompt += attachment_refs

        # Debug: log the full prompt being sent to Claude
        print("DEBUG: Full prompt being sent to Claude:")
        print("=" * 50)
        print(full_prompt)
        print("=" * 50)

        # Build the claude-code command - use interactive mode with prompt
        cmd = [
            "claude",
            "-p",
            full_prompt,
            "--append-system-prompt",
            CLAUDE_SYSTEM_PROMPT,
        ]

        # Set environment for Claude Code
        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY", "")

        # Run Claude Code CLI
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            env=env,
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            # Limit response length for Slack
            if len(output) > 4000:
                output = output[:3900] + "\n\n... (response truncated for Slack)"
            return output if output else "Claude Code completed but returned no output."
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return f"Claude Code execution failed: {error_msg}"

    except subprocess.TimeoutExpired:
        return "⏰ Claude Code execution timed out after 5 minutes. Your request may be too complex or the repository too large."
    except FileNotFoundError:
        return "❌ Claude Code CLI not found. Please ensure it's installed and in your PATH."
    except Exception as e:
        return f"❌ Error running Claude Code: {str(e)}"
    finally:
        os.chdir(original_cwd)


def cleanup_workspace(workspace_dir: str):
    """Clean up the git worktree workspace"""
    try:
        workspace_path = Path(workspace_dir)

        # Get the base repo directory and worktree info
        base_git_dir = workspace_path.parent
        main_repo_path = base_git_dir / "main"

        # Remove the git worktree
        subprocess.run(
            ["git", "worktree", "remove", workspace_dir, "--force"],
            cwd=main_repo_path,
            capture_output=True,
        )

        # Clean up any remaining files
        if workspace_path.exists():
            shutil.rmtree(workspace_dir)

    except Exception as e:
        print(f"Warning: Failed to cleanup workspace {workspace_dir}: {e}")


async def send_slack_response(message_data: Dict[str, Any], response_text: str):
    """Send response back to Slack"""
    try:
        await slack_client.send_message(
            message_data["channel"],
            response_text,
            thread_ts=message_data.get("thread_ts"),
        )
    except Exception as e:
        print(f"Failed to send Slack response: {e}")


async def send_error_response(message_data: Dict[str, Any], error_text: str):
    """Send error response and add error reaction"""
    try:
        # Send error message
        await slack_client.send_message(
            message_data["channel"], error_text, thread_ts=message_data.get("thread_ts")
        )

        # Add error reaction
        await slack_client.add_reaction(
            message_data["channel"], message_data["timestamp"], "x"
        )
    except Exception as e:
        print(f"Failed to send error response: {e}")
