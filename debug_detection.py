#!/usr/bin/env python3
"""
Debug version of smoke detection to understand what's happening.
"""
import argparse

import numpy as np
from scipy import signal
import librosa
from pathlib import Path
from collections import deque

class DebugSmokeAlarmDetector:
    """Debug version with detailed logging."""
    
    def __init__(
        self,
        sample_rate: int = 44100,
        chunk_size: int = 4096,
        target_frequency: float = 3200.0,
        frequency_tolerance: float = 300.0,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.target_frequency = target_frequency
        self.frequency_tolerance = frequency_tolerance
        self.beep_timestamps = deque(maxlen=10)
        self.debug_beeps_recorded = []
    
    def debug_audio_file(self, audio_file: Path):
        """Debug process an audio file."""
        print(f"🔍 DEBUG: Processing {audio_file.name}")
        
        # Load audio file
        audio_data, sr = librosa.load(audio_file, sr=self.sample_rate, mono=True)
        print(f"   Audio length: {len(audio_data)} samples, {len(audio_data)/sr:.1f}s")
        
        # Process chunks and show what we find
        chunk_samples = self.chunk_size
        total_chunks = len(audio_data) // chunk_samples
        
        potential_beeps = []
        
        for i in range(0, len(audio_data) - chunk_samples, chunk_samples):
            chunk = audio_data[i:i + chunk_samples]
            chunk_start_time = i / sr
            
            result = self.debug_chunk(chunk, chunk_start_time)
            if result:
                potential_beeps.append(result)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total chunks processed: {total_chunks}")
        print(f"   Potential beeps found: {len(potential_beeps)}")
        
        if potential_beeps:
            print(f"\n🔊 POTENTIAL BEEPS:")
            for i, beep in enumerate(potential_beeps, 1):
                print(f"   {i}. Time: {beep['time']:.1f}s, Freq: {beep['frequency']:.1f}Hz, SNR: {beep['snr']:.1f}, Peak: {beep['peak_mag']:.1f}")
        
        return potential_beeps
    
    def debug_chunk(self, audio_data: np.ndarray, timestamp: float):
        """Debug process a single chunk."""
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
            return None
            
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
            background_noise = np.mean(magnitudes) * 0.1
        
        signal_to_noise = peak_magnitude / (background_noise + 1e-10)
        
        # Current algorithm thresholds (updated)
        magnitude_threshold = np.percentile(magnitudes, 90)
        mean_magnitude = np.mean(magnitudes)
        
        # Check if this would pass the current criteria
        passes_snr = signal_to_noise > 10.0
        passes_percentile = peak_magnitude > magnitude_threshold * 2.0
        passes_mean = peak_magnitude > mean_magnitude * 15
        
        # Log if we find anything interesting in the target frequency range
        if signal_to_noise > 5.0 and peak_magnitude > mean_magnitude * 10:  # Much lower thresholds for logging
            result = {
                'time': timestamp,
                'frequency': peak_frequency,
                'peak_mag': peak_magnitude,
                'snr': signal_to_noise,
                'magnitude_threshold_95': magnitude_threshold,
                'mean_magnitude': mean_magnitude,
                'passes_snr_25': passes_snr,
                'passes_percentile_4x': passes_percentile, 
                'passes_mean_100x': passes_mean,
                'would_detect': passes_snr and passes_percentile and passes_mean
            }
            
            # If this passes all thresholds, simulate recording beep
            if passes_snr and passes_percentile and passes_mean:
                detected = self._debug_record_beep(timestamp, peak_frequency, signal_to_noise)
                if detected:
                    print(f"   🚨 SMOKE ALARM DETECTED at {timestamp:.1f}s! 🚨")
                    
            # Only print every 10th potential beep to avoid spam
            if len(self.debug_beeps_recorded) % 10 == 0:
                print(f"   🔍 Time: {timestamp:.1f}s, Freq: {peak_frequency:.1f}Hz, SNR: {signal_to_noise:.1f}")
                print(f"       Peak: {peak_magnitude:.1f}, Threshold95: {magnitude_threshold:.1f}, Mean: {mean_magnitude:.1f}")
                print(f"       Passes - SNR>10: {passes_snr}, Peak>2xThresh: {passes_percentile}, Peak>15xMean: {passes_mean}")
            
            return result
        
        return None
    
    def _debug_record_beep(self, timestamp: float, frequency: float, strength: float) -> bool:
        """Debug version of beep recording with pattern matching."""
        # Add beep timestamp
        self.beep_timestamps.append(timestamp)
        self.debug_beeps_recorded.append({'time': timestamp, 'freq': frequency, 'strength': strength})
        
        print(f"       🎯 Recorded beep at {timestamp:.1f}s (total: {len(self.beep_timestamps)})")
        
        # Check for alarm pattern - need at least 3 beeps for pattern detection
        if len(self.beep_timestamps) >= 3:
            intervals = []
            for i in range(1, len(self.beep_timestamps)):
                intervals.append(self.beep_timestamps[i] - self.beep_timestamps[i-1])
            
            # Analyze the last several intervals for consistency
            recent_intervals = intervals[-3:] if len(intervals) >= 3 else intervals
            
            if len(recent_intervals) >= 2:  # Changed from 3 to 2
                avg_interval = np.mean(recent_intervals)
                interval_std = np.std(recent_intervals) if len(recent_intervals) > 1 else 0
                
                print(f"       📊 Pattern analysis: avg_interval={avg_interval:.2f}s, std={interval_std:.2f}")
                print(f"       📊 Recent intervals: {[f'{x:.2f}' for x in recent_intervals]}")
                
                # Reasonable pattern matching for smoke alarms
                if (2.5 <= avg_interval <= 4.5 and  # Typical smoke alarm interval range
                    interval_std < 0.8 and  # Allow some timing variation
                    strength > 15.0 and  # Reasonable signal strength requirement
                    self.target_frequency - self.frequency_tolerance <= frequency <= self.target_frequency + self.frequency_tolerance):
                    
                    print(f"       ✅ Pattern matches smoke alarm criteria!")
                    return True
                else:
                    print(f"       ❌ Pattern doesn't match: interval={avg_interval:.2f} (need 2.5-4.5), std={interval_std:.2f} (need <0.8), strength={strength:.1f} (need >15)")
        
        return False

def main():
    parser = argparse.ArgumentParser(description="Debug Detection")
    parser.add_argument("file", type=Path, help="Process audio file")

    args = parser.parse_args()

    detector = DebugSmokeAlarmDetector()

    test_file = Path(args.file)
    if test_file.exists():
        detector.debug_audio_file(test_file)
    else:
        print(f"Test file not found: {test_file}")

if __name__ == "__main__":
    main()