"""포토 블로그 API 검증 엔진

telnet 으로 손으로 하던 API 검증(강의자료(1) p.8~10)을 소켓 수준에서 자동으로 수행한다.

    python -m api_engine http://127.0.0.1:8000 --token <TOKEN>
    python -m api_engine https://vyjsjs.pythonanywhere.com --user admin --password ****
"""
import json
import socket
import ssl
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .http_message import (DEFAULT_USER_AGENT, build_get_posts_request, build_multipart,
                           build_request, parse_response)
from .validator import validate_post, validate_post_list

API_PATH = '/api_root/Post/'


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ''

    def line(self):
        return '[%s] %s%s' % ('PASS' if self.passed else 'FAIL', self.name,
                              ' - ' + self.detail if self.detail else '')


@dataclass
class EngineReport:
    base_url: str
    results: list = field(default_factory=list)

    @property
    def ok(self):
        return all(r.passed for r in self.results)

    def add(self, name, passed, detail=''):
        result = CheckResult(name, bool(passed), detail)
        self.results.append(result)
        return result

    def render(self):
        lines = ['PhotoBlog API 검증 엔진 - %s' % self.base_url, '-' * 60]
        lines += [r.line() for r in self.results]
        lines.append('-' * 60)
        passed = sum(r.passed for r in self.results)
        lines.append('결과: %d/%d 통과 %s' % (passed, len(self.results), 'OK' if self.ok else 'FAILED'))
        return '\n'.join(lines)


class PhotoBlogApiEngine:
    def __init__(self, base_url, token=None, timeout=5.0):
        parsed = urlparse(base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            raise ValueError('http(s)://host[:port] 형식의 주소가 필요합니다: %r' % base_url)
        self.base_url = base_url.rstrip('/')
        self.scheme = parsed.scheme
        self.hostname = parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        self.host_header = parsed.netloc
        self.token = token
        self.timeout = timeout

    # ---- 전송 계층 (telnet 과 동일하게 소켓으로 직접 송수신) -------------------
    def send_raw(self, raw_request):
        sock = socket.create_connection((self.hostname, self.port), timeout=self.timeout)
        if self.scheme == 'https':
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.hostname)
        try:
            sock.sendall(raw_request)
            chunks = []
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                chunks.append(data)
        finally:
            sock.close()
        return parse_response(b''.join(chunks))

    def _auth_headers(self):
        return {'Authorization': 'Token %s' % self.token} if self.token else {}

    # ---- API 호출 -------------------------------------------------------------
    def obtain_token(self, username, password):
        body, ctype = build_multipart({'username': username, 'password': password}, {})
        raw = build_request('POST', '/api-token-auth/', self.host_header,
                            {'Content-Type': ctype, 'Accept': 'application/json',
                             'Connection': 'close'}, body)
        response = self.send_raw(raw)
        if response.status != 200:
            raise PermissionError('토큰 발급 실패 (%d): %s' % (response.status, response.text))
        self.token = json.loads(response.body)['token']
        return self.token

    def get_posts(self, query='', etag=None):
        extra = {'If-None-Match': etag} if etag else None
        raw = build_get_posts_request(self.host_header, self.token, API_PATH + query, extra)
        return self.send_raw(raw)

    def upload_post(self, title, text, image_bytes, filename='engine.jpg',
                    content_type='image/jpeg', authenticated=True, extra_fields=None):
        fields = {'title': title, 'text': text}
        fields.update(extra_fields or {})
        body, ctype = build_multipart(fields, {'image': (filename, image_bytes, content_type)})
        headers = {'Content-Type': ctype, 'Accept': 'application/json',
                   'User-Agent': DEFAULT_USER_AGENT, 'Connection': 'close'}
        if authenticated:
            headers.update(self._auth_headers())
        return self.send_raw(build_request('POST', API_PATH, self.host_header, headers, body))

    # ---- 검증 시나리오 ---------------------------------------------------------
    def run(self, sample_image=None):
        """GET 목록 형식 → 조건부 GET(304) → 미인증 업로드 거부 → (토큰 있으면) 업로드 검증"""
        report = EngineReport(self.base_url)

        res = self.get_posts()
        report.add('GET %s 상태 코드 200' % API_PATH, res.status == 200,
                   '%d %s' % (res.status, res.reason))
        report.add('Content-Type application/json',
                   (res.header('content-type') or '').startswith('application/json'),
                   res.header('content-type', ''))
        allow = res.header('allow', '')
        report.add('Allow 헤더에 GET, POST 포함', 'GET' in allow and 'POST' in allow, allow)
        body_report = validate_post_list(res.body)
        report.add('Message Body = 게시물 JSON Array', body_report.ok, body_report.summary())

        etag = res.header('etag')
        report.add('ETag 헤더 제공', bool(etag), etag or '')
        if etag:
            again = self.get_posts(etag=etag)
            report.add('If-None-Match → 304 Not Modified', again.status == 304,
                       '%d, body %dB' % (again.status, len(again.body)))

        if sample_image:
            anon = self.upload_post('engine anonymous', 'should be rejected', sample_image,
                                    authenticated=False)
            report.add('토큰 없는 POST 거부(401/403)', anon.status in (401, 403), str(anon.status))
            fake = self.upload_post('engine fake image', 'not an image', b'this is not an image',
                                    filename='fake.jpg', authenticated=bool(self.token))
            report.add('이미지가 아닌 파일 거부(400/401)', fake.status in (400, 401, 403), str(fake.status))
            if self.token:
                ok = self.upload_post('API 검증 엔진 업로드', '검증 엔진이 소켓으로 업로드한 게시물',
                                      sample_image, extra_fields={'author': '9999'})
                report.add('토큰 POST → 201 Created', ok.status == 201, str(ok.status))
                if ok.status == 201:
                    created = json.loads(ok.body)
                    errors = validate_post(created, 'created')
                    report.add('생성 응답 형식 검증', not errors, '; '.join(errors))
                    report.add('author 위조 무시(서버가 지정)', created.get('author') != 9999,
                               'author=%s' % created.get('author'))
        return report
