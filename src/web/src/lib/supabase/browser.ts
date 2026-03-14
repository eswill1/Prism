'use client'

import { createClient, type SupabaseClient } from '@supabase/supabase-js'

let browserClient: SupabaseClient | null = null

export function hasSupabaseBrowserConfig() {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  )
}

export function getSupabaseBrowserClient() {
  if (!hasSupabaseBrowserConfig()) {
    return null
  }

  if (browserClient) {
    return browserClient
  }

  browserClient = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL as string,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY as string,
    {
      global: {
        headers: {
          'x-prism-surface': 'web-preview',
        },
      },
    },
  )

  return browserClient
}
