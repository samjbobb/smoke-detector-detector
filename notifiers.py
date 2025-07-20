#!/usr/bin/env -S uv run --script
"""
Notification system for smoke alarm detection.
Provides a framework for sending alerts through various channels.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List
import time
import logging
import asyncio
import requests
from dataclasses import dataclass


@dataclass
class DetectionEvent:
    """Data structure for detection events to be sent to notifiers."""
    timestamp: float
    frequency: float
    strength: float
    confidence: float
    detection_type: str


class BaseNotifier(ABC):
    """Base abstract class for all notification implementations."""
    
    def __init__(self, name: str, enabled: bool = True, max_retries: int = 3, retry_delay: float = 1.0):
        self.name = name
        self.enabled = enabled
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logging.getLogger(f"notifier.{name}")
    
    @abstractmethod
    async def send_notification(self, event: DetectionEvent, is_test: bool = False) -> bool:
        """Send notification for detection event. Returns True on success."""
        pass
    
    async def notify_with_retry(self, event: DetectionEvent, is_test: bool = False) -> bool:
        """Send notification with retry logic."""
        if not self.enabled:
            self.logger.debug(f"Notifier {self.name} is disabled, skipping")
            return True
            
        for attempt in range(self.max_retries + 1):
            try:
                success = await self.send_notification(event, is_test)
                if success:
                    if attempt > 0:
                        self.logger.info(f"Notification sent successfully on attempt {attempt + 1}")
                    return True
                else:
                    self.logger.warning(f"Notification failed on attempt {attempt + 1}")
            except Exception as e:
                self.logger.error(f"Notification attempt {attempt + 1} failed: {e}")
            
            if attempt < self.max_retries:
                delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                self.logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)
        
        self.logger.error(f"All {self.max_retries + 1} notification attempts failed")
        return False


class NtfyNotifier(BaseNotifier):
    """Notifier that sends alerts via ntfy.sh service."""
    
    def __init__(self, topic: str, server: str = "https://ntfy.sh", **kwargs):
        super().__init__("ntfy", **kwargs)
        self.topic = topic
        self.server = server.rstrip('/')
        self.url = f"{self.server}/{self.topic}"
    
    async def send_notification(self, event: DetectionEvent, is_test: bool = False) -> bool:
        """Send notification via ntfy.sh."""
        title = "SMOKE ALARM DETECTED!"
        message = (
            f"Frequency: {event.frequency:.1f} Hz\n"
            f"Signal Strength: {event.strength:.2f}\n"
            f"Confidence: {event.confidence:.2%}\n"
            f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp))}"
        )
        if is_test:
            title = "TEST: " + title

        
        headers = {
            "Title": title,
            "Priority": "5",
            "Tags": "fire,warning" if not is_test else "test"
        }
        
        try:
            response = requests.post(
                self.url,
                data=message,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            self.logger.info(f"Notification sent successfully to {self.topic}")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send ntfy notification: {e}")
            return False


class NotificationManager:
    """Manages multiple notifiers and handles notification dispatch."""
    
    def __init__(self, notifiers: List[BaseNotifier] = None):
        self.notifiers = notifiers or []
        self.logger = logging.getLogger("notification_manager")
    
    async def notify_all(self, event: DetectionEvent, is_test: bool = False) -> Dict[str, bool]:
        """Send notification to all enabled notifiers."""
        if not self.notifiers:
            self.logger.warning("No notifiers configured")
            return {}
        
        # Send notifications concurrently
        tasks = []
        notifier_names = []
        
        for notifier in self.notifiers:
            if notifier.enabled:
                tasks.append(notifier.notify_with_retry(event, is_test))
                notifier_names.append(notifier.name)
        
        if not tasks:
            self.logger.warning("No enabled notifiers found")
            return {}
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        notification_results = {}
        for name, result in zip(notifier_names, results):
            if isinstance(result, Exception):
                self.logger.error(f"Notifier {name} raised exception: {result}")
                notification_results[name] = False
            else:
                notification_results[name] = result
        
        # Log summary
        successful = sum(1 for success in notification_results.values() if success)
        total = len(notification_results)
        self.logger.info(f"Notification summary: {successful}/{total} successful")
        
        return notification_results