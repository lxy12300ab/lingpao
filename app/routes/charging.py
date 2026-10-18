import json
import uuid
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from .api import authorize
from .. import db, config
from ..models import Strict

router = APIRouter(prefix='/api/charging', dependencies=[Depends(authorize)])

class Charge(Strict):
    date: date
    start_pct: float = Field(ge=0, le=100)
    end_pct: float = Field(ge=0, le=100)
    grid_kwh: float | None = Field(default=None, gt=0, le=1000)
    location: str = Field(default='home', pattern='^(home|public|other)$')
    note: str = Field(default='', max_length=2000)
    expected_revision: str = ''

    @model_validator(mode='after')
    def valid(self):
        if self.end_pct <= self.start_pct:
            raise ValueError('结束电量必须大于开始电量')
        if self.date > datetime.now(config.TZ).date():
            raise ValueError('不能填写未来日期')
        return self

class Revision(Strict):
    expected_revision: str

class Meter(Strict):
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    kwh: float | None = Field(default=None, ge=0, le=100000)
    expected_revision: str = ''

def result(row):
    r = dict(row)
    r['estimated_kwh'] = round(r['capacity'] * (r['end_pct']-r['start_pct'])/100, 4)
    r['loss_kwh'] = None if r['grid_kwh'] is None else round(r['grid_kwh']-r['estimated_kwh'], 4)
    r['loss_pct'] = None if r['grid_kwh'] is None else round(r['loss_kwh']/r['grid_kwh']*100, 2)
    return r

@router.get('')
def list_charges():
    with db.connect() as c:
        return {'records': [result(r) for r in c.execute('SELECT * FROM charging WHERE deleted=0 ORDER BY date DESC,id DESC')],
                'meters': [dict(r) for r in c.execute('SELECT * FROM charging_meter ORDER BY month DESC')]}

def save(body, cid=None):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        old = c.execute('SELECT * FROM charging WHERE id=? AND deleted=0',(cid,)).fetchone() if cid else None
        if cid and not old:
            raise HTTPException(404, '充电记录不存在')
        if (old['revision'] if old else '') != body.expected_revision:
            raise HTTPException(409, '记录已变化，请关闭并刷新后重试')
        stamp, revision = config.now(), uuid.uuid4().hex
        values = (str(body.date),body.start_pct,body.end_pct,body.grid_kwh,body.location,body.note,revision,stamp)
        if cid:
            c.execute('UPDATE charging SET date=?,start_pct=?,end_pct=?,grid_kwh=?,location=?,note=?,revision=?,updated_at=? WHERE id=?',(*values,cid))
        else:
            cid = c.execute('INSERT INTO charging(date,start_pct,end_pct,grid_kwh,location,note,revision,updated_at,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(*values,stamp)).lastrowid
        after = result(c.execute('SELECT * FROM charging WHERE id=?',(cid,)).fetchone())
        db.log(c,'charge_save',cid,'ok',json.dumps({'before':dict(old) if old else None,'after':after},ensure_ascii=False))
        return after

@router.post('')
def create(body: Charge):
    return save(body)

@router.put('/{cid}')
def update(cid: int, body: Charge):
    return save(body,cid)

@router.delete('/{cid}')
def delete(cid: int, body: Revision):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT * FROM charging WHERE id=? AND deleted=0',(cid,)).fetchone()
        if not old:
            raise HTTPException(404,'记录不存在')
        if old['revision'] != body.expected_revision:
            raise HTTPException(409,'记录已变化，请刷新后重试')
        c.execute('UPDATE charging SET deleted=1,updated_at=?,revision=? WHERE id=?',(config.now(),uuid.uuid4().hex,cid))
        db.log(c,'charge_delete',cid,'ok',json.dumps(dict(old),ensure_ascii=False))
    return {'status':'ok'}

@router.post('/meter')
def meter(body: Meter):
    if body.month > datetime.now(config.TZ).strftime('%Y-%m'):
        raise HTTPException(422,'不能填写未来月份')
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT * FROM charging_meter WHERE month=?',(body.month,)).fetchone()
        if (old['revision'] if old else '') != body.expected_revision:
            raise HTTPException(409,'月度电表数据已变化，请刷新后重试')
        c.execute('INSERT INTO charging_meter VALUES(?,?,?) ON CONFLICT(month) DO UPDATE SET kwh=excluded.kwh,revision=excluded.revision',
                  (body.month,body.kwh,uuid.uuid4().hex))
        db.log(c,'charge_meter',body.month,'ok',json.dumps({'before':dict(old) if old else None,'after':body.model_dump()}))
    return {'status':'ok'}
