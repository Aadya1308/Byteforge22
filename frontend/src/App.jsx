import { useState, useEffect } from 'react'
import './App.css'

const API_BASE = 'http://127.0.0.1:8000'

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [user, setUser] = useState(null)
  const [activeTab, setActiveTab] = useState('auth')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (token) fetchUser()
  }, [token])

  const fetchUser = async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setUser(data)
      } else {
        logout()
      }
    } catch (e) {
      setError('Failed to fetch user')
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    setToken('')
    setUser(null)
    setActiveTab('auth')
  }

  const showMessage = (msg, isError = false) => {
    if (isError) setError(msg)
    else setMessage(msg)
    setTimeout(() => {
      setMessage('')
      setError('')
    }, 5000)
  }

  return (
    <div className="app">
      <header className="header">
        <h1>🏥 ClinicalDoc AI</h1>
        {user && (
          <div className="user-info">
            <span>Dr. {user.full_name}</span>
            <button onClick={logout} className="btn-secondary">Logout</button>
          </div>
        )}
      </header>

      {message && <div className="alert success">{message}</div>}
      {error && <div className="alert error">{error}</div>}

      {!token ? (
        <AuthSection setToken={setToken} showMessage={showMessage} API_BASE={API_BASE} />
      ) : (
        <>
          <nav className="nav">
            <button className={activeTab === 'patients' ? 'active' : ''} onClick={() => setActiveTab('patients')}>Patients</button>
            <button className={activeTab === 'transcribe' ? 'active' : ''} onClick={() => setActiveTab('transcribe')}>Transcribe</button>
            <button className={activeTab === 'sessions' ? 'active' : ''} onClick={() => setActiveTab('sessions')}>Sessions</button>
            <button className={activeTab === 'prescriptions' ? 'active' : ''} onClick={() => setActiveTab('prescriptions')}>Prescriptions</button>
            <button className={activeTab === 'system' ? 'active' : ''} onClick={() => setActiveTab('system')}>System</button>
          </nav>

          <main className="main">
            {activeTab === 'patients' && <PatientsSection token={token} API_BASE={API_BASE} showMessage={showMessage} />}
            {activeTab === 'transcribe' && <TranscribeSection token={token} API_BASE={API_BASE} showMessage={showMessage} />}
            {activeTab === 'sessions' && <SessionsSection token={token} API_BASE={API_BASE} showMessage={showMessage} />}
            {activeTab === 'prescriptions' && <PrescriptionsSection token={token} API_BASE={API_BASE} showMessage={showMessage} />}
            {activeTab === 'system' && <SystemSection token={token} API_BASE={API_BASE} showMessage={showMessage} />}
          </main>
        </>
      )}
    </div>
  )
}

function AuthSection({ setToken, showMessage, API_BASE }) {
  const [isLogin, setIsLogin] = useState(true)
  const [form, setForm] = useState({ email: '', password: '', full_name: '', phone: '', role: 'doctor', specialization: '', hospital_name: '', license_number: '' })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (isLogin) {
        const formData = new FormData()
        formData.append('username', form.email)
        formData.append('password', form.password)
        const res = await fetch(`${API_BASE}/auth/login`, { method: 'POST', body: formData })
        const data = await res.json()
        if (res.ok) {
          localStorage.setItem('token', data.access_token)
          setToken(data.access_token)
          showMessage('Login successful!')
        } else {
          showMessage(data.detail || 'Login failed', true)
        }
      } else {
        const res = await fetch(`${API_BASE}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form)
        })
        const data = await res.json()
        if (res.ok) {
          showMessage('Registration successful! Please login.')
          setIsLogin(true)
        } else {
          showMessage(data.detail || 'Registration failed', true)
        }
      }
    } catch (e) {
      showMessage('Network error', true)
    }
    setLoading(false)
  }

  return (
    <div className="auth-container">
      <h2>{isLogin ? 'Login' : 'Register'}</h2>
      <form onSubmit={handleSubmit} className="form">
        <input type="email" placeholder="Email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} required />
        <input type="password" placeholder="Password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} required />
        {!isLogin && (
          <>
            <input type="text" placeholder="Full Name" value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} required />
            <input type="tel" placeholder="Phone" value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} required />
            <select value={form.role} onChange={e => setForm({...form, role: e.target.value})}>
              <option value="doctor">Doctor</option>
              <option value="nurse">Nurse</option>
              <option value="admin">Admin</option>
              <option value="receptionist">Receptionist</option>
            </select>
            <input type="text" placeholder="Specialization" value={form.specialization} onChange={e => setForm({...form, specialization: e.target.value})} />
            <input type="text" placeholder="Hospital Name" value={form.hospital_name} onChange={e => setForm({...form, hospital_name: e.target.value})} />
            <input type="text" placeholder="License Number" value={form.license_number} onChange={e => setForm({...form, license_number: e.target.value})} />
          </>
        )}
        <button type="submit" disabled={loading} className="btn-primary">
          {loading ? 'Processing...' : (isLogin ? 'Login' : 'Register')}
        </button>
      </form>
      <p className="toggle">
        {isLogin ? "Don't have an account? " : "Already have an account? "}
        <button className="link" onClick={() => setIsLogin(!isLogin)}>
          {isLogin ? 'Register' : 'Login'}
        </button>
      </p>
    </div>
  )
}

function PatientsSection({ token, API_BASE, showMessage }) {
  const [patients, setPatients] = useState([])
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ full_name: '', phone: '', email: '', date_of_birth: '', gender: '', blood_group: '', allergies: '', medical_history: '', emergency_contact_name: '', emergency_contact_phone: '' })
  const [selectedPatient, setSelectedPatient] = useState(null)
  const [history, setHistory] = useState(null)

  const fetchPatients = async () => {
    try {
      const res = await fetch(`${API_BASE}/patients?search=${search}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setPatients(data.patients || [])
      }
    } catch (e) {
      showMessage('Failed to fetch patients', true)
    }
  }

  useEffect(() => {
    fetchPatients()
  }, [search])

  const createPatient = async (e) => {
    e.preventDefault()
    try {
      const res = await fetch(`${API_BASE}/patients`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(form)
      })
      if (res.ok) {
        showMessage('Patient created successfully!')
        setShowForm(false)
        setForm({ full_name: '', phone: '', email: '', date_of_birth: '', gender: '', blood_group: '', allergies: '', medical_history: '', emergency_contact_name: '', emergency_contact_phone: '' })
        fetchPatients()
      } else {
        const data = await res.json()
        showMessage(data.detail || 'Failed to create patient', true)
      }
    } catch (e) {
      showMessage('Network error', true)
    }
  }

  const viewHistory = async (patientId) => {
    try {
      const res = await fetch(`${API_BASE}/patients/${patientId}/history`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setHistory(data)
        setSelectedPatient(patientId)
      }
    } catch (e) {
      showMessage('Failed to fetch history', true)
    }
  }

  return (
    <div className="section">
      <h2>Patients</h2>
      <div className="toolbar">
        <input type="text" placeholder="Search patients..." value={search} onChange={e => setSearch(e.target.value)} className="search-input" />
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">{showForm ? 'Cancel' : 'Add Patient'}</button>
      </div>

      {showForm && (
        <form onSubmit={createPatient} className="form patient-form">
          <input type="text" placeholder="Full Name *" value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} required />
          <input type="tel" placeholder="Phone *" value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} required />
          <input type="email" placeholder="Email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} />
          <input type="date" placeholder="Date of Birth" value={form.date_of_birth} onChange={e => setForm({...form, date_of_birth: e.target.value})} />
          <select value={form.gender} onChange={e => setForm({...form, gender: e.target.value})}>
            <option value="">Gender</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
          <input type="text" placeholder="Blood Group" value={form.blood_group} onChange={e => setForm({...form, blood_group: e.target.value})} />
          <textarea placeholder="Allergies" value={form.allergies} onChange={e => setForm({...form, allergies: e.target.value})} />
          <textarea placeholder="Medical History" value={form.medical_history} onChange={e => setForm({...form, medical_history: e.target.value})} />
          <input type="text" placeholder="Emergency Contact Name" value={form.emergency_contact_name} onChange={e => setForm({...form, emergency_contact_name: e.target.value})} />
          <input type="tel" placeholder="Emergency Contact Phone" value={form.emergency_contact_phone} onChange={e => setForm({...form, emergency_contact_phone: e.target.value})} />
          <button type="submit" className="btn-primary">Create Patient</button>
        </form>
      )}

      {selectedPatient && history && (
        <div className="modal">
          <div className="modal-content">
            <h3>Patient History - {selectedPatient}</h3>
            <p>Total Visits: {history.total_visits}</p>
            <p>Total Prescriptions: {history.total_prescriptions}</p>
            <h4>Sessions</h4>
            {history.sessions.map(s => (
              <div key={s.session_id} className="history-item">
                <p><strong>{s.session_id}</strong> - {s.created_at}</p>
                <p>Status: {s.status}</p>
              </div>
            ))}
            <button onClick={() => setSelectedPatient(null)} className="btn-secondary">Close</button>
          </div>
        </div>
      )}

      <div className="list">
        {patients.map(p => (
          <div key={p.patient_id} className="card">
            <h4>{p.full_name} <span className="badge">{p.patient_id}</span></h4>
            <p>📞 {p.phone}</p>
            <p>🎂 {p.date_of_birth || 'N/A'} | {p.gender || 'N/A'} | {p.blood_group || 'N/A'}</p>
            <p>🚨 Emergency: {p.emergency_contact_name || 'N/A'}</p>
            <div className="card-actions">
              <button onClick={() => viewHistory(p.patient_id)} className="btn-small">View History</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function TranscribeSection({ token, API_BASE, showMessage }) {
  const [file, setFile] = useState(null)
  const [patientId, setPatientId] = useState('')
  const [consent, setConsent] = useState(true)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) {
      showMessage('Please select an audio file', true)
      return
    }
    if (!consent) {
      showMessage('Patient consent required', true)
      return
    }

    setLoading(true)
    const formData = new FormData()
    formData.append('audio', file)
    formData.append('patient_id', patientId || 'unknown')
    formData.append('consent', consent)
    formData.append('session_type', 'consultation')

    try {
      const res = await fetch(`${API_BASE}/sessions/transcribe`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      })
      const data = await res.json()
      if (res.ok) {
        setResult(data)
        showMessage('Transcription completed!')
      } else {
        showMessage(data.detail || 'Transcription failed', true)
      }
    } catch (e) {
      showMessage('Network error', true)
    }
    setLoading(false)
  }

  return (
    <div className="section">
      <h2>🎙️ Transcribe & Generate SOAP</h2>
      <form onSubmit={handleSubmit} className="form">
        <input type="file" accept="audio/*" onChange={e => setFile(e.target.files[0])} />
        {file && <p className="file-info">Selected: {file.name}</p>}
        <input type="text" placeholder="Patient ID (optional)" value={patientId} onChange={e => setPatientId(e.target.value)} />
        <label className="checkbox">
          <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
          Patient consent obtained (HIPAA compliant)
        </label>
        <button type="submit" disabled={loading} className="btn-primary">
          {loading ? 'Processing...' : 'Transcribe & Generate SOAP'}
        </button>
      </form>

      {result && (
        <div className="result">
          <h3>Result</h3>
          <p><strong>Session ID:</strong> {result.session_id}</p>
          <p><strong>Language:</strong> {result.detected_language} ({(result.language_confidence * 100).toFixed(1)}%)</p>
          {result.prescription_id && <p><strong>Prescription ID:</strong> {result.prescription_id}</p>}
          
          <h4>Transcript</h4>
          <div className="transcript">
            <p><strong>Original:</strong> {result.raw_transcript}</p>
            <p><strong>English:</strong> {result.english_transcript}</p>
          </div>

          <h4>SOAP Note</h4>
          {result.soap_note && (
            <div className="soap">
              <div className="soap-section"><h5>Subjective</h5><pre>{JSON.stringify(result.soap_note.subjective, null, 2)}</pre></div>
              <div className="soap-section"><h5>Objective</h5><pre>{JSON.stringify(result.soap_note.objective, null, 2)}</pre></div>
              <div className="soap-section"><h5>Assessment</h5><pre>{JSON.stringify(result.soap_note.assessment, null, 2)}</pre></div>
              <div className="soap-section"><h5>Plan</h5><pre>{JSON.stringify(result.soap_note.plan, null, 2)}</pre></div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SessionsSection({ token, API_BASE, showMessage }) {
  const [sessions, setSessions] = useState([])
  const [searchPatient, setSearchPatient] = useState('')

  const fetchSessions = async () => {
    try {
      const url = searchPatient ? `${API_BASE}/sessions?patient_id=${searchPatient}` : `${API_BASE}/sessions`
      const res = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
      if (res.ok) {
        const data = await res.json()
        setSessions(data.sessions || [])
      }
    } catch (e) {
      showMessage('Failed to fetch sessions', true)
    }
  }

  useEffect(() => {
    fetchSessions()
  }, [searchPatient])

  const markReviewed = async (sessionId) => {
    try {
      const res = await fetch(`${API_BASE}/sessions/${sessionId}/review`, {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        showMessage('Session marked as reviewed')
        fetchSessions()
      }
    } catch (e) {
      showMessage('Failed to mark reviewed', true)
    }
  }

  return (
    <div className="section">
      <h2>📋 Clinical Sessions</h2>
      <input type="text" placeholder="Filter by Patient ID" value={searchPatient} onChange={e => setSearchPatient(e.target.value)} className="search-input" />
      <div className="list">
        {sessions.map(s => (
          <div key={s.session_id} className={`card ${s.status === 'reviewed' ? 'reviewed' : ''}`}>
            <h4>{s.session_id} <span className={`badge ${s.status}`}>{s.status}</span></h4>
            <p>Patient: {s.patient_id}</p>
            <p>Language: {s.detected_language}</p>
            <p>Created: {s.created_at}</p>
            {s.soap_note?.assessment?.primary_diagnosis && (
              <p>Diagnosis: {s.soap_note.assessment.primary_diagnosis}</p>
            )}
            {s.status !== 'reviewed' && (
              <button onClick={() => markReviewed(s.session_id)} className="btn-small">Mark Reviewed</button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function PrescriptionsSection({ token, API_BASE, showMessage }) {
  const [prescriptions, setPrescriptions] = useState([])
  const [patientId, setPatientId] = useState('')

  const fetchPrescriptions = async () => {
    try {
      const url = patientId ? `${API_BASE}/prescriptions/patient/${patientId}` : `${API_BASE}/prescriptions/patient/unknown`
      const res = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
      if (res.ok) {
        const data = await res.json()
        setPrescriptions(data.prescriptions || [])
      }
    } catch (e) {
      showMessage('Failed to fetch prescriptions', true)
    }
  }

  const downloadPDF = async (prescriptionId) => {
    try {
      const res = await fetch(`${API_BASE}/prescriptions/${prescriptionId}/pdf`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        window.open(data.pdf_url, '_blank')
      }
    } catch (e) {
      showMessage('Failed to get PDF', true)
    }
  }

  return (
    <div className="section">
      <h2>💊 Prescriptions</h2>
      <div className="toolbar">
        <input type="text" placeholder="Patient ID" value={patientId} onChange={e => setPatientId(e.target.value)} />
        <button onClick={fetchPrescriptions} className="btn-primary">Search</button>
      </div>
      <div className="list">
        {prescriptions.map(rx => (
          <div key={rx.prescription_id} className="card">
            <h4>{rx.prescription_id}</h4>
            <p>Patient: {rx.patient_name}</p>
            <p>Diagnosis: {rx.diagnosis}</p>
            <p>Medications: {rx.medications?.length || 0}</p>
            <p>Date: {rx.date}</p>
            <button onClick={() => downloadPDF(rx.prescription_id)} className="btn-small">Download PDF</button>
          </div>
        ))}
      </div>
    </div>
  )
}

function SystemSection({ token, API_BASE, showMessage }) {
  const [health, setHealth] = useState(null)
  const [config, setConfig] = useState(null)
  const [logs, setLogs] = useState([])

  useEffect(() => {
    fetchHealth()
    fetchConfig()
    fetchLogs()
  }, [])

  const fetchHealth = async () => {
    const res = await fetch(`${API_BASE}/health`)
    if (res.ok) setHealth(await res.json())
  }

  const fetchConfig = async () => {
    const res = await fetch(`${API_BASE}/config`)
    if (res.ok) setConfig(await res.json())
  }

  const fetchLogs = async () => {
    const res = await fetch(`${API_BASE}/audit`, { headers: { 'Authorization': `Bearer ${token}` } })
    if (res.ok) {
      const data = await res.json()
      setLogs(data.logs || [])
    }
  }

  return (
    <div className="section">
      <h2>⚙️ System</h2>
      
      {health && (
        <div className="info-box">
          <h4>Health Status</h4>
          <p>Status: {health.status}</p>
          <p>Service: {health.service}</p>
          <p>Team: {health.team}</p>
        </div>
      )}

      {config && (
        <div className="info-box">
          <h4>Configuration</h4>
          <p>Languages: {config.supported_languages?.join(', ')}</p>
          <p>Audio formats: {config.supported_audio?.join(', ')}</p>
          <p>ASR Model: {config.asr_model}</p>
          <p>LLM Model: {config.llm_model}</p>
        </div>
      )}

      <h3>Audit Logs</h3>
      <div className="list compact">
        {logs.map(log => (
          <div key={log.audit_id} className="log-item">
            <span className="timestamp">{log.timestamp}</span>
            <span className={`action ${log.action}`}>{log.action}</span>
            <span className="performer">by {log.performed_by}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default App
