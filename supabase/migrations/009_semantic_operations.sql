-- Phase 5: Semantic audit trail and collection config versioning

create table if not exists public.semantic_audit_log (
  audit_id text primary key,
  point_id uuid references public.raw_points(id) on delete set null,
  building_id text not null,
  tenant_id text,
  gateway_id text,
  source_point_id text,
  action text not null,
  previous_state jsonb not null default '{}'::jsonb,
  new_state jsonb not null default '{}'::jsonb,
  actor_user_id text,
  actor_email text,
  comment text,
  confidence double precision,
  created_at timestamptz not null default now()
);

create index if not exists semantic_audit_building_idx on public.semantic_audit_log (building_id, created_at desc);
create index if not exists semantic_audit_point_idx on public.semantic_audit_log (point_id, created_at desc);

create table if not exists public.collection_config_versions (
  config_version text primary key,
  building_id text not null,
  gateway_id text,
  tenant_id text,
  mapping_revision integer not null default 1,
  point_count integer not null default 0,
  approved_count integer not null default 0,
  status text not null default 'DRAFT',
  config_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  activated_at timestamptz
);

create index if not exists collection_config_building_idx on public.collection_config_versions (building_id, created_at desc);
create index if not exists collection_config_gateway_idx on public.collection_config_versions (gateway_id, status);

alter table public.semantic_audit_log enable row level security;
alter table public.collection_config_versions enable row level security;

drop policy if exists "Service manage semantic_audit_log" on public.semantic_audit_log;
create policy "Service manage semantic_audit_log" on public.semantic_audit_log for all using (true) with check (true);

drop policy if exists "Service manage collection_config_versions" on public.collection_config_versions;
create policy "Service manage collection_config_versions" on public.collection_config_versions for all using (true) with check (true);
