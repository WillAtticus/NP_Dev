import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { createPatient, getAcquisitionStatus, getDeviceStatus, getLiveBuffer, getStudies, lookupPatient, startAcquisition, stopAcquisition } from '../api/client'

const PROFILE_BY_SENSOR: Record<string, string> = { PIEZO_LDT0_028K: 'piezo_butterworth_1_20_default', ADXL345: 'adxl345_triaxial_100hz' }
const errorText = (e: any) => e.response?.data?.detail || e.message || 'Thao tác thất bại.'

export default function LiveSensingPage() {
  const [status, setStatus] = useState<any>(null)
  const [device, setDevice] = useState<any>(null)
  const [studies, setStudies] = useState<any[]>([])
  const [participantCode, setParticipantCode] = useState('')
  const [participantMode, setParticipantMode] = useState<'new' | 'existing'>('new')
  const [participantName, setParticipantName] = useState('')
  const [dateOfBirth, setDateOfBirth] = useState('')
  const [chromosomeMarker, setChromosomeMarker] = useState<'' | 'X' | 'Y'>('')
  const [studyId, setStudyId] = useState('')
  const [selectedChannel, setSelectedChannel] = useState('raw_counts')
  const [message, setMessage] = useState('')
  const [working, setWorking] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const fetchStatus = async () => {
    try {
      const [acquisition, connection] = await Promise.all([getAcquisitionStatus(), getDeviceStatus()])
      setStatus(acquisition.data); setDevice(connection.data)
      if (connection.data.sensor_type === 'ADXL345' && selectedChannel === 'raw_counts') setSelectedChannel('x')
      if (connection.data.sensor_type !== 'ADXL345') setSelectedChannel('raw_counts')
    } catch (e: any) { setMessage(errorText(e)) }
  }
  useEffect(() => {
    void fetchStatus()
    getStudies().then(({ data }) => setStudies(data)).catch((e) => setMessage(errorText(e)))
    const timer = window.setInterval(() => void fetchStatus(), 2000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    let alive = true
    let timer: number
    const plot = async () => {
      try {
        const { data } = await getLiveBuffer(selectedChannel, 800)
        const values: number[] = data?.samples || []
        const canvas = canvasRef.current; const ctx = canvas?.getContext('2d')
        if (ctx && canvas && values.length > 1) {
          const { width, height } = canvas; ctx.clearRect(0, 0, width, height)
          ctx.strokeStyle = '#2D3748'; ctx.beginPath(); ctx.moveTo(0, height / 2); ctx.lineTo(width, height / 2); ctx.stroke()
          ctx.strokeStyle = '#00D4FF'; ctx.lineWidth = 1.5; ctx.beginPath()
          const min = Math.min(...values), range = Math.max(Math.max(...values) - min, 1)
          values.forEach((v, i) => { const x = i / (values.length - 1) * width, y = height - ((v - min) / range) * (height - 20) - 10; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y) })
          ctx.stroke()
        }
      } catch { /* Empty buffer while idle is expected. */ }
      if (alive) timer = window.setTimeout(plot, 150)
    }
    void plot()
    return () => { alive = false; window.clearTimeout(timer) }
  }, [selectedChannel])

  const begin = async (event: FormEvent) => {
    event.preventDefault(); setWorking(true); setMessage('')
    try {
      if (!device?.is_connected) throw new Error('Hãy kết nối cảm biến trước khi bắt đầu phiên.')
      const sensor = device.sensor_type
      if (!PROFILE_BY_SENSOR[sensor]) throw new Error('Không có hồ sơ xử lý cho loại cảm biến này.')
      const study = studies.find((item) => item.id === studyId)
      if (study && study.sensor_type !== sensor) throw new Error('Nghiên cứu đã chọn không khớp loại cảm biến.')
      let code = participantCode.trim().toUpperCase()
      if (participantMode === 'new') {
        if (!participantName.trim()) throw new Error('Nhập tên/mã hiển thị người tham gia trước khi cấp mã.')
        if (!chromosomeMarker) throw new Error('Chọn XX hoặc XY theo quy ước của nhóm để tạo mã bệnh nhân.')
        const created = await createPatient({
          full_name: participantName.trim(),
          date_of_birth: dateOfBirth || undefined,
          chromosome_marker: chromosomeMarker,
        })
        code = created.data.patient_code
        setParticipantCode(code)
        setParticipantMode('existing')
      } else {
        if (!code) throw new Error('Nhập mã bệnh nhân đã được cấp.')
        await lookupPatient(code)
      }
      await startAcquisition({ session_id: crypto.randomUUID(), sensor_type: sensor, profile_id: PROFILE_BY_SENSOR[sensor], channel: sensor === 'ADXL345' ? selectedChannel : null, participant_code: code, study_id: studyId || null })
      setMessage(`Đã bắt đầu phiên cho mã ${code}. Để đủ cửa sổ phân tích hiện tại, hãy ghi ít nhất 8 giây rồi dừng và lưu.`)
      await fetchStatus()
    } catch (e) { setMessage(errorText(e)) } finally { setWorking(false) }
  }
  const stop = async () => { setWorking(true); try { await stopAcquisition(); setMessage('Đã dừng và lưu phiên.'); await fetchStatus() } catch (e) { setMessage(errorText(e)) } finally { setWorking(false) } }

  return <div className="space-y-6">
    <div><h1 className="text-2xl font-bold tracking-tight">Live Sensing Stream</h1><p className="text-sm text-gray-400 mt-1">Xem dạng sóng và thông tin chất lượng thu nhận.</p></div>
    <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-amber-200 text-xs">Prototype nghiên cứu. Khi bắt đầu phiên mới, hệ thống sẽ tự tạo hồ sơ local và cấp mã bệnh nhân; mã được lưu cùng phiên đo. Chế độ này không xác thực danh tính. Kết quả không dùng để chẩn đoán.</div>
    {message && <div role="status" className="p-3 bg-white/5 border border-white/10 rounded text-sm text-gray-200">{message}</div>}
    {!status?.is_streaming && <form onSubmit={begin} className="bg-np-panel border border-np-border rounded-lg p-5 grid md:grid-cols-3 gap-4 items-end">
      <div className="md:col-span-1 space-y-2">
        <label className="text-xs text-gray-400">Hồ sơ người tham gia<select value={participantMode} onChange={(e) => setParticipantMode(e.target.value as 'new' | 'existing')} className="mt-1 w-full bg-np-dark border border-np-border rounded px-3 py-2 text-sm text-white"><option value="new">Người tham gia mới · tự cấp mã</option><option value="existing">Dùng mã đã có</option></select></label>
        {participantMode === 'new' ? <div className="grid grid-cols-2 gap-2">
          <input aria-label="Tên hoặc mã hiển thị người tham gia" required maxLength={160} placeholder="Tên / mã hiển thị" value={participantName} onChange={(e) => setParticipantName(e.target.value)} className="bg-np-dark border border-np-border rounded px-3 py-2 text-sm text-white" />
          <select aria-label="Nhiễm sắc thể theo quy ước nhóm" required value={chromosomeMarker} onChange={(e) => setChromosomeMarker(e.target.value as '' | 'X' | 'Y')} className="bg-np-dark border border-np-border rounded px-3 py-2 text-sm text-white"><option value="">Chọn XX/XY</option><option value="X">XX (mã X)</option><option value="Y">XY (mã Y)</option></select>
          <input aria-label="Ngày sinh, nếu có" type="date" value={dateOfBirth} onChange={(e) => setDateOfBirth(e.target.value)} className="col-span-2 bg-np-dark border border-np-border rounded px-3 py-2 text-sm text-white" />
        </div> : <label className="block text-xs text-gray-400">Mã bệnh nhân<input required maxLength={20} value={participantCode} onChange={(e) => setParticipantCode(e.target.value.toUpperCase())} className="mt-1 w-full bg-np-dark border border-np-border rounded px-3 py-2 text-sm font-mono text-white" /></label>}
        {participantCode && <p className="text-xs text-emerald-300">Mã đã cấp cho phiên: <strong className="font-mono">{participantCode}</strong></p>}
      </div>
      <label className="text-xs text-gray-400">Nghiên cứu (tuỳ chọn)<select value={studyId} onChange={(e) => setStudyId(e.target.value)} className="mt-1 w-full bg-np-dark border border-np-border rounded px-3 py-2 text-sm text-white"><option value="">Không gắn nghiên cứu</option>{studies.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.sensor_type})</option>)}</select></label>
      {device?.sensor_type === 'ADXL345' && <label className="text-xs text-gray-400">Trục phân tích<select value={selectedChannel} onChange={(e) => setSelectedChannel(e.target.value)} className="mt-1 w-full bg-np-dark border border-np-border rounded px-3 py-2 text-sm text-white">{['x','y','z','mag'].map((ch) => <option key={ch}>{ch}</option>)}</select></label>}
      <button disabled={working || !device?.is_connected} className="px-4 py-2 bg-np-green text-black font-semibold rounded disabled:opacity-50">{working ? 'Đang xử lý…' : 'Bắt đầu phiên'}</button>
      {!device?.is_connected && <p className="md:col-span-2 text-xs text-gray-400">Chưa kết nối cảm biến. Mở mục Thiết bị để chọn simulator hoặc cổng serial.</p>}
    </form>}
    {status?.is_streaming && <div className="flex items-center justify-between bg-np-panel border border-np-border rounded-lg p-4"><span>Đang ghi phiên <code>{status.active_session_id || '—'}</code></span><button disabled={working} onClick={() => void stop()} className="px-4 py-2 bg-red-600 text-white font-semibold rounded disabled:opacity-50">Dừng và lưu</button></div>}
    {status?.is_simulated && <div className="bg-blue-500/15 border border-blue-500/40 rounded-lg p-3 text-blue-200 text-xs">Dữ liệu tổng hợp · kịch bản {(device?.simulator_profile || 'healthy').toUpperCase()} — provenance: simulated; không phải phép đo người tham gia.</div>}
    <div className="bg-np-panel border border-np-border rounded-lg p-5"><div className="text-sm font-semibold mb-3">Waveform — {selectedChannel}</div><div className="bg-np-dark border border-np-border rounded overflow-hidden"><canvas ref={canvasRef} width={800} height={320} className="w-full h-80 block" /></div><div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 text-xs text-gray-300"><div>Rate: <strong>{status?.effective_sample_rate || 0} Hz</strong></div><div>Samples: <strong>{status?.total_samples || 0}</strong></div><div>Sequence gaps: <strong>{status?.sequence_gaps || 0}</strong></div><div>CRC errors: <strong>{status?.crc_errors || 0}</strong></div></div></div>
  </div>
}
