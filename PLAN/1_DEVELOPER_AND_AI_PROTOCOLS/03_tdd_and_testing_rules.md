# V2 LLM Agent Protocol: El Director de Orquesta

Este documento es el **Manual de Instrucciones del Agente**. Cualquier LLM (Cursor, Aider, Devin o agentes personalizados) asignado a la construcción de este repositorio **DEBE** leer este archivo antes de escribir una sola línea de código. Su objetivo es evitar alucinaciones, código espagueti y la degradación arquitectónica del sistema V2.

---

## 3. Protocolo de Testing Restrictivo (El Flujo TDD)

Ninguna función en producción puede existir sin que el Agente haya demostrado primero que es matemáticamente sólida y resistente a los fallos de red. Se debe utilizar estrictamente `pytest`.

El Agente operará bajo la siguiente secuencia cíclica estricta:
1.  **Redacción de la Prueba (Test First):** Antes de tocar `/src/`, el Agente escribe la función de prueba en `/tests/` describiendo qué debe hacer la función que aún no existe, inyectando variables límite y mockeando la red.
2.  **Verificación de Falla:** El Agente corre el test y comprueba explícitamente que falla.
3.  **Implementación Temprana:** El Agente escribe el código real de producción en `/src/` estrictamente para cumplir y pasar la prueba escrita.
4.  **Refactorización Segura:** Una vez que el test está verde, se optimiza (Vectorización, Offloading de Hilos).
5.  **Pruebas de Casos Borde y Red (Mocking):** El LLM debe generar explícitamente DataFrames corruptos (con brechas `NaN`, ceros o strings) e inyectarlos para confirmar que la aplicación falla limpiamente, en lugar de causar OOM. Las APIs de red JAMÁS deben llamarse nativamente en los tests.
6.  **Dependencias "Fantasma" en los Tests:** Al exigir asincronía y TDD, el Agente no debe asumir que el entorno ya tiene configurados plugins como `pytest-asyncio`. Debe verificar e instalar explícitamente las dependencias de testing asíncrono para que los tests no se salten silenciosamente.
7.  **El "Fail-Fast" del Agente (Anti-Bucle):** Si un test falla en 3 iteraciones consecutivas de código, el Agente tiene ESTRICTAMENTE PROHIBIDO seguir intentando parchearlo. Debe ejecutar `git reset --hard` para revertir el código al último commit funcional, detener su ejecución y emitir un mensaje al Humano detallando el bloqueo matemático.

---

