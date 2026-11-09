# PhotoViewer (Android, Java)

- minSdk 24 / target·compileSdk 36, AGP 9.2.1, Java 11
- 패키지 : `com.example.photoviewer`

## 화면

| 화면 | 파일 | 내용 |
|---|---|---|
| 메인 | `MainActivity.java`, `activity_main.xml` | [동기화] `onClickDownload` → `CloadImage`, [새로운 이미지 게시] `onClickUpload` → 게시 화면 → `PutPost` |
| 게시 (Upload UI) | `dialog_upload.xml` | Photo Picker 사진 선택, 제목/내용 입력, 압축 결과·진행률·재시도 로그 표시 |
| 목록 항목 | `ImageAdapter.java`, `item_image.xml` | 썸네일 + 제목/본문/날짜/작성자 카드, 탭 → 상세 |
| 상세 | `DetailActivity.java`, `ZoomImageView.java` | 원본 이미지, 핀치 줌·더블탭 |
| 로그인 · 설정 | `SettingsActivity.java` | 서버 주소(로컬 ↔ PythonAnywhere), ID/PW 로그인(토큰 발급), 테스트 옵션 |

## 공통평가02 추가 (YOLO 침입 감지 확인)

| 기능 | 파일 |
|---|---|
| 감지 게시물 카드에 `● 미확인 · person, cell phone · 최고 91% · 장치명` 표시 | `PostItem.detectionSummary()`, `ImageAdapter`, `item_image.xml` |
| 필터 칩 : 전체 / YOLO 감지 / 미확인 / 클래스별(서버 `/api_root/Post/stats/` 로 구성) | `MainActivity.renderFilterChips()`, `activity_main.xml` |
| 상세 화면 검출 목록(클래스·신뢰도·박스) + **감지 확인 처리** (`POST /api_root/Post/<id>/ack/`) | `DetailActivity.setupDetection()`, `activity_detail.xml` |

## 주요 클래스

| 클래스 | 역할 |
|---|---|
| `AppSettings` | 서버 주소, 로그인 정보, ETag 캐시 저장 |
| `TokenStore` | 토큰을 Android Keystore AES-256/GCM 으로 암호화 |
| `ImageCache` | 메모리(LruCache) + 디스크 이미지 캐시 |
| `ImageCompressor` | 업로드 전 1600px 축소, JPEG 85%, EXIF 회전 보정 |

## 실행

1. Android Studio → Open → `PhotoViewer`
2. 서버 실행 (`PhotoBlogServer`, `python manage.py runserver`)
3. 에뮬레이터에서 실행 → 메뉴(⋮) → **로그인 · 설정** 에서 로그인 → [동기화] / [새로운 이미지 게시]

에뮬레이터에서 호스트 PC 의 서버는 `http://10.0.2.2:8000` 으로 접속한다.
