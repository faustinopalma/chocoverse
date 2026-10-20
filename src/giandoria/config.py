import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamps must have an explicit timezone.")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamps must have an explicit timezone.")
    if parsed.microsecond % 1000:
        raise ValueError("Timestamps must have millisecond precision or coarser.")
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class DemoConfig:
    scenario: str
    epoch: datetime
    seed: int
    tick_seconds: int
    speed: int
    business_timezone: str

    @classmethod
    def from_json(cls, text: str) -> "DemoConfig":
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Demo configuration must be a JSON object.")
        fixed = {
            "project": "giandoria",
            "environment": "demo",
            "location": "swedencentral",
            "fabricSku": "F4",
            "businessTimezone": "Europe/Rome",
            "networking": "public-where-policy-allows",
            "storageAccess": "public-with-resource-policy-exemption",
        }
        for key, expected in fixed.items():
            if data.get(key) != expected:
                raise ValueError(f"{key} must be {expected!r} for the agreed demo.")
        for key in ("seed", "tickSeconds", "speed"):
            value = data.get(key)
            if type(value) is not int or value < (0 if key == "seed" else 1):
                raise ValueError(f"{key} must be a {'non-negative' if key == 'seed' else 'positive'} integer.")
        if not isinstance(data.get("scenario"), str) or not data["scenario"].strip():
            raise ValueError("scenario must be a non-empty string.")
        if not isinstance(data.get("epoch"), str):
            raise ValueError("epoch must be a timezone-aware timestamp.")
        ZoneInfo(data["businessTimezone"])
        return cls(
            scenario=data["scenario"],
            epoch=parse_timestamp(data["epoch"]),
            seed=data["seed"],
            tick_seconds=data["tickSeconds"],
            speed=data["speed"],
            business_timezone=data["businessTimezone"],
        )

    @classmethod
    def load(cls, path: Path) -> "DemoConfig":
        return cls.from_json(path.read_text(encoding="utf-8"))
