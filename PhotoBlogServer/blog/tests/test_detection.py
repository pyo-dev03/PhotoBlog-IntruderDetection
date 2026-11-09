"""공통평가02 : YOLOv5 Edge Client 연동 API / 편의기능 ① 감지 대시보드 테스트"""
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authtoken.models import Token

from blog.models import Post

from .helpers import make_upload
from .test_api import API, PostApiTestBase

DETS = [{'label': 'person', 'confidence': 0.91, 'box': [10, 20, 110, 220]},
        {'label': 'cell phone', 'confidence': 0.55, 'box': [50, 60, 70, 90]}]


class EdgeUploadTest(PostApiTestBase):
    """강의자료 p.10 changedetection.send() 와 같은 형식의 요청"""

    def lecture_upload(self, **extra):
        now = timezone.now().isoformat()
        data = {'title': 'person', 'text': 'person, cell phone, ', 'created_date': now,
                'published_date': now, 'image': make_upload('0-4-19-953675.jpg')}
        data.update(extra)
        return self.client.post(API, data, format='multipart')

    def test_lecture_format_with_jwt_header(self):
        self.auth(keyword='JWT')                       # headers = {'Authorization': 'JWT ' + token}
        res = self.lecture_upload()
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()['source'], 'manual')  # detections 없이 보내면 일반 게시물

    def test_detections_as_json_string_in_multipart(self):
        self.auth(keyword='JWT')
        res = self.lecture_upload(detections=json.dumps(DETS), device='macbook-cam0')
        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertEqual(body['source'], 'edge')
        self.assertEqual(body['labels'], ['person', 'cell phone'])
        self.assertEqual(body['device'], 'macbook-cam0')
        self.assertAlmostEqual(body['max_confidence'], 0.91)
        self.assertFalse(body['acknowledged'])
        post = Post.objects.get(pk=body['id'])
        self.assertEqual(post.labels, ',person,cell phone,')
        self.assertEqual(post.author, self.user)

    def test_invalid_detections_rejected(self):
        self.auth()
        for bad in ('not json', '{"label": "x"}', json.dumps([{'label': ''}]),
                    json.dumps([{'label': 'a', 'confidence': 3}]),
                    json.dumps([{'label': 'a', 'box': [1, 2]}]),
                    json.dumps([{'label': 'a,b'}]),
                    json.dumps([{'label': 'p'}] * 101)):
            res = self.lecture_upload(detections=bad)
            self.assertEqual(res.status_code, 400, bad)
            self.assertIn('detections', res.json())

    def test_unauthenticated_edge_upload_rejected(self):
        self.assertEqual(self.lecture_upload(detections=json.dumps(DETS)).status_code, 401)

    def test_client_cannot_set_acknowledged_or_source(self):
        self.auth()
        res = self.lecture_upload(acknowledged='true', source='edge')
        self.assertFalse(res.json()['acknowledged'])
        self.assertEqual(res.json()['source'], 'manual')


class DetectionFilterAndStatsTest(PostApiTestBase):
    def setUp(self):
        super().setUp()
        self.p1 = self.create_post(title='person', detections=DETS, device='cam0')
        self.p2 = self.create_post(title='dog', detections=[{'label': 'dog', 'confidence': 0.7}], device='cam1')
        self.p3 = self.create_post(title='manual')

    def ids(self, res):
        return sorted(p['id'] for p in res.json())

    def test_label_filter_matches_whole_name(self):
        self.create_post(title='x', detections=[{'label': 'personal'}])
        res = self.client.get(API, {'label': 'person'})
        self.assertEqual(self.ids(res), [self.p1.id])
        self.assertEqual(self.ids(self.client.get(API, {'label': 'cell phone'})), [self.p1.id])

    def test_source_filter(self):
        self.assertEqual(self.ids(self.client.get(API, {'source': 'edge'})), sorted([self.p1.id, self.p2.id]))
        self.assertEqual(self.ids(self.client.get(API, {'source': 'manual'})), [self.p3.id])
        self.assertEqual(self.client.get(API, {'source': 'robot'}).status_code, 400)

    def test_date_filter(self):
        today = timezone.localdate().isoformat()
        self.assertEqual(len(self.client.get(API, {'date': today}).json()), 3)
        self.assertEqual(self.client.get(API, {'date': '2001-01-01'}).json(), [])
        self.assertEqual(self.client.get(API, {'date': '11/09'}).status_code, 400)

    def test_unacked_filter_and_ack_action(self):
        self.assertEqual(self.ids(self.client.get(API, {'unacked': '1'})), sorted([self.p1.id, self.p2.id]))
        self.auth()
        res = self.client.post('%s%d/ack/' % (API, self.p1.id))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['acknowledged'])
        self.assertIsNotNone(res.json()['acknowledged_at'])
        self.assertEqual(self.ids(self.client.get(API, {'unacked': '1'})), [self.p2.id])
        res = self.client.post('%s%d/ack/' % (API, self.p1.id), {'acknowledged': False}, format='json')
        self.assertFalse(res.json()['acknowledged'])

    def test_ack_requires_owner_or_staff(self):
        self.assertEqual(self.client.post('%s%d/ack/' % (API, self.p1.id)).status_code, 401)
        self.auth(self.other_token)
        self.assertEqual(self.client.post('%s%d/ack/' % (API, self.p1.id)).status_code, 403)
        admin = User.objects.create_user('boss', password='pw', is_staff=True)
        self.auth(Token.objects.create(user=admin))
        self.assertEqual(self.client.post('%s%d/ack/' % (API, self.p1.id)).status_code, 200)

    def test_stats(self):
        old = self.create_post(title='old', detections=[{'label': 'person'}], device='cam0')
        Post.objects.filter(pk=old.pk).update(published_date=timezone.now() - timedelta(days=3))
        s = self.client.get(API + 'stats/').json()
        self.assertEqual(s['total'], 4)
        self.assertEqual(s['edge_total'], 3)
        self.assertEqual(s['today'], 2)
        self.assertEqual(s['unacked'], 3)
        self.assertEqual(s['top_label'], 'person')
        self.assertEqual(s['by_label'][0], {'label': 'person', 'count': 2})
        self.assertEqual(sum(h['count'] for h in s['by_hour']), 2)
        self.assertEqual(len(s['by_day']), 7)
        self.assertEqual(sum(d['count'] for d in s['by_day']), 3)
        self.assertEqual({d['device'] for d in s['devices']}, {'cam0', 'cam1'})
        self.assertTrue(all(d['online'] for d in s['devices']))
        self.assertNotIn('Post', s)

    def test_stats_is_read_only(self):
        self.auth()
        self.assertEqual(self.client.post(API + 'stats/').status_code, 405)


class DashboardWebTest(PostApiTestBase):
    def setUp(self):
        super().setUp()
        self.post = self.create_post(title='person', detections=DETS, device='cam0')

    def test_dashboard_page(self):
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn('시간대별 감지', html)
        self.assertIn('cam0', html)
        self.assertIn('/api_root/Post/stats/', html)

    def test_list_page_filters_and_badges(self):
        self.create_post(title='manual-only')
        html = self.client.get('/', {'label': 'person'}).content.decode()
        self.assertIn('미확인', html)
        self.assertNotIn('manual-only', html)
        self.assertEqual(self.client.get('/', {'date': 'bad'}).status_code, 200)

    def test_detail_shows_detection_table(self):
        html = self.client.get('/post/%d/' % self.post.pk).content.decode()
        self.assertIn('cell phone', html)
        self.assertIn('91%', html)

    def test_web_ack(self):
        self.client.force_login(self.user)
        res = self.client.post('/post/%d/ack/' % self.post.pk, {'value': '1', 'next': '/dashboard/'})
        self.assertRedirects(res, '/dashboard/')
        self.post.refresh_from_db()
        self.assertTrue(self.post.acknowledged)
        # 외부 URL 로의 open redirect 방지
        res = self.client.post('/post/%d/ack/' % self.post.pk, {'value': '0', 'next': 'https://evil.example/'})
        self.assertRedirects(res, '/post/%d/' % self.post.pk, fetch_redirect_response=False)

    def test_web_ack_other_user_ignored(self):
        self.client.force_login(self.other)
        self.client.post('/post/%d/ack/' % self.post.pk, {'value': '1'})
        self.post.refresh_from_db()
        self.assertFalse(self.post.acknowledged)
