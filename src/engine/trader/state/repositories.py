"""Repository/service container for trader state."""

import sqlite3
from dataclasses import dataclass

from src.engine.trader.state.commands import CommandRepository
from src.engine.trader.state.equity import EquityRepository
from src.engine.trader.state.events import EventRepository
from src.engine.trader.state.legs import LegRepository
from src.engine.trader.state.lifecycle import PositionLifecycleService
from src.engine.trader.state.positions import PositionRepository
from src.engine.trader.state.reconciliation import ReconciliationRepository
from src.engine.trader.state.runtime import RuntimeStateRepository
from src.engine.trader.state.signals import TickSignalRepository


@dataclass(frozen=True)
class StateRepositories:
    """All state repositories and coordinating services for one SQLite connection."""

    positions: PositionRepository
    events: EventRepository
    legs: LegRepository
    equity: EquityRepository
    signals: TickSignalRepository
    runtime: RuntimeStateRepository
    commands: CommandRepository
    reconciliation: ReconciliationRepository
    lifecycle: PositionLifecycleService


def build_state_repositories(conn: sqlite3.Connection) -> StateRepositories:
    """Build repositories and services sharing one SQLite connection."""
    positions = PositionRepository(conn)
    events = EventRepository(conn)
    legs = LegRepository(conn)

    return StateRepositories(
        positions=positions,
        events=events,
        legs=legs,
        equity=EquityRepository(conn),
        signals=TickSignalRepository(conn),
        runtime=RuntimeStateRepository(conn),
        commands=CommandRepository(conn),
        reconciliation=ReconciliationRepository(conn),
        lifecycle=PositionLifecycleService(
            conn=conn,
            positions=positions,
            events=events,
            legs=legs,
        ),
    )
