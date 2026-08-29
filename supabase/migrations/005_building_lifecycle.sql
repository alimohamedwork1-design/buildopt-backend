-- Mirror of frontend migration 20260829120000 (apply via Supabase CLI)

DO $$ BEGIN
  CREATE TYPE public.building_lifecycle AS ENUM (
    'DRAFT', 'CONFIGURING', 'CONNECTION_FAILED', 'DISCOVERING',
    'MAPPING_REQUIRED', 'VALIDATING', 'ACTIVE', 'DEGRADED', 'DISABLED'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

ALTER TABLE public.buildings
  ADD COLUMN IF NOT EXISTS lifecycle public.building_lifecycle NOT NULL DEFAULT 'DRAFT',
  ADD COLUMN IF NOT EXISTS timezone text DEFAULT 'Asia/Dubai';
