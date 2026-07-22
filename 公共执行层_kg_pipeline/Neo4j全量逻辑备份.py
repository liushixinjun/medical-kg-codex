#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Neo4j 全量逻辑备份（只读）。

导出全部节点、关系、索引、约束和统计信息，并生成文件哈希及前后计数校验。
本脚本不执行任何 CREATE/MERGE/SET/DELETE/DROP 写操作。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]


def parse_connection_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    bolt = re.search(r"bolt(?:\+s|\+ssc)?://[^\s；;，,]+", text, re.I)
    username = re.search(r"(?:用户名|username|user)\s*[:：]\s*([^\s；;，,]+)", text, re.I)
    password = re.search(r"(?:密码|password)\s*[:：]\s*([^\s；;，,]+)", text, re.I)
    if not bolt or not password:
        raise ValueError(f"无法从连接文件解析 Bolt 地址或密码：{path}")
    return {
        "uri": bolt.group(0),
        "username": username.group(1) if username else "neo4j",
        "password": password.group(1),
    }


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"__type__": "bytes", "base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    iso_format = getattr(value, "iso_format", None)
    if callable(iso_format):
        return iso_format()
    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(json_safe(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(json_safe(row), ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            count += 1
    return count


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def query_rows(session: Any, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = session.run(cypher, parameters or {})
    return [dict(record) for record in result]


def query_scalar(session: Any, cypher: str, key: str) -> int:
    record = session.run(cypher).single(strict=True)
    return int(record[key])


def iter_nodes(session: Any, total: int, batch_size: int) -> Iterable[dict[str, Any]]:
    """流式导出节点，避免 SKIP/LIMIT 对全库进行重复扫描。"""
    del total, batch_size
    rows = session.run(
        """
        MATCH (n)
        RETURN elementId(n) AS element_id,
               labels(n) AS labels,
               properties(n) AS properties
        """
    )
    for row in rows:
        yield dict(row)


def iter_relationships(session: Any, total: int, batch_size: int) -> Iterable[dict[str, Any]]:
    """流式导出关系，避免 SKIP/LIMIT 对全库进行重复扫描。"""
    del total, batch_size
    rows = session.run(
        """
        MATCH (source)-[r]->(target)
        RETURN elementId(r) AS element_id,
               type(r) AS relationship_type,
               elementId(source) AS start_element_id,
               elementId(target) AS end_element_id,
               properties(r) AS properties
        """
    )
    for row in rows:
        yield dict(row)


def safe_query(session: Any, cypher: str) -> dict[str, Any]:
    try:
        return {"ok": True, "rows": query_rows(session, cypher)}
    except Exception as exc:  # 权限或 Neo4j 版本不支持时保留错误，不中断主体备份
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def build_file_manifest(output_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name == "备份清单_manifest.json":
            continue
        rows.append(
            {
                "file": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="只读导出 Neo4j 全量逻辑备份")
    parser.add_argument("--connection-file", type=Path, default=ROOT / "图谱数据库链接.txt")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--batch-size", type=int, default=2000)
    args = parser.parse_args()

    if args.batch_size < 100:
        parser.error("--batch-size 不得小于 100")

    connection_file = args.connection_file.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    conn = parse_connection_file(connection_file)
    parsed_uri = urlparse(conn["uri"])
    source_endpoint = f"{parsed_uri.scheme}://{parsed_uri.hostname}:{parsed_uri.port or 7687}"
    started_at = datetime.now(timezone.utc)

    driver = GraphDatabase.driver(conn["uri"], auth=(conn["username"], conn["password"]))
    try:
        driver.verify_connectivity()
        with driver.session(database=args.database, default_access_mode="READ") as session:
            counts_before = {
                "nodes": query_scalar(session, "MATCH (n) RETURN count(n) AS count", "count"),
                "relationships": query_scalar(
                    session, "MATCH ()-[r]->() RETURN count(r) AS count", "count"
                ),
            }

            database_info = {
                "source_endpoint": source_endpoint,
                "database": args.database,
                "dbms_components": safe_query(session, "CALL dbms.components()"),
                "databases": safe_query(session, "SHOW DATABASES"),
            }
            write_json(output_dir / "数据库信息_database_info.json", database_info)
            write_json(output_dir / "索引_indexes.json", safe_query(session, "SHOW INDEXES"))
            write_json(output_dir / "约束_constraints.json", safe_query(session, "SHOW CONSTRAINTS"))
            write_json(
                output_dir / "标签统计_label_counts.json",
                query_rows(
                    session,
                    "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count ORDER BY label",
                ),
            )
            write_json(
                output_dir / "关系统计_relationship_type_counts.json",
                query_rows(
                    session,
                    "MATCH ()-[r]->() RETURN type(r) AS relationship_type, count(*) AS count "
                    "ORDER BY relationship_type",
                ),
            )
            write_json(
                output_dir / "属性键_property_keys.json",
                safe_query(session, "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey ORDER BY propertyKey"),
            )

            exported_nodes = write_jsonl(
                output_dir / "全部节点_nodes.jsonl",
                iter_nodes(session, counts_before["nodes"], args.batch_size),
            )
            exported_relationships = write_jsonl(
                output_dir / "全部关系_relationships.jsonl",
                iter_relationships(session, counts_before["relationships"], args.batch_size),
            )

            counts_after = {
                "nodes": query_scalar(session, "MATCH (n) RETURN count(n) AS count", "count"),
                "relationships": query_scalar(
                    session, "MATCH ()-[r]->() RETURN count(r) AS count", "count"
                ),
            }
    finally:
        driver.close()

    finished_at = datetime.now(timezone.utc)
    count_consistent = (
        counts_before == counts_after
        and exported_nodes == counts_before["nodes"]
        and exported_relationships == counts_before["relationships"]
    )
    readme = f"""# Neo4j 全量逻辑备份说明

- 备份时间（UTC）：{started_at.isoformat()} 至 {finished_at.isoformat()}
- 来源：`{source_endpoint}` / 数据库 `{args.database}`
- 节点：{exported_nodes}
- 关系：{exported_relationships}
- 前后计数及导出数量一致：{'是' if count_consistent else '否'}

## 内容

- `全部节点_nodes.jsonl`：每行一个节点，保留标签和全部属性。
- `全部关系_relationships.jsonl`：每行一条有向关系，保留起点、终点、关系类型和全部属性。
- `索引_indexes.json`、`约束_constraints.json`：数据库结构信息。
- 统计文件：标签、关系类型和属性键清单。
- `备份清单_manifest.json`：数量校验、文件大小和 SHA-256 哈希。

## 恢复注意

该备份使用 Neo4j `elementId` 记录节点与关系的原始连接。恢复时必须先导入节点并建立“原 elementId → 新节点”的映射，再创建关系；不得把原 elementId 当成新库永久业务编码。正式恢复前应在空测试库演练并复核节点、关系、索引和约束数量。
"""
    (output_dir / "恢复与校验说明_README.md").write_text(readme, encoding="utf-8")

    manifest = {
        "backup_format": "neo4j_logical_jsonl_v1",
        "read_only": True,
        "source_endpoint": source_endpoint,
        "database": args.database,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "batch_size": args.batch_size,
        "counts_before": counts_before,
        "exported": {"nodes": exported_nodes, "relationships": exported_relationships},
        "counts_after": counts_after,
        "count_consistent": count_consistent,
        "files": build_file_manifest(output_dir),
    }
    write_json(output_dir / "备份清单_manifest.json", manifest)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "nodes": exported_nodes,
                "relationships": exported_relationships,
                "count_consistent": count_consistent,
            },
            ensure_ascii=False,
        )
    )
    return 0 if count_consistent else 2


if __name__ == "__main__":
    raise SystemExit(main())
