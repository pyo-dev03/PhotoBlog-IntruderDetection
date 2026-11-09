"""ch03-02 : Python을 이용한 Socket Server

클라이언트(curl)의 HTTP Request 를 확인하기 위한 소켓 서버
 - 실습 1: 클라이언트 요청을 그대로 "request" 폴더 하위에
           "년-월-일-시-분-초.bin" 파일명의 이진 파일로 저장
 - 실습 2: multipart/form-data 로 전송 받은 이미지 데이터를
           별도 이미지 파일로 저장 (request/ 폴더, 같은 타임스탬프 + 원본 파일명)
"""
import os
import re
import socket
from datetime import datetime


class SocketServer:
    def __init__(self):
        self.bufsize = 1024  # 버퍼 크기 설정
        base = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base, 'response.bin'), 'rb') as file:
            self.RESPONSE = file.read()  # 응답 파일 읽기

        self.DIR_PATH = os.path.join(base, 'request')
        self.createDir(self.DIR_PATH)

    def createDir(self, path):
        """디렉토리 생성"""
        try:
            if not os.path.exists(path):
                os.makedirs(path)
        except OSError:
            print("Error: Failed to create the directory.")

    # ------------------------------------------------------------------
    # 요청 수신
    # ------------------------------------------------------------------
    def recvRequest(self, clnt_sock):
        """HTTP 요청 전체(헤더 + Content-Length 만큼의 본문)를 수신"""
        data = b""
        # 1) 헤더 끝(\r\n\r\n)까지 수신
        while b"\r\n\r\n" not in data:
            chunk = clnt_sock.recv(self.bufsize)
            if not chunk:
                return data
            data += chunk

        header_bytes, _ = data.split(b"\r\n\r\n", 1)
        headers = self.parseHeaders(header_bytes)

        # curl 은 큰 파일 전송 시 "Expect: 100-continue" 를 보내고 서버 응답을 기다림
        if headers.get('expect', '').lower() == '100-continue':
            clnt_sock.sendall(b"HTTP/1.1 100 Continue\r\n\r\n")

        # 2) Content-Length 만큼 본문 수신
        length = int(headers.get('content-length', 0))
        total = len(header_bytes) + 4 + length
        while len(data) < total:
            chunk = clnt_sock.recv(self.bufsize)
            if not chunk:
                break
            data += chunk
        return data

    @staticmethod
    def parseHeaders(header_bytes):
        """헤더를 {소문자 이름: 값} 딕셔너리로 변환 (첫 줄은 Request Line)"""
        headers = {}
        for line in header_bytes.split(b"\r\n")[1:]:
            if b":" in line:
                name, value = line.split(b":", 1)
                headers[name.decode('latin-1').strip().lower()] = value.decode('latin-1').strip()
        return headers

    # ------------------------------------------------------------------
    # 실습 2: multipart/form-data 에서 이미지 추출
    # ------------------------------------------------------------------
    def saveMultipartImages(self, request, prefix):
        """multipart 본문을 boundary 로 나누고, 이미지 파트를 파일로 저장"""
        header_bytes, body = request.split(b"\r\n\r\n", 1)
        headers = self.parseHeaders(header_bytes)
        content_type = headers.get('content-type', '')
        if not content_type.startswith('multipart/form-data'):
            return []

        m = re.search(r'boundary="?([^";]+)"?', content_type)
        if not m:
            return []
        boundary = b"--" + m.group(1).encode('latin-1')

        saved = []
        # 각 파트: [boundary]\r\n[파트 헤더]\r\n\r\n[데이터]\r\n[다음 boundary]
        for part in body.split(boundary)[1:]:
            if part.startswith(b"--"):  # "--boundary--" : 멀티파트 끝
                break
            part = part[2:] if part.startswith(b"\r\n") else part  # boundary 뒤 CRLF 제거
            if b"\r\n\r\n" not in part:
                continue
            part_header, part_data = part.split(b"\r\n\r\n", 1)
            if part_data.endswith(b"\r\n"):  # 다음 boundary 앞 CRLF 제거
                part_data = part_data[:-2]

            part_header = part_header.decode('utf-8', errors='replace')
            disp = re.search(r'Content-Disposition:.*', part_header, re.IGNORECASE)
            ctype = re.search(r'Content-Type:\s*([^\r\n]+)', part_header, re.IGNORECASE)
            fname = re.search(r'filename="([^"]*)"', disp.group(0)) if disp else None
            name = re.search(r'\bname="([^"]*)"', disp.group(0)) if disp else None

            if name:  # 텍스트 필드도 확인용으로 출력
                if not fname:
                    print(f"  [field] {name.group(1)} = {part_data.decode('utf-8', errors='replace')}")

            is_image = (ctype and ctype.group(1).strip().lower().startswith('image/'))
            if fname and is_image:
                original = os.path.basename(fname.group(1)) or 'image'
                filename = f"{prefix}_{original}"
                path = os.path.join(self.DIR_PATH, filename)
                with open(path, 'wb') as f:
                    f.write(part_data)
                print(f"  [image] {original} ({ctype.group(1).strip()}, {len(part_data)} bytes) -> {path}")
                saved.append(path)
        return saved

    def run(self, ip, port):
        """서버 실행"""
        # 소켓 생성
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((ip, port))
        self.sock.listen(10)
        print("Start the socket server...")
        print("\"Ctrl+C\" for stopping the server!\r\n")

        try:
            while True:
                # 클라이언트의 요청 대기
                clnt_sock, req_addr = self.sock.accept()
                clnt_sock.settimeout(5.0)  # 타임아웃 설정 (5초)
                print("Request message...\r\n")

                response = b""
                # ---------------- 여기에 구현 ----------------
                try:
                    response = self.recvRequest(clnt_sock)
                except socket.timeout:
                    print("  (timeout: 수신된 데이터까지만 저장)")

                if response:
                    # 실습 1: 요청 원본을 "년-월-일-시-분-초.bin" 으로 저장
                    prefix = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
                    bin_path = os.path.join(self.DIR_PATH, prefix + ".bin")
                    with open(bin_path, 'wb') as f:
                        f.write(response)
                    print(f"  [raw]   {len(response)} bytes -> {bin_path}")
                    print(response.split(b"\r\n\r\n", 1)[0].decode('latin-1'))

                    # 실습 2: 멀티파트 이미지 저장
                    self.saveMultipartImages(response, prefix)
                # ----------------------------------------------

                # 응답 전송
                clnt_sock.sendall(self.RESPONSE)

                # 클라이언트 소켓 닫기
                clnt_sock.close()
        except KeyboardInterrupt:
            print("\r\nStop the server...")

        # 서버 소켓 닫기
        self.sock.close()


if __name__ == "__main__":
    server = SocketServer()
    server.run("127.0.0.1", 8000)
