Arch Linux mirror delay monitor
====

Configuration
----

Setup database and create a PostgreSQL account for Grafana:

```sh
sudo -u postgres psql
```

```pgsql
create role grafana password 'xxx' login;
```

```sh
psql < dbsetup.sql
```

```pgsql
grant usage on schema mirror_delay to grafana;
grant select on all tables in schema mirror_delay to grafana;
```

Grafana panel SQL:

```pgsql
select 
  $__timeGroupAlias(ts,$__interval),
  name,
  avg(delay) filter (where ts <= ts and ts > ts - '24 hours'::interval) over (partition by name order by ts desc) as delay
from mirror_delay.cnmirror_delay
where
  $__timeFilter(ts)
order by ts asc
```
