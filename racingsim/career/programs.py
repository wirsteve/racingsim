"""Manufacturer development programs, scholarships and shootouts.

* Manufacturer programs sign prospects around age 16 (research C 5.2), fund part of
  their next step and push them toward affiliated teams. Prospects who stall are
  released; blocked prospects may defect when another program offers more
  (research C 4.3: Deegan, Larson).
* Ladder scholarships award series champions a partial voucher toward the next
  rung (research B 2.3 / 10.4) -- the budget gap still has to be closed.
* Shootouts and combines are *meritocratic*: they test true ability with little
  noise, which is why they are the main way an unfunded talent breaks through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..constants import PROGRAM_AGE_MEAN, PROGRAM_AGE_RANGE, PROGRAM_AGE_SD, TIER_STRENGTH
from ..util import clamp
from ..world.entities import RETIRED, Driver
from .scouting import estimated_potential, is_aware

if TYPE_CHECKING:
    from ..sim.season import SeasonResults
    from ..world.world import World, YearSummary


def clear_consumed_scholarships(world: "World") -> None:
    for d in world.drivers.values():
        d.scholarship = 0.0


def award_champion_scholarships(world: "World", results: "SeasonResults") -> None:
    for sid, did in results.champions.items():
        tpl = world.series(sid).template
        if tpl.champion_scholarship > 0:
            d = world.drivers[did]
            d.scholarship += tpl.champion_scholarship
            d.log(world.year, f"earned a ${tpl.champion_scholarship:,.0f} advancement scholarship")


def manufacturer_programs(world: "World", summary: "YearSummary") -> None:
    rng = world.rng
    year = world.year
    for m in world.manufacturers.values():
        # Review current prospects.
        for did in list(m.prospects):
            d = world.drivers.get(did)
            if d is None or d.status == RETIRED:
                m.prospects.remove(did)
                continue
            d.program_years += 1
            age = d.age(year)
            behind = d.demonstrated < TIER_STRENGTH[min(7, d.tier + 1)] - 4
            if (age >= 24 and d.tier < 5) or (d.program_years >= 3 and behind and rng.random() < 0.5):
                m.prospects.remove(did)
                d.program_mfr = None
                d.log(year, f"released from the {m.name} development program")
                continue
            # Funding support toward the next step.
            d.scholarship += m.program_budget / max(1, m.program_slots) * rng.uniform(0.5, 1.0)
            d.connections[f"mfr:{m.id}"] = 1.0

        open_slots = m.program_slots - len(m.prospects)
        if open_slots <= 0:
            continue
        lo, hi = PROGRAM_AGE_RANGE
        candidates = []
        for d in world.drivers.values():
            if d.status == RETIRED or d.program_mfr is not None:
                continue
            age = d.age(year)
            if not (lo <= age <= hi + 3):
                continue
            if max(d.proficiency.get(x, 0) for x in m.disciplines) < 0.3:
                continue
            if d.tier < 1:
                continue
            if not is_aware(world, 4, None, d.primary_discipline, d):
                continue
            age_fit = 1 - abs(age - PROGRAM_AGE_MEAN) / (PROGRAM_AGE_SD * 4) * m.aggressiveness
            score = (estimated_potential(d, year) + len(d.crown_jewels) * 3 + d.exposure * 0.1
                     + d.marketability * 0.05) * clamp(age_fit, 0.6, 1.1) + rng.gauss(0, 3)
            candidates.append((score, d))
        candidates.sort(key=lambda x: -x[0])
        bar = TIER_STRENGTH[6] - 2 * m.aggressiveness
        for score, d in candidates[:open_slots]:
            if score < bar:
                break
            m.prospects.append(d.id)
            d.program_mfr = m.id
            d.program_years = 0
            d.connections[f"mfr:{m.id}"] = 1.0
            d.reputation = clamp(d.reputation + 8)
            d.exposure = clamp(d.exposure + 15)
            d.scholarship += m.program_budget / max(1, m.program_slots) * 0.6
            d.log(year, f"signed to the {m.name} driver development program at {d.age(year)}")
            summary.signings.append(f"{d.name} -> {m.name} development")


def run_shootouts(world: "World", summary: "YearSummary") -> None:
    rng = world.rng
    year = world.year
    for so in world.shootouts:
        templates = set(so["from_templates"])
        pool: list[Driver] = []
        for d in world.drivers.values():
            if d.status == RETIRED or not d.history:
                continue
            rec = d.history[-1]
            if rec.year != year:
                continue
            tkey = world.series(rec.series_id).template.key if rec.series_id in world.pyramid.series else ""
            if tkey not in templates:
                continue
            if not (so["min_age"] <= d.age(year) <= so["max_age"]):
                continue
            pool.append(d)
        if len(pool) < 4:
            continue

        def invite_score(d: Driver) -> float:
            rec = d.history[-1]
            fin = 1 - (rec.avg_finish - 1) / max(1, rec.field_size - 1)
            s = d.demonstrated + fin * 10 + rec.wins + (6 if rec.champion else 0) + rng.gauss(0, 3)
            if so.get("prefer_low_funding"):
                s -= min(15, d.available_funding() / 20_000)
            return s

        pool.sort(key=invite_score, reverse=True)
        invited = pool[: so["invites"]]
        target = world.pyramid.templates.get(so["target_template"])
        disc = target.discipline if target else invited[0].primary_discipline

        def test_score(d: Driver) -> float:
            # A shootout is a controlled test in identical cars: true ability shows.
            return d.ability * (0.8 + 0.2 * d.proficiency.get(disc, 0.3)) + d.adaptability * 0.05 + rng.gauss(0, 2.5)

        ranked = sorted(invited, key=test_score, reverse=True)
        winner = ranked[0]
        winner.scholarship += so["award"]
        winner.exposure = clamp(winner.exposure + 25)
        winner.reputation = clamp(winner.reputation + 10)
        winner.connections[f"target:{so['target_template']}"] = 1.0
        winner.log(year, f"won the {so['name']} (${so['award']:,.0f} toward the {target.name if target else 'next step'})")
        summary.signings.append(f"{winner.name} wins {so['name']}")
        for d in ranked[1:3]:
            d.exposure = clamp(d.exposure + 8)
