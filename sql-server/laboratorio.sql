/*
Laboratorio SQL Server: 1.000.000 filas, 100.000 para junio de 2025.
Ejecutar TODO este archivo en una base de laboratorio, en una sola sesion.
No activar Ctrl+M durante las mediciones. Ver README.md.
No elimina tablas existentes. Al terminar conserva tabla e indice del caso 4.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET STATISTICS TIME OFF;
SET STATISTICS IO OFF;

DECLARE @CapturarPlanes bit = 0; -- 1: una ejecucion XML extra por escenario
DECLARE @Repeticiones int = 5;

IF DB_NAME() IN (N'master', N'model', N'msdb', N'tempdb')
    THROW 50001, 'Selecciona una base de usuario para el laboratorio.', 1;

IF OBJECT_ID(N'dbo.LabPeriodos') IS NOT NULL
    THROW 50002, 'dbo.LabPeriodos ya existe. Usa otra base de laboratorio para repetir la carga.', 1;

CREATE TABLE dbo.LabPeriodos
(
    Id int NOT NULL,
    Anio int NOT NULL,
    Mes int NOT NULL CHECK (Mes BETWEEN 1 AND 12),
    Importe decimal(12,2) NOT NULL,
    Detalle char(100) NOT NULL
);

-- Seis digitos: exactamente 1.000.000 identificadores distintos.
-- Cada decima fila es del periodo objetivo. El resto recorre 59 meses:
-- enero 2022 a diciembre 2026, excluyendo junio 2025 (offset 41).
;WITH Digito AS
(
    SELECT d FROM (VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) AS v(d)
), Numeros AS
(
    SELECT 1 + a.d + 10*b.d + 100*c.d + 1000*d.d
           + 10000*e.d + 100000*f.d AS n
    FROM Digito AS a CROSS JOIN Digito AS b CROSS JOIN Digito AS c
    CROSS JOIN Digito AS d CROSS JOIN Digito AS e CROSS JOIN Digito AS f
)
INSERT dbo.LabPeriodos (Id, Anio, Mes, Importe, Detalle)
SELECT n,
       CASE WHEN n % 10 = 0 THEN 2025 ELSE 2022 + p.OffsetMes / 12 END,
       CASE WHEN n % 10 = 0 THEN 6 ELSE p.OffsetMes % 12 + 1 END,
       CAST((n % 100000) / 100.0 AS decimal(12,2)),
       CAST(CONCAT('Registro ', n, ' ', REPLICATE('X', 80)) AS char(100))
FROM Numeros
CROSS APPLY (VALUES ((n - n / 10 - 1) % 59)) AS r(Posicion)
CROSS APPLY (VALUES (r.Posicion + CASE WHEN r.Posicion >= 41 THEN 1 ELSE 0 END)) AS p(OffsetMes)
ORDER BY n
OPTION (MAXDOP 1);
-- El ORDER BY intercala periodos en el flujo de carga; un heap no garantiza
-- orden de lectura ni un orden fisico permanente.

DECLARE @Total bigint, @Objetivo bigint, @Aritmetico bigint;
SELECT @Total = COUNT_BIG(*),
       @Objetivo = SUM(CONVERT(bigint, CASE WHEN Anio = 2025 AND Mes = 6 THEN 1 ELSE 0 END)),
       @Aritmetico = SUM(CONVERT(bigint, CASE WHEN Anio * 100 + Mes = 202506 THEN 1 ELSE 0 END))
FROM dbo.LabPeriodos;

IF @Total <> 1000000 OR @Objetivo <> 100000 OR @Aritmetico <> 100000
    THROW 50003, 'La carga no cumple las cantidades esperadas.', 1;

SELECT @Total AS TotalFilas, @Objetivo AS FilasPeriodo,
       @Aritmetico AS FilasFiltroAritmetico;
SELECT Anio, Mes, COUNT_BIG(*) AS Filas
FROM dbo.LabPeriodos GROUP BY Anio, Mes ORDER BY Anio, Mes;

-- Estadisticas explicitas desde el caso 1: no son indices.
CREATE STATISTICS ST_LabPeriodos_Anio ON dbo.LabPeriodos (Anio) WITH FULLSCAN;
CREATE STATISTICS ST_LabPeriodos_Mes ON dbo.LabPeriodos (Mes) WITH FULLSCAN;
CREATE STATISTICS ST_LabPeriodos_AnioMes ON dbo.LabPeriodos (Anio, Mes) WITH FULLSCAN;

SELECT @@VERSION AS VersionSQLServer, DB_NAME() AS BaseDatos,
       compatibility_level AS Compatibilidad
FROM sys.databases WHERE database_id = DB_ID();

DECLARE @Escenario int = 1, @Iteracion int, @Consulta nvarchar(max);
WHILE @Escenario <= 4
BEGIN
    SET STATISTICS TIME OFF;
    SET STATISTICS IO OFF;

    IF @Escenario = 3
    BEGIN
        CREATE NONCLUSTERED INDEX IX_LabPeriodos_Anio ON dbo.LabPeriodos (Anio);
        CREATE NONCLUSTERED INDEX IX_LabPeriodos_Mes ON dbo.LabPeriodos (Mes);
    END;

    IF @Escenario = 4
    BEGIN
        DROP INDEX IX_LabPeriodos_Anio ON dbo.LabPeriodos;
        DROP INDEX IX_LabPeriodos_Mes ON dbo.LabPeriodos;
        CREATE CLUSTERED INDEX CX_LabPeriodos_AnioMes ON dbo.LabPeriodos (Anio, Mes);
    END;

    UPDATE STATISTICS dbo.LabPeriodos WITH FULLSCAN;

    -- Literales identicos en todas las repeticiones. Sin hints de acceso,
    -- sin RECOMPILE y sin MAXDOP en los SELECT medidos.
    SET @Consulta = CASE WHEN @Escenario = 1
        THEN N'SELECT * FROM dbo.LabPeriodos WHERE Anio * 100 + Mes = 202506;'
        ELSE N'SELECT * FROM dbo.LabPeriodos WHERE Anio = 2025 AND Mes = 6;'
    END;

    RAISERROR(N'ESCENARIO %d - CALENTAMIENTO (excluir de resultados)', 0, 1, @Escenario) WITH NOWAIT;
    EXEC sys.sp_executesql @Consulta;

    SET @Iteracion = 1;
    WHILE @Iteracion <= @Repeticiones
    BEGIN
        -- Solo la base actual de laboratorio; incluye planes autoparametrizados.
        -- Requiere ALTER ANY DATABASE SCOPED CONFIGURATION en esta base.
        -- No vacia el buffer de datos ni los planes de otras bases.
        ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
        RAISERROR(N'ESCENARIO %d - MEDICION %d - INICIO', 0, 1, @Escenario, @Iteracion) WITH NOWAIT;
        SET STATISTICS TIME ON;
        SET STATISTICS IO ON;
        EXEC sys.sp_executesql @Consulta;
        SET STATISTICS TIME OFF;
        SET STATISTICS IO OFF;
        RAISERROR(N'ESCENARIO %d - MEDICION %d - FIN', 0, 1, @Escenario, @Iteracion) WITH NOWAIT;
        SET @Iteracion += 1;
    END;

    IF @CapturarPlanes = 1
    BEGIN
        RAISERROR(N'ESCENARIO %d - PLAN REAL (excluir de tiempos)', 0, 1, @Escenario) WITH NOWAIT;
        SET STATISTICS XML ON;
        EXEC sys.sp_executesql @Consulta;
        SET STATISTICS XML OFF;
    END;

    SET @Escenario += 1;
END;

-- Comprobacion final: solo debe quedar el indice clustered compuesto.
SELECT name, type_desc FROM sys.indexes
WHERE object_id = OBJECT_ID(N'dbo.LabPeriodos');

RAISERROR(N'Laboratorio terminado. Conservar Mensajes y calcular medianas de las cinco mediciones por escenario.', 0, 1) WITH NOWAIT;
-- Quedan activadas para consultas posteriores de esta sesion.
SET STATISTICS TIME ON;
SET STATISTICS IO ON;
