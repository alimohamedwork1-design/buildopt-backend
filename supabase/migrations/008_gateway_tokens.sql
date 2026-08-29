-- Phase 4: Per-gateway scoped ingest tokens
-- Apply via Lovable query_database or Supabase SQL editor

create table if not exists public.gateway_tokens (
  token_id text primary key,
  gateway_id text not null references public.gateways(gateway_id) on delete cascade,
  token_hash text not null unique,
  label text,
  created_at timestamptz not null default now(),
  revoked_at timestamptz,
  expires_at timestamptz
);

create index if not exists gateway_tokens_gateway_idx on public.gateway_tokens (gateway_id);
create index if not exists gateway_tokens_hash_idx on public.gateway_tokens (token_hash);

alter table public.gateway_tokens enable row level security;

drop policy if exists "Service manage gateway_tokens" on public.gateway_tokens;
create policy "Service manage gateway_tokens" on public.gateway_tokens for all using (true) with check (true);
