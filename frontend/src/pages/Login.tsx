import { useState, type FormEvent } from 'react'
import { Loader2 } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../context/AuthContext'
import { ApiError, apiPublic } from '../services/api'

type Mode = 'login' | 'register' | 'forgot' | 'reset'

type VerifyPurpose = 'signup' | 'password_reset'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [awaitingVerification, setAwaitingVerification] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const nextRaw = new URLSearchParams(location.search).get('next') || '/app/dashboard'
  const next = nextRaw.startsWith('/') ? nextRaw : '/app/dashboard'

  const submitLogin = async () => {
    await login(email, password)
    navigate(next, { replace: true })
  }

  const sendVerification = async (purpose: VerifyPurpose) => {
    const res = await apiPublic<{ dev_code?: string; message?: string }>('/api/auth/send-verification', {
      method: 'POST',
      body: JSON.stringify({ email, purpose }),
    })

    if (res.dev_code) {
      setVerificationCode(res.dev_code)
      setSuccess(`[DEV] Codigo: ${res.dev_code}`)
    } else {
      setSuccess(res.message || 'Codigo enviado com sucesso.')
    }
  }

  const submitRegister = async () => {
    const res = await apiPublic<{ requires_verification?: boolean; dev_code?: string }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        full_name: fullName || undefined,
      }),
    })

    if (res.requires_verification) {
      setAwaitingVerification(true)
      if (res.dev_code) {
        setVerificationCode(res.dev_code)
        setSuccess(`[DEV] Codigo: ${res.dev_code}`)
      }
      return
    }

    await submitLogin()
  }

  const submitVerification = async () => {
    await apiPublic('/api/auth/verify-code', {
      method: 'POST',
      body: JSON.stringify({
        email,
        code: verificationCode,
        purpose: 'signup',
      }),
    })
    await submitLogin()
  }

  const resendCode = async () => {
    setError('')
    setSuccess('')
    try {
      await sendVerification('signup')
    } catch {
      setError('Falha ao reenviar codigo.')
    }
  }

  const submitForgotPassword = async () => {
    await sendVerification('password_reset')
    setMode('reset')
  }

  const submitResetPassword = async () => {
    await apiPublic('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({
        email,
        code: verificationCode,
        new_password: newPassword,
      }),
    })

    setSuccess('Senha redefinida com sucesso. Fazendo login...')
    await login(email, newPassword)
    navigate(next, { replace: true })
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      if (mode === 'login') {
        await submitLogin()
      } else if (mode === 'forgot') {
        await submitForgotPassword()
      } else if (mode === 'reset') {
        await submitResetPassword()
      } else if (awaitingVerification) {
        await submitVerification()
      } else {
        await submitRegister()
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        const message = err.message || 'Falha de autenticacao'
        if (err.status === 403 && message.toLowerCase().includes('email not verified')) {
          setAwaitingVerification(true)
          setError('Email ainda nao verificado. Digite o codigo recebido.')
          try {
            await sendVerification('signup')
          } catch {
            // ignore resend errors here
          }
        } else {
          setError(message)
        }
      } else {
        const msg = err instanceof Error ? err.message : ''
        setError(
          msg && (msg.includes('failed') || msg.includes('Network') || msg.includes('Fetch'))
            ? 'Nao foi possivel conectar ao servidor. Verifique se o backend esta rodando.'
            : 'Nao foi possivel processar sua solicitacao agora.'
        )
      }
    } finally {
      setLoading(false)
    }
  }

  const title = {
    login: 'Entrar',
    register: awaitingVerification ? 'Verificar email' : 'Criar conta',
    forgot: 'Esqueci a senha',
    reset: 'Redefinir senha',
  }[mode]

  const subtitle = {
    login: 'Acesse sua conta para gerenciar seus leads.',
    register: awaitingVerification
      ? 'Digite o codigo enviado para seu email.'
      : 'Crie sua conta para comecar a gerar leads.',
    forgot: 'Informe seu email para receber o codigo.',
    reset: 'Digite o codigo recebido e sua nova senha.',
  }[mode]

  const submitLabel = {
    login: 'Entrar',
    register: awaitingVerification ? 'Verificar e entrar' : 'Criar conta',
    forgot: 'Enviar codigo',
    reset: 'Redefinir senha',
  }[mode]

  return (
    <div className="flex min-h-screen items-center justify-center bg-nexus-bg px-4 py-10">
      <div className="w-full max-w-[400px]">
        <div className="mb-10 text-center">
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.08]">
            <span className="text-lg font-bold text-white">N</span>
          </div>
          <h1 className="text-lg font-semibold text-white">Nexus Leads</h1>
        </div>

        <div className="card p-6 md:p-8">
          <h2 className="text-xl font-semibold tracking-tight text-white">{title}</h2>
          <p className="mt-1.5 text-[13px] text-nexus-muted">{subtitle}</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {mode === 'register' && !awaitingVerification ? (
              <InputField label="Nome" type="text" value={fullName} onChange={setFullName} placeholder="Seu nome" />
            ) : null}

            <InputField
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="voce@empresa.com"
              required
            />

            {(mode === 'login' || (mode === 'register' && !awaitingVerification)) ? (
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

            {(awaitingVerification || mode === 'reset') ? (
              <InputField
                label="Codigo de verificacao"
                type="text"
                value={verificationCode}
                onChange={(value) => setVerificationCode(value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                required
              />
            ) : null}

            {mode === 'reset' ? (
              <InputField
                label="Nova senha"
                type="password"
                value={newPassword}
                onChange={setNewPassword}
                placeholder="Minimo 8 caracteres"
                required
                minLength={8}
              />
            ) : null}

            {error ? (
              <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-[13px] text-red-400">
                {error}
              </div>
            ) : null}

            {success ? (
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2.5 text-[13px] text-emerald-400">
                {success}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-white py-2.5 text-[13px] font-semibold text-zinc-900 transition-colors hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {loading ? 'Processando...' : submitLabel}
            </button>
          </form>

          {awaitingVerification ? (
            <button
              type="button"
              onClick={() => { void resendCode() }}
              className="mt-4 text-[13px] text-nexus-muted transition-colors hover:text-white"
            >
              Reenviar codigo
            </button>
          ) : null}

          {mode === 'login' ? (
            <button
              type="button"
              onClick={() => {
                setMode('forgot')
                setError('')
                setSuccess('')
              }}
              className="mt-4 block text-[13px] text-nexus-muted transition-colors hover:text-white"
            >
              Esqueceu a senha?
            </button>
          ) : null}
        </div>

        <p className="mt-4 text-center text-[13px] text-nexus-muted">
          <button
            type="button"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login')
              setAwaitingVerification(false)
              setVerificationCode('')
              setNewPassword('')
              setError('')
              setSuccess('')
            }}
            className="transition-colors hover:text-white"
          >
            {mode === 'login'
              ? 'Nao tem conta? Criar agora'
              : mode === 'register'
                ? 'Ja possui conta? Entrar'
                : 'Voltar para login'}
          </button>
        </p>
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
      <span className="mb-1.5 block text-[12px] font-medium text-nexus-muted">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        minLength={minLength}
        className="input-base"
        placeholder={placeholder}
      />
    </label>
  )
}
