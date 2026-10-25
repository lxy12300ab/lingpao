"""Copy the restored black C11 sprites byte-for-byte and locate plate planes.

One-time asset preparation; Pillow/numpy are only used to READ pixels. No sprite
is re-encoded. The viewer renders its own SVG plate on a separate canvas layer.
Run: python3 scripts/import_vehicle_frames.py /path/to/dcd3d-mirror/mirror
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import numpy as np
from PIL import Image


def hull(points):
    points = sorted(set(points))
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for chain, values in ((lower, points), (upper, reversed(points))):
        for p in values:
            while len(chain) >= 2 and cross(chain[-2], chain[-1], p) <= 0:
                chain.pop()
            chain.append(p)
    return lower[:-1] + upper[:-1]


def plate_quad(image):
    a = np.asarray(image).astype(np.int16)
    r, g, b, alpha = [a[:, :, n] for n in range(4)]
    mask = (r > 140) & (g > 100) & (b < 140) & (r-b > 65) & (g-b > 30) & (alpha > 240)
    ys, xs = np.nonzero(mask)
    remaining = set(zip(xs.tolist(), ys.tolist()))
    components = []
    while remaining:
        p = remaining.pop()
        stack, component = [p], [p]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
                q = x+dx, y+dy
                if q in remaining:
                    remaining.remove(q)
                    stack.append(q)
                    component.append(q)
        if len(component) >= 6:
            components.append(component)
    if not components:
        return None
    points = max(components, key=len)
    poly = hull(points)
    while len(poly) > 4:
        costs = []
        for i, p in enumerate(poly):
            prev, nex = poly[i-1], poly[(i+1) % len(poly)]
            costs.append(abs((prev[0]-p[0])*(nex[1]-p[1])-(prev[1]-p[1])*(nex[0]-p[0])))
        poly.pop(int(np.argmin(costs)))
    if len(poly) != 4:
        return None
    # The top edge, then clockwise: TL, TR, BR, BL.
    start = min(range(4), key=lambda i: poly[i][1]+poly[(i+1) % 4][1])
    poly = poly[start:]+poly[:start]
    # Move each edge out to contain the measured yellow contour, including its
    # antialiased border. Radial expansion under-covers a thin plate's long edges.
    lines=[]
    for i, p in enumerate(poly):
        edge=np.array(poly[(i+1)%4],dtype=float)-p
        normal=np.array([edge[1],-edge[0]])/np.linalg.norm(edge)
        lines.append((normal,float(np.max(np.array(points)@normal))+0.8))
    poly=[np.linalg.solve(np.array([lines[i-1][0],lines[i][0]]),
                          np.array([lines[i-1][1],lines[i][1]])) for i in range(4)]
    return [[round(float(x), 2), round(float(y), 2)] for x, y in poly]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mirror', type=Path)
    args = parser.parse_args()
    colors = None
    for meta in sorted((args.mirror/'api.dcarapi.com').glob('*.meta.json')):
        if 'full_exterior' in json.loads(meta.read_text()).get('url', ''):
            data = json.loads(meta.with_name(meta.name.replace('.meta.json', '.body')).read_text())
            colors = data['data']['simple_3d']['car_data']['colors']
            break
    if not colors:
        raise SystemExit('Missing cached exterior metadata')
    color = next(c for c in colors if c['ColorName'] == '金属黑')
    hashes = [re.search(r'DCP_([0-9a-f]{32})', p)[1] for p in color['exterior_360']['pics']]
    candidates = {}
    for meta in (args.mirror/'p5-auto.dcarimg.com').glob('*.meta.json'):
        match = re.search(r'DCP_([0-9a-f]{32})', json.loads(meta.read_text()).get('url', ''))
        if match and match[1] in hashes:
            body = meta.with_name(meta.name.replace('.meta.json', '.body'))
            with Image.open(body) as image:
                if image.size == (843, 562) and image.mode == 'RGBA':
                    candidates[match[1]] = body
    missing = set(hashes)-set(candidates)
    if missing:
        raise SystemExit(f'Missing transparent 843x562 frames: {missing}')
    dest = Path(__file__).resolve().parents[1]/'app/static/vehicle'
    dest.mkdir(exist_ok=True)
    frames = []
    for i, key in enumerate(hashes):
        source = candidates[key]
        filename = f'black-{i:02}.webp'
        shutil.copyfile(source, dest/filename)
        with Image.open(source) as image:
            quad = plate_quad(image)
        frames.append({'src': filename, 'plate': quad,
                       'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    manifest = {'width': 843, 'height': 562, 'initialFrame': 0,
                'plateText': '沪B·AY7772', 'frames': frames}
    (dest/'frames.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(f'Copied {len(frames)} unchanged RGBA frames; {sum(f["plate"] is not None for f in frames)} visible plate planes')


if __name__ == '__main__':
    main()
