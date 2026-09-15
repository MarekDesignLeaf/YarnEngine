from fastapi.testclient import TestClient
from src.web.app import app

client=TestClient(app)


def test_health():
    r=client.get('/api/health')
    assert r.status_code==200
    assert r.json()['version']=='M11.0'


def test_library_endpoints():
    p=client.get('/api/patterns')
    y=client.get('/api/yarns')
    assert p.status_code==200 and len(p.json())>=7
    assert y.status_code==200 and len(y.json())>=2


def test_swatch_calculation():
    payload={
      'pattern_id':'RIB_2X2','pattern_version':'1.0.0','yarn_id':'TEST_Y1',
      'width_cm':50,'height_cm':60,'gauge_stitches_per_10cm':20,'gauge_rows_per_10cm':28,
      'allowance_percent':8,'partial_repeat_mode':'reject',
      'edges':{'left_stitches':2,'right_stitches':2,'left_operation':'K','right_operation':'K'},
      'calculation_mode':'swatch','swatch':{'stitches':40,'rows':56,'yarn_length_m':15},
      'yarn_diameter_mm':None
    }
    r=client.post('/api/calculate',json=payload)
    assert r.status_code==200, r.text
    d=r.json()
    assert d['consumption']['tier']=='A'
    assert d['consumption']['recommended_length_m']>d['consumption']['core_length_m']
    assert d['project']['stitches']==100
    assert d['project']['rows']==168
    assert d['consumption']['packages'] is not None


def test_geometry_restricted_to_stockinette():
    payload={
      'pattern_id':'CABLE_2X2_SIMPLE','pattern_version':'1.0.0','yarn_id':None,
      'width_cm':50,'height_cm':60,'gauge_stitches_per_10cm':20,'gauge_rows_per_10cm':28,
      'allowance_percent':8,'partial_repeat_mode':'reject',
      'edges':{'left_stitches':0,'right_stitches':0,'left_operation':'K','right_operation':'K'},
      'calculation_mode':'geometry','swatch':None,'yarn_diameter_mm':1.0
    }
    r=client.post('/api/calculate',json=payload)
    assert r.status_code==422
    assert 'STOCKINETTE' in r.json()['detail']


def test_geometry_stockinette():
    payload={
      'pattern_id':'STOCKINETTE','pattern_version':'1.0.0','yarn_id':'TEST_Y1',
      'width_cm':50,'height_cm':60,'gauge_stitches_per_10cm':20,'gauge_rows_per_10cm':28,
      'allowance_percent':8,'partial_repeat_mode':'reject',
      'edges':{'left_stitches':0,'right_stitches':0,'left_operation':'K','right_operation':'K'},
      'calculation_mode':'geometry','swatch':None,'yarn_diameter_mm':1.0
    }
    r=client.post('/api/calculate',json=payload)
    assert r.status_code==200, r.text
    assert r.json()['consumption']['tier']=='B'
    assert r.json()['confidence']['level']=='research'
