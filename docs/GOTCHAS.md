# Gotchas: filtros de período, planes y cachés

Hallazgos del laboratorio del 24-sep-2026. Los diagnósticos de planes y autenticación son notas del proceso; las métricas finales se conservan como archivos públicos. No son leyes universales ni recomendaciones para Fabric.

## DE-PER-001 — Tres cachés diferentes

**Hallazgo:** Limpiar planes no elimina resultados reutilizables ni enfría páginas/archivos.

**Evidencia y alcance:** SQL tuvo cero lecturas físicas; Delta final tuvo cero bytes remotos y resultados no cacheados.

**Práctica:** Declarar y verificar cada capa por separado. [Referencia](METODOLOGIA.md).

## DE-PER-002 — Plan ad hoc e interno autoparametrizado

**Hallazgo:** La expulsión del plan visible dejó un plan preparado interno durante el diagnóstico SQL.

**Evidencia y alcance:** El protocolo final usa limpieza por base y verifica execution_count=1.

**Práctica:** En una base aislada, limpiar su caché y comprobar las DMV; no asumir que un handle cubre todos los planes. [Referencia](../sql-server/ejecutar.py).

## DE-PER-003 — ParameterizedText no garantiza handle

**Hallazgo:** Puede existir texto parametrizado sin ParameterizedPlanHandle.

**Evidencia y alcance:** Hallazgo diagnóstico archivado; el ejecutor final evita depender de esa suposición.

**Práctica:** Seguir únicamente handles realmente presentes; no convertir texto en evidencia de un plan accesible. [Referencia](../sql-server/ejecutar.py).

## DE-PER-004 — DMV contaminada por otras bases

**Hallazgo:** Buscar solo texto puede recoger una corrida anterior conservada.

**Evidencia y alcance:** Cada corrida SQL crea una base distinta.

**Práctica:** Restringir el diagnóstico por base y consulta, además de verificar ejecución única. [Referencia](../sql-server/ejecutar.py).

## DE-PER-005 — Un índice presente puede no usarse

**Hallazgo:** Dos índices individuales no garantizaron acceso por índice.

**Evidencia y alcance:** Casos 2 y 3: Table Scan y 16.130 lecturas lógicas.

**Práctica:** Comprobar el operador real; no atribuir los 77 frente a 65 ms a índices que no participaron. [Referencia](../results/sql-server/resumen.json).

## DE-PER-006 — Separar predicados no fabrica un seek

**Hallazgo:** El caso 2 continuó leyendo el heap completo.

**Evidencia y alcance:** Casos 1/2: mismo número de lecturas lógicas.

**Práctica:** Distinguir expresión del filtro de estructura de acceso disponible. [Referencia](../results/sql-server/plan-2.sqlplan).

## DE-PER-007 — Un calentamiento no garantiza datos calientes

**Hallazgo:** Dos mediciones iniciales serverless todavía leyeron bytes remotos.

**Evidencia y alcance:** La primera ronda conserva ambas lecturas; la ronda final completa reporta cero.

**Práctica:** Inspeccionar métricas y repetir una ronda completa con criterio explícito, conservando la anterior. [Referencia](../results/databricks/initial.csv).

## DE-PER-008 — Desactivar result cache exige verificar la sesión

**Hallazgo:** Una configuración en otra conexión no prueba cómo corrió la consulta medida.

**Evidencia y alcance:** 24 consultas finales, incluidos calentamientos: result_from_cache=false.

**Práctica:** Establecer y consultar use_cached_result en cada sesión; contrastar con historial. [Referencia](../results/databricks/metricas-historial.json).

## DE-PER-009 — Sesión nueva no es plan cache vacío

**Hallazgo:** No se certificó vacía la caché interna de planes de Databricks.

**Evidencia y alcance:** El protocolo solo controla result cache y observa residencia de datos.

**Práctica:** No presentar CLEAR CACHE ni reconexión como equivalentes de CLEAR PROCEDURE_CACHE. [Referencia](METODOLOGIA.md).

## DE-PER-010 — B-tree, particiones y liquid son mecanismos distintos

**Hallazgo:** Delta no replica los índices individuales o clustered del laboratorio SQL.

**Evidencia y alcance:** El diseño usa particionado y liquid como adaptaciones.

**Práctica:** Explicar qué organización se compara antes de interpretar resultados. [Referencia](../README.md).

## DE-PER-011 — Un millón de filas puede ser muy poco volumen

**Hallazgo:** La base Delta ocupó 4,1 MB y liquid terminó en un archivo.

**Evidencia y alcance:** Caso 4: un archivo leído y cero descartados; ejecución mediana 216 ms.

**Práctica:** Evaluar bytes y granularidad; no extrapolar que liquid clustering sea lento en general. [Referencia](../results/databricks/layouts.json).

## DE-PER-012 — Menos bytes con demasiados archivos

**Hallazgo:** El particionado generó 480 archivos de aproximadamente 9 KB de media.

**Evidencia y alcance:** Descartó 472 y redujo bytes 92,6%, pero la diferencia mediana con caso 2 fue solo 3 ms.

**Práctica:** Separar prueba de pruning de una recomendación de diseño para producción. [Referencia](../results/databricks/resumen.json).

## DE-PER-013 — Métricas y planes con nombres engañosos

**Hallazgo:** Tiempo de tareas no es CPU; EXPLAIN no es plan real instrumentado.

**Evidencia y alcance:** Se guardan XML reales SQL y EXPLAIN Delta junto al historial de ejecución.

**Práctica:** Etiquetar fuente y unidad de cada métrica; no equiparar filas leídas de Photon con ActualRowsRead. [Referencia](METODOLOGIA.md).

## DE-PER-014 — Comparar motores requeriría otro diseño

**Hallazgo:** Hardware, red, runtime y límites de medición son diferentes.

**Evidencia y alcance:** SQL corre traducido en Mac ARM; Delta usa warehouse serverless.

**Práctica:** Comparar escenarios dentro de cada motor; no declarar ganador entre plataformas. [Referencia](METODOLOGIA.md).

## DE-PER-015 — La autenticación efectiva puede diferir del PAT configurado

**Hallazgo:** Un PAT antiguo falló aunque la sesión OAuth de CLI seguía válida.

**Evidencia y alcance:** El diagnóstico de autenticación precedió a la construcción de tablas; no forma parte de las mediciones.

**Práctica:** Usar el token de la sesión CLI autenticada sin imprimirlo ni publicarlo; parametrizar perfil y warehouse. [Referencia](../databricks/ejecutar.py).
