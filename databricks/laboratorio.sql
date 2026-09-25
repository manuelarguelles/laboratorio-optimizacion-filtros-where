-- Elegir un esquema nuevo para repetir. Ver ejecutar.py para sesiones nuevas y metricas.

SET use_cached_result = false;

SELECT current_version() AS version, current_user() AS usuario;

CREATE SCHEMA workspace.period_filter_lab;

ALTER SCHEMA workspace.period_filter_lab DISABLE PREDICTIVE OPTIMIZATION;

CREATE TABLE workspace.period_filter_lab.base USING DELTA
TBLPROPERTIES ('delta.autoOptimize.optimizeWrite'='false', 'delta.autoOptimize.autoCompact'='false')
AS
WITH numeros AS (SELECT CAST(id AS INT) AS n FROM range(1,1000001)),
posiciones AS (SELECT n, (n - (n DIV 10) - 1) % 59 AS posicion FROM numeros),
offsets AS (SELECT n, posicion + CASE WHEN posicion >= 41 THEN 1 ELSE 0 END AS offset_mes FROM posiciones)
SELECT /*+ REPARTITION(8) */ n AS Id,
       CAST(CASE WHEN n % 10 = 0 THEN 2025 ELSE 2022 + (offset_mes DIV 12) END AS INT) AS Anio,
       CAST(CASE WHEN n % 10 = 0 THEN 6 ELSE offset_mes % 12 + 1 END AS INT) AS Mes,
       CAST((n % 100000) / 100.0 AS DECIMAL(12,2)) AS Importe,
       rpad(concat('Registro ',CAST(n AS STRING),' ',repeat('X',80)),100,' ') AS Detalle
FROM offsets;

CREATE TABLE workspace.period_filter_lab.particionada USING DELTA PARTITIONED BY (Anio,Mes)
TBLPROPERTIES ('delta.autoOptimize.optimizeWrite'='false', 'delta.autoOptimize.autoCompact'='false')
AS SELECT * FROM workspace.period_filter_lab.base;

CREATE TABLE workspace.period_filter_lab.clusterizada USING DELTA CLUSTER BY (Anio,Mes)
AS SELECT * FROM workspace.period_filter_lab.base;

OPTIMIZE workspace.period_filter_lab.clusterizada FULL;

SELECT count(*) AS total,
            count_if(Anio=2025 AND Mes=6) AS objetivo,
            count_if(Anio*100+Mes=202506) AS objetivo_aritmetico,
            count(DISTINCT Id) AS ids,
            min(length(Detalle)) AS largo_min, max(length(Detalle)) AS largo_max FROM workspace.period_filter_lab.base;

ANALYZE TABLE workspace.period_filter_lab.base COMPUTE STATISTICS FOR COLUMNS Anio,Mes;

DESCRIBE DETAIL workspace.period_filter_lab.base;

DESCRIBE HISTORY workspace.period_filter_lab.base LIMIT 1;

SELECT _metadata.file_path AS path, count(*) AS filas,
                            min(Anio*100+Mes) AS periodo_min,max(Anio*100+Mes) AS periodo_max
                            FROM workspace.period_filter_lab.base GROUP BY _metadata.file_path;

SELECT count(*) AS total,
            count_if(Anio=2025 AND Mes=6) AS objetivo,
            count_if(Anio*100+Mes=202506) AS objetivo_aritmetico,
            count(DISTINCT Id) AS ids,
            min(length(Detalle)) AS largo_min, max(length(Detalle)) AS largo_max FROM workspace.period_filter_lab.particionada;

SELECT count(*) AS diferencias FROM (SELECT Id,Anio,Mes,Importe,Detalle FROM workspace.period_filter_lab.base EXCEPT ALL SELECT Id,Anio,Mes,Importe,Detalle FROM workspace.period_filter_lab.particionada);

SELECT count(*) AS diferencias FROM (SELECT Id,Anio,Mes,Importe,Detalle FROM workspace.period_filter_lab.particionada EXCEPT ALL SELECT Id,Anio,Mes,Importe,Detalle FROM workspace.period_filter_lab.base);

ANALYZE TABLE workspace.period_filter_lab.particionada COMPUTE STATISTICS FOR COLUMNS Anio,Mes;

DESCRIBE DETAIL workspace.period_filter_lab.particionada;

DESCRIBE HISTORY workspace.period_filter_lab.particionada LIMIT 1;

SELECT _metadata.file_path AS path, count(*) AS filas,
                            min(Anio*100+Mes) AS periodo_min,max(Anio*100+Mes) AS periodo_max
                            FROM workspace.period_filter_lab.particionada GROUP BY _metadata.file_path;

SELECT count(*) AS total,
            count_if(Anio=2025 AND Mes=6) AS objetivo,
            count_if(Anio*100+Mes=202506) AS objetivo_aritmetico,
            count(DISTINCT Id) AS ids,
            min(length(Detalle)) AS largo_min, max(length(Detalle)) AS largo_max FROM workspace.period_filter_lab.clusterizada;

SELECT count(*) AS diferencias FROM (SELECT Id,Anio,Mes,Importe,Detalle FROM workspace.period_filter_lab.base EXCEPT ALL SELECT Id,Anio,Mes,Importe,Detalle FROM workspace.period_filter_lab.clusterizada);

SELECT count(*) AS diferencias FROM (SELECT Id,Anio,Mes,Importe,Detalle FROM workspace.period_filter_lab.clusterizada EXCEPT ALL SELECT Id,Anio,Mes,Importe,Detalle FROM workspace.period_filter_lab.base);

ANALYZE TABLE workspace.period_filter_lab.clusterizada COMPUTE STATISTICS FOR COLUMNS Anio,Mes;

DESCRIBE DETAIL workspace.period_filter_lab.clusterizada;

DESCRIBE HISTORY workspace.period_filter_lab.clusterizada LIMIT 1;

SELECT _metadata.file_path AS path, count(*) AS filas,
                            min(Anio*100+Mes) AS periodo_min,max(Anio*100+Mes) AS periodo_max
                            FROM workspace.period_filter_lab.clusterizada GROUP BY _metadata.file_path;

-- CALENTAMIENTO: excluir

/* LabPeriodos 20260924_162841 escenario=1 iteracion=0 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio*100+Mes=202506;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=1 iteracion=1 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio*100+Mes=202506;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=1 iteracion=2 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio*100+Mes=202506;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=1 iteracion=3 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio*100+Mes=202506;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=1 iteracion=4 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio*100+Mes=202506;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=1 iteracion=5 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio*100+Mes=202506;

-- CALENTAMIENTO: excluir

/* LabPeriodos 20260924_162841 escenario=2 iteracion=0 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=2 iteracion=1 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=2 iteracion=2 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=2 iteracion=3 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=2 iteracion=4 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=2 iteracion=5 */ SELECT * FROM workspace.period_filter_lab.base WHERE Anio=2025 AND Mes=6;

-- CALENTAMIENTO: excluir

/* LabPeriodos 20260924_162841 escenario=3 iteracion=0 */ SELECT * FROM workspace.period_filter_lab.particionada WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=3 iteracion=1 */ SELECT * FROM workspace.period_filter_lab.particionada WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=3 iteracion=2 */ SELECT * FROM workspace.period_filter_lab.particionada WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=3 iteracion=3 */ SELECT * FROM workspace.period_filter_lab.particionada WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=3 iteracion=4 */ SELECT * FROM workspace.period_filter_lab.particionada WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=3 iteracion=5 */ SELECT * FROM workspace.period_filter_lab.particionada WHERE Anio=2025 AND Mes=6;

-- CALENTAMIENTO: excluir

/* LabPeriodos 20260924_162841 escenario=4 iteracion=0 */ SELECT * FROM workspace.period_filter_lab.clusterizada WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=4 iteracion=1 */ SELECT * FROM workspace.period_filter_lab.clusterizada WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=4 iteracion=2 */ SELECT * FROM workspace.period_filter_lab.clusterizada WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=4 iteracion=3 */ SELECT * FROM workspace.period_filter_lab.clusterizada WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=4 iteracion=4 */ SELECT * FROM workspace.period_filter_lab.clusterizada WHERE Anio=2025 AND Mes=6;

-- MEDICION

/* LabPeriodos 20260924_162841 escenario=4 iteracion=5 */ SELECT * FROM workspace.period_filter_lab.clusterizada WHERE Anio=2025 AND Mes=6;

EXPLAIN FORMATTED SELECT * FROM workspace.period_filter_lab.base WHERE Anio*100+Mes=202506;

EXPLAIN FORMATTED SELECT * FROM workspace.period_filter_lab.base WHERE Anio=2025 AND Mes=6;

EXPLAIN FORMATTED SELECT * FROM workspace.period_filter_lab.particionada WHERE Anio=2025 AND Mes=6;

EXPLAIN FORMATTED SELECT * FROM workspace.period_filter_lab.clusterizada WHERE Anio=2025 AND Mes=6;
