# V2 LLM Agent Protocol: The Orchestrator

This document is the **Agent's Instruction Manual**. Any LLM (Cursor, Aider, Devin, or custom agents) assigned to building this repository **MUST** read this file before writing a single line of code. Its objective is to prevent hallucinations, spaghetti code, and architectural degradation of the V2 system.

---

## 3. Restrictive Testing Protocol (The TDD Flow)

No production function can exist without the Agent first proving that it is mathematically sound and resistant to network failures. Strict use of `pytest` is mandated.

The Agent will operate under the following strictly cyclical sequence:
1.  **Writing the Test (Test First):** Before touching `/src/`, the Agent writes the test function in `/tests/` describing what the yet-to-exist function must do, injecting edge-case variables and mocking the network.
2.  **Failure Verification:** The Agent runs the test and explicitly verifies that it fails.
3.  **Early Implementation:** The Agent writes the actual production code in `/src/` strictly to satisfy and pass the written test.
4.  **Safe Refactoring:** Once the test is green, optimization begins (Vectorization, Thread Offloading).
5.  **Edge Cases and Network Mocking:** The LLM must explicitly generate corrupt DataFrames (with `NaN` gaps, zeros, or strings) and inject them to confirm the application fails gracefully, rather than causing OOM. Network APIs must NEVER be called natively in tests.
6.  **"Ghost" Dependencies in Tests:** Accompanying the async and TDD constraints, the Agent must not assume that plugins like `pytest-asyncio` are already configured in the environment. It must explicitly verify and install async testing dependencies to avoid tests being silently skipped.
7.  **The Agent's "Fail-Fast" (Anti-Loop):** If a test fails for 3 consecutive code iterations, the Agent is STRICTLY FORBIDDEN from continuing to try and patch it. It must execute `git reset --hard` to revert the code to the last functional commit, halt its execution, and issue a message to the Human detailing the mathematical deadlock.
