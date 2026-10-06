"""Read API over the knowledge tables (used by the UI's Encyclopedia and by the simulation)."""

from __future__ import annotations

import json
import sqlite3
from typing import Optional


class Knowledge:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @classmethod
    def default(cls) -> Optional["Knowledge"]:
        from ..history import HistoryDB
        h = HistoryDB.load_default()
        return cls(h.conn) if h is not None else None

    def _rows(self, sql: str, args: tuple = ()) -> list:
        try:
            return self.conn.execute(sql, args).fetchall()
        except sqlite3.OperationalError:  # database built before the knowledge layer
            return []

    # ------------------------------------------------------------------ lists
    def series(self) -> list[dict]:
        out = []
        for sid, name, body, disc, level, tier, tpl, src, conf, doc in self._rows(
                "SELECT id, name, sanctioning_body, discipline, level, game_tier, game_template, history_source, "
                "confidence, doc FROM series_info ORDER BY game_tier DESC, name"):
            d = json.loads(doc)
            years = d.get("years") or {}
            out.append({"id": sid, "name": name, "body": body, "discipline": disc, "level": level, "tier": tier,
                        "game_template": tpl, "history_source": src, "confidence": conf,
                        "regions": d.get("regions") or [], "from": years.get("from") if isinstance(years, dict) else None,
                        "to": years.get("to") if isinstance(years, dict) else None,
                        "annual_cost_usd": d.get("annual_cost_usd"), "typical_age": d.get("typical_age")})
        return out

    def series_detail(self, sid: str) -> Optional[dict]:
        row = self._rows("SELECT doc FROM series_info WHERE id = ?", (sid,))
        if not row:
            return None
        doc = json.loads(row[0][0])
        doc["facts"] = self.facts(sid)
        doc["links"] = [{"kind": k, "id": o, "name": self._name(o)} for k, o in
                        self._rows("SELECT kind, other_id FROM series_link WHERE series_id = ?", (sid,))]
        doc["linked_from"] = [{"kind": k, "id": s, "name": self._name(s)} for s, k in
                              self._rows("SELECT series_id, kind FROM series_link WHERE other_id = ?", (sid,))]
        doc["body_detail"] = self.body(doc.get("sanctioning_body")) if doc.get("sanctioning_body") else None
        doc["car_class_detail"] = self.car_class(doc.get("car_class")) if doc.get("car_class") else None
        doc["source_detail"] = self.sources_for(doc.get("sources") or [])
        if doc.get("history_source"):
            doc["seasons"] = [{"year": y, "name": n, "data_level": lvl} for y, n, lvl in self._rows(
                "SELECT year, official_name, data_level FROM season WHERE source = ? ORDER BY year",
                (doc["history_source"],))]
        return doc

    def _name(self, eid: str) -> str:
        for table in ("series_info", "sanctioning_body", "car_class", "career_path"):
            r = self._rows(f"SELECT name FROM {table} WHERE id = ?", (eid,))
            if r:
                return r[0][0]
        return eid

    def facts(self, eid: str) -> list[dict]:
        return [{"attribute": a, "value": json.loads(v) if v else None, "min": lo, "max": hi, "unit": u,
                 "category": c, "confidence": conf, "sources": json.loads(s or "[]"), "notes": n}
                for a, v, lo, hi, u, c, conf, s, n in self._rows(
                    "SELECT attribute, value, min, max, unit, category, confidence, sources, notes FROM fact "
                    "WHERE entity_id = ? ORDER BY attribute", (eid,))]

    def body(self, bid: str) -> Optional[dict]:
        r = self._rows("SELECT doc FROM sanctioning_body WHERE id = ?", (bid,))
        return json.loads(r[0][0]) if r else None

    def bodies(self) -> list[dict]:
        return [json.loads(d) for (d,) in self._rows("SELECT doc FROM sanctioning_body ORDER BY name")]

    def car_class(self, cid: str) -> Optional[dict]:
        r = self._rows("SELECT doc FROM car_class WHERE id = ?", (cid,))
        return json.loads(r[0][0]) if r else None

    def car_classes(self) -> list[dict]:
        return [json.loads(d) for (d,) in self._rows("SELECT doc FROM car_class ORDER BY discipline, name")]

    def paths(self) -> list[dict]:
        out = []
        for (doc,) in self._rows("SELECT doc FROM career_path ORDER BY discipline, name"):
            p = json.loads(doc)
            for step in p.get("steps") or []:
                step["series_names"] = [{"id": x, "name": self._name(x)} if isinstance(x, str) else x
                                        for x in step.get("series") or []]
            out.append(p)
        return out

    def factors(self) -> list[dict]:
        out = []
        for (doc,) in self._rows("SELECT doc FROM advancement_factor ORDER BY id"):
            out.append(json.loads(doc))
        return out

    def transitions(self) -> list[dict]:
        return [dict(json.loads(doc), from_name=self._name(f), to_name=self._name(t))
                for f, t, doc in self._rows("SELECT from_id, to_id, doc FROM transition")]

    def stages(self) -> list[dict]:
        return [json.loads(d) for (d,) in self._rows("SELECT doc FROM career_stage ORDER BY age_min")]

    def sources_for(self, ids: list[str]) -> list[dict]:
        out = []
        for sid in ids:
            r = self._rows("SELECT id, name, url, kind, reliability, license, accessed FROM source WHERE id = ?", (sid,))
            if r:
                i, n, u, k, rel, lic, acc = r[0]
                out.append({"id": i, "name": n, "url": u, "kind": k, "reliability": rel, "license": lic, "accessed": acc})
            else:
                out.append({"id": sid, "name": sid})
        return out

    def sources(self) -> dict:
        srcs = [{"id": i, "name": n, "url": u, "kind": k, "reliability": rel, "license": lic, "accessed": acc,
                 "uses": uses}
                for i, n, u, k, rel, lic, acc, uses in self._rows(
                    "SELECT s.id, s.name, s.url, s.kind, s.reliability, s.license, s.accessed, "
                    "(SELECT COUNT(*) FROM ledger l WHERE l.source_id = s.id) FROM source s ORDER BY s.kind, s.name")]
        unavailable = [{"source": s, "url": u, "reason": r, "checked": c, "replacement": rep}
                       for s, u, r, c, rep in self._rows("SELECT * FROM source_unavailable")]
        datasets = [dict(zip(("name", "url", "coverage", "accuracy", "license", "update_frequency", "usefulness",
                              "decision", "notes"), r)) for r in self._rows("SELECT * FROM dataset ORDER BY name")]
        return {"sources": srcs, "unavailable": unavailable, "datasets": datasets}

    def summary(self) -> dict:
        from .report import confidence_by_category, gaps, summary
        return {"counts": summary(self.conn),
                "confidence": {k: dict(v) for k, v in confidence_by_category(self.conn).items()},
                "gaps": gaps(self.conn)}
