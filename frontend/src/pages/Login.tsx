import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { ApiError, api } from '../services/api'

type Mode = 'login' | 'register'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [awaitingVerification, setAwaitingVerification] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const nextRaw = new URLSearchParams(location.search).get('next') || '/app/dashboard'
  const next = nextRaw.startsWith('/') ? nextRaw : '/app/dashboard'

  const submitLogin = async () => {
    await login(email, password)
    navigate(next, { replace: true })
  }

  const submitRegister = async () => {
    const res = await api<{ requires_verification: boolean }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        full_name: fullName || undefined,
      }),
      skipAuthRedirect: true,
    })
    if (res.requires_verification) {
      setAwaitingVerification(true)
      return
    }
    await submitLogin()
  }

  const submitVerification = async () => {
    await api('/api/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ email, code: verificationCode }),
      skipAuthRedirect: true,
    })
    await submitLogin()
  }

  const resendCode = async () => {
    await api('/api/auth/resend-verification', {
      method: 'POST',
      body: JSON.stringify({ email }),
      skipAuthRedirect: true,
    })
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'login') {
        await submitLogin()
      } else if (awaitingVerification) {
        await submitVerification()
      } else {
        await submitRegister()
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 403 && err.message.toLowerCase().includes('email not verified')) {
          setAwaitingVerification(true)
          setError('Email ainda não verificado. Digite o código enviado.')
        } else {
          setError(err.message || 'Falha de autenticação')
        }
      } else {
        const msg = err instanceof Error ? err.message : ''
        setError(
          msg && (msg.includes('failed') || msg.includes('Network') || msg.includes('Fetch'))
            ? 'Não foi possível conectar ao servidor. Verifique se o backend está rodando na porta 8000.'
            : 'Não foi possível processar sua solicitação agora.'
        )
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-black px-4">
      <div className="w-full max-w-[400px]">
        <div className="mb-10">
          <h1 className="text-xl font-bold tracking-tight text-white">Nexus Leads Manager</h1>
        </div>

        <h1 className="text-2xl font-semibold tracking-tight text-white">
          {mode === 'login'
            ? 'Entrar'
            : awaitingVerification
              ? 'Verificar email'
              : 'Criar conta'}
        </h1>
        <p className="mt-2 text-[14px] text-[#666666]">
          {mode === 'login'
            ? 'Acesse o Nexus Leads Manager para gerar oportunidades.'
            : awaitingVerification
              ? 'Digite o código enviado para seu email.'
              : 'Crie sua conta para começar.'}
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          {mode === 'register' && !awaitingVerification ? (
            <InputField
              label="Nome"
              type="text"
              value={fullName}
              onChange={setFullName}
              placeholder="Seu nome"
            />
          ) : null}

          <InputField
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="voce@empresa.com"
            required
          />

          {!awaitingVerification ? (
            <InputField
              label="Senha"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="Sua senha"
              required
              minLength={8}
            />
          ) : null}

          {awaitingVerification ? (
            <InputField
              label="Código de verificação"
              type="text"
              value={verificationCode}
              onChange={setVerificationCode}
              placeholder="000000"
              required
            />
          ) : null}

          {error ? (
            <p className="rounded-lg border border-nexus-red/20 bg-nexus-red/5 px-3 py-2.5 text-[13px] text-nexus-red">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-white py-3 text-[14px] font-semibold text-black transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {loading
              ? 'Processando...'
              : mode === 'login'
                ? 'Entrar'
                : awaitingVerification
                  ? 'Verificar e entrar'
                  : 'Criar conta'}
          </button>
        </form>

        {awaitingVerification ? (
          <button
            type="button"
            onClick={() => { void resendCode() }}
            className="mt-4 text-[13px] text-[#888888] transition hover:text-white"
          >
            Reenviar código
          </button>
        ) : null}

        <button
          type="button"
          onClick={() => {
            setMode((prev) => (prev === 'login' ? 'register' : 'login'))
            setAwaitingVerification(false)
            setVerificationCode('')
            setError('')
          }}
          className="mt-6 block text-[13px] text-[#555555] transition hover:text-white"
        >
          {mode === 'login' ? 'Não tem conta? Criar agora' : 'Já possui conta? Entrar'}
        </button>
      </div>
    </div>
  )
}

function InputField({
  label,
  type,
  value,
  onChange,
  placeholder,
  required,
  minLength,
}: {
  label: string
  type: string
  value: string
  onChange: (v: string) => void
  placeholder: string
  required?: boolean
  minLength?: number
}) {
  return (
    <label className="block">
      <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#555555]">
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        minLength={minLength}
        className="mt-2 block w-full rounded-lg border border-white/[0.1] bg-white/[0.03] px-4 py-3 text-[14px] text-white placeholder-[#444444] transition focus:border-white/[0.25]"
        placeholder={placeholder}
      />
    </label>
  )
}
