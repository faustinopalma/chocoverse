import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from .config import DemoConfig
from .events import Json, make_business_event


@dataclass(frozen=True)
class Product:
    share: int
    line: str
    wholesaleCents: int
    retailCents: int
    recipeGrams: dict[str, int]


@dataclass(frozen=True)
class BusinessConfig:
    version: int
    fidelity: str
    dailyDemandKg: int
    initialRawMaterialDays: int
    initialFinishedGoodsDays: int
    initialChannelStockDays: int
    qualityHoldHours: int
    supplierLeadHours: int
    packagingLeadHours: int
    distributionLeadHours: int
    reviewEveryHours: int
    territories: list[str]
    channels: dict[str, int]
    lines: dict[str, int]
    products: dict[str, Product]
    materialCentsPerKg: dict[str, int]
    packagingCentsPerUnit: int
    conversionCentsPerKg: int

    @classmethod
    def load(cls, path: Path) -> "BusinessConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        data["products"] = {name: Product(**values) for name, values in data["products"].items()}
        result = cls(**data)
        if result.version != 1 or result.fidelity != "causal-aggregate":
            raise ValueError("Unsupported business scenario version/fidelity.")
        for name, value in asdict(result).items():
            if isinstance(value, int) and (type(value) is not int or value < 1):
                raise ValueError(f"{name} must be a positive integer.")
        if set(result.channels) != {"modern_trade", "export", "own_retail", "traditional", "professional", "campaigns", "travel"}:
            raise ValueError("The complete seven-channel mix is required.")
        if sum(result.channels.values()) != 100 or sum(p.share for p in result.products.values()) != 100:
            raise ValueError("Channel and product shares must sum to 100.")
        if any(type(v) is not int or v < 1 for v in result.channels.values()):
            raise ValueError("Channel shares must be positive integers.")
        if not result.territories or len(set(result.territories)) != len(result.territories):
            raise ValueError("Territories must be nonempty and unique.")
        if any(type(v) is not int or v < 1 for v in result.lines.values()):
            raise ValueError("Line capacities must be positive integers.")
        for product in result.products.values():
            if any(type(v) is not int or v < 1 for v in (product.share, product.wholesaleCents, product.retailCents)):
                raise ValueError("Product shares and prices must be positive integers.")
            if product.line not in result.lines or sum(product.recipeGrams.values()) != 1000:
                raise ValueError("Every product needs a valid line and a one-kilogram recipe.")
            if any(m not in result.materialCentsPerKg or type(q) is not int or q < 1 for m, q in product.recipeGrams.items()):
                raise ValueError("Invalid material recipe.")
        if any(type(v) is not int or v < 1 for v in result.materialCentsPerKg.values()):
            raise ValueError("Material prices must be positive integer cents per kilogram.")
        return result

    def baseline(self, sku: str) -> int:
        return math.ceil(self.dailyDemandKg * self.products[sku].share / 100)

    def raw_target(self, days: int) -> dict[str, int]:
        result = {name: 0 for name in self.materialCentsPerKg}
        for sku, product in self.products.items():
            for material, grams in product.recipeGrams.items():
                result[material] += self.baseline(sku) * days * grams
            result[f"pack:{sku}"] = self.baseline(sku) * days
        return result


@dataclass(frozen=True)
class Message:
    id: str
    sender: str
    recipient: str
    kind: str
    sent_tick: int
    deliver_tick: int
    correlation: str
    item: str = ""
    quantity: int = 0
    channel: str = ""
    amount_cents: int = 0
    values: dict[str, Json] = field(default_factory=dict)


@dataclass
class StepResult:
    messages: list[Message] = field(default_factory=list)
    facts: list[tuple[str, dict[str, Json]]] = field(default_factory=list)
    review: bool = False


class Module:
    name: str

    def __init__(self, name: str, config: BusinessConfig, seed: int) -> None:
        self.name, self.config, self.seed = name, config, seed
        self.result = StepResult()
        self.tick = 0

    def draw(self, key: str) -> float:
        value = f"{self.seed}:{self.name}:{self.tick}:{key}".encode()
        return int.from_bytes(hashlib.sha256(value).digest()[:8], "big") / 2**64

    def send(
        self, kind: str, recipient: str, *, delay: int = 1, correlation: str = "",
        item: str = "", quantity: int = 0, channel: str = "", amount_cents: int = 0,
        values: dict[str, Json] | None = None,
    ) -> None:
        if delay < 1 or quantity < 0:
            raise ValueError("Messages need positive lookahead and non-negative quantities.")
        identity = f"{self.name}:{self.tick}:{len(self.result.messages)}"
        self.result.messages.append(Message(
            identity, self.name, recipient, kind, self.tick, self.tick + delay, correlation or identity,
            item, quantity, channel, amount_cents, values or {},
        ))

    def emit(self, kind: str, **values: Json) -> None:
        self.result.facts.append((kind, values))

    def step(self, tick: int, sim_time: datetime, inbox: list[Message]) -> StepResult:
        self.tick, self.result = tick, StepResult()
        self.advance(sim_time, inbox)
        return self.result

    def advance(self, sim_time: datetime, inbox: list[Message]) -> None:
        raise NotImplementedError

    def snapshot(self) -> dict:
        raise NotImplementedError

    def restore(self, state: dict) -> None:
        raise NotImplementedError

    def observe(self) -> dict[str, Json]:
        raise PermissionError(f"{self.name} does not expose enterprise observations.")

    def health(self) -> dict[str, Json]:
        return {"module": self.name, "tick": self.tick, "healthy": True}


class World(Module):
    def advance(self, sim_time: datetime, inbox: list[Message]) -> None:
        if self.tick % 24 == 0:
            self.emit("world.calendar.day", date=sim_time.date().isoformat(), month=sim_time.month)

    def snapshot(self) -> dict:
        return {}

    def restore(self, state: dict) -> None:
        if state:
            raise ValueError("Unexpected world state.")


class Market(World):
    def advance(self, sim_time: datetime, inbox: list[Message]) -> None:
        if self.tick % 24:
            return
        seasonal = 1.7 if sim_time.month in (3, 4, 11, 12) else 0.65
        weekend = 1.12 if sim_time.weekday() >= 5 else 1.0
        for channel, share in self.config.channels.items():
            for sku in self.config.products:
                for territory in self.config.territories:
                    factor = seasonal if sku.startswith("seasonal") else 1.0
                    mean = self.config.baseline(sku) * share / 100 / len(self.config.territories)
                    quantity = max(1, round(mean * factor * weekend * (0.8 + 0.4 * self.draw(f"{channel}:{sku}:{territory}"))))
                    self.send(
                        "market.purchase.intent", "retail" if channel == "own_retail" else "trade",
                        item=sku, quantity=quantity, channel=channel, values={"territory": territory},
                    )


class Channels(Module):
    def __init__(self, name: str, config: BusinessConfig, seed: int) -> None:
        super().__init__(name, config, seed)
        self.channels = [c for c in config.channels if (c == "own_retail") == (name == "retail")]
        self.stock = {
            f"{c}:{sku}": math.ceil(config.baseline(sku) * config.channels[c] / 100 * config.initialChannelStockDays)
            for c in self.channels for sku in config.products
        }
        self.initial = self.stock.copy()
        self.sold = {key: 0 for key in self.stock}
        self.received = self.sold.copy()
        self.pending = self.sold.copy()
        self.day_sold = self.sold.copy()

    def advance(self, sim_time: datetime, inbox: list[Message]) -> None:
        for message in inbox:
            key = f"{message.channel}:{message.item}"
            if message.kind == "logistics.goods.delivered":
                self.stock[key] += message.quantity
                self.received[key] += message.quantity
                self.pending[key] -= message.quantity
            elif message.kind == "market.purchase.intent":
                sold = min(self.stock[key], message.quantity)
                self.stock[key] -= sold
                self.sold[key] += sold
                self.day_sold[key] += sold
                if sold:
                    self.emit(f"{self.name}.sellout.recorded", channel=message.channel, sku=message.item, quantity=sold,
                              territory=message.values["territory"], correlation=message.correlation)
                    if self.name == "retail":
                        self.send("retail.cash.received", "finance", item=message.item, quantity=sold,
                                  channel=message.channel, amount_cents=sold * self.config.products[message.item].retailCents,
                                  correlation=message.correlation)
            else:
                raise ValueError(f"Unexpected channel message {message.kind}.")
        if self.tick % 24 == 3:
            for channel in self.channels:
                for sku in self.config.products:
                    key = f"{channel}:{sku}"
                    self.send("commerce.sellout.reported", "planning", item=sku, channel=channel,
                              quantity=self.day_sold[key], values={"stock": self.stock[key]})
                    self.day_sold[key] = 0
                    target = math.ceil(self.config.baseline(sku) * self.config.channels[channel] / 100 * 4)
                    quantity = max(0, target - self.stock[key] - self.pending[key])
                    if quantity:
                        self.pending[key] += quantity
                        self.send("commerce.salesorder.placed", "logistics", item=sku, channel=channel, quantity=quantity)

    def snapshot(self) -> dict:
        return {k: getattr(self, k).copy() for k in ("stock", "sold", "received", "pending", "day_sold")}

    def restore(self, state: dict) -> None:
        for name in ("stock", "sold", "received", "pending", "day_sold"):
            setattr(self, name, state[name].copy())

    def observe(self) -> dict[str, Json]:
        return {"stock_kg": sum(self.stock.values()), "sold_kg": sum(self.sold.values()), "ordered_kg": sum(self.pending.values())}


class Logistics(Module):
    def __init__(self, config: BusinessConfig, seed: int) -> None:
        super().__init__("logistics", config, seed)
        self.stock = {sku: config.baseline(sku) * config.initialFinishedGoodsDays for sku in config.products}
        self.initial = self.stock.copy()
        self.received = {sku: 0 for sku in config.products}
        self.dispatched = self.received.copy()
        self.orders: list[dict] = []

    def advance(self, sim_time: datetime, inbox: list[Message]) -> None:
        for message in inbox:
            if message.kind == "factory.finished.released":
                self.stock[message.item] += message.quantity
                self.received[message.item] += message.quantity
            elif message.kind == "commerce.salesorder.placed":
                self.orders.append({"sku": message.item, "channel": message.channel, "quantity": message.quantity,
                                    "correlation": message.correlation})
            else:
                raise ValueError(f"Unexpected logistics message {message.kind}.")
        remaining = []
        for order in self.orders:
            sku, channel = order["sku"], order["channel"]
            quantity = min(self.stock[sku], order["quantity"])
            if quantity:
                self.stock[sku] -= quantity
                self.dispatched[sku] += quantity
                self.send("logistics.goods.delivered", "retail" if channel == "own_retail" else "trade",
                          item=sku, quantity=quantity, channel=channel, delay=self.config.distributionLeadHours,
                          correlation=order["correlation"])
                self.emit("logistics.shipment.dispatched", sku=sku, channel=channel, quantity=quantity,
                          correlation=order["correlation"])
                if channel != "own_retail":
                    self.send("finance.sales.invoice", "finance", item=sku, quantity=quantity, channel=channel,
                              amount_cents=quantity * self.config.products[sku].wholesaleCents,
                              delay=self.config.distributionLeadHours, correlation=order["correlation"])
                order["quantity"] -= quantity
            if order["quantity"]:
                remaining.append(order)
        self.orders = remaining
        if self.tick % 24 == 2:
            for sku in self.stock:
                backlog = sum(o["quantity"] for o in self.orders if o["sku"] == sku)
                self.send("logistics.inventory.reported", "planning", item=sku, quantity=self.stock[sku], values={"backlog": backlog})

    def snapshot(self) -> dict:
        return {"stock": self.stock.copy(), "received": self.received.copy(), "dispatched": self.dispatched.copy(),
                "orders": [o.copy() for o in self.orders]}

    def restore(self, state: dict) -> None:
        self.stock, self.received, self.dispatched, self.orders = state["stock"], state["received"], state["dispatched"], state["orders"]

    def observe(self) -> dict[str, Json]:
        return {"finished_kg": sum(self.stock.values()), "backlog_kg": sum(o["quantity"] for o in self.orders),
                "shipped_kg": sum(self.dispatched.values())}


class Factory(Module):
    def __init__(self, config: BusinessConfig, seed: int) -> None:
        super().__init__("factory", config, seed)
        self.materials = config.raw_target(config.initialRawMaterialDays)
        self.initial = self.materials.copy()
        self.received = {m: 0 for m in self.materials}
        self.consumed = self.received.copy()
        self.produced = {sku: 0 for sku in config.products}
        self.started = self.produced.copy()
        self.wip: list[dict] = []
        self.line_use: dict[str, int] = {line: 0 for line in config.lines}
        self.line_day = -1

    def advance(self, sim_time: datetime, inbox: list[Message]) -> None:
        if self.tick // 24 != self.line_day:
            self.line_day = self.tick // 24
            self.line_use = {line: 0 for line in self.config.lines}
        for batch in self.wip[:]:
            if batch["ready"] <= self.tick:
                self.produced[batch["sku"]] += batch["quantity"]
                self.send("factory.finished.released", "logistics", item=batch["sku"], quantity=batch["quantity"],
                          correlation=batch["correlation"])
                self.emit("factory.quality.released", sku=batch["sku"], quantity=batch["quantity"],
                          correlation=batch["correlation"], hold_hours=self.config.qualityHoldHours)
                self.wip.remove(batch)
        for message in inbox:
            if message.kind == "supply.material.delivered":
                self.materials[message.item] += message.quantity
                self.received[message.item] += message.quantity
                self.emit("factory.material.received", material=message.item, quantity=message.quantity,
                          correlation=message.correlation)
            elif message.kind == "planning.production.scheduled":
                sku = message.item
                product = self.config.products[sku]
                recipe = {**product.recipeGrams, f"pack:{sku}": 1}
                quantity = min(message.quantity, self.config.lines[product.line] - self.line_use[product.line],
                               *(self.materials[m] // grams for m, grams in recipe.items()))
                if quantity:
                    for material, grams in recipe.items():
                        self.materials[material] -= quantity * grams
                        self.consumed[material] += quantity * grams
                    self.line_use[product.line] += quantity
                    self.started[sku] += quantity
                    self.wip.append({"sku": sku, "quantity": quantity, "ready": self.tick + 6 + self.config.qualityHoldHours,
                                     "correlation": message.correlation})
                    self.emit("factory.production.started", sku=sku, quantity=quantity, line=product.line,
                              correlation=message.correlation)
                    self.send("finance.conversion.paid", "finance", item=sku, quantity=quantity,
                              amount_cents=quantity * self.config.conversionCentsPerKg, correlation=message.correlation)
                if quantity < message.quantity:
                    self.emit("factory.production.constrained", sku=sku, requested=message.quantity, started=quantity,
                              correlation=message.correlation)
            else:
                raise ValueError(f"Unexpected factory message {message.kind}.")
        if self.tick % 24 == 2:
            for material, quantity in self.materials.items():
                self.send("factory.material.reported", "planning", item=material, quantity=quantity)
            for sku in self.config.products:
                self.send("factory.wip.reported", "planning", item=sku,
                          quantity=sum(b["quantity"] for b in self.wip if b["sku"] == sku))

    def snapshot(self) -> dict:
        return {"materials": self.materials.copy(), "received": self.received.copy(), "consumed": self.consumed.copy(),
                "produced": self.produced.copy(), "started": self.started.copy(), "wip": [b.copy() for b in self.wip],
                "line_use": self.line_use.copy(), "line_day": self.line_day}

    def restore(self, state: dict) -> None:
        for name in ("materials", "received", "consumed", "produced", "started", "wip", "line_use", "line_day"):
            setattr(self, name, state[name])

    def observe(self) -> dict[str, Json]:
        return {"produced_kg": sum(self.produced.values()), "wip_kg": sum(b["quantity"] for b in self.wip),
                "line_use_kg": dict(self.line_use)}


class Supply(Module):
    def __init__(self, config: BusinessConfig, seed: int) -> None:
        super().__init__("supply", config, seed)
        self.orders = 0
        self.confirmed: dict[str, int] = {}

    def advance(self, sim_time: datetime, inbox: list[Message]) -> None:
        for message in inbox:
            if message.kind != "planning.purchase.placed":
                raise ValueError(f"Unexpected supplier message {message.kind}.")
            self.orders += 1
            self.confirmed[message.item] = self.confirmed.get(message.item, 0) + message.quantity
            packaging = message.item.startswith("pack:")
            lead = self.config.packagingLeadHours if packaging else self.config.supplierLeadHours
            lead += 24 if self.draw(message.item) < 0.1 else 0
            self.send("supply.purchase.confirmed", "planning", item=message.item, quantity=message.quantity,
                      correlation=message.correlation, values={"lead_hours": lead})
            self.send("supply.material.delivered", "factory", delay=lead, item=message.item,
                      quantity=message.quantity, correlation=message.correlation)
            self.send("supply.purchase.received", "planning", delay=lead + 1, item=message.item,
                      quantity=message.quantity, correlation=message.correlation)
            cost = message.quantity * self.config.packagingCentsPerUnit if packaging else (
                message.quantity * self.config.materialCentsPerKg[message.item] // 1000
            )
            self.send("finance.purchase.invoice", "finance", delay=lead, item=message.item,
                      quantity=message.quantity, amount_cents=cost, correlation=message.correlation)

    def snapshot(self) -> dict:
        return {"orders": self.orders, "confirmed": self.confirmed.copy()}

    def restore(self, state: dict) -> None:
        self.orders, self.confirmed = state["orders"], state["confirmed"]

    def observe(self) -> dict[str, Json]:
        return {"confirmed_orders": self.orders}


OPTIONS = {
    "lean": {"forecast_percent": 100, "cover_days": 2},
    "balanced": {"forecast_percent": 105, "cover_days": 3},
    "resilient": {"forecast_percent": 115, "cover_days": 4},
}


class Planning(Module):
    def __init__(self, config: BusinessConfig, seed: int) -> None:
        super().__init__("planning", config, seed)
        self.forecast = {sku: float(config.baseline(sku)) for sku in config.products}
        self.finished = {sku: config.baseline(sku) * config.initialFinishedGoodsDays for sku in config.products}
        self.backlog = {sku: 0 for sku in config.products}
        self.wip = self.backlog.copy()
        self.raw = config.raw_target(config.initialRawMaterialDays)
        self.on_order = {m: 0 for m in self.raw}
        self.option = "lean"
        self.review_count = 0

    def advance(self, sim_time: datetime, inbox: list[Message]) -> None:
        sales = {sku: 0 for sku in self.config.products}
        reported = False
        for message in inbox:
            if message.kind == "commerce.sellout.reported":
                sales[message.item] += message.quantity
                reported = True
            elif message.kind == "logistics.inventory.reported":
                self.finished[message.item] = message.quantity
                self.backlog[message.item] = int(str(message.values["backlog"]))
            elif message.kind == "factory.wip.reported":
                self.wip[message.item] = message.quantity
            elif message.kind == "factory.material.reported":
                self.raw[message.item] = message.quantity
            elif message.kind == "supply.purchase.received":
                self.on_order[message.item] -= message.quantity
            elif message.kind == "supply.purchase.confirmed":
                pass
            elif message.kind == "agents.strategy.selected":
                option = str(message.values["option"])
                if option not in OPTIONS:
                    raise ValueError("Strategy outside S&OP authority.")
                before = self.option
                self.option = option
                self.review_count += 1
                self.emit("planning.strategy.applied", before=before, option=option,
                          forecast_percent=OPTIONS[option]["forecast_percent"], cover_days=OPTIONS[option]["cover_days"])
            else:
                raise ValueError(f"Unexpected planning message {message.kind}.")
        if reported:
            for sku, quantity in sales.items():
                self.forecast[sku] = round(0.8 * self.forecast[sku] + 0.2 * quantity, 3)
        if self.tick % 24 == 6:
            policy = OPTIONS[self.option]
            daily = {sku: max(1, math.ceil(q * policy["forecast_percent"] / 100)) for sku, q in self.forecast.items()}
            capacity = self.config.lines.copy()
            for sku in sorted(self.config.products, key=lambda s: (-self.backlog[s], s)):
                product = self.config.products[sku]
                needed = max(0, daily[sku] * policy["cover_days"] + self.backlog[sku] - self.finished[sku] - self.wip[sku])
                quantity = min(needed, capacity[product.line])
                if quantity:
                    capacity[product.line] -= quantity
                    self.send("planning.production.scheduled", "factory", item=sku, quantity=quantity)
            target = {m: 0 for m in self.raw}
            for sku, quantity in daily.items():
                for material, grams in self.config.products[sku].recipeGrams.items():
                    target[material] += quantity * (math.ceil(self.config.supplierLeadHours / 24) + policy["cover_days"]) * grams
                target[f"pack:{sku}"] = quantity * (math.ceil(self.config.packagingLeadHours / 24) + policy["cover_days"])
            for material, quantity in target.items():
                needed = max(0, quantity - self.raw[material] - self.on_order[material])
                if needed:
                    self.on_order[material] += needed
                    self.send("planning.purchase.placed", "supply", item=material, quantity=needed)
        if self.tick > 0 and self.tick % self.config.reviewEveryHours == 0:
            self.result.review = True

    def snapshot(self) -> dict:
        return {name: getattr(self, name) for name in ("forecast", "finished", "backlog", "wip", "raw", "on_order", "option", "review_count")}

    def restore(self, state: dict) -> None:
        for name in ("forecast", "finished", "backlog", "wip", "raw", "on_order", "option", "review_count"):
            setattr(self, name, state[name])

    def observe(self) -> dict[str, Json]:
        return {"forecast_kg_per_day": dict(self.forecast), "backlog_kg": sum(self.backlog.values()),
                "strategy": self.option, "reviews_applied": self.review_count}


class Finance(Module):
    def __init__(self, config: BusinessConfig, seed: int) -> None:
        super().__init__("finance", config, seed)
        self.cash = 10_000_000
        self.revenue = self.purchases = self.conversion = self.receivable = self.payable = 0
        self.settlements: list[dict] = []

    def advance(self, sim_time: datetime, inbox: list[Message]) -> None:
        for settlement in self.settlements[:]:
            if settlement["due"] <= self.tick:
                amount = settlement["amount"]
                self.cash += amount
                if amount > 0:
                    self.receivable -= amount
                else:
                    self.payable += amount
                self.emit("finance.cash.settled", amount_cents=amount, correlation=settlement["correlation"])
                self.settlements.remove(settlement)
        for message in inbox:
            amount = message.amount_cents
            if message.kind == "retail.cash.received":
                self.cash += amount
                self.revenue += amount
            elif message.kind == "finance.sales.invoice":
                self.revenue += amount
                self.receivable += amount
                self.settlements.append({"due": self.tick + 168, "amount": amount, "correlation": message.correlation})
            elif message.kind == "finance.purchase.invoice":
                self.purchases += amount
                self.payable += amount
                self.settlements.append({"due": self.tick + 168, "amount": -amount, "correlation": message.correlation})
            elif message.kind == "finance.conversion.paid":
                self.cash -= amount
                self.conversion += amount
            else:
                raise ValueError(f"Unexpected finance message {message.kind}.")
            self.emit("finance.ledger.posted", posting_type=message.kind, amount_cents=amount, correlation=message.correlation)

    def snapshot(self) -> dict:
        return {name: getattr(self, name) for name in ("cash", "revenue", "purchases", "conversion", "receivable", "payable", "settlements")}

    def restore(self, state: dict) -> None:
        for name in ("cash", "revenue", "purchases", "conversion", "receivable", "payable", "settlements"):
            setattr(self, name, state[name])

    def observe(self) -> dict[str, Json]:
        return {"cash_cents": self.cash, "revenue_cents": self.revenue, "purchases_cents": self.purchases,
                "receivable_cents": self.receivable, "payable_cents": self.payable}


class ReportProvider(Protocol):
    def briefing(self, role: str, cut_off: int) -> dict[str, Json]: ...


class Manager(Protocol):
    def decide(self, key: str, report: dict[str, Json]) -> dict[str, Json]: ...


class OperationalReports:
    def __init__(self, modules: dict[str, Module]) -> None:
        self.modules = modules

    def briefing(self, role: str, cut_off: int) -> dict[str, Json]:
        if role != "sop_chair":
            raise PermissionError("No report scope configured for this manager role.")
        return {"role": role, "cut_off_tick": cut_off,
                "reports": {name: self.modules[name].observe() for name in ("planning", "logistics", "factory", "finance")},
                "options": {name: dict(values) for name, values in OPTIONS.items()}}


class BusinessEngine:
    def __init__(self, config: DemoConfig, business: BusinessConfig, run_id: str, manager: Manager) -> None:
        if config.tick_seconds != 3600:
            raise ValueError("The initial business fidelity requires hourly ticks.")
        if not run_id or len(run_id) > 64 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
            raise ValueError("Run IDs must be safe nonempty identifiers of at most 64 characters.")
        self.config, self.business, self.run_id, self.manager = config, business, run_id, manager
        self.speed = config.speed
        self.tick, self.sequence = 0, 0
        modules = [
            World("world", business, config.seed), Market("market", business, config.seed),
            Channels("retail", business, config.seed), Channels("trade", business, config.seed),
            Logistics(business, config.seed), Factory(business, config.seed), Supply(business, config.seed),
            Planning(business, config.seed), Finance(business, config.seed),
        ]
        self.modules = {module.name: module for module in modules}
        self.reports: ReportProvider = OperationalReports(self.modules)
        self.pending: list[Message] = []
        self.outbox: list[dict[str, Json]] = []
        self.event_counts: dict[str, int] = {}

    @property
    def fingerprint(self) -> str:
        value = json.dumps({"clock": asdict(self.config), "business": asdict(self.business)}, default=str, sort_keys=True)
        return hashlib.sha256(value.encode()).hexdigest()

    def event(self, source: str, kind: str, values: dict[str, Json]) -> None:
        self.sequence += 1
        event = make_business_event(
            config=self.config, run_id=self.run_id, sequence=self.sequence, tick=self.tick,
            sim_time=self.config.epoch + timedelta(hours=self.tick), wall_time=datetime.now(UTC),
            source=source, event_type=kind, data=values, visibility="truth" if source == "market" else "enterprise",
        )
        event["speed"] = self.speed
        self.outbox.append(event)
        self.event_counts[kind] = self.event_counts.get(kind, 0) + 1

    def route(self, message: Message) -> None:
        if message.recipient not in self.modules or message.deliver_tick <= self.tick:
            raise ValueError("Unknown recipient or noncausal message.")
        correlation = message.correlation
        if len(correlation) != 36 or correlation.count("-") != 4:
            correlation = str(uuid5(NAMESPACE_URL, f"{self.run_id}:{correlation}"))
        message = Message(**{**asdict(message), "id": str(uuid5(NAMESPACE_URL, f"{self.run_id}:{message.id}")),
                             "correlation": correlation})
        self.pending.append(message)
        self.event(message.sender, message.kind, {
            "message_id": message.id, "to": message.recipient, "sent_tick": message.sent_tick,
            "deliver_tick": message.deliver_tick, "correlation": message.correlation,
            "item": message.item, "quantity": message.quantity, "channel": message.channel,
            "amount_cents": message.amount_cents, "values": dict(message.values),
        })

    def step(self) -> None:
        inbox: dict[str, list[Message]] = {name: [] for name in self.modules}
        later = []
        for message in self.pending:
            if message.deliver_tick <= self.tick:
                inbox[message.recipient].append(message)
            else:
                later.append(message)
        self.pending = later
        review = False
        for name, module in self.modules.items():
            result = module.step(self.tick, self.config.epoch + timedelta(hours=self.tick), inbox[name])
            for kind, data in result.facts:
                self.event(name, kind, data)
            for message in result.messages:
                self.route(message)
            review = review or result.review
        if review:
            decision = self.manager.decide(f"{self.run_id}:{self.tick}:sop_chair", self.reports.briefing("sop_chair", self.tick))
            option = decision.get("option")
            if not isinstance(option, str) or option not in OPTIONS:
                raise ValueError("Manager returned an unauthorized strategy.")
            self.event("agents", "agents.decision.recorded", decision)
            self.route(Message(f"agents:{self.tick}:0", "agents", "planning", "agents.strategy.selected",
                               self.tick, self.tick + 1, f"review:{self.tick}", values={"option": option}))
        self.assert_invariants()
        self.tick += 1

    def snapshot(self) -> dict:
        state = {"version": 1, "fingerprint": self.fingerprint, "run_id": self.run_id, "tick": self.tick,
                "sequence": self.sequence, "pending": [asdict(m) for m in self.pending],
                "modules": {name: module.snapshot() for name, module in self.modules.items()},
                "outbox": self.outbox, "event_counts": self.event_counts}
        return json.loads(json.dumps(state, allow_nan=False))

    def restore(self, snapshot: dict) -> None:
        if snapshot["version"] != 1 or snapshot["run_id"] != self.run_id or snapshot["fingerprint"] != self.fingerprint:
            raise ValueError("Snapshot version, run identity or scenario fingerprint mismatch.")
        self.tick, self.sequence = snapshot["tick"], snapshot["sequence"]
        self.pending = [Message(**m) for m in snapshot["pending"]]
        if len({m.id for m in self.pending}) != len(self.pending) or any(m.deliver_tick < self.tick for m in self.pending):
            raise ValueError("Corrupt pending message queue.")
        for name, module in self.modules.items():
            module.restore(snapshot["modules"][name])
        self.outbox, self.event_counts = snapshot["outbox"], snapshot["event_counts"]
        self.assert_invariants()

    def assert_invariants(self) -> None:
        factory = self.modules["factory"]
        logistics = self.modules["logistics"]
        finance = self.modules["finance"]
        supply = self.modules["supply"]
        if not isinstance(factory, Factory) or not isinstance(logistics, Logistics) or not isinstance(finance, Finance) or not isinstance(supply, Supply):
            raise TypeError("Invalid business module registry.")
        for material, quantity in factory.materials.items():
            if quantity < 0 or factory.initial[material] + factory.received[material] - factory.consumed[material] != quantity:
                raise ValueError("Raw material conservation violated.")
            recipe_use = sum(factory.started[sku] * (1 if material == f"pack:{sku}" else product.recipeGrams.get(material, 0))
                             for sku, product in self.business.products.items())
            if factory.consumed[material] != recipe_use:
                raise ValueError("Production recipe conservation violated.")
            inbound = sum(m.quantity for m in self.pending if m.kind == "supply.material.delivered" and m.item == material)
            if supply.confirmed.get(material, 0) != factory.received[material] + inbound:
                raise ValueError("Supplier-to-factory conservation violated.")
        for sku, quantity in logistics.stock.items():
            if quantity < 0 or logistics.initial[sku] + logistics.received[sku] - logistics.dispatched[sku] != quantity:
                raise ValueError("Finished goods conservation violated.")
            wip = sum(b["quantity"] for b in factory.wip if b["sku"] == sku)
            if factory.started[sku] != factory.produced[sku] + wip:
                raise ValueError("Work-in-progress conservation violated.")
            in_transfer = sum(m.quantity for m in self.pending if m.kind == "factory.finished.released" and m.item == sku)
            if factory.produced[sku] != logistics.received[sku] + in_transfer:
                raise ValueError("Factory-to-warehouse transfer conservation violated.")
        for line, quantity in factory.line_use.items():
            if not 0 <= quantity <= self.business.lines[line]:
                raise ValueError("Finite line capacity violated.")
        for name in ("retail", "trade"):
            channels = self.modules[name]
            if not isinstance(channels, Channels):
                raise TypeError("Invalid channel module.")
            for key, quantity in channels.stock.items():
                if min(quantity, channels.pending[key]) < 0 or channels.initial[key] + channels.received[key] - channels.sold[key] != quantity:
                    raise ValueError("Channel stock conservation violated.")
                channel, sku = key.split(":")
                open_orders = sum(o["quantity"] for o in logistics.orders if o["sku"] == sku and o["channel"] == channel)
                in_transit = sum(m.quantity for m in self.pending if m.kind in ("commerce.salesorder.placed", "logistics.goods.delivered")
                                 and m.item == sku and m.channel == channel)
                if channels.pending[key] != open_orders + in_transit:
                    raise ValueError("Channel replenishment pipeline conservation violated.")
        if finance.cash + finance.receivable - finance.payable != 10_000_000 + finance.revenue - finance.purchases - finance.conversion:
            raise ValueError("Finance ledger conservation violated.")

    def summary(self) -> dict[str, Json]:
        return {"run_id": self.run_id, "tick": self.tick, "events": self.sequence,
                "fidelity": self.business.fidelity, "event_counts": dict(self.event_counts),
                "observations": {name: self.modules[name].observe() for name in self.modules if name not in ("world", "market")}}
