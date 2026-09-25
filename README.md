# El WHERE no cuenta toda la historia

**Un millón de filas, cuatro escenarios y dos motores: SQL Server y Databricks.**

Queríamos consultar junio de 2025. El período no existía como columna: estaba dividido en `Anio` y `Mes`. ¿Cuánto cambia la consulta al escribir el filtro de otra forma o reorganizar los datos?

Construimos una tabla de **1.000.000 de filas**, exactamente **100.000 del período objetivo**, y ejecutamos dos laboratorios. El clustered de SQL Server redujo lecturas; liquid clustering de Delta no ganó en esta tabla pequeña. Entre ambos resultados aparecieron planes internos, cachés que no eran la misma caché y 480 archivos diminutos.

> No es una carrera entre motores. Son dos comparaciones internas, con infraestructura y métricas diferentes. Los casos Delta 3/4 son **adaptaciones**, no índices equivalentes a SQL Server.

## El experimento

```sql
-- Caso 1
SELECT * FROM tabla WHERE Anio * 100 + Mes = 202506;
-- Casos 2, 3 y 4: mismo filtro, distinta organización
SELECT * FROM tabla WHERE Anio = 2025 AND Mes = 6;
```

| Caso | SQL Server | Databricks Delta |
|---|---|---|
| 1 | Heap + filtro aritmético | Tabla base + filtro aritmético |
| 2 | Mismo heap + filtros separados | Misma tabla base + filtros separados |
| 3 | Dos nonclustered individuales | Particiones `(Anio,Mes)` |
| 4 | Clustered compuesto `(Anio,Mes)` | Liquid clustering `(Anio,Mes)` + `OPTIMIZE FULL` |

Un calentamiento y cinco mediciones por caso. Siempre `SELECT *` y **100.000 filas consumidas por el cliente**. Construcción, estadísticas, mantenimiento y captura de planes fuera de las mediciones. Datos sintéticos deterministas: [metodología y distribución](docs/METODOLOGIA.md).

## Lo que medimos

**SQL Server 2022 CU27**, 2 CPU, contenedor 4 GiB, motor 3 GiB. Mac ARM con traducción x86; compatibilidad 160. Medianas de cinco ejecuciones, medidas con `STATISTICS TIME/IO`:

| Caso | CPU ms | Ejecución ms | Lecturas lógicas | Acceso |
|---|---:|---:|---:|---|
| 1. Aritmética | 118 | 112 | 16.130 | Table Scan paralelo |
| 2. Filtros separados | 103 | 77 | 16.130 | Table Scan paralelo |
| 3. Índices individuales | 94 | 65 | 16.130 | Table Scan paralelo |
| 4. Clustered compuesto | 26 | 45 | 1.733 | Clustered Index Seek |

El clustered redujo lecturas **89,3%**. Los índices individuales estaban presentes, pero no se utilizaron: la diferencia temporal entre 2 y 3 no demuestra una mejora por esos índices. [CSV](results/sql-server/mediciones.csv) · [mensajes TIME/IO](results/sql-server/mensajes.txt).

**Databricks SQL 2026.36**, warehouse Small serverless con Photon. Medianas de cinco ejecuciones finales:

| Caso | Ejecución ms | Compilación ms | Leídos MB¹ | Archivos leídos / descartados |
|---|---:|---:|---:|---|
| 1. Aritmética | 99 | 210 | 5,184 | 8 / 0 |
| 2. Filtros separados | 88 | 203 | 5,184 | 8 / 0 |
| 3. Particiones | 85 | 179 | 0,382 | 8 / 472 |
| 4. Liquid clustering | 216 | 218 | 3,732 | 1 / 0 |

¹ MB decimales. El caso particionado redujo bytes leídos **92,6%**, pero 3 ms de diferencia no prueban una mejora estable de latencia. Liquid clustering compactó a **un solo archivo** y no descartó archivos completos. La tabla base ocupaba apenas **4,1 MB comprimidos**: un millón de filas no implica una tabla grande. [CSV](results/databricks/mediciones.csv) · [métricas del historial](results/databricks/metricas-historial.json).

## La parte que casi engaña al benchmark

- Expulsar el plan ad hoc no eliminó el plan interno autoparametrizado de SQL Server.
- `ParameterizedText` puede aparecer sin `ParameterizedPlanHandle`.
- Un calentamiento en serverless no garantizó datos calientes: dos primeras mediciones leyeron remotamente. Repetimos **la ronda completa**, sin escoger resultados individuales.
- Particionar produjo **480 archivos**, aproximadamente 9 KB de media. Leer menos bytes no convierte ese diseño en una recomendación general.
- `EXPLAIN` no es un plan real instrumentado; tiempo agregado de tareas no es CPU; caché de datos no es caché de resultados ni caché de planes.

Los **15 gotchas** tienen identificadores y evidencias: [GOTCHAS.md](docs/GOTCHAS.md).

## Caché: qué se controló realmente

En SQL Server limpiamos la caché de planes **solo de la base aislada**, comprobamos ausencia de planes y después `execution_count=1`. Los datos permanecieron calientes.

```sql
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
SET STATISTICS TIME ON;
SET STATISTICS IO ON;
```

En Databricks usamos una sesión nueva por consulta y:

```sql
SET use_cached_result = false;
```

El historial confirmó resultados no reutilizados. Las veinte mediciones finales reportaron cero bytes remotos. **No se limpió ni se certifica vacía la caché interna de planes de Databricks**: no es el mismo control que SQL Server. [Protocolo y límites](docs/METODOLOGIA.md).

## Reproducir y verificar

- [SQL Server: contenedor y ejecutor](sql-server/README.md).
- [Databricks: warehouse y ejecutor](databricks/README.md).
- Sin cuentas ni cómputo, validar los resultados publicados:

```sh
python3 tools/verify_results.py
```

Los ejecutores públicos adaptan la configuración de los usados en el laboratorio. Se verificaron localmente su sintaxis y los resultados archivados; **no se volvió a ejecutar el benchmark en una instancia nueva para publicar este repositorio**. Nuevas corridas pueden dar otros tiempos.

## Evidencia y límites

Resultados medidos el **24-sep-2026**; publicación preparada el **25-sep-2026**. Se incluyen las 20 mediciones finales de cada motor, la primera ronda Databricks, planes SQL Server, EXPLAIN de Delta y métricas seleccionadas. Los metadatos identificadores de la infraestructura se sustituyeron u omitieron; los números se conservaron. [Procedencia y exportación](docs/PROCEDENCIA.md).

No se ejecutó una variante en Microsoft Fabric. No se recomienda un proveedor, un índice o una partición únicamente a partir de estos tiempos. El siguiente experimento sería variar **bytes, selectividad y número de archivos** con un protocolo acordado, no aumentar filas hasta que gane una técnica.
