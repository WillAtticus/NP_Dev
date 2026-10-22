import { useState } from 'react'
import { simulateAndAnalyse } from '../api/client'

export default function SignalAnalysisPage() {
  const [sensorType, setSensorType] = useState('PIEZO_LDT0_028K')
  const [profileId, setProfileId] = useState('piezo_butterworth_1_20_default')
  const [tremorFreq, setTremorFreq] = useState(5.0)
  const [tremorAmp, setTremorAmp] = useState(250.0)
  const [noiseAmp, setNoiseAmp] = useState(25.0)
  const [duration, setDuration] = useState(8.0)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const handleRun = async () => {
    setLoading(true)
    try {
      const res = await simulateAndAnalyse({
        sensor_type: sensorType,
        profile_id: profileId,
        tremor_freq_hz: tremorFreq,
        tremor_amp: tremorAmp,
        noise_amp: noiseAmp,
        duration_sec: duration,
      })
      setResult(res.data)
    } catch (e: any) {
      alert(`Analysis failed: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const an = result?.analysis
  const npi = an?.npi

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Signal Analysis & Spectral Engine</h1>
        <p className="text-sm text-gray-400 mt-1">Multi-stage pipeline: Detrend &rarr; Butterworth IIR &rarr; Welch PSD &rarr; Band Power (3-6 Hz) &rarr; NPI</p>
      </div>

      <div className="bg-np-panel border border-np-border rounded-lg p-5 space-y-4">
        <h2 className="text-base font-semibold">Simulation & Processing Parameters</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Sensor Modality</label>
            <select
              value={sensorType}
              onChange={(e) => { const sensor = e.target.value; setSensorType(sensor); setProfileId(sensor === 'ADXL345' ? 'adxl345_triaxial_100hz' : 'piezo_butterworth_1_20_default') }}
              className="w-full bg-np-dark border border-np-border rounded px-3 py-2 text-white"
            >
              <option value="PIEZO_LDT0_028K">Piezo Film (LDT0-028K)</option>
              <option value="ADXL345">ADXL345 Triaxial Accelerometer</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Processing Profile</label>
            <select
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
              className="w-full bg-np-dark border border-np-border rounded px-3 py-2 text-white"
            >
              {sensorType === 'PIEZO_LDT0_028K' ? <>
                <option value="piezo_butterworth_1_20_default">Butterworth 1–20 Hz (Default)</option>
                <option value="piezo_butterworth_5_20_candidate">Butterworth 5–20 Hz (Candidate)</option>
              </> : <option value="adxl345_triaxial_100hz">ADXL345 100Hz Triaxial</option>}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Target Tremor Freq: {tremorFreq} Hz</label>
            <input
              type="range"
              min="0.5"
              max="25.0"
              step="0.5"
              value={tremorFreq}
              onChange={(e) => setTremorFreq(Number(e.target.value))}
              className="w-full"
            />
          </div>
          <label className="block text-xs text-gray-400">Synthetic amplitude
            <input type="number" min="0" max="2000" step="1" value={tremorAmp} onChange={(e) => setTremorAmp(Number(e.target.value))} className="mt-1 w-full bg-np-dark border border-np-border rounded px-3 py-2 text-white" />
          </label>
          <label className="block text-xs text-gray-400">Synthetic noise amplitude
            <input type="number" min="0" step="1" value={noiseAmp} onChange={(e) => setNoiseAmp(Number(e.target.value))} className="mt-1 w-full bg-np-dark border border-np-border rounded px-3 py-2 text-white" />
          </label>
          <label className="block text-xs text-gray-400">Synthetic duration (seconds)
            <input type="number" min="2" max="120" step="1" value={duration} onChange={(e) => setDuration(Number(e.target.value))} className="mt-1 w-full bg-np-dark border border-np-border rounded px-3 py-2 text-white" />
          </label>
        </div>

        <button
          onClick={handleRun}
          disabled={loading}
          className="px-5 py-2.5 bg-np-blue text-black font-semibold rounded hover:bg-np-blue/90 disabled:opacity-50 text-sm transition"
        >
          {loading ? 'Processing...' : '🔬 Execute Signal Processing Pipeline'}
        </button>
      </div>

      <div className="bg-blue-500/15 border border-blue-500/40 rounded-lg p-3 text-blue-100 text-xs">Màn hình này chỉ tạo tín hiệu tổng hợp để kiểm tra pipeline (provenance: simulated). Kết quả không đại diện cho dữ liệu người tham gia và không phải diễn giải lâm sàng.</div>

      {result && (
        <div className="space-y-4">
          {/* NPI Card */}
          <div className="bg-np-panel border border-np-border rounded-lg p-5">
            <h3 className="text-sm font-semibold uppercase text-gray-400 mb-3">Experimental Results</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-np-dark p-4 rounded border border-np-border">
                <div className="text-xs text-gray-400">NPI (0–100)</div>
                <div className="text-3xl font-extrabold text-np-green mt-1">
                  {npi?.npi_value !== null ? npi?.npi_value : 'N/A'}
                </div>
                <div className="text-[11px] text-gray-400 mt-1">Experimental metric only</div>
              </div>

              <div className="bg-np-dark p-4 rounded border border-np-border">
                <div className="text-xs text-gray-400">TBR (3-6Hz / 1-20Hz)</div>
                <div className="text-2xl font-bold text-white mt-1">{an?.tbr || 'N/A'}</div>
                <div className="text-[11px] text-gray-500 mt-1">Power Ratio</div>
              </div>

              <div className="bg-np-dark p-4 rounded border border-np-border">
                <div className="text-xs text-gray-400">Dominant Frequency</div>
                <div className="text-2xl font-bold text-np-blue mt-1">{an?.dominant_freq_hz} Hz</div>
                <div className="text-[11px] text-gray-500 mt-1">Spectral Peak</div>
              </div>

              <div className="bg-np-dark p-4 rounded border border-np-border">
                <div className="text-xs text-gray-400">Quality Status</div>
                <div className="text-xl font-bold text-white mt-1">{an?.quality_status}</div>
                <div className="text-[11px] text-gray-500 mt-1">RMS: {an?.rms}</div>
              </div>
            </div>
          </div>

          {/* Feature Breakdown Table */}
          <div className="bg-np-panel border border-np-border rounded-lg p-5">
            <h3 className="text-sm font-semibold mb-3">Extracted Feature Values</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-gray-300">
              <div className="p-2 bg-np-dark rounded">RMS: <strong className="text-white">{an?.rms}</strong></div>
              <div className="p-2 bg-np-dark rounded">Peak-to-Peak: <strong className="text-white">{an?.peak_to_peak}</strong></div>
              <div className="p-2 bg-np-dark rounded">Tremor Power (3-6Hz): <strong className="text-white">{an?.band_power_tremor}</strong></div>
              <div className="p-2 bg-np-dark rounded">Ref Power (1-20Hz): <strong className="text-white">{an?.band_power_ref}</strong></div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
