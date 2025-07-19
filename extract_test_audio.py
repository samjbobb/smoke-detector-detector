#!/usr/bin/env python3
"""
Extract test audio from YouTube videos for smoke detector testing.

Usage:
    python extract_test_audio.py add "https://youtube.com/watch?v=abc123" "First Alarm Co detector test" "0:15" "0:25"
    python extract_test_audio.py add "https://youtube.com/watch?v=def456" "Kidde smoke alarm" "1:30" "1:45" --expect-alarms "1:32,1:36,1:40"
    python extract_test_audio.py add "https://youtube.com/watch?v=xyz789" "Long test" "2:15" "3:05" --expect-alarms "2:18,2:22,2:26"
    python extract_test_audio.py list
    python extract_test_audio.py extract-all  # Extract any pending cases
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional
import re


class TestAudioExtractor:
    def __init__(self, test_dir: str = "test_audio"):
        self.test_dir = Path(test_dir)
        self.config_file = self.test_dir / "test_cases.json"
        self._ensure_dirs()
    
    @staticmethod
    def _parse_time(time_str: str) -> float:
        """Parse time string in format MM:SS or SS to seconds."""
        time_str = time_str.strip()
        
        # Handle MM:SS format
        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) == 2:
                minutes, seconds = parts
                return float(minutes) * 60 + float(seconds)
            elif len(parts) == 3:  # HH:MM:SS format
                hours, minutes, seconds = parts
                return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
            else:
                raise ValueError(f"Invalid time format: {time_str}")
        else:
            # Handle plain seconds
            return float(time_str)
        
    def _ensure_dirs(self):
        self.test_dir.mkdir(exist_ok=True)
        if not self.config_file.exists():
            self._save_config({"test_cases": []})
    
    def _load_config(self) -> Dict:
        with open(self.config_file) as f:
            return json.load(f)
    
    def _save_config(self, config: Dict):
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def add_test_case(
        self, 
        url: str, 
        description: str, 
        start_time: str, 
        end_time: str,
        expected_alarms: Optional[List[str]] = None
    ):
        """Add a new test case configuration."""
        config = self._load_config()
        
        # Parse time strings to seconds
        try:
            start_seconds = self._parse_time(start_time)
            end_seconds = self._parse_time(end_time)
            
            # Parse expected alarm times
            expected_seconds = []
            if expected_alarms:
                expected_seconds = [self._parse_time(alarm_time) for alarm_time in expected_alarms]
            
        except ValueError as e:
            print(f"❌ Time parsing error: {e}")
            print("   Use format: MM:SS (e.g., '1:35') or seconds (e.g., '95')")
            return
        
        if end_seconds <= start_seconds:
            print("❌ End time must be after start time")
            return
        
        # Generate filename from description
        filename = self._sanitize_filename(description) + ".wav"
        
        test_case = {
            "url": url,
            "description": description,
            "filename": filename,
            "start_time": start_seconds,
            "end_time": end_seconds,
            "duration": end_seconds - start_seconds,
            "expected_alarms": expected_seconds,
            "extracted": False
        }
        
        config["test_cases"].append(test_case)
        self._save_config(config)
        
        print(f"✅ Added test case: {description}")
        print(f"   File: {filename}")
        print(f"   Duration: {end_seconds - start_seconds:.1f}s ({start_time} to {end_time})")
        if expected_seconds:
            alarm_times = [f"{t:.1f}s" for t in expected_seconds]
            print(f"   Expected alarms at: {', '.join(alarm_times)}")
        
        # Automatically extract the audio
        print(f"\n🎵 Extracting audio...")
        if self._extract_audio(test_case):
            # Update the config to mark as extracted
            config["test_cases"][-1]["extracted"] = True
            self._save_config(config)
            print(f"   ✅ Audio extracted successfully!")
        else:
            print(f"   ❌ Audio extraction failed")
    
    def list_test_cases(self):
        """List all configured test cases."""
        config = self._load_config()
        
        if not config["test_cases"]:
            print("No test cases configured yet.")
            print("Use 'add' command to add test cases.")
            return
        
        print("Test Cases:")
        print("-" * 60)
        
        for i, case in enumerate(config["test_cases"], 1):
            status = "✅ Extracted" if case["extracted"] else "⏳ Pending"
            print(f"{i}. {case['description']}")
            print(f"   File: {case['filename']}")
            print(f"   Duration: {case['duration']:.1f}s ({case['start_time']:.1f}-{case['end_time']:.1f}s)")
            if case['expected_alarms']:
                print(f"   Expected alarms: {case['expected_alarms']}")
            print(f"   Status: {status}")
            print()
    
    def extract_all(self):
        """Extract audio for all pending test cases."""
        config = self._load_config()
        pending_cases = [case for case in config["test_cases"] if not case["extracted"]]
        
        if not pending_cases:
            print("All test cases already extracted!")
            return
        
        print(f"Extracting {len(pending_cases)} test cases...")
        
        for case in pending_cases:
            print(f"\n🎵 Extracting: {case['description']}")
            
            if self._extract_audio(case):
                case["extracted"] = True
                print(f"   ✅ Success: {case['filename']}")
            else:
                print(f"   ❌ Failed: {case['filename']}")
        
        self._save_config(config)
        print("\n🎉 Extraction complete!")
    
    def _extract_audio(self, case: Dict) -> bool:
        """Extract audio segment using yt-dlp and ffmpeg."""
        output_path = self.test_dir / case["filename"]
        
        try:
            # Use yt-dlp to download and ffmpeg to extract segment
            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "wav",
                "--audio-quality", "0",  # Best quality
                "--postprocessor-args",
                f"ffmpeg:-ss {case['start_time']} -t {case['duration']} -ar 44100 -ac 1",
                "--output", str(output_path.with_suffix('.%(ext)s')),
                case["url"]
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return output_path.exists()
            else:
                print(f"   Error: {result.stderr}")
                return False
                
        except FileNotFoundError:
            print("   Error: yt-dlp not found. Install with: pip install yt-dlp")
            return False
        except Exception as e:
            print(f"   Error: {e}")
            return False
    
    def _sanitize_filename(self, filename: str) -> str:
        """Convert description to safe filename."""
        import re
        # Remove/replace unsafe characters
        safe = re.sub(r'[<>:"/\\|?*]', '', filename)
        safe = re.sub(r'\s+', '_', safe.strip())
        return safe.lower()


def main():
    parser = argparse.ArgumentParser(description="Extract test audio from YouTube videos")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new test case")
    add_parser.add_argument("url", help="YouTube URL")
    add_parser.add_argument("description", help="Test case description")
    add_parser.add_argument("start_time", help="Start time (MM:SS or seconds)")
    add_parser.add_argument("end_time", help="End time (MM:SS or seconds)")
    add_parser.add_argument("--expect-alarms", help="Expected alarm timestamps (comma-separated, MM:SS or seconds)")
    
    # List command
    subparsers.add_parser("list", help="List all test cases")
    
    # Extract command
    subparsers.add_parser("extract-all", help="Extract audio for all pending test cases")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    extractor = TestAudioExtractor()
    
    if args.command == "add":
        expected_alarms = None
        if args.expect_alarms:
            expected_alarms = [t.strip() for t in args.expect_alarms.split(',')]
        
        extractor.add_test_case(
            args.url, 
            args.description, 
            args.start_time, 
            args.end_time,
            expected_alarms
        )
    
    elif args.command == "list":
        extractor.list_test_cases()
    
    elif args.command == "extract-all":
        extractor.extract_all()


if __name__ == "__main__":
    main()