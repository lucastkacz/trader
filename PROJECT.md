# Crypto StatArb Project Documentation

## 1. Overview
This project is a professional-grade statistical arbitrage trading system for cryptocurrency markets. It is built using Python and follows a strict **Modular Monolith** architecture to ensure safety, testability, and scalability without the complexity of microservices.

## 2. Architecture: Modular Monolith
The system is divided into distinct layers with strict boundaries. Access generally flows downwards (Services -> Domain -> Core) or outwards to Infra.

### Layers (`src/statarb/`)
1.  **Core (`core/`)**:
    *   **Purpose**: The bedrock of the system. Contains pure Python primitives, types, and constants.
    *   **Constraints**: No internal dependencies, NO I/O, NO external library heaviness.
    *   **Components**: Configuration (`config.py`), Event definitions, Error types.

2.  **Domain (`domain/`)**:
    *   **Purpose**: Pure business logic and mathematical models.
    *   **Constraints**: Pure functions only. No database access, no API calls.
    *   **Components**:
        *   `models/`: Canonical data models (e.g., `Candle` Pydantic model).
        *   `analytics/`: Maths for Z-Score, Cointegration, etc.

3.  **Infrastructure (`infra/`)**:
    *   **Purpose**: All implementations of Input/Output. Adapters for the "outside world".
    *   **Components**:
        *   `market_data/`: CCXT wrappers to fetch and normalize data.
        *   `lakehouse/`: Storage engine (Parquet Writer + DuckDB Reader).
        *   `observability/`: Structured logging and metrics.

4.  **Services (`services/`)**:
    *   **Purpose**: Orchestration layer. Glues Infra and Domain together to perform workflows.
    *   **Components**: Ingestion loops, Feature calculation pipelines, Signal generation, Order execution.

5.  **Applications (`apps/`)**:
    *   **Purpose**: Entry points to the system.
    *   **Components**: CLI tools, Live Trading Bot, Dashboards.

## 3. Key Architectural Decisions

### Data Lakehouse (Hive Partitioning)
*   **Decision**: Store market data in a Hive-partitioned directory structure using Parquet files, managed by DuckDB.
*   **Structure**: `data/lake/exchange={ex}/timeframe={tf}/symbol={sym}/data.parquet`
*   **Reasoning**: 
    *   **Performance**: DuckDB enables extremely fast "pruning" ensures we only read the specific files needed for a query.
    *   **Maintainability**: Deleting or fixing a symbol is as easy as deleting a folder.
    *   **Scalability**: Parquet is highly compressed and columnar, ideal for time-series.
    *   **Deduplication**: We implemented a custom "Upsert" logic using DuckDB to prevent duplicate candles.

### Configuration (`pyproject.toml` & `config/`)
*   **Tooling**: Moved to `pyproject.toml` for a modern, unified configuration of tools (`ruff`, `pytest`, `mypy`).
*   **App Config**: Environment-based YAML Configuration (`local.yaml`, `live.yaml`) loaded via Pydantic Settings.
    *   **Safety**: `live` execution is disabled by default in code.

### "Lib" to "Src" Refactor
*   **Decision**: Deleted the legacy unstructured `lib/` folder and moved all code to `src/statarb/`.
*   **Reasoning**: Standard python package structure prevents import errors, ensures separation of concerns, and simplifies packaging/distribution.

## 4. Current State (Phase 1 Complete)
*   **Branch**: `data`
*   **Completed**:
    *   Project Skeleton established.
    *   Canonical `Candle` model defined.
    *   `ParquetWriter` and `DuckDBReader` implemented and tested.
    *   Legacy imports fixed and extraneous documentation removed.

## 5. Directory Tree
```text
trading_system/
├── config/                 # Runtime Configuration (YAML)
├── src/
│   └── statarb/
│       ├── core/           # Config, Types
│       ├── domain/         # Models (Candle), Logic
│       ├── infra/          # Lakehouse (Reader/Writer), Logger
│       ├── services/       # (Orchestration - Pending)
│       └── apps/           # (CLI, Bot - Pending)
├── tests/                  # Unit and Integration Tests
├── pyproject.toml          # Dependencies & Tooling
└── PROJECT.md              # This Documentation
```
