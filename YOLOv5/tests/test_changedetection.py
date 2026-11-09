"""changedetection.py 단위 테스트 (torch 없이 실행 가능)

    python -m pytest tests/test_changedetection.py -q
"""

import json
import time

import numpy as np
import pytest
import requests

import changedetection
from changedetection import ChangeDetection

NAMES = {0: "person", 1: "bicycle", 2: "car", 3: "cell phone"}


class FakeResponse:
    def __init__(self, status=201, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeServer:
    """requests.post 대체 : 토큰 발급과 게시물 생성을 기록"""

    def __init__(self):
        self.posts = []
        self.down = False

    def post(self, url, data=None, files=None, headers=None, timeout=None):
        if self.down:
            raise requests.ConnectionError("server down")
        if url.endswith("/api-token-auth/"):
            return FakeResponse(200, {"token": "tok123"})
        assert headers["Authorization"] == "JWT tok123"  # 강의자료 p.10 헤더 형식
        files["image"].read()
        self.posts.append(data)
        return FakeResponse(201, {"id": len(self.posts), "labels": [d["label"] for d in json.loads(data["detections"])]})


@pytest.fixture
def server(monkeypatch):
    s = FakeServer()
    monkeypatch.setattr(changedetection.requests, "post", s.post)
    return s


def make(tmp_path, monkeypatch, **kw):
    monkeypatch.chdir(tmp_path)
    kw.setdefault("min_frames", 1)
    kw.setdefault("off_frames", 1)
    kw.setdefault("cooldown", 0)
    return ChangeDetection(NAMES, outbox=str(tmp_path / "outbox"), verbose=False, **kw)


def frame(*classes):
    detected = [0] * len(NAMES)
    dets = []
    for c in classes:
        detected[c] = 1
        dets.append({"label": NAMES[c], "confidence": 0.9, "box": [0, 0, 64, 48]})
    return detected, dets


IMG = np.zeros((480, 640, 3), dtype=np.uint8)


def feed(cd, *frames):
    for classes in frames:
        detected, dets = frame(*classes)
        cd.add(NAMES, detected, "runs", IMG, dets)
    cd.close(wait=5)


def test_login_and_lecture_change_rule(tmp_path, monkeypatch, server):
    cd = make(tmp_path, monkeypatch)
    assert cd.token == "tok123"
    feed(cd, [], [0], [0], [0, 3], [], [0])  # 0->1 변화에서만 전송
    titles = [p["title"] for p in server.posts]
    assert titles == ["person", "cell phone", "person"]
    first = server.posts[0]
    assert first["text"].startswith("person, ")
    assert set(first) >= {"title", "text", "created_date", "published_date", "detections", "device"}
    assert (tmp_path / "runs" / "detected").exists()  # 강의자료 p.10 저장 경로


def test_flicker_suppression(tmp_path, monkeypatch, server):
    cd = make(tmp_path, monkeypatch, min_frames=3, off_frames=3)
    feed(cd, [0], [], [0], [0], [], [0], [0], [0], [0], [], [0], [0])
    # 1프레임 오검출, 1프레임 가림은 무시 -> 1번만 전송
    assert [p["title"] for p in server.posts] == ["person"]


def test_cooldown(tmp_path, monkeypatch, server):
    cd = make(tmp_path, monkeypatch, cooldown=60)
    feed(cd, [0], [], [0], [], [0])
    assert len(server.posts) == 1
    assert cd.stats["suppressed"] == 2


def test_watch_classes_and_min_conf(tmp_path, monkeypatch, server):
    cd = make(tmp_path, monkeypatch, watch=["person"], min_conf=0.5)
    detected, dets = frame(0)
    dets[0]["confidence"] = 0.3
    cd.add(NAMES, detected, "runs", IMG, dets)  # 신뢰도 부족
    cd.add(NAMES, *frame()[:1], "runs", IMG, [])
    for classes in ([2], [2, 0]):  # car 는 관심 클래스 아님
        cd.add(NAMES, *frame(*classes)[:1], "runs", IMG, frame(*classes)[1])
    cd.close(wait=5)
    assert [p["title"] for p in server.posts] == ["person"]


def test_box_scaled_to_sent_image(tmp_path, monkeypatch, server):
    cd = make(tmp_path, monkeypatch, send_size=(320, 240))
    feed(cd, [0])
    det = json.loads(server.posts[0]["detections"])[0]
    assert det["box"] == [0.0, 0.0, 32.0, 24.0]


def test_offline_queue_and_retry(tmp_path, monkeypatch, server):
    server.down = True
    cd = make(tmp_path, monkeypatch)
    assert cd.token == ""
    detected, dets = frame(0)
    cd.add(NAMES, detected, "runs", IMG, dets)
    deadline = time.time() + 3
    while not list((tmp_path / "outbox").glob("*.json")) and time.time() < deadline:
        time.sleep(0.05)
    assert len(list((tmp_path / "outbox").glob("*.json"))) == 1  # 장애 중 outbox 에 보관
    server.down = False  # 서버 복구 -> 백오프 후 자동 재전송
    deadline = time.time() + 6
    while not server.posts and time.time() < deadline:
        time.sleep(0.1)
    cd.close(wait=2)
    assert len(server.posts) == 1
    assert not list((tmp_path / "outbox").glob("*.json"))


def test_outbox_resent_on_restart(tmp_path, monkeypatch, server):
    server.down = True
    cd = make(tmp_path, monkeypatch)
    feed(cd, [0])
    cd._stop.set()
    assert len(list((tmp_path / "outbox").glob("*.json"))) == 1
    server.down = False
    cd2 = make(tmp_path, monkeypatch)  # 재시작 시 outbox 재전송
    cd2.close(wait=5)
    assert len(server.posts) == 1
