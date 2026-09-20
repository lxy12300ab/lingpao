import os
from datetime import date
from pathlib import Path
import pytest
from app.ocr import period_for, recognize

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
