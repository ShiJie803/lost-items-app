use zhoushijie_db;
alter table claim add column timestamp datetime default now();
