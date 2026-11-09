import json

from rest_framework import serializers

from .models import Post

MAX_DETECTIONS = 100


class DetectionsField(serializers.JSONField):
    """YOLO 검출 결과 목록.

    multipart/form-data 로 이미지와 함께 보낼 때는 중첩 JSON 을 보낼 수 없으므로
    JSON 문자열('[{"label": "person", ...}]')도 받아서 파싱한다.
    """

    def to_internal_value(self, data):
        if isinstance(data, (bytes, bytearray)):
            data = data.decode('utf-8')
        if isinstance(data, str):
            data = data.strip() or '[]'
            try:
                data = json.loads(data)
            except ValueError:
                raise serializers.ValidationError('JSON 배열 문자열이어야 합니다.')
        data = super().to_internal_value(data)
        return self._clean(data)

    @staticmethod
    def _clean(data):
        if not isinstance(data, list):
            raise serializers.ValidationError('검출 결과는 배열이어야 합니다.')
        if len(data) > MAX_DETECTIONS:
            raise serializers.ValidationError('검출 결과는 최대 %d개까지 보낼 수 있습니다.' % MAX_DETECTIONS)
        cleaned = []
        for i, det in enumerate(data):
            if not isinstance(det, dict):
                raise serializers.ValidationError('%d번째 항목이 객체가 아닙니다.' % i)
            label = str(det.get('label', '')).strip()
            if not label or len(label) > 50 or ',' in label:
                raise serializers.ValidationError('%d번째 항목의 label 이 올바르지 않습니다.' % i)
            item = {'label': label}
            conf = det.get('confidence')
            if conf is not None:
                try:
                    conf = float(conf)
                except (TypeError, ValueError):
                    raise serializers.ValidationError('%d번째 항목의 confidence 는 숫자여야 합니다.' % i)
                if not 0.0 <= conf <= 1.0:
                    raise serializers.ValidationError('%d번째 항목의 confidence 는 0~1 사이여야 합니다.' % i)
                item['confidence'] = round(conf, 4)
            box = det.get('box')
            if box is not None:
                if (not isinstance(box, (list, tuple)) or len(box) != 4
                        or not all(isinstance(v, (int, float)) for v in box)):
                    raise serializers.ValidationError('%d번째 항목의 box 는 [x1, y1, x2, y2] 이어야 합니다.' % i)
                item['box'] = [round(float(v), 1) for v in box]
            cleaned.append(item)
        return cleaned


class PostSerializer(serializers.ModelSerializer):
    # 편의기능 ③(공통평가01) : 작성자는 클라이언트가 보낸 값이 아니라 인증된 사용자(토큰)로 서버가 지정
    author = serializers.PrimaryKeyRelatedField(read_only=True)
    author_name = serializers.CharField(source='author.username', read_only=True)
    thumbnail = serializers.ImageField(read_only=True)
    # 공통평가02 : YOLOv5 침입 감지 정보
    detections = DetectionsField(required=False)
    labels = serializers.ListField(source='label_list', child=serializers.CharField(), read_only=True)
    max_confidence = serializers.FloatField(read_only=True)

    class Meta:
        model = Post
        # 강의자료 p.9 의 필드 순서(author, title, text, created_date, published_date, image) 유지
        fields = ('author', 'title', 'text', 'created_date', 'published_date', 'image',
                  'id', 'author_name', 'thumbnail', 'updated_date',
                  'source', 'device', 'detections', 'labels', 'max_confidence',
                  'acknowledged', 'acknowledged_at')
        read_only_fields = ('id', 'updated_date', 'source', 'acknowledged', 'acknowledged_at')
        extra_kwargs = {'device': {'required': False}}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # 썸네일이 없는 과거 게시물은 원본 URL 로 대체 → 클라이언트는 항상 thumbnail 사용 가능
        if not data.get('thumbnail'):
            data['thumbnail'] = data.get('image')
        return data
