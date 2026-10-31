"""
简单的 WebSocket 测试
"""

from flask import Flask
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

@sock.route('/echo')
def echo(ws):
    while True:
        data = ws.receive()
        if data is None:
            break
        ws.send(data)

if __name__ == '__main__':
    print("启动简单的 WebSocket 服务器...")
    print("测试命令: wscat -c ws://localhost:5000/echo")
    app.run(port=5000, debug=True)
