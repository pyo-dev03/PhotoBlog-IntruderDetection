"""편의기능 ① - 썸네일 자동 생성 (효율성)

목록 화면(Android 동기화)에서는 원본 대신 수십 KB 크기의 썸네일만 내려받도록
업로드 시점에 서버가 JPEG 썸네일을 한 번 만들어 둔다.
"""
import os
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def thumbnail_name(image_name):
    stem = os.path.splitext(os.path.basename(image_name))[0]
    return f'{stem}_thumb.jpg'


def make_thumbnail(field_file):
    """ImageField 파일로부터 JPEG 썸네일(ContentFile)을 만든다.

    - EXIF 회전 정보를 반영해 실제 보이는 방향으로 회전
    - 투명 배경(PNG/GIF/WEBP)은 흰색으로 합성
    """
    size = getattr(settings, 'PHOTO_THUMBNAIL_SIZE', (480, 480))
    quality = getattr(settings, 'PHOTO_THUMBNAIL_QUALITY', 80)

    field_file.open('rb')
    field_file.seek(0)
    with Image.open(field_file) as src:
        img = ImageOps.exif_transpose(src)
        img.thumbnail(size)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGBA')
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
    field_file.seek(0)
    return ContentFile(buf.getvalue(), name=thumbnail_name(field_file.name))
