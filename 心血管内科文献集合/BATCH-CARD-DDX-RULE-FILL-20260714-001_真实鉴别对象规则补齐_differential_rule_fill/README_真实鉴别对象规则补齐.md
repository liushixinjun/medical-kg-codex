# 真实鉴别对象规则补齐批次

- 批次：BATCH-CARD-DDX-RULE-FILL-20260714-001
- 执行时间：2026-07-14 09:58:05
- 处理范围：历史治理后仍缺少明细的真实 DifferentialDiagnosis 对象
- 旧自动候选：52 条，因证据泛化/OCR噪声污染，本轮不入库
- 精修规则：14 条
- 阻断：0 条
- 写库策略：DifferentialDiagnosis -> has_differential_point -> ClinicalRule -> supported_by_evidence -> Evidence

## 数据库复核

```json
{
  "raw_differential_without_detail": 0,
  "batch_rules_without_evidence": 0,
  "batch_rules_with_wrong_type": 0,
  "label_entity_mismatch": 0,
  "differentiates_from_to_non_ddx": 0,
  "non_kgnode_nodes": 0,
  "empty_shell_clinical_rules": 676,
  "formal_cdss_hard_gate_pass": false,
  "batch_rule_samples": [
    {
      "ddx": "冠心病",
      "rule": "心肌病与冠心病鉴别规则",
      "rule_text": "诊断心肌病时，若心肌结构或功能异常可由冠状动脉粥样硬化/心肌缺血充分解释，应优先考虑冠心病或缺血性心肌病；若异常不能由缺血解释，才支持原发或特定类型心肌病。需注意冠心病可与心肌病共存，一种疾病存在不排除另一种疾病。",
      "evidence_codes": [
        "EVD-EA12FDB1586C16E92E2D-RCM"
      ]
    },
    {
      "ddx": "冠状动脉痉挛",
      "rule": "冠状动脉痉挛与固定冠脉狭窄鉴别规则",
      "rule_text": "出现心肌缺血症状但冠脉造影/CTA未提示固定心外膜冠脉狭窄时，应考虑冠状动脉痉挛或微血管病变；其与稳定粥样硬化固定狭窄导致的冠心病表型不同，需结合发作特点、动态心电图、冠脉功能评估和抗痉挛治疗反应鉴别。",
      "evidence_codes": [
        "EVD-TB-084D561AEA10CE9D4B47-CCS"
      ]
    },
    {
      "ddx": "嗜铬细胞瘤",
      "rule": "STEMI与嗜铬细胞瘤鉴别规则",
      "rule_text": "STEMI疑似场景如伴头痛、心悸、出汗、血压剧烈波动或收缩压显著升高后骤降，应鉴别嗜铬细胞瘤；嗜铬细胞瘤可因儿茶酚胺大量释放导致冠脉弥漫性收缩、ST段改变和心肌坏死标志物升高，但冠脉常无狭窄病变，需结合腹部影像及血/尿儿茶酚胺和代谢产物。",
      "evidence_codes": [
        "EVD-TB-E70DF8CB7C3CA076A861-AMI"
      ]
    },
    {
      "ddx": "心房颤动",
      "rule": "室上速/房扑与心房颤动鉴别规则",
      "rule_text": "快速性心律失常患者需鉴别心房颤动：房颤心电图表现为P波消失或无明确可重复P波，常以f波代之，且无房室传导阻滞时RR间期绝对不规则；典型房扑则为规律锯齿状F波，房室传导比例可导致心室率规则或不规则。",
      "evidence_codes": [
        "EVD-B9CAB7EC30CAB04B08EC-AFL",
        "EVD-31BFE9E10B3D29C7915D-AF"
      ]
    },
    {
      "ddx": "心绞痛",
      "rule": "STEMI与心绞痛鉴别规则",
      "rule_text": "胸痛患者需区分心绞痛与AMI/STEMI：心绞痛多为暂时性心肌缺血而无坏死，疼痛持续较短且硝酸甘油常可缓解；AMI/STEMI为持续严重缺血导致心肌坏死，疼痛更持久，常伴心肌坏死标志物升高和特征性/动态性心电图变化。",
      "evidence_codes": [
        "EVD-CARD-TEXTBOOK-21604E90EA3EDFCC"
      ]
    },
    {
      "ddx": "心肌炎",
      "rule": "STEMI与急性心包炎/心肌炎鉴别规则",
      "rule_text": "疑似STEMI如表现为较剧烈且持久的心前区疼痛，同时伴发热，疼痛随呼吸或咳嗽加重，早期可闻及心包摩擦音，心电图表现为除aVR外多导联ST段弓背向下抬高、T波倒置且无异常Q波时，应鉴别急性心包炎/心肌炎。",
      "evidence_codes": [
        "EVD-CARD-TEXTBOOK-21604E90EA3EDFCC"
      ]
    },
    {
      "ddx": "急性肺动脉栓塞",
      "rule": "STEMI与急性肺动脉栓塞鉴别规则",
      "rule_text": "胸痛、呼吸困难或休克患者需鉴别STEMI与急性肺动脉栓塞；若伴咯血、晕厥、发绀、P2亢进、颈静脉充盈、右心负荷急性增加、低氧血症，且肺动脉CTA或肺通气/灌注检查异常，应优先考虑肺栓塞；D-二聚体在AMI和肺栓塞中均可升高，不能单独作为鉴别依据。",
      "evidence_codes": [
        "EVD-CARD-TEXTBOOK-21604E90EA3EDFCC"
      ]
    },
    {
      "ddx": "急腹症",
      "rule": "STEMI与急腹症鉴别规则",
      "rule_text": "STEMI可出现上腹痛、恶心呕吐而误诊为急腹症；当存在上腹痛或休克表现时，应结合病史、体格检查、心电图、血清心肌酶和肌钙蛋白动态检测，鉴别急性胰腺炎、消化性溃疡穿孔、急性胆囊炎、胆石症等急腹症。",
      "evidence_codes": [
        "EVD-CARD-TEXTBOOK-21604E90EA3EDFCC"
      ]
    },
    {
      "ddx": "房性早搏",
      "rule": "房性早搏与房室折返性心动过速触发鉴别规则",
      "rule_text": "房性早搏可作为房室折返性心动过速的触发因素：当房性期前收缩下传时旁道仍处不应期而房室结已恢复兴奋性，可经房室结前传、旁道逆传形成折返环。临床展示时应将房性早搏作为触发/鉴别线索，不应误作持续性室上速本体。",
      "evidence_codes": [
        "EVD-DA73254797A17F116872-AVRT"
      ]
    },
    {
      "ddx": "瓣膜性心脏病",
      "rule": "心肌病与瓣膜性心脏病鉴别规则",
      "rule_text": "心肌肥厚、扩大或收缩/舒张功能异常患者，应评估瓣膜狭窄或关闭不全等异常负荷是否足以解释心肌改变；若瓣膜性心脏病足以解释结构功能异常，则不应直接归因于原发心肌病；若两者共存，应分别记录并判断主导病因。",
      "evidence_codes": [
        "EVD-EA12FDB1586C16E92E2D-RCM"
      ]
    },
    {
      "ddx": "癫痫",
      "rule": "心脏骤停/室颤与癫痫样抽搐鉴别规则",
      "rule_text": "心脏骤停或恶性室性心律失常可因脑血流骤降导致意识突然丧失，并伴局部或全身性抽搐，临床不能仅凭抽搐表现判断为癫痫。应同步核查脉搏、呼吸、皮肤颜色、瞳孔、心电监测和复苏反应，优先排除心源性意识丧失。",
      "evidence_codes": [
        "EVD-CARD-DEEP-066B33C52F2F1B"
      ]
    },
    {
      "ddx": "窦性心动过速",
      "rule": "室上速与窦性心动过速鉴别规则",
      "rule_text": "疑似室上性心动过速时需鉴别窦性心动过速：窦速定义为窦性心率>100次/分，I、II、aVF导联P波直立，V1导联双向或倒置；不恰当窦速为排除性诊断，需排除体位性心动过速综合征、窦房结折返性心动过速、局灶性房速以及发热、贫血、疼痛、甲亢等继发因素。",
      "evidence_codes": [
        "EVD-CF7BB456375EF4CC379E-AVNRT"
      ]
    },
    {
      "ddx": "预激综合征伴心房颤动",
      "rule": "预激伴房颤与普通房颤/室颤风险鉴别规则",
      "rule_text": "宽QRS、极不规则快速心律或已知预激患者出现房颤/房扑时，应识别预激伴房颤这一高危情境；其治疗不同于普通房颤，首选电复律或伊布利特/普罗帕酮，避免β受体拮抗剂、维拉帕米、地尔硫䓬、洋地黄类药物和胺碘酮，以免抑制房室结传导、加剧旁道下传并诱发室颤。",
      "evidence_codes": [
        "EVD-FA19DDD6812364E50C63-VF",
        "EVD-3C8217C70100704827CC-VF"
      ]
    },
    {
      "ddx": "高血压性心脏病",
      "rule":
```

## 关键文件

- differential_rule_refined_to_apply.jsonl：正式入库规则
- differential_rule_refined_to_apply.csv：人工可读清单
- differential_rule_auto52_rejection_summary.json：旧自动候选拒绝说明
- neo4j_ddx_rule_fill_summary.json：写库摘要
- neo4j_postcheck_summary.json：写库后复核


## 2026-07-14 10:02 最终复核

- 14 个真实鉴别对象全部补齐 `has_differential_point -> ClinicalRule`。
- 本批规则无证据：0。
- `DifferentialDiagnosis` 无明细：0。
- 旧 ClinicalRule 字段兼容：496 条 `rule_logic` 回填 `rule_text`。
- 历史短句型规则隔离：180 条，标记为 `blocked`，不进入正式 CDSS。
- 正式 CDSS 硬闸门：通过。
