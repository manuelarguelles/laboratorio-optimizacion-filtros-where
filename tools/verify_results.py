"""Validación offline de evidencia publicada; no ejecuta consultas remotas."""
import ast
import csv
import hashlib
import json
import re
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def rows(engine, name='mediciones.csv'):
    with (ROOT/'results'/engine/name).open() as f:
        result = list(csv.DictReader(f))
    assert len(result) == 20
    assert {(int(r['escenario']), int(r['ejecucion'])) for r in result} == {(s,i) for s in range(1,5) for i in range(1,6)}
    assert all(int(r['filas']) == 100000 for r in result)
    return result

for engine in ('sql-server', 'databricks'):
    data = rows(engine)
    summaries = json.loads((ROOT/'results'/engine/'resumen.json').read_text())
    for summary in summaries:
        selected = [r for r in data if int(r['escenario']) == summary['escenario']]
        for key, value in summary.items():
            if key == 'escenario' or key not in selected[0]:
                continue
            if isinstance(value, bool):
                assert all(r[key].lower() == str(value).lower() for r in selected)
            else:
                assert abs(statistics.median(float(r[key]) for r in selected)-value) < 0.00001, (engine,key)
    if engine == 'sql-server':
        assert all(int(r['execution_count']) == 1 and int(r['last_rows']) == 100000 and int(r['last_physical_reads']) == 0 for r in data)
        for i in range(1,5):
            tree = ET.parse(ROOT/'results'/engine/f'plan-{i}.sqlplan')
            operators = {e.get('PhysicalOp') for e in tree.iter() if e.get('PhysicalOp')}
            assert ('Table Scan' if i < 4 else 'Clustered Index Seek') in operators
    else:
        assert all(r['result_from_cache'] == 'False' and int(r['read_remote_bytes']) == 0 for r in data)
        history = json.loads((ROOT/'results'/engine/'metricas-historial.json').read_text())
        assert len(history) == 24
        assert all(r['status'] == 'FINISHED' and r['metrics']['result_from_cache'] is False and r['rows_produced'] == 100000 for r in history)
initial = rows('databricks', 'initial.csv')
assert sorted(int(r['read_remote_bytes']) for r in initial if int(r['read_remote_bytes'])) == [622893,1296322]
for path in ROOT.rglob('*.py'):
    if '.git' not in path.parts:
        ast.parse(path.read_text(), filename=str(path))
for path in ROOT.rglob('*.md'):
    for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        if '://' not in link and not link.startswith('#'):
            assert (path.parent/link.split('#')[0]).exists(), (path,link)
for line in (ROOT/'results/SHA256SUMS').read_text().splitlines():
    expected, relative = line.split('  ',1)
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == expected, relative
print('OK: 40 mediciones finales + 20 iniciales, medianas, cachés, 24 entradas de historial, planes XML, sintaxis, enlaces e integridad.')
