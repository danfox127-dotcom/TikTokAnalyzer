import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

// Only instantiate when configured. When these env vars are absent the app
// falls back to the local FastAPI engine (see app/page.tsx) and never touches
// this client — but calling createClient with empty credentials throws at
// import time, which crashed SSR / `next build` prerendering of `/`.
export const supabase: SupabaseClient =
  supabaseUrl && supabaseAnonKey
    ? createClient(supabaseUrl, supabaseAnonKey)
    : (null as unknown as SupabaseClient)
