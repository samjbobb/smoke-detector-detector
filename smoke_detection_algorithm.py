#!/usr/bin/env python3
"""
Smoke alarm detection algorithm and detector class.
This module contains the complete smoke alarm detection logic used by both live monitoring and file processing.
"""

import numpy as np
from scipy import signal
import time
from collections import deque
from typing import Optional, Dict, Callable


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
        
        # Detection callback
        self.detection_callback: Optional[Callable[[Dict], None]] = None
        
        # Detection state
        self.beep_timestamps = deque(maxlen=10)
    
    def reset_state(self):
        """Reset detection state."""
        self.beep_timestamps.clear()
    
    def process_audio_chunk(self, audio_data: np.ndarray, timestamp: Optional[float] = None) -> Optional[Dict]:
        """
        Process an audio chunk and return detection info if a smoke alarm pattern is detected.
        
        Args:
            audio_data: Audio data chunk
            timestamp: Absolute timestamp for the chunk (for file processing)
            
        Returns:
            Detection dict if smoke alarm detected, None otherwise
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
        
        return None
    
    def _record_beep(self, timestamp: float, frequency: float, strength: float) -> Optional[Dict]:
        """
        Record a beep detection and check for alarm pattern.
        
        Returns:
            Detection dict if smoke alarm pattern is detected, None otherwise
        """
        # Consolidate consecutive beeps - if this beep is within consolidation window of the last one,
        # consider it the same beep and don't add a new timestamp
        consolidation_window = 1.0  # seconds - unified for both live and file processing
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
                        return {
                            'timestamp': timestamp,
                            'frequency': frequency,
                            'strength': strength,
                            'confidence': 1.0,
                            'beep_count': len(self.beep_timestamps),
                            'avg_interval': avg_interval
                        }
        
        return None
    
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

    def set_detection_callback(self, callback: Callable[[Dict], None]) -> None:
        """Set callback function to be called when detection occurs."""
        self.detection_callback = callback
    
    def process_audio_stream(self, audio_data: np.ndarray, timestamp: Optional[float] = None) -> Optional[Dict]:
        """Process audio stream chunk and trigger callback if detection occurs.
        
        This is the main method both live monitoring and file processing should use.
        
        Args:
            audio_data: Audio data chunk
            timestamp: Timestamp for the chunk (defaults to current time)
            
        Returns:
            Detection dict if alarm detected, None otherwise
        """
        detection = self.process_audio_chunk(audio_data, timestamp)
        if detection and self.detection_callback:
            self.detection_callback(detection)
        return detection
    

