"""공통평가02 : 침입 감지 필터 / 통계 계산 (웹 대시보드, REST API, Android 앱 공용)"""
from collections import Counter, OrderedDict
from datetime import datetime, timedelta

from django.utils import timezone


def filter_posts(qs, params):
    """?label= ?source= ?date= ?unacked= 공통 필터. 잘못된 값이면 ValueError"""
    label = (params.get('label') or '').strip()
    if label:
        qs = qs.filter(labels__contains=',%s,' % label)
    source = (params.get('source') or '').strip()
    if source:
        if source not in ('edge', 'manual'):
            raise ValueError("source 는 'edge' 또는 'manual' 이어야 합니다.")
        qs = qs.filter(source=source)
    date = (params.get('date') or '').strip()
    if date:
        try:
            day = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError('date 는 YYYY-MM-DD 형식이어야 합니다.')
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(day, datetime.min.time()), tz)
        qs = qs.filter(published_date__gte=start, published_date__lt=start + timedelta(days=1))
    if params.get('unacked') in ('1', 'true'):
        qs = qs.filter(source='edge', acknowledged=False)
    return qs


def detection_stats(queryset, now=None):
    now = timezone.localtime(now or timezone.now())
    edge = list(queryset.filter(source='edge')
                .values('id', 'labels', 'device', 'published_date', 'created_date', 'acknowledged'))
    today = now.date()
    label_counter = Counter()
    hour_counts = [0] * 24
    day_counts = OrderedDict(((today - timedelta(days=i)).isoformat(), 0) for i in range(6, -1, -1))
    devices = {}
    last = None
    for row in edge:
        when = row['published_date'] or row['created_date']
        local = timezone.localtime(when) if when else None
        for name in [x for x in row['labels'].split(',') if x]:
            label_counter[name] += 1
        if local:
            if now - local <= timedelta(hours=24) and local <= now:
                hour_counts[local.hour] += 1
            key = local.date().isoformat()
            if key in day_counts:
                day_counts[key] += 1
            if last is None or local > last:
                last = local
        dev = row['device'] or '(unknown)'
        info = devices.setdefault(dev, {'device': dev, 'count': 0, 'last': None})
        info['count'] += 1
        if local and (info['last'] is None or local > info['last']):
            info['last'] = local
    device_list = sorted(devices.values(), key=lambda d: d['last'] or now - timedelta(days=9999), reverse=True)
    for d in device_list:
        d['online'] = bool(d['last'] and now - d['last'] <= timedelta(minutes=10))
        d['last'] = d['last'].isoformat() if d['last'] else None
    return {
        'total': queryset.count(),
        'edge_total': len(edge),
        'today': sum(1 for r in edge if (r['published_date'] or r['created_date'])
                     and timezone.localtime(r['published_date'] or r['created_date']).date() == today),
        'unacked': sum(1 for r in edge if not r['acknowledged']),
        'last_detected': last.isoformat() if last else None,
        'top_label': label_counter.most_common(1)[0][0] if label_counter else None,
        'by_label': [{'label': k, 'count': v} for k, v in label_counter.most_common()],
        'by_hour': [{'hour': h, 'count': hour_counts[h]} for h in range(24)],
        'by_hour_counts': hour_counts,
        'by_day': [{'date': k, 'count': v} for k, v in day_counts.items()],
        'devices': device_list,
        'generated_at': now.isoformat(),
    }
