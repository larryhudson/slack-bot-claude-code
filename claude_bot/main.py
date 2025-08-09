from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
from dotenv import load_dotenv
from .credentials import credentials_manager
from .slack_auth import slack_oauth
from .github_auth import github_oauth
from .slack_client import slack_client
from .tasks import process_slack_message

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Slack Bot Claude Code", version="0.1.0")

@app.get("/", response_class=HTMLResponse)
async def status_dashboard():
    """Simple HTML status dashboard"""
    slack_connected = credentials_manager.is_slack_connected()
    github_connected = credentials_manager.is_github_connected()
    
    slack_status = "✅ Connected" if slack_connected else "❌ Not Connected"
    slack_class = "connected" if slack_connected else "disconnected"
    slack_button = "" if slack_connected else '<a href="/slack/install" class="button">Install Slack App</a>'
    
    github_creds = credentials_manager.get_github_credentials()
    if github_connected and github_creds:
        github_status = f"✅ Connected to {github_creds['repository']}"
    else:
        github_status = "❌ Not Connected"
    github_class = "connected" if github_connected else "disconnected"
    github_button = "" if github_connected else '<a href="/github/install" class="button">Install GitHub App</a>'
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Slack Bot Claude Code Status</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .status {{ margin: 20px 0; }}
            .connected {{ color: green; }}
            .disconnected {{ color: red; }}
            .button {{ 
                display: inline-block; 
                padding: 10px 20px; 
                background: #4CAF50; 
                color: white; 
                text-decoration: none; 
                border-radius: 4px; 
                margin: 10px 5px;
            }}
        </style>
    </head>
    <body>
        <h1>Slack Bot Claude Code Status</h1>
        <div class="status">
            <h3>Slack Connection</h3>
            <span class="{slack_class}">{slack_status}</span>
            {slack_button}
        </div>
        <div class="status">
            <h3>GitHub Connection</h3>
            <span class="{github_class}">{github_status}</span>
            {github_button}
        </div>
    </body>
    </html>
    """
    return html_content

@app.post("/slack/webhook")
async def slack_webhook(request: Request):
    """Handle incoming Slack messages"""
    body = await request.json()
    
    # Handle URL verification challenge
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}
    
    # Handle actual events
    if body.get("type") == "event_callback":
        event = body.get("event", {})
        event_type = event.get("type")
        
        if event_type in ["app_mention", "message"]:
            # Skip bot's own messages and messages with subtypes (like file uploads without text)
            if event.get("bot_id") or event.get("subtype"):
                return {"status": "ignored"}
                
            # For DMs, process all messages. For channels, only process @mentions
            channel_type = event.get("channel_type", "")
            is_dm = channel_type == "im"
            is_mention = event_type == "app_mention"
            
            if is_dm or is_mention:
                # Parse the message
                message_data = slack_client.parse_message_event(event)
                print(f"Received {event_type} in {channel_type}: {message_data['text']}")
                
                # Add eyes emoji to acknowledge receipt
                reaction_success = await slack_client.add_reaction(
                    message_data['channel'], 
                    message_data['timestamp'], 
                    'eyes'
                )
                print(f"Reaction added successfully: {reaction_success}")
                
                # Process message in background with Celery
                task = process_slack_message.delay(message_data)
                print(f"Started background task: {task.id}")
                
                return {"status": "received"}
    
    return {"status": "ignored"}

@app.get("/slack/install")
async def slack_install():
    """Redirect to Slack OAuth installation"""
    install_url = slack_oauth.get_install_url()
    if install_url:
        return RedirectResponse(url=install_url)
    else:
        return {"error": "Slack OAuth not configured. Set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET environment variables."}

@app.get("/slack/callback")
async def slack_callback(code: str = Query(...), state: str = Query(None)):
    """Handle Slack OAuth callback"""
    oauth_result = await slack_oauth.handle_callback(code)
    
    if oauth_result:
        # Store credentials
        credentials_manager.set_slack_credentials(
            access_token=oauth_result['access_token'],
            bot_token=oauth_result['bot_token'], 
            team_id=oauth_result['team_id']
        )
        
        # Redirect to status page
        return RedirectResponse(url="/", status_code=302)
    else:
        return {"error": "Failed to complete Slack OAuth flow"}

@app.get("/github/install") 
async def github_install():
    """Redirect to GitHub App installation"""
    install_url = github_oauth.get_install_url()
    if install_url:
        return RedirectResponse(url=install_url)
    else:
        return {"error": "GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables."}

@app.get("/github/callback")
async def github_callback(code: str = Query(...)):
    """Handle GitHub OAuth callback"""
    oauth_result = await github_oauth.handle_callback(code)
    
    if oauth_result and oauth_result['repositories']:
        # Store OAuth result temporarily in credentials manager
        credentials_manager._temp_github_oauth = oauth_result
        
        # Redirect to repository selection page
        return RedirectResponse(url="/github/select-repository", status_code=302)
    else:
        return {"error": "Failed to complete GitHub OAuth flow or no repositories found"}

@app.get("/github/select-repository", response_class=HTMLResponse)
async def github_select_repository():
    """Show repository selection page"""
    # Get temporary OAuth result
    oauth_result = getattr(credentials_manager, '_temp_github_oauth', None)
    
    if not oauth_result or not oauth_result.get('repositories'):
        return RedirectResponse(url="/github/install", status_code=302)
    
    repositories = oauth_result['repositories']
    
    # Generate repository options HTML
    repo_options = ""
    for repo in repositories:
        repo_options += f'''
            <div class="repo-option">
                <input type="radio" id="{repo['full_name']}" name="repository" value="{repo['full_name']}" required>
                <label for="{repo['full_name']}">
                    <strong>{repo['full_name']}</strong>
                    {f"- {repo['description']}" if repo.get('description') else ""}
                    <small>({repo.get('visibility', 'private')})</small>
                </label>
            </div>
        '''
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Select Repository - Slack Bot Claude Code</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 800px; }}
            .repo-option {{ margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 8px; }}
            .repo-option:hover {{ background-color: #f5f5f5; }}
            .repo-option label {{ display: block; cursor: pointer; margin-left: 25px; }}
            .repo-option input[type="radio"] {{ margin-right: 10px; }}
            .button {{ 
                display: inline-block; 
                padding: 12px 24px; 
                background: #4CAF50; 
                color: white; 
                text-decoration: none; 
                border: none;
                border-radius: 4px; 
                cursor: pointer;
                font-size: 16px;
            }}
            .button:hover {{ background: #45a049; }}
            small {{ color: #666; }}
        </style>
    </head>
    <body>
        <h1>Select Repository</h1>
        <p>Choose which repository you want to connect to your Slack bot:</p>
        
        <form action="/github/confirm-repository" method="post">
            {repo_options}
            <br>
            <button type="submit" class="button">Connect Repository</button>
        </form>
        
        <p><a href="/github/install">← Back to GitHub installation</a></p>
    </body>
    </html>
    """
    return html_content

@app.post("/github/confirm-repository")
async def github_confirm_repository(request: Request):
    """Handle repository selection confirmation"""
    form_data = await request.form()
    selected_repo = form_data.get("repository")
    
    # Get temporary OAuth result
    oauth_result = getattr(credentials_manager, '_temp_github_oauth', None)
    
    if not oauth_result or not selected_repo:
        return RedirectResponse(url="/github/install", status_code=302)
    
    # Store credentials with selected repository
    credentials_manager.set_github_credentials(
        installation_id=str(oauth_result['user_id']),
        access_token=oauth_result['access_token'],
        repository=selected_repo
    )
    
    # Clean up temporary OAuth result
    if hasattr(credentials_manager, '_temp_github_oauth'):
        delattr(credentials_manager, '_temp_github_oauth')
    
    # Redirect to status page
    return RedirectResponse(url="/", status_code=302)

def main():
    uvicorn.run("claude_bot.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
