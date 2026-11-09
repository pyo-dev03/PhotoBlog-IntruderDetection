"""편의기능 ③ 업로드 검증기 단위 테스트"""
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from blog.validators import validate_photo

from .helpers import make_image_bytes, make_upload


class ValidatePhotoTest(SimpleTestCase):
    def test_valid_jpeg_passes(self):
        validate_photo(make_upload())

    def test_valid_png_passes_and_stream_rewound(self):
        upload = make_upload('a.png', fmt='PNG', content_type='image/png')
        validate_photo(upload)
        self.assertEqual(upload.file.tell(), 0)

    def test_no_extension_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_photo(SimpleUploadedFile('noext', make_image_bytes()))
        self.assertEqual(ctx.exception.code, 'invalid_extension')

    def test_text_file_disguised_as_jpg_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_photo(SimpleUploadedFile('x.jpg', b'hello world'))
        self.assertEqual(ctx.exception.code, 'invalid_image')

    @override_settings(PHOTO_MAX_UPLOAD_BYTES=10)
    def test_size_limit(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_photo(make_upload())
        self.assertEqual(ctx.exception.code, 'file_too_large')

    def test_png_content_with_jpg_extension_is_still_image(self):
        # 확장자와 실제 형식이 달라도 허용 형식이면 통과 (확장자보다 실제 내용 기준)
        validate_photo(SimpleUploadedFile('a.jpg', make_image_bytes('PNG')))

    @override_settings(PHOTO_ALLOWED_FORMATS=('JPEG',))
    def test_format_not_allowed(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_photo(SimpleUploadedFile('a.png', make_image_bytes('PNG')))
        self.assertEqual(ctx.exception.code, 'invalid_format')

    @override_settings(PHOTO_MAX_PIXELS=10)
    def test_pixel_limit(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_photo(make_upload())
        self.assertEqual(ctx.exception.code, 'too_many_pixels')

    def test_missing_stored_file_is_skipped(self):
        class Missing:
            name = 'blog_image/missing.png'

            @property
            def size(self):
                raise FileNotFoundError

        validate_photo(Missing())

    def test_object_without_tell_is_handled(self):
        class NoTell:
            def __init__(self, data):
                from io import BytesIO
                self._buf = BytesIO(data)
                self.name = 'x.jpg'
                self.size = len(data)

            def read(self, *a):
                return self._buf.read(*a)

            def seek(self, *a):
                return self._buf.seek(*a)

            def tell(self):
                raise OSError('not seekable')

        validate_photo(NoTell(make_image_bytes()))
