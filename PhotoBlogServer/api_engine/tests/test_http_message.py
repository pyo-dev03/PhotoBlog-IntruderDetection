"""HTTP 메시지 생성/파싱 단위 테스트 (TDD : 테스트 먼저 작성 → 구현)"""
import unittest

from api_engine.http_message import (HttpParseError, build_get_posts_request, build_multipart,
                                     build_request, parse_response)


class BuildRequestTest(unittest.TestCase):
    def test_request_line_header_empty_line(self):
        raw = build_request('get', '/api_root/Post/', '127.0.0.1:8000', {'Accept': 'application/json'})
        self.assertEqual(raw, b'GET /api_root/Post/ HTTP/1.1\r\nHost: 127.0.0.1:8000\r\n'
                              b'Accept: application/json\r\n\r\n')

    def test_body_adds_content_length(self):
        raw = build_request('POST', '/x/', 'h', body=b'abc')
        self.assertIn(b'Content-Length: 3\r\n\r\nabc', raw)

    def test_path_must_start_with_slash(self):
        with self.assertRaises(ValueError):
            build_request('GET', 'api_root/Post/', 'h')

    def test_lecture_get_request_has_token_and_dalvik_agent(self):
        raw = build_get_posts_request('10.0.2.2:8000', token='abc123').decode()
        self.assertTrue(raw.startswith('GET /api_root/Post/ HTTP/1.1\r\n'))
        self.assertIn('Authorization: Token abc123\r\n', raw)
        self.assertIn('User-Agent: Dalvik/2.1.0', raw)
        self.assertIn('Host: 10.0.2.2:8000\r\n', raw)
        self.assertTrue(raw.endswith('\r\n\r\n'))

    def test_get_request_without_token(self):
        raw = build_get_posts_request('h').decode()
        self.assertNotIn('Authorization', raw)

    def test_extra_headers(self):
        raw = build_get_posts_request('h', extra_headers={'If-None-Match': '"x"'}).decode()
        self.assertIn('If-None-Match: "x"', raw)


class MultipartTest(unittest.TestCase):
    def test_fields_and_file_parts(self):
        body, ctype = build_multipart({'title': '제목'}, {'image': ('a.jpg', b'\xff\xd8', 'image/jpeg')},
                                      boundary='BOUND')
        self.assertEqual(ctype, 'multipart/form-data; boundary=BOUND')
        self.assertIn('name="title"\r\n\r\n제목\r\n'.encode(), body)
        self.assertIn(b'filename="a.jpg"\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8\r\n', body)
        self.assertTrue(body.endswith(b'--BOUND--\r\n'))


class ParseResponseTest(unittest.TestCase):
    RAW = (b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAllow: GET, POST, HEAD, OPTIONS\r\n'
           b'Content-Length: 2\r\n\r\n[]extra')

    def test_parse_status_headers_body(self):
        res = parse_response(self.RAW)
        self.assertEqual((res.version, res.status, res.reason), ('HTTP/1.1', 200, 'OK'))
        self.assertEqual(res.header('Allow'), 'GET, POST, HEAD, OPTIONS')
        self.assertEqual(res.body, b'[]')  # Content-Length 만큼만
        self.assertEqual(res.text, '[]')

    def test_header_default(self):
        self.assertEqual(parse_response(self.RAW).header('x-none', 'd'), 'd')

    def test_chunked_body(self):
        raw = (b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'
               b'4\r\n[{"a\r\n5;ext=1\r\n":1}]\r\n0\r\n\r\n')
        self.assertEqual(parse_response(raw).body, b'[{"a":1}]')

    def test_broken_chunk(self):
        with self.assertRaises(HttpParseError):
            parse_response(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n4')

    def test_status_without_reason(self):
        self.assertEqual(parse_response(b'HTTP/1.1 304\r\n\r\n').reason, '')

    def test_missing_empty_line(self):
        with self.assertRaises(HttpParseError):
            parse_response(b'HTTP/1.1 200 OK\r\nA: b')

    def test_bad_status_line(self):
        with self.assertRaises(HttpParseError):
            parse_response(b'GARBAGE\r\n\r\n')

    def test_non_numeric_status(self):
        with self.assertRaises(HttpParseError):
            parse_response(b'HTTP/1.1 OK fine\r\n\r\n')

    def test_bad_header(self):
        with self.assertRaises(HttpParseError):
            parse_response(b'HTTP/1.1 200 OK\r\nNoColonHeader\r\n\r\n')


if __name__ == '__main__':
    unittest.main()
