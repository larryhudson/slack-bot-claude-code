import os
import httpx
from urllib.parse import urlencode
from typing import Optional, Dict, Any

# Slack OAuth configuration - these should be set as environment variables
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI", "http://localhost:8000/slack/callback")

# Slack OAuth scopes needed for the bot
SLACK_SCOPES = "chat:write,files:read,channels:read,groups:read,im:read,mpim:read"

class SlackOAuth:
    """Handle Slack OAuth authentication flow"""
    
    def __init__(self):
        if not SLACK_CLIENT_ID or not SLACK_CLIENT_SECRET:
            print("WARNING: SLACK_CLIENT_ID and SLACK_CLIENT_SECRET must be set as environment variables")
    
    def get_install_url(self) -> Optional[str]:
        """Generate Slack OAuth installation URL"""
        if not SLACK_CLIENT_ID:
            return None
        
        params = {
            'client_id': SLACK_CLIENT_ID,
            'scope': SLACK_SCOPES,
            'redirect_uri': SLACK_REDIRECT_URI
        }
        
        return f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"
    
    async def handle_callback(self, code: str) -> Optional[Dict[str, Any]]:
        """Handle OAuth callback and exchange code for tokens"""
        if not SLACK_CLIENT_ID or not SLACK_CLIENT_SECRET:
            return None
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://slack.com/api/oauth.v2.access",
                    data={
                        'client_id': SLACK_CLIENT_ID,
                        'client_secret': SLACK_CLIENT_SECRET,
                        'code': code,
                        'redirect_uri': SLACK_REDIRECT_URI
                    }
                )
                
                result = response.json()
                
                if result.get('ok'):
                    return {
                        'access_token': result['access_token'],
                        'bot_token': result['access_token'],  # In OAuth v2, this is the bot token
                        'team_id': result['team']['id'],
                        'team_name': result['team']['name'],
                        'bot_user_id': result['bot_user_id']
                    }
                else:
                    print(f"Slack OAuth error: {result.get('error')}")
                    return None
                    
            except Exception as e:
                print(f"Error during Slack OAuth: {e}")
                return None
    
    async def test_connection(self, bot_token: str) -> bool:
        """Test if the bot token is valid"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={'Authorization': f'Bearer {bot_token}'}
                )
                
                result = response.json()
                return result.get('ok', False)
                
            except Exception as e:
                print(f"Error testing Slack connection: {e}")
                return False

# Global Slack OAuth handler
slack_oauth = SlackOAuth()