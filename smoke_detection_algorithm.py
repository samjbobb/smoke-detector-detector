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
        sample_rate: int = 44100,  # Hz - Audio sampling rate (44.1 kHz standard)
        chunk_size: int = 4096,  # samples - FFT window size, determines frequency resolution (~10.8 Hz at 44.1 kHz)
        target_frequency: float = 3200.0,  # Hz - Typical smoke alarm beep frequency (3.2 kHz)
        frequency_tolerance: float = 400.0,  # Hz - Frequency search range (±400 Hz around target)
        ambient_learning_time: float = 10.0,  # seconds - Time to learn background noise levels at startup
        alarm_sustain_threshold: float = 4.0,  # seconds - Required duration of sustained signal for alarm detection
        alarm_latch_time: float = 300.0,  # seconds - Cooldown period after alarm (5 minutes) to prevent spam
        min_signal_ratio: float = 75.0,  # ratio - Minimum signal-to-background strength required (dimensionless)
        frequency_occupation_threshold: float = 0.25  # ratio - Minimum fraction of time frequency must be present (25%)
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.target_frequency = target_frequency
        self.frequency_tolerance = frequency_tolerance
        self.ambient_learning_time = ambient_learning_time
        self.alarm_sustain_threshold = alarm_sustain_threshold
        self.alarm_latch_time = alarm_latch_time
        self.min_signal_ratio = min_signal_ratio
        self.frequency_occupation_threshold = frequency_occupation_threshold
        
        # Detection callback
        self.detection_callback: Optional[Callable[[Dict], None]] = None
        
        # State tracking for improved algorithm
        self.start_time: Optional[float] = None
        self.ambient_background_level = 0.0
        self.ambient_samples_count = 0
        self.is_learning_ambient = True
        
        # Track detection windows for sustained signal analysis
        self.detection_windows = deque(maxlen=100)  # samples - Store recent detection results (circular buffer)
        self.last_alarm_time: Optional[float] = None
        self.is_alarm_latched = False
        
        # Legacy compatibility
        self.beep_timestamps = deque(maxlen=10)  # samples - Legacy beep timestamp storage (10 most recent)
    
    
    def process_audio_chunk(self, audio_data: np.ndarray, timestamp: Optional[float] = None) -> Optional[Dict]:
        """
        Process an audio chunk and return detection info if a smoke alarm pattern is detected.
        
        Args:
            audio_data: Audio data chunk
            timestamp: Absolute timestamp for the chunk (for file processing)
            
        Returns:
            Detection dict if smoke alarm detected, None otherwise
        """
        current_time = timestamp if timestamp is not None else time.time()
        
        # Initialize start time on first chunk
        if self.start_time is None:
            self.start_time = current_time
        
        # Check if we're in alarm latch period
        if self.is_alarm_latched and self.last_alarm_time:
            if current_time - self.last_alarm_time < self.alarm_latch_time:
                return None  # Still in latch period
            else:
                self.is_alarm_latched = False  # Reset latch
        
        # Apply window function to reduce spectral leakage
        windowed = audio_data * signal.windows.hann(len(audio_data))
        
        # Compute FFT
        fft = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(len(windowed), 1/self.sample_rate)
        magnitudes = np.abs(fft)
        
        # Calculate overall background level (excluding target frequency)
        target_range = (
            self.target_frequency - self.frequency_tolerance,
            self.target_frequency + self.frequency_tolerance
        )
        mask = (freqs >= target_range[0]) & (freqs <= target_range[1])
        background_mask = ~mask
        
        if np.any(background_mask):
            current_background = np.mean(magnitudes[background_mask])
        else:
            current_background = np.mean(magnitudes) * 0.1  # ratio - Fallback: 10% of average magnitude as background estimate
        
        # Learn ambient levels during startup
        time_since_start = current_time - self.start_time
        if self.is_learning_ambient and time_since_start < self.ambient_learning_time:
            self.ambient_background_level = (
                self.ambient_background_level * self.ambient_samples_count + current_background
            ) / (self.ambient_samples_count + 1)
            self.ambient_samples_count += 1
            return None  # Don't detect during learning phase
        elif self.is_learning_ambient:
            self.is_learning_ambient = False  # Done learning
        
        # Analyze target frequency range
        if not np.any(mask):
            self._record_detection_window(current_time, False, 0.0, 0.0, 0.0)
            return None
            
        target_magnitudes = magnitudes[mask]
        target_freqs = freqs[mask]
        
        # Find peak in target frequency range
        peak_idx = np.argmax(target_magnitudes)
        peak_magnitude = target_magnitudes[peak_idx]
        peak_frequency = target_freqs[peak_idx]
        
        # Calculate metrics for alarm detection
        signal_to_background = peak_magnitude / (self.ambient_background_level + 1e-10)  # ratio - Add small epsilon to prevent division by zero
        signal_to_current = peak_magnitude / (current_background + 1e-10)  # ratio - Prevents division by zero with small epsilon
        
        # Check if signal is strong enough with more stringent criteria
        is_strong_signal = (
            signal_to_background > self.min_signal_ratio and
            signal_to_current > 8.0 and  # ratio - Signal must be 8x stronger than current background noise
            peak_magnitude > np.mean(magnitudes) * 12.0  # ratio - Peak must be 12x the average FFT magnitude
        )
        
        # Record this detection window
        self._record_detection_window(current_time, is_strong_signal, peak_frequency, 
                                      signal_to_background, peak_magnitude)
        
        # Analyze sustained signal over recent time window
        return self._analyze_sustained_detection(current_time, peak_frequency, signal_to_background)
    
    def _record_detection_window(self, timestamp: float, is_strong_signal: bool, 
                                 frequency: float, signal_ratio: float, magnitude: float) -> None:
        """Record a detection window result for sustained analysis."""
        self.detection_windows.append({
            'timestamp': timestamp,
            'is_strong_signal': is_strong_signal,
            'frequency': frequency,
            'signal_ratio': signal_ratio,
            'magnitude': magnitude
        })
    
    def _analyze_sustained_detection(self, current_time: float, peak_frequency: float, 
                                     signal_ratio: float) -> Optional[Dict]:
        """
        Analyze recent detection windows for sustained smoke alarm signal.
        
        This replaces the 3-beep pattern detection with frequency/loudness/time-domain analysis.
        """
        if len(self.detection_windows) < 5:  # samples - Need minimum detection history for analysis
            return None
        
        # Analyze recent window (last N seconds)
        analysis_window = self.alarm_sustain_threshold
        recent_detections = [
            d for d in self.detection_windows 
            if current_time - d['timestamp'] <= analysis_window
        ]
        
        if len(recent_detections) < 3:  # samples - Need minimum samples in analysis window for reliable detection
            return None
        
        # Calculate metrics over the analysis window
        strong_signal_count = sum(1 for d in recent_detections if d['is_strong_signal'])
        total_detections = len(recent_detections)
        frequency_occupation_ratio = strong_signal_count / total_detections
        
        # Get frequency consistency
        strong_detections = [d for d in recent_detections if d['is_strong_signal']]
        if len(strong_detections) < 2:  # samples - Need at least 2 strong signals for frequency consistency analysis
            return None
            
        frequencies = [d['frequency'] for d in strong_detections]
        freq_std = np.std(frequencies)
        avg_frequency = np.mean(frequencies)
        avg_signal_ratio = np.mean([d['signal_ratio'] for d in strong_detections])
        
        # Enhanced alarm detection criteria with better discrimination
        # 1. High frequency occupation (signal present most of the time)
        # 2. Consistent frequency (not random noise)
        # 3. Strong signal relative to ambient background
        # 4. Sustained over minimum time period
        # 5. Consistent signal strength (not just noise spikes)
        # 6. Temporal pattern analysis (not constant presence)
        
        signal_ratios = [d['signal_ratio'] for d in strong_detections]
        signal_ratio_std = np.std(signal_ratios) if len(signal_ratios) > 1 else 0.0
        
        # Check for temporal variation (smoke alarms often have pulses, not constant tones)
        # If occupation is too high (near 100%), it might be music or constant noise
        is_reasonable_occupation = 0.20 <= frequency_occupation_ratio <= 0.80  # ratio - 20-80% occupation range for realistic alarm patterns
        
        # Check signal strength variation - smoke alarms often have some variation
        signal_strength_variation = signal_ratio_std / (avg_signal_ratio + 1e-10)  # ratio - Coefficient of variation (dimensionless)
        has_reasonable_variation = 0.1 <= signal_strength_variation <= 2.0  # ratio - 10-200% variation range for natural alarm signals
        
        # Exclude sounds that are too consistent (like pure tones) OR too inconsistent (like noise/music)
        # Sweet spot: some variation but not too much
        has_appropriate_consistency = (
            ((10.0 < freq_std < 100.0) or (freq_std <= 10.0 and avg_signal_ratio > 500)) and  # Hz - Allow 10-100 Hz variation OR very strong consistent signals
            (0.2 < signal_strength_variation < 1.2)  # ratio - 20-120% strength variation for realistic alarms
        )
        
        alarm_detected = (
            frequency_occupation_ratio >= self.frequency_occupation_threshold and
            is_reasonable_occupation and  # Not constant presence
            avg_signal_ratio > self.min_signal_ratio and
            has_reasonable_variation and  # Some strength variation expected  
            has_appropriate_consistency and  # Proper frequency and strength consistency
            self.target_frequency - self.frequency_tolerance <= avg_frequency <= self.target_frequency + self.frequency_tolerance and
            len(strong_detections) >= 5  # samples - Need at least 5 strong detections for sustained alarm confirmation
        )
        
        if alarm_detected:
            # Set latch to prevent immediate re-triggering
            self.last_alarm_time = current_time
            self.is_alarm_latched = True
            
            return {
                'timestamp': current_time,
                'frequency': avg_frequency,
                'strength': avg_signal_ratio,
                'confidence': min(1.0, frequency_occupation_ratio * 2.0),  # ratio - Confidence score (0-1), capped at 100%
                'detection_type': 'sustained_frequency',
                'frequency_occupation': frequency_occupation_ratio,
                'analysis_window': analysis_window
            }
        
        return None
    
    def _record_beep(self, timestamp: float, frequency: float, strength: float) -> Optional[Dict]:
        """Legacy method maintained for compatibility."""
        # For compatibility with existing code, but the new algorithm doesn't use this
        self.beep_timestamps.append(timestamp)
        return None
    
    def get_detection_info(self) -> dict:
        """Get information about the current detection state."""
        if len(self.detection_windows) < 2:
            return {}
        
        # Get info about recent detection windows
        recent_windows = list(self.detection_windows)[-10:]  # samples - Analyze last 10 detection windows for status
        strong_signals = [d for d in recent_windows if d['is_strong_signal']]
        
        if not strong_signals:
            return {
                'ambient_background_level': self.ambient_background_level,
                'is_learning_ambient': self.is_learning_ambient,
                'detection_windows_count': len(recent_windows),
                'strong_signals_count': 0
            }
        
        frequencies = [d['frequency'] for d in strong_signals]
        signal_ratios = [d['signal_ratio'] for d in strong_signals]
        
        return {
            'ambient_background_level': self.ambient_background_level,
            'is_learning_ambient': self.is_learning_ambient,
            'detection_windows_count': len(recent_windows),
            'strong_signals_count': len(strong_signals),
            'avg_frequency': np.mean(frequencies),
            'frequency_std': np.std(frequencies) if len(frequencies) > 1 else 0.0,
            'avg_signal_ratio': np.mean(signal_ratios),
            'last_timestamp': recent_windows[-1]['timestamp'],
            'is_alarm_latched': self.is_alarm_latched,
            'last_alarm_time': self.last_alarm_time
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
    

