-- Create the dossiers table for persistent forensic reports
CREATE TABLE IF NOT EXISTS public.dossiers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  profile_payload JSONB NOT NULL,
  primary_archetype TEXT,
  total_conscious_videos INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  
  -- Metadata for tracking multiple exports over time
  fingerprint TEXT
);

-- Enable RLS
ALTER TABLE public.dossiers ENABLE ROW LEVEL SECURITY;

-- Allow users to read their own dossiers
CREATE POLICY "Users can view own dossiers" ON public.dossiers
  FOR SELECT USING (auth.uid() = auth.uid());

-- Allow anyone to create a dossier (for guest flow)
CREATE POLICY "Anyone can create a dossier" ON public.dossiers
  FOR INSERT WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- STORAGE CONFIGURATION
-- ---------------------------------------------------------------------------

-- 1. Create the 'exports' bucket if it doesn't exist
INSERT INTO storage.buckets (id, name, public)
VALUES ('exports', 'exports', true)
ON CONFLICT (id) DO NOTHING;

-- 2. Allow Public Uploads to 'exports'
CREATE POLICY "Allow public uploads"
ON storage.objects FOR INSERT
WITH CHECK ( bucket_id = 'exports' );

-- 3. Allow Public Reads (so Edge Function and Frontend can access)
CREATE POLICY "Allow public reads"
ON storage.objects FOR SELECT
USING ( bucket_id = 'exports' );
