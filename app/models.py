import re
from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

def normalize_period(value):
    match = re.fullmatch(r'(\d{4})[/-](\d{2})[/-](\d{2})\s*-\s*(\d{4})[/-](\d{2})[/-](\d{2})', value)
    if not match:
        raise ValueError('周期必须为 YYYY/MM/DD - YYYY/MM/DD')
    nums = list(map(int, match.groups()))
    start, end = date(*nums[:3]), date(*nums[3:])
    if (end-start).days != 6:
        raise ValueError('能耗周期必须连续七天')
    return f'{start:%Y/%m/%d} - {end:%Y/%m/%d}'

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Daily(Strict):
    date: date
    km: float = Field(ge=0, le=3000)

class ManualMileage(Strict):
    km: float | None = Field(ge=0, le=3000)
    expected_km: float | None = Field(ge=0, le=3000)
    note: str | None = Field(default=None, max_length=2000)
    expected_note: str | None = Field(default=None, max_length=2000)

class Weekly(Strict):
    period: str
    value: float = Field(gt=0, le=50)
    _period = field_validator('period')(normalize_period)

class Energy(Strict):
    period: str
    totalKwh: float = Field(ge=0, le=10000)
    drive: float = Field(ge=0, le=100)
    ac: float = Field(ge=0, le=100)
    other: float = Field(ge=0, le=100)
    _period = field_validator('period')(normalize_period)

    @model_validator(mode='after')
    def percentages(self):
        if abs(self.drive + self.ac + self.other - 100) > 0.2:
            raise ValueError('能耗占比之和必须接近 100%')
        return self

class Dataset(Strict):
    daily: list[Daily] = Field(default_factory=list, max_length=40000)
    weekly: list[Weekly] = Field(default_factory=list, max_length=6000)
    energy: list[Energy] = Field(default_factory=list, max_length=6000)

    @model_validator(mode='after')
    def unique(self):
        for rows, key in ((self.daily, 'date'), (self.weekly, 'period'), (self.energy, 'period')):
            keys = [getattr(r, key) for r in rows]
            if len(keys) != len(set(keys)):
                raise ValueError('同一批数据不能包含重复日期/周期')
        return self
