# Ejecutar SQL Server

Requisitos: Docker, Python 3 con venv y acceso al puerto local 14333. El laboratorio crea una base nueva por corrida y usa sa para creación, estadísticas y DMV. Usar una instancia dedicada. Conserva la base y los resultados para inspección.

Desde esta carpeta:

```sh
cp .env.example .env
chmod 600 .env
# Editar .env y reemplazar MSSQL_SA_PASSWORD por una contraseña propia.
docker run -d --name period-filter-sql --platform linux/amd64 --cpus 2 --memory 4g --env-file .env -p 127.0.0.1:14333:1433 mcr.microsoft.com/mssql/server@sha256:4402d880dd4c34bfa7d8705e56a86cd6c88da80a1f6bbbe741f999e76264a090
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Esperar a que SQL Server acepte conexiones.
.venv/bin/python ejecutar.py
```

La imagen archivada corresponde al laboratorio SQL Server 2022 CU27 Developer. ACCEPT_EULA=Y acepta los términos de la imagen; Developer se utiliza aquí para desarrollo/pruebas. En ARM el experimento original dependió de traducción x86; registrar arquitectura y recursos de cualquier reproducción.

El ejecutor lee .env, conecta a localhost:14333 y escribe corrida-<fecha>. Consume todas las filas, habilita STATISTICS TIME/IO, limpia la caché de planes de la base aislada y registra validaciones. Los planes reales se capturan fuera de la medición. No enfría la caché de datos.

[laboratorio.sql](laboratorio.sql) sirve para inspección/manual en SSMS; [ejecutar.py](ejecutar.py) es el protocolo automatizado con resultados estructurados. [Evidencia publicada](../results/sql-server/mediciones.csv).
