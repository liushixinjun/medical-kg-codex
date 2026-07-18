set echo off
set feedback off
set heading on
set pagesize 100
set linesize 320
set trimspool on
set colsep '|'

column id format a40
column code format a20
column name format a70
column class_code format a16
column version format a12
column source format a24
column age_limit_l format a10
column age_limit_h format a10

select id,
       code,
       name,
       class_code,
       version,
       source,
       valid_flag,
       sex_limit,
       age_limit_l,
       age_limit_h
  from k_icd10_dict
 where valid_flag = 1
   and code in (
       'I21.900',
       'I21.300x004',
       'I21.401',
       'I42.900',
       'I42.000',
       'I42.100',
       'I42.101',
       'I42.200',
       'I42.200x001',
       'I42.200x002',
       'I42.201'
   )
 order by code;

exit
