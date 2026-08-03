// P4 正式推荐主证据补链预览
// 说明：此文件只作为人工审核后的写库脚本草案，生成时未执行。
MATCH (rec:KGNode {entityType:'RecommendationStatement', code:'REC-CDSS-VASCD-SCD-ARREST-01-01-DIAG'})
MATCH (ev:KGNode {entityType:'Evidence', code:'EVD-A41D5F17B34CAE07E13C-CPVT'})
MERGE (rec)-[:supported_by_evidence]->(ev)
SET rec.primary_evidence_code = 'EVD-A41D5F17B34CAE07E13C-CPVT';
MATCH (rec:KGNode {entityType:'RecommendationStatement', code:'REC-CDSS-VASCD-SCD-ARREST-01-01-DIAG'})
MATCH (gl:KGNode {entityType:'Guideline', code:'SRC-DOC-00005AB23BE6D130'})
MERGE (rec)-[:uses_primary_guideline]->(gl)
SET rec.primary_guideline_code = 'SRC-DOC-00005AB23BE6D130';
MATCH (rec:KGNode {entityType:'RecommendationStatement', code:'REC-CDSS-VASCD-SCD-ARREST-04-01-FOLLOW'})
MATCH (ev:KGNode {entityType:'Evidence', code:'EVD-A215F735B3016E6E5D52-SQTS'})
MERGE (rec)-[:supported_by_evidence]->(ev)
SET rec.primary_evidence_code = 'EVD-A215F735B3016E6E5D52-SQTS';
MATCH (rec:KGNode {entityType:'RecommendationStatement', code:'REC-CDSS-VASCD-SCD-ARREST-04-01-FOLLOW'})
MATCH (gl:KGNode {entityType:'Guideline', code:'SRC-DOC-00005AB23BE6D130'})
MERGE (rec)-[:uses_primary_guideline]->(gl)
SET rec.primary_guideline_code = 'SRC-DOC-00005AB23BE6D130';
MATCH (rec:KGNode {entityType:'RecommendationStatement', code:'REC-CDSS-VASCD-SCD-SUDDEN-01-01-DIAG'})
MATCH (ev:KGNode {entityType:'Evidence', code:'EVD-22F1D1DDC36B0B600F0B-NSVT'})
MERGE (rec)-[:supported_by_evidence]->(ev)
SET rec.primary_evidence_code = 'EVD-22F1D1DDC36B0B600F0B-NSVT';
MATCH (rec:KGNode {entityType:'RecommendationStatement', code:'REC-CDSS-VASCD-SCD-SUDDEN-01-01-DIAG'})
MATCH (gl:KGNode {entityType:'Guideline', code:'SRC-DOC-00005AB23BE6D130'})
MERGE (rec)-[:uses_primary_guideline]->(gl)
SET rec.primary_guideline_code = 'SRC-DOC-00005AB23BE6D130';
MATCH (rec:KGNode {entityType:'RecommendationStatement', code:'REC-CDSS-VASCD-SCD-SUDDEN-04-01-FOLLOW'})
MATCH (ev:KGNode {entityType:'Evidence', code:'EVD-9C098C7E7DD357B920F1-SUDDEN'})
MERGE (rec)-[:supported_by_evidence]->(ev)
SET rec.primary_evidence_code = 'EVD-9C098C7E7DD357B920F1-SUDDEN';
MATCH (rec:KGNode {entityType:'RecommendationStatement', code:'REC-CDSS-VASCD-SCD-SUDDEN-04-01-FOLLOW'})
MATCH (gl:KGNode {entityType:'Guideline', code:'SRC-DOC-00005AB23BE6D130'})
MERGE (rec)-[:uses_primary_guideline]->(gl)
SET rec.primary_guideline_code = 'SRC-DOC-00005AB23BE6D130';
