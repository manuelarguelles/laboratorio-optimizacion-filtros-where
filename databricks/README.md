# Ejecutar Databricks

Requisitos: Python 3, Databricks CLI con OAuth autenticado, warehouse SQL y permisos para crear esquemas/tablas, desactivar predictive optimization en el esquema del laboratorio, usar liquid clustering con OPTIMIZE FULL y consultar el historial de las propias consultas. El original usó Small serverless Photon. La disponibilidad depende del entorno contratado.

Desde esta carpeta, sustituir los valores de ejemplo por los propios:

```sh
databricks auth login --host https://YOUR-WORKSPACE --profile period-lab
export DATABRICKS_CONFIG_PROFILE=period-lab
export DATABRICKS_WAREHOUSE_ID=YOUR_WAREHOUSE_ID
export DATABRICKS_CATALOG=workspace
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python ejecutar.py
```

El token se obtiene de la sesión CLI y se utiliza en memoria; no se imprime. El script crea un esquema con fecha y tres tablas. Genera 1M filas, verifica igualdad, mide cuatro escenarios y exporta planes/historial a corrida-<fecha>. Cada consulta abre una sesión con result cache desactivado y consume 100k filas. No se afirma limpiar la caché interna de planes. La ejecución usa cómputo del warehouse y deja tablas para inspección.

Para repetir la ronda completa sobre las mismas tablas, en el mismo workspace y catálogo:

```sh
export LAB_REUSE_RUN=/ruta/a/la/corrida-anterior
.venv/bin/python ejecutar.py
```

Revisar read_remote_bytes en todas las mediciones. Conservar tanto la ronda anterior como la repetida; no escoger muestras de diferentes rondas. Las sesiones serverless pueden cambiar de residencia entre ejecuciones.

[laboratorio.sql](laboratorio.sql) es la versión manual con esquema genérico workspace.period_filter_lab; [ejecutar.py](ejecutar.py) genera nombres por corrida y automatiza el protocolo. Los archivos locales de nuevas corridas contienen metadatos privados: no publicarlos sin aplicar la selección documentada en [procedencia](../docs/PROCEDENCIA.md).
