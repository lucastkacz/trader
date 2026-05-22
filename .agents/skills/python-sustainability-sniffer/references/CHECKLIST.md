# Python Sustainability Checklist

Use this checklist as prompts for inspection, not as automatic findings.

## Interface Smells

- Public function accepts raw dicts where typed config/value objects exist.
- Method signature mixes unrelated concerns such as config, state, I/O, and
  presentation flags.
- Class constructor hides operational dependencies by reading global settings,
  paths, clocks, or stores.
- Module exports multiple ways to do the same thing.
- Return type is ambiguous, tuple-heavy, or forces callers to know positional
  meaning.

## OOP And Domain Model Smells

- Class has more than one durable reason to change.
- Method mutates object state and external state without an explicit boundary.
- Inheritance is used only to share code, not to model substitutable behavior.
- Subclass requirements are implicit instead of expressed through a protocol or
  narrow interface.
- Data containers include business logic that belongs in a service, or services
  carry data that should be a value object.
- Boolean flags select fundamentally different workflows.

## Pythonic Design Smells

- Manual resource lifecycle where a context manager would be safer.
- Repeated ad hoc parsing instead of structured APIs, dataclasses, pydantic
  models, enums, or pathlib.
- Mutable defaults or shared mutable state.
- Broad `except Exception` without adding context or preserving failure
  visibility.
- Async code wraps long CPU/pandas work without an explicit boundary.
- Row-by-row DataFrame iteration for historical price or indicator work.

## Dependency And Side-Effect Smells

- Domain code reaches directly into filesystem paths, exchange names, timeframes,
  environment names, or storage locations.
- Research/reporting/config code can mutate exchange state.
- Tests depend on network, wall-clock sleeps, or real services.
- Runtime orchestration owns math or presentation logic that could be isolated.
- Presentation code mutates runtime state.

## Testability Smells

- Only internal helper behavior is tested while the public module contract is
  untested.
- Tests mock away the behavior that needs confidence.
- A behavior change lacks a failure-mode test.
- Fixtures create unrealistic objects that production code could never receive.
- Test setup requires too much hidden global state.

## Sustainable Refactor Heuristics

- Prefer extracting a value object before introducing a service.
- Prefer a function before a class when no durable state or polymorphism exists.
- Prefer a protocol/adapter seam when external behavior varies by environment.
- Prefer typed config at the boundary and explicit parameters below it.
- Prefer one small behavior-preserving move plus tests over a sweeping cleanup.
- Keep live-trading risk boundaries visible even if they make code more verbose.
