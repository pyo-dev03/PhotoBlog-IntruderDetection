"""HTTP 메시지(Request / Response) 생성·파싱

강의자료(1) p.8~9 의 telnet 실습을 코드로 옮긴 것.
  Request Line / HTTP Header / Empty Line / Message Body 를 직접 다룬다.
"""
from dataclasses import dataclass, field

CRLF = '\r\n'

# 강의자료 p.8 의 Android(Dalvik) 클라이언트 요청 헤더
DEFAULT_USER_AGENT = ('Dalvik/2.1.0 (Linux; U; Android 13; sdk_gphone64_arm64 '
                      'Build/TPB4.220624.004)')


class HttpParseError(ValueError):
    """응답 메시지 형식이 HTTP/1.x 규칙에 맞지 않을 때"""


def build_request(method, path, host, headers=None, body=b''):
    """Request Line + Header + Empty Line (+ Body) 바이트열을 만든다."""
    if not path.startswith('/'):
        raise ValueError('path 는 / 로 시작해야 합니다: %r' % path)
    lines = ['%s %s HTTP/1.1' % (method.upper(), path), 'Host: %s' % host]
    for name, value in (headers or {}).items():
        lines.append('%s: %s' % (name, value))
    if body:
        lines.append('Content-Length: %d' % len(body))
    head = CRLF.join(lines) + CRLF + CRLF
    return head.encode('utf-8') + (body or b'')


def build_get_posts_request(host, token=None, path='/api_root/Post/', extra_headers=None):
    """강의자료 p.8 과 같은 GET /api_root/Post/ 요청"""
    headers = {}
    if token:
        headers['Authorization'] = 'Token %s' % token
    headers['User-Agent'] = DEFAULT_USER_AGENT
    headers['Accept'] = 'application/json'
    headers['Connection'] = 'close'
    headers.update(extra_headers or {})
    return build_request('GET', path, host, headers)


def build_multipart(fields, files, boundary='----PhotoBlogBoundary7MA4YWxkTrZu0gW'):
    """multipart/form-data 본문 생성. files: {name: (filename, bytes, content_type)}"""
    out = bytearray()
    for name, value in fields.items():
        out += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                % (boundary, name, value)).encode('utf-8')
    for name, (filename, data, ctype) in files.items():
        out += ('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
                'Content-Type: %s\r\n\r\n' % (boundary, name, filename, ctype)).encode('utf-8')
        out += data + b'\r\n'
    out += ('--%s--\r\n' % boundary).encode('utf-8')
    return bytes(out), 'multipart/form-data; boundary=%s' % boundary


@dataclass
class HttpResponse:
    version: str
    status: int
    reason: str
    headers: dict = field(default_factory=dict)
    body: bytes = b''

    def header(self, name, default=None):
        return self.headers.get(name.lower(), default)

    @property
    def text(self):
        return self.body.decode('utf-8', errors='replace')


def _decode_chunked(data):
    out = bytearray()
    pos = 0
    while True:
        end = data.find(b'\r\n', pos)
        if end < 0:
            raise HttpParseError('chunk size 줄이 끝나지 않았습니다')
        size = int(data[pos:end].split(b';')[0].strip() or b'0', 16)
        pos = end + 2
        if size == 0:
            return bytes(out)
        out += data[pos:pos + size]
        pos += size + 2


def parse_response(raw):
    """서버 응답 바이트열 → HttpResponse (Response Line / Header / Empty Line / Body 분리)"""
    sep = raw.find(b'\r\n\r\n')
    if sep < 0:
        raise HttpParseError('Header 와 Body 를 구분하는 Empty Line 이 없습니다')
    head = raw[:sep].decode('iso-8859-1')
    body = raw[sep + 4:]
    lines = head.split('\r\n')
    status_line = lines[0].split(' ', 2)
    if len(status_line) < 2 or not status_line[0].startswith('HTTP/'):
        raise HttpParseError('잘못된 Response Line: %r' % lines[0])
    try:
        status = int(status_line[1])
    except ValueError:
        raise HttpParseError('상태 코드가 숫자가 아닙니다: %r' % status_line[1])
    headers = {}
    for line in lines[1:]:
        if ':' not in line:
            raise HttpParseError('잘못된 Header: %r' % line)
        name, value = line.split(':', 1)
        headers[name.strip().lower()] = value.strip()
    if headers.get('transfer-encoding', '').lower() == 'chunked':
        body = _decode_chunked(body)
    elif 'content-length' in headers:
        body = body[:int(headers['content-length'])]
    return HttpResponse(status_line[0], status, status_line[2] if len(status_line) > 2 else '',
                        headers, body)
