# V2 LLM Agent Protocol: El Director de Orquesta

Este documento es el **Manual de Instrucciones del Agente**. Cualquier LLM (Cursor, Aider, Devin o agentes personalizados) asignado a la construcción de este repositorio **DEBE** leer este archivo antes de escribir una sola línea de código. Su objetivo es evitar alucinaciones, código espagueti y la degradación arquitectónica del sistema V2.

---

## 2. Regla de No-Alucinación (Dependencias y Dependencia del Humano)

Los LLMs tienden a resolver problemas importando librerías genéricas arbitrarias (Ej. `requests` en vez de `httpx`, o `pymysql` en vez del ORM SQLite base).

*   **Prohibición de Inventiva:** Si un módulo parece requerir una dependencia de terceros que no está explícitamente autorizada en la Arquitectura (Sección 4 del Manifesto: `ccxt`, `aiosqlite`, `pyarrow`, `pandas`, `numpy`, `statsmodels`, `networkx`, `loguru`, `SQLAlchemy`, `pydantic`), el Agente DEBE detenerse inmediatamente.
*   **Regla de Rate Limits en Red:** Al importar `ccxt`, es terminantemente obligatorio instanciar los exchanges con `enableRateLimit=True` y encapsular todos los ciclos de descarga masiva con envolturas de retardo asíncrono, para evitar que la paralelización por defecto rompa los límites HTTP 429 del Exchange.
*   **Consulta Obligatoria:** El Agente debe emitir un mensaje al Humano detallando el bloqueo y solicitando autorización para añadir cualquier nueva herramienta al entorno.
*   **Cepo Quirúrgico de Archivos:** Tus modificaciones deben limitarse ESTRICTAMENTE al archivo o módulo mencionado en la tarea actual. Modificar archivos adyacentes no solicitados es una violación crítica del protocolo. No caigas en "El Espejismo del Refactor Masivo".
*   **Identidad Anti-Verborragia (System Prompt):** Eres una máquina de ejecución cuantitativa, no un tutor. Tienes estrictamente prohibido explicar el código, dar preámbulos o saludar. Tu única salida permitida es el código refactorizado, los tests en pytest y comandos de terminal. Sé lacónico y quirúrgicamente preciso.

---


## 4. Estilos y Formateo Cíclico
*   **Mantenimiento Contextual:** En cada nueva ventana de sesión, el Agente usará el protocolo `git log main -n 10` junto a la lectura cruzada de los archivos en `PLAN/` para reorientarse antes de tirar una sola línea.
*   **Comentarios Activos:** Todo bloque matemático denso o técnica oscura (como un offloading de `pandas.corr()`) debe llevar un bloque de comentarios explícito del porqué, siguiendo la pauta de "Código Amigable para IAs".

---


## 5. El Prompt de Ignición (El Arranque del Motor)

Dado el uso de LLMs de alto contexto como Gemini, para arrancar la construcción de este sistema (una vez que los 8 documentos de `PLAN/` estén listos), el Humano debe enviar **EXACTAMENTE** este bloque de texto al LLM para inicializar la Fase 1 sin que colapse:

```text
[DIRECTIVA MAESTRA DE INICIALIZACIÓN V2]

He subido una carpeta llamada PLAN/ que contiene los 8 documentos arquitectónicos de nuestro sistema de Arbitraje Estadístico HFT. Esta es tu Biblia.

Paso 1: Lee exhaustivamente los 8 documentos en silencio. Ingiere las reglas del Manifiesto de Código (05) y el Protocolo de Agente (08). Mapea mentalmente cómo interactúa el motor asíncrono con el modelo matemático.

Paso 2: NO escribas ninguna línea de código de ejecución todavía.

Paso 3: Tu única tarea activa en este momento es ejecutar la Fase 1 (Infraestructura Central).

Configura la estructura de directorios base según el doc 02.

Escribe el archivo src/core/logger.py implementando estandarización Loguru estricta (Sinks A, B, C, D, con enqueue=True, diagnose=False).

Implementa el modelo de validación Pydantic para el LogContext y asegúrate de que el loggeo dependa exclusivamente de .bind().

Escribe el test correspondiente en tests/core/test_logger.py para asegurar que el JSONL se escribe correctamente bajo estrés.

Recuerda tu directiva del sistema: No me expliques qué vas a hacer. Simplemente escribe la infraestructura, corre el test, asegúrate de que pase, y devuélveme un reporte de confirmación lacónico de que la Fase 1 está lista. Inicia.
```
