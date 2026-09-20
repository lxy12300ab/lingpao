"""UI v2 regression. Uses real read-only data; upload/confirmation writes are mocked."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

root=Path(__file__).resolve().parents[1]
env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if line and not line.startswith('#'))
out=root/'test-results';out.mkdir(exist_ok=True)
engine=os.getenv('BROWSER','chromium')
checks=[]
with sync_playwright() as p:
    browser=p.webkit.launch(headless=True) if engine=='webkit' else p.chromium.launch(channel='chrome',headless=True)
    context=browser.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1000},color_scheme='light')
    page=context.new_page();errors=[];requests=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:requests.append(request.url))
    page.goto('https://localhost:'+env.get('HTTPS_PORT','8443'))
    page.locator('#tokenInput').fill(env['API_TOKEN'])
    page.locator('#loginForm button').click()
    expect(page.locator('#loginDialog')).not_to_be_visible()
    expect(page.locator('#connection')).to_contain_text('已同步')
    expect(page.locator('html')).to_have_attribute('data-theme','light')
    page.screenshot(path=str(out/(engine+'-desktop-light.png')),full_page=True)
    page.emulate_media(color_scheme='dark')
    expect(page.locator('html')).to_have_attribute('data-theme','dark')
    page.screenshot(path=str(out/(engine+'-desktop-dark.png')),full_page=True)
    page.locator('#settingsButton').click()
    expect(page.locator('#adminDialog')).to_be_visible()
    page.locator('[data-theme-choice=light]').click()
    expect(page.locator('html')).to_have_attribute('data-theme','light')
    page.reload()
    expect(page.locator('html')).to_have_attribute('data-theme','light')
    page.locator('#settingsButton').click()
    page.locator('[data-theme-choice=system]').click()
    expect(page.locator('html')).to_have_attribute('data-theme','dark')
    page.locator('[data-close=adminDialog]').click()
    page.emulate_media(color_scheme='light')
    expect(page.locator('html')).to_have_attribute('data-theme','light')
    checks.append('system theme changes live; manual override survives reload; returns to system')

    page.locator('[data-range=all]').click()
    for mode in ['daily', 'weekly', 'monthly', 'yearly']:
        page.locator('[data-view='+mode+']').click()
        expected=page.evaluate('chartData(selectedRows()).find(r => r.value !== null).key')
        assert page.evaluate('selectedMileage')==expected
        page.locator('#mileageChart .chart-hit').first.hover()
        assert page.evaluate('selectedMileage')==expected
        page.locator('#mileageChart .chart-hit').first.click()
        assert page.evaluate('selectedMileage')==page.evaluate('chartData(selectedRows())[0].key')
    page.locator('[data-view=daily]').click()
    checks.append('day/week/month default to latest record; hover does not change selection; click still works')

    # Synthetic ten-year history stays in browser memory, never touches storage.
    page.evaluate("""() => {
      window.originalDaily = structuredClone(data.daily);
      data.daily = Array.from({length:3653}, (_,i) => ({date:add('2016-09-20',i),km:i % 5}));
      setRange('all');
    }""")
    for mode, limit in [('daily',31),('weekly',26),('monthly',24),('yearly',10)]:
        page.locator('[data-view='+mode+']').click()
        keys=page.evaluate('chartData(selectedRows()).map(r=>r.key)')
        assert keys==sorted(keys,reverse=True)
        assert page.locator('#mileageChart .chart-hit').count()<=limit
        assert page.evaluate('selectedMileage')==keys[0]
        if len(keys)>limit:
            page.locator('#mileageOlder').click()
            assert page.evaluate('selectedMileage')==keys[limit]
            page.evaluate('turnMileagePage(10000)')
            assert page.locator('#mileageChart .chart-hit').last.get_attribute('aria-label').startswith(keys[-1])
            expect(page.locator('#mileageOlder')).to_be_disabled()
            page.locator('#mileageLatest').click()
            assert page.evaluate('selectedMileage')==keys[0]
        assert page.evaluate('chartData(selectedRows()).reduce((s,r)=>s+(r.value||0),0)')==page.evaluate('data.daily.reduce((s,r)=>s+r.km,0)')
    page.evaluate('data.daily=window.originalDaily; delete window.originalDaily; setRange("all")')
    page.locator('[data-view=daily]').click()
    checks.append('ten-year history: descending day/week/month/year, bounded pages, earliest data reachable, totals preserved')

    page.locator('[data-range=custom]').click()
    page.locator('#startDate').fill('2026-09-13');page.locator('#endDate').fill('2026-09-19')
    page.locator('#applyDates').click()
    expect(page.locator('#total')).to_have_text('413')
    page.locator('#mileageChart .chart-hit').last.click()
    expect(page.locator('#mileageReadout')).to_contain_text('42')
    page.locator('#mileageChart .chart-hit').first.focus()
    page.keyboard.press('Enter')
    expect(page.locator('#mileageReadout')).to_contain_text('0')
    page.locator('[data-view=weekly]').click()
    expect(page.locator('#averageLegend')).to_have_text('已记录周均')
    page.locator('[data-view=monthly]').click()
    expect(page.locator('#mileageReadout')).to_contain_text('413')
    page.locator('[data-range=custom]').click()
    page.locator('#startDate').fill('2026-10-01')
    page.locator('#applyDates').click()
    expect(page.locator('#dateError')).to_contain_text('有效')
    page.locator('[data-close=dateDialog]').click()
    expect(page.locator('#total')).to_have_text('413')
    page.locator('[data-range=month]').click();page.locator('[data-view=daily]').click()
    page.locator('#calendarGrid [data-date="2026-09-19"]').click()
    expect(page.locator('#dayDetail')).to_contain_text('0')
    page.locator('[data-close=dayDialog]').click()
    page.locator('#calendarGrid [data-date="2026-09-20"]').click()
    day_value=page.evaluate('data.daily.find(r => r.date === "2026-09-20")?.km ?? null')
    expect(page.locator('#dayDetail')).to_contain_text('未记录' if day_value is None else str(day_value)+' km')
    page.locator('[data-close=dayDialog]').click()
    checks.append('custom dates, invalid date guard, day/week/month charts, keyboard, missing versus zero')

    page.locator('[data-page=energy]').click()
    expect(page.locator('#latestEnergy')).to_have_text('13.7')
    page.locator('#weeklyChart .chart-hit').first.click()
    expect(page.locator('#weeklyReadout')).to_contain_text('13.8')
    page.locator('.breakdown-row').first.click()
    expect(page.locator('.donut-center')).to_contain_text('85.61%')
    page.locator('#energyPeriod').select_option('2026/08/31 - 2026/09/06')
    expect(page.locator('.donut-center')).to_contain_text('76.3')
    page.screenshot(path=str(out/(engine+'-energy-light.png')),full_page=True)
    checks.append('weekly point selection and independent breakdown period selection')

    for size in [390,320,768]:
        page.set_viewport_size({'width':size,'height':844})
        for name in ['overview','energy','records']:
            page.locator('[data-page='+name+']').click()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(size,name)
        if size==390:
            page.locator('[data-page=overview]').click()
            page.screenshot(path=str(out/(engine+'-mobile-light.png')),full_page=True)
            page.emulate_media(color_scheme='dark')
            expect(page.locator('html')).to_have_attribute('data-theme','dark')
            page.screenshot(path=str(out/(engine+'-mobile-dark.png')),full_page=True)
            page.locator('[data-page=energy]').click()
            page.screenshot(path=str(out/(engine+'-mobile-energy-dark.png')),full_page=True)
            page.emulate_media(color_scheme='light')
    checks.append('320/390/768px pages without document overflow')

    page.set_viewport_size({'width':390,'height':844})
    page.locator('[data-page=records]').click()
    page.locator('.record-row').first.click()
    expect(page.locator('#dayDialog')).to_be_visible()
    page.locator('[data-close=dayDialog]').click()
    page.locator('#mobileUpload').click()
    expect(page.locator('#uploadDialog')).to_be_visible()
    page.screenshot(path=str(out/(engine+'-upload-mobile.png')))
    # All network mutations below are mocked; no test values are written to the user's database.
    sample=root/'app/static/c11_hero.jpg'
    proposal={'id':99999,'status':'review','data':{'daily':[{'date':'2026-09-19','km':0}],'weekly':[],'energy':[]},'warnings':['请核对测试记录']}
    page.route('**/api/upload',lambda route:route.fulfill(json=proposal))
    page.route('**/api/screenshots/99999/image',lambda route:route.fulfill(path=str(sample),content_type='image/jpeg'))
    confirmed=[]
    def confirm(route):
        confirmed.append(route.request.post_data_json)
        route.fulfill(json={'inserted':0,'updated':0,'unchanged':1,'rejected':[]})
    page.route('**/api/screenshots/99999/confirm',confirm)
    page.locator('#screenshotFile').set_input_files(str(sample))
    expect(page.locator('#uploadPreview')).to_be_visible()
    page.locator('#captureDate').fill('2026-09-19')
    page.locator('#submitUpload').click()
    expect(page.locator('#reviewDialog')).to_be_visible()
    page.locator('#reviewFields [data-field=km]').fill('1')
    page.locator('#confirmButton').click()
    expect(page.locator('#reviewResult')).to_contain_text('已计入手记')
    assert confirmed[0]['daily'][0]['km']==1
    page.locator('[data-close=reviewDialog]').click()
    page.locator('[data-close=uploadDialog]').click()
    checks.append('mobile upload preview, review form edit and confirmation feedback (mocked writes)')

    page.locator('[data-page=overview]').click()
    page.locator('#calendarGrid [data-date="2026-09-19"]').click()
    edits=[]
    def edit(route):
        edits.append(route.request.post_data_json)
        route.fulfill(json={'date':'2026-09-19', 'km':12.5})
    page.route('**/api/daily/2026-09-19', edit)
    page.locator('#dayKm').fill('12.5')
    page.locator('#daySave').click()
    expect(page.locator('#dayDialog')).not_to_be_visible()
    expect(page.locator('#calendarGrid [data-date="2026-09-19"] .calendar-km')).to_have_text('12.5')
    assert edits==[{'km':12.5,'expected_km':0}]
    page.locator('#calendarGrid [data-date="2026-09-19"]').click()
    page.route('**/api/daily/2026-09-19', lambda route:route.fulfill(status=409,json={'detail':'数据已变化'}))
    page.locator('#dayKm').fill('10')
    page.locator('#daySave').click()
    expect(page.locator('#dayEditError')).to_contain_text('数据已变化')
    expect(page.locator('#dayKm')).to_have_value('10')
    page.locator('[data-close=dayDialog]').click()
    checks.append('calendar mileage, manual editing and conflict feedback (mocked writes)')

    page.locator('[data-page=overview]').click()
    page.route('**/api/data',lambda route:route.abort())
    page.locator('#refreshButton').click()
    expect(page.locator('#offlineBanner')).to_be_visible()
    page.unroute('**/api/data')
    page.locator('#retryButton').click()
    expect(page.locator('#offlineBanner')).not_to_be_visible()
    checks.append('failed sync preserves data and retry recovers')
    page.route('**/api/version*',lambda route:route.fulfill(json={'build':'qa-new-version'}))
    with page.expect_navigation():
        page.evaluate('checkVersion()')
    assert 'v=qa-new-version' in page.url
    checks.append('version navigation')
    assert not errors,errors
    assert all(url.startswith(('https://localhost:','blob:')) for url in requests),requests
    print(json.dumps({'engine':engine,'checks':checks,'js_errors':errors,'external_requests':False},ensure_ascii=False,indent=2))
    browser.close()
