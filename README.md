# PhotoBlog Intruder Detection - 모바일/웹서비스 프로젝트 공통평가 02

- 학번 / 이름 : 2022105757 / 표정수
- 강의자료 **Ch08. Django 와 YOLO 를 이용한 침입자 감지 시스템**
- 공통평가 01 레포([pyo-dev03/PhotoBlog](https://github.com/pyo-dev03/PhotoBlog))를 기반으로 기능을 추가한 **별도 레포지토리**

```
ROOT
 ├─ PhotoBlogServer/   Django Server  (REST API + 감지 수신/통계/확인 처리 + 대시보드 웹)
 ├─ PhotoViewer/       Android Client (감지 목록·필터·확인 처리)
 ├─ YOLOv5/            Edge Client    (YOLOv5 + changedetection.py → 서버 전송)
 └─ 모바일/웹서비스 프로젝트 공통평가 02_수행 결과 보고서.docx
```

## 시스템 구성 (강의자료 p.3)

```
[카메라/영상] → YOLOv5 detect.py ──(변화 감지: changedetection.py)──▶ POST /api_root/Post/  (JWT 토큰)
                                                                      │
                                    Django PhotoBlogServer (SQLite) ◀──┘
                                      ├─ /            감지 목록 (클래스·미확인 필터)
                                      ├─ /dashboard/  감지 대시보드
                                      └─ /api_root/   REST API  ◀── Android PhotoViewer
```

| 서버 | 주소 |
|---|---|
| 로컬 | http://127.0.0.1:8000/ , API http://127.0.0.1:8000/api_root/Post/ |
| Android 에뮬레이터 | http://10.0.2.2:8000 |
| PythonAnywhere | https://vyjsjs.pythonanywhere.com/ |

## 실행 순서

```bash
# 1) 서버
cd PhotoBlogServer && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && python manage.py migrate
python manage.py createsuperuser            # Edge 가 사용할 계정
python manage.py runserver

# 2) Edge Client (다른 터미널)
cd YOLOv5 && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python detect.py --source 0 --no-send                                  # 강의 p.6 기본 실행 (전송 없음)
python detect.py --source 0 --server http://127.0.0.1:8000 \
       --username admin --password <pw> --device-name macbook-cam0       # 웹캠 → 서버 전송
python detect.py --source data/videos/intruder_demo.mp4 --server https://vyjsjs.pythonanywhere.com ...

# 3) Android : PhotoViewer 를 Android Studio 로 열어 실행 → 메뉴 > 로그인·설정
```

## 구현 항목 (보고서 번호)

| # | 항목 | 구현 위치 |
|---|---|---|
| 3 | YOLOv5 설치 및 실행 | `YOLOv5/` (ultralytics/yolov5), `python detect.py` |
| 4 | 검출기 코드 수정 | `YOLOv5/changedetection.py`, `YOLOv5/detect.py` (`# added` 표시), `YOLOv5/.vscode/launch.json` |
| 5-6 | 블로그 등록 결과 (localhost) | `PhotoBlogServer/blog/` |
| 7 | 모바일 화면 확인 | `PhotoViewer/` (감지 요약·필터 칩·확인 처리), 반응형 웹 |
| 8-9 | PythonAnywhere | 아래 배포 절차 |
| 10 | 편의 기능 2개 | 아래 표 |

## 기획되지 않은 편의 기능 (2개)

| # | 기능 | 구현 | 설명 |
|---|---|---|---|
| ① | **침입 감지 대시보드 & 확인(Ack) 처리** | Server `blog/stats.py`, `views.py`(`stats`, `ack`, `dashboard`), `templates/blog/dashboard.html` / Android `MainActivity`(필터 칩), `DetailActivity`(확인 버튼) | 검출 클래스·신뢰도·박스(JSON)를 저장하고 클래스/날짜/미확인 필터, 시간대·클래스·일별 통계, Edge 장치 온라인 상태, 새 감지 실시간 배너, 감지 확인 처리 제공 |
| ② | **Edge 감지 신뢰성 강화** | Edge `YOLOv5/changedetection.py` | N프레임 연속 검출 시에만 출현 인정(깜빡임 억제), 클래스별 쿨다운, 관심 클래스/최소 신뢰도 필터, 비동기 전송 스레드, 서버 장애 시 outbox 저장 후 지수 백오프 재전송(재시작해도 유지) |

## 테스트

```bash
cd PhotoBlogServer && python manage.py test          # 142 tests (감지 API/통계/대시보드 21개 추가)
cd YOLOv5 && python -m pytest tests/test_changedetection.py   # 7 tests (변화 감지, 깜빡임, 쿨다운, 오프라인 큐)
```
