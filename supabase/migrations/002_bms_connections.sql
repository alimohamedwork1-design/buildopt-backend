-- Run in Supabase SQL editor (project: arddnpiluxrkndzzdpfi)
-- Stores encrypted BMS connection credentials for Metasys/BACnet/Modbus/MQTT

create table if not exists public.bms_connections (
  id uuid default gen_random_uuid() primary key,
  protocol text not null unique,
  host text,
  username text,
  password_encrypted text,
  version text,
  status text default 'disconnected',
  last_connected_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists bms_connections_protocol_idx on public.bms_connections (protocol);

alter table public.bms_connections enable row level security;

drop policy if exists "Service manage bms_connections" on public.bms_connections;
create policy "Service manage bms_connections"
  on public.bms_connections for all
  using (true)
  with check (true);
