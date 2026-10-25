"""Isolated-browser regression for the interactive vehicle. No business writes.

Start a disposable preview server with API_TOKEN=banner-preview-token-local-only-2026,
DATA_DIR pointing at a disposable directory and ENABLE_SCHEDULER=0, then run this.
"""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'test-results/vehicle'
OUT.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get('VEHICLE_TEST_URL', 'http://127.0.0.1:8790')


def ready(page):
    page.goto(BASE)
    page.locator('#tokenInput').fill('banner-preview-token-local-only-2026')
    page.locator('#loginForm button').click()
    expect(page.locator('#loginDialog')).not_to_be_visible()
    expect(page.locator('#vehicleViewer')).to_have_attribute('data-loaded','36',timeout=30000)


with sync_playwright() as p:
    for engine in os.environ.get('VEHICLE_TEST_ENGINES','chromium,webkit').split(','):
        browser = getattr(p, engine).launch(**({'channel': 'chrome'} if engine == 'chromium' else {}))
        context = browser.new_context(viewport={'width':1440,'height':1000},color_scheme='light')
        page = context.new_page()
        errors, requests = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append(request.url))
        ready(page)
        viewer = page.locator('#vehicleViewer')
        viewer.focus()
        # Inspect each rendered frame against a fresh decode of the original sprite.
        report=[]
        for i in range(36):
            expect(viewer).to_have_attribute('data-frame', str(i))
            result=page.evaluate('''async index => {
              const viewer=document.querySelector('#vehicleViewer');
              const m=await (await fetch('/vehicle/frames.json')).json();
              const canvas=viewer.querySelector('canvas');
              const original=new Image();original.src='/vehicle/'+m.frames[index].src;
              await original.decode();
              const reference=document.createElement('canvas');reference.width=canvas.width;reference.height=canvas.height;
              const c=reference.getContext('2d');c.drawImage(original,0,0);
              const a=c.getImageData(0,0,canvas.width,canvas.height).data;
              const b=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
              const q=m.frames[index].plate;
              const xs=q?q.map(p=>p[0]):[-10],ys=q?q.map(p=>p[1]):[-10];
              const bounds=[Math.floor(Math.min(...xs))-2,Math.floor(Math.min(...ys))-2,Math.ceil(Math.max(...xs))+2,Math.ceil(Math.max(...ys))+2];
              let alphaChanges=0,outsideChanges=0,yellowRemaining=0;
              for(let k=0;k<a.length;k+=4){
                if(a[k+3]!==b[k+3]) alphaChanges++;
                const x=(k/4)%canvas.width,y=Math.floor(k/4/canvas.width);
                if((x<bounds[0]||x>bounds[2]||y<bounds[1]||y>bounds[3]) && (a[k]!==b[k]||a[k+1]!==b[k+1]||a[k+2]!==b[k+2])) outsideChanges++;
                if(b[k]>140&&b[k+1]>100&&b[k+2]<140&&b[k]-b[k+2]>65&&b[k+1]-b[k+2]>30&&b[k+3]>240)yellowRemaining++;
              }
              window.vehicleReview=window.vehicleReview||[];
              const copy=document.createElement('canvas');copy.width=canvas.width;copy.height=canvas.height;
              copy.getContext('2d').drawImage(canvas,0,0);
              window.vehicleReview.push({index,canvas:copy});
              return {index,alphaChanges,outsideChanges,yellowRemaining};
            }''',i)
            report.append(result)
            assert result['alphaChanges']==0, result
            assert result['outsideChanges']==0, result
            page.keyboard.press('ArrowRight')
        expect(viewer).to_have_attribute('data-frame','0')
        page.keyboard.press('ArrowLeft')
        expect(viewer).to_have_attribute('data-frame','35')
        page.keyboard.press('Home')
        expect(viewer).to_have_attribute('data-frame','0')
        page.keyboard.press('End')
        expect(viewer).to_have_attribute('data-frame','35')
        page.keyboard.press('Home')
        # Real mouse drag beyond a complete revolution must still wrap correctly.
        box=viewer.bounding_box()
        page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
        page.mouse.down()
        page.mouse.move(box['x']+box['width']/2+box['width']*2.2,box['y']+box['height']/2,steps=12)
        page.mouse.up()
        page.wait_for_timeout(100)
        assert 0<=int(viewer.get_attribute('data-frame'))<36
        assert viewer.get_attribute('data-frame')!='0'
        viewer.focus();page.keyboard.press('Home')
        # Responsive screenshots and overflow checks, both themes.
        for width in (320,390,768,1440):
            page.set_viewport_size({'width':width,'height':1000 if width>700 else 844})
            viewer.scroll_into_view_if_needed()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(engine,width)
            for scheme in ('light','dark'):
                page.emulate_media(color_scheme=scheme)
                viewer.screenshot(path=str(OUT/f'{engine}-{width}-{scheme}.png'))
        # Rear, head-on front and near-edge plates, captured at readable size.
        page.set_viewport_size({'width':1440,'height':1000})
        for index in (4,14,22,30,32):
            viewer.focus();page.keyboard.press('Home')
            for _ in range(index):page.keyboard.press('ArrowRight')
            expect(viewer).to_have_attribute('data-frame',str(index))
            viewer.screenshot(path=str(OUT/f'{engine}-angle-{index}.png'))
        assert not errors,errors
        assert all(url.startswith(BASE) for url in requests),set(requests)
        # A contact sheet made from the actual renderer (not edited asset files).
        page.evaluate('''() => {
          const grid=document.createElement('main');grid.id='vehicle-review';
          Object.assign(grid.style,{position:'absolute',inset:'0 auto auto 0',width:'1440px',display:'grid',gridTemplateColumns:'repeat(6,1fr)',background:'#ebe7df',zIndex:'10000'});
          for(const entry of window.vehicleReview){
            const item=document.createElement('div'),label=document.createElement('p');
            entry.canvas.style.width='100%';label.textContent=String(entry.index);label.style.color='#111';
            item.append(entry.canvas,label);grid.append(item);
          }
          document.body.append(grid);
        }''')
        page.locator('#vehicle-review').screenshot(path=str(OUT/f'{engine}-all-angles.png'))
        # Upload route should never fetch vehicle sprites.
        other=context.new_page();upload_requests=[]
        other.on('request',lambda request: upload_requests.append(request.url))
        other.goto(BASE+'/upload');other.wait_for_timeout(200)
        assert not any('/vehicle/' in url and 'showroom' not in url for url in upload_requests),upload_requests
        other.close()
        # Missing frames keep the last successful view and allow other angles.
        partial=context.new_page()
        partial.route('**/vehicle/black-05.webp*',lambda route:route.abort())
        partial.goto(BASE)
        partial.locator('#tokenInput').fill('banner-preview-token-local-only-2026')
        partial.locator('#loginForm button').click()
        expect(partial.locator('#vehicleViewer')).to_have_attribute('data-loaded','35',timeout=30000)
        partial_viewer=partial.locator('#vehicleViewer');partial_viewer.focus()
        for index in range(1,5):
            partial.keyboard.press('ArrowRight')
            expect(partial_viewer).to_have_attribute('data-frame',str(index))
        partial.keyboard.press('ArrowRight')
        expect(partial.locator('#vehicleHint')).to_contain_text('此角度暂未加载')
        expect(partial_viewer).to_have_attribute('data-frame','4')
        partial.keyboard.press('ArrowRight')
        expect(partial_viewer).to_have_attribute('data-frame','6')
        partial.close()
        # Startup failures preserve the static banner.
        failed=context.new_page()
        failed.route('**/vehicle/frames.json*',lambda route:route.abort())
        failed.goto(BASE)
        expect(failed.locator('#vehicleViewer')).to_have_attribute('data-ready','false',timeout=30000)
        expect(failed.locator('.vehicle-poster')).to_be_visible()
        expect(failed.locator('#vehicleViewer canvas')).not_to_be_visible()
        failed.close()
        (OUT/f'{engine}-pixels.json').write_text(json.dumps(report,indent=2))
        print(engine, 'PASS: 36 frames, exact alpha and unchanged pixels outside plates; mouse/keyboard/wrap; 4 widths; 2 themes; startup/partial failure; local-only; upload isolation')
        context.close()
        if engine=='chromium':
            # Native touch event sequence: horizontal rotates, vertical scrolls.
            touch=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=3,is_mobile=True,has_touch=True)
            page=touch.new_page();ready(page)
            viewer=page.locator('#vehicleViewer');viewer.scroll_into_view_if_needed()
            client=touch.new_cdp_session(page)
            def swipe(dx,dy):
                box=viewer.bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
                client.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
                for step in range(1,9):
                    client.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+dx*step/8,'y':y+dy*step/8}]})
                    page.wait_for_timeout(20)
                client.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
                page.wait_for_timeout(150)
            swipe(-110,0)
            assert viewer.get_attribute('data-frame')!='0'
            frame=viewer.get_attribute('data-frame');before=page.evaluate('scrollY')
            swipe(0,-130)
            assert page.evaluate('scrollY')>before+20
            assert viewer.get_attribute('data-frame')==frame
            print('chromium PASS: native horizontal touch rotates; vertical touch scrolls without rotation')
            touch.close()
        browser.close()
