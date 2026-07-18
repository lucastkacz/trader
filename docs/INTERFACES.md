# Interfaces Module

## 1. Purpose

The Interfaces module contains delivery adapters through which humans and
external systems invoke Operations use cases, inspect read models, and receive
notifications.

CLI, HTTP, Telegram, webhooks, and a UI backend are different transports over
the same application capabilities. They translate protocol-specific input and
output; they do not implement quantitative policy, read domain persistence
directly, or call an exchange.

The module makes the platform accessible without allowing a delivery mechanism
to become the system architecture.

## 2. Responsibilities and Boundaries

### 2.1 Interfaces owns

- transport routing and protocol lifecycle;
- parsing and syntactic validation;
- authentication integration and principal construction;
- transport-level authorization failure handling;
- translation to Operations commands and queries;
- delivery DTOs, pagination, versioning, and rendering;
- HTTP/CLI/Telegram error mapping;
- inbound rate limits and abuse protection;
- outbound notification channel adapters;
- protocol-specific observability with secret redaction.

### 2.2 Interfaces does not own

- Research, pair, market-data, signal, risk, order, or accounting policy;
- application authorization decisions for sensitive commands;
- workflow orchestration or scheduling;
- direct database, artifact, filesystem, or exchange access;
- domain transaction boundaries;
- process supervision or deployment;
- transport-specific copies of domain state.

### 2.3 Dependency direction

```text
external actor/system
-> interfaces
-> operations commands and queries
-> domain modules
```

Interfaces depends on stable Operations contracts. Operations receives no
Telegram update, HTTP request, argparse namespace, HTML string, or framework
object.

## 3. Delivery Adapters

The module supports adapter families rather than one privileged UI:

- **CLI** for local development, scripts, recovery, and independent safety
  access;
- **HTTP API** for remote automation and UI backends;
- **Telegram** for constrained notifications and selected operator actions;
- **webhooks** for verified inbound events or outbound integrations;
- **notification adapters** for Telegram, email, Slack, or other channels.

Each adapter is added only when a real use case and Operations contract exist.
A UI does not require domain packages to expose web-shaped APIs.

### 3.1 Logical package shape

```text
interfaces/
├── cli/
├── http/
├── telegram/
├── webhooks/
└── notifications/
```

The top level is organized by transport because each transport has its own
authentication, lifecycle, parsing, rendering, and failure semantics. There is
no global `api.py`: the stable application API belongs to Operations, and every
interface is an adapter over it.

Transport packages are created only for supported delivery mechanisms. Shared
domain or application models do not move here merely because several adapters
render them; each adapter receives delivery-neutral Operations contracts and
owns only its protocol-specific DTOs.

## 4. Interface Contract

An inbound adapter performs:

1. authenticate the caller;
2. parse protocol data;
3. validate syntax, size, and supported version;
4. build a typed principal and command/query request;
5. invoke one Operations interface;
6. map its typed result to the protocol;
7. record transport metadata and return.

It does not catch every failure and return success text. Error status, machine
code, correlation id, and safe detail remain explicit.

## 5. Delivery Models

Delivery DTOs are stable, serializable views designed for external consumers.
They may flatten or paginate Operations read models but cannot change their
meaning.

DTO fields carry explicit units and timestamps. Internal database ids, raw
venue payloads, filesystem paths, stack traces, secrets, and Pydantic/ORM
implementation details are not exposed accidentally.

Commands use explicit names and request bodies. Ambiguous transport labels such
as `stop` are replaced with the exact intended operation.

## 6. Authentication

Authentication proves principal identity. Supported mechanisms may include:

- local OS/session identity for CLI;
- scoped API tokens or OAuth/OIDC for HTTP/UI;
- verified chat/user identity for Telegram;
- signed secrets for webhooks;
- workload identity for automation.

Authentication configuration and secrets enter through typed settings. They are
never embedded in URLs, logs, domain commands, or source files.

Telegram chat-id matching is one transport authentication signal, not the
platform's universal identity system.

## 7. Authorization

Interfaces may reject obviously unauthenticated or transport-forbidden access,
but Operations owns the authoritative permission decision for an application
action.

Permissions distinguish at least:

- read operational state;
- run Research or Market Data workflows;
- review or promote pair sets;
- pause/resume new entries;
- activate/clear safety controls;
- cancel orders;
- request liquidation;
- enable Exchange routing toward a Demo or Production target.

High-impact commands require stronger authentication, explicit reason, target
scope, idempotency key, and confirmation appropriate to the transport.

## 8. CLI

The CLI is the first independent operator and recovery interface. It:

- has stable subcommands mapped one-to-one to Operations use cases;
- supports structured JSON output in addition to human-readable output;
- writes diagnostic text to stderr and machine output to stdout;
- returns documented exit codes;
- requires explicit config/profile paths or identities;
- never imports domain private helpers;
- never reads/writes databases or artifacts around Operations;
- provides kill-switch inspection/activation even when network UIs fail.

CLI parsing functions are not application APIs. Business behavior is tested
through Operations, with a smaller adapter test for parsing and exit mapping.

## 9. HTTP API

The HTTP adapter exposes versioned command and query resources. It provides:

- authentication and scoped authorization context;
- request-size, timeout, pagination, and rate-limit policy;
- idempotency keys for commands;
- correlation/request ids;
- typed error responses;
- asynchronous run resources for long work;
- secure CORS/CSRF behavior appropriate to its clients;
- health endpoints that distinguish liveness and readiness.

Long Research, refresh, or reconciliation requests return a run identity rather
than holding one connection indefinitely.

HTTP handlers never construct exchange clients or database sessions except
through the application composition root.

## 10. UI Backend

A visual UI consumes the same HTTP/query/command contracts. It presents status,
evidence, audit, and confirmations but does not become the source of truth.

UI absence or failure cannot remove access to critical safety controls. A local
CLI or independent emergency interface remains available.

The UI cannot infer production readiness from labels. It displays deployment
environment, routing mode, Exchange target, authorization, promoted pair-set
identity, data freshness, and unresolved safety state explicitly.

## 11. Telegram

Telegram is a convenience adapter for concise visibility and a deliberately
limited set of actions. It is not the primary architecture or the only safety
channel.

It may provide:

- notifications;
- health/run summaries;
- pair-set and position summaries;
- read-only inspection;
- selected low-ambiguity commands after authentication and authorization.

Telegram handlers call Operations. They never open Trading state, read JSON
artifacts, calculate PnL, or write command strings directly to a database.

Messages are escaped, length-bounded, paginated, and clear about deployment
environment, Observe/Paper/Exchange routing, and Demo/Production Exchange
target.

## 12. Notifications

Outbound adapters receive channel-neutral messages with severity, subject,
body, structured facts, correlation id, deduplication key, and target policy.

Adapters provide bounded timeouts, retry/backoff, rate-limit handling, and
delivery outcome. Notification delivery is best-effort unless an Operations
policy explicitly requires acknowledgement.

Network I/O never blocks Trading's event loop. A failed notification cannot
silently swallow the underlying domain event.

## 13. Commands

Every inbound command includes:

- command type and version;
- principal and authentication context;
- target scope;
- idempotency key;
- requested time;
- reason when required;
- expected state/version for conflict detection;
- confirmation evidence for high-impact actions.

Interfaces display the Operations result, including accepted, queued,
completed, rejected, conflicted, or failed status. “Command logged” is not
reported as successful execution.

## 14. Queries, Pagination, and Freshness

Query responses disclose:

- observation/as-of time;
- source projection identity;
- freshness or stale status;
- pagination cursor and stable ordering;
- omitted/unavailable data reasons;
- environment and scope.

Interfaces do not join raw tables or recalculate metrics. Expensive views are
prepared by Operations/domain read models and bounded by pagination or explicit
export workflows.

## 15. Error Mapping

Protocol responses distinguish:

- unauthenticated;
- unauthorized;
- invalid request;
- not found;
- conflict/idempotency mismatch;
- not ready or safety blocked;
- domain rejection;
- rate limited;
- external dependency unavailable;
- internal failure with correlation id.

Secrets, SQL, filesystem layouts, raw exchange payloads, and internal tracebacks
are never returned to untrusted callers.

## 16. API Evolution

External contracts are versioned independently from internal Python modules.
Breaking changes receive a new API/command version and a bounded transition
period only when an actual consumer requires it.

Delivery DTOs do not mirror every domain object. They expose deliberate stable
views and preserve unknown-vs-zero, unavailable-vs-empty, and current-vs-stale
semantics.

## 17. Observability and Audit

Every request records transport, principal id, route/command, result status,
latency, correlation id, and safe target scope. Sensitive values are redacted.

The authoritative command and promotion audit remains in Operations/domain
stores. Interface logs cannot substitute for authorization or state-transition
records.

## 18. Availability and Failure Isolation

Delivery adapters fail independently. Telegram outage does not stop Trading;
HTTP outage does not corrupt a Research run; UI outage does not erase kill-
switch state.

Adapters close network clients gracefully, apply bounded concurrency, and do
not retry non-idempotent commands without an idempotency key and durable status
lookup.

## 19. Determinism and Testability

Adapter tests use fake Operations APIs and no network. They prove:

- protocol input maps to the correct typed request;
- authentication and permission context is preserved;
- unsafe commands require confirmation and reason;
- typed outcomes map to correct statuses/exit codes/messages;
- escaping, pagination, and redaction are correct;
- retries do not duplicate commands;
- adapters never access domain stores or exchange clients;
- notification timeout does not block domain processing.

Separate explicitly selected probes verify real Telegram/HTTP infrastructure.

## 20. Safety Invariants

- Interfaces never mutate an exchange directly.
- Interfaces never bypass Operations authorization or domain risk controls.
- A UI label or available credential cannot enable Production routing.
- Query/rendering paths are read-only.
- Critical safety control remains accessible without Telegram or the main UI.
- Commands report durable outcome, not merely transport receipt.
- No interface reads or writes raw Trading databases or pair artifacts.
