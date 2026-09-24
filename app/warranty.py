"""Conservative mileage budgeting; not an eligibility determination."""
import calendar
from datetime import date, timedelta


def cycle(delivery, today):
    def anniversary(year):
        return date(year, delivery.month, min(delivery.day, calendar.monthrange(year, delivery.month)[1]))
    start = anniversary(today.year)
    if start > today:
        start = anniversary(today.year - 1)
    return start, anniversary(start.year + 1)


def summarize(settings, rows, today):
    if not settings:
        return {'configured': False}
    delivery = date.fromisoformat(settings['delivery'])
    start, end = cycle(delivery, today)
    result = {'configured': True, 'settings': settings, 'start': str(start),
              'end': str(end - timedelta(days=1)), 'limit': settings['limit'],
              'used': None, 'remaining': None, 'projection': None,
              'daily_budget': None, 'level': 'unknown', 'estimated': True}
    captured = date.fromisoformat(settings['captured_date'])
    if today < delivery or settings['baseline_date'] != str(start) or not start <= captured < end:
        result['message'] = '本年度缺少起点或仪表校准，请更新本周期起点读数；历史记录不会清零。'
        return result
    used = settings['odometer'] - settings['baseline']
    if settings['kind'] == 'intraday':
        result['message'] = '日中读数，尚未结算：仅显示校准时额度，不叠加当天或后续里程。请补充日终仪表读数。'
    else:
        by_date = {r['date']: r['km'] for r in rows}
        cursor = captured + timedelta(days=1)
        missing = 0
        while cursor <= today:
            key = str(cursor)
            used += by_date.get(key, 0)
            if cursor < today and key not in by_date:
                missing += 1
            cursor += timedelta(days=1)
        result['message'] = (f'校准后缺少 {missing} 天记录，已用里程仅为下限、剩余额度仅为上限，请重新校准。'
                             if missing else '按日终仪表及后续已记录里程估算；今天可能尚未完整，请定期校准。')
        if not missing:
            elapsed = (today - start).days + 1
            result['projection'] = round(used / elapsed * (end-start).days)
            result['daily_budget'] = round(max(0, settings['limit']-used) / max(1, (end-today).days), 1)
    result['used'] = round(used, 1)
    result['remaining'] = round(settings['limit']-used, 1)
    ratio = used / settings['limit']
    result['level'] = ('exceeded' if ratio > 1 else 'critical' if ratio >= .95
                       else 'warning' if ratio >= .9 else 'notice' if ratio >= .8 else 'tracking')
    if result['projection'] and result['projection'] > settings['limit']:
        result['message'] += ' 按目前速度，预计年度里程会超过上限。'
        if ratio < .9:
            result['level'] = 'notice'
    return result
