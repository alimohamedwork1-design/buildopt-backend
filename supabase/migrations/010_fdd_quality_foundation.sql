-- Phase 6: FDD faults, fault audit, historical quality rollups

create table if not exists public.fdd_faults (
  fault_id text primary key,
  rule_id text not null,
  tenant_id text,
  building_id text not null,
  equipment_id text not null,
  equipment_type text not null default 'AHU',
  severity text not null default 'warning',
  status text not null default 'DETECTED',
  confidence double precision not null default 0.5,
  data_quality_score double precision,
  input_coverage double precision,
  evidence jsonb not null default '{}'::jsonb,
  source_points jsonb not null default '[]'::jsonb,
  observed_values jsonb not null default '{}'::jsonb,
  reason text,
  recommended_next_check text,
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  detected_at timestamptz not null default now(),
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists fdd_faults_building_idx on public.fdd_faults (building_id, status, last_seen desc);
create index if not exists fdd_faults_equipment_idx on public.fdd_faults (equipment_id, status);

create table if not exists public.fdd_fault_audit (
  audit_id text primary key,
  fault_id text references public.fdd_faults(fault_id) on delete cascade,
  action text not null,
  previous_status text,
  new_status text,
  actor_user_id text,
  comment text,
  created_at timestamptz not null default now()
);

create index if not exists fdd_fault_audit_fault_idx on public.fdd_fault_audit (fault_id, created_at desc);

create table if not exists public.point_quality_rollups (
  rollup_id text primary key,
  point_id uuid,
  building_id text not null,
  period_start timestamptz not null,
  period_end timestamptz not null,
  sample_count integer not null default 0,
  good_count integer not null default 0,
  stale_count integer not null default 0,
  bad_count integer not null default 0,
  gap_count integer not null default 0,
  quality_score double precision not null default 0,
  components jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists point_quality_rollups_building_idx on public.point_quality_rollups (building_id, period_end desc);

alter table public.fdd_faults enable row level security;
alter table public.fdd_fault_audit enable row level security;
alter table public.point_quality_rollups enable row level security;

drop policy if exists "Service manage fdd_faults" on public.fdd_faults;
create policy "Service manage fdd_faults" on public.fdd_faults for all using (true) with check (true);

drop policy if exists "Service manage fdd_fault_audit" on public.fdd_fault_audit;
create policy "Service manage fdd_fault_audit" on public.fdd_fault_audit for all using (true) with check (true);

drop policy if exists "Service manage point_quality_rollups" on public.point_quality_rollups;
create policy "Service manage point_quality_rollups" on public.point_quality_rollups for all using (true) with check (true);
