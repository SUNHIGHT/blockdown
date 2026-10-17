-- MVP schema. Differences from the first sketch:
--   foods.chain_norm added (normalized chain for exact matching)
--   daily_activity added (steps)
--   v_daily: sleep/steps/weight are aggregated in separate sub-selects so the
--            meal_items join cannot multiply them.
create extension if not exists pg_trgm;
create extension if not exists pgcrypto;   -- gen_random_uuid() on older PG

create table users (
  id uuid primary key,
  tz text not null default 'Asia/Tokyo',
  height_cm numeric,
  goal text check (goal in ('bulk','maintain','cut')),
  kcal_target int, protein_target_g int, fat_target_g int, carbs_target_g int
);

create table foods (
  id bigserial primary key,
  user_id uuid references users(id),            -- null = shared master
  chain text, chain_norm text,
  name text not null, name_norm text not null,  -- name_norm = normalize_food_name(name)
  kcal numeric not null,
  protein_g numeric, fat_g numeric, carbs_g numeric,
  macro_estimated boolean not null default false,
  source text not null check (source in ('official','user','packaged','llm')),
  source_url text, fetched_at date
);
create index foods_name_trgm on foods using gin (name_norm gin_trgm_ops);
create index foods_chain_norm on foods (chain_norm);
create index foods_user on foods (user_id);

create table meals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  local_date date not null, eaten_at timestamptz not null,
  slot text not null check (slot in ('朝','昼','夜','間食','トレ前','トレ後')),
  input_kind text check (input_kind in ('text','photo','barcode','manual','copy')),
  photo_path text
);
create index meals_user_date on meals (user_id, local_date);

create table meal_items (
  id uuid primary key default gen_random_uuid(),
  meal_id uuid not null references meals(id) on delete cascade,
  food_id bigint references foods(id),
  name text not null, amount_ratio numeric not null default 1.0,
  kcal numeric not null, protein_g numeric, fat_g numeric, carbs_g numeric,
  kcal_min numeric, kcal_max numeric,
  source text not null, confidence numeric,
  user_corrected boolean not null default false
);

create table ai_estimates (
  id uuid primary key default gen_random_uuid(),
  meal_id uuid references meals(id) on delete cascade,
  request_id text, model text, input_tokens int, output_tokens int,
  draft jsonb not null, final jsonb,
  created_at timestamptz not null default now()
);

create table sleep_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  local_date date not null,                      -- the day you woke up
  bed_at timestamptz, wake_at timestamptz,
  quality smallint check (quality between 1 and 5),
  asleep_min int,                                -- minutes actually asleep (from the watch/ring), if known
  duration_min int generated always as           -- bed -> wake
    ((extract(epoch from (wake_at - bed_at)) / 60)::int) stored,
  source text not null default 'manual',
  unique (user_id, local_date)
);

create table daily_activity (
  user_id uuid not null references users(id),
  local_date date not null,
  steps int not null, source text not null default 'healthkit',
  primary key (user_id, local_date)
);

create table workouts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  local_date date not null, kind text not null,
  sets jsonb not null,
  device_kcal numeric                            -- reference only; never fed into the energy balance
);

create table body_metrics (
  user_id uuid not null references users(id), local_date date not null,
  weight_kg numeric, waist_cm numeric, shoulder_cm numeric,
  primary key (user_id, local_date)
);

create view v_daily as
with days as (
  select user_id, local_date from meals
  union select user_id, local_date from sleep_logs
  union select user_id, local_date from daily_activity
  union select user_id, local_date from body_metrics
  union select user_id, local_date from workouts
), food as (
  select m.user_id, m.local_date,
         sum(mi.kcal) kcal_in, sum(mi.protein_g) protein_g, sum(mi.fat_g) fat_g, sum(mi.carbs_g) carbs_g
  from meals m join meal_items mi on mi.meal_id = m.id
  group by m.user_id, m.local_date
)
select d.user_id, d.local_date,
       coalesce(f.kcal_in,0) kcal_in, coalesce(f.protein_g,0) protein_g,
       coalesce(f.fat_g,0) fat_g, coalesce(f.carbs_g,0) carbs_g,
       coalesce(s.asleep_min, s.duration_min) as sleep_min, s.quality as sleep_quality,
       a.steps, b.weight_kg,
       (select count(*) from workouts w where w.user_id=d.user_id and w.local_date=d.local_date) workouts
from days d
left join food f using (user_id, local_date)
left join sleep_logs s using (user_id, local_date)
left join daily_activity a using (user_id, local_date)
left join body_metrics b using (user_id, local_date);
