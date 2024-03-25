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
  ts as time,
  name,
  avg(delay) filter (where ts > ts - '24 hours'::interval) over (partition by name order by ts asc) as delay
from mirror_delay.cnmirror_delay
where
  ts > $__timeFrom()::timestamp - '24 hours'::interval and ts <= $__timeTo()
  and name != 'archlinuxcn'
order by ts asc
```
