"""
PhotoBlogServer - Django settings

강의자료(1) ch05 "모바일 앱으로 사용하는 기본 포토 블로그" 의 서버.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 운영(PythonAnywhere)에서는 환경변수로 비밀키를 지정할 수 있게 함
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-photoblog-2022105757-local-development-key-change-me',
)

DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'

# 강의자료 p.5 : 접속 가능한 Host 설정
#   127.0.0.1 / localhost : 브라우저, telnet
#   10.0.2.2              : Android 에뮬레이터에서 바라본 호스트 PC
#   .pythonanywhere.com   : 클라우드 배포
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '10.0.2.2', '.pythonanywhere.com']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'blog',
    'rest_framework',
    'rest_framework.authtoken',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mysite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mysite.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/admin/login/'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # 강의자료 p.8, p.21 : 'Authorization: Token <key>'
        'rest_framework.authentication.TokenAuthentication',
        # ch03 curl 실습 호환 : 'Authorization: JWT <key>'
        'blog.authentication.JWTKeywordTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    # 페이지네이션 없음 : Android 클라이언트(강의자료 p.22)가 응답을 JSONArray 로 바로 파싱함
    'DEFAULT_PAGINATION_CLASS': None,
}

# ---- 편의기능 ③ 업로드 검증 정책 ----
PHOTO_MAX_UPLOAD_BYTES = 10 * 1024 * 1024          # 10 MB
PHOTO_ALLOWED_FORMATS = ('JPEG', 'PNG', 'WEBP', 'GIF')
PHOTO_MAX_PIXELS = 40_000_000                       # 40 MP (decompression bomb 방지)

# ---- 편의기능 ① 썸네일 ----
PHOTO_THUMBNAIL_SIZE = (480, 480)
PHOTO_THUMBNAIL_QUALITY = 80

# 테스트 실행 속도 향상 (테스트에서만 빠른 해시 사용)
import sys  # noqa: E402
if len(sys.argv) > 1 and sys.argv[1] == 'test':
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
