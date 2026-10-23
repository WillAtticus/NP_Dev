import { useCallback, useEffect, useState } from 'react'
import { createPatient, getPatients, setPatientRetention } from '../api/client'
import type { LocalRole, PatientRecord } from '../api/client'

const errorText = (error: any) => error?.response?.data?.detail || error?.message || 'Không thể hoàn tất thao tác.'
const ageLabels: Record<string, string> = { I: 'Chưa rõ', C: 'Dưới 10', J: '10–17', Y: '18–29', M: '30–49', E: '50+' }

export default function PatientRegistryPage({ role }: { role: LocalRole }) {
  const [patients, setPatients] = useState<PatientRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [createdCode, setCreatedCode] = useState('')
  const [working, setWorking] = useState(false)
  const refresh = useCallback(async () => {
    setLoading(true)
    try { const { data } = await getPatients(); setPatients(data); setError('') }
    catch (reason) { setError(errorText(reason)) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setWorking(true); setError(''); setCreatedCode('')
    const form = new FormData(event.currentTarget)
    try {
      const { data } = await createPatient({
        full_name: String(form.get('full_name') || '').trim(),
        date_of_birth: String(form.get('date_of_birth') || '') || undefined,
        reported_sex: String(form.get('reported_sex')) as 'female' | 'male',
        medical_history: String(form.get('medical_history') || '').trim() || undefined,
        family_history: String(form.get('family_history') || '').trim() || undefined,
        diet: (String(form.get('diet') || '') || undefined) as 'vegetarian' | 'omnivore' | undefined,
      })
      setCreatedCode(data.patient_code); event.currentTarget.reset(); await refresh()
    } catch (reason) { setError(errorText(reason)) }
    finally { setWorking(false) }
  }

  const toggleRetention = async (patient: PatientRecord, checked: boolean) => {
    try { await setPatientRetention(patient.patient_code, checked); await refresh() }
    catch (reason) { setError(errorText(reason)) }
  }

  return <section className="space-y-6 max-w-6xl">
    <header><h1 className="text-2xl font-bold">Hồ sơ bệnh nhân</h1><p className="text-sm text-gray-400 mt-1">Hồ sơ được lưu trên máy này và tra cứu bằng mã bệnh nhân.</p></header>
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">Prototype nghiên cứu. Mã bệnh nhân là mã tra cứu, không phải xác thực danh tính. NPI/cảnh báo là giả thuyết demo, chưa được xác nhận lâm sàng.</div>
    {error && <div role="alert" className="text-sm text-red-300">{error}</div>}
    {createdCode && <div role="status" className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4"><p className="text-sm text-emerald-200">Đã tạo hồ sơ. Ghi lại mã để tra cứu:</p><code className="mt-1 block text-xl font-bold tracking-widest">{createdCode}</code></div>}
    <form onSubmit={submit} className="grid gap-4 rounded-lg border border-np-border bg-np-panel p-5 md:grid-cols-2">
      <h2 className="text-lg font-semibold md:col-span-2">Tạo hồ sơ mới</h2>
      <label className="text-sm">Họ và tên<input name="full_name" required maxLength={160} className="mt-1 block w-full rounded border border-np-border bg-np-dark p-2" /></label>
      <label className="text-sm">Ngày sinh<input name="date_of_birth" type="date" className="mt-1 block w-full rounded border border-np-border bg-np-dark p-2" /></label>
      <label className="text-sm">Giới tính<select name="reported_sex" required className="mt-1 block w-full rounded border border-np-border bg-np-dark p-2"><option value="female">Nữ</option><option value="male">Nam</option></select><small className="block text-gray-500">Quy ước mã nội bộ: nữ → X, nam → Y; không phải xét nghiệm nhiễm sắc thể.</small></label>
      <label className="text-sm">Chế độ ăn<select name="diet" className="mt-1 block w-full rounded border border-np-border bg-np-dark p-2"><option value="">Chưa ghi nhận</option><option value="vegetarian">Chay</option><option value="omnivore">Mặn</option></select></label>
      <label className="text-sm md:col-span-2">Tiền sử cá nhân<textarea name="medical_history" maxLength={4000} rows={2} className="mt-1 block w-full rounded border border-np-border bg-np-dark p-2" /></label>
      <label className="text-sm md:col-span-2">Tiền sử gia đình<textarea name="family_history" maxLength={4000} rows={2} className="mt-1 block w-full rounded border border-np-border bg-np-dark p-2" /></label>
      <button disabled={working} className="rounded bg-np-blue px-4 py-2 font-semibold text-black disabled:opacity-50 md:col-span-2">{working ? 'Đang tạo…' : 'Tạo hồ sơ và cấp mã'}</button>
    </form>
    <div className="overflow-x-auto rounded-lg border border-np-border bg-np-panel">
      <table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-np-dark text-gray-400"><tr>{['Mã / bệnh nhân','Nhóm tuổi','Giới tính','Ngày sinh','Lưu trữ'].map((item) => <th key={item} className="p-3">{item}</th>)}</tr></thead>
        <tbody>{patients.map((patient) => <tr key={patient.id} className="border-t border-np-border"><td className="p-3"><code>{patient.patient_code}</code><div className="text-gray-400">{patient.full_name}</div></td><td className="p-3">{ageLabels[patient.age_band] || patient.age_band}</td><td className="p-3">{patient.reported_sex === 'female' ? 'Nữ' : patient.reported_sex === 'male' ? 'Nam' : 'Chưa ghi nhận'}</td><td className="p-3">{patient.date_of_birth || '—'}</td><td className="p-3">{role === 'admin' ? <label className="flex items-center gap-2"><input type="checkbox" checked={patient.retain_indefinitely} onChange={(event) => void toggleRetention(patient, event.target.checked)} />Vô thời hạn</label> : patient.retain_indefinitely ? 'Vô thời hạn' : `Đến ${patient.retention_expires_at ? new Date(patient.retention_expires_at).toLocaleDateString() : 'hết hạn'}`}</td></tr>)}</tbody>
      </table>
      {loading && <p className="p-4 text-sm text-gray-400">Đang tải hồ sơ…</p>}
      {!loading && patients.length === 0 && <p className="p-4 text-sm text-gray-400">Chưa có hồ sơ.</p>}
    </div>
    <p className="text-xs text-gray-500">{patients.length} hồ sơ trên máy này. Thời hạn 3 tuần được cấu hình ở cấp hồ sơ; tác vụ tự xóa dữ liệu hết hạn chưa được bật.</p>
  </section>
}
