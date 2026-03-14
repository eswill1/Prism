'use client'

import { useEffect, useState } from 'react'

import { getSupabaseBrowserClient } from './supabase/browser'

export type ReaderSessionState = {
  status: 'loading' | 'signed_out' | 'signed_in' | 'unavailable'
  email?: string
  accessToken?: string
  userId?: string
}

export function useReaderSession(): ReaderSessionState {
  const [state, setState] = useState<ReaderSessionState>(() => {
    const client = getSupabaseBrowserClient()
    return client ? { status: 'loading' } : { status: 'unavailable' }
  })

  useEffect(() => {
    const client = getSupabaseBrowserClient()
    if (!client) {
      setState({ status: 'unavailable' })
      return
    }

    let active = true

    client.auth
      .getSession()
      .then(({ data, error }) => {
        if (!active) {
          return
        }

        if (error || !data.session) {
          setState({ status: 'signed_out' })
          return
        }

        setState({
          status: 'signed_in',
          email: data.session.user.email || undefined,
          accessToken: data.session.access_token,
          userId: data.session.user.id,
        })
      })
      .catch(() => {
        if (active) {
          setState({ status: 'signed_out' })
        }
      })

    const { data } = client.auth.onAuthStateChange((_event, session) => {
      if (!active) {
        return
      }

      if (!session) {
        setState({ status: 'signed_out' })
        return
      }

      setState({
        status: 'signed_in',
        email: session.user.email || undefined,
        accessToken: session.access_token,
        userId: session.user.id,
      })
    })

    return () => {
      active = false
      data.subscription.unsubscribe()
    }
  }, [])

  return state
}
