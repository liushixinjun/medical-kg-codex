set echo off
set feedback off
set heading on
set pagesize 1000
set linesize 360
set trimspool on
set colsep '|'

column id format a40
column code format a20
column name format a80
column class_code format a20
column version format a20
column source format a30
column age_limit_l format a12
column age_limit_h format a12

select id,
       code,
       name,
       class_code,
       version,
       source,
       sex_limit,
       age_limit_l,
       age_limit_h,
       crb_flag
  from k_icd10_dict
 where valid_flag = 1
   and (
        name like '%心肌梗死%'
        or name like '%肥厚型心肌病%'
        or name like '%扩张型心肌病%'
        or name like '%心肌病%'
       )
 order by case
            when code = 'I21.900' then 1
            when code like 'I21%' then 2
            when code = 'I42.900' then 3
            when code like 'I42%' then 4
            else 9
          end,
          code,
          name;

exit
