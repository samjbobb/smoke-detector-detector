#!/usr/bin/env -S uv run --script
"""Simple test to debug detection issues"""

from smoke_detection_algorithm import SmokeAlarmDetector
from pathlib import Path

detector = SmokeAlarmDetector()
test_file = Path("test_audio/first_alert_sa511.wav")

print("Testing detection on", test_file)
results = detector.process_audio_file(test_file, verbose=True)
print(f"Results: {results}")

# Check some basic properties
print(f"Sample rate: {detector.sample_rate}")
print(f"Target frequency: {detector.target_frequency}")
print(f"Frequency tolerance: {detector.frequency_tolerance}")
print(f"Confidence threshold: {detector.confidence_threshold}")