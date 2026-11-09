import logging

from django.conf import settings
from django.db import models
from django.utils import timezone

from .imaging import make_thumbnail, thumbnail_name
from .validators import validate_photo

logger = logging.getLogger(__name__)


class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    text = models.TextField()
    created_date = models.DateTimeField(default=timezone.now)
    published_date = models.DateTimeField(blank=True, null=True)
    image = models.ImageField(upload_to='blog_image/%Y/%m/%d/',
                              default='blog_image/default_error.png',
                              validators=[validate_photo])
    # 편의기능 ① : 서버가 자동 생성하는 목록용 썸네일
    thumbnail = models.ImageField(upload_to='blog_thumb/%Y/%m/%d/', blank=True,
                                  editable=False)
    # 편의기능 ① : 증분 동기화(since / ETag) 판단 기준
    updated_date = models.DateTimeField(auto_now=True, db_index=True)

    # ---- 공통평가 02 : YOLOv5 Edge Client 가 보내는 침입 감지 정보 ----
    SOURCE_MANUAL = 'manual'
    SOURCE_EDGE = 'edge'
    SOURCE_CHOICES = [(SOURCE_MANUAL, '직접 게시'), (SOURCE_EDGE, 'YOLO 감지')]
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_MANUAL,
                              db_index=True)
    # 검출된 객체 목록 : [{"label": "person", "confidence": 0.91, "box": [x1, y1, x2, y2]}, ...]
    detections = models.JSONField(default=list, blank=True)
    # 검출 클래스 이름을 ','로 감싼 문자열 (",person,cell phone,") → SQLite 에서도 클래스 필터 가능
    labels = models.CharField(max_length=500, blank=True, default='', db_index=True)
    device = models.CharField(max_length=64, blank=True, default='')   # Edge 장치 이름
    # 편의기능 ① : 관리자 확인(Ack) 처리
    acknowledged = models.BooleanField(default=False, db_index=True)
    acknowledged_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-published_date', '-id']

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._loaded_image_name = instance.image.name if instance.image else ''
        return instance

    def _image_changed(self):
        return self.image.name != getattr(self, '_loaded_image_name', None)

    # ---- 감지 정보 도우미 ----
    def label_list(self):
        return [x for x in self.labels.split(',') if x]

    def sync_labels(self):
        """detections(JSON) → labels 문자열/source 동기화"""
        names = []
        for det in self.detections or []:
            name = str(det.get('label', '')).strip() if isinstance(det, dict) else ''
            if name and name not in names:
                names.append(name)
        self.labels = (',' + ','.join(names) + ',') if names else ''
        if names or self.device:
            self.source = self.SOURCE_EDGE

    def max_confidence(self):
        confs = [d.get('confidence') for d in (self.detections or [])
                 if isinstance(d, dict) and isinstance(d.get('confidence'), (int, float))]
        return max(confs) if confs else None

    def save(self, *args, **kwargs):
        self.sync_labels()
        if self.image and (not self.thumbnail or self._image_changed()):
            try:
                thumb = make_thumbnail(self.image)
                self.thumbnail.save(thumbnail_name(self.image.name), thumb, save=False)
            except (OSError, ValueError) as exc:  # 썸네일 실패가 게시를 막지는 않음
                logger.warning('thumbnail generation failed for %s: %s', self.image.name, exc)
                self.thumbnail = None
        super().save(*args, **kwargs)
        self._loaded_image_name = self.image.name if self.image else ''

    def publish(self):
        self.published_date = timezone.now()
        self.save()

    def __str__(self):
        return self.title
