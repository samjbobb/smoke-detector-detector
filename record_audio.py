#!/usr/bin/env python3
"""
Cross-platform audio recording script for smoke detector tests.
Records audio in the correct format: 44.1kHz, mono, 16-bit WAV.
"""

import platform
import subprocess
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

def get_ffmpeg_audio_input():
    """Get the correct audio input format for the current platform."""
    system = platform.system().lower()
    if system == 'darwin':  # macOS
        return 'avfoundation'
    elif system == 'linux':
        return 'alsa'
    else:
        print(f"Unsupported platform: {system}")
        print("This script supports macOS and Linux only.")
        sys.exit(1)

def list_audio_devices():
    """List available audio input devices for the current platform."""
    system = platform.system().lower()
    
    print("Available audio devices:")
    print("-" * 40)
    
    if system == 'darwin':  # macOS
        try:
            cmd = ['ffmpeg', '-f', 'avfoundation', '-list_devices', 'true', '-i', '']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            lines = result.stdout.split('\n')
            audio_devices = []
            in_audio_section = False
            
            for line in lines:
                if '[AVFoundation indev' in line and 'audio devices:' in line:
                    in_audio_section = True
                    continue
                elif '[AVFoundation indev' in line and 'video devices:' in line:
                    in_audio_section = False
                    continue
                
                if in_audio_section and '] [' in line and 'AVFoundation' in line:
                    device_info = line.split('] ', 1)[-1]
                    audio_devices.append(device_info)
                    print(f"  {len(audio_devices)-1}: {device_info}")
            
            return audio_devices
            
        except FileNotFoundError:
            print("Error: ffmpeg not found. Please install ffmpeg.")
            sys.exit(1)
        except Exception as e:
            print(f"Error listing devices: {e}")
            return []
    
    elif system == 'linux':
        try:
            # Try arecord first
            result = subprocess.run(['arecord', '-l'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                print("Using arecord -l:")
                print(result.stdout)
                
                # Also show /proc/asound/cards for more detail
                try:
                    with open('/proc/asound/cards', 'r') as f:
                        print("\nDetailed device info (/proc/asound/cards):")
                        print(f.read())
                except:
                    pass
                
                print("\nCommon device formats:")
                print("  hw:0,0 - First card, first device (usually built-in)")
                print("  hw:1,0 - Second card, first device (usually USB mic)")
                print("  default - System default device")
                
                return ["hw:0,0", "hw:1,0", "hw:2,0", "default"]
            else:
                print("arecord not available, trying ffmpeg...")
                
        except FileNotFoundError:
            pass
        
        # Fallback to common ALSA device names
        print("Common ALSA devices (may or may not exist):")
        devices = ["hw:0,0", "hw:1,0", "hw:2,0", "default", "plughw:1,0"]
        for i, device in enumerate(devices):
            print(f"  {i}: {device}")
        return devices

def test_audio_device(device_name, input_format):
    """Test if an audio device works by doing a short recording."""
    system = platform.system().lower()
    
    if system == 'darwin':
        device_input = f":{device_name}"
    else:  # linux
        device_input = device_name
    
    cmd = [
        'ffmpeg', '-y',  # -y to overwrite
        '-f', input_format,
        '-i', device_input,
        '-ar', '44100',
        '-ac', '1',
        '-acodec', 'pcm_s16le',
        '-t', '1',  # 1 second test
        '/tmp/audio_test.wav'
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        success = result.returncode == 0 and Path('/tmp/audio_test.wav').exists()
        
        # Clean up test file
        try:
            Path('/tmp/audio_test.wav').unlink(missing_ok=True)
        except:
            pass
            
        return success, result.stderr if not success else ""
    except Exception as e:
        return False, str(e)

def select_audio_device():
    """Interactive device selection with testing."""
    input_format = get_ffmpeg_audio_input()
    devices = list_audio_devices()
    
    if not devices:
        print("No audio devices found!")
        sys.exit(1)
    
    while True:
        try:
            print(f"\nEnter device number (0-{len(devices)-1}) or 'q' to quit: ", end='')
            choice = input().strip()
            
            if choice.lower() == 'q':
                sys.exit(0)
            
            device_idx = int(choice)
            if 0 <= device_idx < len(devices):
                device_name = str(device_idx) if platform.system().lower() == 'darwin' else devices[device_idx]
                
                print(f"Testing device: {devices[device_idx]}")
                success, error = test_audio_device(device_name, input_format)
                
                if success:
                    print("✓ Device test successful!")
                    return device_name, devices[device_idx]
                else:
                    print(f"✗ Device test failed: {error}")
                    print("Try another device.")
            else:
                print("Invalid device number!")
                
        except ValueError:
            print("Please enter a valid number!")
        except KeyboardInterrupt:
            print("\nExiting...")
            sys.exit(0)

def record_audio(device_name, input_format):
    """Record audio until user stops."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"recording_{timestamp}.wav"
    
    cmd = [
        'ffmpeg', '-y',
        '-f', input_format,
        '-i', f":{device_name}" if platform.system().lower() == 'darwin' else device_name,
        '-ar', '44100',   # 44.1 kHz sample rate
        '-ac', '1',       # Mono
        '-acodec', 'pcm_s16le',  # 16-bit PCM
        output_file
    ]
    
    print(f"\nStarting recording to: {output_file}")
    print("Format: 44.1kHz, mono, 16-bit WAV")
    print("Press ENTER to stop recording...")
    print("-" * 50)
    
    # Start ffmpeg process
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for user input in separate thread
    stop_event = threading.Event()
    
    def wait_for_input():
        input()  # Wait for Enter key
        stop_event.set()
    
    input_thread = threading.Thread(target=wait_for_input)
    input_thread.daemon = True
    input_thread.start()
    
    # Monitor recording
    start_time = time.time()
    try:
        while not stop_event.is_set():
            if process.poll() is not None:
                # Process ended unexpectedly
                stdout, stderr = process.communicate()
                print(f"\nRecording ended unexpectedly!")
                print(f"Error: {stderr.decode()}")
                return False
            
            # Show elapsed time
            elapsed = time.time() - start_time
            print(f"\rRecording... {elapsed:.1f}s", end='', flush=True)
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        stop_event.set()
    
    # Stop recording
    print(f"\nStopping recording...")
    process.terminate()
    
    # Wait a moment for clean termination
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
    
    # Check if file was created
    if Path(output_file).exists():
        file_size = Path(output_file).stat().st_size
        duration = time.time() - start_time
        print(f"✓ Recording saved: {output_file}")
        print(f"  Duration: {duration:.1f}s")
        print(f"  File size: {file_size:,} bytes")
        
        # Verify file format
        try:
            result = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', 
                                   '-show_format', '-show_streams', output_file], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                import json
                info = json.loads(result.stdout)
                stream = info['streams'][0]
                print(f"  Verified: {stream['sample_rate']}Hz, {stream['channels']} channel(s), {stream['codec_name']}")
        except:
            pass
            
        return True
    else:
        print("✗ Recording file not found!")
        return False

def main():
    """Main function."""
    print("🎤 Audio Recording Tool for Smoke Detector Tests")
    print("=" * 50)
    print("This tool records audio in the correct format for your tests:")
    print("• Sample Rate: 44.1 kHz")
    print("• Channels: Mono (1)")
    print("• Bit Depth: 16-bit")
    print("• Format: WAV (PCM)")
    
    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("\n❌ Error: ffmpeg not found!")
        print("Please install ffmpeg:")
        if platform.system().lower() == 'darwin':
            print("  brew install ffmpeg")
        else:
            print("  sudo apt-get install ffmpeg  # Debian/Ubuntu")
        sys.exit(1)
    
    input_format = get_ffmpeg_audio_input()
    print(f"\nDetected platform: {platform.system()}")
    print(f"Audio input format: {input_format}")
    
    # Device selection
    device_name, device_display = select_audio_device()
    print(f"\nSelected device: {device_display}")
    
    # Start recording
    while True:
        try:
            print(f"\nPress ENTER to start recording (or 'q' to quit): ", end='')
            if input().strip().lower() == 'q':
                break
            
            success = record_audio(device_name, input_format)
            
            if success:
                print(f"\nRecord another? (ENTER = yes, 'q' = quit): ", end='')
                if input().strip().lower() == 'q':
                    break
            else:
                print("Recording failed. Try again or quit.")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
    
    print("Thanks for using the audio recording tool! 👋")

if __name__ == '__main__':
    main()