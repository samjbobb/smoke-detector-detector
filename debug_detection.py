#!/usr/bin/env -S uv run --script
"""
Debug version of smoke detection to understand what's happening.
Uses the main algorithm with instrumentation hooks to eliminate code duplication.
"""
import argparse

import numpy as np
import librosa
from pathlib import Path
from smoke_detection_algorithm import SmokeAlarmDetector

class DebugSmokeAlarmDetector:
    """Debug version with detailed logging using instrumentation hooks."""
    
    def __init__(
        self,
        sample_rate: int = 44100,
        chunk_size: int = 4096,
        target_frequency: float = 3200.0,
        frequency_tolerance: float = 300.0,
    ):
        self.potential_beeps = []
        self.debug_output_count = 0
        
        # Create main detector and set instrumentation hooks
        self.detector = SmokeAlarmDetector(
            sample_rate=sample_rate,
            chunk_size=chunk_size,
            target_frequency=target_frequency,
            frequency_tolerance=frequency_tolerance
        )
        
        # Set instrumentation hooks using setter method
        self.detector.set_instrumentation_hooks(
            on_chunk_analyzed=self._on_chunk_analyzed,
            on_peak_found=self._on_peak_found,
            on_signal_strength_calculated=self._on_signal_strength_calculated,
            on_detection_recorded=self._on_detection_recorded,
            on_sustained_analysis=self._on_sustained_analysis
        )
    
    def _on_chunk_analyzed(self, data):
        """Called when FFT analysis is complete for a chunk."""
        pass  # Basic FFT data available but not needed for current debug output
    
    def _on_peak_found(self, data):
        """Called when a peak is found in target frequency range."""
        pass  # Peak data available but processed in signal strength callback
    
    def _on_signal_strength_calculated(self, data):
        """Called when signal strength calculations are complete."""
        timestamp = data['timestamp']
        peak_frequency = data['peak_frequency']
        peak_magnitude = data['peak_magnitude']
        signal_to_background = data['signal_to_background']
        signal_to_current = data['signal_to_current']
        magnitude_threshold_90 = data['magnitude_threshold_90']
        mean_magnitude = data['mean_magnitude']
        
        # Similar thresholds to original debug version for comparison
        passes_snr = signal_to_background > 10.0
        passes_percentile = peak_magnitude > magnitude_threshold_90 * 2.0
        passes_mean = peak_magnitude > mean_magnitude * 15
        
        # Log if we find anything interesting (lower threshold for logging)
        if signal_to_background > 5.0 and peak_magnitude > mean_magnitude * 10:
            result = {
                'time': timestamp,
                'frequency': peak_frequency,
                'peak_mag': peak_magnitude,
                'snr': signal_to_background,
                'magnitude_threshold_90': magnitude_threshold_90,
                'mean_magnitude': mean_magnitude,
                'passes_snr_10': passes_snr,
                'passes_percentile_2x': passes_percentile, 
                'passes_mean_15x': passes_mean,
                'would_detect': passes_snr and passes_percentile and passes_mean
            }
            
            self.potential_beeps.append(result)
            
            # Only print every 10th potential beep to avoid spam
            if len(self.potential_beeps) % 10 == 0:
                print(f"   🔍 Time: {timestamp:.1f}s, Freq: {peak_frequency:.1f}Hz, SNR: {signal_to_background:.1f}")
                print(f"       Peak: {peak_magnitude:.1f}, Threshold90: {magnitude_threshold_90:.1f}, Mean: {mean_magnitude:.1f}")
                print(f"       Passes - SNR>10: {passes_snr}, Peak>2xThresh: {passes_percentile}, Peak>15xMean: {passes_mean}")
    
    def _on_detection_recorded(self, data):
        """Called when a detection window is recorded."""
        if data['is_strong_signal']:
            print(f"       🎯 Recorded strong signal at {data['timestamp']:.1f}s (total windows: {data['total_detection_windows']})")
    
    def _on_sustained_analysis(self, data):
        """Called when sustained analysis is performed."""
        if data['alarm_detected']:
            print(f"   🚨 SMOKE ALARM DETECTED at {data['timestamp']:.1f}s! 🚨")
            print(f"       Frequency occupation: {data['frequency_occupation_ratio']:.2f}, Avg frequency: {data['avg_frequency']:.1f}Hz")
    
    def debug_audio_file(self, audio_file: Path):
        """Debug process an audio file using main detector with hooks."""
        print(f"🔍 DEBUG: Processing {audio_file.name}")
        
        # Load audio file
        audio_data, sr = librosa.load(audio_file, sr=self.detector.sample_rate, mono=True)
        print(f"   Audio length: {len(audio_data)} samples, {len(audio_data)/sr:.1f}s")
        
        # Process chunks using main detector
        chunk_samples = self.detector.chunk_size
        total_chunks = len(audio_data) // chunk_samples
        
        for i in range(0, len(audio_data) - chunk_samples, chunk_samples):
            chunk = audio_data[i:i + chunk_samples]
            chunk_start_time = i / sr
            
            # Process chunk using main detector (which will call our hooks)
            detection = self.detector.process_audio_chunk(chunk, chunk_start_time)
            
        print(f"\n📊 SUMMARY:")
        print(f"   Total chunks processed: {total_chunks}")
        print(f"   Potential beeps found: {len(self.potential_beeps)}")
        
        if self.potential_beeps:
            print(f"\n🔊 POTENTIAL BEEPS:")
            for i, beep in enumerate(self.potential_beeps, 1):
                print(f"   {i}. Time: {beep['time']:.1f}s, Freq: {beep['frequency']:.1f}Hz, SNR: {beep['snr']:.1f}, Peak: {beep['peak_mag']:.1f}")
        
        return self.potential_beeps

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