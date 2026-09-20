"""Local OCR for the supplied Leap App layout. Ambiguous sections never auto-merge."""
import re
from datetime import date, timedelta
from itertools import product
from collections import Counter
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract
from .models import Dataset

Image.MAX_IMAGE_PIXELS = 16_000_000
NUMBER = re.compile(r'^\d{1,4}(?:\.\d{1,2})?$')
PERIOD = re.compile(r'(\d{1,2})/(\d{1,2})\s*[-–—~至]\s*(\d{1,2})/(\d{1,2})')

def prep(image):
    image = ImageOps.grayscale(image)
    image = image.resize((image.width * 2, image.height * 2))
    return ImageEnhance.Contrast(image).enhance(1.6).filter(ImageFilter.SHARPEN)

def text(image, lang='chi_sim+eng', psm=6, whitelist=None):
    flags = f'--psm {psm}'
    if whitelist:
        flags += f' -c tessedit_char_whitelist={whitelist}'
    return pytesseract.image_to_string(prep(image), lang=lang, config=flags, timeout=20).strip()

def tokens(image, lang='chi_sim+eng', psm=11, enhance=True):
    scale=2 if enhance else 1
    data = pytesseract.image_to_data(prep(image) if enhance else image, lang=lang, config=f'--psm {psm}',
                                    output_type=pytesseract.Output.DICT, timeout=40)
    return [{'text': data['text'][i].strip(), 'x': data['left'][i]/scale, 'y': data['top'][i]/scale,
             'w': data['width'][i]/scale, 'h': data['height'][i]/scale, 'conf': float(data['conf'][i])}
            for i in range(len(data['text'])) if data['text'][i].strip()]

def period_for(raw, captured):
    match = PERIOD.search(raw.replace(' ', ''))
    if not match:
        raise ValueError('无法识别完整周期日期')
    sm, sd, em, ed = map(int, match.groups())
    # Choose the latest period that has started by the screenshot date (handles New Year).
    candidates = []
    for year in (captured.year-1, captured.year):
        try:
            start = date(year, sm, sd)
            end = date(year + ((em, ed) < (sm, sd)), em, ed)
        except ValueError:
            continue
        if start <= captured and (end-start).days == 6 and (captured-start).days < 370:
            candidates.append((start, end))
    if not candidates:
        raise ValueError('周期日期或年份与截图日期不符')
    start, end = max(candidates)
    return f'{start:%Y/%m/%d} - {end:%Y/%m/%d}'

def crop(image, box):
    x1, y1, x2, y2 = box
    return image.crop((max(0, int(x1)), max(0, int(y1)), min(image.width, int(x2)), min(image.height, int(y2))))

def retry_daily_label(image, labels, center, step):
    """Retry one localized numeric label; never reconstruct it from the total."""
    nearby = [t for t in labels
              if re.fullmatch(r'[0-9][0-9./]*', t['text'])
              and abs(t['x'] + t['w']/2 - center) < step*.3
              and 0 < t['w'] < step*.8 and 0 < t['h'] < image.width*.08]
    if len(nearby) != 1:
        return None, []
    t = nearby[0]
    pad = max(4, image.width*.006)
    region = crop(image, (t['x']-pad, t['y']-pad,
                          t['x']+t['w']+pad, t['y']+t['h']+pad))
    readings = [text(region, 'eng', psm, '0123456789.') for psm in (7, 8, 13)]
    votes = Counter(float(s) for s in readings if NUMBER.fullmatch(s) and 0 <= float(s) <= 3000)
    agreed = [value for value, count in votes.items() if count >= 2]
    return (agreed[0] if len(agreed) == 1 else None), readings

def recognize(path, captured: date):
    with Image.open(path) as src:
        if src.format not in ('PNG', 'JPEG', 'WEBP'):
            raise ValueError('仅支持 PNG、JPEG、WebP 截图')
        image = ImageOps.exif_transpose(src).convert('RGB')
    if image.width < 300 or image.height < 600:
        raise ValueError('截图分辨率过低')
    image.thumbnail((1320, 5000))
    w, h = image.size
    ts = tokens(image)
    output = {'daily': [], 'weekly': [], 'energy': []}
    warnings, evidence = [], {}
    # Independent sections: a failed daily chart must not invalidate verified weekly data.
    try:
        today = [t for t in ts if '今天' in t['text']]
        if not today:
            # English mixed OCR can misread green Chinese labels as Latin letters.
            numeric_dates = [t for t in ts if re.fullmatch(r'\d{1,2}',t['text']) and t['y']>h*.6]
            for candidate in sorted(numeric_dates, key=lambda t:t['y'], reverse=True):
                peers = [t for t in numeric_dates if abs(t['y']-candidate['y'])<w*.025]
                if len(peers)<3:
                    continue
                y0=max(0,int(candidate['y']-w*.025))
                band=crop(image,(0,y0,w,candidate['y']+w*.06))
                localized=tokens(band,'chi_sim',6)
                for t in localized:
                    t['y']+=y0
                if any('今天' in t['text'] for t in localized) and '前天' in ''.join(t['text'] for t in localized):
                    ts=[t for t in ts if abs(t['y']-candidate['y'])>=w*.025]+localized
                    today=[t for t in localized if '今天' in t['text']]
                    break
        if len(today) != 1:
            raise ValueError('找不到唯一“今天”日期锚点，请上传完整近7天里程区域')
        anchor = today[0]
        axis_y = anchor['y']
        axis = sorted([t for t in ts if abs(t['y']-axis_y) < w*.025], key=lambda t: t['x'])
        day_tokens = [t for t in axis if re.fullmatch(r'\d{1,2}', t['text'])]
        if len(day_tokens) < 3:
            raise ValueError('日期刻度不完整')
        x0 = day_tokens[0]['x'] + day_tokens[0]['w']/2
        x6 = anchor['x'] + anchor['w']/2
        step = (x6-x0)/6
        if step < w*.08:
            raise ValueError('七日日期间距异常')
        for t in day_tokens:
            i = round((t['x']+t['w']/2-x0)/step)
            if not 0 <= i <= 6 or int(t['text']) != (captured-timedelta(days=6-i)).day:
                raise ValueError('截图日期与图中日期不匹配，请更正拍摄日期')
        km_labels = [t for t in ts if t['text'].lower() == 'km' and t['y'] < axis_y]
        if not km_labels:
            raise ValueError('找不到近7天里程总数单位')
        km = max(km_labels, key=lambda t: t['y'])
        totals = [t for t in ts if NUMBER.fullmatch(t['text']) and t['x'] < km['x']
                  and abs(t['y']+t['h']/2 - km['y']-km['h']/2) < w*.04]
        if len(totals) != 1:
            raise ValueError('近7天总里程无法唯一识别')
        total = float(totals[0]['text'])
        candidates = [t for t in ts+tokens(image,enhance=False) if NUMBER.fullmatch(t['text']) and t['conf'] >= 85
                      and km['y']+km['h']+w*.04 < t['y'] < axis_y-w*.03]
        groups = [[] for _ in range(7)]
        for t in candidates:
            i = round((t['x']+t['w']/2-x0)/step)
            if 0 <= i <= 6 and abs(t['x']+t['w']/2-(x0+i*step)) < step*.3:
                if float(t['text']) not in groups[i]:
                    groups[i].append(float(t['text']))
        # A missing label is zero only with a visible green point on the chart baseline.
        for i, group in enumerate(groups):
            if not group:
                box = crop(image, (x0+i*step-w*.016, axis_y-w*.05, x0+i*step+w*.016, axis_y-w*.008))
                green = sum(1 for r,g,b in box.get_flattened_data() if g > 100 and g > r*1.35 and g > b*1.15)
                if green > box.width*box.height*.025:
                    group.append(0.)
        labels = [t for t in ts if km['y']+km['h']+w*.04 < t['y'] < axis_y-w*.03]
        retries = []
        for i, group in enumerate(groups):
            if len(group) != 1:
                value, readings = retry_daily_label(image, labels, x0+i*step, step)
                retries.append({'date': (captured-timedelta(days=6-i)).isoformat(),
                                'readings': readings, 'accepted': value})
                if value is not None:
                    groups[i] = [value]
        evidence['daily_total'] = total
        evidence['daily_columns'] = [
            {'date': (captured-timedelta(days=6-i)).isoformat(), 'candidates': group}
            for i, group in enumerate(groups)]
        if retries:
            evidence['daily_retries'] = retries
        unresolved = [r['date'] for r in evidence['daily_columns'] if len(r['candidates']) != 1]
        if unresolved:
            raise ValueError('每日里程需核对：' + '、'.join(unresolved) + ' 数字缺失或存在歧义，未写入每日数据')
        valid = {tuple(v) for v in product(*groups) if abs(sum(v)-total) <= max(5, total*.05)}
        if len(valid) != 1:
            raise ValueError('七日数字之和与总里程不符或存在歧义，请核对 ' +
                             (captured-timedelta(days=6)).isoformat() + ' 至 ' + captured.isoformat())
        values = valid.pop()
        output['daily'] = [{'date': (captured-timedelta(days=6-i)).isoformat(), 'km': v} for i,v in enumerate(values)]
        evidence['daily_total'] = total
        evidence['daily_sum'] = sum(values)
    except ValueError as exc:
        warnings.append(str(exc))

    # Read a horizontal period above the donut; never assume the selected week is the latest bar.
    period_tokens = [t for t in ts if PERIOD.search(t['text'])]
    try:
        if len(period_tokens) != 1:
            raise ValueError('找不到唯一周能耗分布周期')
        label = period_tokens[0]
        selected_period = period_for(label['text'], captured)
        percentages = sorted([t for t in ts if re.fullmatch(r'\d+(?:\.\d+)?%', t['text'])
                              and label['y'] < t['y'] < label['y']+w*.4], key=lambda t: t['y'])
        totals = [t for t in ts if NUMBER.fullmatch(t['text']) and t['x'] < w*.5
                  and label['y']+w*.05 < t['y'] < label['y']+w*.3 and t['h'] > w*.035]
        if len(percentages) != 3 or len(totals) != 1:
            raise ValueError('能耗总数或三个占比识别不完整')
        pcts = [float(t['text'][:-1]) for t in percentages]
        entry = {'period': selected_period, 'totalKwh': float(totals[0]['text']),
                 'drive': pcts[0], 'ac': pcts[1], 'other': pcts[2]}
        Dataset(energy=[entry])
        output['energy'] = [entry]
    except ValueError as exc:
        warnings.append(f'能耗构成：{exc}')

    try:
        if len(period_tokens) != 1:
            raise ValueError('缺少周能耗区域锚点')
        label_y = period_tokens[0]['y']
        bars = sorted([t for t in ts if re.fullmatch(r'\d{1,2}\.\d{1,2}', t['text'])
                       and 1 <= float(t['text']) <= 50 and w*.2 < t['y'] < label_y-w*.12
                       and t['conf'] >= 65], key=lambda t: t['x'])
        if len(bars) != 6:
            raise ValueError('周柱状图没有识别出唯一六个数字')
        centers = [t['x']+t['w']/2 for t in bars]
        gap = (centers[-1]-centers[0])/5
        if any(abs((centers[i+1]-centers[i])-gap) > gap*.15 for i in range(5)):
            raise ValueError('周能耗列间距异常')
        periods = []
        for x in centers:
            # Date captions are rotated ~30 degrees in the Leap App screenshot.
            region = crop(image, (x-gap*.51, label_y-w*.185, x+gap*.51, label_y-w*.035))
            found = set()
            for angle in (-30, -25):
                raw = text(region.rotate(angle, expand=True, fillcolor='white'), 'eng', 6, '0123456789/-')
                try:
                    found.add(period_for(raw, captured))
                except ValueError:
                    pass
            if len(found) != 1:
                raise ValueError('倾斜周期标签不清晰，请在待确认数据中补全；未推测周期')
            periods.append(found.pop())
        starts = [date.fromisoformat(p.split(' - ')[0].replace('/', '-')) for p in periods]
        if any((starts[i+1]-starts[i]).days != 7 for i in range(5)):
            raise ValueError('六个周周期不连续')
        output['weekly'] = [{'period': p, 'value': float(t['text'])} for p,t in zip(periods,bars)]
    except ValueError as exc:
        warnings.append(f'周能耗：{exc}')
    return {'data': Dataset(**output).model_dump(mode='json'), 'warnings': warnings, 'evidence': evidence,
            'captured_date': captured.isoformat(), 'engine': 'tesseract-chi_sim+eng-v2'}
