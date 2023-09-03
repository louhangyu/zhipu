-- mysql
CREATE USER 'cacti'@'%' IDENTIFIED BY 'cacti123';

-- postgresql
create user reporter with password 'report_1232*()';
GRANT pg_read_all_data TO reporter;

create user feature_dev with password 'howtodoit12345_*&%';
GRANT pg_read_all_data TO feature_dev;
GRANT ALL PRIVILEGES ON feature TO feature_dev;