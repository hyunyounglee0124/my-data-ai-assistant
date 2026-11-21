import os
import tempfile
from pathlib import Path

p = Path(tempfile.mkdtemp()) / 'test.db'
os.environ['DATABASE_PATH'] = str(p)
os.environ.pop('CODYSSEY_API_KEY', None)
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

def test_crud_analysis_chat():
    a=client.post('/api/records',json={'date':'2026-11-01','value':10,'memo':'첫날'})
    assert a.status_code==201
    rid=a.json()['id']
    assert client.get('/api/records').json()[0]['memo']=='첫날'
    assert client.put(f'/api/records/{rid}',json={'date':'2026-11-02','value':20,'memo':'변경'}).status_code==200
    b=client.post('/api/records',json={'date':'2026-11-03','value':30,'memo':'마지막'})
    assert b.status_code==201
    s=client.get('/api/analysis').json()
    assert s['count']==2 and s['total']==50 and s['change']==10
    assert client.post('/api/analysis/save').status_code==200
    assert len(client.get('/api/analysis/history').json())==1
    reply=client.post('/api/chat',json={'question':'합계가 얼마야?'})
    assert reply.status_code==200 and reply.json()['mode']=='local'
    assert client.delete(f'/api/records/{rid}').status_code==200
    assert client.delete(f'/api/records/{rid}').status_code==404

def test_validation():
    assert client.post('/api/records',json={'date':'not-a-date','value':3}).status_code==422
    assert client.post('/api/chat',json={'question':''}).status_code==422
