-- Optional: track who acknowledged an alert (run if not applied)
alter table public.building_alerts
  add column if not exists acknowledged_by text,
  add column if not exists updated_at timestamptz default now();

create index if not exists building_alerts_acknowledged_idx on public.building_alerts (acknowledged);
