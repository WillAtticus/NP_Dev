import axios from 'axios'

export type LocalRole = 'admin' | 'operator' | 'researcher' | 'reviewer' | 'kiosk' | 'patient'
export type LocalUser = { id: string; username: string; role: LocalRole }
export type AuthResult = { access_token: string; token_type: 'bearer'; expires_at: string; user: LocalUser }
export type SessionRecord = {
  id: string
  session_id?: string
  sensor_type: string
  profile_id: string
  status: string
  provenance: string
  participant_code?: string | null
  notes?: string | null
  created_at?: string | null
  start_time?: string | null
  end_time?: string | null
  duration_sec?: number | null
  sample_count?: number | null
  sample_rate_hz?: number | null
  tbr?: number | null
  npi_value?: number | null
  npi_category?: string | null
  dominant_freq_hz?: number | null
  quality_status?: string | null
  sha256_hash?: string | null
}

export type PatientRecord = {
  id: string
  patient_code: string
  full_name: string
  date_of_birth: string | null
  chromosome_marker: 'X' | 'Y'
  reported_sex?: 'female' | 'male' | null
  age_band: string
  medical_history: string | null
  family_history: string | null
  diet: 'vegetarian' | 'omnivore' | null
  retain_indefinitely: boolean
  retention_expires_at: string | null
  created_at: string
  updated_at: string
}
export type PatientLookup = {
  patient: PatientRecord
  sessions: SessionRecord[]
  screening_notice: string
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 8000,
})
const TOKEN_KEY = 'neuropulse.local_access_token'
const MODE_KEY = 'neuropulse.local_mode'
const PATIENT_CODE_KEY = 'neuropulse.patient_code'

api.interceptors.request.use((config) => {
  config.headers['X-NeuroPulse-Mode'] = localStorage.getItem(MODE_KEY) || 'operator'
  const patientCode = localStorage.getItem(PATIENT_CODE_KEY)
  if (patientCode) config.headers['X-NeuroPulse-Patient-Code'] = patientCode
  const token = sessionStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use((response) => response, (error: unknown) => {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    sessionStorage.removeItem(TOKEN_KEY)
    window.dispatchEvent(new Event('neuropulse-auth-expired'))
  }
  return Promise.reject(error)
})

export const getAccessToken = () => sessionStorage.getItem(TOKEN_KEY)
export const setAccessToken = (token: string) => sessionStorage.setItem(TOKEN_KEY, token)
export const clearAccessToken = () => sessionStorage.removeItem(TOKEN_KEY)

export const getHealth = () => api.get('/health')
export const setCurrentPatientCode = (code: string) => {
  const normalized = code.trim().toUpperCase()
  if (normalized) localStorage.setItem(PATIENT_CODE_KEY, normalized)
  else localStorage.removeItem(PATIENT_CODE_KEY)
}
export const getCurrentPatientCode = () => localStorage.getItem(PATIENT_CODE_KEY) || ''
export const getAuthStatus = () => api.get<{ bootstrap_required: boolean }>('/auth/status')
export const bootstrapAdmin = (payload: { username: string; password: string }) => api.post<AuthResult>('/auth/bootstrap', payload)
export const login = (payload: { username: string; password: string }) => api.post<AuthResult>('/auth/login', payload)
export const getCurrentUser = () => api.get<LocalUser>('/auth/me')
export const logout = () => api.post('/auth/logout')
export const getLocalUsers = () => api.get<Array<LocalUser & { is_active: boolean; created_at: string | null }>>('/auth/users')
export const createLocalUser = (payload: { username: string; password: string; role: LocalRole }) => api.post('/auth/users', payload)
export const setLocalUserActive = (id: string, is_active: boolean) => api.patch(`/auth/users/${id}/active`, { is_active })
export const resetLocalUserPassword = (id: string, password: string) => api.put(`/auth/users/${id}/password`, { password })

export const getPatients = () => api.get<PatientRecord[]>('/patients')
export const createPatient = (payload: {
  full_name: string
  date_of_birth?: string
  reported_sex?: 'female' | 'male'
  chromosome_marker?: 'X' | 'Y'
  medical_history?: string
  family_history?: string
  diet?: 'vegetarian' | 'omnivore'
}) => api.post<PatientRecord>('/patients', payload)
export const lookupPatient = (patientCode: string) =>
  api.get<PatientLookup>(`/patients/lookup/${encodeURIComponent(patientCode)}`)
export const exportPatientRecord = (patientCode: string) =>
  api.get(`/patients/lookup/${encodeURIComponent(patientCode)}/export`, { responseType: 'json' })
export const setPatientRetention = (patientCode: string, retain_indefinitely: boolean) =>
  api.patch<PatientRecord>(`/patients/${encodeURIComponent(patientCode)}/retention`, { retain_indefinitely })

export const getPorts = () => api.get('/devices/ports')
export const getDeviceStatus = () => api.get('/devices/status')
export const connectDevice = (payload: { port: string; baud_rate: number; sensor_type: string; simulator_profile?: 'healthy' | 'volatile' }) =>
  api.post('/devices/connect', payload)
export const disconnectDevice = () => api.post('/devices/disconnect')
export type CohortFilters = {
  provenance?: string
  study_id?: string
  sensor_type?: string
  quality_status?: string
  date_from?: string
  date_to?: string
}
export const getCohortAnalytics = (filters: CohortFilters = {}) => {
  const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value && value !== 'all'))
  return api.get('/analytics/cohorts', { params })
}

export const startAcquisition = (payload: {
  session_id: string
  sensor_type: string
  profile_id: string
  channel?: string | null
  participant_code?: string | null
  study_id?: string | null
}) => api.post('/acquisition/start', payload)
export const stopAcquisition = () => api.post('/acquisition/stop')
export const getAcquisitionStatus = () => api.get('/acquisition/status')
export const getLiveBuffer = (channel: string, max_samples = 1000) =>
  api.get('/acquisition/live-buffer', { params: { channel, max_samples } })
export const getLiveAnalysis = () => api.get('/acquisition/live-analysis')

export const getProfiles = () => api.get('/processing/profiles')
export const simulateAndAnalyse = (payload: object) => api.post('/simulate-and-analyse', payload)
export const analyseSession = (payload: object) => api.post('/processing/analyse', payload)
export const getAlgorithms = () => api.get('/algorithms')
export const computeNPI = (payload: object) => api.post('/algorithms/npi/compute', payload)
export type FormulaRecord = { id: string; version: number; name: string; expression: string; tbr_min: number; tbr_max: number; status: string; change_note: string | null; created_at: string | null }
export const getAlgorithmFormulas = () => api.get<FormulaRecord[]>('/algorithms/formulas')
export const createAlgorithmFormula = (payload: { name: string; expression: string; tbr_min: number; tbr_max: number; change_note: string }) => api.post<FormulaRecord>('/algorithms/formulas', payload)
export const retireAlgorithmFormula = (id: string) => api.delete(`/algorithms/formulas/${encodeURIComponent(id)}`)
export const evaluateAlgorithmFormula = (id: string, payload: { tbr: number; quality_status: string }) => api.post(`/algorithms/formulas/${encodeURIComponent(id)}/compute`, payload)
export const evaluateAlgorithmFormulaOnSession = (id: string, payload: { session_id: string; channel?: string }) => api.post(`/algorithms/formulas/${encodeURIComponent(id)}/evaluate-session`, payload)
export const getAlgorithmEvaluations = (limit = 100, offset = 0) => api.get<any[]>('/algorithms/evaluations', { params: { limit, offset } })
export const exportAlgorithmEvaluations = () => api.get('/algorithms/evaluations/export', { params: { format: 'csv' }, responseType: 'text' })

export const getSessions = (limit = 50, offset = 0) =>
  api.get<{ sessions: SessionRecord[]; total: number; stats: Record<string, unknown> }>('/sessions', { params: { limit, offset } })
export const getSession = (id: string) => api.get<SessionRecord>(`/sessions/${encodeURIComponent(id)}`)
export const deleteSession = (id: string) => api.delete(`/sessions/${encodeURIComponent(id)}`)
export const exportSession = (id: string, format: 'json' | 'csv' = 'json') =>
  api.get(`/sessions/${encodeURIComponent(id)}/export`, { params: { format }, responseType: format === 'json' ? 'json' : 'text' })
export const getStudies = () => api.get<Array<{ id: string; name: string; sensor_type: string; protocol_version: string }>>('/studies')
