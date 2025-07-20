#!/usr/bin/env python3
"""
Main entry point for smoke alarm detector.
Handles live audio monitoring using sounddevice.
"""

import sounddevice as sd
import numpy as np
import time
from smoke_detection_algorithm import SmokeAlarmDetector


def trigger_alarm(detection: dict) -> None:
    """Callback function when smoke alarm is detected."""
    print(f"\n🚨 SMOKE ALARM DETECTED! 🚨")
    print(f"Frequency: {detection['frequency']:.1f} Hz")
    print(f"Signal Strength: {detection['strength']:.2f}")
    print(f"Beep Interval: {detection['avg_interval']:.2f}s")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)


def audio_callback(indata: np.ndarray, frames: int, time_info, status, detector: SmokeAlarmDetector) -> None:
    """Audio callback for live monitoring."""
    if status:
        print(f"Audio callback status: {status}")
    
    # Convert to mono if stereo
    audio_data = indata[:, 0] if indata.ndim > 1 else indata
    
    # Stream audio to detector
    detector.process_audio_stream(audio_data)


def main():
    detector = SmokeAlarmDetector()
    detector.set_detection_callback(trigger_alarm)
    
    print("🎤 Starting smoke alarm detection...")
    print(f"Listening for alarms at ~{detector.target_frequency}Hz")
    print("Press Ctrl+C to stop")
    
    try:
        with sd.InputStream(
            callback=lambda indata, frames, time_info, status: audio_callback(indata, frames, time_info, status, detector),
            channels=1,
            samplerate=detector.sample_rate,
            blocksize=detector.chunk_size
        ):
            while True:
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\n🛑 Stopping smoke alarm detection...")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()