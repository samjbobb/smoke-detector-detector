# Smoke Detector Detector

Detects smoke alarm beeping patterns using real-time audio analysis. Listens for the characteristic 3.2kHz beeping pattern of smoke alarms and triggers alerts.

## Features

- Real-time microphone monitoring
- Audio file processing for testing
- YouTube test case extraction
- Pattern recognition for smoke alarm sequences
- Docker containerization support

## Quick Start

### Live Monitoring
```bash
uv run python main.py
```

### Test with Audio File
```bash
uv run python main.py --test-file test_audio/sample.wav
```

### Docker
```bash
docker build -t smoke-detector-detector .
docker run --device /dev/snd smoke-detector-detector
```

## Testing Workflow

### 1. Add Test Cases from YouTube (auto-extracts audio)
```bash
# Basic usage with MM:SS format - extracts audio immediately
./extract_test_audio.py add "https://youtu.be/VIDEO_ID" "Description" "1:15" "1:25" --expect-alarms "1:18,1:22"

# Mixed time formats supported
./extract_test_audio.py add "https://youtu.be/VIDEO_ID" "Long test" "2:30" "180" --expect-alarms "2:32,155,2:40"
```

### 2. Run Tests

#### Run All Tests
```bash
./test_runner.py
```

This will:
- Process all extracted audio files
- Compare detections against expected alarm timestamps
- Report precision, recall, F1 scores for each test case
- Show overall performance summary

#### Debug Single Test Case
```bash
# By test case number (from list command)
./test_runner.py --single 1

# By description/filename (partial match)
./test_runner.py --single "kidde"
./test_runner.py --single "alarm_test"
```

Single test mode shows:
- Expected vs detected alarm timestamps
- True positives with detection latency
- False positives (unexpected detections)  
- False negatives (missed alarms)
- Performance recommendations

### 3. View Test Cases
```bash
./extract_test_audio.py list
```

### Optional: Extract pending cases
```bash
# Only needed if previous extractions failed
./extract_test_audio.py extract-all
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
  - Excellent: F1 e 0.9
  - Good: F1 e 0.8  
  - Acceptable: F1 e 0.6

### Dependencies
- `sounddevice`: Audio I/O
- `numpy`: Signal processing
- `scipy`: FFT and filtering
- `librosa`: Audio file loading
- `yt-dlp`: YouTube audio extraction