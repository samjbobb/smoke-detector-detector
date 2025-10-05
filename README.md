# Smoke Detector Detector

> Note: this was all written by Claude Code in a few hours over one weekend. I directed it but wrote essentially zero code. It's working for my use-case. I suspect the actual detection algorithm could be simpler, but I don't want to spend time on it. We live in a weird weird AI world now...

> Purpose: I want to know if my dog is being terrorized by smoke detector false alarms when I'm not home.
 
Detects smoke alarm beeping patterns using real-time audio analysis. Listens for the characteristic 3.2kHz beeping pattern of smoke alarms and triggers push notifications.

## Quick Start

### Live Monitoring
```bash
./main.py
# or
uv run python main.py
```

### Key Options
```bash
./main.py --device 1              # Specify audio input device
./main.py -v                      # Verbose logging
./main.py --test-notifications    # Test notification system
./main.py --config custom.json    # Use custom config file
```

### Configuration
Create a `config.json` file (see `config.example.json` for structure):
```json
{
  "notifications": {
    "ntfy": {
      "enabled": true,
      "topic": "your-topic-name",
      "server": "https://ntfy.sh"
    }
  },
  "audio": {
    "device": null
  }
}
```

## Testing

### Run All Tests
```bash
./test_runner.py
```

### Debug Single Test
```bash
./test_runner.py --single 1       # By test number
./test_runner.py --single "kidde"  # By name/description
```

### Add Test Cases from YouTube
```bash
./extract_test_audio.py add "https://youtu.be/VIDEO_ID" "Description" "1:15" "1:25" --expect-alarms "1:18,1:22"
```

### View Test Cases
```bash
./extract_test_audio.py list
```

## Features

- Real-time microphone monitoring with configurable audio device selection
- Push notifications via ntfy.sh
- Comprehensive test suite with 99+ test cases from real smoke alarm videos
- YouTube test case extraction and management
- Pattern recognition for smoke alarm sequences (3.2kHz ± 300Hz)
- Docker containerization support

## Docker Deployment
```bash
# Create config.json first
cp config.example.json config.json
# Edit config.json with your settings

docker build -t smoke-detector-detector .
docker run --device /dev/snd -v $(pwd)/config.json:/app/config.json smoke-detector-detector
```

## Time Format Reference

The extraction script accepts multiple time formats for convenience:

| Format | Example | Seconds |
|--------|---------|---------|
| MM:SS | "1:35" | 95 |
| HH:MM:SS | "1:02:30" | 3750 |
| Seconds | "95" | 95 |

You can mix formats in the same command:
```bash
./extract_test_audio.py add "url" "test" "1:15" "85" --expect-alarms "1:18,80"
```

## FAQ

### Q: Are expected alarm timestamps relative to the video or the extracted clip?
**A:** Expected alarm timestamps use the **same reference frame as start/end times** (overall video timeline).

**Example:**
```bash
# Video timeline: alarm occurs at 1:18
# Extract clip from 1:15-1:25 
# Use 1:18 for expected alarm (not 0:03)
./extract_test_audio.py add "url" "test" "1:15" "1:25" --expect-alarms "1:18"
```

This approach eliminates mental math and matches the YouTube UI timestamps directly.

### Q: Smoke alarms beep 3 times over ~3 seconds. Which timestamp should I use?
**A:** Use the timestamp of the **first beep** (beginning of the sequence).

**Why:**
- Matches natural behavior: "alarm starts at 1:18"
- Detection algorithm triggers early in the sequence
- Easier to mark consistently while watching videos
- 2-second test tolerance accommodates timing variations

**Example sequence:**
- 1:18.0 - First beep � **Use this timestamp**
- 1:19.0 - Second beep
- 1:20.0 - Third beep

The test runner accepts detections within �2 seconds, covering the entire sequence.

## Technical Details

### Detection Algorithm
- **Frequency Analysis:** FFT-based detection targeting 3.2kHz � 300Hz
- **Pattern Recognition:** Identifies 3-4 second beeping intervals
- **Signal Processing:** Hanning window, signal-to-noise ratio filtering
- **Confidence Threshold:** Requires 3+ consistent beeps for alarm trigger

### Test Validation
- **Tolerance:** �2 seconds for alarm matching
- **Metrics:** Precision, recall, F1 score, detection latency
- **Performance Thresholds:**
  - Excellent: F1 ≥ 0.9, Good: F1 ≥ 0.8, Acceptable: F1 ≥ 0.6

### Key Dependencies
- Uses `uv` for modern Python package management
- `sounddevice`: Audio I/O, `numpy`: Signal processing
- `scipy`: FFT and filtering, `librosa`: Audio file loading
- `yt-dlp`: YouTube audio extraction, `httpx`: HTTP notifications

## Raspberry Pi Deployment

### Quick Install
```bash
# Clone the repository on your Pi
git clone git@github.com:samjbobb/smoke-detector-detector.git
cd smoke-detector-detector

# Run the installer (will prompt for configuration)
./install.sh
```

The installer will:
1. Detect current user and configure paths accordingly
2. Install system dependencies (audio libraries)
3. Install uv package manager
4. Copy project files to installation directory
5. Set up Python dependencies
6. Create `config.json` with your notification settings
7. Configure as a systemd service for auto-start
8. Start the service (optional)

### Service Management
```bash
# Start/stop/restart the service
sudo systemctl start smoke-detector
sudo systemctl stop smoke-detector
sudo systemctl restart smoke-detector

# Check service status
sudo systemctl status smoke-detector

# View live logs
sudo journalctl -u smoke-detector -f

# Disable auto-start
sudo systemctl disable smoke-detector
```

### Configuration

The application uses a `config.json` file for all settings. The installer creates this automatically, but you can edit it later:

```bash
# Edit configuration
nano ~/smoke-detector-detector/config.json

# Restart service after config changes
sudo systemctl restart smoke-detector
```

### Uninstall
```bash
./uninstall.sh  # Removes service and optionally backs up config
```

### Requirements
- Raspberry Pi OS (Debian 12/Bookworm) or compatible
- Python 3.12+
- Audio input device (USB microphone recommended)
- Network connection for notifications

### Troubleshooting
- **Audio device not found:** Check USB microphone connection and run `arecord -l`
- **Permission denied:** Ensure user is in `audio` group: `sudo usermod -a -G audio $USER`
- **Service fails to start:** Check logs with `sudo journalctl -u smoke-detector -n 50`
- **No notifications:** Check `config.json` in installation directory (`~/smoke-detector-detector/config.json`)