import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv('DATABASE_PATH', str(ROOT / 'data' / 'assistant.db')))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
app = FastAPI(title='내 데이터를 아는 AI 비서', version='1.0.0')

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def initialize():
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, value REAL NOT NULL, memo TEXT NOT NULL DEFAULT "", created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_records_date ON records(date)')
        c.execute('CREATE TABLE IF NOT EXISTS analysis_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, record_count INTEGER NOT NULL, summary TEXT NOT NULL)')
initialize()

class Record(BaseModel):
    date: date
    value: float = Field(ge=-1e12, le=1e12)
    memo: str = Field(default='', max_length=500)

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

def records():
    with db() as c:
        return [dict(r) for r in c.execute('SELECT id, date, value, memo FROM records ORDER BY date ASC, id ASC')]

def analyze(items):
    vals = [r['value'] for r in items]
    by_date = {}
    for r in items:
        by_date[r['date']] = by_date.get(r['date'], 0) + r['value']
    series = [{'date': d, 'value': round(v, 4)} for d, v in sorted(by_date.items())]
    total = sum(vals)
    first, last = (series[0]['value'], series[-1]['value']) if series else (0, 0)
    change = last - first
    percent = (change / abs(first) * 100) if first else None
    return {'count': len(items), 'total': round(total, 4), 'average': round(total / len(vals), 4) if vals else 0,
            'minimum': min(vals) if vals else None, 'maximum': max(vals) if vals else None,
            'first_date': series[0]['date'] if series else None, 'last_date': series[-1]['date'] if series else None,
            'first_daily_value': first, 'last_daily_value': last, 'change': round(change, 4),
            'change_percent': round(percent, 2) if percent is not None else None, 'series': series}

@app.get('/')
def home():
    return FileResponse(ROOT / 'static' / 'index.html')

@app.get('/api/records')
def list_records():
    return records()

@app.post('/api/records', status_code=201)
def add_record(payload: Record):
    with db() as c:
        cur = c.execute('INSERT INTO records(date,value,memo) VALUES(?,?,?)', (payload.date.isoformat(), payload.value, payload.memo))
        return {'id': cur.lastrowid, **payload.model_dump(mode='json')}

@app.put('/api/records/{record_id}')
def edit_record(record_id: int, payload: Record):
    with db() as c:
        cur = c.execute('UPDATE records SET date=?, value=?, memo=? WHERE id=?', (payload.date.isoformat(), payload.value, payload.memo, record_id))
        if not cur.rowcount:
            raise HTTPException(404, '데이터가 없습니다.')
    return {'id': record_id, **payload.model_dump(mode='json')}

@app.delete('/api/records/{record_id}')
def delete_record(record_id: int):
    with db() as c:
        cur = c.execute('DELETE FROM records WHERE id=?', (record_id,))
        if not cur.rowcount:
            raise HTTPException(404, '데이터가 없습니다.')
    return {'deleted': True}

@app.get('/api/analysis')
def get_analysis():
    return analyze(records())

@app.post('/api/analysis/save')
def save_analysis():
    import json
    summary = analyze(records())
    with db() as c:
        cur = c.execute('INSERT INTO analysis_snapshots(record_count,summary) VALUES(?,?)', (summary['count'], json.dumps(summary, ensure_ascii=False)))
    return {'snapshot_id': cur.lastrowid, 'summary': summary}

@app.get('/api/analysis/history')
def history():
    import json
    with db() as c:
        return [{**dict(r), 'summary': json.loads(r['summary'])} for r in c.execute('SELECT * FROM analysis_snapshots ORDER BY id DESC LIMIT 30')]

def local_answer(question, summary, items):
    if not items:
        return '아직 저장된 데이터가 없습니다. 데이터 관리에서 날짜, 값, 메모를 먼저 등록해 주세요.'
    q = question.replace(' ', '')
    if '이번달' in q or '지난달' in q:
        today = date.today()
        start = today.replace(day=1)
        if '지난달' in q:
            start = (start - timedelta(days=1)).replace(day=1)
            end = today.replace(day=1)
        else:
            end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        subset = [r for r in items if start.isoformat() <= r['date'] < end.isoformat()]
        s = analyze(subset)
        return f'{start:%Y년 %m월}에는 {s["count"]}건이 기록되었으며 합계는 {s["total"]:,.2f}, 평균은 {s["average"]:,.2f}입니다.' if subset else f'{start:%Y년 %m월}에 등록된 데이터가 없습니다.'
    trend = '증가' if summary['change'] > 0 else '감소' if summary['change'] < 0 else '변화 없음'
    return (f'저장된 {summary["count"]}건을 분석했습니다. 전체 합계 {summary["total"]:,.2f}, 평균 {summary["average"]:,.2f}, '
            f'최솟값 {summary["minimum"]:,.2f}, 최댓값 {summary["maximum"]:,.2f}입니다. '
            f'첫 기록일({summary["first_date"]})과 마지막 기록일({summary["last_date"]})의 일별 합계를 비교하면 {trend}({summary["change"]:+,.2f})입니다. '
            '동일 날짜에 여러 기록이 있다면 일별 합계로 비교했습니다. 이 답변은 저장된 데이터에 근거한 기본 분석입니다.')

@app.post('/api/chat')
async def chat(payload: ChatRequest):
    items = records()
    summary = analyze(items)
    fallback = local_answer(payload.question, summary, items)
    key = os.getenv('CODYSSEY_API_KEY', '').strip()
    if not key or key.startswith('여기에_'):
        return {'answer': fallback, 'mode': 'local', 'notice': 'API 키 미설정: 기본 데이터 분석 응답입니다.'}
    base = os.getenv('CODYSSEY_BASE_URL', 'https://copa.codyssey.kr/v1').rstrip('/')
    model = os.getenv('CODYSSEY_MODEL', 'gpt-5-mini')
    context = {'summary': summary, 'records': items[-300:]}
    import json
    messages = [{'role': 'system', 'content': '당신은 한국어 데이터 분석 비서입니다. 제공된 기록만 근거로 답변하세요. 데이터가 없거나 판단 불가하면 명시하세요. 기록의 값에 통화 단위가 없으므로 임의로 원화라고 가정하지 마세요. 날짜별 기록과 요약을 구분하세요. 간결하고 정확하게 설명하세요. 데이터: ' + json.dumps(context, ensure_ascii=False)}, {'role': 'user', 'content': payload.question}]
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.post(base + '/chat/completions', headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, json={'model': model, 'messages': messages})
            response.raise_for_status()
            answer = response.json()['choices'][0]['message']['content']
        return {'answer': answer, 'mode': 'ai'}
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        return {'answer': fallback, 'mode': 'local', 'notice': 'AI 연결 실패로 기본 분석으로 전환했습니다. 서버 설정 및 API 사용량을 확인하세요.'}
