# Deployment Guide: Ghost Trader Infrastructure

This document covers the complete deployment strategy for running the Epoch 3 Paper-Tracer (Ghost Trader), both locally for rapid validation and on a cloud VPS for the mandated 3-4 week forward test.

---

## Part 1: Local Deployment (Rapid Validation)

Before committing to a VPS, the ghost trader must be validated locally on your Mac. Start with Turbo Mode (minutes), then graduate to production mode (hours).

### Prerequisites

```bash
cd ~/Documents/quant
source .venv/bin/activate

# Ensure .env exists with your exchange API credentials
cat .env
# Must contain at minimum:
# BYBIT_API_KEY=your_key
# BYBIT_API_SECRET=your_secret
# GHOST_EXCHANGE=bybit
```

### Step 0: Verify Exchange Connectivity

Before anything else, confirm the API connection works:

```bash
PYTHONPATH=. .venv/bin/pytest tests/data/test_live_client.py -v -s
```

This runs 3 tests: 4H candles, 1m candles, and a Tier 1 pair check. All must pass.

### Step 1: Turbo Mode (Quick Integration Test)

Turbo mode uses **1m candles** and a **60-second sleep cycle** to validate the entire pipeline in ~5 minutes. It auto-stops after 5 ticks and writes to an isolated database (`data/ghost/trades_turbo.db`).

```bash
PYTHONPATH=. .venv/bin/python -m scripts.ghost_trader --turbo
```

| Setting | Production | Turbo |
|---------|-----------|-------|
| Timeframe | 4h | 1m |
| Sleep cycle | ~4 hours | 60 seconds |
| Auto-stop | Never (runs forever) | After 5 ticks |
| Database | `data/ghost/trades.db` | `data/ghost/trades_turbo.db` |

> **⚠️ NOTE:** Turbo mode signals are not meaningful — the pairs were calibrated on 4H data. It exists purely to verify that fetch → signal → SQLite → report all work mechanically without crashing.

After turbo completes, verify the database populated correctly:

```bash
# Check the turbo database
sqlite3 data/ghost/trades_turbo.db ".tables"
sqlite3 data/ghost/trades_turbo.db "SELECT COUNT(*) FROM ghost_orders;"
sqlite3 data/ghost/trades_turbo.db "SELECT COUNT(*) FROM equity_snapshots;"

# Run the report (it reads the production DB by default,
# point it at the turbo DB by temporarily setting GHOST_DB_PATH)
GHOST_DB_PATH=data/ghost/trades_turbo.db PYTHONPATH=. .venv/bin/python -m scripts.ghost_report
```

If turbo passes, move to production mode.

### Step 2: Production Mode (4H Candles)

#### Option A: Foreground (Interactive Debugging)

```bash
PYTHONPATH=. .venv/bin/python -m scripts.ghost_trader
```

The script will log the next 4H boundary it is sleeping until, then wake and execute. You can watch the output in real-time and `Ctrl+C` to kill it. Useful for verifying the first 1-2 ticks work correctly.

#### Option B: Background with nohup (Overnight Test)

```bash
nohup .venv/bin/python -m scripts.ghost_trader > logs/ghost_local.log 2>&1 &
echo $! > ghost.pid

# Check if it's running
cat ghost.pid | xargs ps -p

# View live logs
tail -f logs/ghost_local.log

# Kill it when done
kill $(cat ghost.pid) && rm ghost.pid
```

#### Option C: launchd Daemon (Mac-Native, Survives Reboots)

For multi-day local testing without worrying about terminal sessions:

```bash
# Create the plist
cat > ~/Library/LaunchAgents/com.quant.ghost-trader.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.quant.ghost-trader</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/lucastkacz/Documents/quant/.venv/bin/python</string>
        <string>-m</string>
        <string>scripts.ghost_trader</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/lucastkacz/Documents/quant</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>/Users/lucastkacz/Documents/quant</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/lucastkacz/Documents/quant/logs/ghost_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/lucastkacz/Documents/quant/logs/ghost_stderr.log</string>
</dict>
</plist>
EOF

# Load and start
launchctl load ~/Library/LaunchAgents/com.quant.ghost-trader.plist

# Check status
launchctl list | grep ghost

# Stop and unload
launchctl unload ~/Library/LaunchAgents/com.quant.ghost-trader.plist
```

### Local Validation Checklist

Before moving to VPS, confirm every item:

- [ ] Script boots and correctly calculates the next UTC 4H boundary
- [ ] First tick successfully fetches candles for all 13 Tier 1 pairs via CCXT
- [ ] Signal engine produces valid Z-scores and volatility parity weights
- [ ] SQLite `trades.db` is created at `data/ghost/trades.db` with correct schema
- [ ] At least one ghost order is written (entry or hold) on the first tick
- [ ] Equity snapshots are recorded per tick
- [ ] `ghost_report.py` reads the database and prints a coherent summary
- [ ] Process survives at least 2 consecutive 4H ticks without crashing
- [ ] Loguru JSONL sink captures structured ghost trading events
- [ ] `Ctrl+C` or `kill` results in clean shutdown (no corrupted SQLite)

### Quick Diagnostic Commands

```bash
# Inspect the trade database
sqlite3 data/ghost/trades.db ".tables"
sqlite3 data/ghost/trades.db "SELECT * FROM ghost_orders ORDER BY timestamp_open DESC LIMIT 5;"
sqlite3 data/ghost/trades.db "SELECT * FROM equity_snapshots ORDER BY timestamp DESC LIMIT 10;"

# Run the report
PYTHONPATH=. .venv/bin/python -m scripts.ghost_report
```

---

## Part 2: VPS Deployment (The 3-4 Week Forward Test)

### Binance API Access & Geolocation

#### Argentina: Fully Authorized ✅

Binance completed its official VASP (Virtual Asset Service Provider) registration with Argentina's CNV (Comisión Nacional de Valores) in October 2024. This means:

- **Full API access** from Argentine IPs is legally permitted
- Spot, Futures (USD-M), and P2P services are all available
- No VPN/proxy workarounds needed — doing so would actually *violate* Binance ToS

#### VPS Region Selection (Critical)

Binance actively monitors and blocks API requests from restricted jurisdictions (US, Iran, North Korea, etc.). Your VPS IP address **must** originate from a permitted country.

**Recommended VPS regions (in priority order):**

| Region | Provider | Latency to Binance | Notes |
|--------|----------|-------------------|-------|
| **São Paulo, Brazil** | Oracle Cloud (GRU) | ~15ms | Same continent, same timezone, fully permitted |
| **Frankfurt, Germany** | Oracle Cloud (FRA) | ~50ms | EU jurisdiction, no restrictions |
| **Tokyo, Japan** | Oracle Cloud (NRT) | ~5ms | Closest to Binance matching engines |
| Singapore | Oracle Cloud (SIN) | ~3ms | Closest to Binance, but verify current regulatory status |

> **⚠️ WARNING:** Do NOT deploy in a US-based region (Ashburn, Phoenix, Chicago, etc.). Binance will detect the datacenter IP and may freeze your account permanently. This is non-negotiable.

**Our recommendation: Oracle Cloud São Paulo (GRU).** Same continent, negligible latency, and since we only wake up every 4 hours, even 200ms latency is irrelevant. The timezone alignment also simplifies log reading.

---

### The Free VPS: Oracle Cloud Always Free Tier

Oracle Cloud offers a permanently free ARM-based VPS that is absurdly overpowered for our use case:

#### Always Free Specs

| Resource | Free Allocation | Our Requirement |
|----------|----------------|-----------------|
| **CPU** | 4 ARM OCPUs (Ampere A1) | <0.1 OCPU (script sleeps 99.97% of the time) |
| **RAM** | 24 GB | <500 MB (13 DataFrames in memory for ~2 seconds per tick) |
| **Storage** | 200 GB Block Volume | <1 GB (SQLite DB + Python env) |
| **Bandwidth** | 10 TB/month outbound | <100 MB/month (6 API calls/day × 13 pairs) |
| **Duration** | **Forever** | 3-4 weeks minimum |

This is not a trial. Oracle's Always Free tier is permanent for the lifetime of your account.

#### Account Setup

1. Go to [cloud.oracle.com](https://cloud.oracle.com) and create a free account
2. **Home Region:** Select **Brazil East (São Paulo)** — this cannot be changed later
3. You will need a credit/debit card for identity verification (no charge is made)
4. Once verified, navigate to **Compute → Instances → Create Instance**

#### Instance Configuration

```
Shape:          VM.Standard.A1.Flex (ARM)
OCPUs:          1 (of your 4 free)
Memory:         6 GB (of your 24 free)
Image:          Oracle Linux 8 (ARM) or Ubuntu 22.04 (ARM)
Boot Volume:    50 GB (of your 200 free)
```

> **💡 TIP:** If you get an "Out of capacity" error, try a different Availability Domain (AD) within the São Paulo region, or retry during off-peak hours (early morning UTC). This is a known issue with high-demand regions.

---

### Initial Server Setup

```bash
# SSH into your instance
ssh -i ~/.ssh/oracle_key opc@<your-public-ip>

# System updates
sudo dnf update -y          # Oracle Linux
# or: sudo apt update && sudo apt upgrade -y  # Ubuntu

# Install Python 3.11+
sudo dnf install python3.11 python3.11-pip git -y
# or: sudo apt install python3.11 python3.11-venv git -y

# Clone your repository
git clone <your-repo-url> ~/quant
cd ~/quant

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env file with your exchange API credentials
cat > .env << 'EOF'
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
GHOST_EXCHANGE=bybit
ENV=production
EOF

# Create required directories
mkdir -p data/ghost logs

# Verify connectivity
PYTHONPATH=. .venv/bin/pytest tests/data/test_live_client.py -v

# Run a turbo test to validate everything works
PYTHONPATH=. .venv/bin/python -m scripts.ghost_trader --turbo
```

---

### Running on VPS

#### systemd Service (Recommended — Auto-Restart, Boot Persistence)

```bash
sudo tee /etc/systemd/system/ghost-trader.service << 'EOF'
[Unit]
Description=Stat-Arb Ghost Trader (Epoch 3)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=opc
WorkingDirectory=/home/opc/quant
Environment="PYTHONPATH=/home/opc/quant"
ExecStart=/home/opc/quant/.venv/bin/python -m scripts.ghost_trader
Restart=on-failure
RestartSec=30
StandardOutput=append:/home/opc/quant/logs/ghost_stdout.log
StandardError=append:/home/opc/quant/logs/ghost_stderr.log

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable ghost-trader
sudo systemctl start ghost-trader

# Monitor
sudo systemctl status ghost-trader
journalctl -u ghost-trader -f
```

#### tmux Fallback (Simple, No Root)

```bash
tmux new-session -d -s ghost 'cd ~/quant && PYTHONPATH=. .venv/bin/python -m scripts.ghost_trader'

# Reattach later
tmux attach -t ghost
```

---

### Monitoring & Maintenance

#### Daily Health Check

```bash
# Is the process alive?
sudo systemctl status ghost-trader

# Recent structured logs
tail -20 ~/quant/logs/engine.jsonl | python3 -m json.tool

# Database state
sqlite3 ~/quant/data/ghost/trades.db "SELECT COUNT(*) as open FROM ghost_orders WHERE status='OPEN';"
sqlite3 ~/quant/data/ghost/trades.db "SELECT * FROM equity_snapshots ORDER BY timestamp DESC LIMIT 5;"

# Full diagnostic report
cd ~/quant && PYTHONPATH=. .venv/bin/python -m scripts.ghost_report
```

#### API Key Security

1. Generate API keys with **Read-Only** permission (no trading/withdrawal)
2. **Whitelist the VPS static IP** in the API key settings on your exchange
3. The ghost trader only reads market data — it never places real orders

> **⚠️ CRITICAL:** Since Epoch 3 is pure paper trading, the API keys should have READ-ONLY permissions. There is zero reason to enable trading permissions until Epoch 4.

#### Backup Strategy

The SQLite database is the single most valuable artifact of Epoch 3:

```bash
# Add to crontab (daily backup at midnight UTC)
crontab -e
0 0 * * * cp ~/quant/data/ghost/trades.db ~/quant/data/ghost/trades_backup_$(date +\%Y\%m\%d).db
```

---

### Cost Summary

| Item | Cost |
|------|------|
| Oracle Cloud VPS | **$0/month** (Always Free) |
| Binance API | **$0** (public market data) |
| Domain/SSL | Not needed |
| **Total** | **$0/month** |

---

### Alternative Free VPS Providers

If Oracle Cloud capacity is unavailable in São Paulo:

| Provider | Free Tier | Region Options | Limitations |
|----------|-----------|---------------|-------------|
| **Google Cloud** | e2-micro (0.25 vCPU, 1GB RAM) for 90 days | São Paulo available | Very limited RAM, expires |
| **AWS** | t2.micro (1 vCPU, 1GB RAM) for 12 months | São Paulo available | Expires after 1 year |
| **Hetzner** | No free tier, but €3.79/mo for CX22 | Frankfurt, Helsinki | Cheapest paid option, rock-solid |

Oracle Cloud remains the unambiguous winner for a free, permanent, overpowered VPS.
