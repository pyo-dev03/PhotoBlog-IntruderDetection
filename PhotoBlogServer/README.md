# PhotoBlogServer (Django)

## 실행

```bash
cd PhotoBlogServer
python3.13 -m venv venv && source venv/bin/activate     # Django 6.1 → Python 3.12 이상
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py drf_create_token <username>             # API 토큰 (앱은 로그인으로 자동 발급)
python manage.py runserver                               # http://127.0.0.1:8000/
```

## API

| Method | URL | 설명 |
|---|---|---|
| GET | `/api_root/Post/` | 게시물 목록 (JSON Array, 페이지네이션 없음) |
| GET | `/api_root/Post/?search=키워드` | 제목/본문 검색 |
| GET | `/api_root/Post/?since=2026-10-14T12:00:00+09:00` | 이후 변경된 게시물만 |
| GET + `If-None-Match` | `/api_root/Post/` | 변경 없으면 `304 Not Modified` |
| POST | `/api_root/Post/` | multipart: `title`, `text`, `image`, (`created_date`, `published_date`) - 인증 필요 |
| PATCH/DELETE | `/api_root/Post/<id>/` | 작성자 본인만 |
| POST | `/api-token-auth/` | `username`, `password` → `{"token": ...}` |
| GET | `/api_root/Post/?label=person` | **공통평가02** 검출 클래스 필터 |
| GET | `/api_root/Post/?source=edge` / `?unacked=1` / `?date=2026-11-09` | YOLO 감지만 / 미확인만 / 날짜 |
| GET | `/api_root/Post/stats/` | 감지 통계 (오늘·미확인·클래스별·시간대별·일별·장치별) |
| POST | `/api_root/Post/<id>/ack/` | 감지 확인 처리 (`{"acknowledged": false}` 로 취소) - 작성자/관리자 |

### YOLOv5 Edge Client 전송 형식 (강의자료 Ch08 p.10 + 확장)

multipart : `title`, `text`, `created_date`, `published_date`, `image` (+ `detections` JSON 문자열, `device`)

```
detections = [{"label": "person", "confidence": 0.91, "box": [x1, y1, x2, y2]}, ...]
```
`detections` 가 있으면 `source = edge` 로 저장되고 `labels`, `max_confidence`, `acknowledged` 가 응답에 포함된다.

웹 : `/` 감지 목록(클래스·미확인 필터), `/dashboard/` 감지 대시보드, `/post/<id>/` 검출 표 + 확인 처리

인증 헤더 : `Authorization: Token <key>` (강의자료) 또는 `Authorization: JWT <key>` (ch03 실습 호환)

응답 예
```json
[{"author":1,"title":"우주이야기","text":"...","created_date":"...","published_date":"...",
  "image":"http://10.0.2.2:8000/media/blog_image/2026/10/14/a.jpg",
  "id":3,"author_name":"vyjsjs","thumbnail":"http://10.0.2.2:8000/media/blog_thumb/2026/10/14/a_thumb.jpg",
  "updated_date":"..."}]
```

## 자동 테스트 / Code Coverage (강의자료(2) ch04)

```bash
coverage run manage.py test        # 142 tests
coverage report
coverage html                      # htmlcov/index.html
```

| 테스트 | 내용 |
|---|---|
| `blog/tests/test_api.py` | API 목록/생성/권한/ETag/since/search/업로드 검증 |
| `blog/tests/test_models.py` | 썸네일 생성(EXIF 회전, 투명 PNG, CMYK), 재생성 조건 |
| `blog/tests/test_validators.py` | 업로드 이미지 검증기 |
| `blog/tests/test_web.py` | 웹 페이지 |
| `api_engine/tests/` | 검증 엔진 단위 테스트 + 실제 서버(LiveServer) 통합 테스트 |

## API 검증 엔진

telnet 실습(강의자료 p.8~10)을 자동화한 엔진. 소켓으로 HTTP 메시지를 직접 송수신하고
응답의 Response Line / Header / Message Body(JSON Array 형식)를 검증한다.

```bash
python -m api_engine http://127.0.0.1:8000 --user <id> --password <pw> --image media/blog_image/default_error.png
python -m api_engine https://vyjsjs.pythonanywhere.com
```

## Socket Server (강의자료 p.24)

```bash
python socket_server/socket_server.py   # 127.0.0.1:8000, 수신 요청을 socket_server/request/*.bin 으로 저장
```

## PythonAnywhere 배포

```bash
git clone https://github.com/pyo-dev03/PhotoBlog-IntruderDetection.git
cd PhotoBlog-IntruderDetection/PhotoBlogServer
python3.13 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate && python manage.py collectstatic --noinput
python manage.py createsuperuser
```
Web 탭 : Manual configuration (Python 3.13), Virtualenv `~/PhotoBlog-IntruderDetection/PhotoBlogServer/venv`,
Static `/static/` → `~/PhotoBlog-IntruderDetection/PhotoBlogServer/staticfiles`, `/media/` → `~/PhotoBlog-IntruderDetection/PhotoBlogServer/media`,
WSGI 파일에서 `path = '/home/vyjsjs/PhotoBlog-IntruderDetection/PhotoBlogServer'`, `DJANGO_SETTINGS_MODULE = 'mysite.settings'`.
