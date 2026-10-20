from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class State(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    HIBERNATED = "hibernated"
    STOPPED = "stopped"


TRANSITIONS = {
    "start": ({State.CREATED}, State.RUNNING),
    "resume": ({State.PAUSED, State.HIBERNATED}, State.RUNNING),
    "pause": ({State.RUNNING}, State.PAUSED),
    "hibernate": ({State.RUNNING, State.PAUSED}, State.HIBERNATED),
    "stop": ({State.PAUSED, State.HIBERNATED}, State.STOPPED),
}


@dataclass
class Clock:
    sim_time: datetime
    tick: int = 0
    state: State = State.CREATED

    def transition(self, action: str) -> None:
        if action not in TRANSITIONS:
            raise ValueError(f"Unknown clock action: {action}")
        allowed, target = TRANSITIONS[action]
        if self.state not in allowed:
            raise ValueError(f"Cannot {action} a {self.state} run.")
        self.state = target

    def advance(self, seconds: int) -> tuple[datetime, datetime]:
        if self.state != State.RUNNING:
            raise ValueError("Only a running clock can advance.")
        if type(seconds) is not int or seconds <= 0:
            raise ValueError("Tick duration must be a positive integer.")
        previous = self.sim_time
        self.sim_time += timedelta(seconds=seconds)
        self.tick += 1
        return previous, self.sim_time
