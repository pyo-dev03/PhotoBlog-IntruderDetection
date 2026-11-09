from rest_framework.authentication import TokenAuthentication


class JWTKeywordTokenAuthentication(TokenAuthentication):
    """'Authorization: JWT <key>' 헤더도 받는 토큰 인증 (ch03 curl 실습 호환).

    DRF 기본 TokenAuthentication 은 'Token <key>' 만 인식하므로 keyword 만 바꾼 클래스.
    실제 JWT 가 아니라 rest_framework.authtoken 의 토큰을 그대로 사용한다.
    """
    keyword = 'JWT'
