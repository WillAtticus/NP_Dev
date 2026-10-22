import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { analyseSession, createPatient, getAcquisitionStatus, getCurrentPatientCode, getDeviceStatus, getLiveBuffer, lookupPatient, setCurrentPatientCode, startAcquisition, stopAcquisition } from '../api/client'
import type { PatientLookup, SessionRecord } from '../api/client'

const fmt = (value?: number | null, digits = 2) => value == null || !Number.isFinite(value) ? '—' : value.toFixed(digits)
const category = (key?: string | null) => ({ experimental_reference_range: 'Trong khoảng tham chiếu thử nghiệm', experimental_monitoring: 'Theo dõi theo giả thuyết thử nghiệm', outside_experimental_reference_range: 'Ngoài khoảng tham chiếu thử nghiệm' }[key || ''] || 'Chưa đủ dữ liệu phân tích')
const qualityLabel = (key?: string | null) => ({ VALID_FOR_ANALYSIS: 'Đủ dữ liệu để xử lý', WARNING: 'Tín hiệu cần được kiểm tra', INVALID: 'Vui lòng đo lại', INSUFFICIENT_DATA: 'Phiên đo chưa đủ dài', ANALYSIS_PENDING: 'Đang xử lý' }[key || ''] || 'Chưa đánh giá')

export default function PatientMeasurementPage() {
  const [code, setCode] = useState(getCurrentPatientCode())
  const [lookup, setLookup] = useState<PatientLookup | null>(null)
  const [device, setDevice] = useState<any>(null)
  const [streaming, setStreaming] = useState(false)
  const [live, setLive] = useState<number[]>([])
  const [selected, setSelected] = useState<SessionRecord | null>(null)
  const [analysis, setAnalysis] = useState<any>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [chromosome, setChromosome] = useState<'X' | 'Y'>('X')
  const [dob, setDob] = useState('')
  const [channel, setChannel] = useState('raw_counts')
  const activeCode = code.trim().toUpperCase()

  const refresh = useCallback(async () => {
    setCurrentPatientCode(activeCode)
    if (!activeCode) { setLookup(null); setSelected(null); setAnalysis(null); return }
    try {
      const [profile, deviceResult, acquisition] = await Promise.all([lookupPatient(activeCode), getDeviceStatus(), getAcquisitionStatus()])
      setLookup(profile.data); setDevice(deviceResult.data)
      const ownStream = acquisition.data?.is_streaming && acquisition.data?.active_session_id && profile.data.sessions.some((s) => s.id === acquisition.data.active_session_id)
      setStreaming(!!ownStream)
      const sessions = profile.data.sessions.filter((s) => s.status === 'completed')
      setSelected((current) => current && sessions.some((s) => s.id === current.id) ? current : sessions[0] || null)
      if (ownStream) {
        const sensor = deviceResult.data.sensor_type
        const nextChannel = sensor === 'ADXL345' ? channel === 'raw_counts' ? 'x_counts' : channel : 'raw_counts'
        if (nextChannel !== channel) setChannel(nextChannel)
        const result = await getLiveBuffer(nextChannel, 1800)
        setLive(result.data.samples || [])
      } else setLive([])
      setError('')
    } catch (reason: any) {
      setLookup(null); setSelected(null); setAnalysis(null); setStreaming(false); setLive([])
      setError(reason.response?.status === 404 ? 'Chưa tìm thấy hồ sơ. Bạn có thể tạo mã bệnh nhân mới bên dưới.' : reason.response?.data?.detail || reason.message || 'Không tải được hồ sơ.')
    }
  }, [activeCode, channel])

  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 1000); return () => window.clearInterval(timer) }, [refresh])

  useEffect(() => {
    let liveEffect = true
    const loadAnalysis = async () => {
      if (!selected || selected.status !== 'completed') { setAnalysis(null); return }
      try {
        const result = await analyseSession({ session_id: selected.id, profile_id: selected.profile_id, channel: selected.sensor_type === 'ADXL345' ? 'x_counts' : undefined })
        if (liveEffect) setAnalysis(result.data.analysis)
      } catch { if (liveEffect) setAnalysis(null) }
    }
    void loadAnalysis()
    return () => { liveEffect = false }
  }, [selected])

  const waveform = streaming ? live : (analysis?.filtered_signal || analysis?.raw_signal_preview || [])
  const waveformPoints = useMemo(() => {
    if (!waveform.length) return ''
    const stride = Math.max(1, Math.floor(waveform.length / 650)); const points = waveform.filter((_: number, i: number) => i % stride === 0)
    const min = Math.min(...points), span = Math.max(...points) - min || 1
    return points.map((v: number, i: number) => `${i / Math.max(points.length - 1, 1) * 1000},${180 - ((v - min) / span) * 155}`).join(' ')
  }, [waveform])
  const npi = analysis?.npi?.npi_value ?? selected?.npi_value
  const npiCategory = analysis?.npi?.category ?? selected?.npi_category

  const makeProfile = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const created = await createPatient({ full_name: name.trim(), chromosome_marker: chromosome, date_of_birth: dob || undefined })
      setCode(created.data.patient_code); setCurrentPatientCode(created.data.patient_code); setName('')
      setError(`Đã cấp mã bệnh nhân ${created.data.patient_code}. Hãy giữ mã này để xem lại lịch sử.`)
    } catch (reason: any) { setError(reason.response?.data?.detail || reason.message || 'Không tạo được hồ sơ.') }
    finally { setBusy(false) }
  }

  const toggleMeasurement = async () => {
    setBusy(true); setError('')
    try {
      if (streaming) await stopAcquisition()
      else {
        if (!lookup) throw new Error('Nhập mã bệnh nhân hợp lệ hoặc tạo hồ sơ mới trước khi đo.')
        if (!device?.is_connected) throw new Error('Thiết bị chưa sẵn sàng. Nhờ nhân viên kết nối thiết bị hoặc simulator.')
        const sensor = device.sensor_type
        const profile = sensor === 'ADXL345' ? 'adxl345_triaxial_100hz' : 'piezo_butterworth_1_20_default'
        const selectedChannel = sensor === 'ADXL345' ? 'x_counts' : null
        setChannel(selectedChannel || 'raw_counts')
        await startAcquisition({ session_id: crypto.randomUUID(), sensor_type: sensor, profile_id: profile, channel: selectedChannel, participant_code: activeCode })
      }
      await refresh()
    } catch (reason: any) { setError(reason.response?.data?.detail || reason.message || 'Không thể bắt đầu phiên đo.') }
    finally { setBusy(false) }
  }

  const changeCode = (value: string) => { const normalized = value.toUpperCase(); setCode(normalized); setCurrentPatientCode(normalized); setLookup(null); setSelected(null); setAnalysis(null) }

  return <div className="patient-measurement space-y-4">
    <header className="patient-header"><div><p className="eyebrow">NEUROPULSE · THEO DÕI CÁ NHÂN</p><h1 className="page-title">Phiên đo của tôi</h1><p className="page-subtitle">Kết quả được lưu theo mã bệnh nhân đang chọn.</p></div><div className={`device-pill ${device?.is_connected ? 'is-connected' : ''}`}><span className="status-dot" />{device?.is_connected ? 'Thiết bị sẵn sàng' : 'Chưa kết nối'}<small>{streaming ? 'Đang đo' : 'Chờ phiên đo'}</small></div></header>
    <div className="research-note">NPI và thông báo là kết quả thử nghiệm, chưa được xác nhận lâm sàng và không dùng để chẩn đoán.</div>
    {error && <div role="status" className="error-banner">{error}</div>}
    {device?.is_simulated && <div className="simulation-banner"><strong>DỮ LIỆU MÔ PHỎNG · {(device.simulator_profile || 'healthy').toUpperCase()}</strong><span>Tín hiệu tổng hợp, không phải phép đo người tham gia.</span></div>}
    <div className="patient-code-bar card-surface"><div><span className="eyebrow">MÃ BỆNH NHÂN CỦA PHIÊN</span><p>Phiên tiếp theo sẽ gắn với mã đang chọn.</p></div><input aria-label="Mã bệnh nhân" value={code} disabled={streaming} onChange={(e) => changeCode(e.target.value)} onBlur={() => void refresh()} placeholder="Nhập mã bệnh nhân"/><button disabled={streaming || !activeCode} onClick={() => void refresh()}>Mở hồ sơ</button></div>
    {!lookup && <form onSubmit={makeProfile} className="new-patient-form card-surface"><div><strong>Tạo mã bệnh nhân mới</strong><p>Hệ thống cấp mã để lưu lịch sử đo cá nhân.</p></div><input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên người sử dụng" aria-label="Tên người sử dụng"/><select value={chromosome} onChange={(e) => setChromosome(e.target.value as 'X' | 'Y')} aria-label="Nhiễm sắc thể"><option value="X">XX</option><option value="Y">XY</option></select><input type="date" value={dob} onChange={(e) => setDob(e.target.value)} aria-label="Ngày sinh (tuỳ chọn)"/><button disabled={busy} className="patient-create">{busy ? 'Đang tạo…' : 'Cấp mã bệnh nhân'}</button></form>}

    <div className="patient-result-grid">
      <div className="patient-main-column">
        <section className="card-surface patient-wave-card"><div className="card-heading"><div><span className="eyebrow">{streaming ? 'ĐANG THU NHẬN' : 'DẠNG SÓNG VI CHẤN'}</span><h2>{streaming ? 'Tín hiệu live' : selected ? 'Phiên đo gần nhất' : 'Sẵn sàng đo'}</h2></div><span className={`quality-state ${streaming ? 'streaming-state' : ''}`}>{streaming ? 'LIVE' : selected?.status === 'completed' ? 'Đã lưu' : 'Chưa có phiên'}</span></div><div className="patient-wave"><svg viewBox="0 0 1000 200" preserveAspectRatio="none" role="img" aria-label="Biểu đồ dạng sóng tín hiệu vi chấn">{waveformPoints ? <polyline points={waveformPoints} fill="none" stroke="#3478e8" strokeWidth="2" vectorEffect="non-scaling-stroke"/> : null}</svg>{!waveformPoints && <div className="patient-wave-empty">{lookup ? 'Nhấn “Bắt đầu đo” để xem tín hiệu truyền về.' : 'Nhập hoặc tạo mã bệnh nhân để bắt đầu.'}</div>}</div><div className="chart-axis"><span>Bắt đầu</span><span>{streaming ? `${live.length.toLocaleString()} mẫu đang nhận` : analysis?.quality_status || selected?.quality_status || 'Chưa có dữ liệu'}</span><span>Hiện tại</span></div></section>
        <section className="patient-npi-card"><span className="eyebrow">NEUROPULSE INDEX · THỬ NGHIỆM</span><strong>{streaming ? 'Đang thu nhận' : fmt(npi, 1)}</strong><span className="patient-score-status">{streaming ? 'Chỉ số được tính khi kết thúc phiên và đủ dữ liệu' : category(npiCategory)}</span></section>
        <section className="card-surface patient-clinical-card"><div className="card-heading"><div><h3>Thông tin phiên đo</h3><p>Thông tin cá nhân của phiên hiện tại</p></div></div><div className="patient-clinical-grid"><div><small>Chất lượng phép đo</small><strong>{streaming ? 'Đang thu nhận' : qualityLabel(analysis?.quality_status || selected?.quality_status)}</strong></div><div><small>Thời lượng</small><strong>{streaming ? 'Đang đo' : selected?.duration_sec ? `${Math.floor(selected.duration_sec / 60)} phút ${Math.round(selected.duration_sec % 60)} giây` : '—'}</strong></div><div className="patient-clinical-notice"><small>Thông báo thử nghiệm</small><strong>{npiCategory === 'outside_experimental_reference_range' ? 'Ngoài khoảng tham chiếu demo' : npiCategory === 'experimental_monitoring' ? 'Theo dõi theo giả thuyết demo' : npiCategory ? 'Trong khoảng tham chiếu demo' : 'Chưa có kết quả phân tích'}</strong></div></div><p className="chart-footnote">Các ngưỡng chỉ phục vụ trình diễn giả thuyết nghiên cứu, không phải kết luận y khoa.</p></section>
      </div>
      <aside className="patient-history card-surface"><div className="card-heading"><div><h3>Lịch sử đo</h3><p>{lookup?.patient.patient_code || 'Nhập mã để mở lịch sử'}</p></div></div>{lookup?.sessions.length ? <div className="patient-session-list">{lookup.sessions.map((session) => <button key={session.id} onClick={() => setSelected(session)} className={selected?.id === session.id ? 'selected' : ''}><strong>{session.start_time ? new Date(session.start_time).toLocaleDateString() : 'Phiên đo'}</strong><span>{session.status === 'completed' ? `NPI ${fmt(session.npi_value, 1)}` : session.status}</span><small>{session.duration_sec ? `${Math.round(session.duration_sec)} giây` : 'Đang cập nhật'}</small></button>)}</div> : <div className="patient-history-empty">Lịch sử phiên đo của mã này sẽ xuất hiện ở đây.</div>}</aside>
    </div>
    <div className="patient-start-wrap"><button className={`patient-start-button ${streaming ? 'stop' : ''}`} disabled={busy || (!streaming && (!lookup || !device?.is_connected))} onClick={() => void toggleMeasurement()}>{busy ? 'Đang xử lý…' : streaming ? 'Dừng và lưu phiên đo' : 'Bắt đầu đo'}</button><span>{!device?.is_connected && 'Thiết bị đang chờ nhân viên kết nối tại máy này.'}</span></div>
  </div>
}
