-- Calories — server schema.
-- Paste the whole file into the Supabase SQL editor and run it. Safe to re-run.
--
-- It can share a project with other apps: everything here is prefixed cal_ and
-- nothing else in the database is read, changed or dropped.
--
-- The shape
--   cal_invites  invite codes, each with a use limit
--   cal_users    one row per person, keyed by a 160-bit key their phone mints
--   cal_days     one row per person per day (food entries, weigh-in)
--   cal_foods    foods everyone in the group can search (barcodes, custom foods)
--
-- RLS is on with deliberately NO policies, so none of these tables is reachable
-- over REST. Everything goes through the security-definer functions below, and
-- each one only touches rows belonging to the key it is handed. That is why the
-- publishable key sitting in the page source does not matter.
--
-- After running this, create the invite code (do not commit it — the repo is
-- public):
--   insert into public.cal_invites (code, max_uses) values ('YOUR_CODE', 10);

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------
create table if not exists public.cal_invites (
  code     text primary key check (code = upper(code)),
  max_uses int  not null default 10 check (max_uses >= 0),
  uses     int  not null default 0
);

create table if not exists public.cal_users (
  key        text primary key check (key ~ '^[0-9a-f]{40}$'),
  invite     text references public.cal_invites(code) on delete set null,
  meta       jsonb       not null default '{}'::jsonb,
  meta_at    timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table if not exists public.cal_days (
  key        text not null references public.cal_users(key) on delete cascade,
  day        date not null,
  data       jsonb       not null,
  updated_at timestamptz not null default now(),
  primary key (key, day)
);
create index if not exists cal_days_key_updated on public.cal_days (key, updated_at);

create table if not exists public.cal_foods (
  id         text primary key check (id ~ '^[A-Za-z0-9_-]{8,40}$'),
  by_key     text not null references public.cal_users(key) on delete cascade,
  barcode    text,
  data       jsonb       not null,
  updated_at timestamptz not null default now()
);
create index if not exists cal_foods_updated on public.cal_foods (updated_at);
create index if not exists cal_foods_barcode on public.cal_foods (barcode);

alter table public.cal_invites enable row level security;
alter table public.cal_users   enable row level security;
alter table public.cal_days    enable row level security;
alter table public.cal_foods   enable row level security;
revoke all on public.cal_invites, public.cal_users, public.cal_days, public.cal_foods
  from anon, authenticated;
-- no policies on purpose: nothing reaches these tables directly

-- ---------------------------------------------------------------------------
-- Joining. The hard cap lives here: an invite stops working after max_uses,
-- and the whole app stops taking people at MAX_USERS whatever the invites say.
-- ---------------------------------------------------------------------------
create or replace function public.cal_join(p_code text, p_key text)
  returns jsonb
  language plpgsql
  security definer
  set search_path = public
as $$
declare
  max_users constant int := 10;
  inv public.cal_invites;
begin
  if p_key is null or p_key !~ '^[0-9a-f]{40}$' then
    raise exception 'bad key';
  end if;
  -- Joining twice with the same phone is not a second person.
  if exists (select 1 from cal_users where key = p_key) then
    return jsonb_build_object('ok', true);
  end if;

  select * into inv from cal_invites
   where code = upper(btrim(coalesce(p_code, '')))
   for update;
  if not found then
    raise exception 'invite not recognised';
  end if;
  if inv.uses >= inv.max_uses then
    raise exception 'invite already used up';
  end if;
  if (select count(*) from cal_users) >= max_users then
    raise exception 'app is full';
  end if;

  insert into cal_users (key, invite) values (p_key, inv.code);
  update cal_invites set uses = uses + 1 where code = inv.code;
  return jsonb_build_object('ok', true);
end;
$$;

-- Leaving deletes everything the server holds for this key and gives the seat
-- back to the invite it came from.
create or replace function public.cal_leave(p_key text)
  returns void
  language plpgsql
  security definer
  set search_path = public
as $$
declare
  inv text;
begin
  select invite into inv from cal_users where key = p_key;
  if not found then return; end if;
  delete from cal_users where key = p_key;
  if inv is not null then
    update cal_invites set uses = greatest(uses - 1, 0) where code = inv;
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- Pull everything changed since a moment. p_since null = everything.
-- Group foods say whether they are yours, never whose they are: by_key is a
-- password, so it never leaves the database.
-- ---------------------------------------------------------------------------
create or replace function public.cal_pull(p_key text, p_since timestamptz)
  returns jsonb
  language plpgsql
  security definer
  set search_path = public
as $$
declare
  u public.cal_users;
begin
  select * into u from cal_users where key = p_key;
  if not found then
    raise exception 'unknown key';
  end if;
  return jsonb_build_object(
    'now',  now(),
    'meta', case when p_since is null or u.meta_at > p_since then u.meta end,
    'days', coalesce((
      select jsonb_object_agg(d.day::text, d.data)
        from cal_days d
       where d.key = p_key and (p_since is null or d.updated_at > p_since)
    ), '{}'::jsonb),
    'foods', coalesce((
      select jsonb_agg(jsonb_build_object('id', f.id, 'mine', f.by_key = p_key, 'data', f.data))
        from cal_foods f
       where p_since is null or f.updated_at > p_since
    ), '[]'::jsonb)
  );
end;
$$;

-- ---------------------------------------------------------------------------
-- Push. One round trip for everything that changed on the phone.
--   p_meta   whole meta object, or null if unchanged
--   p_days   {"2026-10-24": {...}, ...}
--   p_foods  [{"id": "...", "barcode": "...", "data": {...}}, ...]
-- The phone merges before it pushes, so these are already the merged values.
-- A food can only be changed by the person who added it.
-- ---------------------------------------------------------------------------
create or replace function public.cal_push(p_key text, p_meta jsonb, p_days jsonb, p_foods jsonb)
  returns jsonb
  language plpgsql
  security definer
  set search_path = public
as $$
declare
  d record;
  f jsonb;
begin
  if not exists (select 1 from cal_users where key = p_key) then
    raise exception 'unknown key';
  end if;
  -- Generous for one person; only stops someone filling the free tier.
  if pg_column_size(p_meta) > 1024 * 1024
     or pg_column_size(p_days) > 4 * 1024 * 1024
     or pg_column_size(p_foods) > 1024 * 1024 then
    raise exception 'payload too large';
  end if;

  if p_meta is not null then
    update cal_users set meta = p_meta, meta_at = now() where key = p_key;
  end if;

  if p_days is not null and jsonb_typeof(p_days) = 'object' then
    for d in select * from jsonb_each(p_days) loop
      if d.key !~ '^\d{4}-\d{2}-\d{2}$' then continue; end if;
      if pg_column_size(d.value) > 64 * 1024 then
        raise exception 'day too large';
      end if;
      insert into cal_days (key, day, data, updated_at)
      values (p_key, d.key::date, d.value, now())
      on conflict (key, day) do update
        set data = excluded.data, updated_at = now();
    end loop;
  end if;

  if p_foods is not null and jsonb_typeof(p_foods) = 'array' then
    if (select count(*) from cal_foods where by_key = p_key) + jsonb_array_length(p_foods) > 3000 then
      raise exception 'too many foods';
    end if;
    for f in select * from jsonb_array_elements(p_foods) loop
      if pg_column_size(f->'data') > 16 * 1024 then continue; end if;
      insert into cal_foods (id, by_key, barcode, data, updated_at)
      values (f->>'id', p_key, nullif(f->>'barcode', ''), f->'data', now())
      on conflict (id) do update
        set barcode = excluded.barcode, data = excluded.data, updated_at = now()
        where cal_foods.by_key = excluded.by_key;
    end loop;
  end if;

  return jsonb_build_object('now', now());
end;
$$;

revoke all on function public.cal_join(text, text)                 from public;
revoke all on function public.cal_leave(text)                      from public;
revoke all on function public.cal_pull(text, timestamptz)          from public;
revoke all on function public.cal_push(text, jsonb, jsonb, jsonb)  from public;
grant execute on function public.cal_join(text, text)                to anon;
grant execute on function public.cal_leave(text)                     to anon;
grant execute on function public.cal_pull(text, timestamptz)         to anon;
grant execute on function public.cal_push(text, jsonb, jsonb, jsonb) to anon;
