import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { analyseSession, getDeviceStatus, getSessions } from '../api/client'
import type { SessionRecord } from '../api/client'

type Analysis = {
  analysis?: {
    freqs?: number[]; psd?: number[]; filtered_signal?: number[]; sample_rate_hz?: number
    raw_signal_preview?: number[]; raw_signal_preview_stride?: number
    quality_status?: string; quality_flags?: string[]; dominant_freq_hz?: number; tbr?: number
    npi?: { npi_value?: number | null; category?: string | null }
  }
  disclaimer?: string
}

const fmt = (value: number | null | undefined, digits = 2) => value == null || !Number.isFinite(value) ? '—' : value.toFixed(digits)
const categoryLabel = (value?: string | null) => ({
  experimental_reference_range: 'Trong khoảng tham chiếu thử nghiệm',
  experimental_monitoring: 'Theo dõi theo giả thuyết thử nghiệm',
  outside_experimental_reference_range: 'Ngoài khoảng tham chiếu thử nghiệm',
}[value || ''] || 'Chưa có phân loại')
const provenanceLabel = (value: string) => ({ simulated: 'Mô phỏng', device: 'Thiết bị', imported_benchmark: 'Benchmark nhập', reprocessed: 'Xử lý lại' }[value] || value)

function Sparkline({ values, color = '#4285f4', fill = false }: { values?: number[]; color?: string; fill?: boolean }) {
  const points = useMemo(() => {
    if (!values?.length) return ''
    const stride = Math.max(1, Math.floor(values.length / 260))
    const sampled = values.filter((_, index) => index % stride === 0)
    const min = Math.min(...sampled); const max = Math.max(...sampled); const span = max - min || 1
    return sampled.map((value, index) => `${(index / Math.max(1, sampled.length - 1)) * 100},${92 - ((value - min) / span) * 82}`).join(' ')
  }, [values])
  if (!points) return <div className="chart-empty">Chưa có chuỗi dữ liệu để hiển thị.</div>
  return <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="np-chart" role="img" aria-label="Biểu đồ dữ liệu phiên đo">
    {fill && <polygon points={`0,100 ${points} 100,100`} fill={`${color}18`} />}
    <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
  </svg>
}

export default function OverviewPage({ role = 'operator' }: { role?: string }) {
  const [status, setStatus] = useState<any>(null)
  const [sessions, setSessions] = useState<SessionRecord[]>([])
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [axis, setAxis] = useState('x_counts')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    const refresh = async () => {
      try {
        const [deviceResult, sessionResult] = await Promise.all([getDeviceStatus(), getSessions(50, 0)])
        if (!alive) return
        setStatus(deviceResult.data)
        const completed = sessionResult.data.sessions.filter((session) => session.status === 'completed')
        setSessions(completed)
        setError('')
        const latest = completed[0]
        if (latest && latest.profile_id && (latest.sensor_type !== 'ADXL345' || axis)) {
          try {
            const result = await analyseSession({ session_id: latest.id, profile_id: latest.profile_id, channel: latest.sensor_type === 'ADXL345' ? axis : undefined })
            if (alive) setAnalysis(result.data)
          } catch { if (alive) setAnalysis(null) }
        } else setAnalysis(null)
      } catch (reason: any) {
        if (alive) setError(reason.response?.data?.detail || reason.message || 'Không tải được thông tin phiên đo.')
      } finally { if (alive) setLoading(false) }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 10000)
    return () => { alive = false; window.clearInterval(timer) }
  }, [axis])

  const current = sessions[0]
  const previous = sessions[1]
  const measuredNpi = analysis?.analysis?.npi?.npi_value ?? current?.npi_value
  const npiCategory = analysis?.analysis?.npi?.category ?? current?.npi_category
  const npiDisplay = measuredNpi == null ? '—' : fmt(measuredNpi, 1)
  const filtered = analysis?.analysis?.filtered_signal || analysis?.analysis?.raw_signal_preview
  const showingRawPreview = !!analysis?.analysis?.raw_signal_preview && !analysis?.analysis?.filtered_signal
  const freqs = analysis?.analysis?.freqs
  const psd = analysis?.analysis?.psd
  const combined = useMemo(() => freqs && psd ? freqs.map((x, i) => ({ x, y: psd[i] })).filter((point) => point.x >= 0 && point.x <= 20).map((point) => point.y) : undefined, [freqs, psd])

  return <div className="space-y-5">
    <div className="overview-topline">
      <div><p className="eyebrow">NEUROPULSE · NỀN TẢNG NGHIÊN CỨU</p><h1 className="page-title">Kết quả phiên đo</h1><p className="page-subtitle">Tổng quan phiên gần nhất và chất lượng tín hiệu đã lưu</p></div>
      <div className={`device-pill ${status?.is_connected ? 'is-connected' : ''}`}><span className="status-dot" />{status?.is_connected ? 'Thiết bị đã kết nối' : 'Chưa kết nối'}<small>{status?.sensor_type || 'Local · offline'}</small></div>
    </div>

    <div className="research-note">Chỉ số và dải hiển thị là giả thuyết thử nghiệm của nhóm; chưa được xác nhận lâm sàng và không dùng để chẩn đoán.</div>
    {error && <div role="alert" className="error-banner">{error}</div>}
    {status?.is_simulated && <div className="simulation-banner"><strong>DỮ LIỆU MÔ PHỎNG{status.simulator_profile ? ` · ${status.simulator_profile.toUpperCase()}` : ''}</strong><span>Tín hiệu tổng hợp không phải dữ liệu đo từ người tham gia.</span></div>}

    {!current ? <section className="empty-session card-surface">
      <div className="empty-icon">∿</div><h2>Chưa có phiên đo hoàn tất</h2><p>Bắt đầu thu nhận tín hiệu để xem kết quả, biểu đồ và chất lượng phiên tại đây.</p>
      <Link to="/live" className="primary-action">Bắt đầu phiên đo <span>→</span></Link>
      <div className="device-summary"><span>Trạng thái thiết bị</span><strong>{status?.is_connected ? 'Đã kết nối' : 'Chưa kết nối'}</strong><small>{status?.is_streaming ? 'Đang truyền dữ liệu' : 'Có thể kết nối từ mục Thiết bị'}</small></div>
    </section> : <div className="result-layout">
      <div className="result-main">
        <section className="hero-result card-surface">
          <div className="session-heading"><div><span className="eyebrow">PHIÊN GẦN NHẤT</span><h2>{current.participant_code || 'Phiên nghiên cứu'}</h2><p>{current.start_time ? new Date(current.start_time).toLocaleString() : 'Thời điểm không có sẵn'}{role !== 'reviewer' ? ` · ${current.sensor_type}` : ''}{current.notes?.startsWith('Kịch bản mô phỏng:') ? ` · ${current.notes}` : ''}</p></div>
            <span className={`provenance-tag provenance-${current.provenance}`}>{provenanceLabel(current.provenance)}</span></div>
          <div className="hero-score"><span className="eyebrow">NEUROPULSE INDEX · THỬ NGHIỆM</span><div className="score-number">{npiDisplay}</div><div className="score-caption">{categoryLabel(npiCategory)}</div></div>
          <div className="waveform-wrap"><div className="chart-caption"><span>{showingRawPreview ? 'Tín hiệu thô · chưa đủ dữ liệu phân tích' : 'Dạng sóng vi chấn đã lọc'}</span><span>{current.sensor_type === 'ADXL345' && role !== 'reviewer' && <label className="axis-picker">Trục <select value={axis} onChange={(event) => setAxis(event.target.value)}><option value="">Chọn trục</option><option value="x_counts">X</option><option value="y_counts">Y</option><option value="z_counts">Z</option></select></label>}{analysis?.analysis?.sample_rate_hz || current.sample_rate_hz || '—'} Hz · {current.sample_count?.toLocaleString() || '—'} mẫu</span></div><Sparkline values={filtered} color="#3578e5" fill /></div>
          <div className="chart-axis"><span>Đầu phiên</span><span>Chuỗi mẫu theo thời gian</span><span>Cuối phiên</span></div>
          {!analysis && <p className="chart-footnote">Không tải được chuỗi mẫu của phiên này; chỉ hiển thị các giá trị có trong bản ghi.</p>}
          {showingRawPreview && <p className="chart-footnote">Dữ liệu vẫn được vẽ từ mẫu thô đã lưu. Cửa sổ chưa đủ dài nên hệ thống giữ trạng thái chưa phân tích và không tính chỉ số.</p>}
        </section>

        <div className="lower-grid">
        {role !== 'reviewer' && <section className="card-surface chart-card"><div className="card-heading"><div><h3>Phổ tần số</h3><p>PSD từ pipeline xử lý · 0–20 Hz</p></div><span className="mini-icon">⌁</span></div><Sparkline values={combined} color="#7c65d8" fill /><div className="chart-axis"><span>0 Hz</span><span>10 Hz</span><span>20 Hz</span></div></section>}
          <section className="card-surface chart-card"><div className="card-heading"><div><h3>Chất lượng tín hiệu</h3><p>Trạng thái pipeline</p></div><span className="quality-state">{analysis?.analysis?.quality_status || current.quality_status || 'Chưa đánh giá'}</span></div>
            <div className="quality-metric"><span className="quality-ring">{analysis?.analysis?.quality_status === 'VALID_FOR_ANALYSIS' ? '✓' : '·'}</span><div><strong>{analysis?.analysis?.quality_status === 'VALID_FOR_ANALYSIS' ? 'Đủ điều kiện phân tích' : 'Xem trạng thái phiên'}</strong><small>{analysis?.analysis?.quality_flags?.length ? analysis.analysis.quality_flags.join(', ') : 'Cờ chất lượng theo pipeline hiện có'}</small></div></div>
            <div className="quality-detail"><span>Tần số trội</span><b>{fmt(analysis?.analysis?.dominant_freq_hz ?? current.dominant_freq_hz, 2)} Hz</b></div>
          </section>
        </div>
      </div>

      <aside className="result-side">
        <section className="card-surface side-card"><div className="card-heading"><h3>Thông số phiên</h3><Link to="/sessions">Tất cả phiên →</Link></div>
          <div className="metric-grid"><div className="metric-tile metric-primary"><small>NPI thử nghiệm</small><strong>{npiDisplay}</strong><span>{categoryLabel(npiCategory)}</span></div><div className="metric-tile"><small>TBR (3–6 Hz)</small><strong>{fmt(analysis?.analysis?.tbr ?? current.tbr, 3)}</strong><span>Tỷ số băng tần thử nghiệm</span></div><div className="metric-tile"><small>Tần số trội</small><strong>{fmt(analysis?.analysis?.dominant_freq_hz ?? current.dominant_freq_hz, 2)} <i>Hz</i></strong><span>Từ phổ phiên</span></div><div className="metric-tile"><small>Thời lượng</small><strong>{current.duration_sec ? `${Math.floor(current.duration_sec / 60)}m ${Math.round(current.duration_sec % 60)}s` : '—'}</strong><span>{current.sample_rate_hz || '—'} Hz lấy mẫu</span></div></div>
        </section>
        {previous && <section className="card-surface side-card"><div className="card-heading"><h3>So sánh phiên trước</h3><span className="neutral-label">Giá trị ghi nhận</span></div><div className="comparison-row"><div><small>Phiên hiện tại · NPI</small><strong>{fmt(current.npi_value, 1)}</strong></div><div><small>Phiên trước · NPI</small><strong>{fmt(previous.npi_value, 1)}</strong></div></div><p className="comparison-footnote">So sánh mô tả giữa hai phiên; không diễn giải là cải thiện hay xấu đi.</p></section>}
        <section className="session-complete card-surface"><div className="complete-mark">✓</div><div><strong>{current.status === 'completed' ? 'Phiên đã lưu' : current.status}</strong><small>{current.id}</small></div></section>
        {role !== 'reviewer' && <section className="card-surface system-card"><div className="card-heading"><h3>Thiết bị & dữ liệu</h3><Link to="/device">Chi tiết →</Link></div><div className="system-line"><span>Kết nối</span><b>{status?.is_connected ? 'Đã kết nối' : 'Đang ngắt'}</b></div><div className="system-line"><span>Luồng</span><b>{status?.is_streaming ? 'Đang thu nhận' : 'Không hoạt động'}</b></div><div className="system-line"><span>Provenance</span><b>{provenanceLabel(current.provenance)}</b></div></section>}
      </aside>
    </div>}
    {loading && <p className="loading-note">Đang tải phiên đo…</p>}
  </div>
}
