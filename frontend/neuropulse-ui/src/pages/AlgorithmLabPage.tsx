import { useEffect, useState } from 'react'
import { computeNPI, createAlgorithmFormula, evaluateAlgorithmFormula, evaluateAlgorithmFormulaOnSession, exportAlgorithmEvaluations, getAlgorithmEvaluations, getAlgorithmFormulas, getSessions, retireAlgorithmFormula } from '../api/client'
import type { FormulaRecord } from '../api/client'

export default function AlgorithmLabPage() {
  const [tbrInput, setTbrInput] = useState(0.55)
  const [tbrMin, setTbrMin] = useState(0.40)
  const [tbrMax, setTbrMax] = useState(0.85)
  const [result, setResult] = useState<any>(null)
  const [formulas, setFormulas] = useState<FormulaRecord[]>([])
  const [sessions, setSessions] = useState<any[]>([])
  const [evaluations, setEvaluations] = useState<any[]>([])
  const [sessionId, setSessionId] = useState('')
  const [sessionChannel, setSessionChannel] = useState('x_counts')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [name, setName] = useState('NPI baseline')
  const [changeNote, setChangeNote] = useState('')
  const [expression, setExpression] = useState('100 * (1 - clip((tbr - tbr_min) / (tbr_max - tbr_min), 0, 1))')

  const refreshFormulas = async () => { try { setFormulas((await getAlgorithmFormulas()).data) } catch (e: any) { setError(e.response?.data?.detail || e.message || 'Không tải được công thức đã lưu.') } }
  const refreshEvaluations = async () => { try { setEvaluations((await getAlgorithmEvaluations()).data) } catch { setEvaluations([]) } }
  useEffect(() => { void refreshFormulas(); void refreshEvaluations(); getSessions(100, 0).then(({ data }) => setSessions(data.sessions || [])).catch(() => setSessions([])) }, [])

  const handleCompute = async () => {
    try {
      const activeFormula = formulas.find((formula) => formula.name === name && formula.status !== 'retired')
      if (!activeFormula && formulas.some((formula) => formula.name === name)) throw new Error('Công thức này đã ngừng dùng. Tạo phiên bản mới trước khi đánh giá.')
      const res = activeFormula
        ? await evaluateAlgorithmFormula(activeFormula.id, { tbr: tbrInput, quality_status: 'VALID_FOR_ANALYSIS' })
        : await computeNPI({ tbr: tbrInput, tbr_min: tbrMin, tbr_max: tbrMax, quality_status: 'VALID_FOR_ANALYSIS' })
      setResult(res.data)
      void refreshEvaluations()
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Không tính được chỉ số.')
    }
  }

  const handleSavedSession = async () => {
    const formula = formulas.find((item) => item.name === name && item.status !== 'retired')
    if (!formula || !sessionId) { setError('Chọn một công thức đang dùng và một phiên đo đã lưu.'); return }
    try {
      const selectedSession = sessions.find((item) => item.id === sessionId)
      const { data } = await evaluateAlgorithmFormulaOnSession(formula.id, { session_id: sessionId, channel: selectedSession?.sensor_type === 'ADXL345' ? sessionChannel : undefined })
      setResult(data); setMessage(`Đã phân tích lại phiên bằng ${formula.name} v${formula.version}. Phiên tóm tắt mặc định không bị ghi đè.`)
      void refreshEvaluations()
    } catch (e: any) { setError(e.response?.data?.detail || e.message || 'Không đánh giá được phiên.') }
  }

  const handleExportEvaluations = async () => {
    try {
      const { data } = await exportAlgorithmEvaluations()
      const blob = new Blob([data], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = 'neuropulse_algorithm_evaluations.csv'
      document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setMessage('Đã xuất lịch sử đánh giá công thức thử nghiệm. Tệp có mã phiên và thông tin nghiên cứu; hãy lưu trữ an toàn.')
    } catch (e: any) { setError(e.response?.data?.detail || e.message || 'Không xuất được lịch sử đánh giá.') }
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Algorithm Experimentation Lab</h1>
        <p className="text-sm text-gray-400 mt-1">Định nghĩa, kiểm tra và lưu phiên bản công thức nghiên cứu</p>
      </div>

      {error && <div role="alert" className="rounded border border-red-400/40 bg-red-400/10 p-3 text-sm">{error}</div>}
      {message && <div role="status" className="rounded border border-emerald-400/40 bg-emerald-400/10 p-3 text-sm">{message}</div>}

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="bg-np-panel border border-np-border rounded-lg p-5 space-y-3"><h2 className="font-semibold">Định nghĩa kỹ thuật · NPI v1 baseline</h2>
          <dl className="grid grid-cols-[130px_1fr] gap-y-2 text-sm"><dt className="text-gray-400">Trạng thái</dt><dd>Experimental · chưa xác nhận lâm sàng</dd><dt className="text-gray-400">Đầu vào</dt><dd>Tín hiệu cảm biến, tần số lấy mẫu đã đo, quality flags</dd><dt className="text-gray-400">Tiền xử lý</dt><dd>Loại xu hướng, Butterworth bandpass, tùy chọn notch 50 Hz</dd><dt className="text-gray-400">Đặc trưng</dt><dd>Welch PSD; TBR = power 3–6 Hz / power 1–20 Hz</dd><dt className="text-gray-400">Đầu ra</dt><dd>TBR (không đơn vị), NPI 0–100, trạng thái chất lượng và cờ cảnh báo thử nghiệm</dd><dt className="text-gray-400">Cửa kiểm soát</dt><dd>Mẫu lỗi, thiếu/cũ/trùng, sample rate chưa đo hoặc dữ liệu chưa đủ → không xuất NPI</dd><dt className="text-gray-400">Mã nguồn</dt><dd><code>backend/app/services/processing/engine.py</code> · <code>backend/app/services/algorithms/npi.py</code></dd><dt className="text-gray-400">Đặc tả</dt><dd><code>docs/ALGORITHM_SPEC.md</code> · phép tính vẫn cần xác nhận chuyên môn</dd></dl>
        </div>
        <div className="bg-np-panel border border-np-border rounded-lg p-5 space-y-3"><h2 className="font-semibold">Vết xử lý</h2><ol className="list-decimal pl-5 space-y-2 text-sm text-gray-300"><li>Nhận frame có CRC, sequence, timestamp và loại cảm biến.</li><li>Đổi raw counts theo adapter; giữ bản raw bất biến cùng provenance.</li><li>Kiểm tra sample rate, độ dài, mẫu không hữu hạn, mất gói và chất lượng tín hiệu.</li><li>Chạy bộ lọc theo profile cảm biến; tính PSD và năng lượng các dải.</li><li>Tính TBR, sau đó đưa TBR qua công thức NPI và dải demo.</li><li>Lưu metadata/phiên bản để tái lập; kết quả thử nghiệm không phải chẩn đoán.</li></ol><p className="text-xs text-amber-300">Các phiên đo hiện vẫn chạy NPI baseline tích hợp; phiên bản lưu ở khu vực Lab chưa được gán làm thuật toán chạy acquisition. Không nên so sánh như thể phiên đo đã dùng phiên bản Lab.</p><p className="text-xs text-gray-400">Đây là mô tả các bước hiện có trong code, không phải bằng chứng hiệu năng hay xác nhận lâm sàng.</p></div>
      </section>

      <details className="bg-np-panel border border-np-border rounded-lg p-5"><summary className="cursor-pointer font-semibold">Mã nguồn NPI baseline (trích đoạn thực thi)</summary><pre className="mt-3 overflow-x-auto rounded border border-np-border bg-np-dark p-3 text-xs text-emerald-200"><code>{'if quality_status in ("INVALID", "INSUFFICIENT_DATA"):\n    return {"npi_value": None, ...}\n\ndenom = tbr_max - tbr_min\nif denom <= 0:\n    raise ValueError("tbr_max must be greater than tbr_min")\nnormalised = (tbr - tbr_min) / denom\nclipped = max(0.0, min(1.0, normalised))\nnpi_value = round(100.0 * (1.0 - clipped), 2)'}</code></pre><p className="mt-2 text-xs text-gray-400">Nguồn đầy đủ: backend/app/services/algorithms/npi.py. Pipeline Welch, bộ lọc và kiểm soát chất lượng nằm trong backend/app/services/processing/engine.py.</p></details>

      <div className="bg-np-panel border border-np-border rounded-lg p-5 space-y-4">
        <h2 className="text-base font-semibold">NPI Formula: Baseline Specification</h2>
        <div className="p-3 bg-np-dark border border-np-border rounded text-xs font-mono text-np-green">
          {expression}
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

      <section className="bg-np-panel border border-np-border rounded-lg p-5 space-y-4"><div><h2 className="font-semibold">Thêm / thay thế công thức thử nghiệm</h2><p className="mt-1 text-xs text-gray-400">Biểu thức giới hạn: số, tbr, tbr_min, tbr_max, phép cộng/trừ/nhân/chia và clip(x,min,max). Không chạy Python tùy ý; thay cùng tên tạo phiên bản mới, ngừng dùng giữ lịch sử.</p></div><label className="block text-xs text-gray-400">Biểu thức<textarea value={expression} onChange={e => setExpression(e.target.value)} rows={2} className="mt-1 w-full rounded border border-np-border bg-np-dark p-2 font-mono text-white"/></label><div className="grid gap-3 md:grid-cols-3"><label className="text-xs text-gray-400">Tên nhóm công thức<input value={name} onChange={e => setName(e.target.value)} className="mt-1 w-full rounded border border-np-border bg-np-dark p-2 text-white"/></label><label className="text-xs text-gray-400">Ghi chú thay đổi<input value={changeNote} onChange={e => setChangeNote(e.target.value)} className="mt-1 w-full rounded border border-np-border bg-np-dark p-2 text-white" placeholder="Lý do / giả thuyết"/></label><button className="self-end rounded bg-np-blue px-4 py-2 text-sm font-semibold text-black" onClick={async () => { setError(''); setMessage(''); try { const saved = await createAlgorithmFormula({ name, expression, tbr_min: tbrMin, tbr_max: tbrMax, change_note: changeNote || 'Tạo phiên bản thử nghiệm mới' }); setMessage(`Đã lưu ${saved.data.name} v${saved.data.version}; phiên bản trước được giữ trong lịch sử.`); await refreshFormulas() } catch (e: any) { setError(e.response?.data?.detail || e.message || 'Không lưu được.') } }}>Lưu phiên bản mới</button></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="text-gray-400"><th className="p-2">Công thức</th><th className="p-2">Phiên bản</th><th className="p-2">Min / max</th><th className="p-2">Trạng thái</th><th className="p-2">Ghi chú / thao tác</th></tr></thead><tbody>{formulas.map(f => <tr key={f.id} className="border-t border-np-border"><td className="p-2">{f.name}<div className="max-w-sm truncate font-mono text-xs text-gray-400">{f.expression}</div></td><td className="p-2">v{f.version}</td><td className="p-2">{f.tbr_min} / {f.tbr_max}</td><td className="p-2">{f.status}</td><td className="p-2">{f.change_note || '—'} {f.status !== 'retired' && <button className="ml-2 text-red-300" onClick={async () => { try { await retireAlgorithmFormula(f.id); setMessage('Đã ngừng công thức; dấu vết được giữ lại.'); await refreshFormulas() } catch (e: any) { setError(e.response?.data?.detail || e.message) } }}>Ngừng dùng</button>}</td></tr>)}</tbody></table>{!formulas.length && <p className="p-2 text-xs text-gray-400">Chưa lưu phiên bản nào.</p>}</div></section>

      <section className="bg-np-panel border border-np-border rounded-lg p-5 space-y-3"><h2 className="font-semibold">Đánh giá công thức trên phiên đã lưu</h2><p className="text-xs text-gray-400">Pipeline chạy lại từ raw đã lưu; kết quả công thức được ghi audit riêng, không ghi đè tóm tắt phiên.</p><div className="flex flex-wrap gap-3"><select aria-label="Chọn phiên đã lưu" value={sessionId} onChange={e => setSessionId(e.target.value)} className="min-w-80 rounded border border-np-border bg-np-dark p-2 text-white"><option value="">Chọn phiên hoàn tất</option>{sessions.filter(s => s.status === 'completed').map(s => <option key={s.id} value={s.id}>{s.participant_code || 'Không mã'} · {s.sensor_type} · {s.id.slice(0, 8)} · {s.provenance}</option>)}</select>{sessions.find(s => s.id === sessionId)?.sensor_type === 'ADXL345' && <select aria-label="Kênh ADXL345" value={sessionChannel} onChange={e => setSessionChannel(e.target.value)} className="rounded border border-np-border bg-np-dark p-2 text-white"><option value="x_counts">Trục X</option><option value="y_counts">Trục Y</option><option value="z_counts">Trục Z</option></select>}<button onClick={() => void handleSavedSession()} className="rounded bg-np-blue px-4 py-2 text-sm font-semibold text-black">Chạy lại pipeline và đánh giá</button></div>{sessions.filter(s => s.status === 'completed').length === 0 && <p className="text-xs text-gray-400">Chưa có phiên đo hoàn tất. Có thể dùng simulator để tạo dữ liệu, sau đó chọn phiên ở đây.</p>}</section>

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
          {result.formula_id && <p className="mt-2 text-xs text-gray-400">Công thức đã đánh giá: {result.formula_name} v{result.formula_version} · ID {result.formula_id} · tham số {JSON.stringify(result.parameter_snapshot)}</p>}
          {result.reprocessing && <p className="mt-2 text-xs text-gray-400">Phiên {result.session_id} · {result.reprocessing.sensor_type} · kênh {result.reprocessing.channel} · {result.reprocessing.provenance} · {result.reprocessing.sample_count} mẫu @ {result.reprocessing.sample_rate_hz || 'không rõ'} Hz · quality {result.reprocessing.quality_status} · flags {result.reprocessing.quality_flags.join(', ') || 'none'} · TBR {result.reprocessing.tbr ?? '—'}</p>}
        </div>
      )}
      <section className="bg-np-panel border border-np-border rounded-lg p-5"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Lịch sử đánh giá công thức</h2><div className="flex gap-3"><button className="text-xs text-np-blue" onClick={() => void refreshEvaluations()}>Làm mới</button><button className="text-xs text-np-blue" onClick={() => void handleExportEvaluations()}>Xuất CSV</button></div></div>{evaluations.length ? <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="text-gray-400"><tr><th className="p-2">Thời gian</th><th className="p-2">Phiên</th><th className="p-2">TBR</th><th className="p-2">NPI thử nghiệm</th><th className="p-2">Quality</th><th className="p-2">Công thức / tham số</th></tr></thead><tbody>{evaluations.map((row) => <tr key={row.id} className="border-t border-np-border"><td className="p-2">{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</td><td className="p-2"><code>{row.session_id || 'Nhập thủ công'}</code></td><td className="p-2">{row.tbr ?? '—'}</td><td className="p-2">{row.npi_value ?? '—'}</td><td className="p-2">{row.quality_status}</td><td className="p-2">v{row.formula_version} · {JSON.stringify(row.parameters_snapshot)}</td></tr>)}</tbody></table></div> : <p className="text-xs text-gray-400">Chưa có lần đánh giá nào.</p>}</section>
    </div>
  )
}
