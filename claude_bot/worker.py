#!/usr/bin/env python3
"""
Celery worker startup script for the Slack bot
"""
from .celery_app import celery_app

if __name__ == '__main__':
    celery_app.start()