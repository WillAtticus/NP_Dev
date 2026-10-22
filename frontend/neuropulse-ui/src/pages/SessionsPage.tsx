import { useCallback, useEffect, useState } from 'react'
import { exportSession, getSessions } from '../api/client'
import type { SessionRecord } from '../api/client'

const fmtDate = (value?: string | null) => value ? new Date(value).toLocaleString() : '—'

export default function SessionsPage({ role = 'operator' }: { role?: string }) {
  const [sessions, setSessions] = useState<SessionRecord[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState('')
  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try { const { data } = await getSessions(); setSessions(data.sessions); setTotal(data.total) }
    catch (e: any) { setError(e.response?.data?.detail || e.message || 'Không tải được danh sách phiên.') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void refresh() }, [refresh])
  const download = async (session: SessionRecord, format: 'json' | 'csv') => {
    setExporting(`${session.id}:${format}`); setError('')
    try {
      const { data } = await exportSession(session.id, format)
      const blob = new Blob([typeof data === 'string' ? data : JSON.stringify(data, null, 2)], { type: format === 'csv' ? 'text/csv' : 'application/json' })
      const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `neuropulse-${session.id}.${format}`; link.click(); URL.revokeObjectURL(url)
    } catch (e: any) { setError(e.response?.data?.detail || e.message || 'Xuất phiên thất bại.') }
    finally { setExporting('') }
  }

  return <div className="space-y-6">
    <div className="flex items-start justify-between"><div><h1 className="text-2xl font-bold tracking-tight">Saved Sessions & Recordings</h1><p className="text-sm text-gray-400 mt-1">Danh mục phiên và trạng thái lưu trữ local. Mẫu thô không được chỉnh sửa tại đây.</p></div><button onClick={() => void refresh()} className="px-3 py-2 bg-white/10 rounded text-sm">Làm mới</button></div>
    <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-amber-200 text-xs">Provenance luôn hiển thị với từng phiên. Dữ liệu simulated hoặc imported benchmark không phải dữ liệu đo lâm sàng.</div>
    {error && <div role="alert" className="text-sm text-red-300">{error}</div>}
    <div className="bg-np-panel border border-np-border rounded-lg overflow-x-auto">
      <table className="w-full text-left text-xs min-w-[900px]"><thead className="bg-np-dark text-gray-400"><tr>{['Session / participant',role === 'reviewer' ? 'Thông tin phiên' : 'Sensor & profile','Status','Provenance','Started','Samples / rate','Integrity / export'].map((x) => <th key={x} className="p-3 font-semibold">{x}</th>)}</tr></thead>
        <tbody>{sessions.map((s) => <tr key={s.id} className="border-t border-np-border text-gray-200"><td className="p-3"><code className="text-[10px]">{s.id}</code><div className="mt-1 text-gray-400">Participant: {s.participant_code || '—'}</div></td><td className="p-3">{role === 'reviewer' ? 'Thông tin giới hạn theo vai trò' : <>{s.sensor_type}<div className="text-gray-400">{s.profile_id}</div></>}</td><td className="p-3">{s.status}</td><td className="p-3"><span className="rounded bg-white/10 px-2 py-1">{s.provenance}</span></td><td className="p-3">{fmtDate(s.start_time)}</td><td className="p-3">{role === 'reviewer' ? '—' : <>{s.sample_count ?? '—'}<div className="text-gray-400">{s.sample_rate_hz ?? '—'} Hz</div></>}</td><td className="p-3">{role !== 'reviewer' && <><div>{s.sha256_hash ? `${s.sha256_hash.slice(0, 12)}…` : 'Checksum pending'}</div>{(role === 'admin' || role === 'operator' || role === 'researcher') && <div className="flex gap-2 mt-2"><button disabled={!!exporting} onClick={() => void download(s, 'json')} className="text-np-blue disabled:opacity-50">JSON</button><button disabled={!!exporting} onClick={() => void download(s, 'csv')} className="text-np-blue disabled:opacity-50">CSV</button></div>}</>}</td></tr>)}</tbody>
      </table>
      {!loading && sessions.length === 0 && <p className="p-5 text-sm text-gray-400">Chưa có phiên được lưu.</p>}
      {loading && <p className="p-5 text-sm text-gray-400">Đang tải phiên…</p>}
    </div>
    <p className="text-xs text-gray-500">Hiển thị {sessions.length} trên tổng số {total} phiên. Admin, Operator và Researcher có thể xuất dữ liệu.</p>
  </div>
}
