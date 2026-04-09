# V2 LLM Agent Protocol: The Orchestrator

This document is the **Agent's Instruction Manual**. Any LLM (Cursor, Aider, Devin, or custom agents) assigned to building this repository **MUST** read this file before writing a single line of code. Its objective is to prevent hallucinations, spaghetti code, and architectural degradation of the V2 system.

---

## 2. Anti-Hallucination Rule (Dependencies and Human Reliance)

LLMs tend to solve problems by importing arbitrary generic libraries (E.g., `requests` instead of `httpx`, or `pymysql` instead of the base SQLite ORM).

*   **Prohibition of Inventiveness:** If a module seems to require a third-party dependency not explicitly authorized in the Architecture (Section 4 of the Manifesto: `ccxt`, `aiosqlite`, `pyarrow`, `pandas`, `numpy`, `statsmodels`, `networkx`, `loguru`, `SQLAlchemy`, `pydantic`), the Agent MUST stop immediately.
*   **Network Rate Limits Rule:** When importing `ccxt`, it is strictly mandatory to instantiate exchanges with `enableRateLimit=True` and encapsulate all massive download loops with async delay wrappers, preventing default parallelization from breaking the Exchange's HTTP 429 limits.
*   **Mandatory Consultation:** The Agent must issue a message to the Human detailing the block and requesting authorization before adding any new tool to the environment.
*   **Surgical File Constraints:** Your modifications must be STRICTLY limited to the file or module mentioned in the current task. Modifying unrequested adjacent files is a critical violation of the protocol. Do not fall into the "Massive Refactoring Mirage".
*   **Anti-Verbosity Identity (System Prompt):** You are a quantitative execution machine, not a tutor. You are strictly prohibited from explaining the code, giving preambles, or greeting. Your only permitted output is refactored code, pytest tests, and terminal commands. Be laconic and surgically precise.

---


## 4. Cyclical Formatting and Styling
*   **Context Maintenance:** In each new session window, the Agent will use the `git log main -n 10` protocol alongside cross-reading files in `PLAN/` to reorient itself before committing a single line.
*   **Active Comments:** Any dense mathematical block or obscure technique (like an offloading of `pandas.corr()`) must carry an explicit comment block explaining the *why*, strictly following the "AI-Friendly Code" guideline.

---


## 5. The Ignition Prompt (Engine Startup)

Given the use of high-context LLMs like Gemini, to kickstart the construction of this system (once the documents in `PLAN/` are ready), the Human must send **EXACTLY** this text block to the LLM to initialize Phase 1 without causing collapse:

```text
[V2 INITIALIZATION MASTER DIRECTIVE]

I have uploaded a folder named PLAN/ containing the architectural documents for our Statistical Arbitrage Engine. This is your Bible.

Step 1: Exhaustively read all the documents in silence. Ingest the rules of the Coding Manifesto (01) and the Agent Protocol. Map mentally how the asynchronous engine interacts with the mathematical model.

Step 2: Do NOT write any execution code yet.

Step 3: Your only active task right now is to execute Phase 1 (Central Infrastructure).

Set up the base directory structure according to the structural documents.

Write the src/core/logger.py file implementing strict Loguru standardization (Sinks A, B, C, D, with enqueue=True, diagnose=False).

Implement the Pydantic validation model for the LogContext and ensure that logging relies exclusively on .bind().

Write the corresponding test in tests/core/test_logger.py to ensure the JSONL writes correctly under stress.

Remember your system directive: Do not explain what you are going to do. Simply write the infrastructure, run the test, ensure it passes, and return a laconic confirmation report stating that Phase 1 is ready. Initiate.
```
