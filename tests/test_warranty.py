from datetime import date
from fastapi.testclient import TestClient
from app import config, warranty, db
from app.main import app

def settings(**changes):
    return dict(delivery='2026-07-18', limit=35000, baseline_date='2026-07-18',
                baseline=0, captured_date='2026-09-24', odometer=7406,
                kind='intraday', **changes)

def test_intraday_never_double_counts():
    s = settings()
    result = warranty.summarize(s, [{'date':'2026-09-24','km':100}, {'date':'2026-09-25','km':100}], date(2026,9,25))
    assert result['used'] == 7406 and result['remaining'] == 27594
    assert result['projection'] is None
    assert warranty.summarize(s, [], date(2027,7,18))['used'] is None

def test_end_of_day_missing_and_projection():
    s=settings();s['kind']='end_of_day'
    r=warranty.summarize(s,[{'date':'2026-09-25','km':100}],date(2026,9,25))
    assert r['used']==7506 and r['projection'] is None
    assert r['level']=='tracking'
    r=warranty.summarize(s,[],date(2026,9,26))
    assert r['projection'] is None and '缺少 1 天' in r['message']
    assert warranty.cycle(date(2024,2,29),date(2025,3,1))[0]==date(2025,2,28)

def test_recent_weeks_forecast():
    from datetime import timedelta
    s=settings();s.update(kind='end_of_day', odometer=7441)
    rows=[{'date':str(date(2026,8,24)+timedelta(days=i)), 'km':70} for i in range(28)]
    rows.append({'date':'2026-09-25','km':29})
    r=warranty.summarize(s,rows,date(2026,9,25))
    assert len(r['sample_weeks'])==4 and r['weekly_average']==490
    assert r['projection']==7470+41+70*295
    assert r['extra_budget']==35000-r['projection']
    # Missing a day excludes a week; explicit zero is valid.
    rows[0]['km']=0
    assert len(warranty.summarize(s,rows,date(2026,9,25))['sample_weeks'])==4
    rows.pop(0)
    assert len(warranty.summarize(s,rows,date(2026,9,25))['sample_weeks'])==3

def test_calibration_api(storage):
    with TestClient(app) as client:
        assert client.get('/api/warranty').status_code==401
        client.headers['Authorization']='Bearer '+config.TOKEN
        assert not client.get('/api/warranty').json()['configured']
        # Use runtime dates to keep this test independent of the day it is run.
        today=date.fromisoformat(config.now()[:10])
        start,_=warranty.cycle(date(2020,7,18),today)
        body=settings();body.update(delivery='2020-07-18',baseline_date=str(start),captured_date=str(today))
        before=db.get_data()
        response=client.put('/api/warranty',json=body)
        assert response.status_code==200
        assert client.put('/api/warranty',json=body).status_code==409
        body['expected_revision']=response.json()['settings']['revision']
        body['odometer']=-1
        assert client.put('/api/warranty',json=body).status_code==422
        assert db.get_data()==before
