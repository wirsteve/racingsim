"""Owner mode: the player starts, runs and sells a team.

In any off-season the player can put their savings into a team in a team-run touring or national
series. The new team starts small: one car, a modest shop, a few local sponsors, and a staff hired
at its level. From then on it lives in the same economy as every other team (world/finance.py):
purses, sponsors, fans and merchandise come in; running the car, the staff and the drivers go out.
The difference is the owner's money is the player's. Losses come out of the player's savings, and
a team that runs dry with nothing left to cover it is sold.

Owner decisions, once per off-season:
  * budget: lean (bank money), normal, or push (spend ahead of income for speed)
  * hiring priority: speed (results), money (pay drivers), or youth (potential)
  * drive for the team yourself (an off-season choice), or let the market fill the seats
  * sell the team (the shop, the cars and any cash left)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..history.economy import nominal_usd
from ..util import clamp

if TYPE_CHECKING:
    from ..world.entities import Driver, Team
    from ..world.world import World, YearSummary

OWNER_TIERS = (3, 6)          # touring series up to the national level below the top (no charters to buy)
BUY_IN = 0.5                  # of one car's full-season cost: cars, engines, shop and tools
SELL_BACK = 0.6               # of the buy-in a buyer pays for the team (plus the cash)
BUDGET = {"lean": 0.8, "normal": 1.0, "push": 1.25}
PRIORITY = {"speed": {"performance": 0.6, "potential": 0.15, "money": 0.15, "marketability": 0.1},
            "money": {"performance": 0.25, "potential": 0.1, "money": 0.55, "marketability": 0.1},
            "youth": {"performance": 0.25, "potential": 0.5, "money": 0.15, "marketability": 0.1}}


def owned(world: "World") -> Optional["Team"]:
    tid = world.__dict__.get("owned_team_id")
    return world.teams.get(tid) if tid is not None else None


def buy_in(tpl) -> float:
    return BUY_IN * tpl.season_cost


def options(world: "World", d: "Driver") -> list[dict]:
    """Series where the player could start a team, cheapest first (the best few per level)."""
    out = []
    for s in world.pyramid.active():
        tpl = s.template
        if not tpl.team_based or not OWNER_TIERS[0] <= s.tier <= OWNER_TIERS[1]:
            continue
        cost = buy_in(tpl)
        out.append({"value": s.id, "label": s.name, "tier": s.tier, "cost": round(cost),
                    "afford": d.savings >= cost})
    out.sort(key=lambda o: (o["cost"], -o["tier"], o["label"]))
    return out[:30]


def actions(world: "World", d: "Driver") -> list[dict]:
    """Owner actions for the off-season menu."""
    t = owned(world)
    if t is None:
        opts = options(world, d)
        if not opts:
            return []
        return [{"id": "found_team", "label": "Start a team",
                 "detail": "Put your savings into a team of your own: one car, a small shop and a staff. "
                           "Losses come out of your savings.",
                 "options": [{"value": o["value"], "label": f'{o["label"]} (T{o["tier"]}) - {nominal_usd(world.year, o["cost"])}'
                              + ("" if o["afford"] else " (can't afford)")} for o in opts]}]
    return [
        {"id": "team_budget", "label": f"{t.name}: budget",
         "detail": "Lean banks money, push spends ahead of income for speed. What you spend this year is next year's car.",
         "options": [{"value": k, "label": k.title() + (" (current)" if k == t.budget_mode else ""),
                      "selected": k == t.budget_mode} for k in BUDGET]},
        {"id": "team_priority", "label": f"{t.name}: hiring priority",
         "detail": "Who your team signs for open seats when the market runs.",
         "options": [{"value": k, "label": k.title()} for k in PRIORITY]},
        {"id": "sell_team", "label": f"Sell {t.name}",
         "detail": f"A buyer pays about {nominal_usd(world.year, SELL_BACK * buy_in(world.series(t.series_id).template) + _facilities(world, t))} "
                   "for the shop, the cars and the facilities you built, plus whatever cash the team holds."},
    ]


def _facilities(world: "World", t: "Team") -> float:
    from ..rules.shop import team_value
    return team_value(world, t)


def act(world: "World", d: "Driver", action: str, arg: Optional[str]) -> Optional[str]:
    """Apply an owner action; None if the action isn't an owner action."""
    if action == "found_team":
        return found(world, d, arg)
    if action == "team_budget":
        t = owned(world)
        if t is None or arg not in BUDGET:
            return "Pick a budget."
        t.budget_mode = arg
        return f"{t.name} will run a {arg} budget next season."
    if action == "team_priority":
        t = owned(world)
        if t is None or arg not in PRIORITY:
            return "Pick a hiring priority."
        w = PRIORITY[arg]
        t.w_performance, t.w_potential, t.w_money, t.w_marketability = (
            w["performance"], w["potential"], w["money"], w["marketability"])
        return f"{t.name} will hire for {arg}."
    if action == "sell_team":
        return sell(world, d)
    return None


def found(world: "World", d: "Driver", series_id: Optional[str]) -> str:
    from ..career.market import _push
    from ..world import finance
    from ..world.entities import Team
    from ..world.factory import base_selection
    from ..world.staff import staff_team
    if owned(world) is not None:
        return "You already own a team."
    s = world.pyramid.series.get(series_id) if series_id else None
    if s is None or s.dormant or not s.template.team_based or not OWNER_TIERS[0] <= s.tier <= OWNER_TIERS[1]:
        return "Pick a series to start a team in."
    tpl = s.template
    cost = buy_in(tpl)
    if d.savings < cost:
        return f"Starting a team in the {s.name} takes about {nominal_usd(world.year, cost)}; you have {nominal_usd(world.year, d.savings)}."
    d.savings -= cost
    rivals = sorted(t.equipment for t in world.teams_in(s.id)) or [40.0]
    name = f"{d.last_name} Motorsports"
    if any(t.name == name for t in world.teams.values()):
        name = f"{d.first_name[0]}. {d.last_name} Racing"
    sel, conn_w = base_selection(tpl)
    total = sum(sel.values()) or 1.0
    per_seat = tpl.season_cost / max(1, tpl.drivers_per_car)
    t = Team(id=world.next_id("team"), name=name, series_id=s.id, home_region=d.home_region, owner_type="family",
             equipment=round(rivals[len(rivals) // 4], 1), sponsor_funding=round(0.1 * per_seat), cars=1,
             drivers_per_car=tpl.drivers_per_car,
             w_performance=sel.get("performance", 0.45) / total, w_potential=sel.get("potential", 0.15) / total,
             w_money=sel.get("money", 0.3) / total, w_marketability=sel.get("marketability", 0.1) / total,
             w_connections=conn_w, reputation=25.0)
    t.roster = [None] * t.seats
    t.player_owned = True
    t.spend = 0.8
    t.cash = 0.0
    world.teams[t.id] = t
    world.owned_team_id = t.id
    world.cache.pop("staff_by_team", None)
    staff_team(world, t)
    finance.ensure(world)
    for slot in range(t.seats):          # the market fills the seats unless the owner drives
        _push(world.market.queue, t, slot, tpl)
    d.log(world.year, f"founded {t.name} in the {s.name}")
    world.post("player", f"You founded {t.name} to race in the {s.name} ({nominal_usd(world.year, cost)})", driver_id=d.id,
               series_id=s.id, importance=3)
    world.market.player_offers = None
    return f"{t.name} is open for business in the {s.name}. Drive for it yourself, or let the market find a driver."


def sell(world: "World", d: "Driver") -> str:
    from ..career.market import _push
    t = owned(world)
    if t is None:
        return "You don't own a team."
    from ..rules.shop import team_value
    tpl = world.series(t.series_id).template
    price = SELL_BACK * buy_in(tpl) + max(0.0, t.cash) + team_value(world, t)
    d.savings += price
    t.cash = round(0.25 * tpl.season_cost * t.cars)   # the buyer brings money of their own
    t.player_owned = False
    t.owner_type = "privateer"
    world.owned_team_id = None
    if d.team_id == t.id:
        from .career import _vacate
        _vacate(world, d)
    d.log(world.year, f"sold {t.name}")
    world.post("player", f"You sold {t.name} for {nominal_usd(world.year, price)}", driver_id=d.id, importance=3)
    world.market.player_offers = None
    return f"Sold {t.name} for {nominal_usd(world.year, price)}."


def drive_choice(world: "World", d: "Driver") -> Optional[dict]:
    """An off-season choice: drive your own car next season."""
    from ..career.market import _eligible, seat_role
    t = owned(world)
    if t is None or d.team_id == t.id:
        return None
    tpl = world.series(t.series_id).template
    if not _eligible(world, d, tpl, seat_role(tpl, 0)):
        return None
    return {"id": "own_team", "kind": "own_team", "team_id": t.id, "series_id": t.series_id}


def drive(world: "World", d: "Driver", summary: "YearSummary") -> str:
    from ..career.market import _push, _sign, release_seat
    from .career import _vacate
    t = owned(world)
    if t is None:
        return "You don't own a team."
    s = world.series(t.series_id)
    _vacate(world, d)
    slot = next((i for i, x in enumerate(t.roster) if x is None), 0)
    if t.roster[slot] is not None:                 # the owner takes the seat
        other = world.drivers.get(t.roster[slot])
        if other is not None:
            release_seat(world, other)
            other.series_id = None
    _sign(world, d, t, slot, s, 0.0, 1.0, True, summary, world.market.queue)
    d.salary = 0.0                                   # owner-drivers take the money out as profit, if any
    world.market.signed.add(d.id)
    return f"You'll drive your own car for {t.name} in the {s.name}."


def settle(world: "World", t: "Team", tpl) -> Optional[str]:
    """Season end for the player's team: the owner covers losses from savings, or sells if they can't."""
    d = world.player
    if d is None:
        return None
    draw = 0.0
    if t.cash < 0:
        draw = min(-t.cash, max(0.0, d.savings))
        d.savings -= draw
        t.cash += draw
        if t.books:
            t.books[-1]["owner_draw"] = round(draw)
    if t.cash < -0.25 * tpl.season_cost * t.cars:
        world.post("player", f"{t.name} ran out of money and your savings couldn't cover it: the team is sold",
                   driver_id=d.id, importance=3)
        t.player_owned = False
        t.owner_type = "privateer"
        t.cash = round(0.25 * tpl.season_cost * t.cars)
        world.owned_team_id = None
        return "sold"
    if draw:
        world.post("player", f"{t.name} lost money: you covered {nominal_usd(world.year, draw)} from your savings", driver_id=d.id,
                   importance=2)
    return None


def budget_factor(t: "Team") -> float:
    return BUDGET.get(getattr(t, "budget_mode", "normal"), 1.0)


def clamp_spend(x: float) -> float:
    from ..world.finance import SPEND_MAX, SPEND_MIN
    return clamp(x, SPEND_MIN, SPEND_MAX)
