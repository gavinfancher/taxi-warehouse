create or replace table vendors (
    vendor_id integer primary key,
    vendor_name varchar not null
);

insert into vendors (vendor_id, vendor_name) values
    (1, 'Creative Mobile Technologies, LLC'),
    (2, 'Curb Mobility, LLC'),
    (6, 'Myle Technologies Inc'),
    (7, 'Helix');


create or replace table rate_codes (
    rate_code_id integer primary key,
    rate_code_name varchar not null
);

insert into rate_codes (rate_code_id, rate_code_name) values
    (1, 'Standard rate'),
    (2, 'JFK'),
    (3, 'Newark'),
    (4, 'Nassau or Westchester'),
    (5, 'Negotiated fare'),
    (6, 'Group ride'),
    (99, 'Null/unknown');


create or replace table payment_types (
    payment_type_id integer primary key,
    payment_type_name varchar not null
);

insert into payment_types (payment_type_id, payment_type_name) values
    (0, 'Flex Fare trip'),
    (1, 'Credit card'),
    (2, 'Cash'),
    (3, 'No charge'),
    (4, 'Dispute'),
    (5, 'Unknown'),
    (6, 'Voided trip');


create or replace table trip_types (
    trip_type_id integer primary key,
    trip_type_name varchar not null
);

insert into trip_types (trip_type_id, trip_type_name) values
    (1, 'Street-hail'),
    (2, 'Dispatch');
