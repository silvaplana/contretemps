import { useEffect, useState } from 'react'
import './App.css'

// URL de base de l'API backend (voir .env.example / VITE_API_URL).
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [apiStatus, setApiStatus] = useState('...')

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => res.json())
      .then((data) => setApiStatus(data.status))
      .catch(() => setApiStatus('injoignable'))
  }, [])

  return (
    <div className="app">
      <h1>Contretemps</h1>
      <p>Gestion d'école de danse</p>
      <span className="status">API : {apiStatus}</span>
    </div>
  )
}

export default App
