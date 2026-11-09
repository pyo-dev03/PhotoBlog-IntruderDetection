"""Message Body(JSON) 검증

강의자료(1) p.9~10 에서 codebeautify 로 눈으로 확인하던 JSON Array 검증을 자동화한다.
"""
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

ISO8601 = re.compile(
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$')

# 강의자료 p.9 의 필드 + 서버 확장 필드
REQUIRED_FIELDS = {
    'author': int,
    'title': str,
    'text': str,
    'created_date': str,
    'published_date': (str, type(None)),
    'image': str,
}
OPTIONAL_FIELDS = {
    'id': int,
    'author_name': str,
    'thumbnail': (str, type(None)),
    'updated_date': str,
}
TITLE_MAX_LENGTH = 200


@dataclass
class ValidationReport:
    count: int = 0
    errors: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors

    def add(self, where, message):
        self.errors.append('%s: %s' % (where, message))

    def summary(self):
        if self.ok:
            return 'OK - JSON Array %d건, 형식 오류 없음' % self.count
        return 'FAIL - %d건 중 오류 %d개\n  ' % (self.count, len(self.errors)) + '\n  '.join(self.errors)


def is_iso8601(value):
    return isinstance(value, str) and bool(ISO8601.match(value))


def is_http_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def validate_post(post, where='post'):
    """게시물 1건(JSON Object)을 검증하고 오류 메시지 목록을 돌려준다."""
    report = ValidationReport(count=1)
    if not isinstance(post, dict):
        report.add(where, 'JSON Object 가 아닙니다')
        return report.errors

    for name, kind in REQUIRED_FIELDS.items():
        if name not in post:
            report.add(where, "필수 필드 '%s' 누락" % name)
        elif not isinstance(post[name], kind) or isinstance(post[name], bool):
            report.add(where, "'%s' 타입 오류 (%s)" % (name, type(post[name]).__name__))
    for name, kind in OPTIONAL_FIELDS.items():
        if name in post and not isinstance(post[name], kind):
            report.add(where, "'%s' 타입 오류 (%s)" % (name, type(post[name]).__name__))

    if isinstance(post.get('title'), str):
        if not post['title'].strip():
            report.add(where, 'title 이 비어 있습니다')
        elif len(post['title']) > TITLE_MAX_LENGTH:
            report.add(where, 'title 이 %d자를 넘습니다' % TITLE_MAX_LENGTH)
    for name in ('created_date', 'published_date', 'updated_date'):
        value = post.get(name)
        if isinstance(value, str) and not is_iso8601(value):
            report.add(where, "'%s' 가 ISO 8601 형식이 아닙니다: %s" % (name, value))
    for name in ('image', 'thumbnail'):
        value = post.get(name)
        if isinstance(value, str) and not is_http_url(value):
            report.add(where, "'%s' 가 절대 URL 이 아닙니다: %s" % (name, value))
    return report.errors


def validate_post_list(body):
    """GET /api_root/Post/ 의 Message Body 검증 (bytes / str / list 모두 허용)"""
    report = ValidationReport()
    if isinstance(body, (bytes, bytearray)):
        body = body.decode('utf-8')
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError as exc:
            report.add('body', 'JSON 파싱 실패 (%s)' % exc.msg)
            return report
    if not isinstance(body, list):
        report.add('body', 'JSON Array 가 아닙니다 (%s)' % type(body).__name__)
        return report
    report.count = len(body)
    for i, post in enumerate(body):
        report.errors.extend(validate_post(post, where='[%d]' % i))
    return report
