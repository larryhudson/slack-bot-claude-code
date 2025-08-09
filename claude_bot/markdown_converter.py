"""
Convert Markdown to Slack's mrkdwn format for rich text display
"""
import re
from markdown_to_mrkdwn import SlackMarkdownConverter

# Create a global converter instance
converter = SlackMarkdownConverter()


def markdown_to_slack(text: str) -> str:
    """Convert Markdown to Slack mrkdwn format using the markdown-to-mrkdwn package"""
    try:
        return converter.convert(text)
    except Exception as e:
        print(f"Error converting markdown: {e}")
        return text  # Fallback to original text if conversion fails


def should_use_blocks(text: str) -> bool:
    """Determine if the text is complex enough to warrant Block Kit formatting"""
    # Use blocks for messages with code blocks, lists, or long content
    has_code_blocks = '```' in text
    has_lists = bool(re.search(r'^[\s]*[-*+•] ', text, re.MULTILINE))
    is_long = len(text) > 1000
    
    print(f"DEBUG: should_use_blocks - code_blocks: {has_code_blocks}, lists: {has_lists}, long: {is_long}")
    return has_code_blocks or has_lists or is_long


def create_slack_blocks(text: str):
    """Create Slack Block Kit blocks for complex formatting"""
    blocks = []
    
    # Split text by code blocks and regular text
    parts = re.split(r'(```[\s\S]*?```)', text)
    
    for part in parts:
        if not part.strip():
            continue
            
        if part.startswith('```') and part.endswith('```'):
            # Code block
            code_content = part[3:-3].strip()
            
            # Extract language if specified
            lines = code_content.split('\n', 1)
            if lines[0] and not ' ' in lines[0] and len(lines) > 1:
                code_content = lines[1]
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{code_content}```"
                }
            })
        else:
            # Regular text - convert to mrkdwn
            mrkdwn_text = markdown_to_slack(part)
            if mrkdwn_text.strip():
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": mrkdwn_text
                    }
                })
    
    return blocks