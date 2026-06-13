create or replace table rideshare_licenses (
    rideshare_license_num varchar primary key,
    company_name varchar not null
);

insert into rideshare_licenses (rideshare_license_num, company_name) 
values
    ('HV0002', 'Juno'),
    ('HV0003', 'Uber'),
    ('HV0004', 'Via'),
    ('HV0005', 'Lyft');