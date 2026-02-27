import { useState, type FormEvent } from 'react'
import { useAuth } from '../context/AuthContext'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/')
    } catch (err: any) {
      setError(err.message || 'Credenciais inválidas')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-nexus-bg px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <img
            src="/assets/logo2.png"
            alt="Nexus"
            className="h-14 mx-auto mb-4 object-contain"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
          <h1 className="text-2xl font-bold text-white">Leads Dashboard</h1>
          <p className="text-sm text-nexus-muted mt-1">Acesso restrito</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-nexus-card border border-white/[0.06] rounded-xl p-6 space-y-4 shadow-lg shadow-black/20"
        >
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Usuário</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:border-nexus-accent focus:ring-1 focus:ring-nexus-accent/30 transition"
              placeholder="admin"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:border-nexus-accent focus:ring-1 focus:ring-nexus-accent/30 transition"
              placeholder="••••••"
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-nexus-accent text-white py-2.5 rounded-lg font-semibold hover:bg-blue-500 disabled:opacity-50 transition shadow-lg shadow-blue-500/20 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}
