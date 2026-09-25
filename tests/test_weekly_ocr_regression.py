import os
from datetime import date
import pytest
from app.ocr import recognize

@pytest.mark.skipif(not os.getenv('OCR_FIXTURE_SEP25'), reason='Private screenshot supplied externally')
def test_date_digit_not_counted_as_seventh_energy_bar():
    result = recognize(os.environ['OCR_FIXTURE_SEP25'], date(2026,9,25))
    assert result['warnings'] == []
    assert [r['value'] for r in result['data']['weekly']] == [17.6,14.2,13.6,13.8,13.7,12]
    assert sum(r['km'] for r in result['data']['daily']) == 466
    assert result['data']['energy'][0]['totalKwh'] == 51.9
    assert len(result['evidence']['weekly_readings']) == 6
