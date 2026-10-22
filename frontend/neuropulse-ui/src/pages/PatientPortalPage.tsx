import { useState } from 'react'
import { lookupPatient } from '../api/client'
import type { PatientLookup } from '../api/client'

const errorText = (error: any) => error?.response?.data?.detail || error?.message || 'Không thể tra cứu hồ sơ.'
const dateText = (value?: string | null) => value ? new Date(value).toLocaleString() : 'Chưa có dữ liệu'

function alertCopy(category?: string | null) {
  if (category === 'experimental_reference_range') return { tone: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200', label: 'Trong khoảng tham chiếu thử nghiệm (NPI ≥70)' }
  if (category === 'experimental_monitoring') return { tone: 'border-amber-500/30 bg-amber-500/10 text-amber-200', label: 'Theo dõi theo giả thuyết thử nghiệm (NPI 40–69)' }
  if (category === 'outside_experimental_reference_range') return { tone: 'border-red-500/30 bg-red-500/10 text-red-200', label: 'Ngoài khoảng tham chiếu thử nghiệm (NPI <40)' }
  return { tone: 'border-white/10 bg-white/5 text-gray-300', label: 'Chưa có phân loại' }
}

export default function PatientPortalPage() {
  const [code, setCode] = useState('')
  const [result, setResult] = useState<PatientLookup | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setLoading(true); setError(''); setResult(null)
    try { const { data } = await lookupPatient(code.trim()); setResult(data) }
    catch (reason) { setError(errorText(reason)) }
    finally { setLoading(false) }
  }
  const exportPersonal = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a')
    anchor.href = url; anchor.download = `neuropulse-${result.patient.patient_code}-personal-record.json`; anchor.click()
    URL.revokeObjectURL(url)
  }
  const patient = result?.patient

  return <main className="min-h-screen bg-np-dark px-4 py-10 text-white">
    <div className="mx-auto max-w-4xl space-y-6">
      <header><a href="/" className="text-np-blue font-bold">NeuroPulse</a><h1 className="mt-3 text-3xl font-bold">Hồ sơ theo dõi cá nhân</h1><p className="mt-2 text-gray-400">Nhập mã bệnh nhân để xem thông tin và lịch sử lưu trên máy này.</p></header>
      <form onSubmit={submit} className="flex flex-col gap-3 rounded-xl border border-np-border bg-np-panel p-5 sm:flex-row">
        <label className="flex-1 text-sm">Mã bệnh nhân<input required maxLength={20} value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} placeholder="NXM2612345" className="mt-1 block w-full rounded border border-np-border bg-np-dark p-3 font-mono tracking-widest" /></label>
        <button disabled={loading} className="self-end rounded bg-np-blue px-5 py-3 font-semibold text-black disabled:opacity-50">{loading ? 'Đang tìm…' : 'Tra cứu hồ sơ'}</button>
      </form>
      {error && <div role="alert" className="rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</div>}
      {result && patient && <>
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">{result.screening_notice} Các kết quả này không thay thế đánh giá của chuyên gia y tế.</div>
        <section className="rounded-xl border border-np-border bg-np-panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-np-blue">{patient.patient_code}</p><h2 className="mt-1 text-2xl font-semibold">{patient.full_name}</h2></div><button onClick={exportPersonal} className="rounded bg-white/10 px-3 py-2 text-sm hover:bg-white/15">Xuất hồ sơ cá nhân</button></div>
          <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2"><div><dt className="text-gray-400">Ngày sinh</dt><dd>{patient.date_of_birth || 'Chưa ghi nhận'}</dd></div><div><dt className="text-gray-400">Tiền sử cá nhân</dt><dd>{patient.medical_history || 'Chưa ghi nhận'}</dd></div><div><dt className="text-gray-400">Tiền sử gia đình</dt><dd>{patient.family_history || 'Chưa ghi nhận'}</dd></div><div><dt className="text-gray-400">Chế độ ăn</dt><dd>{patient.diet === 'vegetarian' ? 'Chay' : patient.diet === 'omnivore' ? 'Mặn' : 'Chưa ghi nhận'}</dd></div></dl>
        </section>
        <section className="space-y-3"><div className="flex items-center justify-between"><h2 className="text-xl font-semibold">Lịch sử đo</h2><span className="text-sm text-gray-400">{result.sessions.length} phiên</span></div>
          {result.sessions.length === 0 && <div className="rounded-xl border border-np-border bg-np-panel p-5 text-sm text-gray-400">Chưa có phiên đo được lưu cho mã này.</div>}
          {result.sessions.map((session) => { const alert = alertCopy(session.npi_category); return <article key={session.id} className="rounded-xl border border-np-border bg-np-panel p-5">
            <div className="flex flex-wrap justify-between gap-2"><div><p className="font-medium">{dateText(session.start_time || session.created_at)}</p><p className="text-xs text-gray-400">{session.sensor_type} · {session.provenance === 'simulated' ? 'Mô phỏng' : session.provenance}</p></div><span className="rounded bg-white/10 px-2 py-1 text-xs">{session.quality_status || session.status}</span></div>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4"><div><p className="text-xs text-gray-400">NPI thử nghiệm</p><p className="text-2xl font-bold">{session.npi_value ?? '—'}</p></div><div><p className="text-xs text-gray-400">TBR</p><p className="text-lg">{session.tbr ?? '—'}</p></div><div><p className="text-xs text-gray-400">Tần số đỉnh</p><p className="text-lg">{session.dominant_freq_hz ?? '—'} Hz</p></div><div><p className="text-xs text-gray-400">Tốc độ lấy mẫu</p><p className="text-lg">{session.sample_rate_hz ?? '—'} Hz</p></div></div>
            <div className={`mt-4 rounded border p-3 text-sm ${alert.tone}`}>{alert.label}</div>
          </article> })}
        </section>
      </>}
      <p className="text-center text-xs text-gray-500">Prototype nghiên cứu nội bộ · Thông tin lưu cục bộ trên máy · Không dùng để tự chẩn đoán</p>
    </div>
  </main>
}
