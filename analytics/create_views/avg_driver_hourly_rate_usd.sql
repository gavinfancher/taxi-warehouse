create view avg_driver_hourly_rate_usd as
with aggregated_trips as (
    select
        avg(trip_time) / 3600.0 as avg_trip_time_hours,
        avg(driver_pay) as avg_driver_pay,
        avg(tips) as avg_tips
    from rideshare_trips
)
select
    round((avg_driver_pay + avg_tips) / avg_trip_time_hours, 2) as avg_hourly_rate_usd
from aggregated_trips;