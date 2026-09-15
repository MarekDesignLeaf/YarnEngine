from pathlib import Path
from fastapi.testclient import TestClient
from src.web.app import app

client=TestClient(app)

def test_chart_endpoint_stockinette():
    r=client.get('/api/patterns/STOCKINETTE/1.0.0/chart')
    assert r.status_code==200
    d=r.json()
    assert d['repeat_width']==1
    assert d['repeat_height']==2
    assert len(d['rows'])==2
    assert d['legend']


def test_chart_cable_spans_four_stitches():
    r=client.get('/api/patterns/CABLE_2X2_SIMPLE/1.0.0/chart')
    assert r.status_code==200
    d=r.json()
    row3=next(x for x in d['rows'] if x['row']==3)
    cable=next(x for x in row3['cells'] if x['op']=='C2_2R')
    assert cable['span']==4
    assert row3['produced_columns']==8


def test_chart_balanced_eyelet_matches_repeat_width():
    r=client.get('/api/patterns/EYELET_BALANCED/1.0.0/chart')
    assert r.status_code==200
    d=r.json()
    assert all(x['produced_columns']==d['repeat_width'] for x in d['rows'])
    assert d['warnings']==[]


def test_chart_missing_pattern_404():
    assert client.get('/api/patterns/NO_SUCH/1.0.0/chart').status_code==404
