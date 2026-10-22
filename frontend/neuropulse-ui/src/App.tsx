import { useMemo, useState } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import OverviewPage from './pages/OverviewPage'
import DevicePage from './pages/DevicePage'
import LiveSensingPage from './pages/LiveSensingPage'
import SignalAnalysisPage from './pages/SignalAnalysisPage'
import AlgorithmLabPage from './pages/AlgorithmLabPage'
import SessionsPage from './pages/SessionsPage'
import PatientRegistryPage from './pages/PatientRegistryPage'
import PatientMeasurementPage from './pages/PatientMeasurementPage'
import AnalyticsPage from './pages/AnalyticsPage'
import type { LocalRole } from './api/client'

type PageItem = { to: string; label: string; roles: LocalRole[] }
const STAFF_ROLES: LocalRole[] = ['admin', 'operator', 'researcher', 'reviewer']
const NAV_ITEMS: PageItem[] = [
  { to: '/', label: 'Đo của tôi', roles: ['patient'] },
  { to: '/', label: 'Tổng quan', roles: STAFF_ROLES },
  { to: '/device', label: 'Thiết bị', roles: ['admin', 'operator', 'researcher'] },
  { to: '/live', label: 'Thu nhận tín hiệu', roles: ['admin', 'operator'] },
  { to: '/analysis', label: 'Phân tích tín hiệu', roles: ['admin', 'operator', 'researcher'] },
  { to: '/algorithms', label: 'Phòng thí nghiệm thuật toán', roles: ['admin', 'researcher'] },
  { to: '/sessions', label: 'Phiên nghiên cứu', roles: STAFF_ROLES },
  { to: '/analytics', label: 'Thống kê & nhóm', roles: STAFF_ROLES },
  { to: '/patients', label: 'Hồ sơ bệnh nhân', roles: STAFF_ROLES },
  { to: '/kiosk', label: 'Hướng dẫn người tham gia', roles: ['kiosk'] },
]
const ROLE_LABELS: Record<LocalRole, string> = {
  admin: 'Admin', operator: 'Operator', researcher: 'Researcher', reviewer: 'Clinical Reviewer', kiosk: 'Hướng dẫn', patient: 'Bệnh nhân',
}

function KioskPage() {
  return <section className="max-w-2xl space-y-4">
    <h1 className="text-2xl font-bold">Hướng dẫn phiên đo</h1>
    <p className="text-gray-300">Vui lòng làm theo hướng dẫn của nhân viên nghiên cứu và giữ thiết bị đúng vị trí đã được chỉ dẫn.</p>
    <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 text-amber-100 text-sm">Chế độ này chỉ hiển thị hướng dẫn quy trình. Không hiển thị dữ liệu phân tích hoặc diễn giải y khoa.</div>
  </section>
}

export default function App() {
  const [role, setRole] = useState<LocalRole>(() => {
    localStorage.setItem('neuropulse.local_mode', 'patient')
    return 'patient'
  })
  const user = { id: `local-mode-${role}`, username: `local-${role}`, role }
  const pages = useMemo(() => NAV_ITEMS.filter((page) => page.roles.includes(role)), [role])
  const changeMode = (next: LocalRole) => { localStorage.setItem('neuropulse.local_mode', next); setRole(next) }

  const fallback = pages[0]?.to || '/kiosk'
  return <div className="np-app-shell flex min-h-screen bg-np-dark text-white">
    <nav className="np-sidebar w-64 bg-np-panel border-r border-np-border flex flex-col shrink-0">
      <div className="np-brand p-4 border-b border-np-border">
        <div className="brand-row"><span className="brand-mark">∿</span><span className="text-np-blue font-bold text-lg tracking-wide">NeuroPulse</span></div>
        <div className="text-xs text-gray-500 mt-1">Small movements. Big insights.</div>
      </div>
      <div className="px-4 py-3 text-xs text-gray-300">
        <label htmlFor="operation-mode" className="block text-gray-500 mb-1">Chế độ vận hành trên máy này</label>
        <select id="operation-mode" value={role} onChange={(event) => changeMode(event.target.value as LocalRole)} className="w-full rounded border border-np-border bg-np-dark px-2 py-2 text-sm text-white">
          {(['patient', 'admin', 'operator', 'researcher', 'reviewer', 'kiosk'] as LocalRole[]).map((item) => <option key={item} value={item}>{ROLE_LABELS[item]}</option>)}
        </select>
        <p className="mt-2 text-[10px] leading-4 text-gray-500">Prototype local: chế độ chỉ giới hạn giao diện/thao tác, không xác thực danh tính.</p>
      </div>
      <ul className="flex-1 p-2 space-y-1 overflow-y-auto">
        {pages.map(({ to, label }) => <li key={to}>
          <NavLink to={to} end={to === '/'} className={({ isActive }) => `np-nav-link block px-3 py-2 rounded text-sm transition-colors ${isActive ? 'active' : ''}`}>
            <span className="nav-glyph" aria-hidden="true">{({ '/': '⌂', '/device': '⌁', '/live': '∿', '/analysis': '◌', '/algorithms': '⚙', '/sessions': '▤', '/analytics': '▥', '/patients': '♙', '/kiosk': 'ⓘ', '/patient': '♙' } as Record<string, string>)[to] || '·'}</span>{label}
          </NavLink>
        </li>)}
      </ul>
      <div className="np-sidebar-footer p-3 border-t border-np-border space-y-2">
        <div className="text-xs text-gray-400">Mode: {ROLE_LABELS[role]}</div>
        <p className="text-[10px] text-gray-500 text-center">Nghiên cứu thử nghiệm · Không dùng để chẩn đoán</p>
      </div>
    </nav>
    <main className="flex-1 min-w-0 overflow-y-auto p-5 md:p-7">
      <Routes>
        {pages.some((page) => page.to === '/') && <Route path="/" element={role === 'patient' ? <PatientMeasurementPage /> : <OverviewPage role={user.role} />} />}
        {pages.some((page) => page.to === '/device') && <Route path="/device" element={<DevicePage role={user.role} />} />}
        {pages.some((page) => page.to === '/live') && <Route path="/live" element={<LiveSensingPage />} />}
        {pages.some((page) => page.to === '/analysis') && <Route path="/analysis" element={<SignalAnalysisPage />} />}
        {pages.some((page) => page.to === '/algorithms') && <Route path="/algorithms" element={<AlgorithmLabPage />} />}
        {pages.some((page) => page.to === '/sessions') && <Route path="/sessions" element={<SessionsPage role={user.role} />} />}
        {pages.some((page) => page.to === '/analytics') && <Route path="/analytics" element={<AnalyticsPage />} />}
        {pages.some((page) => page.to === '/patients') && <Route path="/patients" element={<PatientRegistryPage role={user.role} />} />}
        {role === 'kiosk' && <Route path="/kiosk" element={<KioskPage />} />}
        <Route path="*" element={<Navigate to={fallback} replace />} />
      </Routes>
    </main>
  </div>
}
