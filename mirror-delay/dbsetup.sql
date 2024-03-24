create schema if not exists mirror_delay;
set search_path to mirror_delay;

create table cnmirror_delay (
  id serial primary key,
  ts timestamp with time zone not null default current_timestamp,
  name text not null,
  delay integer not null
);

create index ts_idx on cnmirror_delay (ts);
