"""Message Body(JSON Array) 검증기 단위 테스트"""
import json
import unittest

from api_engine.validator import (ValidationReport, is_http_url, is_iso8601, validate_post,
                                  validate_post_list)

# 강의자료(1) p.9 의 실제 응답 예시
LECTURE_BODY = (
    '[{"author":1,"title":"서진이","text":"서진이가 그림을 그린다","created_date":"2024-10-07T18:05:00+09:00",'
    '"published_date":"2024-10-07T18:05:00+09:00","image":"http://10.0.2.2:8000/media/blog_image/2024/10/07/IMG_4352.jpeg"},'
    '{"author":1,"title":"우주이야기","text":"제임스웹이 보내온 성운","created_date":"2024-10-08T09:19:28.458758+09:00",'
    '"published_date":"2024-10-08T09:19:28.462477+09:00","image":"http://10.0.2.2:8000/media/%E1%84%89.jpg"}]'
)


def good_post(**overrides):
    post = json.loads(LECTURE_BODY)[0]
    post.update(overrides)
    return post


class HelperTest(unittest.TestCase):
    def test_iso8601(self):
        self.assertTrue(is_iso8601('2024-10-07T18:05:00+09:00'))
        self.assertTrue(is_iso8601('2024-10-08T09:19:28.458758Z'))
        self.assertFalse(is_iso8601('2024-10-07 18:05'))
        self.assertFalse(is_iso8601(None))

    def test_http_url(self):
        self.assertTrue(is_http_url('https://vyjsjs.pythonanywhere.com/media/a.jpg'))
        self.assertFalse(is_http_url('/media/a.jpg'))
        self.assertFalse(is_http_url(3))


class ValidatePostListTest(unittest.TestCase):
    def test_lecture_example_is_valid(self):
        report = validate_post_list(LECTURE_BODY.encode('utf-8'))
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(report.count, 2)
        self.assertIn('2건', report.summary())

    def test_accepts_python_list(self):
        self.assertTrue(validate_post_list([good_post()]).ok)

    def test_empty_array_is_valid(self):
        self.assertTrue(validate_post_list('[]').ok)

    def test_invalid_json(self):
        report = validate_post_list('[{"author":1,')
        self.assertFalse(report.ok)
        self.assertIn('JSON 파싱 실패', report.errors[0])

    def test_object_instead_of_array(self):
        report = validate_post_list('{"count": 2, "results": []}')
        self.assertIn('JSON Array 가 아닙니다', report.errors[0])

    def test_item_not_object(self):
        self.assertIn('JSON Object 가 아닙니다', validate_post_list('[1]').errors[0])

    def test_failure_summary_lists_errors(self):
        report = validate_post_list([good_post(image='/media/a.jpg')])
        self.assertIn('FAIL', report.summary())
        self.assertIn('[0]', report.summary())


class ValidatePostTest(unittest.TestCase):
    def test_missing_required_field(self):
        post = good_post()
        del post['title']
        self.assertIn("필수 필드 'title' 누락", validate_post(post)[0])

    def test_wrong_type(self):
        self.assertIn("'author' 타입 오류", validate_post(good_post(author='1'))[0])

    def test_bool_is_not_int(self):
        self.assertTrue(validate_post(good_post(author=True)))

    def test_optional_field_type(self):
        self.assertIn("'id' 타입 오류", validate_post(good_post(id='7'))[0])

    def test_null_published_date_ok(self):
        self.assertEqual(validate_post(good_post(published_date=None)), [])

    def test_blank_title(self):
        self.assertIn('비어 있습니다', validate_post(good_post(title='  '))[0])

    def test_too_long_title(self):
        self.assertIn('200자', validate_post(good_post(title='a' * 201))[0])

    def test_bad_date(self):
        self.assertIn('ISO 8601', validate_post(good_post(created_date='어제'))[0])

    def test_relative_image_url(self):
        self.assertIn('절대 URL', validate_post(good_post(thumbnail='/media/t.jpg'))[0])


class ReportTest(unittest.TestCase):
    def test_add_and_ok(self):
        report = ValidationReport()
        self.assertTrue(report.ok)
        report.add('x', 'bad')
        self.assertFalse(report.ok)
        self.assertEqual(report.errors, ['x: bad'])


if __name__ == '__main__':
    unittest.main()
