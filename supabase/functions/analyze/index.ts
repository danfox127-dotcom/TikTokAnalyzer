import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"
import { parseTiktokData } from "../_shared/forensics/tiktok_parser.ts"
import { buildGhostProfile } from "../_shared/forensics/ghost_profile.ts"

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    )

    let rawData;
    const body = await req.json().catch(() => ({}))
    
    if (body.filePath) {
      // 1. Download from Storage
      const { data: fileData, error: downloadError } = await supabase.storage
        .from('exports')
        .download(body.filePath)

      if (downloadError) throw downloadError
      const text = await fileData.text()
      rawData = JSON.parse(text)
    } else {
      // Fallback to direct multipart upload (smaller files)
      const formData = await req.formData()
      const file = formData.get('file') as File
      if (!file) throw new Error('No file provided')
      const text = await file.text()
      rawData = JSON.parse(text)
    }
    
    // 2. Parse the raw TikTok export
    const parsed = parseTiktokData(rawData)
    
    // 3. Build the behavioral Ghost Profile
    const ghostProfile = buildGhostProfile(parsed)
    
    // 4. Save to Database for persistence
    const { data: dossier, error: dbError } = await supabase
      .from('dossiers')
      .insert({
        profile_payload: ghostProfile,
        primary_archetype: ghostProfile.primary_archetype.name,
        total_conscious_videos: ghostProfile.stopwatch_metrics.total_conscious_videos
      })
      .select()
      .single()

    return new Response(JSON.stringify({ ...ghostProfile, dossier_id: dossier?.id }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }
})
