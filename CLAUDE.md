# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Essential Commands
- `./main.py` - Live smoke alarm detection with real-time audio monitoring
- `./main.py --test-notifications` - Test notification system configuration 
- `./test_runner.py` - Run comprehensive test suite (11 test cases, F1 metrics)
- `./test_runner.py --single <name|number>` - Debug specific test with detailed analysis
- `./extract_test_audio.py list` - View all test cases and their metadata
- `./extract_test_audio.py add <youtube_url> <description> <start> <end> --expect-alarms <times>` - Add new test case from YouTube

### Development Analysis Tools
- `./debug_detection.py` - Detailed algorithm introspection with hook instrumentation
- `./analyze_audio.py` - Audio file frequency analysis and visualization
- `./visualize_fft.py` - Real-time FFT visualization for algorithm tuning
- `./record_audio.py` - Record audio samples for testing

### Environment Setup
- Requires `export NTFY_TOPIC="your-topic"` for notifications
- Uses `uv` package manager (modern Python dependency management)
- All scripts have uv shebang: `#!/usr/bin/env -S uv run --script`

## Architecture Overview

### Core Algorithm (smoke_detection_algorithm.py)
- **SmokeAlarmDetector** class implements sophisticated multi-stage signal processing
- FFT-based frequency analysis targeting 3.2kHz ± 400Hz (smoke alarm standard)
- Uses Hanning window preprocessing, dynamic background noise learning, sustained pattern recognition
- Advanced validation: signal-to-noise ratio (75:1 min), temporal consistency (25-80% occupation), frequency stability analysis
- Extensive instrumentation hooks for debugging without code duplication

### Live Monitoring (main.py)
- Real-time audio streaming with sounddevice integration
- Audio device discovery and selection with fallback handling
- Asynchronous notification dispatch with threading for non-blocking alerts
- Integration point between detection algorithm and notification system

### Notification System (notifiers.py)
- Abstract base class design for extensible notification types
- Currently implements ntfy.sh push notifications with retry logic
- Async/await pattern with proper error handling and timeout management
- NotificationManager orchestrates multiple notifier instances

### Testing Infrastructure
- **test_runner.py**: File-based testing using same algorithm as live monitoring
- Comprehensive metrics: precision, recall, F1 scores with ±2 second tolerance
- Performance thresholds: Excellent (F1≥0.9), Good (F1≥0.8), Acceptable (F1≥0.6)
- **extract_test_audio.py**: YouTube test case extraction with time-based audio clipping
- Test cases stored in `test_audio/test_cases.json` with expected alarm timestamps

### Signal Processing Details
- 44.1kHz sample rate, 4096-sample chunks (~93ms processing windows)
- 10-second startup phase for ambient noise learning
- Latch mechanism with 5-minute cooldown to prevent notification spam
- Multiple validation criteria: SNR, temporal patterns, frequency stability, signal strength variation

## File Processing vs Live Monitoring

- **Live monitoring**: Use `main.py` for real-time microphone input
- **File testing**: Use `test_runner.py` for audio file analysis
- `main.py` does NOT support `--test-file` option (this was removed)
- Test audio files are managed through `extract_test_audio.py` and processed via `test_runner.py`

## Testing Patterns

- Production uses same algorithm as testing (no separate test implementations)
- Test cases include positive samples (3 smoke alarm models) and negative samples (music, leaf blower, chirps)
- Debug single tests for algorithm tuning: `./test_runner.py --single "first_alert"`
- Add new test cases from real YouTube videos of smoke alarms for validation
- All test timestamps use video timeline reference (not clip-relative timing)

## Key Dependencies

- **Audio**: sounddevice (I/O), numpy (processing), scipy (FFT), librosa (file loading)
- **Testing**: yt-dlp (YouTube extraction)
- **Notifications**: requests (HTTP notifications)
- **Python**: Requires ≥3.12, uses uv for package management