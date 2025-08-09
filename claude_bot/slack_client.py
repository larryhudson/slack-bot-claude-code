import httpx
from typing import Optional, Dict, Any, List
from .credentials import credentials_manager
from .markdown_converter import markdown_to_slack, should_use_blocks, create_slack_blocks

class SlackClient:
    """Handle sending messages and responses to Slack"""
    
    def __init__(self):
        self.base_url = "https://slack.com/api"
    
    def _get_bot_token(self) -> Optional[str]:
        """Get bot token from credentials"""
        slack_creds = credentials_manager.get_slack_credentials()
        return slack_creds.get('bot_token') if slack_creds else None
    
    async def send_message(self, channel: str, text: str, thread_ts: str = None, use_rich_text: bool = True) -> bool:
        """Send a message to a Slack channel with optional rich text formatting"""
        bot_token = self._get_bot_token()
        if not bot_token:
            print("No Slack bot token available")
            return False
        
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    'channel': channel,
                }
                
                if thread_ts:
                    payload['thread_ts'] = thread_ts
                
                # Decide on formatting approach
                if use_rich_text and should_use_blocks(text):
                    # Use Block Kit for complex formatting
                    print("DEBUG: Using Block Kit formatting")
                    blocks = create_slack_blocks(text)
                    payload['blocks'] = blocks
                    payload['text'] = text  # Fallback text for notifications
                elif use_rich_text:
                    # Use mrkdwn for simple formatting
                    print("DEBUG: Using mrkdwn formatting")
                    converted_text = markdown_to_slack(text)
                    payload['text'] = converted_text
                    payload['mrkdwn'] = True
                    print(f"DEBUG: Original: {text[:100]}...")
                    print(f"DEBUG: Converted: {converted_text[:100]}...")
                else:
                    # Plain text
                    print("DEBUG: Using plain text")
                    payload['text'] = text
                
                response = await client.post(
                    f"{self.base_url}/chat.postMessage",
                    headers={'Authorization': f'Bearer {bot_token}'},
                    json=payload
                )
                
                result = response.json()
                if not result.get('ok'):
                    print(f"Slack API error: {result.get('error')}")
                    return False
                
                return True
                
            except Exception as e:
                print(f"Error sending Slack message: {e}")
                return False
    
    async def add_reaction(self, channel: str, timestamp: str, emoji: str) -> bool:
        """Add an emoji reaction to a message"""
        bot_token = self._get_bot_token()
        if not bot_token:
            print("No bot token available for reaction")
            return False
        
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    'channel': channel,
                    'timestamp': timestamp,
                    'name': emoji
                }
                print(f"Adding reaction {emoji} to message {timestamp} in channel {channel}")
                
                response = await client.post(
                    f"{self.base_url}/reactions.add",
                    headers={'Authorization': f'Bearer {bot_token}'},
                    json=payload
                )
                
                result = response.json()
                print(f"Reaction API response: {result}")
                
                if not result.get('ok'):
                    print(f"Slack reaction API error: {result.get('error')}")
                    return False
                
                return True
                
            except Exception as e:
                print(f"Error adding reaction: {e}")
                return False
    
    async def get_thread_history(self, channel: str, thread_ts: str) -> list:
        """Get the conversation history of a thread"""
        bot_token = self._get_bot_token()
        if not bot_token:
            return []
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/conversations.replies",
                    headers={'Authorization': f'Bearer {bot_token}'},
                    params={
                        'channel': channel,
                        'ts': thread_ts,
                        'limit': 10  # Last 10 messages in thread
                    }
                )
                
                result = response.json()
                if result.get('ok'):
                    messages = result.get('messages', [])
                    # Format messages as conversation history
                    history = []
                    for msg in messages:
                        if msg.get('text'):
                            # Include both user and bot messages for full context
                            is_bot = msg.get('bot_id') is not None
                            history.append({
                                'user': msg.get('user'),
                                'text': msg.get('text'),
                                'ts': msg.get('ts'),
                                'is_bot': is_bot
                            })
                    return history
                
                return []
                
            except Exception as e:
                print(f"Error fetching thread history: {e}")
                return []

    async def download_file(self, file_url: str, file_path: str) -> bool:
        """Download a file from Slack"""
        bot_token = self._get_bot_token()
        if not bot_token:
            return False
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    file_url,
                    headers={'Authorization': f'Bearer {bot_token}'}
                )
                
                if response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    return True
                
                return False
                
            except Exception as e:
                print(f"Error downloading file: {e}")
                return False
    
    def parse_message_event(self, event: Dict[str, Any]) -> Dict[str, str]:
        """Parse a Slack message event into useful components"""
        # If there's no thread_ts, use the message timestamp to start a new thread
        thread_ts = event.get('thread_ts') or event.get('ts')
        
        return {
            'user_id': event.get('user', ''),
            'channel': event.get('channel', ''),
            'text': event.get('text', ''),
            'timestamp': event.get('ts', ''),
            'thread_ts': thread_ts,
            'files': event.get('files', [])
        }

# Global Slack client instance
slack_client = SlackClient()