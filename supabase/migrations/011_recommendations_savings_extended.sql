-- Extend recommendations & savings for durable productization (do not rewrite 006)

ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS tenant_id text;
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS equipment_id text;
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS rec_type text NOT NULL DEFAULT 'fdd_action';
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS recommended_action text;
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS expected_impact jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS confidence double precision;
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS risk text;
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS comfort_impact text;
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS verification_plan text;
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS approved_by text;
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS implemented_at timestamptz;
ALTER TABLE public.recommendations ADD COLUMN IF NOT EXISTS verified_at timestamptz;

CREATE TABLE IF NOT EXISTS public.recommendation_audit (
  audit_id text PRIMARY KEY,
  recommendation_id text NOT NULL REFERENCES public.recommendations(id) ON DELETE CASCADE,
  action text NOT NULL,
  previous_state text,
  new_state text,
  actor_user_id text,
  comment text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS recommendation_audit_rec_idx ON public.recommendation_audit (recommendation_id, created_at DESC);

ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS tenant_id text;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS recommendation_id text;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS measurement_period_start timestamptz;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS measurement_period_end timestamptz;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS implementation_date timestamptz;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS before_energy_kwh double precision;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS after_energy_kwh double precision;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS normalized_baseline_kwh double precision;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS weather_context jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS schedule_context jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS energy_saved_kwh double precision;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS cost_saved double precision;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT 'AED';
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS uncertainty double precision;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS verification_status text;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS excluded_periods jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS calculation_version text NOT NULL DEFAULT 'mv_v1';
ALTER TABLE public.savings_opportunities ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS public.savings_audit (
  audit_id text PRIMARY KEY,
  savings_id text NOT NULL REFERENCES public.savings_opportunities(id) ON DELETE CASCADE,
  action text NOT NULL,
  previous_state text,
  new_state text,
  actor_user_id text,
  comment text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS savings_audit_sav_idx ON public.savings_audit (savings_id, created_at DESC);

ALTER TABLE public.recommendation_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.savings_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS recommendation_audit_owner ON public.recommendation_audit;
CREATE POLICY recommendation_audit_owner ON public.recommendation_audit FOR ALL USING (
  EXISTS (
    SELECT 1 FROM public.recommendations r
    JOIN public.buildings b ON b.id = r.building_id
    WHERE r.id = recommendation_audit.recommendation_id AND b.owner_id = auth.uid()
  )
);

DROP POLICY IF EXISTS savings_audit_owner ON public.savings_audit;
CREATE POLICY savings_audit_owner ON public.savings_audit FOR ALL USING (
  EXISTS (
    SELECT 1 FROM public.savings_opportunities s
    JOIN public.buildings b ON b.id = s.building_id
    WHERE s.id = savings_audit.savings_id AND b.owner_id = auth.uid()
  )
);
