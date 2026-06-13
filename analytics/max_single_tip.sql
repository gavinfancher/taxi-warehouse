select
    pickup_datetime,
    tips
from rideshare_trips
order by tips desc
limit 1;