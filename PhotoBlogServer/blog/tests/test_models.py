"""모델 / 썸네일(편의기능 ①) 테스트"""
from django.contrib.auth.models import User
from django.test import TestCase
from PIL import Image

from blog.imaging import make_thumbnail, thumbnail_name
from blog.models import Post

from .helpers import TempMediaMixin, make_upload


class PostModelTest(TempMediaMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user('writer', password='pw')

    def test_str_is_title(self):
        post = Post(author=self.user, title='제목', text='본문')
        self.assertEqual(str(post), '제목')

    def test_publish_sets_published_date(self):
        post = Post.objects.create(author=self.user, title='t', text='x', image=make_upload())
        self.assertIsNone(post.published_date)
        post.publish()
        self.assertIsNotNone(post.published_date)

    def test_thumbnail_created_and_smaller(self):
        post = Post.objects.create(author=self.user, title='t', text='x',
                                   image=make_upload(size=(2000, 1500)))
        with Image.open(post.thumbnail.path) as thumb:
            self.assertLessEqual(max(thumb.size), 480)
            self.assertEqual(thumb.format, 'JPEG')
        self.assertLess(post.thumbnail.size, post.image.size)

    def test_thumbnail_respects_exif_orientation(self):
        # orientation 6 = 90도 회전 → 가로 사진이 세로 썸네일이 되어야 함
        post = Post.objects.create(author=self.user, title='t', text='x',
                                   image=make_upload(size=(800, 400), exif_orientation=6))
        with Image.open(post.thumbnail.path) as thumb:
            self.assertGreater(thumb.size[1], thumb.size[0])

    def test_thumbnail_not_regenerated_when_image_unchanged(self):
        post = Post.objects.create(author=self.user, title='t', text='x', image=make_upload())
        first = post.thumbnail.name
        post = Post.objects.get(pk=post.pk)
        post.title = 'changed'
        post.save()
        self.assertEqual(post.thumbnail.name, first)

    def test_thumbnail_regenerated_when_image_changes(self):
        post = Post.objects.create(author=self.user, title='t', text='x', image=make_upload())
        first = post.thumbnail.name
        post = Post.objects.get(pk=post.pk)
        post.image = make_upload('second.jpg')
        post.save()
        self.assertNotEqual(post.thumbnail.name, first)
        self.assertIn('second', post.thumbnail.name)

    def test_missing_image_file_does_not_block_save(self):
        post = Post.objects.create(author=self.user, title='t', text='x',
                                   image='blog_image/does_not_exist.png')
        self.assertFalse(post.thumbnail)

    def test_grayscale_image_thumbnail(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
        buf = BytesIO()
        Image.new('L', (300, 300), 128).save(buf, 'JPEG')
        post = Post.objects.create(author=self.user, title='t', text='x',
                                   image=SimpleUploadedFile('g.jpg', buf.getvalue()))
        self.assertTrue(post.thumbnail)

    def test_cmyk_image_thumbnail_converted_to_rgb(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
        buf = BytesIO()
        Image.new('CMYK', (300, 300), (0, 50, 50, 0)).save(buf, 'JPEG')
        post = Post.objects.create(author=self.user, title='t', text='x',
                                   image=SimpleUploadedFile('c.jpg', buf.getvalue()))
        with Image.open(post.thumbnail.path) as thumb:
            self.assertEqual(thumb.mode, 'RGB')

    def test_thumbnail_name(self):
        self.assertEqual(thumbnail_name('blog_image/2026/10/14/sky.png'), 'sky_thumb.jpg')

    def test_make_thumbnail_returns_content_file(self):
        post = Post.objects.create(author=self.user, title='t', text='x', image=make_upload())
        content = make_thumbnail(post.image)
        self.assertTrue(content.name.endswith('_thumb.jpg'))
        self.assertGreater(len(content.read()), 0)
