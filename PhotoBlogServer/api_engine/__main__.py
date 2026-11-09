import argparse
import os
import sys

from .engine import PhotoBlogApiEngine


def main(argv=None):
    parser = argparse.ArgumentParser(description='PhotoBlog REST API 검증 엔진')
    parser.add_argument('base_url', nargs='?', default='http://127.0.0.1:8000')
    parser.add_argument('--token', default=os.environ.get('API_TOKEN'))
    parser.add_argument('--user', default=os.environ.get('API_USER'))
    parser.add_argument('--password', default=os.environ.get('API_PASSWORD'))
    parser.add_argument('--image', help='업로드 검증에 사용할 이미지 파일 경로')
    args = parser.parse_args(argv)

    engine = PhotoBlogApiEngine(args.base_url, token=args.token)
    if not engine.token and args.user and args.password:
        engine.obtain_token(args.user, args.password)
    sample = None
    if args.image:
        with open(args.image, 'rb') as f:
            sample = f.read()
    report = engine.run(sample_image=sample)
    print(report.render())
    return 0 if report.ok else 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
