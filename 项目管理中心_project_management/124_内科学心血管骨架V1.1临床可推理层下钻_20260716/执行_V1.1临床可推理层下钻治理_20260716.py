from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

from neo4j import GraphDatabase


ROOT = Path(r"E:\BigMouse\0.CDSS文献诊疗指南材料PDF\AI专科知识图谱生成")
OUT = ROOT / "项目管理中心_project_management" / "124_内科学心血管骨架V1.1临床可推理层下钻_20260716"
CONN = ROOT / "图谱数据库链接.txt"
BOOK = "《内科学（第10版）》"
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_connection() -> tuple[str, str, str]:
    raw = CONN.read_bytes()
    texts: list[str] = []
    for enc in ("utf-8-sig", "utf-8", "gbk", "cp936"):
        try:
            texts.append(raw.decode(enc, errors="ignore"))
        except Exception:
            pass
    joined = "\n".join(texts)
    uri_match = re.search(r"bolt://[0-9A-Za-z\.:_-]+", joined)
    uri = uri_match.group(0) if uri_match else "bolt://192.168.3.27:7687"
    user = "neo4j" if "neo4j" in joined.lower() else os.environ.get("NEO4J_USERNAME", "neo4j")
    candidates: list[str] = []
    if os.environ.get("NEO4J_PASSWORD"):
        candidates.append(os.environ["NEO4J_PASSWORD"])
    for text in texts:
        for line in text.splitlines():
            if "@" in line and "http" not in line.lower() and "bolt" not in line.lower():
                candidates.extend(
                    m.group(0)
                    for m in re.finditer(r"[A-Za-z0-9._%+\-#$!]+@[A-Za-z0-9._%+\-#$!]+", line)
                )
    seen: list[str] = []
    for x in candidates:
        if x and x not in seen:
            seen.append(x)
    last = None
    for pwd in seen:
        try:
            d = GraphDatabase.driver(uri, auth=(user, pwd))
            d.verify_connectivity()
            d.close()
            return uri, user, pwd
        except Exception as exc:
            last = exc
    raise RuntimeError(f"Neo4j认证失败，候选数={len(seen)}，最后错误={type(last).__name__ if last else 'None'}")


EXAM_INDICATORS: dict[str, list[str]] = {
    "心电图": ["ST段抬高", "ST段压低", "T波倒置", "病理性Q波", "QRS波时限", "PR间期", "QT间期", "心律"],
    "12导联心电图": ["ST段抬高", "ST段压低", "T波倒置", "病理性Q波", "QRS波时限", "PR间期", "QT间期", "心律"],
    "动态心电图": ["心律失常发作频率", "最长RR间期", "室性早搏负荷", "房颤负荷", "心率变异性"],
    "Holter": ["心律失常发作频率", "最长RR间期", "室性早搏负荷", "房颤负荷", "心率变异性"],
    "心电图及长程心电监测": ["心律失常发作频率", "最长RR间期", "室性早搏负荷", "房颤负荷", "心率变异性"],
    "事件记录仪": ["症状相关心律事件", "阵发性心律失常记录"],
    "植入式心电监测": ["长程心律事件", "隐匿性房颤事件", "症状相关心律事件"],
    "食管心房调搏": ["诱发性室上性心动过速", "房室结传导特征", "旁路传导证据"],
    "电生理检查": ["诱发性心动过速", "房室传导时间", "旁路定位", "室性心律失常诱发"],
    "心脏电生理检查": ["诱发性心动过速", "房室传导时间", "旁路定位", "室性心律失常诱发"],
    "超声心动图": ["左室射血分数", "室壁运动异常", "室壁厚度", "瓣口面积", "跨瓣压差", "反流程度", "肺动脉压力估测", "心包积液"],
    "经食管超声心动图": ["左心耳血栓", "瓣膜赘生物", "瓣膜反流程度", "房间隔缺损分流", "心内血栓"],
    "冠状动脉造影": ["冠状动脉狭窄程度", "冠状动脉闭塞", "TIMI血流分级", "罪犯血管", "侧支循环"],
    "冠状动脉CTA": ["冠状动脉狭窄程度", "冠状动脉钙化", "冠状动脉斑块性质", "冠状动脉起源异常"],
    "冠状动脉CT血管成像": ["冠状动脉狭窄程度", "冠状动脉钙化", "冠状动脉斑块性质", "冠状动脉起源异常"],
    "CT肺动脉造影": ["肺动脉充盈缺损", "肺动脉栓塞部位", "右心负荷征象"],
    "肺通气/灌注显像": ["通气灌注不匹配", "肺灌注缺损"],
    "血管超声": ["血管狭窄程度", "血流速度", "血栓形成", "斑块性质"],
    "主动脉CTA": ["主动脉内膜片", "真假腔", "主动脉夹层范围", "主动脉瘤直径"],
    "CT检查": ["结构异常", "钙化", "血栓", "占位或积液"],
    "CT": ["结构异常", "钙化", "血栓", "占位或积液"],
    "计算机断层扫描": ["结构异常", "钙化", "血栓", "占位或积液"],
    "胸部X线检查": ["心影增大", "肺淤血", "肺水肿", "胸腔积液"],
    "X线": ["心影增大", "肺淤血", "肺水肿", "胸腔积液"],
    "胸部影像学检查": ["心影增大", "肺淤血", "肺水肿", "胸腔积液"],
    "磁共振成像": ["延迟钆增强", "心肌水肿", "心室容积", "左室射血分数", "心肌纤维化"],
    "CMR": ["延迟钆增强", "心肌水肿", "心室容积", "左室射血分数", "心肌纤维化"],
    "心脏CT": ["心脏结构异常", "冠状动脉钙化", "心腔血栓", "心包异常"],
    "血管内超声": ["斑块负荷", "最小管腔面积", "支架贴壁", "血管夹层"],
    "IVUS": ["斑块负荷", "最小管腔面积", "支架贴壁", "血管夹层"],
    "光学相干断层扫描": ["纤维帽厚度", "斑块破裂", "支架贴壁", "血栓影像"],
    "OCT": ["纤维帽厚度", "斑块破裂", "支架贴壁", "血栓影像"],
    "运动负荷试验": ["运动诱发ST段压低", "运动诱发心绞痛", "运动耐量", "血压反应", "运动诱发心律失常"],
    "运动试验": ["运动诱发ST段压低", "运动诱发心绞痛", "运动耐量", "血压反应", "运动诱发心律失常"],
    "诊室血压测量": ["收缩压", "舒张压", "脉压"],
    "家庭血压监测": ["家庭平均收缩压", "家庭平均舒张压", "晨峰血压"],
    "24小时动态血压监测": ["24小时平均血压", "白昼平均血压", "夜间平均血压", "夜间血压下降率"],
    "眼底检查": ["高血压视网膜病变", "视乳头水肿", "眼底出血"],
    "肾动脉超声": ["肾动脉狭窄", "肾动脉血流速度", "阻力指数"],
    "肾上腺CT": ["肾上腺占位", "肾上腺增生"],
    "肾上腺静脉采血": ["醛固酮皮质醇比值", "侧别化指数"],
    "睡眠呼吸监测": ["呼吸暂停低通气指数", "夜间低氧饱和度", "最低血氧饱和度"],
    "阿托品试验": ["心率反应", "窦房结功能反应"],
    "正电子发射断层显像": ["心肌代谢", "心肌存活性"],
    "单光子发射计算机断层显像": ["心肌灌注缺损", "室壁运动", "左室射血分数"],
    "心脏导管检查": ["心腔压力", "肺动脉压力", "心排血量", "血氧饱和度阶差"],
    "心导管检查": ["心腔压力", "肺动脉压力", "心排血量", "血氧饱和度阶差"],
    "心内膜心肌活检": ["心肌炎症浸润", "淀粉样沉积", "心肌纤维化", "病原体证据"],
    "基因检测": ["致病变异", "可能致病变异", "家族遗传证据"],
}

LAB_RECLASSIFY = {
    "利钠肽": ["BNP", "NT-proBNP"],
    "血常规与血红蛋白": ["白细胞计数", "血红蛋白", "血小板计数"],
    "肾功能与电解质": ["血肌酐", "估算肾小球滤过率", "血钾", "血钠"],
    "CKD高血压肾功能和尿蛋白评估": ["估算肾小球滤过率", "尿白蛋白肌酐比值", "血肌酐"],
}

PROCEDURE_STANDARD = {
    "PCI": ("经皮冠状动脉介入治疗", ["PCI", "经皮冠状动脉介入术", "PTCA"]),
    "TAVI": ("经导管主动脉瓣植入术", ["TAVI", "TAVR", "经导管主动脉瓣置换术"]),
    "TAVR": ("经导管主动脉瓣置换术", ["TAVR", "TAVI", "经导管主动脉瓣植入术"]),
    "TEER": ("经导管缘对缘修复术", ["TEER", "二尖瓣经导管缘对缘修复"]),
    "PBPV": ("经皮球囊肺动脉瓣成形术", ["PBPV"]),
    "PBMV": ("经皮球囊二尖瓣成形术", ["PBMV"]),
}

MED_ALIASES = {
    "钠-葡萄糖共转运蛋白2抑制剂": ["SGLT2抑制剂", "SGLT2i", "SGLT-2抑制剂"],
    "选择性5-羟色胺再摄取抑制剂": ["SSRI", "SSRIs"],
}

RISK_COMPONENTS = {
    "GRACE评分": ["年龄", "充血性心力衰竭史", "心肌梗死史", "静息心率", "收缩压", "血肌酐", "ST段偏移", "心肌损伤标志物升高", "是否行血运重建"],
    "TIMI评分": ["年龄", "冠心病危险因素", "已知冠状动脉狭窄", "近期阿司匹林使用", "严重心绞痛发作", "ST段偏移", "心肌损伤标志物升高"],
    "CHA2DS2-VASc评分": ["充血性心力衰竭", "高血压", "年龄≥75岁", "糖尿病", "卒中或短暂性脑缺血发作", "血管疾病", "年龄65-74岁", "女性"],
    "HAS-BLED评分": ["高血压", "肝肾功能异常", "卒中史", "出血史或出血倾向", "INR不稳定", "年龄>65岁", "药物或饮酒"],
    "SAMe-TT2R2评分": ["女性", "年龄<60岁", "合并疾病", "治疗药物相互作用", "吸烟", "非白人种族"],
    "EHRA症状分级": ["无症状", "轻度症状", "重度症状", "致残性症状"],
    "Killip分级": ["Ⅰ级无明显心力衰竭", "Ⅱ级左心衰竭肺部啰音小于50%肺野", "Ⅲ级急性肺水肿", "Ⅳ级心源性休克"],
}

CONTRA_LINKS = {
    "活动性出血": ["抗凝治疗", "溶栓治疗", "抗凝药物", "直接口服抗凝药"],
    "中重度二尖瓣狭窄": ["直接口服抗凝药", "利伐沙班", "阿哌沙班", "达比加群", "达比加群酯", "依度沙班"],
    "机械瓣膜": ["直接口服抗凝药", "利伐沙班", "阿哌沙班", "达比加群", "达比加群酯", "依度沙班"],
    "病态窦房结综合征": ["β受体拮抗剂", "地尔硫卓", "维拉帕米"],
    "二度或三度房室传导阻滞": ["β受体拮抗剂", "地尔硫卓", "维拉帕米"],
    "严重低血压": ["硝酸酯类药物", "β受体拮抗剂", "地尔硫卓", "维拉帕米"],
    "支气管哮喘": ["β受体拮抗剂"],
    "预激合并房颤": ["地尔硫卓", "维拉帕米", "洋地黄类药物", "β受体拮抗剂"],
    "妊娠": ["华法林", "ACEI", "ARB", "ARNI"],
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    uri, user, pwd = parse_connection()
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    summary: dict[str, object] = {
        "batch_id": "20260716_内科学心血管骨架V1.1临床可推理层下钻治理",
        "executed_at": NOW,
        "password_printed": False,
        "exam_indicator_links": [],
        "lab_reclassified": [],
        "procedure_standardized": [],
        "medication_alias_fixed": [],
        "risk_components_linked": [],
        "contraindication_links": [],
        "treatment_plans_marked": [],
        "generic_risks_marked": 0,
        "generic_exams_marked": 0,
    }

    with driver.session(database="neo4j") as s:
        # 1. 检查项目 → 检查指标
        for exam_name, indicators in EXAM_INDICATORS.items():
            rows = s.run(
                """
                MATCH (e:KGNode {entityType:'Exam', name:$exam_name})
                RETURN e.code AS code, e.name AS name
                """,
                exam_name=exam_name,
            ).data()
            for row in rows:
                for indicator in indicators:
                    ind_code = "IND-" + re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", f"{row['code']}-{indicator}")[:90]
                    rec = s.run(
                        """
                        MATCH (e:KGNode {code:$exam_code})
                        MERGE (i:KGNode:ExamIndicator {entityType:'ExamIndicator', code:$ind_code})
                        SET i.name=$indicator,
                            i.display_name=$indicator,
                            i.preferred_name=$indicator,
                            i.source_name=coalesce(i.source_name, $book),
                            i.source_type=coalesce(i.source_type, 'authoritative_textbook'),
                            i.source_authority=coalesce(i.source_authority, 'authoritative_textbook'),
                            i.knowledge_layer=coalesce(i.knowledge_layer, 'textbook_inference_v1_1'),
                            i.skeleton_slot='exam_indicator',
                            i.skeleton_slot_status='v1_1_inference_indicator',
                            i.batch_id='20260716_内科学心血管骨架V1.1临床可推理层下钻治理',
                            i.created_at=coalesce(i.created_at, $now),
                            i.updated_at=$now
                        MERGE (e)-[r:exam_has_indicator]->(i)
                        SET r.source='textbook_inference_v1_1',
                            r.updated_at=$now
                        SET e.inference_status='has_indicator',
                            e.updated_at=$now
                        RETURN e.code AS exam_code, i.name AS indicator
                        """,
                        exam_code=row["code"],
                        ind_code=ind_code,
                        indicator=indicator,
                        book=BOOK,
                        now=NOW,
                    ).single()
                    if rec:
                        summary["exam_indicator_links"].append(dict(rec))

        # 2. 被误放在检查里的检验项目，改回 LabTest 并补检验指标。
        for lab_name, indicators in LAB_RECLASSIFY.items():
            rows = s.run(
                """
                MATCH (n:KGNode {name:$name})
                WHERE n.entityType='Exam'
                SET n.entityType='LabTest',
                    n.type_label='检验项目',
                    n.inference_status='has_lab_indicator',
                    n.updated_at=$now
                REMOVE n:Exam
                SET n:LabTest
                RETURN n.code AS code, n.name AS name
                """,
                name=lab_name,
                now=NOW,
            ).data()
            for row in rows:
                for indicator in indicators:
                    ind_code = "LABIND-" + re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", f"{row['code']}-{indicator}")[:90]
                    s.run(
                        """
                        MATCH (l:KGNode {code:$lab_code})
                        MERGE (i:KGNode:ExamIndicator {entityType:'ExamIndicator', code:$ind_code})
                        SET i.name=$indicator,
                            i.display_name=$indicator,
                            i.preferred_name=$indicator,
                            i.source_name=coalesce(i.source_name, $book),
                            i.source_type=coalesce(i.source_type, 'authoritative_textbook'),
                            i.source_authority=coalesce(i.source_authority, 'authoritative_textbook'),
                            i.knowledge_layer=coalesce(i.knowledge_layer, 'textbook_inference_v1_1'),
                            i.skeleton_slot='lab_indicator',
                            i.skeleton_slot_status='v1_1_inference_indicator',
                            i.batch_id='20260716_内科学心血管骨架V1.1临床可推理层下钻治理',
                            i.created_at=coalesce(i.created_at, $now),
                            i.updated_at=$now
                        MERGE (l)-[r:lab_test_has_indicator]->(i)
                        SET r.source='textbook_inference_v1_1',
                            r.updated_at=$now
                        """,
                        lab_code=row["code"],
                        ind_code=ind_code,
                        indicator=indicator,
                        book=BOOK,
                        now=NOW,
                    )
                summary["lab_reclassified"].append({"code": row["code"], "name": row["name"], "indicators": indicators})

        # 3. 操作/手术简称改为中文全称，简称进入别名。
        for old_name, (full_name, aliases) in PROCEDURE_STANDARD.items():
            rows = s.run(
                """
                MATCH (p:KGNode {entityType:'Procedure', name:$old_name})
                SET p.name=$full_name,
                    p.display_name=$full_name,
                    p.preferred_name=$full_name,
                    p.aliases=apoc.coll.toSet(coalesce(p.aliases, []) + $aliases),
                    p.inference_status='standard_name_with_alias',
                    p.updated_at=$now
                RETURN p.code AS code, p.name AS name, p.aliases AS aliases
                """,
                old_name=old_name,
                full_name=full_name,
                aliases=aliases,
                now=NOW,
            ).data()
            summary["procedure_standardized"].extend(rows)

        # 4. 药物类别补别名。
        for name, aliases in MED_ALIASES.items():
            rows = s.run(
                """
                MATCH (m:KGNode {entityType:'Medication', name:$name})
                SET m.aliases=apoc.coll.toSet(coalesce(m.aliases, []) + $aliases),
                    m.inference_status='standard_name_with_alias',
                    m.updated_at=$now
                RETURN m.code AS code, m.name AS name, m.aliases AS aliases
                """,
                name=name,
                aliases=aliases,
                now=NOW,
            ).data()
            summary["medication_alias_fixed"].extend(rows)

        # 5. 风险分层量表补组件。
        for risk_name, components in RISK_COMPONENTS.items():
            risk_rows = s.run(
                """
                MATCH (r:KGNode {entityType:'RiskStratification', name:$name})
                RETURN r.code AS code, r.name AS name
                """,
                name=risk_name,
            ).data()
            for risk in risk_rows:
                for comp in components:
                    comp_code = "RISKCOMP-" + re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", f"{risk['code']}-{comp}")[:90]
                    rec = s.run(
                        """
                        MATCH (r:KGNode {code:$risk_code})
                        MERGE (c:KGNode:RiskFactor {entityType:'RiskFactor', code:$comp_code})
                        SET c.name=$component,
                            c.display_name=$component,
                            c.preferred_name=$component,
                            c.source_name=coalesce(c.source_name, $book),
                            c.source_type=coalesce(c.source_type, 'authoritative_textbook'),
                            c.source_authority=coalesce(c.source_authority, 'authoritative_textbook'),
                            c.knowledge_layer=coalesce(c.knowledge_layer, 'textbook_inference_v1_1'),
                            c.skeleton_slot='risk_component',
                            c.skeleton_slot_status='v1_1_inference_component',
                            c.batch_id='20260716_内科学心血管骨架V1.1临床可推理层下钻治理',
                            c.created_at=coalesce(c.created_at, $now),
                            c.updated_at=$now
                        MERGE (r)-[rel:has_risk_factor]->(c)
                        SET rel.source='textbook_inference_v1_1',
                            rel.updated_at=$now
                        SET r.inference_status='has_risk_components',
                            r.updated_at=$now
                        RETURN r.name AS risk, c.name AS component
                        """,
                        risk_code=risk["code"],
                        comp_code=comp_code,
                        component=comp,
                        book=BOOK,
                        now=NOW,
                    ).single()
                    if rec:
                        summary["risk_components_linked"].append(dict(rec))

        # 6. 禁忌/排除条件连接到可阻断动作。
        for contra_name, target_names in CONTRA_LINKS.items():
            for target_name in target_names:
                rows = s.run(
                    """
                    MATCH (c:KGNode {entityType:'Contraindication', name:$contra_name})
                    MATCH (a:KGNode)
                    WHERE a.name=$target_name AND a.entityType IN ['Medication','TreatmentPlan','Procedure']
                    MERGE (c)-[r:blocks_action]->(a)
                    SET r.source='textbook_inference_v1_1',
                        r.logic='禁忌或排除条件阻断该动作进入正式推荐',
                        r.updated_at=$now
                    SET c.inference_status='blocks_action',
                        c.updated_at=$now
                    RETURN c.name AS contraindication, a.entityType AS target_type, a.name AS target, a.code AS target_code
                    """,
                    contra_name=contra_name,
                    target_name=target_name,
                    now=NOW,
                ).data()
                summary["contraindication_links"].extend(rows)

        # 7. 宽泛治疗方案不硬造动作链，明确标为知识浏览；已有推荐陈述仍走正式推荐链。
        rows = s.run(
            """
            MATCH (d:KGNode {entityType:'Disease'})-[:has_treatment_plan]->(tp:KGNode {entityType:'TreatmentPlan'})
            WHERE NOT (tp)-[:has_recommended_action]->(:KGNode)
              AND NOT (tp)-[:recommends_action]->(:KGNode)
              AND NOT (tp)-[:includes_medication]->(:KGNode)
              AND NOT (tp)-[:includes_procedure]->(:KGNode)
            SET tp.formal_cdss_ready='no',
                tp.inference_status=CASE
                  WHEN tp.name CONTAINS '治疗方案' OR tp.name CONTAINS '治疗总原则' THEN 'broad_plan_knowledge_browse_only'
                  WHEN size(tp.name) > 45 THEN 'misclassified_text_sentence_needs_manual_review'
                  ELSE 'textbook_plan_without_action_detail'
                END,
                tp.cdss_usage_scope='knowledge_browse_only',
                tp.updated_at=$now
            RETURN d.name AS disease, tp.code AS code, tp.name AS name, tp.inference_status AS status
            """,
            now=NOW,
        ).data()
        summary["treatment_plans_marked"].extend(rows)

        # 8. 其余泛风险节点标为框架节点，避免被误当完整评分。
        res = s.run(
            """
            MATCH (r:KGNode {entityType:'RiskStratification'})
            WHERE NOT (r)-[:has_risk_factor]->(:KGNode)
              AND NOT (r)-[:has_threshold_rule]->(:KGNode)
            SET r.inference_status='risk_framework_only_wait_guideline_or_textbook_detail',
                r.formal_cdss_ready='no',
                r.cdss_usage_scope='knowledge_browse_only',
                r.updated_at=$now
            RETURN count(r) AS c
            """,
            now=NOW,
        ).single()
        summary["generic_risks_marked"] = res["c"] if res else 0

        # 9. 没有明确指标的检查项目标为“仅检查项目”，不再误入正式推理。
        res = s.run(
            """
            MATCH (e:KGNode {entityType:'Exam'})
            WHERE NOT (e)-[:exam_has_indicator]->(:KGNode)
            SET e.inference_status='exam_item_only_wait_indicator_detail',
                e.formal_cdss_ready='no',
                e.cdss_usage_scope='knowledge_browse_only',
                e.updated_at=$now
            RETURN count(e) AS c
            """,
            now=NOW,
        ).single()
        summary["generic_exams_marked"] = res["c"] if res else 0

        # 10. 中文全称标准化后可能形成重复，做同类型同名归并。
        duplicate_rows = s.run(
            """
            MATCH (n:KGNode)
            WHERE n.entityType IS NOT NULL AND n.name IS NOT NULL AND coalesce(n.status,'active') <> 'deleted'
            WITH n.entityType AS type, n.name AS name, count(*) AS c
            WHERE c > 1 AND type IN ['Procedure','Medication','Exam','LabTest','ExamIndicator','RiskFactor']
            RETURN type, name
            """
        ).data()
        merged = []
        for row in duplicate_rows:
            rec = s.run(
                """
                MATCH (n:KGNode {entityType:$type, name:$name})
                WHERE coalesce(n.status,'active') <> 'deleted'
                WITH n, COUNT { (n)--() } AS rel_count
                ORDER BY rel_count DESC, coalesce(n.updated_at,'') DESC
                WITH collect(n) AS nodes
                WITH nodes[0] AS keep, nodes AS nodes
                CALL apoc.refactor.mergeNodes(nodes, {properties:'combine', mergeRels:true, produceSelfRel:false}) YIELD node
                SET node.code=keep.code,
                    node.name=$name,
                    node.display_name=coalesce(node.display_name,$name),
                    node.preferred_name=coalesce(node.preferred_name,$name),
                    node.merge_status='v1_1_inference_standardization_merge',
                    node.updated_at=$now
                RETURN node.entityType AS type, node.name AS name, node.code AS code
                """,
                type=row["type"],
                name=row["name"],
                now=NOW,
            ).single()
            if rec:
                merged.append(dict(rec))
        summary["standardization_duplicate_merged"] = merged

    driver.close()
    (OUT / "02_V1.1临床可推理层治理执行结果.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "exam_indicator_links": len(summary["exam_indicator_links"]),
                "lab_reclassified": len(summary["lab_reclassified"]),
                "procedure_standardized": len(summary["procedure_standardized"]),
                "medication_alias_fixed": len(summary["medication_alias_fixed"]),
                "risk_components_linked": len(summary["risk_components_linked"]),
                "contraindication_links": len(summary["contraindication_links"]),
                "treatment_plans_marked": len(summary["treatment_plans_marked"]),
                "generic_risks_marked": summary["generic_risks_marked"],
                "generic_exams_marked": summary["generic_exams_marked"],
                "standardization_duplicate_merged": len(summary["standardization_duplicate_merged"]),
                "output": str(OUT / "02_V1.1临床可推理层治理执行结果.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
