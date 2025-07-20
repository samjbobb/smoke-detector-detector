#!/usr/bin/env python3
"""
Simple audio analysis tool for smoke detector debugging.
Analyzes frequency content at specific time points without requiring matplotlib.
"""

import numpy as np
import librosa
import sys
from pathlib import Path

def analyze_audio_at_timepoints(audio_file: str, timepoints: list):
    """Analyze frequency content at specific time points."""
    audio_path = Path(audio_file)
    
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}")
        return
    
    print(f"Loading audio file: {audio_path}")
    
    # Load audio
    y, sr = librosa.load(audio_path, sr=48000)
    duration = len(y) / sr
    
    print(f"Duration: {duration:.1f}s")
    print(f"Sample rate: {sr} Hz")
    print(f"Audio samples: {len(y)}")
    
    # Analyze each timepoint
    window_size = 2048  # ~43ms at 48kHz
    
    for i, time_point in enumerate(timepoints):
        print(f"\n{'='*60}")
        print(f"ANALYSIS AT {time_point:.1f}s")
        print(f"{'='*60}")
        
        # Get sample index
        sample_idx = int(time_point * sr)
        
        if sample_idx + window_size >= len(y):
            print(f"⚠️  Time point beyond audio duration")
            continue
        
        # Extract window
        window = y[sample_idx:sample_idx + window_size]
        
        # Apply window function to reduce spectral leakage
        windowed = window * np.hanning(window_size)
        
        # Compute FFT
        fft = np.fft.fft(windowed)
        fft_mag = np.abs(fft)
        freqs = np.fft.fftfreq(window_size, 1/sr)
        
        # Only analyze positive frequencies
        positive_mask = freqs >= 0
        pos_freqs = freqs[positive_mask]
        pos_mags = fft_mag[positive_mask]
        
        # Find peak frequencies
        peak_indices = []
        for j in range(1, len(pos_mags) - 1):
            if pos_mags[j] > pos_mags[j-1] and pos_mags[j] > pos_mags[j+1]:
                # Only consider significant peaks
                if pos_mags[j] > 0.1 * np.max(pos_mags):
                    peak_indices.append(j)
        
        # Sort peaks by magnitude
        peak_indices = sorted(peak_indices, key=lambda x: pos_mags[x], reverse=True)
        
        print(f"Top frequency peaks:")
        for idx in peak_indices[:10]:  # Show top 10 peaks
            freq = pos_freqs[idx]
            mag = pos_mags[idx]
            mag_db = 20 * np.log10(mag) if mag > 0 else -np.inf
            print(f"   {freq:6.1f} Hz: {mag_db:6.1f} dB")
        
        # Check energy in smoke detector frequency ranges
        print(f"\nEnergy analysis:")
        
        ranges = [
            (2800, 3200, "Typical smoke alarm range"),
            (2000, 4000, "Extended smoke alarm range"), 
            (1000, 2000, "Low frequency range"),
            (4000, 8000, "High frequency range"),
            (100, 1000, "Very low frequency range")
        ]
        
        for low_freq, high_freq, label in ranges:
            mask = (pos_freqs >= low_freq) & (pos_freqs <= high_freq)
            if np.any(mask):
                energy = np.sum(pos_mags[mask] ** 2)
                energy_db = 10 * np.log10(energy) if energy > 0 else -np.inf
                max_in_range = np.max(pos_mags[mask]) if np.any(mask) else 0
                max_db = 20 * np.log10(max_in_range) if max_in_range > 0 else -np.inf
                print(f"   {label:25s}: Energy = {energy_db:6.1f} dB, Peak = {max_db:6.1f} dB")
        
        # Check for tonal components (typical of smoke alarms)
        print(f"\nTonal analysis:")
        
        # Look for strong narrow peaks that could be smoke alarms
        smoke_candidates = []
        for idx in peak_indices[:5]:  # Check top 5 peaks
            freq = pos_freqs[idx]
            mag = pos_mags[idx]
            
            if 2000 <= freq <= 4000:  # In smoke detector range
                # Check if it's a narrow peak (tonal)
                # Look at neighboring bins to see if it's narrow
                left_mag = pos_mags[max(0, idx-2)] if idx >= 2 else 0
                right_mag = pos_mags[min(len(pos_mags)-1, idx+2)] if idx < len(pos_mags)-2 else 0
                avg_neighbor = (left_mag + right_mag) / 2
                
                if mag > 2 * avg_neighbor:  # Peak is significantly higher than neighbors
                    smoke_candidates.append((freq, mag))
                    
        if smoke_candidates:
            print(f"   Potential smoke alarm tones:")
            for freq, mag in smoke_candidates:
                mag_db = 20 * np.log10(mag) if mag > 0 else -np.inf
                print(f"      {freq:6.1f} Hz at {mag_db:6.1f} dB")
        else:
            print(f"   No strong tonal components found in smoke detector range")
        
        # RMS level analysis
        rms = np.sqrt(np.mean(window ** 2))
        rms_db = 20 * np.log10(rms) if rms > 0 else -np.inf
        print(f"\nOverall RMS level: {rms_db:.1f} dB")

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_audio.py <audio_file> [time1] [time2] ...")
        print("Example: python analyze_audio.py test_audio/recording_20250720_093110.wav 45 70.3")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    
    # Parse time points from command line, or use defaults for the failing test
    if len(sys.argv) > 2:
        timepoints = [float(t) for t in sys.argv[2:]]
    else:
        # Default to the failing test timepoints
        if 'recording_20250720_093110.wav' in audio_file:
            timepoints = [45.0, 70.3]  # Expected and detected times
        else:
            timepoints = [10.0]  # Generic timepoint
    
    analyze_audio_at_timepoints(audio_file, timepoints)

if __name__ == "__main__":
    main()