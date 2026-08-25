from pathlib import Path
import re, os
from neo4j import GraphDatabase
root=Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
text=(root/'图谱数据库链接.txt').read_text(encoding='utf-8',errors='ignore')
bolt=re.search(r'bolt://[^\s，,;；]+',text).group(0)
u=re.search(r'(?:用户名|username|NEO4J_USERNAME)\s*[:：=]\s*([^\s，,;；]+)',text,re.I); user=u.group(1) if u else os.environ.get('NEO4J_USERNAME','neo4j')
p=re.search(r'(?:密码|password|NEO4J_PASSWORD)\s*[:：=]\s*([^\s，,;；]+)',text,re.I); pwd=p.group(1) if p else os.environ.get('NEO4J_PASSWORD','')
with GraphDatabase.driver(bolt,auth=(user,pwd)) as driver:
  with driver.session(database='neo4j') as s:
    rows=s.run("""MATCH (a:Exam) WHERE coalesce(a.status,'active') <> 'deprecated' AND coalesce(a.disease_code,'') STARTS WITH 'DIS-CARD-CAD' RETURN a.code as code, coalesce(a.display_name,a.preferred_name,a.name,'') as name, coalesce(a.disease_code,'') as disease_code, a.aliases as aliases ORDER BY disease_code,name LIMIT 100""")
    for r in rows: print(dict(r))
