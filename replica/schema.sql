-- Aura v2: OPTIONAL cross-device sync (favourites + watch history).
-- Not required for feature parity: v1/v2 keep this state in localStorage.
-- Target: Supabase Postgres. Access rule: row level security, user_id = auth.uid().
-- Identity: Supabase anonymous auth per device; devices are linked to one user
-- with a short pairing code (no passwords on a TV remote).

create table devices (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('web','phone','tv')),
  label text,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on devices (user_id);

-- channel_num refers to Channel.num in channels.json (static data, so there is no FK).
-- The pipeline guarantees num stability across refreshes.
create table favourites (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  channel_num integer not null check (channel_num > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, channel_num)            -- favouriting twice is a no-op (upsert)
);
create index on favourites (user_id, created_at desc);

create table watch_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  device_id uuid references devices(id) on delete set null,
  channel_num integer not null check (channel_num > 0),
  watched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, channel_num)            -- MRU list: upsert bumps watched_at
);
create index on watch_history (user_id, watched_at desc);

alter table devices       enable row level security;
alter table favourites    enable row level security;
alter table watch_history enable row level security;

create policy own_devices on devices
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_favourites on favourites
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_history on watch_history
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Trim history to the 8 most recent per user (the client shows 8).
-- Run from a scheduled function or after each upsert.
-- delete from watch_history w where w.user_id = auth.uid() and w.id not in (
--   select id from watch_history where user_id = auth.uid() order by watched_at desc limit 8);
