"""Laboratorio Delta: tres layouts, cuatro escenarios, sin result cache."""
import re
import csv
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from statistics import median

import requests
from databricks import sql

ROOT = Path(__file__).resolve().parent
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
OUT = ROOT / ('corrida-' + STAMP)
OUT.mkdir()
PROFILE = os.environ.get('DATABRICKS_CONFIG_PROFILE','DEFAULT')
WAREHOUSE = os.environ['DATABRICKS_WAREHOUSE_ID']
CATALOG = os.environ.get('DATABRICKS_CATALOG','workspace')
if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', CATALOG):
    raise ValueError('Usar un catalogo con identificador simple para este laboratorio')
SCHEMA = CATALOG + '.lab_periodos_' + STAMP
config = json.loads(subprocess.check_output(
    ['databricks','auth','env','--profile',PROFILE],text=True))['env']
host = config['DATABRICKS_HOST'].rstrip('/')
token = json.loads(subprocess.check_output(
    ['databricks','auth','token','-p',PROFILE],text=True))['access_token']
http = requests.Session()
http.headers['Authorization'] = 'Bearer ' + token
start_ms = int(time.time()*1000)
ledger = []
statements = []

def connect():
    return sql.connect(server_hostname=host.removeprefix('https://'),
                       http_path='/sql/1.0/warehouses/' + WAREHOUSE,
                       access_token=token,
                       session_configuration={'use_cached_result':'false'},
                       user_agent_entry='LabPeriodosBenchmark')

def run(cur, statement):
    print(statement.splitlines()[0][:100], flush=True)
    statements.append(statement)
    (OUT/'laboratorio.sql').write_text(';\n\n'.join(statements)+';\n')
    cur.execute(statement)
    rows=cur.fetchall()
    ledger.append({'query_id':cur.query_id,'sql':statement,'rows':len(rows)})
    (OUT/'operaciones.json').write_text(json.dumps(ledger,indent=2))
    return [r.asDict() for r in rows]

reuse=os.environ.get('LAB_REUSE_RUN')
if reuse:
    previous=Path(reuse)
    environment=json.loads((previous/'entorno.json').read_text())
    SCHEMA=environment['schema']
    environment['reused_from']=str(previous)
    (OUT/'entorno.json').write_text(json.dumps(environment,indent=2))
    (OUT/'layouts.json').write_text((previous/'layouts.json').read_text())
else:
    with connect() as conn, conn.cursor() as cur:
        settings = run(cur,'SET use_cached_result')
        assert str(settings[0]['value']).lower() == 'false', settings
        version = run(cur,'SELECT current_version() AS version, current_user() AS usuario')
        run(cur,f'CREATE SCHEMA {SCHEMA}')
        run(cur,f'ALTER SCHEMA {SCHEMA} DISABLE PREDICTIVE OPTIMIZATION')
        # Mismos valores que en SQL Server. Solo difiere CHAR(100) -> STRING de 100 caracteres.
        run(cur,f'''CREATE TABLE {SCHEMA}.base USING DELTA
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
    FROM offsets''')
        run(cur,f'''CREATE TABLE {SCHEMA}.particionada USING DELTA PARTITIONED BY (Anio,Mes)
    TBLPROPERTIES ('delta.autoOptimize.optimizeWrite'='false', 'delta.autoOptimize.autoCompact'='false')
    AS SELECT * FROM {SCHEMA}.base''')
        run(cur,f'''CREATE TABLE {SCHEMA}.clusterizada USING DELTA CLUSTER BY (Anio,Mes)
    AS SELECT * FROM {SCHEMA}.base''')
        optimization = run(cur,f'OPTIMIZE {SCHEMA}.clusterizada FULL')
        layouts = {}
        cols='Id,Anio,Mes,Importe,Detalle'
        for table in ['base','particionada','clusterizada']:
            full=f'{SCHEMA}.{table}'
            counts=run(cur,f'''SELECT count(*) AS total,
                count_if(Anio=2025 AND Mes=6) AS objetivo,
                count_if(Anio*100+Mes=202506) AS objetivo_aritmetico,
                count(DISTINCT Id) AS ids,
                min(length(Detalle)) AS largo_min, max(length(Detalle)) AS largo_max FROM {full}''')[0]
            assert counts == dict(total=1000000,objetivo=100000,objetivo_aritmetico=100000,ids=1000000,largo_min=100,largo_max=100), counts
            if table!='base':
                for left,right in [('base',table),(table,'base')]:
                    diff=run(cur,f'SELECT count(*) AS diferencias FROM (SELECT {cols} FROM {SCHEMA}.{left} EXCEPT ALL SELECT {cols} FROM {SCHEMA}.{right})')[0]
                    assert diff['diferencias']==0,diff
            run(cur,f'ANALYZE TABLE {full} COMPUTE STATISTICS FOR COLUMNS Anio,Mes')
            layouts[table]={'counts':counts,'detail':run(cur,f'DESCRIBE DETAIL {full}'),
                            'history':run(cur,f'DESCRIBE HISTORY {full} LIMIT 1'),
                            'files':run(cur,f'''SELECT _metadata.file_path AS path, count(*) AS filas,
                                min(Anio*100+Mes) AS periodo_min,max(Anio*100+Mes) AS periodo_max
                                FROM {full} GROUP BY _metadata.file_path''')}
        (OUT/'layouts.json').write_text(json.dumps(layouts,indent=2,default=str))
        (OUT/'entorno.json').write_text(json.dumps({'profile':PROFILE,'host':host,'warehouse':WAREHOUSE,
            'schema':SCHEMA,'version':version,'settings':settings,'optimization':optimization},indent=2,default=str))

samples=[]
queries={1:('base','Anio*100+Mes=202506'),2:('base','Anio=2025 AND Mes=6'),
         3:('particionada','Anio=2025 AND Mes=6'),4:('clusterizada','Anio=2025 AND Mes=6')}
for scenario,(table,predicate) in queries.items():
    for iteration in range(0,6):
        # Sesion nueva; no afirma limpiar una cache interna de planes del warehouse.
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SET use_cached_result')
            assert str(cur.fetchall()[0]['value']).lower()=='false'
            statement=f'/* LabPeriodos {STAMP} escenario={scenario} iteracion={iteration} */ SELECT * FROM {SCHEMA}.{table} WHERE {predicate}'
            t=time.perf_counter()
            cur.execute(statement)
            query_id=cur.query_id
            rows=0
            while True:
                batch=cur.fetchmany_arrow(10000)
                if batch.num_rows==0:
                    break
                rows+=batch.num_rows
            elapsed=(time.perf_counter()-t)*1000
            assert rows==100000,(scenario,iteration,rows)
            sample=dict(escenario=scenario,ejecucion=iteration,query_id=query_id,
                        filas=rows,cliente_ms=round(elapsed,3),sql=statement)
            samples.append(sample)
            (OUT/'consultas.json').write_text(json.dumps(samples,indent=2))
            print(f'E{scenario} iteracion {iteration}: {rows} filas; cliente {elapsed:.0f} ms; {query_id}',flush=True)
    with connect() as conn, conn.cursor() as cur:
        explanation=run(cur,f'EXPLAIN FORMATTED SELECT * FROM {SCHEMA}.{table} WHERE {predicate}')
        (OUT/f'plan-{scenario}.txt').write_text('\n'.join(str(next(iter(r.values()))) for r in explanation))

# Historial: usar metricas del motor, no confundir RTT/fetch con ejecucion.
wanted={s['query_id'] for s in samples}
found={}
for attempt in range(20):
    payload={'max_results':100,'include_metrics':True,
             'filter_by':{'warehouse_ids':[WAREHOUSE],
                          'query_start_time_range':{'start_time_ms':start_ms}}}
    response=http.get(host+'/api/2.0/sql/history/queries',json=payload,timeout=40)
    response.raise_for_status()
    data=response.json()
    found.update({q['query_id']:q for q in data.get('res',[]) if q['query_id'] in wanted})
    if wanted<=found.keys() and all(found[q].get('is_final') for q in wanted):
        break
    print(f'Esperando metricas finales: {len(found)}/{len(wanted)}',flush=True)
    time.sleep(3)
assert wanted<=found.keys(),wanted-found.keys()
(OUT/'historial.json').write_text(json.dumps(found,indent=2))
result=[]
metrics=['execution_time_ms','compilation_time_ms','total_time_ms','task_total_time_ms',
         'read_bytes','read_files_count','pruned_files_count','rows_read_count',
         'read_cache_bytes','read_remote_bytes','result_from_cache']
for s in samples:
    q=found[s['query_id']]; m=q['metrics']
    assert q['status']=='FINISHED' and q.get('is_final'),q
    assert m['result_from_cache'] is False,(s,m)
    assert q['rows_produced']==100000,(s,q['rows_produced'])
    if s['ejecucion']==0: continue
    result.append({k:v for k,v in s.items() if k!='sql'} | {k:m.get(k) for k in metrics})
with (OUT/'resultados.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
summaries=[]
for scenario in range(1,5):
    part=[r for r in result if r['escenario']==scenario]
    sm={'escenario':scenario}
    for key in metrics+['cliente_ms']:
        values=[r[key] for r in part]
        sm[key]=median(values) if all(v is not None for v in values) else None
    summaries.append(sm)
(OUT/'resumen.json').write_text(json.dumps(summaries,indent=2))
print(json.dumps(summaries,indent=2),flush=True)
print('EVIDENCIA: '+str(OUT),flush=True)
