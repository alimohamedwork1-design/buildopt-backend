-- Recommendations and savings lifecycle tables (OpenBlue parity)

DO $$ BEGIN
  CREATE TYPE public.recommendation_state AS ENUM (
    'DETECTED', 'INVESTIGATING', 'RECOMMENDED', 'APPROVED', 'SCHEDULED',
    'IMPLEMENTED', 'MONITORING', 'VERIFIED', 'CLOSED', 'REJECTED'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE public.savings_state AS ENUM (
    'POTENTIAL', 'APPROVED', 'IMPLEMENTED', 'MONITORING', 'VERIFIED', 'REJECTED'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS public.recommendations (
  id text PRIMARY KEY,
  building_id uuid NOT NULL REFERENCES public.buildings(id) ON DELETE CASCADE,
  title text NOT NULL,
  description text NOT NULL DEFAULT '',
  state public.recommendation_state NOT NULL DEFAULT 'DETECTED',
  severity text NOT NULL DEFAULT 'warning',
  owner text,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  expected_saving_aed double precision,
  verified_saving_aed double precision,
  fault_id text,
  work_order_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_recommendations_building ON public.recommendations(building_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_state ON public.recommendations(state);

CREATE TABLE IF NOT EXISTS public.savings_opportunities (
  id text PRIMARY KEY,
  building_id uuid NOT NULL REFERENCES public.buildings(id) ON DELETE CASCADE,
  title text NOT NULL,
  state public.savings_state NOT NULL DEFAULT 'POTENTIAL',
  baseline_kwh double precision NOT NULL DEFAULT 0,
  expected_kwh double precision NOT NULL DEFAULT 0,
  actual_kwh double precision,
  avoided_kwh double precision,
  tariff_aed_per_kwh double precision NOT NULL DEFAULT 0.38,
  expected_saving_aed double precision NOT NULL DEFAULT 0,
  verified_saving_aed double precision,
  confidence double precision NOT NULL DEFAULT 0.5,
  methodology text NOT NULL DEFAULT 'baseline_comparison',
  data_coverage_pct double precision NOT NULL DEFAULT 0,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_savings_building ON public.savings_opportunities(building_id);
CREATE INDEX IF NOT EXISTS idx_savings_state ON public.savings_opportunities(state);

ALTER TABLE public.recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.savings_opportunities ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS recommendations_owner ON public.recommendations;
DROP POLICY IF EXISTS savings_owner ON public.savings_opportunities;

CREATE POLICY recommendations_owner ON public.recommendations
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.buildings b
      WHERE b.id = recommendations.building_id AND b.owner_id = auth.uid()
    )
  );

CREATE POLICY savings_owner ON public.savings_opportunities
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.buildings b
      WHERE b.id = savings_opportunities.building_id AND b.owner_id = auth.uid()
    )
  );
