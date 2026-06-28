-- Run in Supabase SQL editor (project: arddnpiluxrkndzzdpfi)
-- Extends alerts for BMS/FDD pipeline pushes from Railway

create table if not exists public.building_alerts (
  id text primary key,
  building_id text not null,
  equipment_id text,
  severity text not null check (severity in ('critical', 'warning', 'info')),
  category text,
  title text not null,
  message text,
  message_ar text,
  acknowledged boolean default false,
  created_at timestamptz default now()
);

create index if not exists building_alerts_building_id_idx on public.building_alerts (building_id);
create index if not exists building_alerts_created_at_idx on public.building_alerts (created_at desc);

alter table public.building_alerts enable row level security;

drop policy if exists "Public read building_alerts" on public.building_alerts;
create policy "Public read building_alerts"
  on public.building_alerts for select
  using (true);

drop policy if exists "Service insert building_alerts" on public.building_alerts;
create policy "Service insert building_alerts"
  on public.building_alerts for insert
  with check (true);
