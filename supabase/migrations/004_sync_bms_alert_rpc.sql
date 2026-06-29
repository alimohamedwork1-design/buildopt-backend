-- BuildOpt: BMS alert sync (SQL replacement for sync-bms-alert edge function)
-- Project: arddnpiluxrkndzzdpfi
-- Run in Supabase Dashboard → SQL Editor → New query → paste → Run
--
-- Secret must match Railway ALERT_WEBHOOK_SECRET (default: buildopt-alert-sync-2026-secret)

create table if not exists public.building_alerts (
  id text primary key,
  building_id text not null,
  equipment_id text,
  severity text not null check (severity in ('critical', 'warning', 'info')),
  category text,
  title text not null,
  message text,
  message_ar text,
  acknowledged boolean not null default false,
  acknowledged_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists building_alerts_building_id_idx
  on public.building_alerts (building_id);

create index if not exists building_alerts_created_at_idx
  on public.building_alerts (created_at desc);

create index if not exists building_alerts_acknowledged_idx
  on public.building_alerts (acknowledged);

create or replace function public.sync_bms_alert(p_secret text, p_alert jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_expected_secret text := 'buildopt-alert-sync-2026-secret';
  v_id text;
  v_row public.building_alerts%rowtype;
begin
  if p_secret is null or p_secret <> v_expected_secret then
    raise exception 'Unauthorized' using errcode = '28000';
  end if;

  v_id := coalesce(p_alert->>'id', gen_random_uuid()::text);

  insert into public.building_alerts (
    id,
    building_id,
    equipment_id,
    severity,
    category,
    title,
    message,
    message_ar,
    acknowledged,
    created_at,
    updated_at
  )
  values (
    v_id,
    coalesce(p_alert->>'building_id', 'unknown'),
    nullif(p_alert->>'equipment_id', ''),
    coalesce(nullif(p_alert->>'severity', ''), 'info'),
    nullif(p_alert->>'category', ''),
    coalesce(nullif(p_alert->>'title', ''), 'BMS alert'),
    nullif(p_alert->>'message', ''),
    coalesce(
      nullif(p_alert->>'message_ar', ''),
      nullif(p_alert->>'message', '')
    ),
    coalesce((p_alert->>'acknowledged')::boolean, false),
    coalesce(
      nullif(p_alert->>'timestamp', '')::timestamptz,
      nullif(p_alert->>'created_at', '')::timestamptz,
      now()
    ),
    now()
  )
  on conflict (id) do update set
    building_id = excluded.building_id,
    equipment_id = excluded.equipment_id,
    severity = excluded.severity,
    category = excluded.category,
    title = excluded.title,
    message = excluded.message,
    message_ar = excluded.message_ar,
    acknowledged = excluded.acknowledged,
    updated_at = now()
  returning * into v_row;

  return jsonb_build_object(
    'success', true,
    'table', 'building_alerts',
    'id', v_row.id
  );
end;
$$;

revoke all on function public.sync_bms_alert(text, jsonb) from public;
grant execute on function public.sync_bms_alert(text, jsonb) to anon, authenticated, service_role;

alter table public.building_alerts enable row level security;

drop policy if exists "Public read building_alerts" on public.building_alerts;
create policy "Public read building_alerts"
  on public.building_alerts
  for select
  to anon, authenticated
  using (true);

drop policy if exists "Authenticated update building_alerts" on public.building_alerts;
create policy "Authenticated update building_alerts"
  on public.building_alerts
  for update
  to authenticated
  using (true)
  with check (true);

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'building_alerts'
  ) then
    alter publication supabase_realtime add table public.building_alerts;
  end if;
end $$;
