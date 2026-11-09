# edge_outbox

`detect.py --server https://vyjsjs.pythonanywhere.com` 로 실행했으나 Edge 장비(클라우드 작업 환경)에서
PythonAnywhere 로 접속할 수 없어 `changedetection.py` 가 보관한 감지 9건 (편의기능② 오프라인 큐).
각 감지는 `*.json`(title, text, created_date, detections, device) + `*.jpg`(박스가 그려진 감지 이미지) 한 쌍이다.

서버에 접속 가능한 곳(PythonAnywhere Bash 콘솔)에서 재전송 :

```bash
cd ~/photoblog-intruderdetection/YOLOv5
python changedetection.py --outbox edge_outbox --server https://vyjsjs.pythonanywhere.com --username yolo-edge --password <pw>
```
전송에 성공한 감지는 outbox 에서 삭제된다.
