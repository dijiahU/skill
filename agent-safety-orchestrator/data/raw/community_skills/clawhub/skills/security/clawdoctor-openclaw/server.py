#!/usr/bin/env python3
"""
ClawDoctor API Server
提供 HTTP API 供 Dashboard 调用
"""

import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import threading
import time

# 导入 ClawDoctor 核心
import sys
sys.path.insert(0, str(Path(__file__).parent))
from clawdoctor import ClawDoctor, OpenClawMonitor, OpenClawFixer, SecurityScanner

# 全局实例
doctor = ClawDoctor()
monitor = OpenClawMonitor()
fixer = OpenClawFixer()
scanner = SecurityScanner()

# 数据存储
logs_data = []
max_logs = 100

class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 静默日志
        pass
    
    def do_GET(self):
        """处理 GET 请求"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        path = self.path
        
        if path == '/api/status':
            # 获取当前状态
            result = monitor.full_check()
            self.wfile.write(json.dumps(result).encode())
            
        elif path == '/api/logs':
            # 获取日志数据
            self.wfile.write(json.dumps({'data': logs_data}).encode())
            
        elif path == '/api/check':
            # 完整检查
            result = monitor.full_check()
            self._add_log(result)
            self.wfile.write(json.dumps(result).encode())
            
        elif path == '/api/scan':
            # 安全扫描
            result = scanner.full_scan()
            self.wfile.write(json.dumps({'risks': result}).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """处理 POST 请求"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        path = self.path
        
        if path == '/api/fix':
            # 一键修复
            result = fixer.fix_all()
            self.wfile.write(json.dumps(result).encode())
            
        elif path == '/api/fix/gateway':
            # 修复 Gateway
            result = fixer.fix_gateway()
            self.wfile.write(json.dumps({'fixes': result}).encode())
            
        elif path == '/api/fix/qqbot':
            # 修复 QQ Bot
            result = fixer.fix_qqbot()
            self.wfile.write(json.dumps({'fixes': result}).encode())
            
        elif path == '/api/fix/config':
            # 修复配置
            result = fixer.fix_config()
            self.wfile.write(json.dumps({'fixes': result}).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def _add_log(self, data):
        """添加日志记录"""
        global logs_data
        logs_data.append({
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            **data
        })
        if len(logs_data) > max_logs:
            logs_data = logs_data[-max_logs:]


def run_server(port=0):
    """运行 API 服务器"""
    import socket
    # 使用随机端口
    server = HTTPServer(('127.0.0.1', port), APIHandler)
    actual_port = server.server_address[1]
    print(f"ClawDoctor API Server running on http://127.0.0.1:{actual_port}")
    # 写入端口文件供前端读取
    with open('/tmp/clawdoctor-port.txt', 'w') as f:
        f.write(str(actual_port))
    server.serve_forever()


def collect_data():
    """后台收集数据"""
    while True:
        try:
            status = monitor.full_check()
            global logs_data
            logs_data.append({
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
                **status
            })
            if len(logs_data) > max_logs:
                logs_data = logs_data[-max_logs:]
            time.sleep(60)  # 每分钟收集一次
        except Exception as e:
            print(f"数据收集错误: {e}")
            time.sleep(60)


if __name__ == '__main__':
    # 启动数据收集线程
    collector = threading.Thread(target=collect_data, daemon=True)
    collector.start()
    
    # 启动服务器
    run_server()
