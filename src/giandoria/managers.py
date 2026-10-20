import hashlib
import json
from typing import Protocol

from .business import OPTIONS
from .events import Json


class JsonStore(Protocol):
    def get_json(self, container: str, name: str) -> dict | None: ...
    def put_json(self, container: str, name: str, value: dict) -> None: ...


class DecisionUnavailable(RuntimeError):
    pass


class ChatModel(Protocol):
    deployment: str
    version: str

    def choose(self, report: str, max_output_tokens: int) -> tuple[dict, dict]: ...


class StrategicManager:
    def __init__(
        self, store: JsonStore, model: ChatModel, run_id: str, *,
        max_calls: int = 2, max_output_tokens: int = 4096, max_reserved_tokens: int = 24000,
        budget_scope: str | None = None,
    ) -> None:
        if not 1 <= max_calls <= 128 or not 128 <= max_output_tokens <= 4096 or not 1 <= max_reserved_tokens <= 2_000_000:
            raise ValueError("LLM limits are outside the bounded demo envelope.")
        self.store, self.model = store, model
        self.path = f"{run_id}/ledger.json"
        self.max_calls, self.max_output_tokens, self.max_reserved_tokens = max_calls, max_output_tokens, max_reserved_tokens
        self.budget_scope = budget_scope

    def decide(self, key: str, report: dict[str, Json]) -> dict[str, Json]:
        prompt = json.dumps(report, separators=(",", ":"), sort_keys=True, allow_nan=False)
        digest = hashlib.sha256(prompt.encode()).hexdigest()
        ledger = self.store.get_json("decisions", self.path)
        if ledger is None:
            ledger = {"version": 1, "calls": 0, "reserved_tokens": 0, "records": {}}
        if ledger["version"] != 1:
            raise ValueError("Unsupported decision ledger.")
        budget = ledger if self.budget_scope is None else ledger.setdefault("session_budgets", {}).setdefault(
            self.budget_scope, {"calls": 0, "reserved_tokens": 0},
        )
        records = ledger["records"]
        if key in records:
            existing = records[key]
            if existing["input_digest"] != digest:
                raise ValueError("Replay briefing differs from the recorded decision.")
            if existing["state"] == "Complete":
                return existing["decision"]
            if existing["state"] != "Reserved":
                raise ValueError("Invalid decision record state.")
            return self._complete(ledger, key, self._fallback("InterruptedAttempt", digest))
        # UTF-8 bytes plus a fixed system-message allowance conservatively bound input size.
        reserved = len(prompt.encode()) + 2048 + self.max_output_tokens
        reason = None
        if len(prompt.encode()) > 12000:
            reason = "BriefingTooLarge"
        elif budget["calls"] >= self.max_calls:
            reason = "RequestLimit"
        elif budget["reserved_tokens"] + reserved > self.max_reserved_tokens:
            reason = "TokenReservationLimit"
        records[key] = {"state": "Reserved", "input_digest": digest, "deployment": self.model.deployment,
                        "model_version": self.model.version, "budget_scope": self.budget_scope}
        if reason:
            return self._complete(ledger, key, self._fallback(reason, digest))
        ledger["calls"] += 1
        ledger["reserved_tokens"] += reserved
        if budget is not ledger:
            budget["calls"] += 1
            budget["reserved_tokens"] += reserved
        self.store.put_json("decisions", self.path, ledger)
        try:
            answer, usage = self.model.choose(prompt, self.max_output_tokens)
            if (set(answer) != {"option", "reason"} or not isinstance(answer["option"], str)
                    or answer["option"] not in OPTIONS or not isinstance(answer["reason"], str)
                    or not 1 <= len(answer["reason"]) <= 600):
                raise DecisionUnavailable("InvalidStructuredOutput")
            for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
                if type(usage.get(field)) is not int or usage[field] < 0:
                    raise DecisionUnavailable("MissingTokenUsage")
            if usage["completion_tokens"] > self.max_output_tokens:
                raise DecisionUnavailable("OutputTokenLimit")
            decision: dict[str, Json] = {
                "mode": "llm", "option": answer["option"], "reason": answer["reason"], "input_digest": digest,
                "deployment": self.model.deployment, "model_version": self.model.version,
                "usage": {name: usage[name] for name in ("prompt_tokens", "completion_tokens", "total_tokens")},
            }
        except DecisionUnavailable as error:
            decision = self._fallback(str(error), digest)
        return self._complete(ledger, key, decision)

    def _fallback(self, reason: str, digest: str) -> dict[str, Json]:
        print(json.dumps({"operation": "manager.fallback", "reason": reason, "input_digest": digest}), flush=True)
        return {"mode": "fallback", "option": "balanced", "reason": reason, "input_digest": digest,
                "deployment": self.model.deployment, "model_version": self.model.version}

    def _complete(self, ledger: dict, key: str, decision: dict[str, Json]) -> dict[str, Json]:
        ledger["records"][key].update(state="Complete", decision=decision)
        self.store.put_json("decisions", self.path, ledger)
        return decision
