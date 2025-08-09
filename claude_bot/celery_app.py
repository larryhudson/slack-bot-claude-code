from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

# Redis connection for Celery broker and backend
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'claude_bot',
    broker=redis_url,
    backend=redis_url,
    include=['claude_bot.tasks']
)

# Configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # Result expires after 1 hour
    result_expires=3600,
)