from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional, Tuple, Protocol
from app.schemas.relation_extract import EN_TO_CN_KIND
from app.core.config import settings


class KnowledgeGraphUnavailableError(RuntimeError):
	pass


class KnowledgeGraphProvider(Protocol):
	def ingest_aliases(self, project_id: int, mapping: Dict[str, List[str]]) -> None: ...
	def ingest_triples_with_attributes(self, project_id: int, triples: List[Tuple[str, str, str, Dict[str, Any]]]) -> None: ...
	def query_subgraph(
		self,
		project_id: int,
		participants: Optional[List[str]] = None,
		radius: int = 2,
		edge_type_whitelist: Optional[List[str]] = None,
		top_k: int = 50,
		max_chapter_id: Optional[int] = None,
		pov_character: Optional[str] = None,
	) -> Dict[str, Any]: ...
	def delete_project_graph(self, project_id: int) -> None: ...
	def get_full_graph(self, project_id: int) -> Dict[str, Any]: ...


class Neo4jKGProvider:
	def __init__(self) -> None:
		from neo4j import GraphDatabase  # type: ignore
		self._driver = GraphDatabase.driver(
			settings.NEO4J_URI, 
			auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
		)

	def close(self) -> None:
		try:
			self._driver.close()
		except Exception:
			pass

	@staticmethod
	def _group(project_id: int) -> str:
		return f"proj:{project_id}"

	def ingest_triples_with_attributes(self, project_id: int, triples: List[Tuple[str, str, str, Dict[str, Any]]]) -> None:
		group = self._group(project_id)
		if not triples:
			return
		rows: List[Dict[str, Any]] = []
		for s, p, o, attrs in triples:
			# 只写 RELATES_TO，具体类型写入 kind(kind_cn/kind_en)
			kind_cn = EN_TO_CN_KIND.get(p, p)
			payload: Dict[str, Any] = {
				"s": s,
				"o": o,
				"kind_cn": kind_cn,
				"kind_en": p,
				"fact": f"{s} {p} {o}",
				"a_to_b": attrs.get("a_to_b_addressing"),
				"b_to_a": attrs.get("b_to_a_addressing"),
				"recent_dialogues": attrs.get("recent_dialogues") or [],
				"recent_event_summaries_json": json.dumps(attrs.get("recent_event_summaries") or [], ensure_ascii=False),
				"stance_json": json.dumps(getattr(attrs.get("stance"), "model_dump", lambda: attrs.get("stance"))(), ensure_ascii=False) if attrs.get("stance") is not None else None,
				"valid_from": attrs.get("valid_from_chapter"),
				"valid_until": attrs.get("valid_until_chapter"),
				"observed_by": attrs.get("observed_by"),
			}
			rows.append(payload)

		if not rows:
			return
		cypher = (
			"UNWIND $rows AS row "
			"MERGE (a:Entity {name: row.s, group_id: $group}) "
			"MERGE (b:Entity {name: row.o, group_id: $group}) "
			"MERGE (a)-[r:RELATES_TO]->(b) "
			"SET r.kind = row.kind_cn, "
			"r.kind_en = row.kind_en, "
			"r.fact = row.fact, "
			"r.a_to_b_addressing = row.a_to_b, "
			"r.b_to_a_addressing = row.b_to_a, "
			"r.recent_dialogues = row.recent_dialogues, "
			"r.recent_event_summaries_json = row.recent_event_summaries_json, "
			"r.stance_json = row.stance_json, "
			"r.valid_from = row.valid_from, "
			"r.valid_until = row.valid_until, "
			"r.observed_by = row.observed_by"
		)
		with self._driver.session() as sess:
			try:
				sess.run(cypher, rows=rows, group=group)
			except Exception as e:
				error_msg = str(e)
				if "Security.Forbidden" in error_msg or "access denied" in error_msg.lower():
					raise RuntimeError(f"知识图谱写入失败: 权限不足 (Neo4j Access Denied)。请检查数据库用户权限或是否处于只读模式。详情: {error_msg}")
				raise RuntimeError(f"知识图谱写入失败: {error_msg}")

	def query_subgraph(
		self,
		project_id: int,
		participants: Optional[List[str]] = None,
		radius: int = 2,
		edge_type_whitelist: Optional[List[str]] = None,
		top_k: int = 50,
		max_chapter_id: Optional[int] = None,
		pov_character: Optional[str] = None,
	) -> Dict[str, Any]:
		group = self._group(project_id)
		parts = [p for p in (participants or []) if isinstance(p, str) and p.strip()]
		if not parts:
			return {"nodes": [], "edges": [], "alias_table": {}, "fact_summaries": [], "relation_summaries": []}

		# 仅查询 RELATES_TO，支持时间切片和 POV 过滤
		where_clause = "a.name IN $parts AND b.name IN $parts"
		if max_chapter_id is not None:
			where_clause += " AND (r.valid_from IS NULL OR r.valid_from <= $max_chapter_id) AND (r.valid_until IS NULL OR r.valid_until >= $max_chapter_id)"
		
		if pov_character:
			where_clause += " AND (r.observed_by IS NULL OR r.observed_by = $pov_character)"

		rel_cypher = (
			f"MATCH (a:Entity {{group_id:$group}})-[r:RELATES_TO]->(b:Entity {{group_id:$group}}) "
			f"WHERE {where_clause} "
			"RETURN a.name AS a, 'RELATES_TO' AS t, b.name AS b, r {.*} as props "
			"LIMIT $limit"
		)

		fact_summaries: List[str] = []
		rel_items: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
		edges: List[Dict[str, Any]] = []
		with self._driver.session() as sess:
			results = sess.run(rel_cypher, group=group, parts=parts, limit=max(1, int(top_k)), max_chapter_id=max_chapter_id, pov_character=pov_character)
			for rec in results:
				a = rec["a"]; b = rec["b"]; t = rec["t"]; props = rec["props"] or {}
				# 中文关系类型优先来自属性
				kind_cn = props.get("kind") or props.get("kind_cn") or None
				if not kind_cn and props.get("kind_en"):
					kind_cn = EN_TO_CN_KIND.get(props.get("kind_en"), props.get("kind_en"))
				if not kind_cn:
					kind_cn = "其他"
				fact = props.get("fact") or f"{a} relates_to {b}"
				key = (a, b, str(kind_cn))
				if key not in rel_items:
					rel_items[key] = { "a": a, "b": b, "kind": kind_cn }
				# 附带属性
				try:
					ev = json.loads(props.get("recent_event_summaries_json") or "[]")
				except Exception: ev = []
				try:
					s = json.loads(props.get("stance_json") or "null")
				except Exception: s = None
				if props.get("a_to_b_addressing"): rel_items[key]["a_to_b_addressing"] = props.get("a_to_b_addressing")
				if props.get("b_to_a_addressing"): rel_items[key]["b_to_a_addressing"] = props.get("b_to_a_addressing")
				if props.get("recent_dialogues"): rel_items[key]["recent_dialogues"] = props.get("recent_dialogues")
				if ev: rel_items[key]["recent_event_summaries"] = ev
				if s is not None: rel_items[key]["stance"] = s
				# 回显
				if len(fact_summaries) < top_k:
					fact_summaries.append(fact)
				if len(edges) < top_k:
					edges.append({"source": a, "target": b, "type": "relates_to", "fact": fact, "kind": kind_cn})

		relation_summaries = list(rel_items.values())
		return {
			"nodes": [],
			"edges": edges,
			"alias_table": {},
			"fact_summaries": fact_summaries,
			"relation_summaries": relation_summaries,
		}

	def delete_project_graph(self, project_id: int) -> None:
		"""删除某个项目(group_id)下的所有节点和关系。"""
		group = self._group(project_id)
		with self._driver.session() as sess:
			# 先删关系再删节点
			sess.run("MATCH (n:Entity {group_id:$group})-[r]-() DELETE r", group=group)
			sess.run("MATCH (n:Entity {group_id:$group}) DELETE n", group=group)

	def get_full_graph(self, project_id: int) -> Dict[str, Any]:
		"""获取某个项目下的完整图谱数据（节点与关系）。"""
		group = self._group(project_id)
		node_cypher = "MATCH (n:Entity {group_id: $group}) RETURN n.name AS name"
		edge_cypher = (
			"MATCH (a:Entity {group_id: $group})-[r:RELATES_TO]->(b:Entity {group_id: $group}) "
			"RETURN a.name AS source, b.name AS target, r.kind AS kind, r.kind_en AS kind_en, r.fact AS fact, r.recent_event_summaries_json AS events"
		)
		
		nodes = []
		edges = []
		with self._driver.session() as sess:
			node_results = sess.run(node_cypher, group=group)
			for rec in node_results:
				nodes.append({"id": rec["name"], "label": rec["name"]})
			
			edge_results = sess.run(edge_cypher, group=group)
			for rec in edge_results:
				events = []
				try:
					if rec["events"]:
						events = json.loads(rec["events"])
				except: pass
				
				edges.append({
					"source": rec["source"],
					"target": rec["target"],
					"label": rec["kind"] or rec["kind_en"] or "RELATES_TO",
					"properties": {
						"fact": rec["fact"],
						"events": events
					}
				})
		
		return {"nodes": nodes, "edges": edges}


def get_provider() -> KnowledgeGraphProvider:
	# 仅使用 Neo4j 提供方
	return Neo4jKGProvider()