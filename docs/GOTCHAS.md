

## DE-PER-020 — Con una clave de pocos valores, la partición lee menos que liquid clustering; el clustering compensa frente a nada desde unos 5 GB

**Hallazgo:** En Fabric (Spark 4.1.1, Delta 4.2.0), con la consulta `Anio=2025 AND Mes=6` (0,63 % de las filas) sobre tablas de 1, 5 y 20 GB, el porcentaje de bytes leídos fue: control 100 %; liquid clustering con `OPTIMIZE FULL` 43 %, 7,5 % y 1,2 %; partición por `(Anio, Mes)` 0,67 %, 0,64 % y 0,64 %. El tiempo de LC frente a la partición fue 0,59 vs 0,21 s, 0,62 vs 0,33 s y 0,57 vs 0,52 s. Frente al control, LC compensa desde unos 5 GB (~40 archivos tras `OPTIMIZE FULL`). En una consulta por una columna fuera de la clave (`Sucursal`) la tabla particionada fue la más lenta en los tres tamaños, y a 1 GB dejó 108 archivos de ~10 MB.

**Evidencia y alcance:** Una corrida por tamaño y consulta; 11 columnas, ~51 bytes por fila; clave de 108 combinaciones sin sesgo, un diseño que favorece a la partición. A 20 GB Fabric subió el tamaño objetivo de archivo de 128 a 256 MB. Que LC iguale a la partición en bytes cuando tamaño × selectividad alcance el tamaño objetivo de archivo es una inferencia, no una medición. No vale para claves de muchos valores distintos o con sesgo.

**Práctica:** Para claves de pocos valores y estables, la partición sigue siendo válida si casi todas las consultas filtran por ella; liquid clustering no compensa por debajo de ~5 GB. Medir con el volumen y la clave reales antes de decidir.
