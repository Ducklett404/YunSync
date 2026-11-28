import unittest
from email.message import Message
from io import BytesIO
from unittest.mock import patch

from check_config import web_port
from smoke import check_h5


def board_config(proxy="172.30.84.2", pool="172.30.84.128/25", port="18081"):
    return {
        "networks": {"proxy": {"ipam": {"config": [{"subnet": "172.30.84.0/24", "ip_range": pool}]}}},
        "services": {"web": {
            "networks": {"proxy": {"ipv4_address": proxy}},
            "ports": [{"target": 80, "published": port}],
        }},
    }


class BoardConfigTests(unittest.TestCase):
    def test_custom_port(self):
        self.assertEqual(web_port(board_config()), 18081)

    def test_invalid_address_plan_or_port(self):
        for invalid in ({"proxy": "172.30.84.1"}, {"proxy": "172.30.84.128"},
                        {"proxy": "172.30.85.2"}, {"pool": "172.30.85.128/25"},
                        {"port": "0"}, {"port": "70000"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                web_port(board_config(**invalid))


class BoardEntryTests(unittest.TestCase):
    def setUp(self):
        self.site = "http://127.0.0.1:18081"
        self.files = {
            self.site: ("text/html", b'<script type="module" src="/assets/main.js"></script>'
                                     b'<link rel="stylesheet" href="/assets/main.css">'),
            self.site + "/assets/main.js": ("text/javascript", b"export {}"),
            self.site + "/assets/main.css": ("text/css", b"body{}"),
        }

    def open_asset(self, url, timeout):
        mime, body = self.files[url]
        response = BytesIO(body)
        response.headers = Message()
        response.headers["Content-Type"] = mime
        return response

    def test_entry_and_assets(self):
        with patch("smoke.urlopen", self.open_asset):
            check_h5(self.site)

    def test_default_page_html_instead_of_js_or_empty_css_fails(self):
        for path, replacement in (("", ("text/html", b"<h1>Welcome to nginx</h1>")),
                                  ("/assets/main.js", ("text/html", b"<html>")),
                                  ("/assets/main.css", ("text/css", b""))):
            with self.subTest(path=path), patch.dict(self.files, {self.site + path: replacement}):
                with patch("smoke.urlopen", self.open_asset), self.assertRaises(RuntimeError):
                    check_h5(self.site)
