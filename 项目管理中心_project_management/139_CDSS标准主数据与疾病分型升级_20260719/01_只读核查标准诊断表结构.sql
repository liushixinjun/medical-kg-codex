set echo off
set feedback off
set heading on
set pagesize 500
set linesize 240
set trimspool on
set colsep '|'

column table_name format a28
column column_name format a32
column data_type format a18

select table_name,
       column_id,
       column_name,
       data_type,
       data_length,
       nullable
  from user_tab_columns
 where table_name in ('K_ICD10_DICT', 'K_DISEASE_DICT')
 order by table_name, column_id;

exit
