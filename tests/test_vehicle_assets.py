import hashlib
import json
from pathlib import Path

from PIL import Image


def test_vehicle_sprites_keep_original_bytes_and_alpha():
    folder = Path(__file__).resolve().parents[1]/'app/static/vehicle'
    manifest = json.loads((folder/'frames.json').read_text())
    assert len(manifest['frames']) == 36
    assert manifest['plateText'] == '沪B·AY7772'
    for frame in manifest['frames']:
        path = folder/frame['src']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == frame['sha256']
        with Image.open(path) as image:
            assert image.size == (manifest['width'], manifest['height'])
            assert image.mode == 'RGBA'
            assert image.getchannel('A').getextrema() == (0, 255)
        if frame['plate'] is not None:
            assert len(frame['plate']) == 4
            assert all(0 <= x < manifest['width'] and 0 <= y < manifest['height']
                       for x, y in frame['plate'])
