#!/usr/bin/env python3
"""
Smoke alarm detection algorithm and detector class.
This module contains the complete smoke alarm detection logic used by both live monitoring and file processing.
"""

import sounddevice as sd
import numpy as np
from scipy import signal
import librosa
import time
from threading import Event
from pathlib import Path
from collections import deque
from typing import Optional, List, Dict


class SmokeAlarmDetector:
    """Complete smoke alarm detector with both live monitoring and file processing capabilities."""
    
    def __init__(
        self,
        sample_rate: int = 44100,
        chunk_size: int = 4096,
        target_frequency: float = 3200.0,
        frequency_tolerance: float = 300.0,
        beep_duration: float = 0.5,
        beep_interval: float = 3.0,
        confidence_threshold: int = 3,
        min_beep_duration: float = 0.3,  # Minimum duration to be considered a smoke alarm beep
        max_beep_duration: float = 1.5   # Maximum duration for a single beep
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.target_frequency = target_frequency
        self.frequency_tolerance = frequency_tolerance
        self.beep_duration = beep_duration
        self.beep_interval = beep_interval
        self.confidence_threshold = confidence_threshold
        self.min_beep_duration = min_beep_duration
        self.max_beep_duration = max_beep_duration
        
        # Live monitoring state
        self.audio_buffer = deque(maxlen=int(sample_rate * 10))  # 10 seconds buffer
        self.stop_event = Event()
        
        # Detection state
        self.beep_timestamps = deque(maxlen=10)
    
    def reset_state(self):
        """Reset detection state."""
        self.beep_timestamps.clear()
    
    def process_audio_chunk(self, audio_data: np.ndarray, timestamp: Optional[float] = None) -> bool:
        """
        Process an audio chunk and return True if a smoke alarm pattern is detected.
        
        Args:
            audio_data: Audio data chunk
            timestamp: Absolute timestamp for the chunk (for file processing)
            
        Returns:
            True if smoke alarm detected in this chunk
        """
        # Apply window function
        windowed = audio_data * signal.windows.hann(len(audio_data))
        
        # Compute FFT
        fft = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(len(windowed), 1/self.sample_rate)
        magnitudes = np.abs(fft)
        
        # Find peak frequency in target range
        target_range = (
            self.target_frequency - self.frequency_tolerance,
            self.target_frequency + self.frequency_tolerance
        )
        mask = (freqs >= target_range[0]) & (freqs <= target_range[1])
        
        if not np.any(mask):
            return False
            
        target_magnitudes = magnitudes[mask]
        target_freqs = freqs[mask]
        
        # Check if there's a strong peak in target frequency range
        peak_idx = np.argmax(target_magnitudes)
        peak_magnitude = target_magnitudes[peak_idx]
        peak_frequency = target_freqs[peak_idx]
        
        # Calculate signal strength relative to background noise
        background_mask = ~mask
        if np.any(background_mask):
            background_noise = np.mean(magnitudes[background_mask])
        else:
            background_noise = np.mean(magnitudes) * 0.1  # Fallback
        
        signal_to_noise = peak_magnitude / (background_noise + 1e-10)
        
        # More reasonable thresholds for beep detection
        magnitude_threshold = np.percentile(magnitudes, 90)  # Top 10% of frequencies
        
        if (signal_to_noise > 10.0 and  # Reasonable SNR threshold
            peak_magnitude > magnitude_threshold * 2.0 and  # Strong absolute signal
            peak_magnitude > np.mean(magnitudes) * 15):  # Strong signal check
            
            # Use provided timestamp or current time
            current_time = timestamp if timestamp is not None else time.time()
            return self._record_beep(current_time, peak_frequency, signal_to_noise)
        
        return False
    
    def _record_beep(self, timestamp: float, frequency: float, strength: float) -> bool:
        """
        Record a beep detection and check for alarm pattern.
        
        Returns:
            True if smoke alarm pattern is detected
        """
        # Consolidate consecutive beeps - if this beep is within 1 second of the last one,
        # consider it the same beep and don't add a new timestamp
        consolidation_window = 1.0  # seconds
        if (len(self.beep_timestamps) > 0 and 
            timestamp - self.beep_timestamps[-1] < consolidation_window):
            # This is part of the same beep, don't add a new timestamp
            pass
        else:
            # This is a new beep
            self.beep_timestamps.append(timestamp)
        
        # Check for alarm pattern - need at least 3 beeps for reliable pattern detection
        if len(self.beep_timestamps) >= max(3, self.confidence_threshold):
            intervals = []
            for i in range(1, len(self.beep_timestamps)):
                intervals.append(self.beep_timestamps[i] - self.beep_timestamps[i-1])
            
            # Analyze the last several intervals for consistency
            recent_intervals = intervals[-4:] if len(intervals) >= 4 else intervals[-3:]
            
            if len(recent_intervals) >= 3:
                avg_interval = np.mean(recent_intervals)
                interval_std = np.std(recent_intervals)
                
                # Reasonable pattern matching for smoke alarms
                if (2.5 <= avg_interval <= 4.5 and  # Typical smoke alarm interval range
                    interval_std < 3.0 and  # Allow more timing variation for real-world conditions
                    strength > 15.0 and  # Reasonable signal strength requirement
                    self.target_frequency - self.frequency_tolerance <= frequency <= self.target_frequency + self.frequency_tolerance):
                    
                    # Additional check: ensure we have sustained pattern
                    min_beeps_in_sequence = 3  # Reduced from 4 to 3
                    if len(self.beep_timestamps) >= min_beeps_in_sequence:
                        return True
        
        return False
    
    def get_detection_info(self) -> dict:
        """Get information about the last detection."""
        if len(self.beep_timestamps) < 4:
            return {}
        
        # Calculate recent intervals
        intervals = []
        for i in range(1, len(self.beep_timestamps)):
            intervals.append(self.beep_timestamps[i] - self.beep_timestamps[i-1])
        
        recent_intervals = intervals[-4:] if len(intervals) >= 4 else intervals[-3:]
        
        return {
            'avg_interval': np.mean(recent_intervals),
            'interval_std': np.std(recent_intervals),
            'beep_count': len(self.beep_timestamps),
            'last_timestamp': self.beep_timestamps[-1] if self.beep_timestamps else None
        }

    def audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Audio callback for live monitoring."""
        if status:
            print(f"Audio callback status: {status}")
        
        # Convert to mono if stereo
        audio_data = indata[:, 0] if indata.ndim > 1 else indata
        self.audio_buffer.extend(audio_data)
        
        # Process audio chunk
        if self.process_audio_chunk(audio_data):
            detection_info = self.get_detection_info()
            self._trigger_alarm(
                self.target_frequency,
                40.0,  # Default strength for live detection
                detection_info.get('avg_interval', 3.0)
            )
    
    def _trigger_alarm(self, frequency: float, strength: float, interval: float) -> None:
        """Trigger alarm notification."""
        print(f"\n🚨 SMOKE ALARM DETECTED! 🚨")
        print(f"Frequency: {frequency:.1f} Hz")
        print(f"Signal Strength: {strength:.2f}")
        print(f"Beep Interval: {interval:.2f}s")
        print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 50)
    
    def start_monitoring(self) -> None:
        """Start live audio monitoring."""
        print("🎤 Starting smoke alarm detection...")
        print(f"Listening for alarms at ~{self.target_frequency}Hz")
        print("Press Ctrl+C to stop")
        
        try:
            with sd.InputStream(
                callback=self.audio_callback,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size
            ):
                while not self.stop_event.is_set():
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            print("\n🛑 Stopping smoke alarm detection...")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def stop_monitoring(self) -> None:
        """Stop live monitoring."""
        self.stop_event.set()

    def process_audio_file(self, audio_file: Path, verbose: bool = True) -> List[Dict]:
        """Process an audio file and return list of detected alarms with timestamps."""
        if verbose:
            print(f"🎵 Processing audio file: {audio_file.name}")
        
        # Load audio file
        try:
            audio_data, sr = librosa.load(audio_file, sr=self.sample_rate, mono=True)
        except Exception as e:
            print(f"❌ Error loading audio file: {e}")
            return []
        
        # Reset detection state
        self.reset_state()
        detections = []
        
        # Process audio in chunks
        chunk_samples = self.chunk_size
        total_chunks = len(audio_data) // chunk_samples
        
        if verbose:
            print(f"   Duration: {len(audio_data) / sr:.1f}s")
            print(f"   Processing {total_chunks} chunks...")
        
        for i in range(0, len(audio_data) - chunk_samples, chunk_samples):
            chunk = audio_data[i:i + chunk_samples]
            chunk_start_time = i / sr
            
            # Process chunk with timestamp
            if self.process_audio_chunk(chunk, chunk_start_time):
                # Calculate actual detection time
                detection_time = chunk_start_time + (chunk_samples / sr / 2)  # Middle of chunk
                
                # Consolidate detections - avoid duplicates within 5 seconds
                consolidation_window = 5.0  # seconds
                if not detections or detection_time - detections[-1]['timestamp'] > consolidation_window:
                    detections.append({
                        'timestamp': detection_time,
                        'frequency': self.target_frequency,
                        'confidence': 1.0  # Could calculate actual confidence
                    })
        
        if verbose:
            if detections:
                print(f"   ✅ Found {len(detections)} smoke alarm detections:")
                for i, detection in enumerate(detections, 1):
                    print(f"      {i}. {detection['timestamp']:.1f}s")
            else:
                print(f"   ℹ️  No smoke alarms detected")
        
        return detections