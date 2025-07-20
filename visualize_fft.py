#!/usr/bin/env python3
"""
FFT visualization tool for smoke detector audio analysis.
Shows frequency domain analysis over time to help debug detection issues.
"""

import numpy as np
import matplotlib.pyplot as plt
import librosa
import librosa.display
import sys
from pathlib import Path

def visualize_audio_fft(audio_file: str):
    """Create FFT visualization for audio file."""
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
    
    # Create figure with multiple subplots
    fig, axes = plt.subplots(4, 1, figsize=(15, 12))
    fig.suptitle(f'Audio Analysis: {audio_path.name}', fontsize=16)
    
    # 1. Time domain waveform
    time = np.linspace(0, duration, len(y))
    axes[0].plot(time, y)
    axes[0].set_title('Waveform')
    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('Amplitude')
    axes[0].grid(True)
    
    # Add markers for expected alarm time if this is the failing test
    if 'recording_20250720_093110.wav' in audio_file:
        axes[0].axvline(x=45.0, color='red', linestyle='--', alpha=0.7, label='Expected alarm (45s)')
        axes[0].axvline(x=70.3, color='orange', linestyle='--', alpha=0.7, label='Detected alarm (70.3s)')
        axes[0].legend()
    
    # 2. Short-Time Fourier Transform (STFT) - full spectrum
    hop_length = 512
    D = librosa.amplitude_to_db(np.abs(librosa.stft(y, hop_length=hop_length)), ref=np.max)
    img = librosa.display.specshow(D, y_axis='hz', x_axis='time', sr=sr, hop_length=hop_length, ax=axes[1])
    axes[1].set_title('Full Spectrogram (dB)')
    axes[1].set_ylim(0, 8000)  # Focus on relevant frequency range
    plt.colorbar(img, ax=axes[1], format='%+2.0f dB')
    
    # Add time markers
    if 'recording_20250720_093110.wav' in audio_file:
        axes[1].axvline(x=45.0, color='red', linestyle='--', alpha=0.7)
        axes[1].axvline(x=70.3, color='orange', linestyle='--', alpha=0.7)
    
    # 3. Smoke detector frequency range (2-4 kHz focus)
    axes[2].set_title('Smoke Detector Range Spectrogram (2-4 kHz)')
    img2 = librosa.display.specshow(D, y_axis='hz', x_axis='time', sr=sr, hop_length=hop_length, ax=axes[2])
    axes[2].set_ylim(2000, 4000)  # Typical smoke detector range
    plt.colorbar(img2, ax=axes[2], format='%+2.0f dB')
    
    # Add time markers  
    if 'recording_20250720_093110.wav' in audio_file:
        axes[2].axvline(x=45.0, color='red', linestyle='--', alpha=0.7)
        axes[2].axvline(x=70.3, color='orange', linestyle='--', alpha=0.7)
    
    # 4. Power spectrum at key time points
    if 'recording_20250720_093110.wav' in audio_file:
        # Extract chunks around expected and detected times
        expected_time = 45.0
        detected_time = 70.3
        window_size = 2048
        
        # Get samples for each time point
        expected_sample = int(expected_time * sr)
        detected_sample = int(detected_time * sr)
        
        # Extract windowed signals
        if expected_sample + window_size < len(y):
            expected_chunk = y[expected_sample:expected_sample + window_size]
            expected_fft = np.abs(np.fft.fft(expected_chunk))
            expected_freqs = np.fft.fftfreq(len(expected_fft), 1/sr)
        else:
            expected_fft = None
            
        if detected_sample + window_size < len(y):
            detected_chunk = y[detected_sample:detected_sample + window_size]
            detected_fft = np.abs(np.fft.fft(detected_chunk))
            detected_freqs = np.fft.fftfreq(len(detected_fft), 1/sr)
        else:
            detected_fft = None
        
        # Plot frequency spectrum comparison
        if expected_fft is not None:
            # Only plot positive frequencies up to 8kHz
            pos_mask = (expected_freqs >= 0) & (expected_freqs <= 8000)
            axes[3].plot(expected_freqs[pos_mask], expected_fft[pos_mask], 
                        label=f'Expected alarm time ({expected_time}s)', color='red', alpha=0.7)
        
        if detected_fft is not None:
            pos_mask = (detected_freqs >= 0) & (detected_freqs <= 8000)
            axes[3].plot(detected_freqs[pos_mask], detected_fft[pos_mask], 
                        label=f'Detected alarm time ({detected_time}s)', color='orange', alpha=0.7)
        
        axes[3].set_title('Frequency Spectrum Comparison')
        axes[3].set_xlabel('Frequency (Hz)')
        axes[3].set_ylabel('Magnitude')
        axes[3].set_xlim(0, 8000)
        axes[3].grid(True)
        axes[3].legend()
        
        # Highlight typical smoke detector frequencies
        axes[3].axvspan(2800, 3200, alpha=0.1, color='green', label='Typical smoke alarm range')
    else:
        # For other files, just show overall frequency content
        fft = np.abs(np.fft.fft(y))
        freqs = np.fft.fftfreq(len(fft), 1/sr)
        pos_mask = (freqs >= 0) & (freqs <= 8000)
        
        axes[3].plot(freqs[pos_mask], fft[pos_mask])
        axes[3].set_title('Overall Frequency Spectrum')
        axes[3].set_xlabel('Frequency (Hz)')
        axes[3].set_ylabel('Magnitude')
        axes[3].set_xlim(0, 8000)
        axes[3].grid(True)
    
    plt.tight_layout()
    
    # Save visualization
    output_path = audio_path.with_suffix('.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Visualization saved to: {output_path}")
    
    plt.show()

def main():
    if len(sys.argv) != 2:
        print("Usage: python visualize_fft.py <audio_file>")
        print("Example: python visualize_fft.py test_audio/recording_20250720_093110.wav")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    visualize_audio_fft(audio_file)

if __name__ == "__main__":
    main()