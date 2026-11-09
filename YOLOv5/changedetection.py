"""
changedetection.py - YOLOv5 Edge Client -> PhotoBlogServer(Django) 침입 감지 전송 모듈

강의자료 Ch08 p.8~10 의 ChangeDetection 클래스를 기반으로 확장했다.

  [강의 기본 동작]
    - 서버 /api-token-auth/ 로 ID/PW 를 보내 토큰 발급 (p.8)
    - 클래스별 출현 상태를 '과거 0 -> 현재 1' 로 바뀌는 순간만 감지 (p.9)
    - 감지 이미지를 날짜별 폴더에 저장하고 'Authorization: JWT <token>' 헤더로
      /api_root/Post/ 에 title, text, created_date, published_date, image 를 POST (p.10)

  [편의 기능 ② : Edge 감지 신뢰성 강화]  (기획되지 않은 기능)
    1) 깜빡임 억제 : N 프레임 연속 검출되어야 '출현', M 프레임 연속 사라져야 '퇴장' (히스테리시스)
       -> 한 프레임 오검출, 순간 가림으로 인한 중복 게시 방지
    2) 클래스별 쿨다운 : 같은 클래스는 cooldown 초 안에 다시 전송하지 않음
    3) 관심 클래스(watch) / 최소 신뢰도 필터 : 예) person, cell phone 만 서버로 전송
    4) 검출 메타데이터 전송 : 클래스·신뢰도·바운딩박스(JSON)와 장치 이름(device)을 함께 전송
       -> 서버 대시보드/앱에서 클래스 필터, 통계, 확인(Ack) 처리에 사용
    5) 비동기 전송 + 오프라인 큐 : 전송은 별도 스레드에서 처리해 추론(FPS)이 멈추지 않고,
       서버 장애 시 outbox 폴더에 저장 후 지수 백오프로 자동 재전송 (재시작해도 유지)

설정은 detect.py 인자 또는 환경변수로 지정한다.
  PHOTOBLOG_HOST, PHOTOBLOG_USERNAME, PHOTOBLOG_PASSWORD, PHOTOBLOG_DEVICE
"""

import json
import os
import pathlib
import queue
import socket
import threading
import time
from datetime import datetime

import cv2
import requests


class ChangeDetection:
    result_prev = []
    HOST = os.environ.get("PHOTOBLOG_HOST", "http://127.0.0.1:8000")
    username = os.environ.get("PHOTOBLOG_USERNAME", "admin")
    password = os.environ.get("PHOTOBLOG_PASSWORD", "password")
    token = ""
    title = ""
    text = ""

    def __init__(
        self,
        names,
        host=None,
        username=None,
        password=None,
        device_name=None,
        watch=None,
        min_conf=0.0,
        min_frames=3,
        off_frames=5,
        cooldown=10.0,
        send_size=(640, 480),
        outbox="outbox",
        timeout=10,
        verbose=True,
    ):
        """names : YOLO 클래스 이름 (list 또는 {index: name} dict)."""
        self.names = names
        self.HOST = (host or self.HOST).rstrip("/")
        self.username = username or self.username
        self.password = password or self.password
        self.device_name = device_name or os.environ.get("PHOTOBLOG_DEVICE") or socket.gethostname()
        n = len(names)
        self.result_prev = [0 for i in range(n)]  # 강의자료 p.8 : 클래스별 직전 상태
        # ---- 편의기능 ② 설정 ----
        self.watch = None
        if watch:
            wanted = {w.strip().lower() for w in watch if str(w).strip()}
            self.watch = {i for i in range(n) if str(names[i]).lower() in wanted or str(i) in wanted}
        self.min_conf = float(min_conf)
        self.min_frames = max(1, int(min_frames))
        self.off_frames = max(1, int(off_frames))
        self.cooldown = float(cooldown)
        self.send_size = send_size
        self.timeout = timeout
        self.verbose = verbose
        self._seen_streak = [0] * n  # 연속 검출 프레임 수
        self._miss_streak = [0] * n  # 연속 미검출 프레임 수
        self._last_sent = [0.0] * n  # 클래스별 마지막 전송 시각 (쿨다운)
        self.stats = {"frames": 0, "events": 0, "sent": 0, "queued": 0, "failed": 0, "suppressed": 0}
        self.outbox = pathlib.Path(outbox)
        self.outbox.mkdir(parents=True, exist_ok=True)
        self._q = queue.Queue()
        self._stop = threading.Event()

        self.login()  # 강의자료 p.8 : 토큰 발급
        self._worker = threading.Thread(target=self._send_loop, name="photoblog-sender", daemon=True)
        self._worker.start()
        self._requeue_outbox()  # 이전 실행에서 못 보낸 감지 재전송

    # ------------------------------------------------------------------ 인증
    def login(self):
        """강의자료 p.8 : /api-token-auth/ 에 ID/PW 를 보내 토큰을 받는다. 실패해도 추론은 계속."""
        try:
            res = requests.post(
                self.HOST + "/api-token-auth/",
                {"username": self.username, "password": self.password},
                timeout=self.timeout,
            )
            res.raise_for_status()
            self.token = res.json()["token"]  # 토큰 저장
            self.log(f"login ok  host={self.HOST}  user={self.username}  device={self.device_name}")
            self.log(f"token = {self.token}")
            return True
        except (requests.RequestException, KeyError, ValueError) as e:
            self.token = ""
            self.log(f"login failed ({e}) -> 감지는 outbox 에 저장 후 서버 복구 시 재전송")
            return False

    # ------------------------------------------------------------------ 변화 감지
    def add(self, names, detected_current, save_dir, image, detections=None):
        """강의자료 p.9 : 클래스 출현 상태가 과거 0 -> 현재 1 로 바뀐 경우 서버로 전송.

        detected_current : 클래스별 0/1 리스트 (detect.py 에서 생성)
        detections       : [{'label', 'confidence', 'box'}] (편의기능 ② 메타데이터, 선택)
        """
        self.title = ""
        self.text = ""
        change_flag = 0  # 변화 감지 플래그
        self.stats["frames"] += 1
        detections = detections or []
        best_conf = {}
        for d in detections:
            best_conf[d["label"]] = max(best_conf.get(d["label"], 0.0), d.get("confidence", 1.0))

        now = time.time()
        stable = list(self.result_prev)
        i = 0
        while i < len(self.result_prev):
            current = detected_current[i]
            # 관심 클래스/최소 신뢰도 필터
            if current and self.watch is not None and i not in self.watch:
                current = 0
            if current and best_conf.get(names[i], 1.0) < self.min_conf:
                current = 0
            # 깜빡임 억제 (히스테리시스)
            if current:
                self._seen_streak[i] += 1
                self._miss_streak[i] = 0
                if self._seen_streak[i] >= self.min_frames:
                    stable[i] = 1
            else:
                self._miss_streak[i] += 1
                self._seen_streak[i] = 0
                if self._miss_streak[i] >= self.off_frames:
                    stable[i] = 0

            if self.result_prev[i] == 0 and stable[i] == 1:
                if now - self._last_sent[i] >= self.cooldown:
                    change_flag = 1
                    if not self.title:
                        self.title = names[i]
                    self.text += names[i] + ", "
                    self._last_sent[i] = now
                else:
                    self.stats["suppressed"] += 1
                    self.log(f"cooldown: {names[i]} ({now - self._last_sent[i]:.1f}s < {self.cooldown}s)")
            i += 1

        self.result_prev = stable[:]  # 객체 검출 상태 저장

        if change_flag == 1:
            # 현재 프레임에 함께 보이는 다른 객체도 본문에 기록
            others = [n for n in best_conf if n + ", " not in self.text]
            if others:
                self.text += "(함께 검출: " + ", ".join(others) + ")"
            self.send(save_dir, image, detections)

    # ------------------------------------------------------------------ 전송
    def send(self, save_dir, image, detections=None):
        """강의자료 p.10 : 이미지를 날짜별 폴더에 저장하고 서버에 게시물로 전송(비동기)."""
        now = datetime.now().astimezone()
        today = now
        save_path = pathlib.Path(os.getcwd()) / save_dir / "detected" / str(today.year) / str(today.month) / str(today.day)
        pathlib.Path(save_path).mkdir(parents=True, exist_ok=True)

        full_path = save_path / "{0}-{1}-{2}-{3}.jpg".format(today.hour, today.minute, today.second, today.microsecond)

        dst = cv2.resize(image, dsize=self.send_size, interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(full_path), dst)

        # 박스 좌표를 전송 이미지 크기에 맞게 변환
        h, w = image.shape[:2]
        sx, sy = self.send_size[0] / w, self.send_size[1] / h
        dets = []
        for d in detections or []:
            item = {"label": d["label"], "confidence": round(float(d.get("confidence", 0)), 4)}
            if d.get("box"):
                x1, y1, x2, y2 = d["box"]
                item["box"] = [round(x1 * sx, 1), round(y1 * sy, 1), round(x2 * sx, 1), round(y2 * sy, 1)]
            dets.append(item)

        data = {
            "title": self.title,
            "text": self.text,
            "created_date": now.isoformat(),
            "published_date": now.isoformat(),
            "detections": json.dumps(dets, ensure_ascii=False),
            "device": self.device_name,
        }
        self.stats["events"] += 1
        self.log(f"EVENT  {self.title!r}  {self.text!r}  -> {full_path.name}")
        self._q.put((data, str(full_path), 0))

    def _post(self, data, image_path):
        if not self.token and not self.login():
            raise requests.ConnectionError("no token")
        # 인증이 필요한 요청에 아래의 headers 를 붙임
        headers = {"Authorization": "JWT " + self.token, "Accept": "application/json"}
        with open(image_path, "rb") as f:
            file = {"image": f}
            res = requests.post(
                self.HOST + "/api_root/Post/", data=data, files=file, headers=headers, timeout=self.timeout
            )
        if res.status_code == 401:  # 토큰 만료/서버 DB 초기화 -> 재로그인 후 1회 재시도
            self.token = ""
            raise requests.ConnectionError("401 Unauthorized")
        if 400 <= res.status_code < 500:
            raise ValueError(f"rejected {res.status_code}: {res.text[:200]}")
        res.raise_for_status()
        return res

    def _send_loop(self):
        """전송 전용 스레드 : 실패 시 outbox 에 저장하고 지수 백오프(1,2,4..60초)로 재시도"""
        while not self._stop.is_set():
            try:
                data, image_path, attempt = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            while not self._stop.is_set():
                try:
                    res = self._post(data, image_path)
                    body = res.json()
                    self.stats["sent"] += 1
                    self.log(f"POST /api_root/Post/ -> {res.status_code}  id={body.get('id')}  labels={body.get('labels')}")
                    self._remove_outbox(image_path)
                    break
                except ValueError as e:  # 서버가 거부한 요청은 재시도해도 소용 없음
                    self.stats["failed"] += 1
                    self.log(f"send rejected: {e}")
                    self._remove_outbox(image_path)
                    break
                except requests.RequestException as e:
                    self.stats["queued"] += 1
                    delay = min(60, 2**attempt)
                    attempt += 1
                    self.log(f"send failed ({e}) -> outbox 저장, {delay}s 후 재시도 #{attempt}")
                    self._save_outbox(data, image_path)
                    self._stop.wait(delay)
            self._q.task_done()

    # ------------------------------------------------------------------ 오프라인 큐
    def _outbox_json(self, image_path):
        return self.outbox / (pathlib.Path(image_path).stem + ".json")

    def _save_outbox(self, data, image_path):
        p = self._outbox_json(image_path)
        if not p.exists():
            p.write_text(json.dumps({"data": data, "image": str(image_path)}, ensure_ascii=False), encoding="utf-8")

    def _remove_outbox(self, image_path):
        p = self._outbox_json(image_path)
        if p.exists():
            p.unlink()

    def _requeue_outbox(self):
        pending = sorted(self.outbox.glob("*.json"))
        for p in pending:
            try:
                item = json.loads(p.read_text(encoding="utf-8"))
                if os.path.exists(item["image"]):
                    self._q.put((item["data"], item["image"], 0))
                else:
                    p.unlink()
            except (ValueError, KeyError, OSError):
                p.unlink(missing_ok=True)
        if pending:
            self.log(f"outbox: 이전에 전송하지 못한 감지 {len(pending)}건 재전송")

    def close(self, wait=10.0):
        """남은 전송을 최대 wait 초 기다린 뒤 종료"""
        end = time.time() + wait
        while self._q.unfinished_tasks and time.time() < end:
            time.sleep(0.2)
        self._stop.set()
        self._worker.join(timeout=2)
        self.log("summary " + ", ".join(f"{k}={v}" for k, v in self.stats.items()))

    def log(self, msg):
        if self.verbose:
            print(f"[ChangeDetection] {msg}", flush=True)
