#!/usr/bin/env python3
"""
Synthetic Signal Generator for NeuroPulse MVP
Generates ground-truth synthetic micro-tremor datasets without requiring physical hardware.
"""
import os
import json
import math
import numpy as np

def generate_synthetic_piezo(
    duration_sec: float = 8.0,
    sample_rate_hz: float = 1000.0,
    tremor_freq_hz: float = 5.0,
    tremor_amp: float = 200.0,
    noise_amp: float = 30.0,
    baseline_offset: float = 2048.0
):
    """
    Generates synthetic 1-channel Piezo data (12-bit ADC counts) with a known tremor peak.
    """
    total_samples = int(duration_sec * sample_rate_hz)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)
    
    # Fundamental tremor frequency (e.g. 5.0 Hz within 3-6 Hz band)
    signal = tremor_amp * np.sin(2 * np.pi * tremor_freq_hz * t)
    # Physiological background drift (0.5 Hz)
    signal += 50.0 * np.sin(2 * np.pi * 0.5 * t)
    # Gaussian noise
    noise = np.random.normal(0, noise_amp, total_samples)
    
    raw_counts = np.clip(baseline_offset + signal + noise, 0, 4095).astype(int)
    
    dataset = {
        "metadata": {
            "sensor_type": "PIEZO_LDT0_028K",
            "provenance": "simulated",
            "sample_rate_hz": sample_rate_hz,
            "duration_sec": duration_sec,
            "total_samples": total_samples,
            "ground_truth": {
                "dominant_frequency_hz": tremor_freq_hz,
                "tremor_band": [3.0, 6.0],
                "reference_band": [1.0, 20.0]
            }
        },
        "channels": {
            "raw_counts": raw_counts.tolist()
        }
    }
    return dataset

def main():
    out_dir = os.path.join(os.path.dirname(__file__), "../data/simulated")
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. Standard Case with prominent 5 Hz micro-tremor
    ds_tremor = generate_synthetic_piezo(tremor_freq_hz=5.0, tremor_amp=350.0)
    out_path_1 = os.path.join(out_dir, "synthetic_piezo_5hz_high_tbr.json")
    with open(out_path_1, "w") as f:
        json.dump(ds_tremor, f)
    print(f"[+] Saved synthetic dataset: {out_path_1}")

    # 2. Control Case with flat baseline / low tremor
    ds_control = generate_synthetic_piezo(tremor_freq_hz=5.0, tremor_amp=10.0, noise_amp=50.0)
    out_path_2 = os.path.join(out_dir, "synthetic_piezo_baseline_control.json")
    with open(out_path_2, "w") as f:
        json.dump(ds_control, f)
    print(f"[+] Saved synthetic dataset: {out_path_2}")

if __name__ == "__main__":
    main()
