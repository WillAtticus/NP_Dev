import { useEffect, useState } from 'react'
import { getCohortAnalytics, type CohortFilters, type LocalRole } from '../api/client'

type Cohort = { group: string; participants: number; sessions: number; avg_npi: number | null; avg_tbr: number | null }
type Metric = 'participants' | 'avg_npi' | 'avg_tbr'
type Analytics = {
  source: string
  participant_count: number
  session_count: number
  completed_session_count: number
  provenance_counts: Record<string, number>
  selected_provenance: string
  by_age_band: Cohort[]
  by_reported_sex: Cohort[]
  by_diet: Cohort[]
  metric_note: string
  filter_options: { studies: Array<{ id: string; name: string }>; sensor_types: string[]; quality_statuses: string[] }
}

const ageLabels: Record<string, string> = { I: 'Chưa rõ', C: '<10', J: '10–17', Y: '18–29', M: '30–49', E: '50+' }
const dietLabels: Record<string, string> = { vegetarian: 'Ăn chay', omnivore: 'Ăn mặn', 'Chưa ghi nhận': 'Chưa khai báo' }
const metricLabels: Record<Metric, string> = {
  participants: 'Số hồ sơ',
  avg_npi: 'NPI thử nghiệm trung bình',
  avg_tbr: 'TBR thử nghiệm trung bình',
}

function formatMetric(value: number | null, metric: Metric) {
  if (value == null || !Number.isFinite(value)) return '—'
  if (metric === 'participants') return new Intl.NumberFormat('vi-VN').format(value)
  return metric === 'avg_npi' ? value.toFixed(1) : value.toFixed(3)
}

export function CohortChart({ title, rows, metric }: { title: string; rows: Cohort[]; metric: Metric }) {
  const values = rows.map((row) => metric === 'participants' ? row.participants : row[metric]).filter((v): v is number => v != null && Number.isFinite(v))
  const max = metric === 'avg_npi' ? 100 : Math.max(1, ...values)
  const hasValues = values.length > 0

  return <section className="rounded-xl border border-np-border bg-np-panel p-5" aria-label={title}>
    <h2 className="font-semibold">{title}</h2>
    <p className="mt-1 text-xs text-gray-400">{metricLabels[metric]}{metric === 'avg_npi' ? ' · thang 0–100' : metric === 'avg_tbr' ? ' · tỷ số không đơn vị' : ''}</p>
    {!rows.length || !hasValues ? <div className="grid min-h-40 place-items-center text-sm text-gray-500">Chưa có dữ liệu lưu phù hợp để so sánh.</div> :
      <div className="mt-5 space-y-4">{rows.map((row) => {
        const value = metric === 'participants' ? row.participants : row[metric]
        const width = value == null ? 0 : Math.max(value > 0 ? 2 : 0, Math.min(100, value / max * 100))
        const detail = metric === 'participants' ? `${row.sessions} phiên hoàn tất` : `${row.participants} hồ sơ · ${row.sessions} phiên hoàn tất`
        return <div key={row.group}>
          <div className="mb-1 flex justify-between gap-3 text-xs"><span>{row.group}</span><strong>{formatMetric(value, metric)} <span className="font-normal text-gray-500">· {detail}</span></strong></div>
          <div className="h-3 overflow-hidden rounded-full bg-np-dark" role="progressbar" aria-label={`${row.group}: ${formatMetric(value, metric)}`} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value ?? 0}>
            <div className="h-full rounded-full bg-np-blue transition-all" style={{ width: `${width}%` }} />
          </div>
        </div>
      })}</div>}
    {metric !== 'participants' && <p className="mt-4 text-[11px] text-gray-500">Trung bình mô tả theo phiên hoàn tất; không phải phép so sánh hay kết luận lâm sàng.</p>}
  </section>
}

export default function AnalyticsPage({ role }: { role: LocalRole }) {
  const [data, setData] = useState<Analytics | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState<CohortFilters>({ provenance: 'all', study_id: 'all', sensor_type: 'all', quality_status: 'all', date_from: '', date_to: '' })
  const [appliedFilters, setAppliedFilters] = useState<CohortFilters>(filters)
  const [metric, setMetric] = useState<Metric>('participants')

  useEffect(() => {
    let active = true
    const load = () => getCohortAnalytics(appliedFilters).then(({ data: result }) => { if (active) { setData(result as Analytics); setError('') } })
      .catch((reason: any) => { if (active) setError(reason.response?.data?.detail || reason.message || 'Không tải được thống kê.') })
      .finally(() => { if (active) setLoading(false) })
    void load()
    const timer = window.setInterval(() => void load(), 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [appliedFilters])

  const provenance = data?.provenance_counts || {}
  const hasSynthetic = (provenance.simulated || 0) > 0 || (provenance.imported_benchmark || 0) > 0
  const ageRows = (data?.by_age_band || []).map((row) => ({ ...row, group: ageLabels[row.group] || row.group }))
  const sexRows = data?.by_reported_sex || []
  const dietRows = (data?.by_diet || []).map((row) => ({ ...row, group: dietLabels[row.group] || row.group }))

  return <div className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">TỔNG HỢP LOCAL</p><h1 className="page-title">Thống kê & so sánh nhóm</h1><p className="page-subtitle">Dữ liệu được tính từ hồ sơ và phiên thực sự đang lưu trên máy này.</p></div><div className="flex flex-wrap items-end gap-2">
      <label className="text-xs text-gray-500">Chỉ số so sánh<select aria-label="Chỉ số so sánh nhóm" value={metric} onChange={(event) => setMetric(event.target.value as Metric)} className="mt-1 block rounded-lg border border-np-border bg-white px-3 py-2 text-sm text-np-ink"><option value="participants">Số hồ sơ</option><option value="avg_npi">NPI thử nghiệm trung bình</option><option value="avg_tbr">TBR thử nghiệm trung bình</option></select></label>
      <button onClick={() => { setLoading(true); void getCohortAnalytics(appliedFilters).then(({ data: result }) => { setData(result as Analytics); setError('') }).catch((e: any) => setError(e.response?.data?.detail || e.message)).finally(() => setLoading(false)) }} className="rounded-lg border border-np-border bg-white px-4 py-2 text-sm text-np-ink">Làm mới</button>
    </div></header>
    <details className="rounded-xl border border-np-border bg-np-panel p-4">
      <summary className="cursor-pointer text-sm font-semibold text-np-ink">Bộ lọc dữ liệu</summary>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <label className="text-xs text-gray-500">Nguồn<select aria-label="Lọc nguồn dữ liệu" value={filters.provenance || 'all'} onChange={(event) => setFilters({ ...filters, provenance: event.target.value })} className="mt-1 block w-full rounded-lg border border-np-border bg-white px-3 py-2 text-sm text-np-ink"><option value="all">Tất cả nguồn</option><option value="device">Thiết bị</option><option value="simulated">Mô phỏng</option><option value="imported_benchmark">Benchmark nhập</option><option value="reprocessed">Xử lý lại</option></select></label>
        <label className="text-xs text-gray-500">Nghiên cứu<select aria-label="Lọc nghiên cứu" value={filters.study_id || 'all'} onChange={(event) => setFilters({ ...filters, study_id: event.target.value })} className="mt-1 block w-full rounded-lg border border-np-border bg-white px-3 py-2 text-sm text-np-ink"><option value="all">Tất cả nghiên cứu</option><option value="unassigned">Chưa gắn nghiên cứu</option>{(data?.filter_options.studies || []).map((study) => <option key={study.id} value={study.id}>{study.name}</option>)}</select></label>
        {role !== 'reviewer' && <label className="text-xs text-gray-500">Cảm biến<select aria-label="Lọc cảm biến" value={filters.sensor_type || 'all'} onChange={(event) => setFilters({ ...filters, sensor_type: event.target.value })} className="mt-1 block w-full rounded-lg border border-np-border bg-white px-3 py-2 text-sm text-np-ink"><option value="all">Tất cả cảm biến</option>{(data?.filter_options.sensor_types || []).map((sensor) => <option key={sensor} value={sensor}>{sensor}</option>)}</select></label>}
        <label className="text-xs text-gray-500">Chất lượng phiên<select aria-label="Lọc chất lượng phiên" value={filters.quality_status || 'all'} onChange={(event) => setFilters({ ...filters, quality_status: event.target.value })} className="mt-1 block w-full rounded-lg border border-np-border bg-white px-3 py-2 text-sm text-np-ink"><option value="all">Tất cả trạng thái</option><option value="unrated">Chưa đánh giá</option>{(data?.filter_options.quality_statuses || []).map((status) => <option key={status} value={status}>{status}</option>)}</select></label>
        <label className="text-xs text-gray-500">Từ ngày (UTC)<input aria-label="Từ ngày UTC" type="date" value={filters.date_from || ''} onChange={(event) => setFilters({ ...filters, date_from: event.target.value })} className="mt-1 block w-full rounded-lg border border-np-border bg-white px-3 py-2 text-sm text-np-ink" /></label>
        <label className="text-xs text-gray-500">Đến ngày (UTC)<input aria-label="Đến ngày UTC" type="date" value={filters.date_to || ''} onChange={(event) => setFilters({ ...filters, date_to: event.target.value })} className="mt-1 block w-full rounded-lg border border-np-border bg-white px-3 py-2 text-sm text-np-ink" /></label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3"><button onClick={() => { setLoading(true); setAppliedFilters({ ...filters }) }} className="rounded-lg bg-np-blue px-4 py-2 text-sm font-semibold text-white">Áp dụng bộ lọc</button><button onClick={() => { const reset: CohortFilters = { provenance: 'all', study_id: 'all', sensor_type: 'all', quality_status: 'all', date_from: '', date_to: '' }; setFilters(reset); setLoading(true); setAppliedFilters(reset) }} className="rounded-lg border border-np-border bg-white px-4 py-2 text-sm text-np-ink">Xóa bộ lọc</button><span className="text-xs text-gray-500">Ngày áp dụng theo UTC; phiên được lọc theo thời điểm bắt đầu.</span></div>
    </details>
    <div className="research-note">Thống kê mô tả nghiên cứu. NPI và TBR là chỉ số thử nghiệm, không dùng để chẩn đoán hay đánh giá hiệu quả lâm sàng.</div>
    {error && <div role="alert" className="error-banner">{error}</div>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {[['Hồ sơ trong bộ lọc', data?.participant_count], ['Tổng phiên trong bộ lọc', data?.session_count], ['Phiên hoàn tất trong bộ lọc', data?.completed_session_count], ['Mô phỏng trong toàn kho', provenance.simulated || 0]].map(([label, value]) => <div key={String(label)} className="card-surface p-5"><p className="text-xs text-gray-500">{label}</p><strong className="mt-2 block text-3xl text-np-ink">{value ?? (loading ? '…' : 0)}</strong></div>)}
    </div>
    {data && hasSynthetic && <div className="rounded-lg border border-blue-300 bg-blue-50 p-3 text-sm text-blue-900">Nguồn có dữ liệu tổng hợp: simulated {provenance.simulated || 0}, benchmark nhập {provenance.imported_benchmark || 0}. Khi chọn Tất cả nguồn, biểu đồ bên dưới gộp các nguồn đã lưu; không xem dữ liệu giả lập/benchmark là dữ liệu người thật.</div>}
    <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
      <CohortChart title="Theo nhóm tuổi" rows={ageRows} metric={metric} />
      <CohortChart title="Theo giới tính khai báo" rows={sexRows} metric={metric} />
      <CohortChart title="Theo chế độ ăn" rows={dietRows} metric={metric} />
    </div>
    <p className="text-xs text-gray-500">Nguồn: {data?.source || 'đang tải SQLite local'} · {data?.metric_note}</p>
  </div>
}
