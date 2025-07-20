#!/usr/bin/env -S uv run --script
"""
Main entry point for smoke alarm detector.
Handles live audio monitoring using sounddevice.
"""

import sounddevice as sd
import numpy as np
import time
import argparse
import asyncio
import logging
import sys
from smoke_detection_algorithm import SmokeAlarmDetector
from notifiers import (
    NotificationManager, 
    NtfyNotifier, 
    DetectionEvent
)


def create_trigger_alarm_callback(notification_manager: NotificationManager):
    """Create alarm callback with notification support."""
    
    def trigger_alarm(detection: dict) -> None:
        """Callback function when smoke alarm is detected."""
        print(f"\n🚨 SMOKE ALARM DETECTED! 🚨")
        print(f"Frequency: {detection['frequency']:.1f} Hz")
        print(f"Signal Strength: {detection['strength']:.2f}")
        if 'avg_interval' in detection:
            print(f"Beep Interval: {detection['avg_interval']:.2f}s")
        print(f"Confidence: {detection.get('confidence', 0):.2%}")
        print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 50)
        
        # Send notifications if manager is configured
        if notification_manager and notification_manager.notifiers:
            event = DetectionEvent(
                timestamp=detection['timestamp'],
                frequency=detection['frequency'],
                strength=detection['strength'],
                confidence=detection.get('confidence', 1.0),
                detection_type=detection.get('detection_type', 'unknown')
            )
            
            # Run notifications in background to not block detection
            try:
                # Try to get the main thread's event loop
                try:
                    loop = asyncio.get_running_loop()
                    # Schedule the coroutine to run in the main thread's event loop
                    asyncio.run_coroutine_threadsafe(notification_manager.notify_all(event), loop)
                except RuntimeError:
                    # No running loop, create a new one in a thread
                    import threading
                    
                    def run_notification():
                        asyncio.run(notification_manager.notify_all(event))
                    
                    thread = threading.Thread(target=run_notification, daemon=True)
                    thread.start()
                    
            except Exception as e:
                logging.error(f"Failed to send notifications: {e}")
                print(f"⚠️  Failed to send notifications: {e}")
    
    return trigger_alarm


def audio_callback(indata: np.ndarray, frames: int, time_info, status, detector: SmokeAlarmDetector) -> None:
    """Audio callback for live monitoring."""
    if status:
        print(f"Audio callback status: {status}")
    
    # Convert to mono if stereo
    audio_data = indata[:, 0] if indata.ndim > 1 else indata
    
    # Stream audio to detector
    detector.process_audio_stream(audio_data)


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def setup_notifiers() -> NotificationManager:
    """Setup notification manager with hardcoded settings."""
    notifiers = []
    
    # Hardcoded ntfy configuration
    ntfy_topic = "PLACEHOLDER_TOPIC"
    ntfy_server = "https://ntfy.sh"
    max_retries = 3
    retry_delay = 1.0
    
    notifier = NtfyNotifier(
        topic=ntfy_topic,
        server=ntfy_server,
        max_retries=max_retries,
        retry_delay=retry_delay
    )
    notifiers.append(notifier)
    print(f"📱 Added ntfy notifier for topic: {ntfy_topic}")
    
    return NotificationManager(notifiers)


async def test_notifiers(manager: NotificationManager):
    """Test all configured notifiers."""
    if not manager.notifiers:
        print("No notifiers configured to test")
        return True
    
    print("Testing configured notifiers...")
    
    # Create a dummy event for testing
    test_event = DetectionEvent(
        timestamp=time.time(),
        frequency=3200.0,
        strength=150.0,
        confidence=1.0,
        detection_type="test"
    )
    
    results = await manager.notify_all(test_event, is_test=True)
    
    all_passed = True
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {name}: {status}")
        if not success:
            all_passed = False
    
    return all_passed


def get_audio_device(device_arg):
    """Get and validate audio device."""
    devices = sd.query_devices()
    
    # If no device specified, show available devices and prompt
    if device_arg is None:
        print("\nAvailable audio input devices:")
        input_devices = []
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                default_marker = " (default)" if i == sd.default.device[0] else ""
                print(f"  {i}: {device['name']}{default_marker}")
                input_devices.append(i)
        
        if not input_devices:
            print("❌ No input devices available")
            sys.exit(1)
        
        print(f"\nUsing default device {sd.default.device[0]}: {devices[sd.default.device[0]]['name']}")
        print("Use --device <number> to specify a different device\n")
        return sd.default.device[0]
    
    # Parse device argument (could be number or name)
    try:
        device_id = int(device_arg)
        if device_id < 0 or device_id >= len(devices):
            print(f"❌ Device {device_id} not found")
            sys.exit(1)
    except ValueError:
        # Try to find device by name
        device_id = None
        for i, device in enumerate(devices):
            if device_arg.lower() in device['name'].lower():
                device_id = i
                break
        if device_id is None:
            print(f"❌ Device '{device_arg}' not found")
            sys.exit(1)
    
    # Validate device has input channels
    device_info = devices[device_id]
    if device_info['max_input_channels'] == 0:
        print(f"❌ Device {device_id} ({device_info['name']}) has no input channels")
        sys.exit(1)
    
    return device_id


def main():
    parser = argparse.ArgumentParser(description="Smoke alarm detector with notifications")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--no-notifications", action="store_true", help="Disable all notifications")
    parser.add_argument("--test-notifications", action="store_true", help="Test notifications and exit")
    parser.add_argument("--device", type=str, help="Audio input device (number or name)")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    # Setup notifications
    notification_manager = None
    if not args.no_notifications:
        notification_manager = setup_notifiers()
    
    # Test notifications and exit if requested
    if args.test_notifications:
        if not notification_manager or not notification_manager.notifiers:
            print("No notifiers configured for testing")
            sys.exit(1)
        
        success = asyncio.run(test_notifiers(notification_manager))
        sys.exit(0 if success else 1)
    
    # Get audio device
    device_id = get_audio_device(args.device)
    device_info = sd.query_devices()[device_id]
    
    # Setup detector
    detector = SmokeAlarmDetector()
    trigger_callback = create_trigger_alarm_callback(notification_manager)
    detector.set_detection_callback(trigger_callback)
    
    print("🎤 Starting smoke alarm detection...")
    print(f"Audio device: {device_id} - {device_info['name']}")
    print(f"Listening for alarms at ~{detector.target_frequency}Hz")
    
    if notification_manager and notification_manager.notifiers:
        notifier_names = [n.name for n in notification_manager.notifiers]
        print(f"📱 Notifications enabled: {', '.join(notifier_names)}")
    else:
        print("📱 Notifications disabled")
    
    print("Press Ctrl+C to stop")
    
    try:
        with sd.InputStream(
            device=device_id,
            callback=lambda indata, frames, time_info, status: audio_callback(indata, frames, time_info, status, detector),
            channels=1,
            samplerate=detector.sample_rate,
            blocksize=detector.chunk_size,
            latency=0.2  # 200ms buffer (explicit value instead of 'high')
        ):
            while True:
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\n🛑 Stopping smoke alarm detection...")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()