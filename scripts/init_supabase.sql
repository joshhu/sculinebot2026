-- sculinebot2026 schema
-- 後端用 service_role key 直接寫入；不啟用 RLS（後端唯一寫入者）

create extension if not exists "pgcrypto";

create table if not exists users (
  line_user_id     text primary key,
  display_name     text,
  picture_url      text,
  created_at       timestamptz default now(),
  active_trip_id   uuid
);

create table if not exists trips (
  id                 uuid primary key default gen_random_uuid(),
  user_id            text references users(line_user_id) on delete cascade,
  title              text,
  status             text not null default 'active' check (status in ('active','closed')),
  started_at         timestamptz default now(),
  ended_at           timestamptz,
  summary_md         text,
  summary_html_url   text,
  cover_photo_url    text
);

create index if not exists trips_user_id_idx on trips(user_id, started_at desc);

create table if not exists trip_entries (
  id          uuid primary key default gen_random_uuid(),
  trip_id     uuid references trips(id) on delete cascade,
  ts          timestamptz default now(),
  kind        text not null check (kind in ('text','photo','audio','location')),
  raw_text    text,
  photo_url   text,
  audio_url   text,
  lat         double precision,
  lng         double precision,
  ai_meta     jsonb
);

create index if not exists trip_entries_trip_ts_idx on trip_entries(trip_id, ts);
