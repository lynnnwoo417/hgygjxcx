-- 回归预告机 · events 表
-- 在 Supabase 控制台 SQL Editor 中整段运行即可。

create table if not exists public.events (
  id bigserial primary key,
  source_event_id text not null unique,
  artist text not null default '',
  title text not null default '',
  event_type text not null default 'other',
  event_date date,
  event_time text,
  end_time text,
  venue text,
  city text,
  region text,
  ticket_platform text,
  ticket_open_time text,
  official_url text,
  source_url text,
  source_name text,
  status text not null default 'upcoming',
  cover_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_checked_at timestamptz
);

comment on table public.events is 'K-pop 活动聚合表，由爬虫写入、Serverless API 读取';
comment on column public.events.source_event_id is '来源稳定 ID，防止同一活动被重复插入';
comment on column public.events.event_type is 'comeback | prerecording | concert | fansign | popup | other';
comment on column public.events.status is 'upcoming | registration_open | sold_out | cancelled | finished';
comment on column public.events.region is 'KR | JP | CN | HK | MO | TW | US | OTHER，供小程序地区筛选';
comment on column public.events.city is '对应小程序 locationText / 展示地点';
comment on column public.events.title is '对应小程序 detail（活动名称）';
comment on column public.events.event_time is '对应小程序 showTime';
comment on column public.events.ticket_open_time is '对应小程序 ticketTime（开票时间，不是场馆）';
comment on column public.events.cover_url is '对应小程序 coverImage';
comment on column public.events.source_url is '对应小程序 detailUrl';
comment on column public.events.official_url is '对应小程序 officialUrl';

create index if not exists events_artist_idx on public.events (artist);
create index if not exists events_event_date_idx on public.events (event_date);
create index if not exists events_event_type_idx on public.events (event_type);
create index if not exists events_status_idx on public.events (status);
create index if not exists events_region_idx on public.events (region);
create index if not exists events_source_name_idx on public.events (source_name);

alter table public.events enable row level security;

-- 匿名用户不能直连数据库。小程序只能走 Serverless API（service_role 在服务端）。
drop policy if exists events_no_direct_anon on public.events;
