# Decisiones con evidencia medida

- Repetir la ronda Delta completa: dos mediciones iniciales leyeron bytes remotos. [Ronda inicial](../results/databricks/initial.csv), [ronda final](../results/databricks/mediciones.csv), [ejecutor](../databricks/ejecutar.py).
- Presentar reducción de lecturas del clustered SQL (16.130 a 1.733) sin adjudicar mejora a índices individuales no usados. [Resumen](../results/sql-server/resumen.json), [ejecutor](../sql-server/ejecutar.py).
- Limitar conclusión Delta: 480 archivos particionados frente a un único archivo liquid en una base de 4,1 MB. [Layouts](../results/databricks/layouts.json). No recomendar producción desde esa escala.
