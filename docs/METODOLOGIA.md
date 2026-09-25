# Metodología y límites

## Datos

`Id` va de 1 a 1.000.000. Cada décima fila corresponde a 2025-06: exactamente 100.000 filas (10%). Las otras 900.000 se distribuyen en los restantes 59 meses de 2022–2026, excluyendo junio de 2025. La generación determinista está en los ejecutores.

Columnas: Id, Anio y Mes enteros, Importe decimal(12,2), Detalle de 100 caracteres. SQL Server usa CHAR(100); Delta usa STRING con relleno. Se verificaron conteos y la igualdad de las tres copias Delta con EXCEPT ALL en ambos sentidos.

## Protocolo

1. Preparar datos, índices/layouts y estadísticas fuera del cronómetro.
2. Ejecutar los escenarios en orden 1–4. Un calentamiento por caso, seguido de cinco ejecuciones medidas. El orden fijo y la muestra pequeña limitan conclusiones temporales.
3. Consumir las 100.000 filas de cada SELECT *; no sustituir por COUNT ni medir solo la primera página.
4. Guardar las mediciones individuales y presentar medianas por métrica. La suma de medianas de componentes no tiene por qué igualar la mediana del total.
5. Capturar los planes fuera de la medición. SQL Server: plan real XML; Databricks: EXPLAIN FORMATTED y métricas reales del historial por separado.

SQL Server modifica los índices de la misma tabla entre escenarios. Delta utiliza tres copias del mismo conjunto; los casos 1/2 comparten tabla base. Las particiones y liquid clustering son adaptaciones de organización física, no implementaciones equivalentes de índices B-tree.

## Control de cachés

| Capa | SQL Server | Databricks |
|---|---|---|
| Planes | Limpieza de caché de la base aislada antes de cada medición; verificación DMV previa y execution_count=1 posterior | No vaciada ni certificada; sesión nueva no demuestra recompilación sin reutilización interna |
| Resultados | Consulta ejecutada y resultados consumidos | use_cached_result=false en cada sesión y result_from_cache=false en historial |
| Datos | Calientes; last_physical_reads=0 | Ronda final con read_remote_bytes=0 en las 20 mediciones |

Limpiar planes no equivale a enfriar datos. En SQL se evitó vaciar globalmente la caché de otras bases. En Delta no se utilizó CLEAR CACHE como supuesto equivalente a DBCC FREEPROCCACHE.

La primera ronda Delta tuvo dos lecturas remotas en el caso 1 (1.296.322 y 622.893 bytes), aun después del calentamiento. Se repitió la ronda completa usando las mismas tablas; se conserva [la ronda inicial](../results/databricks/initial.csv). No se seleccionaron ejecuciones rápidas entre rondas. Esto no garantiza que futuras corridas serverless mantengan la misma residencia de datos.

## Entornos y métricas

SQL Server 2022 CU27 Developer, compatibilidad 160; Docker linux/amd64 sobre Mac ARM con traducción x86, 2 CPU, 4 GiB para contenedor y 3 GiB para motor. STATISTICS TIME/IO aporta CPU, tiempo de ejecución y lecturas lógicas. Los valores DMV tienen su propia unidad y alcance; last_worker_time y last_elapsed_time se conservan en microsegundos.

Databricks SQL 2026.36, Small serverless Photon, máximo un clúster. Base: 8 archivos; particionada: 480; liquid: 1 tras OPTIMIZE FULL. Se desactivó predictive optimization solo en el esquema del laboratorio. En base y particionada se desactivaron optimizeWrite y autoCompact.

execution_time_ms, compilation_time_ms y total_time_ms proceden del historial. task_total_time_ms es tiempo agregado de tareas, no CPU. rows_read_count de Photon no se interpreta como ActualRowsRead de SQL Server. read_bytes es la métrica del historial y no equivale al tamaño físico de los archivos.

El tiempo cliente incluye transferencia y consumo. Sus medianas SQL fueron 316,109 / 320,766 / 314,098 / 306,987 ms; Delta: 1844,833 / 1783,980 / 1910,630 / 2631,947 ms. Son contextos de red y cliente diferentes; tampoco sirven para declarar un ganador entre motores.

## Alcance de las conclusiones

La reducción de lecturas del clustered y el descarte de archivos particionados están respaldados por evidencia. Una diferencia de pocos milisegundos con cinco repeticiones no prueba una ventaja estable. Tampoco un solo archivo Delta permite evaluar beneficios generales de liquid clustering. Repetir con distintos tamaños en bytes, selectividades y órdenes de ejecución sería otro experimento.
