# Test Plan & Quality Assurance — NeuroPulse MVP

---

## 1. Test Strategy

Testing spans firmware logic, serial communication, data persistence, signal processing mathematics, and UI rendering.

1. **Deterministic Ground-Truth Signal Tests:**
   Synthetic signals with known analytical spectral components (e.g., pure 5 Hz sine wave, multi-tone mixtures, white noise) verify FFT, Welch PSD, band power calculations, and TBR within strict numerical tolerances ($\pm 1\%$).
2. **Serial & Protocol Round-Trip Tests:**
   Ensure packet encoders/decoders preserve 100% of samples, detect corrupted CRCs, and identify dropped sequence numbers.
3. **Data Integrity & Immutability:**
   Verify SHA256 checksums of stored raw HDF5 files and ensure processing operations never overwrite raw recordings.
4. **Edge Case & Failure Recovery:**
   Test buffer backpressure, unexpected disconnects, ADC clipping saturation, and flatline signals.
5. **Local Backup & Restore:**
   Snapshot SQLite through its online backup API, verify per-file SHA-256 during restore, reject overwrite/path traversal/tampered archives, and revoke restored authentication sessions while preserving raw session files byte-for-byte.
