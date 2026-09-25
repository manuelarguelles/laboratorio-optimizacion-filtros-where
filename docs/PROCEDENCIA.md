# Procedencia y exportación

Experimentos originales: 24-sep-2026. Exportación pública: 25-sep-2026.

SQL Server: corrida final 153905, cinco mediciones por cada uno de cuatro escenarios. Databricks: ronda inicial 162323 y ronda final 162841 sobre las mismas tablas. Las tentativas diagnósticas incompletas no integran las medianas.

Los CSV preservan números, orden y repeticiones; en Delta se omiten los query IDs. Se incluyen resúmenes, planes, índices SQL y mensajes TIME/IO. Del historial Delta se exportan solo escenario, iteración, estado, filas y métricas; se omiten SQL contextual e identidades. Los layouts publican conteos y tamaños, no ubicaciones.

Se reemplazaron nombres de bases/esquemas del entorno por nombres genéricos y ubicaciones de almacenamiento por un bucket de ejemplo. Se excluyeron credenciales, archivos .env, usuarios, host y ID del warehouse, identificadores de consultas, perfil personal, rutas locales y el historial privado completo.

Los scripts se adaptaron para configurar el entorno mediante variables locales. Su sintaxis y la coherencia de la evidencia se verifican offline; la versión publicada no se volvió a ejecutar remotamente durante esta exportación. Las dependencias indican la versión del conector utilizada, sin congelar todo el entorno original.

[SHA256SUMS](../results/SHA256SUMS) permite verificar integridad de los archivos de evidencia exportados; no es una firma ni un hash de los originales privados. Los diagnósticos cualitativos se describen en gotchas, sin publicar trazas privadas de autenticación.
