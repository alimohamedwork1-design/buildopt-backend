-- Phase 3: Raw Point Registry, Gateway Identity, Current State, Event Idempotency
-- Apply via Supabase SQL editor or scripts/apply_supabase_migration.py

-- Registered edge gateways (server-side identity binding)
create table if not exists public.gateways (
  gateway_id text primary key,
  tenant_id text not null,
  building_id text not null,
  connector_id text not null default 'metasys',
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists gateways_tenant_idx on public.gateways (tenant_id);
create index if not exists gateways_building_idx on public.gateways (building_id);

-- Immutable raw source point identity
create table if not exists public.raw_points (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null,
  building_id text not null,
  gateway_id text not null references public.gateways(gateway_id),
  connector_id text not null,
  source text not null,
  source_point_id text not null,
  source_name text,
  source_path text,
  source_type text,
  raw_unit text,
  metadata jsonb not null default '{}'::jsonb,
  discovered_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  enabled boolean not null default true,
  expected_interval_seconds integer not null default 30,
  unique (tenant_id, connector_id, source_point_id)
);

create index if not exists raw_points_building_idx on public.raw_points (building_id);
create index if not exists raw_points_gateway_idx on public.raw_points (gateway_id);
create index if not exists raw_points_last_seen_idx on public.raw_points (last_seen_at desc);

-- Latest value per point (separate from Influx history)
create table if not exists public.point_current_state (
  point_id uuid primary key references public.raw_points(id) on delete cascade,
  last_value double precision,
  last_value_text text,
  last_source_timestamp timestamptz,
  last_edge_received_at timestamptz,
  last_cloud_received_at timestamptz,
  source_quality text,
  normalized_quality text not null default 'NO_DATA',
  freshness_seconds integer,
  expected_interval_seconds integer not null default 30,
  freshness_state text not null default 'NO_DATA',
  state text not null default 'NO_DATA',
  updated_at timestamptz not null default now()
);

create index if not exists point_current_state_freshness_idx on public.point_current_state (freshness_state);

-- Processed telemetry events (idempotency)
create table if not exists public.telemetry_events (
  event_id text primary key,
  tenant_id text not null,
  building_id text not null,
  gateway_id text not null,
  processed_at timestamptz not null default now()
);

create index if not exists telemetry_events_building_idx on public.telemetry_events (building_id, processed_at desc);

alter table public.gateways enable row level security;
alter table public.raw_points enable row level security;
alter table public.point_current_state enable row level security;
alter table public.telemetry_events enable row level security;

drop policy if exists "Service manage gateways" on public.gateways;
create policy "Service manage gateways" on public.gateways for all using (true) with check (true);

drop policy if exists "Service manage raw_points" on public.raw_points;
create policy "Service manage raw_points" on public.raw_points for all using (true) with check (true);

drop policy if exists "Service manage point_current_state" on public.point_current_state;
create policy "Service manage point_current_state" on public.point_current_state for all using (true) with check (true);

drop policy if exists "Service manage telemetry_events" on public.telemetry_events;
create policy "Service manage telemetry_events" on public.telemetry_events for all using (true) with check (true);
