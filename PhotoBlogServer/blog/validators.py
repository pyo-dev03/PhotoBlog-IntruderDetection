"""편의기능 ③ - 업로드 이미지 검증 (보안 / Secure coding)

확장자만 믿지 않고 Pillow 로 실제 이미지 헤더를 열어 형식·크기·픽셀 수를 확인한다.
모델 필드 validator 로 등록하므로 웹 폼(ModelForm)과 REST API(ModelSerializer) 모두에 적용된다.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

ALLOWED_EXTENSIONS = ('jpg', 'jpeg', 'png', 'webp', 'gif')


def _max_bytes():
    return getattr(settings, 'PHOTO_MAX_UPLOAD_BYTES', 10 * 1024 * 1024)


def validate_photo(value):
    """업로드 이미지가 허용 정책을 만족하는지 검사한다."""
    name = getattr(value, 'name', '') or ''
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            '허용되지 않는 파일 확장자입니다. (%(allowed)s)',
            code='invalid_extension',
            params={'allowed': ', '.join(ALLOWED_EXTENSIONS)},
        )

    try:
        size = value.size
    except (OSError, ValueError):
        # 저장소에 파일이 없는 경우(기본 이미지 등)는 검사 대상이 아님
        return
    if size > _max_bytes():
        raise ValidationError(
            '이미지 크기는 %(limit)dMB 이하만 업로드할 수 있습니다.',
            code='file_too_large',
            params={'limit': _max_bytes() // (1024 * 1024)},
        )

    fp = getattr(value, 'file', value)
    try:
        pos = fp.tell()
    except (AttributeError, OSError, ValueError):
        pos = None
    try:
        with Image.open(fp) as img:
            fmt = img.format
            width, height = img.size
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise ValidationError('이미지 파일이 아니거나 손상된 파일입니다.', code='invalid_image')
    finally:
        if pos is not None:
            fp.seek(pos)

    if fmt not in getattr(settings, 'PHOTO_ALLOWED_FORMATS', ('JPEG', 'PNG', 'WEBP', 'GIF')):
        raise ValidationError('지원하지 않는 이미지 형식입니다: %(fmt)s', code='invalid_format',
                              params={'fmt': fmt})
    if width * height > getattr(settings, 'PHOTO_MAX_PIXELS', 40_000_000):
        raise ValidationError('이미지 해상도가 너무 큽니다.', code='too_many_pixels')
