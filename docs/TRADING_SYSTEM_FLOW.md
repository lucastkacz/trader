# Trading System Flow

Este documento explica visualmente cómo funciona el sistema en dos situaciones:

1. **Cold start:** todavía no existe un promoted pair artifact utilizable o hay
   que reconstruir los datos de research.
2. **Runtime normal:** el trader ya arrancó, cargó su artifact y está ejecutando
   ticks periódicos.

Combina comportamiento actual con el flujo objetivo necesario para completar un
cold start. Las etiquetas significan:

- **ACTUAL**: comportamiento presente en el código.
- **OBJETIVO**: contrato todavía no demostrado de punta a punta.
- `⚠`: gap identificado en
  [`PROJECT_REENTRY_AUDIT.md`](PROJECT_REENTRY_AUDIT.md).

El orden de corrección está en
[`current-roadmap.md`](current-roadmap.md). Este diagrama no es un
runbook ni habilita `live` o capital real.

## 1. Vista general

```mermaid
flowchart TD
    START([Operador inicia el sistema]) --> CHECK{¿Existe un promoted artifact<br/>válido para exchange + timeframe?}

    CHECK -- No --> COLD[OBJETIVO cold start<br/>actualmente bloqueado]
    COLD --> DATA[Construir o reutilizar<br/>historical market data]
    DATA --> DISCOVERY[Descubrir y estresar pares]
    DISCOVERY --> CANDIDATE[Candidate artifact]
    CANDIDATE --> REVIEW{Revisión manual<br/>del operador}
    REVIEW -- Rechazado --> COLD
    REVIEW -- Promovido --> PROMOTED[Promoted pair artifact]

    CHECK -- Sí --> BOOT[Execution boot]
    PROMOTED --> BOOT
    BOOT --> RECON[Boot reconciliation<br/>read-only]
    RECON --> LOOP[Runtime tick loop]
    LOOP --> STATE[(SQLite runtime state)]
    LOOP --> REPORTS[Reporting + Telegram]
    LOOP --> MODE{Execution mode}
    MODE -- state_only --> LOCAL[Estado local solamente<br/>sin órdenes de exchange]
    MODE -- live --> EXCHANGE[Adapter existente<br/>NO aprobado para operar]

    LOCAL --> LOOP
    EXCHANGE --> LOOP

    classDef research fill:#dbeafe,stroke:#2563eb,color:#172554;
    classDef manual fill:#fef3c7,stroke:#d97706,color:#451a03;
    classDef runtime fill:#dcfce7,stroke:#16a34a,color:#052e16;
    classDef mutation fill:#fee2e2,stroke:#dc2626,color:#450a0a;

    class COLD,DATA,DISCOVERY,CANDIDATE research;
    class CHECK,REVIEW,PROMOTED manual;
    class BOOT,RECON,LOOP,STATE,REPORTS,MODE,LOCAL runtime;
    class EXCHANGE mutation;
```

La frontera más importante es:

```text
research produce evidencia y artifacts
                    ↓ promoción manual
execution consume únicamente el promoted artifact
                    ↓ sólo mode=live
exchange puede recibir órdenes
```

Research, recalculación de pares, reporting y pair-validity no deben mutar el
exchange.

## 2. Cold start objetivo en detalle

Los entrypoints existen como `python main.py research ...` o
`python main.py run --config ...`, pero la secuencia completa todavía no está
certificada desde un workspace vacío. El siguiente gráfico muestra el contrato
que Milestone 1 debe conseguir, no una receta soportada hoy.

```mermaid
flowchart TD
    A([main.py research / run]) --> B[Cargar YAML en<br/>typed config objects]
    B --> C[Resolver venue, market profile,<br/>universe, strategy, backtest y lifecycle]
    C --> D[Calcular research window<br/>hasta la última vela cerrada]
    D --> E[CCXT market-data adapter<br/>read-only]

    E --> F[Descubrir mercados]
    F --> G[Pre-download filters:<br/>tipo de mercado, historial,<br/>precio y liquidez]
    G --> H[OHLCV backfill]
    H --> I[(Parquet + metadata<br/>por símbolo)]

    I --> J[Load symbol pool]
    J --> K[Construir log returns]
    K --> L[Grafo de correlaciones]
    L --> M[Clusters Louvain]
    M --> N[Cointegración + hedge ratio<br/>+ half-life]
    N --> O[Candidate artifact<br/>discovery output]

    O --> P[Stress grid:<br/>lookback + entry z]
    P --> Q[Vectorized simulation<br/>+ friction model]
    Q --> R[Elegir mejor configuración<br/>por par]
    R --> S[Candidate artifact<br/>stress survivors]

    S --> T{main.py promote-pairs<br/>manual operator gate}
    T -- Validación falla --> U[No cambia el promoted artifact]
    T -- Validación pasa --> V[(surviving_pairs.json<br/>promoted artifact)]
    T -- Validación pasa --> W[(promotion audit)]
    V --> X([Elegible para validación<br/>de execution boot])

    classDef data fill:#dbeafe,stroke:#2563eb,color:#172554;
    classDef math fill:#ede9fe,stroke:#7c3aed,color:#2e1065;
    classDef artifact fill:#fef3c7,stroke:#d97706,color:#451a03;
    classDef operator fill:#ffedd5,stroke:#ea580c,color:#431407;

    class B,C,D,E,F,G,H,I,J data;
    class K,L,M,N,P,Q,R math;
    class O,S,V,W artifact;
    class T,U operator;
```

### Qué persiste el cold start

| Resultado | Para qué se usa |
|---|---|
| Parquet OHLCV + metadata | Research, stress y pair-validity diagnostics |
| Candidate artifact | Resultado todavía no autorizado para execution |
| Stress report | Evidencia para revisión del operador |
| Promoted artifact | Único universo que execution carga para nuevas entradas |
| Promotion audit | Quién/cuándo/qué contenido fue promovido |

El reemplazo del promoted artifact es atómico a nivel de archivo, pero el append
del audit sucede después. Hoy no forman una única transición recuperable.

### Gaps actuales que afectan el cold start

```mermaid
flowchart LR
    S1[Symbol CCXT<br/>BTC/USDT:USDT] -. filename ambiguo .-> S2[BTC_USDT_USDT.parquet]
    S2 -. reconstrucción actual .-> S3[⚠ BTC/USDT/USDT]

    U1[Universe selection actual] -. se descarta .-> U2[⚠ Discovery escanea<br/>todos los Parquet]

    C1[Candidate DISCOVERED] -. mismo path .-> C2[Candidate STRESS output]
    C2 -. falta stage obligatorio .-> C3[⚠ Promotion no distingue<br/>ambas etapas]

    classDef gap fill:#fee2e2,stroke:#dc2626,color:#450a0a;
    class S3,U2,C3 gap;
```

Por eso el primer milestone del roadmap corrige identidad de símbolos, manifest
de universo, lifecycle incremental y provenance del candidate antes de agregar
sofisticación estadística.

## 3. Execution boot

El entrypoint es `python main.py execute ...`.

```mermaid
flowchart TD
    A([main.py execute]) --> B[Cargar pipeline, venue,<br/>market profile, strategy y risk]
    B --> TG{¿Se indicó<br/>--telegram config?}
    TG -- Sí --> DAEMON[Spawnear Telegram daemon<br/>en background]
    TG -- No --> C[Resolver credential tier]
    DAEMON --> C
    C --> D{order_execution.mode}

    D -- state_only --> E[No construir order adapter]
    D -- live --> F{¿credential tier live<br/>y keys presentes?}
    F -- No --> FAIL[Abortar boot]
    F -- Sí --> G[Construir CCXT<br/>OrderExecutionAdapter]

    E --> H[Construir notifier]
    G --> H
    H --> I[Cargar promoted artifact]
    I --> J[Validar exchange, timeframe,<br/>schema, freshness y min Sharpe]
    J --> K{¿Hay Tier 1 pairs?}
    K -- No --> STOP[Notificar y abortar]
    K -- Sí --> DB[Abrir SQLite state]

    DB --> RUN[Registrar observer run]
    RUN --> REC[Boot reconciliation<br/>read-only snapshot]
    REC --> HEALTH[Boot health notification]
    HEALTH --> LOOP([Entrar al runtime loop])

    classDef safe fill:#dcfce7,stroke:#16a34a,color:#052e16;
    classDef live fill:#fee2e2,stroke:#dc2626,color:#450a0a;
    classDef stop fill:#f3f4f6,stroke:#4b5563,color:#111827;

    class TG,DAEMON,E,H,I,J,DB,RUN,REC,HEALTH,LOOP safe;
    class F,G live;
    class FAIL,STOP stop;
```

Notas importantes:

- Dev, UAT y prod están configurados hoy como `state_only`.
- La rama `live` muestra código existente, no una ruta aprobada; faltan sizing,
  fill lifecycle, recovery, reconciliación fail-closed y emergency controls.
- Con `--telegram`, Prefect lanza el daemon de comandos como proceso separado;
  durante las esperas el trader consume los comandos persistidos.
- La reconciliación de boot registra y notifica deltas, pero actualmente no
  bloquea el loop.
- El runner aborta antes de abrir SQLite si no encuentra Tier 1 pairs.
- El nombre interno “Live Execution” es confuso: el modo efectivo lo determina
  `order_execution.mode`.

## 4. Qué sucede cuando ya está corriendo

```mermaid
flowchart TD
    START([Runtime loop activo]) --> WAIT[Calcular próximo tick:<br/>candle boundary o heartbeat]
    WAIT --> COMMANDS[Procesar comandos de operador<br/>cada 10 segundos como máximo]
    COMMANDS --> READY{¿Llegó el tick?}
    READY -- No --> COMMANDS
    READY -- Sí --> PAUSE{¿Runtime paused?}

    PAUSE -- Sí, comportamiento actual --> SKIP[⚠ Saltar el tick completo]
    PAUSE -- No --> VALIDITY[Construir pair-validity report<br/>si queue future_entries está activa]

    VALIDITY --> FETCH[Fetch OHLCV reciente readonly<br/>cache compartida por símbolo/tick]
    FETCH --> SIGNAL[Spread + rolling z-score<br/>+ inverse-vol weights]
    SIGNAL --> ACTION[Clasificar acción:<br/>SKIP / ENTRY / HOLD / EXIT / FLIP]
    ACTION --> QUEUE[Dynamic promoted-pair queue:<br/>rank + entry eligibility]
    QUEUE --> RISK[Pre-trade risk sólo para<br/>ENTRY o replacement de FLIP]
    RISK --> TRANSITION[Aplicar signal transition]
    TRANSITION --> EQUITY[Snapshot de PnL/equity local]
    EQUITY --> LIMIT{¿Llegó max_ticks?}

    LIMIT -- No --> WAIT
    LIMIT -- Sí --> END[Persistir run status,<br/>notificar y cerrar DB]
    SKIP --> LIMIT

    classDef gap fill:#fee2e2,stroke:#dc2626,color:#450a0a;
    classDef runtime fill:#dcfce7,stroke:#16a34a,color:#052e16;
    classDef decision fill:#fef3c7,stroke:#d97706,color:#451a03;

    class SKIP gap;
    class WAIT,COMMANDS,VALIDITY,FETCH,SIGNAL,ACTION,QUEUE,RISK,TRANSITION,EQUITY runtime;
    class READY,PAUSE,LIMIT decision;
```

La semántica deseada de `pause` es “bloquear nuevas entradas y permitir exits”.
El código actual retorna antes de evaluar todo el tick, por lo que también pausa
MTM y natural exits. Está marcado como corrección `NOW` en el roadmap.

## 5. Decisión por cada par en un tick

```mermaid
flowchart TD
    A[Promoted pair] --> B[Fetch candles A + B]
    B --> C{¿Fetch exitoso?}
    C -- No --> D[Omitir evaluación del par<br/>y registrar warning]
    C -- Sí --> E[Align timestamps]
    E --> F[spread = log A - beta × log B]
    F --> G[Rolling z-score]
    G --> H[Inverse-vol weights]
    H --> I{Posición local actual}

    I -- Sin posición --> J{Señal}
    J -- FLAT --> SKIP[SKIP]
    J -- LONG / SHORT --> ENTRY[ENTRY candidate]

    I -- Posición abierta --> K{Nueva señal}
    K -- Mismo side --> HOLD[HOLD]
    K -- FLAT --> EXIT[EXIT]
    K -- Side opuesto --> FLIP[FLIP]

    ENTRY --> Q{Queue permite entry?}
    Q -- No --> QB[Entry blocked + reasons]
    Q -- Sí --> R{Pre-trade risk permite?}
    R -- No --> RB[Entry blocked + reasons]
    R -- Sí --> OPEN[Open transition]

    EXIT --> CLOSE[Close transition]
    FLIP --> FR{Queue + risk permiten<br/>replacement entry?}
    FR -- No --> CLOSEONLY[Close old position only]
    FR -- Sí --> CLOSEOPEN[Close old + open new side]

    classDef enter fill:#dcfce7,stroke:#16a34a,color:#052e16;
    classDef exit fill:#dbeafe,stroke:#2563eb,color:#172554;
    classDef blocked fill:#fef3c7,stroke:#d97706,color:#451a03;
    classDef gap fill:#fee2e2,stroke:#dc2626,color:#450a0a;

    class ENTRY,OPEN enter;
    class EXIT,CLOSE,FLIP,CLOSEONLY,CLOSEOPEN exit;
    class QB,RB blocked;
    class D gap;
```

Dos distinciones esenciales:

- Queue, validity, slot limits y pre-trade risk pueden bloquear **entradas
  futuras**; no deberían bloquear un exit.
- Una falla de datos debería producir `NO_DATA/HOLD`, pero hoy algunos casos de
  datos insuficientes se convierten en `FLAT`, que puede parecer un exit real.

## 6. Qué cambia entre `state_only` y `live`

```mermaid
flowchart LR
    SIGNAL[Signal transition] --> LOCAL[Mutar estado local<br/>position + legs + events]
    LOCAL --> MODE{Execution mode}

    MODE -- state_only --> TARGETS[Guardar leg targets<br/>filled_qty = 0]
    TARGETS --> PNL[PNL teórico con<br/>precios de señal]

    MODE -- live --> LEG1[Enviar orden leg 1]
    LEG1 --> LEG2[Enviar orden leg 2]
    LEG2 --> OUTCOME[Registrar order outcomes]

    classDef state fill:#dcfce7,stroke:#16a34a,color:#052e16;
    classDef live fill:#fee2e2,stroke:#dc2626,color:#450a0a;

    class LOCAL,MODE,TARGETS,PNL state;
    class LEG1,LEG2,OUTCOME live;
```

| Modo | Qué hace | Qué no prueba |
|---|---|---|
| `state_only` | Señales, queue, pre-trade gates, posiciones/legs locales, PnL teórico, reporting | Fills, fees, funding, slippage, partial orders, exchange recovery |
| `live` | Agrega órdenes CCXT reales | Aún no está aprobado para capital: el lifecycle local se adelanta a fills y faltan recovery/reconciliation gates |
| Paper stateful | **Todavía no existe**; es el siguiente gran milestone | Se construirá sobre replay determinista y simulated fills |

## 7. Artifacts y estado durante el runtime

```mermaid
flowchart LR
    PROMOTED[(Promoted artifact)] -->|se carga al boot| PAIRS[Pairs habilitados]
    PAIRS -->|por tick| QUEUE[Dynamic queue]
    VALIDITY[Pair validity diagnostics] --> QUEUE
    MARKET[Live opportunity evidence] --> QUEUE
    SQLITE[(SQLite positions + runtime state)] --> QUEUE

    QUEUE -->|future entries| TRANSITIONS[Signal transitions]
    TRANSITIONS --> SQLITE
    SQLITE --> REPORT[Reports + Telegram]

    NEW[Candidate nuevo] -->|manual promote| NEXT[(Nuevo promoted artifact)]
    NEXT -. no hay hot reload actual .-> RESTART[Operator restart]
    RESTART --> PAIRS
```

Mientras el proceso corre:

- No se ejecuta research automáticamente.
- No hay hot reload del promoted artifact.
- Un candidate nuevo no cambia el universo activo hasta promoción + restart.
- Pair validity y dynamic queue recalculan evidencia de entradas futuras.
- SQLite persiste posiciones, legs, señales, equity, comandos, runs y
  reconciliación.

La intención segura es que una posición abierta conserve sus parámetros y salga
naturalmente aunque el par desaparezca del artifact siguiente. El código actual
todavía no persiste todo ese contrato ni une correctamente posiciones huérfanas
al boot; por eso aparece como gap prioritario en el roadmap.

## 8. Resumen operativo

### Cold start objetivo — todavía no soportado de punta a punta

```text
typed configs
-> readonly market discovery
-> filtered OHLCV backfill
-> local Parquet
-> returns / clusters / cointegration
-> candidate
-> vector stress
-> candidate survivors
-> manual promotion
-> promoted artifact
-> execution boot
```

### Ya corriendo

```text
sleep while processing commands
-> pair validity
-> fetch recent candles
-> signal per pair
-> dynamic queue
-> pre-trade risk for entries
-> local transition
-> optional live orders only in explicit live mode
-> equity/reporting
-> next tick
```

### Progresión real del producto

```text
state_only actual
-> paper stateful con simulated fills
-> exchange demo/testnet
-> very-small-capital canary
-> producción sólo después del readiness gate
```

El sistema está hoy entre el primer y el segundo escalón.
