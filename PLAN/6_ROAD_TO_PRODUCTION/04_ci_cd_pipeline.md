# CI/CD Pipeline: From Hobby Project to Production System

## The Problem

Right now, every operation in this system is manual:

- Running tests? → You remember to type `PYTHONPATH=. pytest tests/ -v`
- Deploying to VPS? → SSH in, `git pull`, restart the service, hope nothing broke
- Checking if the ghost trader is alive? → SSH in, check systemd status, SSH out
- Generating reports? → SSH in, run the script, copy the output somewhere
- Validating code works? → You trust your memory that you ran tests before pushing

This is how projects die. Not with a crash, but with a slow drift into "I'll fix it later" → "I forgot what state the VPS is in" → "I'll start a new project instead."

**The fix: automated pipelines that enforce discipline without willpower.**

---

## Pipeline Architecture

Five pipelines form a **promotion ladder** — code must pass each gate before reaching the next:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      GitHub Actions (CI/CD)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Pipeline 1: TEST GATE              ← Every push                    │
│  ├─ Lint (ruff)                                                     │
│  ├─ All offline tests (auto-discovered, not hardcoded)              │
│  └─ Fast feedback: ~60 seconds                                      │
│                                                                     │
│  Pipeline 2: TURBO INTEGRATION      ← Manual trigger / nightly      │
│  ├─ Turbo mode (1m candles, 5 ticks, ~6 min)                       │
│  ├─ Tests mechanical correctness of the full pipeline               │
│  └─ Artifacts: turbo DB + report JSON                               │
│                                                                     │
│  Pipeline 3: LOCAL 4H VALIDATION    ← Manual trigger (pre-deploy)   │
│  ├─ Production candles (4H), 2 ticks (~8 hours)                     │
│  ├─ Validates real signal quality on calibrated timeframe            │
│  ├─ Runs locally (Mac) or on VPS via SSH                            │
│  └─ The "real" test before going live                               │
│                                                                     │
│  Pipeline 4: DEPLOY                 ← Manual trigger (after P3 ✅)  │
│  ├─ SSH into Oracle Cloud VPS                                       │
│  ├─ git pull → pip install → systemd restart                        │
│  └─ Health check (verify process is alive after 30s)                │
│                                                                     │
│  Pipeline 5: HEALTH MONITOR         ← Scheduled (every 6 hours)     │
│  ├─ SSH into VPS, check systemd status + data freshness             │
│  ├─ Run ghost_report --json, upload as artifact                     │
│  └─ Pipeline fails = GitHub sends you a notification                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### The Promotion Ladder

```
   Code Change
       │
       ▼
  ┌─────────┐     Automatic on every push
  │  P1 Test │──── "Does it compile and pass all offline tests?"
  └────┬─────┘
       │ ✅
       ▼
  ┌──────────┐    Manual or nightly
  │  P2 Turbo │──── "Does the full pipeline work mechanically?"
  └────┬──────┘     (1m candles, 5 ticks, ~6 min)
       │ ✅
       ▼
  ┌────────────┐  Manual (pre-deploy gate)
  │  P3 Local  │── "Do real 4H signals behave correctly?"
  │   4H Test  │   (2 ticks, ~8 hours, using actual calibrated timeframe)
  └────┬───────┘
       │ ✅
       ▼
  ┌──────────┐    Manual trigger
  │ P4 Deploy │──── "Push to VPS, restart service"
  └────┬──────┘
       │
       ▼
  ┌───────────┐   Automatic every 6 hours
  │ P5 Health  │── "Is it still alive? Is the data fresh?"
  └────────────┘
```

---

## Pipeline 1: Test Gate

**Trigger:** Every push to any branch
**Purpose:** Catch broken code instantly. Zero cognitive load after setup.
**Cost:** Free (GitHub Actions: 2,000 min/month for private repos)
**Runtime:** ~60 seconds

### What It Runs

```yaml
# Step 1: Lint
ruff check src/ scripts/ tests/

# Step 2: ALL offline tests (auto-discovered — grows with the codebase)
PYTHONPATH=. ENV=test pytest tests/ -v -m "not live" --tb=short
```

Tests are auto-discovered by pytest, not hardcoded. As you add new test files under `tests/`, they're automatically included. The only filter is `-m "not live"` which excludes the `@pytest.mark.live` tests that need exchange API keys.

### Test Separation

Tests naturally split into two categories:

| Category | Marker | Needs API Keys | Needs Network | Runs in CI |
|----------|--------|----------------|---------------|------------|
| **Offline** (unit + computation) | *(default)* | No | No | ✅ Always |
| **Live** (exchange connectivity) | `@pytest.mark.live` | Yes (Bybit) | Yes | Only in P2/P3 |

When you write new tests:
- **No marker needed** for offline tests — they're included automatically
- **Add `@pytest.mark.live`** only if the test calls a real exchange API

### Why This Matters

You push code, you get a ✅ or ❌ within 60 seconds. No thinking required. If you do nothing else on this page, **do this one.**

---

## Pipeline 2: Turbo Integration Test

**Trigger:** Manual dispatch (`workflow_dispatch`) or nightly schedule
**Purpose:** Verify the full fetch → signal → SQLite → report pipeline works mechanically
**Requires:** `BYBIT_API_KEY` and `BYBIT_API_SECRET` as GitHub Secrets
**Runtime:** ~8 minutes (60s sleep × 5 ticks + fetch overhead)

### What It Runs

```yaml
# Step 1: All offline tests
PYTHONPATH=. ENV=test pytest tests/ -v -m "not live" --tb=short

# Step 2: Live connectivity tests
PYTHONPATH=. pytest tests/ -v -m "live" --tb=short

# Step 3: Turbo mode (1m candles, 5 ticks, auto-stop)
PYTHONPATH=. python -m scripts.ghost_trader --turbo

# Step 4: Generate report from turbo DB
PYTHONPATH=. python -m scripts.ghost_report --turbo --json > turbo_report.json
PYTHONPATH=. python -m scripts.ghost_report --turbo --export

# Step 5: Upload artifacts (downloadable from GitHub for 90 days)
# → turbo_report.json
# → data/ghost/trades_turbo.db
# → data/ghost/reports/*
```

### What This Catches (That Unit Tests Miss)

- Exchange API changes (CCXT version drift, symbol delistings)
- Data format changes from Bybit that break the DataFrame pipeline
- Signal engine producing NaN/inf on real market data
- SQLite schema issues with real data volumes
- Pairs delisted from exchange (PUMP/USDT → graceful skip)

### When to Run It

- **Nightly (recommended):** Catch API breakage within 24 hours
- **Before any deployment:** Always validate before updating the VPS
- **After CCXT/dependency upgrades:** The most common source of live breakage

### Important Distinction

Turbo mode uses **1m candles**, but the pairs were calibrated on **4H data**. The signals in turbo are **mechanically valid but statistically meaningless** — they prove the pipeline works, not that the strategy works. That's what Pipeline 3 is for.

---

## Pipeline 3: Local 4H Validation (The Real Test)

**Trigger:** Manual dispatch only — you trigger this deliberately before deploying
**Purpose:** Validate real signals on the calibrated 4H timeframe against live market data
**Requires:** Exchange API keys + patience (~8 hours for 2 ticks)
**Runtime:** ~8 hours (2 × 4H candle boundaries)

### Why This Exists

There's a dangerous gap between "turbo works" and "deploy to VPS":

| | Turbo (P2) | Local 4H (P3) | VPS Production |
|---|---|---|---|
| Candle timeframe | 1m | **4H** | 4H |
| Signal validity | Mechanical only | **Real** | Real |
| Duration | ~6 min | **~8 hours** | Weeks |
| Risk of bad deploy | High | **Low** | N/A |

Without P3, your first real 4H tick happens on the VPS — if it crashes, you have to SSH in and debug remotely. With P3, you've already seen 2 real ticks succeed locally.

### What It Runs

This pipeline requires a code change to `ghost_trader.py`: a new `--ticks N` flag that auto-stops after N ticks in production mode (like `--turbo` does with `TURBO_MAX_TICKS`).

```bash
# Run locally on your Mac (or triggered via GitHub Actions → SSH to VPS)
PYTHONPATH=. python -m scripts.ghost_trader --ticks 2
```

This will:
1. Sleep until the next 4H candle boundary (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)
2. Execute tick 1 — fetch 4H candles for all 13 Tier 1 pairs, generate signals, write to SQLite
3. Sleep until the next 4H boundary
4. Execute tick 2
5. Auto-stop

Then validate:

```bash
# Generate report from validation run
PYTHONPATH=. python -m scripts.ghost_report --detailed

# Check the signal quality
PYTHONPATH=. python -m scripts.ghost_report --json | python3 -c "
import json, sys
r = json.load(sys.stdin)
print(f'Status: {r[\"status\"]}')
print(f'Open positions: {r[\"active_pairs\"]}')
print(f'Tick signals: {r[\"signal_quality\"][\"total_signals_recorded\"]}')
print(f'Bar interval: {24*365/r[\"bars_per_year\"]:.1f}h (should be ~4.0)')
"
```

### Running as a GitHub Actions Workflow

For CI, this pipeline can SSH into the VPS (or a self-hosted runner) and run the ghost trader with `--ticks 2`. The workflow would have a timeout of 10 hours (GitHub Actions max is 6h for free tier, but you can use a self-hosted runner with no limit).

**Practical recommendation:** Run this locally on your Mac the first time. Once you trust it, optionally wrap it in a GitHub Actions workflow that SSHs into the VPS for future validations.

### Validation Checklist (Auto-Verified by Report)

- [ ] Bar interval detected as ~4.0h (not 0.0h turbo)
- [ ] At least 1 signal resulted in ENTRY or EXIT (not all SKIPs)
- [ ] No NaN/inf in Z-scores
- [ ] Tick signals count = (number_of_active_pairs × 2 ticks)
- [ ] Process shut down cleanly (no crash)

---

## Pipeline 4: Deploy

**Trigger:** Manual dispatch (after P3 validates successfully)
**Purpose:** Zero-SSH deployments — you click a button, the VPS updates
**Requires:** SSH key to VPS as GitHub Secret

### What It Runs

```yaml
# Step 1: Run test gate (fast fail)
PYTHONPATH=. ENV=test pytest tests/ -v -m "not live" --tb=short

# Step 2: SSH into VPS and deploy
ssh oracle-vps << 'DEPLOY'
  cd ~/quant
  git fetch origin main
  git reset --hard origin/main
  .venv/bin/pip install -r requirements.txt --quiet
  sudo systemctl restart ghost-trader
  sleep 10
  sudo systemctl is-active ghost-trader
DEPLOY

# Step 3: Post-deploy health check
ssh oracle-vps << 'CHECK'
  cd ~/quant
  sqlite3 data/ghost/trades.db "SELECT COUNT(*) FROM equity_snapshots;"
  PYTHONPATH=. .venv/bin/python -m scripts.ghost_report --json | head -5
CHECK
```

### Why Manual Trigger (Not Auto on Push to Main)

For a trading system, auto-deploy is dangerous:
- A code change might alter signal behavior mid-trade
- You might push a doc change to main and accidentally restart the ghost trader during a candle window
- You want to control *when* the VPS restarts (ideally right after a candle close, giving maximum time before the next one)

**Manual trigger = you decide when to deploy.** You can still do it from your phone via the GitHub app.

### Safety Rails

- Tests must pass before the deploy step runs
- If `systemctl is-active` returns failure, the pipeline fails → notification
- `git reset --hard` ensures the VPS is always an exact mirror of `main`

---

## Pipeline 5: Health Monitor (The Watchdog)

**Trigger:** Scheduled — every 6 hours via cron (`0 1,7,13,19 * * *`)
**Purpose:** Detect silent failures before they cost you data
**Requires:** SSH key to VPS

### What It Checks

```yaml
# 1. Is the process alive?
ssh oracle-vps "sudo systemctl is-active ghost-trader"

# 2. Is the data fresh? (last snapshot within 6 hours)
ssh oracle-vps "cd ~/quant && sqlite3 data/ghost/trades.db \
  \"SELECT CASE WHEN \
    (julianday('now') - julianday(MAX(timestamp))) * 24 > 6 \
    THEN 'STALE' ELSE 'FRESH' END FROM equity_snapshots;\""

# 3. Generate and upload latest report
ssh oracle-vps "cd ~/quant && PYTHONPATH=. .venv/bin/python -m scripts.ghost_report --json" \
  > latest_report.json

# 4. Upload as GitHub Actions artifact (downloadable for 90 days)
```

### Alert Conditions (Pipeline Fails = You Get Notified)

| Condition | Detection | What Happens |
|-----------|-----------|--------------|
| Process crashed | `systemctl is-active` ≠ active | Pipeline fails → email notification |
| Data stale (>6h) | SQLite timestamp check | Pipeline fails → investigate |
| Max DD > 30% | Parse report JSON | Pipeline fails → manual review |

### Why This Matters

The ghost trader sleeps 99.97% of the time. When it crashes at 2 AM, nothing visibly happens — it just silently stops collecting data. Without a watchdog, you might not notice for a week.

With this pipeline, GitHub sends you an email the moment something goes wrong.

---

## Code Changes Required

### Ghost Trader Enhancement: `--ticks N` Flag

For Pipeline 3 (Local 4H Validation), the ghost trader needs a `--ticks N` flag that works in production mode:

```python
# Current: only turbo has auto-stop
parser.add_argument("--turbo", action="store_true", ...)

# New: --ticks works in both modes
parser.add_argument("--ticks", type=int, default=None,
    help="Auto-stop after N ticks. If omitted, runs forever (production default).")
```

This way:
- `--turbo` = 1m candles, 60s sleep, auto-stop at 5 ticks (unchanged)
- `--turbo --ticks 10` = turbo mode but 10 ticks instead of 5
- `--ticks 2` = production 4H candles, auto-stop after 2 ticks (Pipeline 3)
- *(no flags)* = production 4H candles, runs forever (VPS deployment)

---

## Implementation Roadmap

### Phase A: Test Gate (Do This First — Zero Dependencies)

**Files to create:**
```
.github/workflows/test.yml
requirements-dev.txt
```

**Estimated effort:** 30 minutes
**Dependencies:** Nothing — works immediately

---

### Phase B: Turbo Integration + `--ticks` Enhancement

**Files to create/modify:**
```
.github/workflows/integration.yml
scripts/ghost_trader.py               ← Add --ticks flag
```

**GitHub Secrets to add:**
```
BYBIT_API_KEY
BYBIT_API_SECRET
```

**Estimated effort:** 30 minutes

---

### Phase C: Local 4H Validation

**Files to create:**
```
.github/workflows/validate_4h.yml    ← Optional (can just run locally)
```

No additional secrets needed — uses the same exchange keys as P2.

**Estimated effort:** 15 minutes (mostly documentation)

---

### Phase D: Deploy Pipeline (After VPS Is Set Up)

**Files to create:**
```
.github/workflows/deploy.yml
```

**GitHub Secrets to add:**
```
VPS_HOST                  ← Oracle Cloud public IP
VPS_SSH_KEY              ← Private SSH key for the VPS
VPS_USER                 ← opc (Oracle Linux) or ubuntu
```

**Estimated effort:** 30 minutes

---

### Phase E: Health Monitor (After Ghost Trader Is Running on VPS)

**Files to create:**
```
.github/workflows/health.yml
```

**Estimated effort:** 20 minutes

---

## GitHub Actions Specifics

### Free Tier Limits (Private Repo)

| Resource | Free Allocation | Our Estimated Usage |
|----------|----------------|---------------------|
| **Minutes/month** | 2,000 | ~200 (P1: ~1min × ~60 pushes + P5: ~1min × 120 checks) |
| **Storage (artifacts)** | 500 MB | ~50 MB (turbo DBs + report JSONs) |
| **Concurrent jobs** | 20 | 1-2 |

Nowhere close to limits.

### Secrets & Environments Management

To prevent variable collisions between Epoch 3 and Epoch 4 (e.g., trying to name things `GHOST_VPS_HOST` vs `PROD_VPS_HOST`), we utilize **GitHub Environments**.

Instead of storing server-specific keys as generic Repository Secrets, we compartmentalize them into specific Environments:

1. **`ghost-trader` Environment:** Contains `VPS_HOST`, `VPS_USER`, and `VPS_SSH_KEY` for the paper-trading Oracle VPS.
2. **`production-trader` Environment:** Will contain the exact same variable names, but populated with the IP and Keys for the Epoch 4 real-money server.

Our GitHub Actions workflows (`deploy.yml` and `health.yml`) include the `environment: ghost-trader` parameter, dynamically routing to the right variables without explicitly prefixing secret names in our code:

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ghost-trader
    steps:
      - run: echo "${{ secrets.VPS_HOST }}" # Automatically points to the Ghost IP!
```

> [!IMPORTANT]
> The `BYBIT_API_KEY` and `BYBIT_API_SECRET` remain as **Repository Secrets** since they are safely shared across integration pipelines. For production (Epoch 4), we can utilize Environment-level secrets to securely isolate the real-money sub-account API keys.

---

## File Changes Summary

### New Files

| File | Pipeline | Purpose |
|------|----------|---------|
| `.github/workflows/test.yml` | P1 | Test gate on every push |
| `.github/workflows/integration.yml` | P2 | Turbo smoke test (manual/nightly) |
| `.github/workflows/validate_4h.yml` | P3 | Local 4H validation (manual) |
| `.github/workflows/deploy.yml` | P4 | Deploy to VPS (manual) |
| `.github/workflows/health.yml` | P5 | Scheduled watchdog every 6h |
| `requirements-dev.txt` | — | Dev-only dependencies (ruff) |

### Modified Files

| File | Change |
|------|--------|
| `scripts/ghost_trader.py` | Add `--ticks N` flag for controlled-duration runs |

---

## What NOT to Automate

| Action | Why Manual |
|--------|-----------|
| **Epoch transitions** (3 → 4) | Requires human judgment on strategy viability |
| **Pair universe updates** | Re-running `discover_pairs.py` should be a deliberate decision |
| **Parameter tuning** | Changing Z-score/lookback is a quantitative decision, not a deployment task |
| **Initial VPS setup** | One-time operation, not worth automating |
| **Database backups** | Handled by cron on the VPS, not GitHub Actions |

---

## The Discipline Contract

Setting up these pipelines is making a commitment to yourself:

1. **Tests run on every push** — you always know if things are broken
2. **Turbo validates the pipeline mechanically** — before you trust it with real time
3. **4H validation proves the signals work** — before you run it unsupervised for weeks
4. **Deployments are one-click** — no SSH, no "I forgot to pip install"
5. **Failures are visible** — email notifications mean you can't ignore problems
6. **Reports are archived** — every 6h health check produces a downloadable artifact

This is the difference between "I have a trading bot" and "I operate a trading system."
