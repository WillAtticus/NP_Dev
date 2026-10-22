import { useState } from 'react'
import { computeNPI } from '../api/client'

export default function AlgorithmLabPage() {
  const [tbrInput, setTbrInput] = useState(0.55)
  const [tbrMin, setTbrMin] = useState(0.40)
  const [tbrMax, setTbrMax] = useState(0.85)
  const [result, setResult] = useState<any>(null)

  const handleCompute = async () => {
    try {
      const res = await computeNPI({
        tbr: tbrInput,
        tbr_min: tbrMin,
        tbr_max: tbrMax,
        quality_status: 'VALID_FOR_ANALYSIS',
      })
      setResult(res.data)
    } catch (e: any) {
      alert(`Compute error: ${e.message}`)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Algorithm Experimentation Lab</h1>
        <p className="text-sm text-gray-400 mt-1">NPI Parameter Tuning & Version Comparison</p>
      </div>

      <div className="bg-np-panel border border-np-border rounded-lg p-5 space-y-4">
        <h2 className="text-base font-semibold">NPI Formula: Baseline Specification</h2>
        <div className="p-3 bg-np-dark border border-np-border rounded text-xs font-mono text-np-green">
          NPI = 100 &times; [ 1 - clip((TBR - tbr_min) / (tbr_max - tbr_min), 0, 1) ]
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <label className="block text-xs text-gray-400 mb-1">TBR Input Value</label>
            <input
              type="number"
              step="0.01"
              value={tbrInput}
              onChange={(e) => setTbrInput(Number(e.target.value))}
              className="w-full bg-np-dark border border-np-border rounded px-3 py-2 text-white"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">TBR Min (Maps to NPI=100)</label>
            <input
              type="number"
              step="0.01"
              value={tbrMin}
              onChange={(e) => setTbrMin(Number(e.target.value))}
              className="w-full bg-np-dark border border-np-border rounded px-3 py-2 text-white"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">TBR Max (Maps to NPI=0)</label>
            <input
              type="number"
              step="0.01"
              value={tbrMax}
              onChange={(e) => setTbrMax(Number(e.target.value))}
              className="w-full bg-np-dark border border-np-border rounded px-3 py-2 text-white"
            />
          </div>
        </div>

        <button
          onClick={handleCompute}
          className="px-4 py-2 bg-np-blue text-black font-semibold rounded hover:bg-np-blue/90 text-sm transition"
        >
          Evaluate NPI Index
        </button>
      </div>

      {result && (
        <div className="bg-np-panel border border-np-border rounded-lg p-5">
          <h3 className="text-sm font-semibold mb-2">Evaluated Result</h3>
          <div className="flex items-center gap-6">
            <div>
              <div className="text-xs text-gray-400">Calculated NPI</div>
              <div className="text-3xl font-extrabold text-np-green mt-1">{result.npi_value}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">Interpretation</div>
              <div className="text-sm font-semibold text-white mt-1">Experimental metric only</div>
            </div>
          </div>
          <div className="mt-3 text-xs text-amber-300">
            {result.warnings?.join(' | ')}
          </div>
        </div>
      )}
    </div>
  )
}
