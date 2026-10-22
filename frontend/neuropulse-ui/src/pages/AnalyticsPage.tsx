import { useEffect, useState } from 'react'
import { getCohortAnalytics } from '../api/client'

type Cohort = { group: string; participants: number; sessions: number; avg_npi: number | null; avg_tbr: number | null }
type Analytics = {
  source: string
  participant_count: number
  session_count: number
  completed_session_count: number
  provenance_counts: Record<string, number>
  by_age_band: Cohort[]
  by_chromosome_marker: Cohort[]
  by_diet: Cohort[]
  metric_note: string
}

const fmt = (value: number | null) => value == null ? '—' : value.toFixed(1)
const ageLabels: Record<string, string> = { I: 'Chưa rõ', C: '<10', J: '10–17', Y: '18–29', M: '30–49', E: '50+' }

function CohortChart({ title, rows, valueKey }: { title: string; rows: Cohort[]; valueKey: 'avg_npi' | 'participants' }) {
  const hasValues = rows.some((row) => row[valueKey] != null)
  const max = valueKey === 'avg_npi' ? 100 : Math.max(1, ...rows.map((row) => Number(row.participants)))
  return <section className="rounded-xl border border-np-border bg-np-panel p-5">
    <h2 className="font-semibold">{title}</h2>
    <p className="mt-1 text-xs text-gray-400">{valueKey === 'avg_npi' ? 'NPI thử nghiệm trung bình theo phiên hoàn tất' : 'Số hồ sơ được lưu'}</p>
    {!rows.length || !hasValues ? <div className="grid min-h-48 place-items-center text-sm text-gray-500">Chưa có dữ liệu lưu phù hợp để so sánh.</div> :
      <div className="mt-5 space-y-4">{rows.map((row) => {
        const value = row[valueKey]
        const width = value == null ? 0 : Math.max(2, Math.min(100, Number(value) / max * 100))
        const label = valueKey === 'avg_npi' ? fmt(value as number | null) : String(row.participants)
        return <div key={row.group}>
          <div className="mb-1 flex justify-between gap-3 text-xs"><span>{row.group}</span><strong>{label}{valueKey === 'avg_npi' ? ` · ${row.sessions} phiên` : ` · ${row.sessions} phiên`}</strong></div>
          <div className="h-3 overflow-hidden rounded-full bg-np-dark"><div className="h-full rounded-full bg-np-blue transition-all" style={{ width: `${width}%` }} /></div>
        </div>
      })}</div>}
    {valueKey === 'avg_npi' && <p className="mt-4 text-[11px] text-gray-500">Thang hiển thị 0–100 · Mô tả dữ liệu nghiên cứu, không phải phân loại bệnh.</p>}
  </section>
}

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let active = true
    const load = () => getCohortAnalytics().then(({ data: result }) => { if (active) { setData(result as Analytics); setError('') } })
      .catch((reason: any) => { if (active) setError(reason.response?.data?.detail || reason.message || 'Không tải được thống kê.') })
      .finally(() => { if (active) setLoading(false) })
    void load()
    const timer = window.setInterval(() => void load(), 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  const provenance = data?.provenance_counts || {}
  return <div className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">TỔNG HỢP LOCAL</p><h1 className="page-title">Thống kê & so sánh nhóm</h1><p className="page-subtitle">Dữ liệu được tính từ hồ sơ và phiên thực sự đang lưu trên máy này.</p></div><button onClick={() => { setLoading(true); void getCohortAnalytics().then(({ data: result }) => setData(result as Analytics)).catch((e: any) => setError(e.message)).finally(() => setLoading(false)) }} className="rounded-lg border border-np-border bg-white px-4 py-2 text-sm text-np-ink">Làm mới</button></header>
    <div className="research-note">Thống kê mô tả nghiên cứu. NPI và TBR là chỉ số thử nghiệm, không dùng để chẩn đoán hay đánh giá hiệu quả lâm sàng.</div>
    {error && <div role="alert" className="error-banner">{error}</div>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {[["Hồ sơ người tham gia", data?.participant_count], ["Tổng phiên lưu", data?.session_count], ["Phiên hoàn tất", data?.completed_session_count], ["Phiên mô phỏng", provenance.simulated || 0]].map(([label, value]) => <div key={String(label)} className="card-surface p-5"><p className="text-xs text-gray-500">{label}</p><strong className="mt-2 block text-3xl text-np-ink">{value ?? (loading ? '…' : 0)}</strong></div>)}
    </div>
    {data && (provenance.simulated > 0 || provenance.imported_benchmark > 0) && <div className="rounded-lg border border-blue-300 bg-blue-50 p-3 text-sm text-blue-900">Nguồn có dữ liệu tổng hợp: simulated {provenance.simulated || 0}, benchmark nhập {provenance.imported_benchmark || 0}. Các nhóm bên dưới gộp các nguồn đã lưu; không xem dữ liệu giả lập/benchmark là dữ liệu người thật.</div>}
    <div className="grid gap-4 xl:grid-cols-2">
      <CohortChart title="Quy mô nhóm theo tuổi" rows={(data?.by_age_band || []).map((row) => ({ ...row, group: ageLabels[row.group] || row.group }))} valueKey="participants" />
      <CohortChart title="Quy mô nhóm theo nhiễm sắc thể" rows={(data?.by_chromosome_marker || []).map((row) => ({ ...row, group: row.group === 'X' ? 'XX' : row.group === 'Y' ? 'XY' : row.group }))} valueKey="participants" />
      <CohortChart title="NPI thử nghiệm theo nhóm tuổi" rows={(data?.by_age_band || []).map((row) => ({ ...row, group: ageLabels[row.group] || row.group }))} valueKey="avg_npi" />
      <CohortChart title="NPI thử nghiệm theo nhóm nhiễm sắc thể" rows={(data?.by_chromosome_marker || []).map((row) => ({ ...row, group: row.group === 'X' ? 'XX' : row.group === 'Y' ? 'XY' : row.group }))} valueKey="avg_npi" />
    </div>
    <p className="text-xs text-gray-500">Nguồn: {data?.source || 'đang tải SQLite local'} · {data?.metric_note}</p>
  </div>
}
