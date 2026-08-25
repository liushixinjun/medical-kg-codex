from pathlib import Path
import re, os, json
from neo4j import GraphDatabase
root=Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
text=(root/'图谱数据库链接.txt').read_text(encoding='utf-8',errors='ignore')
bolt=re.search(r'bolt://[^\s，,;；]+',text).group(0)
user=(re.search(r'(?:用户名|username|NEO4J_USERNAME)\s*[:：=]\s*([^\s，,;；]+)',text,re.I) or [None,os.environ.get('NEO4J_USERNAME','neo4j')]).group(1) if re.search(r'(?:用户名|username|NEO4J_USERNAME)\s*[:：=]\s*([^\s，,;；]+)',text,re.I) else os.environ.get('NEO4J_USERNAME','neo4j')
pwd=(re.search(r'(?:密码|password|NEO4J_PASSWORD)\s*[:：=]\s*([^\s，,;；]+)',text,re.I) or [None,os.environ.get('NEO4J_PASSWORD','')]).group(1) if re.search(r'(?:密码|password|NEO4J_PASSWORD)\s*[:：=]\s*([^\s，,;；]+)',text,re.I) else os.environ.get('NEO4J_PASSWORD','')
terms=['超声心动图','冠状动脉造影','冠脉造影']
with GraphDatabase.driver(bolt,auth=(user,pwd)) as driver:
  with driver.session(database='neo4j') as s:
    for term in terms:
      rows=s.run('''MATCH (a) WHERE coalesce(a.status,'active') <> 'deprecated' AND (coalesce(a.name,'') CONTAINS $term OR coalesce(a.display_name,'') CONTAINS $term OR coalesce(a.preferred_name,'') CONTAINS $term OR reduce(alias_text='', alias IN coalesce(a.aliases, []) | alias_text+'|'+alias) CONTAINS $term) RETURN coalesce(a.code,'') as code, coalesce(a.display_name,a.preferred_name,a.name,'') as name, coalesce(a.disease_code,'') as disease_code, labels(a) as labels, coalesce(a.status,'') as status LIMIT 50''', {'term':term})
      print('TERM=',term)
      for r in rows:
        print(dict(r))
