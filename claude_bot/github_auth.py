import os
import httpx
from urllib.parse import urlencode
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GitHub App configuration - these should be set as environment variables
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/github/callback")

class GitHubOAuth:
    """Handle GitHub App OAuth authentication flow"""
    
    def __init__(self):
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            print("WARNING: GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set as environment variables")
    
    def get_install_url(self) -> Optional[str]:
        """Generate GitHub App installation URL"""
        if not GITHUB_CLIENT_ID:
            return None
        
        params = {
            'client_id': GITHUB_CLIENT_ID,
            'redirect_uri': GITHUB_REDIRECT_URI,
            'scope': 'repo'  # Need repo access to clone and read files
        }
        
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    
    async def handle_callback(self, code: str) -> Optional[Dict[str, Any]]:
        """Handle OAuth callback and exchange code for tokens"""
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            return None
        
        async with httpx.AsyncClient() as client:
            try:
                # Exchange code for access token
                response = await client.post(
                    "https://github.com/login/oauth/access_token",
                    data={
                        'client_id': GITHUB_CLIENT_ID,
                        'client_secret': GITHUB_CLIENT_SECRET,
                        'code': code,
                        'redirect_uri': GITHUB_REDIRECT_URI
                    },
                    headers={'Accept': 'application/json'}
                )
                
                token_data = response.json()
                
                if 'access_token' in token_data:
                    access_token = token_data['access_token']
                    
                    # Get user info to verify the token works
                    user_response = await client.get(
                        "https://api.github.com/user",
                        headers={'Authorization': f'Bearer {access_token}'}
                    )
                    
                    if user_response.status_code == 200:
                        user_data = user_response.json()
                        
                        # Get user's repositories
                        repos_response = await client.get(
                            "https://api.github.com/user/repos",
                            headers={'Authorization': f'Bearer {access_token}'},
                            params={'per_page': 100, 'sort': 'updated'}
                        )
                        
                        repos = repos_response.json() if repos_response.status_code == 200 else []
                        
                        return {
                            'access_token': access_token,
                            'user_id': user_data['id'],
                            'username': user_data['login'],
                            'repositories': repos
                        }
                    
                return None
                    
            except Exception as e:
                print(f"Error during GitHub OAuth: {e}")
                return None
    
    async def test_connection(self, access_token: str) -> bool:
        """Test if the access token is valid"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.github.com/user",
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                
                return response.status_code == 200
                
            except Exception as e:
                print(f"Error testing GitHub connection: {e}")
                return False
    
    async def clone_repository(self, repo_url: str, access_token: str, local_path: str) -> bool:
        """Clone a repository using the access token"""
        import subprocess
        import shutil
        
        try:
            # Remove existing directory if it exists
            if os.path.exists(local_path):
                shutil.rmtree(local_path)
            
            # Clone with authentication
            auth_url = repo_url.replace('https://github.com/', f'https://{access_token}@github.com/')
            
            result = subprocess.run(
                ['git', 'clone', auth_url, local_path],
                capture_output=True,
                text=True
            )
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Error cloning repository: {e}")
            return False

# Global GitHub OAuth handler
github_oauth = GitHubOAuth()