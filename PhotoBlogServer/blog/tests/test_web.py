"""웹 페이지(ch03) 테스트"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from blog.models import Post

from .helpers import TempMediaMixin, make_upload


class WebViewTest(TempMediaMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user('writer', password='pw-12345!')
        self.other = User.objects.create_user('other', password='pw-12345!')
        self.post = Post.objects.create(author=self.user, title='서진이', text='그림',
                                        published_date=timezone.now(), image=make_upload())

    def test_post_list_shows_title_and_thumbnail(self):
        res = self.client.get('/')
        self.assertContains(res, 'Photo blog')
        self.assertContains(res, '서진이')
        self.assertContains(res, self.post.thumbnail.url)

    def test_post_list_without_thumbnail_uses_image(self):
        Post.objects.filter(pk=self.post.pk).update(thumbnail='')
        res = self.client.get('/')
        self.assertContains(res, self.post.image.url)

    def test_post_list_empty(self):
        Post.objects.all().delete()
        self.assertContains(self.client.get('/'), '아직 게시물이 없습니다')

    def test_unpublished_post_hidden_from_list(self):
        Post.objects.create(author=self.user, title='draft', text='x', image=make_upload())
        self.assertNotContains(self.client.get('/'), 'draft')

    def test_post_detail(self):
        res = self.client.get('/post/%d/' % self.post.pk)
        self.assertContains(res, self.post.image.url)

    def test_post_detail_404(self):
        self.assertEqual(self.client.get('/post/9999/').status_code, 404)

    def test_new_requires_login(self):
        res = self.client.get('/post/new/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin/login/', res['Location'])

    def test_new_form_and_create(self):
        self.client.login(username='writer', password='pw-12345!')
        self.assertContains(self.client.get('/post/new/'), 'New post')
        res = self.client.post('/post/new/', {'title': '웹 작성', 'text': '본문',
                                              'image': make_upload()})
        post = Post.objects.get(title='웹 작성')
        self.assertRedirects(res, '/post/%d/' % post.pk)
        self.assertEqual(post.author, self.user)

    def test_new_invalid_form_rerenders(self):
        self.client.login(username='writer', password='pw-12345!')
        res = self.client.post('/post/new/', {'title': '', 'text': ''})
        self.assertEqual(res.status_code, 200)

    def test_edit_by_owner(self):
        self.client.login(username='writer', password='pw-12345!')
        self.assertContains(self.client.get('/post/%d/edit/' % self.post.pk), 'Edit post')
        res = self.client.post('/post/%d/edit/' % self.post.pk, {'title': '수정', 'text': '본문'})
        self.assertRedirects(res, '/post/%d/' % self.post.pk)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, '수정')

    def test_edit_invalid_form_rerenders(self):
        self.client.login(username='writer', password='pw-12345!')
        res = self.client.post('/post/%d/edit/' % self.post.pk, {'title': '', 'text': ''})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Edit post')

    def test_edit_by_other_user_forbidden(self):
        self.client.login(username='other', password='pw-12345!')
        res = self.client.get('/post/%d/edit/' % self.post.pk)
        self.assertEqual(res.status_code, 403)

    def test_js_test_page(self):
        self.assertContains(self.client.get('/js_test/'), 'Number guessing game')

    def test_header_shows_user_when_logged_in(self):
        self.client.login(username='writer', password='pw-12345!')
        self.assertContains(self.client.get('/'), 'writer')

    def test_admin_lists_posts(self):
        User.objects.create_superuser('admin', password='pw-12345!')
        self.client.login(username='admin', password='pw-12345!')
        self.assertContains(self.client.get('/admin/blog/post/'), '서진이')
