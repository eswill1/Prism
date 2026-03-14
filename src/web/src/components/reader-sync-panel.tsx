'use client'

import Link from 'next/link'
import { useState } from 'react'

import { getReaderEmailAuthMode } from '../lib/reader-auth-config'
import { getSupabaseBrowserClient, hasSupabaseBrowserConfig } from '../lib/supabase/browser'
import { useLocalTrackingImport } from '../lib/use-local-tracking-import'
import { useReaderSession } from '../lib/use-reader-session'

export function ReaderSyncPanel() {
  const session = useReaderSession()
  const authMode = getReaderEmailAuthMode()
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const importState = useLocalTrackingImport({
    enabled: session.status === 'signed_in',
  })

  const onRequestCode = async () => {
    const client = getSupabaseBrowserClient()
    if (!client) {
      setStatusMessage('Reader sync is not configured on this environment yet.')
      return
    }

    setIsSubmitting(true)
    setStatusMessage(null)

    const { error } = await client.auth.signInWithOtp({
      email,
      options: {
        shouldCreateUser: true,
        emailRedirectTo:
          authMode === 'magic_link' && typeof window !== 'undefined'
            ? `${window.location.origin}/sync`
            : undefined,
      },
    })

    setIsSubmitting(false)
    if (error) {
      setStatusMessage(error.message)
      return
    }

    setStatusMessage(
      authMode === 'otp'
        ? 'Check your email for the Prism one-time code, then paste it here.'
        : 'Check your email for the Prism magic link. It should return you to this sync page.',
    )
  }

  const onVerifyCode = async () => {
    const client = getSupabaseBrowserClient()
    if (!client) {
      setStatusMessage('Reader sync is not configured on this environment yet.')
      return
    }

    setIsSubmitting(true)
    setStatusMessage(null)

    const { error } = await client.auth.verifyOtp({
      email,
      token: code,
      type: 'email',
    })

    setIsSubmitting(false)
    if (error) {
      setStatusMessage(error.message)
      return
    }

    setStatusMessage('Reader sync is active for this account.')
  }

  const onSignOut = async () => {
    const client = getSupabaseBrowserClient()
    if (!client) {
      return
    }

    setIsSubmitting(true)
    setStatusMessage(null)
    const { error } = await client.auth.signOut()
    setIsSubmitting(false)

    if (error) {
      setStatusMessage(error.message)
      return
    }

      setStatusMessage('Signed out. Browser-local tracking still works without an account.')
    }

  return (
    <section className="panel sync-panel">
      <p className="panel-label">Reader sync</p>
      <h1>Keep saved and followed stories beyond this browser.</h1>
      <p className="hero-dek">
        Prism stays open for normal reading. Sign in only if you want your working set to
        persist across devices and support upcoming saved-story deltas.
      </p>

      {!hasSupabaseBrowserConfig() || session.status === 'unavailable' ? (
        <p className="tracking-footnote">
          Reader sync is not configured in this environment yet. Local save/follow still works.
        </p>
      ) : session.status === 'signed_in' ? (
        <div className="sync-panel-stack">
          <div className="tracking-chip-row">
            <span className="tracking-chip active">Signed in</span>
            <span className="tracking-chip">{session.email || 'reader'}</span>
          </div>
          <p>
            This account now backs saved stories and followed updates. Your browser-local
            working set is imported automatically the first time you sign in here.
          </p>
          <div className="tracking-actions">
            <Link className="primary-link" href="/saved">
              Open saved stories
            </Link>
            <button
              className="action-pill"
              onClick={onSignOut}
              type="button"
              disabled={isSubmitting || importState.isImporting}
            >
              Sign out
            </button>
          </div>
          {importState.isImporting ? (
            <p className="tracking-footnote">Importing this browser’s tracked stories into your account...</p>
          ) : null}
          {importState.error ? <p className="tracking-footnote">{importState.error}</p> : null}
        </div>
      ) : (
        <div className="sync-panel-stack">
          <label className="sync-field">
            <span>Email</span>
            <input
              className="newsletter-input"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </label>
          <div className="tracking-actions">
            <button
              className="primary-link action-pill"
              onClick={onRequestCode}
              type="button"
              disabled={!email || isSubmitting}
            >
              {authMode === 'otp' ? 'Email sign-in code' : 'Email magic link'}
            </button>
          </div>
          {authMode === 'otp' ? (
            <>
              <label className="sync-field">
                <span>One-time code</span>
                <input
                  className="newsletter-input"
                  type="text"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  placeholder="Paste the email code"
                  autoComplete="one-time-code"
                />
              </label>
              <div className="tracking-actions">
                <button
                  className="action-pill"
                  onClick={onVerifyCode}
                  type="button"
                  disabled={!email || !code || isSubmitting}
                >
                  Verify code
                </button>
                <Link className="secondary-link" href="/saved">
                  Keep using local tracking
                </Link>
              </div>
            </>
          ) : (
            <>
              <p className="tracking-footnote">
                This environment is currently configured for magic links. For OTP-only
                testing, switch the Supabase email template to emit <code>{'{{ .Token }}'}</code>{' '}
                and set <code>NEXT_PUBLIC_PRISM_READER_EMAIL_AUTH_MODE=otp</code>.
              </p>
              <div className="tracking-actions">
                <Link className="secondary-link" href="/saved">
                  Keep using local tracking
                </Link>
              </div>
            </>
          )}
        </div>
      )}

      {statusMessage ? <p className="tracking-footnote">{statusMessage}</p> : null}
    </section>
  )
}
