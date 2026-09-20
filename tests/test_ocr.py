import os
from datetime import date
from pathlib import Path
import pytest
from app.ocr import period_for, recognize
from app import ocr
from PIL import Image

def test_column_retry_requires_agreement(monkeypatch):
    image = Image.new('RGB', (1320, 2868), 'white')
    label = {'text':'7/', 'x':620, 'y':2144, 'w':43, 'h':30}
    answers = iter(['7', '77', '77'])
    monkeypatch.setattr(ocr, 'text', lambda *a: next(answers))
    assert ocr.retry_daily_label(image, [label], 641, 172)[0] == 77
    answers = iter(['7', '77', '777'])
    assert ocr.retry_daily_label(image, [label], 641, 172)[0] is None
    assert ocr.retry_daily_label(image, [], 641, 172) == (None, [])
    assert ocr.retry_daily_label(image, [label, label], 641, 172) == (None, [])

@pytest.mark.skipif(not os.getenv('OCR_FIXTURE_SEP20'), reason='Private screenshot path supplied externally')
def test_september20_regression(monkeypatch):
    path = Path(os.environ['OCR_FIXTURE_SEP20'])
    result = recognize(path, date(2026,9,20))
    assert result['warnings'] == []
    assert [r['km'] for r in result['data']['daily']] == [73,73,75,77,73,0,73]
    assert result['evidence']['daily_sum'] == result['evidence']['daily_total'] == 444
    assert [r['value'] for r in result['data']['weekly']] == [16.7,17.6,14.2,13.6,13.8,13.7]
    assert result['data']['energy'][0]['totalKwh'] == 68.1
    original = ocr.text
    def disagreement(image, lang='chi_sim+eng', psm=6, whitelist=None):
        if lang == 'eng' and psm in (7,8,13):
            return str(psm)
        return original(image, lang, psm, whitelist)
    monkeypatch.setattr(ocr, 'text', disagreement)
    uncertain = recognize(path, date(2026,9,20))
    assert uncertain['data']['daily'] == []
    assert '2026-09-16' in uncertain['warnings'][0] and '2026-09-17' in uncertain['warnings'][0]
    monkeypatch.setattr(ocr, 'text', lambda image,lang='chi_sim+eng',psm=6,whitelist=None:
                        '999' if lang=='eng' and psm in (7,8,13) else original(image,lang,psm,whitelist))
    mismatch = recognize(path, date(2026,9,20))
    assert mismatch['data']['daily'] == []
    assert '总里程不符' in mismatch['warnings'][0]

def test_new_year_period():
    assert period_for('12/29-1/4',date(2026,1,5))=='2025/12/29 - 2026/01/04'
    assert period_for('9/7-9/13',date(2026,9,19))=='2026/09/07 - 2026/09/13'
    with pytest.raises(ValueError):period_for('9/7-9/17',date(2026,9,19))

@pytest.mark.skipif(not os.getenv('OCR_FIXTURE'),reason='Set OCR_FIXTURE to the supplied screenshot path')
def test_real_screenshot():
    result=recognize(Path(os.environ['OCR_FIXTURE']),date(2026,9,19))
    assert result['warnings']==[]
    assert [r['km'] for r in result['data']['daily']]==[42,73,73,75,77,73,0]
    assert [r['value'] for r in result['data']['weekly']]==[16.7,17.6,14.2,13.6,13.8,13.7]
    assert result['data']['energy'][0]['totalKwh']==68.1
    assert result['data']['energy'][0]['drive']==85.61
