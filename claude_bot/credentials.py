import json
import os
from typing import Optional, Dict, Any
from pathlib import Path

CREDENTIALS_FILE = "credentials.json"

class CredentialsManager:
    """Manage OAuth credentials stored in local JSON file"""
    
    def __init__(self, credentials_file: str = CREDENTIALS_FILE):
        self.credentials_file = Path(credentials_file)
        self._credentials = self._load_credentials()
    
    def _load_credentials(self) -> Dict[str, Any]:
        """Load credentials from JSON file"""
        if self.credentials_file.exists():
            try:
                with open(self.credentials_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_credentials(self):
        """Save credentials to JSON file"""
        with open(self.credentials_file, 'w') as f:
            json.dump(self._credentials, f, indent=2)
    
    def get_slack_credentials(self) -> Optional[Dict[str, str]]:
        """Get Slack OAuth credentials"""
        # Reload credentials to get the latest data
        self._credentials = self._load_credentials()
        return self._credentials.get('slack')
    
    def set_slack_credentials(self, access_token: str, bot_token: str, team_id: str):
        """Store Slack OAuth credentials"""
        self._credentials['slack'] = {
            'access_token': access_token,
            'bot_token': bot_token,
            'team_id': team_id
        }
        self._save_credentials()
    
    def get_github_credentials(self) -> Optional[Dict[str, str]]:
        """Get GitHub OAuth credentials"""
        # Reload credentials to get the latest data
        self._credentials = self._load_credentials()
        return self._credentials.get('github')
    
    def set_github_credentials(self, installation_id: str, access_token: str, repository: str):
        """Store GitHub OAuth credentials"""
        self._credentials['github'] = {
            'installation_id': installation_id,
            'access_token': access_token,
            'repository': repository
        }
        self._save_credentials()
    
    def is_slack_connected(self) -> bool:
        """Check if Slack is properly configured"""
        slack_creds = self.get_slack_credentials()
        return slack_creds is not None and all(
            key in slack_creds for key in ['access_token', 'bot_token', 'team_id']
        )
    
    def is_github_connected(self) -> bool:
        """Check if GitHub is properly configured"""
        # Reload credentials to get the latest data
        self._credentials = self._load_credentials()
        github_creds = self._credentials.get('github')
        return github_creds is not None and all(
            key in github_creds for key in ['installation_id', 'access_token', 'repository']
        )
    
    def clear_credentials(self):
        """Clear all stored credentials"""
        self._credentials = {}
        self._save_credentials()

# Global credentials manager instance
credentials_manager = CredentialsManager()