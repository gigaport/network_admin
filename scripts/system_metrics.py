#!/usr/bin/env python3
"""호스트 시스템 + 컨테이너 메트릭을 JSON 파일로 저장 (cron에서 30초 주기 실행)"""
import os
import json
import subprocess
import time
from datetime import datetime


def get_host_metrics():
    metrics = {}

    try:
        with open('/proc/stat', 'r') as f:
            line1 = f.readline()
        v1 = list(map(int, line1.split()[1:]))
        time.sleep(0.2)
        with open('/proc/stat', 'r') as f:
            line2 = f.readline()
        v2 = list(map(int, line2.split()[1:]))
        idle_d = v2[3] - v1[3]
        total_d = sum(v2) - sum(v1)
        metrics['cpu'] = {'percent': round((1 - idle_d / max(total_d, 1)) * 100, 1)}
    except:
        metrics['cpu'] = {'percent': 0}

    try:
        meminfo = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                p = line.split()
                meminfo[p[0].rstrip(':')] = int(p[1])
        total = meminfo.get('MemTotal', 0)
        avail = meminfo.get('MemAvailable', 0)
        used = total - avail
        metrics['ram'] = {
            'total_gb': round(total / 1024 / 1024, 1),
            'used_gb': round(used / 1024 / 1024, 1),
            'percent': round(used / max(total, 1) * 100, 1)
        }
    except:
        metrics['ram'] = {'total_gb': 0, 'used_gb': 0, 'percent': 0}

    try:
        st = os.statvfs('/')
        total_b = st.f_blocks * st.f_frsize
        used_b = total_b - st.f_bavail * st.f_frsize
        metrics['disk'] = {
            'total_gb': round(total_b / 1024**3, 1),
            'used_gb': round(used_b / 1024**3, 1),
            'percent': round(used_b / max(total_b, 1) * 100, 1)
        }
    except:
        metrics['disk'] = {'total_gb': 0, 'used_gb': 0, 'percent': 0}

    try:
        with open('/proc/net/dev', 'r') as f:
            lines = f.readlines()[2:]
        rx = tx = 0
        for line in lines:
            p = line.split()
            if p[0].rstrip(':') == 'lo':
                continue
            rx += int(p[1])
            tx += int(p[9])
        metrics['network'] = {'rx_gb': round(rx / 1024**3, 2), 'tx_gb': round(tx / 1024**3, 2)}
    except:
        metrics['network'] = {'rx_gb': 0, 'tx_gb': 0}

    try:
        with open('/proc/uptime', 'r') as f:
            sec = float(f.readline().split()[0])
        d, r = divmod(int(sec), 86400)
        h, r = divmod(r, 3600)
        m = r // 60
        metrics['uptime'] = f"{d}d {h}h {m}m"
    except:
        metrics['uptime'] = '-'

    return metrics


def get_containers():
    containers = []
    try:
        # --size 옵션이 간헐적으로 빈 결과 반환 → 재시도
        ps = None
        for attempt in range(3):
            ps = subprocess.run(
                ['podman', 'ps', '-a', '--size', '--format',
                 '{{.Names}}||{{.Status}}||{{.Size}}'],
                capture_output=True, text=True, timeout=15
            )
            if ps.stdout.strip():
                break
            time.sleep(1)
        for line in ps.stdout.strip().split('\n'):
            if '||' not in line:
                continue
            parts = line.split('||')
            if len(parts) >= 3:
                name = parts[0].strip()
                status = parts[1].strip()
                size = parts[2].strip()

                # 상태에서 uptime 추출
                is_up = 'Up' in status
                containers.append({
                    'name': name,
                    'status': status,
                    'running': is_up,
                    'size': size
                })
    except Exception as e:
        print(f"컨테이너 조회 실패: {e}")

    return containers


def get_backup_info():
    backup_dir = '/home/sysmon/backups/database'
    backups = []
    try:
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.sql.gz') or f.endswith('.tar.gz'):
                path = os.path.join(backup_dir, f)
                stat = os.stat(path)
                size_kb = stat.st_size / 1024
                if size_kb >= 1024:
                    size_str = f"{size_kb/1024:.1f} MB"
                else:
                    size_str = f"{size_kb:.0f} KB"
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                backups.append({
                    'filename': f,
                    'size': size_str,
                    'date': mtime
                })
    except Exception as e:
        print(f"백업 정보 조회 실패: {e}")
    return backups


if __name__ == '__main__':
    data = {
        'success': True,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'host': get_host_metrics(),
        'containers': get_containers(),
        'backups': get_backup_info()
    }

    out_path = '/home/sysmon/network_admin/fastapi/data/system_metrics.json'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # 컨테이너 정보가 비어있으면 이전 파일의 컨테이너 정보 유지
    if not data['containers'] and os.path.exists(out_path):
        try:
            with open(out_path, 'r') as f:
                prev = json.load(f)
            if prev.get('containers'):
                data['containers'] = prev['containers']
        except:
            pass

    with open(out_path, 'w') as f:
        json.dump(data, f, ensure_ascii=False)
