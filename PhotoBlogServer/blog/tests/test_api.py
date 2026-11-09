"""Server API 자동 테스트 - 강의자료(1) p.5~10 의 API 요구사항 + 편의기능 ①③"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from blog.models import Post

from .helpers import TempMediaMixin, make_upload

API = '/api_root/Post/'


class PostApiTestBase(TempMediaMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('writer', password='pw-12345!')
        self.other = User.objects.create_user('other', password='pw-12345!')
        self.token = Token.objects.create(user=self.user)
        self.other_token = Token.objects.create(user=self.other)
        self.client = APIClient()

    def auth(self, token=None, keyword='Token'):
        self.client.credentials(HTTP_AUTHORIZATION='%s %s' % (keyword, (token or self.token).key))

    def create_post(self, author=None, title='서진이', text='서진이가 그림을 그린다', **kwargs):
        return Post.objects.create(author=author or self.user, title=title, text=text,
                                   published_date=timezone.now(), image=make_upload(), **kwargs)

    def upload(self, **overrides):
        data = {'title': '우주이야기', 'text': '제임스웹이 보내온 성운', 'image': make_upload()}
        data.update(overrides)
        return self.client.post(API, data, format='multipart')


class ApiRootTest(PostApiTestBase):
    def test_api_root_lists_post_endpoint(self):
        res = self.client.get('/api_root/', HTTP_ACCEPT='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['Post'].endswith('/api_root/Post/'))

    def test_allowed_methods_are_get_post_head_options(self):
        res = self.client.options(API)
        self.assertEqual(res.status_code, 200)
        for method in ('GET', 'POST', 'HEAD', 'OPTIONS'):
            self.assertIn(method, res['Allow'])


class PostListApiTest(PostApiTestBase):
    def test_empty_list_is_json_array(self):
        res = self.client.get(API)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_list_is_json_array_not_paginated(self):
        for i in range(12):
            self.create_post(title='post %d' % i)
        data = self.client.get(API).json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 12)

    def test_list_item_has_lecture_fields_and_absolute_image_url(self):
        self.create_post()
        item = self.client.get(API, HTTP_HOST='10.0.2.2:8000').json()[0]
        self.assertEqual(list(item)[:6],
                         ['author', 'title', 'text', 'created_date', 'published_date', 'image'])
        self.assertTrue(item['image'].startswith('http://10.0.2.2:8000/media/blog_image/'))
        self.assertTrue(item['thumbnail'].startswith('http://10.0.2.2:8000/media/blog_thumb/'))
        self.assertEqual(item['author_name'], 'writer')

    def test_post_without_thumbnail_falls_back_to_image_url(self):
        post = self.create_post()
        Post.objects.filter(pk=post.pk).update(thumbnail='')
        item = self.client.get(API).json()[0]
        self.assertEqual(item['thumbnail'], item['image'])

    def test_list_newest_first(self):
        old = self.create_post(title='old')
        old.published_date = timezone.now() - timedelta(days=1)
        old.save()
        self.create_post(title='new')
        titles = [p['title'] for p in self.client.get(API).json()]
        self.assertEqual(titles, ['new', 'old'])

    def test_search_by_title_or_text(self):
        self.create_post(title='우주이야기', text='성운')
        self.create_post(title='서진이', text='그림')
        self.assertEqual(len(self.client.get(API, {'search': '우주'}).json()), 1)
        self.assertEqual(len(self.client.get(API, {'search': '그림'}).json()), 1)
        self.assertEqual(len(self.client.get(API, {'search': '없는말'}).json()), 0)

    def test_retrieve_single_post(self):
        post = self.create_post()
        res = self.client.get('%s%d/' % (API, post.pk))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['title'], '서진이')

    def test_list_accessible_with_token_header_like_android(self):
        self.create_post()
        self.auth()
        res = self.client.get(API, HTTP_USER_AGENT='Dalvik/2.1.0 (Linux; U; Android 13)')
        self.assertEqual(res.status_code, 200)

    def test_invalid_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token not-a-real-token')
        self.assertEqual(self.client.get(API).status_code, 401)


class ConditionalGetTest(PostApiTestBase):
    """편의기능 ① : ETag / 304 Not Modified / since 증분 동기화"""

    def test_etag_header_present(self):
        res = self.client.get(API)
        self.assertTrue(res['ETag'].startswith('"'))
        self.assertEqual(res['Cache-Control'], 'no-cache')

    def test_same_etag_returns_304_without_body(self):
        self.create_post()
        etag = self.client.get(API)['ETag']
        res = self.client.get(API, HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(res.status_code, status.HTTP_304_NOT_MODIFIED)
        self.assertEqual(res.content, b'')

    def test_etag_changes_after_new_post(self):
        etag = self.client.get(API)['ETag']
        self.create_post()
        res = self.client.get(API, HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(res.status_code, 200)
        self.assertNotEqual(res['ETag'], etag)

    def test_etag_changes_after_delete(self):
        post = self.create_post()
        self.create_post(title='second')
        etag = self.client.get(API)['ETag']
        post.delete()
        self.assertEqual(self.client.get(API, HTTP_IF_NONE_MATCH=etag).status_code, 200)

    def test_etag_changes_after_edit(self):
        post = self.create_post()
        etag = self.client.get(API)['ETag']
        post.title = 'edited'
        post.save()
        self.assertEqual(self.client.get(API, HTTP_IF_NONE_MATCH=etag).status_code, 200)

    def test_if_none_match_with_multiple_etags(self):
        etag = self.client.get(API)['ETag']
        res = self.client.get(API, HTTP_IF_NONE_MATCH='"stale", %s' % etag)
        self.assertEqual(res.status_code, 304)

    def test_since_returns_only_changed_posts(self):
        self.create_post(title='before')
        Post.objects.update(updated_date=timezone.now() - timedelta(hours=1))
        mark = timezone.now() - timedelta(minutes=1)
        self.create_post(title='after')
        res = self.client.get(API, {'since': mark.isoformat()})
        self.assertEqual([p['title'] for p in res.json()], ['after'])

    def test_since_accepts_plus_sign_decoded_as_space(self):
        self.create_post()
        res = self.client.get(API + '?since=2000-01-01T00:00:00+09:00')  # '+' → ' '
        self.assertEqual(len(res.json()), 1)

    def test_since_naive_datetime_is_local_time(self):
        self.create_post()
        res = self.client.get(API, {'since': '2000-01-01T00:00:00'})
        self.assertEqual(len(res.json()), 1)

    def test_invalid_since_is_400(self):
        res = self.client.get(API, {'since': 'yesterday'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('since', res.json())


class PostCreateApiTest(PostApiTestBase):
    def test_anonymous_post_is_rejected(self):
        res = self.upload()
        self.assertEqual(res.status_code, 401)
        self.assertEqual(Post.objects.count(), 0)

    def test_token_post_multipart_creates_post(self):
        self.auth()
        res = self.upload()
        self.assertEqual(res.status_code, 201, res.content)
        post = Post.objects.get()
        self.assertEqual(post.title, '우주이야기')
        self.assertTrue(post.image.name.startswith('blog_image/'))
        self.assertTrue(post.thumbnail.name.startswith('blog_thumb/'))
        self.assertIsNotNone(post.published_date)

    def test_jwt_keyword_also_accepted(self):
        self.auth(keyword='JWT')
        self.assertEqual(self.upload().status_code, 201)

    def test_basic_auth_accepted(self):
        self.client.login(username='writer', password='pw-12345!')
        self.assertEqual(self.upload().status_code, 201)

    def test_author_is_taken_from_token_not_from_request(self):
        """편의기능 ③ : author=다른사람 으로 보내도 토큰의 사용자로 저장"""
        self.auth()
        res = self.upload(author=self.other.pk)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['author'], self.user.pk)
        self.assertEqual(Post.objects.get().author, self.user)

    def test_published_date_from_client_is_kept(self):
        self.auth()
        res = self.upload(published_date='2024-10-07T18:05:00+09:00')
        self.assertEqual(res.json()['published_date'], '2024-10-07T18:05:00+09:00')

    def test_title_is_required(self):
        self.auth()
        res = self.upload(title='')
        self.assertEqual(res.status_code, 400)
        self.assertIn('title', res.json())

    def test_png_with_alpha_is_accepted_and_thumbnail_is_jpeg(self):
        self.auth()
        res = self.upload(image=make_upload('alpha.png', fmt='PNG', content_type='image/png'))
        self.assertEqual(res.status_code, 201, res.content)
        self.assertTrue(Post.objects.get().thumbnail.name.endswith('_thumb.jpg'))


class UploadValidationTest(PostApiTestBase):
    """편의기능 ③ : 업로드 파일 검증"""

    def setUp(self):
        super().setUp()
        self.auth()

    def test_non_image_with_jpg_extension_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake = SimpleUploadedFile('fake.jpg', b'<?php echo "hack"; ?>', content_type='image/jpeg')
        res = self.upload(image=fake)
        self.assertEqual(res.status_code, 400)
        self.assertIn('image', res.json())

    def test_disallowed_extension_is_rejected(self):
        res = self.upload(image=make_upload('photo.bmp', fmt='BMP', content_type='image/bmp'))
        self.assertEqual(res.status_code, 400)

    @override_settings(PHOTO_MAX_UPLOAD_BYTES=1024)
    def test_too_large_file_is_rejected(self):
        res = self.upload()
        self.assertEqual(res.status_code, 400)
        self.assertIn('MB', str(res.json()['image']))

    @override_settings(PHOTO_ALLOWED_FORMATS=('PNG',))
    def test_disallowed_format_is_rejected(self):
        res = self.upload()
        self.assertEqual(res.status_code, 400)

    @override_settings(PHOTO_MAX_PIXELS=100)
    def test_too_many_pixels_is_rejected(self):
        res = self.upload()
        self.assertEqual(res.status_code, 400)


class OwnershipTest(PostApiTestBase):
    """편의기능 ③ : 수정/삭제는 작성자 본인만"""

    def setUp(self):
        super().setUp()
        self.post = self.create_post()
        self.url = '%s%d/' % (API, self.post.pk)

    def test_owner_can_patch(self):
        self.auth()
        res = self.client.patch(self.url, {'title': '수정됨'}, format='multipart')
        self.assertEqual(res.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, '수정됨')

    def test_other_user_cannot_patch(self):
        self.auth(self.other_token)
        res = self.client.patch(self.url, {'title': 'hacked'}, format='multipart')
        self.assertEqual(res.status_code, 403)

    def test_other_user_cannot_delete(self):
        self.auth(self.other_token)
        self.assertEqual(self.client.delete(self.url).status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_owner_can_delete(self):
        self.auth()
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertFalse(Post.objects.exists())

    def test_staff_can_edit_any_post(self):
        self.other.is_staff = True
        self.other.save()
        self.auth(self.other_token)
        res = self.client.patch(self.url, {'title': 'by admin'}, format='multipart')
        self.assertEqual(res.status_code, 200)

    def test_perform_update_guard_blocks_non_owner(self):
        """권한 클래스를 우회하더라도 perform_update 에서 한 번 더 막는지 확인"""
        from rest_framework.exceptions import PermissionDenied
        from blog.views import BlogImages
        view = BlogImages()
        view.request = type('R', (), {'user': self.other})()
        serializer = type('S', (), {'instance': self.post, 'save': lambda self: None})()
        with self.assertRaises(PermissionDenied):
            view.perform_update(serializer)


class TokenAuthEndpointTest(PostApiTestBase):
    def test_obtain_token_with_id_password(self):
        res = self.client.post('/api-token-auth/', {'username': 'writer', 'password': 'pw-12345!'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['token'], self.token.key)

    def test_wrong_password_gives_400(self):
        res = self.client.post('/api-token-auth/', {'username': 'writer', 'password': 'nope'})
        self.assertEqual(res.status_code, 400)
