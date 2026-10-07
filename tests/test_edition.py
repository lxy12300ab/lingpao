from html.parser import HTMLParser
from fastapi.testclient import TestClient
from app.main import app


class IDs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        value = dict(attrs).get('id')
        if value:
            self.ids.append(value)


def test_edition_assets_and_unique_controls(storage):
    with TestClient(app) as client:
        for route in ('/', '/upload'):
            response = client.get(route)
            assert response.status_code == 200
            parser = IDs()
            parser.feed(response.text)
            assert len(parser.ids) == len(set(parser.ids))
            for control in ('journeyTrend', 'journeyCalendar', 'recordChoice',
                            'wMileage', 'wTime', 'weeklyTabs', 'noteSearch'):
                assert control in parser.ids
        for asset in ('edition.css', 'c11-banner.jpg', 'leap-mark.svg'):
            response = client.get('/' + asset)
            assert response.status_code == 200
            assert 'no-store' in response.headers['cache-control']
