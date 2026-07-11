# 软件化数据字典_system_data_dictionary

本文件定义未来管理系统优先读取的数据源。

| 数据表 | 来源文件 | 用途 |
|---|---|---|
| project_manifest | `01_项目运行清单_manifest.json` | 项目运行配置 |
| file_index | `02_关键文件清单_file_index.csv` | 文件定位 |
| directory_index | `03_目录用途清单_directory_index.csv` | 目录用途与迁移策略 |
| batch_ledger | `04_批次登记台账_batch_ledger.csv` | 批次状态 |
| error_fingerprint | `05_全局错误指纹索引_error_fingerprint.csv` | 错误预警与防复发 |
| script_inventory | `06_脚本资产台账_script_inventory.csv` | 脚本风险分级 |
| terminology_index | `07_术语字典索引_terminology_index.csv` | 术语字典入口 |
