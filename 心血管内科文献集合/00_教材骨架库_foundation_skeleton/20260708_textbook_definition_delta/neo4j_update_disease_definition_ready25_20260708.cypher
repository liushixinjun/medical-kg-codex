// 教材骨架 Disease.definition 更新脚本
// 用法：读取 delta_disease_definition_update_ready25_20260708.jsonl 中每行 set 对象为 rows 参数。
// 本脚本只更新既有 Disease 节点，不创建新疾病。
UNWIND $rows AS row
MATCH (d:Disease {code: row.disease_code})
SET d.definition = row.definition,
    d.description = CASE WHEN row.description IS NOT NULL AND trim(row.description) <> '' THEN row.description ELSE d.description END,
    d.definition_source_type = row.definition_source_type,
    d.definition_source_name = row.definition_source_name,
    d.definition_source_section_path = row.definition_source_section_path,
    d.definition_docx_paragraph_start = row.definition_docx_paragraph_start,
    d.definition_docx_paragraph_end = row.definition_docx_paragraph_end,
    d.definition_pdf_page_start = row.definition_pdf_page_start,
    d.definition_pdf_page_end = row.definition_pdf_page_end,
    d.definition_skeleton_slot = row.definition_skeleton_slot,
    d.definition_knowledge_layer = row.definition_knowledge_layer,
    d.textbook_anchor_status = row.textbook_anchor_status,
    d.textbook_anchor_generated_at = row.textbook_anchor_generated_at
RETURN count(d) AS updated_count;
