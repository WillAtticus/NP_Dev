import { useEffect, useState } from 'react'
import { getPorts, getDeviceStatus, connectDevice, disconnectDevice } from '../api/client'

export default function DevicePage({ role = 'operator' }: { role?: string }) {
  const [ports, setPorts] = useState<any[]>([])
  const [selectedPort, setSelectedPort] = useState('SIMULATOR')
  const [baudRate, setBaudRate] = useState(115200)
  const [sensorType, setSensorType] = useState('PIEZO_LDT0_028K')
  const [simulatorProfile, setSimulatorProfile] = useState<'healthy' | 'volatile'>('healthy')
  const [status, setStatus] = useState<any>(null)
  const [msg, setMsg] = useState('')

  const loadData = async () => {
    try {
      const [portsRes, statusRes] = await Promise.all([getPorts(), getDeviceStatus()])
      setPorts(portsRes.data || [])
      setStatus(statusRes.data)
    } catch (e: any) {
      setMsg(`Error: ${e.message}`)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleConnect = async () => {
    try {
      setMsg('Connecting...')
      const res = await connectDevice({ port: selectedPort, baud_rate: baudRate, sensor_type: sensorType, simulator_profile: simulatorProfile })
      setMsg(`Connected successfully (${res.data.mode})`)
      loadData()
    } catch (e: any) {
      setMsg(`Connection failed: ${e.response?.data?.detail || e.message}`)
    }
  }

  const handleDisconnect = async () => {
    try {
      await disconnectDevice()
      setMsg('Disconnected.')
      loadData()
    } catch (e: any) {
      setMsg(`Error: ${e.message}`)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Device & Port Connection</h1>
        <p className="text-sm text-gray-400 mt-1">Configure physical USB Serial interface or virtual signal simulator</p>
      </div>

      {msg && (
        <div className="p-3 bg-white/5 border border-white/10 rounded text-sm text-np-blue">
          {msg}
        </div>
      )}

      <div className="bg-np-panel border border-np-border rounded-lg p-5 space-y-4">
        <h2 className="text-base font-semibold">Serial Configuration</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Target Port</label>
            <select
              value={selectedPort}
              onChange={(e) => setSelectedPort(e.target.value)}
              className="w-full bg-np-dark border border-np-border rounded px-3 py-2 text-sm text-white"
            >
      {ports.map((p) => (
                <option key={p.port} value={p.port}>
                  {p.port} — {p.description}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Baud Rate (Optimal)</label>
            <select
              value={baudRate}
              onChange={(e) => setBaudRate(Number(e.target.value))}
              className="w-full bg-np-dark border border-np-border rounded px-3 py-2 text-sm text-white"
            >
              <option value={115200}>115,200 bps (Standard Recommended)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Sensor Modality</label>
            <select
              value={sensorType}
              onChange={(e) => setSensorType(e.target.value)}
              className="w-full bg-np-dark border border-np-border rounded px-3 py-2 text-sm text-white"
            >
              <option value="PIEZO_LDT0_028K">Sensor A: Piezo Film LDT0-028K</option>
              <option value="ADXL345">Sensor B: ADXL345 Triaxial Accelerometer</option>
            </select>
          </div>
          {selectedPort === 'SIMULATOR' && <div className="md:col-span-3 rounded-lg border border-blue-200 bg-blue-50 p-4 text-blue-950">
            <label className="block text-xs font-semibold mb-1">Kịch bản simulator</label>
            <select value={simulatorProfile} onChange={(e) => setSimulatorProfile(e.target.value as 'healthy' | 'volatile')} className="w-full rounded border border-blue-200 bg-white px-3 py-2 text-sm">
              <option value="healthy">Healthy · tín hiệu mô phỏng tham chiếu</option>
              <option value="volatile">Volatile · năng lượng 3–6 Hz cao hơn để thử cảnh báo demo</option>
            </select>
            <p className="mt-2 text-xs">Cả hai lựa chọn đều là dữ liệu tổng hợp; Volatile không đại diện hoặc xác nhận một bệnh nhân có nguy cơ. Chọn kịch bản rồi kết nối để dùng trong phiên đo và lưu đúng provenance.</p>
          </div>}
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={handleConnect}
            disabled={role === 'researcher'}
            className="px-4 py-2 bg-np-blue text-black font-semibold rounded hover:bg-np-blue/90 text-sm"
          >
            Connect Interface
          </button>
          <button
            onClick={handleDisconnect}
            disabled={role === 'researcher'}
            className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white font-semibold rounded text-sm"
          >
            Disconnect
          </button>
        </div>
      </div>

      {role === 'researcher' && <p className="text-xs text-gray-400">Chế độ chỉ xem: chỉ admin hoặc operator được thay đổi kết nối thiết bị.</p>}

      {status && (
        <div className="bg-np-panel border border-np-border rounded-lg p-5">
          <h2 className="text-base font-semibold mb-2">Live Connection Status</h2>
          <pre className="bg-np-dark p-3 rounded text-xs text-gray-300 overflow-x-auto">
            {JSON.stringify(status, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
