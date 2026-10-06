"""Staff pages: a team's people, a staff member's profile, and the league-wide staff directory."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from ..world import skills
from ..world import staff as ST

if TYPE_CHECKING:
    from ..world.world import World


def _scouted(world: "World", s: ST.Staff, exact: bool) -> dict:
    """Staff ratings on the 20-80 scale; reputation-driven scouting error unless it's your own team."""
    rng = random.Random(s.id * 6151 + world.year)
    sd = 0.0 if exact else 2 + 10 * (1 - s.reputation / 100)
    step = 1 if exact else 5
    out = {}
    for k, v in s.ratings.items():
        g = skills.grade(v + (rng.gauss(0, sd) if sd else 0))
        out[k] = {"label": ST.RATING_LABEL.get(k, k), "value": int(round(g / step) * step)}
    return out


def brief(world: "World", s: ST.Staff, exact: bool = False) -> dict:
    team = world.teams.get(s.team_id) if s.team_id is not None else None
    return {
        "id": s.id, "name": s.name, "role": s.role, "role_label": ST.ROLES[s.role][0], "age": s.age(world.year),
        "team": {"id": team.id, "name": team.name} if team else None, "car": s.car,
        "ratings": _scouted(world, s, exact), "overall": skills.grade(s.overall()),
        "style": s.style, "reputation": round(s.reputation), "wins": s.wins, "titles": s.titles,
        "former_driver": s.former_driver, "retired": s.retired,
        "salary": round(s.salary) if exact else None, "contract_years": s.contract_years if exact else None,
    }


def own_team(world: "World", team_id: Optional[int]) -> bool:
    p = world.player
    return p is not None and p.team_id is not None and p.team_id == team_id


def team_staff(world: "World", team_id: int) -> list[dict]:
    exact = own_team(world, team_id)
    rows = [brief(world, s, exact) for s in ST.team_staff(world, team_id)]
    order = list(ST.ROLES)
    rows.sort(key=lambda r: (order.index(r["role"]), r["car"] if r["car"] is not None else -1))
    return rows


def staff_detail(world: "World", sid: int) -> Optional[dict]:
    s = world.staff.get(sid)
    if s is None:
        return None
    out = brief(world, s, own_team(world, s.team_id))
    out["about"] = ST.ROLES[s.role][3]
    out["history"] = [{"year": y, "team": t, "series": se, "wins": w, "titles": ti} for y, t, se, w, ti in s.history[-40:]]
    if s.former_driver and s.former_driver in world.drivers:
        out["former_driver_name"] = world.drivers[s.former_driver].name
    return out


def directory(world: "World", role: Optional[str] = None, limit: int = 300) -> dict:
    rows = []
    for s in world.staff.values():
        if s.retired or (role and s.role != role):
            continue
        rows.append(s)
    rows.sort(key=lambda s: (-(world.series(world.teams[s.team_id].series_id).tier if s.team_id in world.teams else -1),
                             -s.overall()))
    return {"roles": [{"key": k, "label": v[0], "about": v[3]} for k, v in ST.ROLES.items()],
            "staff": [brief(world, s, own_team(world, s.team_id)) for s in rows[:limit]]}
