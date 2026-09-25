"""Ejecuta el laboratorio local; drena todas las filas y conserva evidencia."""
import csv
import json
import platform
import re
import time
from datetime import datetime
from pathlib import Path
from statistics import median
from xml.etree import ElementTree as ET
from pymssql import _mssql

ROOT = Path(__file__).resolve().parent
OUT = ROOT / ('corrida-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
OUT.mkdir()
secret = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines())
conn = _mssql.connect(server='127.0.0.1', port='14333', user='sa',
                      password=secret['MSSQL_SA_PASSWORD'], appname='LabPeriodosBench', tds_version='7.4')
conn.query_timeout = 240
messages = []
def handler(*args):
    text = '\n'.join(a.decode('utf-8', errors='replace') for a in args if isinstance(a, bytes))
    messages.append(text)
conn.set_msghandler(handler)

def query(sql, params=None):
    conn.execute_query(sql, params)
    return [{k:v for k,v in row.items() if isinstance(k,str)} for row in conn]

def drain(sql):
    conn.execute_query(sql)
    sizes, xml = [], []
    while True:
        count = 0
        for row in conn:
            count += 1
            value = row.get(0)
            if isinstance(value, str) and '<ShowPlanXML' in value:
                xml.append(value)
        sizes.append(count)
        if not conn.nextresult():
            break
    return sizes, xml

db = 'LabPeriodos_' + datetime.now().strftime('%Y%m%d_%H%M%S')
conn.execute_non_query(f'CREATE DATABASE [{db}];')
conn.select_db(db)
setup = (ROOT / 'laboratorio.sql').read_text().split('DECLARE @Escenario int')[0]
(OUT / 'setup.sql').write_text(setup)
print('Cargando ' + db, flush=True)
sizes, _ = drain(setup)
meta = query('SELECT @@VERSION AS version, DB_NAME() AS db, compatibility_level FROM sys.databases WHERE database_id=DB_ID();')[0]
meta['client_host'] = platform.platform()
meta['host_note'] = 'Documentar arquitectura y recursos del servidor para cada corrida.'
meta['cache'] = 'ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE antes de cada medicion; buffer de datos caliente'
meta['cpu'] = query('SELECT cpu_count, scheduler_count, physical_memory_kb FROM sys.dm_os_sys_info;')[0]
meta['configuration'] = query("SELECT name, CONVERT(int,value_in_use) AS value_in_use FROM sys.configurations WHERE name IN ('max degree of parallelism','cost threshold for parallelism','max server memory (MB)');")
meta['counts'] = query('SELECT COUNT_BIG(*) AS total, SUM(CASE WHEN Anio=2025 AND Mes=6 THEN 1 ELSE 0 END) AS objetivo FROM dbo.LabPeriodos;')[0]
assert meta['counts'] == {'total':1000000, 'objetivo':100000}
(OUT / 'entorno.json').write_text(json.dumps(meta, indent=2, default=str))
raw = (OUT / 'mensajes.txt').open('w')
all_results = []
summaries = []

def cached(sql):
    return query("""SELECT cp.plan_handle FROM sys.dm_exec_cached_plans cp
        CROSS APPLY sys.dm_exec_sql_text(cp.plan_handle) t
        WHERE t.text = %s
        AND EXISTS (SELECT 1 FROM sys.dm_exec_plan_attributes(cp.plan_handle) a
                    WHERE a.attribute='dbid' AND CONVERT(int,a.value)=DB_ID());""", (sql,))

for scenario in range(1,5):
    print(f'Escenario {scenario}: preparando indices', flush=True)
    if scenario == 3:
        conn.execute_non_query('CREATE NONCLUSTERED INDEX IX_LabPeriodos_Anio ON dbo.LabPeriodos(Anio); CREATE NONCLUSTERED INDEX IX_LabPeriodos_Mes ON dbo.LabPeriodos(Mes);')
    if scenario == 4:
        conn.execute_non_query('DROP INDEX IX_LabPeriodos_Anio ON dbo.LabPeriodos; DROP INDEX IX_LabPeriodos_Mes ON dbo.LabPeriodos; CREATE CLUSTERED INDEX CX_LabPeriodos_AnioMes ON dbo.LabPeriodos(Anio,Mes);')
    conn.execute_non_query('UPDATE STATISTICS dbo.LabPeriodos WITH FULLSCAN;')
    indexes = query("SELECT name,type_desc FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.LabPeriodos');")
    (OUT / f'indices-{scenario}.json').write_text(json.dumps(indexes, indent=2))
    predicate = 'Anio * 100 + Mes = 202506' if scenario == 1 else 'Anio = 2025 AND Mes = 6'
    sql = f'/* LabPeriodosBench */ SELECT * FROM dbo.LabPeriodos WHERE {predicate};'
    (OUT / f'consulta-{scenario}.sql').write_text(sql)
    assert drain(sql)[0] == [100000]
    for iteration in range(1,6):
        handles = query('''SELECT cp.plan_handle FROM sys.dm_exec_cached_plans cp
            CROSS APPLY sys.dm_exec_plan_attributes(cp.plan_handle) a
            WHERE a.attribute='dbid' AND CONVERT(int,a.value)=DB_ID();''')
        assert cached(sql), 'No se encontro el plan calentado que se debe expulsar'
        conn.execute_non_query('ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;')
        # Inspeccion desde master para que la propia comprobacion no cree un plan en el laboratorio.
        conn.select_db('master')
        remaining=query('''SELECT cp.plan_handle FROM sys.dm_exec_cached_plans cp
            CROSS APPLY sys.dm_exec_plan_attributes(cp.plan_handle) a
            WHERE a.attribute='dbid' AND CONVERT(int,a.value)=DB_ID(%s);''',(db,))
        assert not remaining, 'Quedan planes del laboratorio en cache'
        conn.select_db(db)
        conn.execute_non_query('SET STATISTICS TIME ON; SET STATISTICS IO ON;')
        messages.clear()
        start = time.perf_counter()
        sizes, _ = drain(sql)
        client_ms = (time.perf_counter() - start)*1000
        text = '\n'.join(messages)
        conn.execute_non_query('SET STATISTICS TIME OFF; SET STATISTICS IO OFF;')
        assert sizes == [100000], sizes
        raw.write(f'ESCENARIO {scenario} MEDICION {iteration} PLANES_EXPULSADOS {len(handles)}\n{text}\n')
        raw.flush()
        execution = re.findall(r'SQL Server Execution Times:\s*CPU time = (\d+) ms,\s*elapsed time = (\d+) ms', text)
        compilation = re.findall(r'SQL Server parse and compile time:\s*CPU time = (\d+) ms,\s*elapsed time = (\d+) ms', text)
        reads = re.findall(r"Table 'LabPeriodos'.*?logical reads (\d+)", text)
        assert len(execution)==1 and len(reads)==1 and compilation, text
        shell = query("""SELECT qp.query_plan FROM sys.dm_exec_cached_plans cp
            CROSS APPLY sys.dm_exec_sql_text(cp.plan_handle) t
            CROSS APPLY sys.dm_exec_query_plan(cp.plan_handle) qp
            WHERE t.text=%s AND EXISTS (SELECT 1 FROM sys.dm_exec_plan_attributes(cp.plan_handle) a
            WHERE a.attribute='dbid' AND CONVERT(int,a.value)=DB_ID());""",(sql,))
        effective_sql = sql
        for item in shell:
            for node in ET.fromstring(item['query_plan']).iter():
                if 'ParameterizedPlanHandle' in node.attrib:
                    effective_sql=node.attrib['ParameterizedText']
        dmv = query("""SELECT qs.execution_count, qs.last_worker_time, qs.last_elapsed_time,
            qs.last_logical_reads, qs.last_physical_reads, qs.last_rows
            FROM sys.dm_exec_query_stats qs CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t
            WHERE t.text=%s
            AND EXISTS (SELECT 1 FROM sys.dm_exec_plan_attributes(qs.plan_handle) a
                        WHERE a.attribute='dbid' AND CONVERT(int,a.value)=DB_ID());""", (effective_sql,))
        assert len(dmv)==1 and dmv[0]['execution_count']==1 and dmv[0]['last_rows']==100000, dmv
        result = dict(escenario=scenario, ejecucion=iteration, filas=100000,
                      cpu_ms=int(execution[0][0]), elapsed_ms=int(execution[0][1]),
                      lecturas_logicas=int(reads[0]),
                      compilacion_cpu_ms=sum(int(c[0]) for c in compilation),
                      compilacion_elapsed_ms=sum(int(c[1]) for c in compilation),
                      cliente_ms=round(client_ms,3), planes_expulsados=len(handles), **dmv[0])
        all_results.append(result)
        print(result, flush=True)
    conn.execute_non_query('SET STATISTICS XML ON;')
    sizes, xml = drain(sql)
    conn.execute_non_query('SET STATISTICS XML OFF;')
    assert len(xml)==1 and sizes[0]==100000, (sizes,len(xml))
    (OUT / f'plan-{scenario}.sqlplan').write_text(xml[0])
    tree=ET.fromstring(xml[0]); ns={'s':'http://schemas.microsoft.com/sqlserver/2004/07/showplan'}
    operators=[e.attrib['PhysicalOp'] for e in tree.findall('.//s:RelOp',ns)]
    actual=[dict(e.attrib) for e in tree.findall('.//s:RunTimeCountersPerThread',ns)]
    (OUT / f'plan-{scenario}-resumen.json').write_text(json.dumps({'operators':operators,'runtime':actual},indent=2))
    sample=[r for r in all_results if r['escenario']==scenario]
    summary={'escenario':scenario,'operadores':operators}
    for key in ['cpu_ms','elapsed_ms','lecturas_logicas','compilacion_cpu_ms','compilacion_elapsed_ms','cliente_ms','last_worker_time','last_elapsed_time','last_physical_reads']:
        summary[key]=median(r[key] for r in sample)
    summaries.append(summary)
    # Persistir despues de cada escenario, incluso si un paso posterior falla.
    with (OUT / 'resultados.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(all_results[0]));writer.writeheader();writer.writerows(all_results)
    (OUT / 'resumen.json').write_text(json.dumps(summaries,indent=2))
raw.close()
conn.close()
print('EVIDENCIA: '+str(OUT),flush=True)
print(json.dumps(summaries,indent=2),flush=True)
