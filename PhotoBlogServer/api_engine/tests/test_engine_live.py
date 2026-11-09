"""검증 엔진 통합 테스트 : 실제 Django 서버(LiveServer)에 소켓으로 접속해 시나리오 수행"""
import io
import shutil
import tempfile
from contextlib import redirect_stdout
from unittest import mock

from django.contrib.auth.models import User
from django.test import LiveServerTestCase, SimpleTestCase, override_settings
from rest_framework.authtoken.models import Token

from api_engine import PhotoBlogApiEngine
from api_engine.__main__ import main
from api_engine.engine import EngineReport
from api_engine.http_message import HttpResponse
from blog.tests.helpers import make_image_bytes

MEDIA = tempfile.mkdtemp(prefix='photoblog-engine-media-')


@override_settings(MEDIA_ROOT=MEDIA)
class EngineLiveServerTest(LiveServerTestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user('engine', password='pw-12345!')
        self.token = Token.objects.create(user=self.user).key
        self.image = make_image_bytes()

    def test_full_scenario_with_token_passes(self):
        report = PhotoBlogApiEngine(self.live_server_url, token=self.token).run(self.image)
        self.assertTrue(report.ok, report.render())
        names = [r.name for r in report.results]
        self.assertIn('If-None-Match → 304 Not Modified', names)
        self.assertIn('author 위조 무시(서버가 지정)', names)

    def test_anonymous_scenario_skips_upload(self):
        report = PhotoBlogApiEngine(self.live_server_url).run(self.image)
        self.assertTrue(report.ok, report.render())
        self.assertNotIn('토큰 POST → 201 Created', [r.name for r in report.results])

    def test_upload_failure_is_reported(self):
        report = PhotoBlogApiEngine(self.live_server_url, token=self.token).run(b'not an image')
        failed = [r.name for r in report.results if not r.passed]
        self.assertEqual(failed, ['토큰 POST → 201 Created'])

    def test_get_only_scenario(self):
        report = PhotoBlogApiEngine(self.live_server_url).run()
        self.assertTrue(report.ok)
        self.assertIn('결과:', report.render())

    def test_obtain_token(self):
        engine = PhotoBlogApiEngine(self.live_server_url)
        self.assertEqual(engine.obtain_token('engine', 'pw-12345!'), self.token)

    def test_obtain_token_wrong_password(self):
        with self.assertRaises(PermissionError):
            PhotoBlogApiEngine(self.live_server_url).obtain_token('engine', 'wrong')

    def test_cli_with_user_password_and_image(self):
        path = tempfile.mktemp(suffix='.jpg', dir=MEDIA)
        with open(path, 'wb') as f:
            f.write(self.image)
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([self.live_server_url, '--user', 'engine', '--password', 'pw-12345!',
                         '--image', path])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn('OK', out.getvalue())


class EngineUnitTest(SimpleTestCase):
    def test_rejects_bad_url(self):
        with self.assertRaises(ValueError):
            PhotoBlogApiEngine('ftp://example.com')

    def test_default_ports(self):
        self.assertEqual(PhotoBlogApiEngine('https://vyjsjs.pythonanywhere.com').port, 443)
        self.assertEqual(PhotoBlogApiEngine('http://example.com').port, 80)

    def test_https_wraps_socket_with_tls(self):
        engine = PhotoBlogApiEngine('https://example.com')
        fake_sock = mock.MagicMock()
        fake_sock.recv.side_effect = [b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n[]', b'']
        ctx = mock.MagicMock()
        ctx.wrap_socket.return_value = fake_sock
        with mock.patch('socket.create_connection', return_value=mock.MagicMock()), \
                mock.patch('ssl.create_default_context', return_value=ctx):
            res = engine.send_raw(b'GET / HTTP/1.1\r\n\r\n')
        ctx.wrap_socket.assert_called_once()
        self.assertEqual(res.body, b'[]')

    def test_failed_report_and_cli_exit_code(self):
        failing = HttpResponse('HTTP/1.1', 500, 'Server Error', {}, b'oops')
        with mock.patch.object(PhotoBlogApiEngine, 'get_posts', return_value=failing):
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(['http://127.0.0.1:1'])
        self.assertEqual(code, 1)
        self.assertIn('[FAIL]', out.getvalue())
        self.assertIn('FAILED', out.getvalue())

    def test_report_ok_property(self):
        report = EngineReport('http://x')
        report.add('a', True)
        self.assertTrue(report.ok)
        report.add('b', False, 'why')
        self.assertFalse(report.ok)
        self.assertIn('[FAIL] b - why', report.render())
