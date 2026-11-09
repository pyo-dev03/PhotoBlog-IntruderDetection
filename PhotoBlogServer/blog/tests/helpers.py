"""테스트 공용 도구 : 임시 MEDIA_ROOT, 테스트 이미지 생성"""
import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image


def make_image_bytes(fmt='JPEG', size=(1200, 800), color=(30, 120, 200), exif_orientation=None):
    img = Image.new('RGBA' if fmt == 'PNG' else 'RGB', size,
                    color + ((128,) if fmt == 'PNG' else ()))
    buf = BytesIO()
    kwargs = {}
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        kwargs['exif'] = exif
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def make_upload(name='photo.jpg', fmt='JPEG', content_type='image/jpeg', **kwargs):
    return SimpleUploadedFile(name, make_image_bytes(fmt, **kwargs), content_type=content_type)


class TempMediaMixin:
    """테스트마다 업로드 파일이 실제 media 폴더를 더럽히지 않도록 임시 폴더 사용"""

    @classmethod
    def setUpClass(cls):
        cls._media_dir = tempfile.mkdtemp(prefix='photoblog-test-media-')
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
