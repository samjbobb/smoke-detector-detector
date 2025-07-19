#!/usr/bin/env python3
"""
Main entry point for smoke alarm detector.
This is a thin wrapper that handles command line arguments and starts the detector.
"""

import argparse
from pathlib import Path
from smoke_detection_algorithm import SmokeAlarmDetector


def main():
    parser = argparse.ArgumentParser(description="Smoke Alarm Detector")
    parser.add_argument("--test-file", type=Path, help="Process audio file instead of live monitoring")
    parser.add_argument("--test-dir", type=Path, default="test_audio", help="Test audio directory")
    
    args = parser.parse_args()
    
    detector = SmokeAlarmDetector()
    
    if args.test_file:
        # Process single audio file
        detector.process_audio_file(args.test_file)
    else:
        # Live monitoring mode
        detector.start_monitoring()


if __name__ == "__main__":
    main()