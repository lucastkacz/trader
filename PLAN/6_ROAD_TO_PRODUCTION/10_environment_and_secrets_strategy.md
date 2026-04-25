# Environment & Secrets Management Strategy

This document defines the canonical strategy for managing secrets, credentials, and environment-specific behavior across all four operational environments of the Stat-Arb engine.

---

## 1. The Two-Layer Model

All configuration is bifurcated into two completely separate layers with a hard architectural boundary between them:

| Layer | Storage | Contains | Committed to Git? |
|---|---|---|---|
| **Secrets** | `.env` / GitHub Secrets | API keys, bot tokens | ❌ Never |
| **Hyperparameters** | `configs/pipelines/*.yml` | Timeframe, db_path, sharpe cutoff | ✅ Always |

**The Rule:** `src/core/config.py` (via `pydantic-settings`) holds ONLY secrets. Strategy logic, thresholds, and pipeline behavior live exclusively in YAML files.

---

## 2. The Four Environments

| Env | Machine | Timeframe | API Permission | Keys Location |
|---|---|---|---|---|
| `dev` | Local Mac | 1m | Read-Only | Local `.env` |
| `uat` | Cloud VPS | 4h | Read-Only | GitHub Secrets → VPS env |
| `prod` | Cloud VPS | 4h | Full Trading | GitHub Secrets → VPS env |
| `backtest` | Local Mac | Any | None (offline) | N/A |

---

## 3. Exchange-Agnostic Credential Design

The engine is **exchange-agnostic**. The `.env` file stores **generic credential slots** — not exchange-specific ones. The exchange itself (Bybit, KuCoin, Binance, etc.) is declared in the pipeline YAML:

```yaml
# configs/pipelines/dev.yml
pipeline:
  execution:
    exchange: "bybit"   ← ccxt adapter, from YAML
```

```env
# .env — generic slots, no exchange name in the key
EXCHANGE_READONLY_API_KEY=xxx
EXCHANGE_READONLY_API_SECRET=yyy

EXCHANGE_LIVE_API_KEY=xxx      # PROD only — left empty locally
EXCHANGE_LIVE_API_SECRET=yyy
```

**To switch from Bybit → KuCoin:**
1. Update `exchange: "kucoin"` in the pipeline YAML
2. Swap the key/secret values in `.env` (or GitHub Secrets for UAT/PROD)
3. Zero Python code changes required

**Why `READONLY` vs `LIVE`, not `DEV` vs `PROD`?**

Both the `dev` (local) and `uat` (VPS) environments use the **read-only key** — they are both paper-trading environments. Only `prod` uses a live-trading key. The semantic distinction is **permission level**, not deployment environment.

---

## 4. The `LOG_LEVEL` Variable

The `LOG_LEVEL` variable in `.env` controls the **Loguru dual-sink behavior** — it is NOT the environment label:

| Value | Console Sink | Console Level | JSON Sink | Used In |
|---|---|---|---|---|
| `debug` | ✅ Enabled | `DEBUG` (verbose) | ✅ Enabled | Local DEV |
| `info` | ✅ Enabled | `INFO` (quiet) | ✅ Enabled | UAT / PROD VPS |
| `silent` | ❌ Disabled | — | ✅ Enabled | pytest (Airplane Mode) |

Your **local `.env`** should always have `LOG_LEVEL=debug`.  
Your **VPS `.env`** (injected by GitHub Actions) should have `LOG_LEVEL=info`.

---

## 5. GitHub Actions Secret Management (UAT & PROD)

Secrets for cloud environments are **never** stored in `.env` files on the VPS. The deployment workflow injects them as OS environment variables at runtime:

```
GitHub Repository Secrets
├── UAT_EXCHANGE_READONLY_API_KEY
├── UAT_EXCHANGE_READONLY_API_SECRET
├── UAT_TELEGRAM_BOT_TOKEN
├── UAT_TELEGRAM_CHAT_ID
├── PROD_EXCHANGE_LIVE_API_KEY
├── PROD_EXCHANGE_LIVE_API_SECRET
├── PROD_TELEGRAM_BOT_TOKEN
└── PROD_TELEGRAM_CHAT_ID
```

The GitHub Actions deployment workflow generates an ephemeral `.env` file on the VPS during each deploy, populated from these secrets. The file is never committed or persisted between deploys.

---

## 6. The Canonical Local `.env` Template

The repository ships with a `.env.example` (committed, no real values) that every developer clones and fills in:

```env
# ─── Logger Behavior ────────────────────────────────────────────
# debug  = verbose console output for local development
# info   = quiet console output for VPS deployment
# silent = no console output (pytest Airplane Mode)
LOG_LEVEL=debug

# ─── Exchange Credentials ────────────────────────────────────────
# The exchange adapter is declared in configs/pipelines/*.yml
# These slots are exchange-agnostic — just swap keys when switching.

# Read-Only key: used by DEV (local) and UAT (VPS paper trading)
EXCHANGE_READONLY_API_KEY=
EXCHANGE_READONLY_API_SECRET=

# Live-Trading key: used by PROD only. Leave empty locally.
EXCHANGE_LIVE_API_KEY=
EXCHANGE_LIVE_API_SECRET=

# ─── Telegram ────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```
