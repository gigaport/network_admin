import os
import subprocess
import logging

logger = logging.getLogger(__name__)


def get_host_metrics():
    """호스트 시스템 CPU, RAM, Disk, Network 사용률 조회"""
    metrics = {}

    try:
        # CPU 사용률
        with open('/proc/stat', 'r') as f:
            line = f.readline()
        cpu_vals = list(map(int, line.split()[1:]))
        idle = cpu_vals[3]
        total = sum(cpu_vals)
        # 두 번째 샘플링 (100ms)
        import time
        time.sleep(0.1)
        with open('/proc/stat', 'r') as f:
            line = f.readline()
        cpu_vals2 = list(map(int, line.split()[1:]))
        idle2 = cpu_vals2[3]
        total2 = sum(cpu_vals2)
        cpu_pct = round((1 - (idle2 - idle) / max(total2 - total, 1)) * 100, 1)
        metrics['cpu'] = {'percent': cpu_pct}
    except Exception as e:
        metrics['cpu'] = {'percent': 0, 'error': str(e)}

    try:
        # RAM
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                meminfo[parts[0].rstrip(':')] = int(parts[1])
        total_kb = meminfo.get('MemTotal', 0)
        avail_kb = meminfo.get('MemAvailable', 0)
        used_kb = total_kb - avail_kb
        ram_pct = round(used_kb / max(total_kb, 1) * 100, 1)
        metrics['ram'] = {
            'total_gb': round(total_kb / 1024 / 1024, 1),
            'used_gb': round(used_kb / 1024 / 1024, 1),
            'percent': ram_pct
        }
    except Exception as e:
        metrics['ram'] = {'percent': 0, 'error': str(e)}

    try:
        # Disk
        st = os.statvfs('/')
        total_bytes = st.f_blocks * st.f_frsize
        free_bytes = st.f_bavail * st.f_frsize
        used_bytes = total_bytes - free_bytes
        disk_pct = round(used_bytes / max(total_bytes, 1) * 100, 1)
        metrics['disk'] = {
            'total_gb': round(total_bytes / 1024**3, 1),
            'used_gb': round(used_bytes / 1024**3, 1),
            'percent': disk_pct
        }
    except Exception as e:
        metrics['disk'] = {'percent': 0, 'error': str(e)}

    try:
        # Network (총 RX/TX)
        with open('/proc/net/dev', 'r') as f:
            lines = f.readlines()[2:]
        rx_total = 0
        tx_total = 0
        for line in lines:
            parts = line.split()
            iface = parts[0].rstrip(':')
            if iface == 'lo':
                continue
            rx_total += int(parts[1])
            tx_total += int(parts[9])
        metrics['network'] = {
            'rx_gb': round(rx_total / 1024**3, 2),
            'tx_gb': round(tx_total / 1024**3, 2)
        }
    except Exception as e:
        metrics['network'] = {'rx_gb': 0, 'tx_gb': 0, 'error': str(e)}

    try:
        # Uptime
        with open('/proc/uptime', 'r') as f:
            uptime_sec = float(f.readline().split()[0])
        days = int(uptime_sec // 86400)
        hours = int((uptime_sec % 86400) // 3600)
        mins = int((uptime_sec % 3600) // 60)
        metrics['uptime'] = f"{days}d {hours}h {mins}m"
    except Exception as e:
        metrics['uptime'] = '-'

    return metrics


def get_container_metrics():
    """Podman 컨테이너별 CPU, RAM, Disk, Uptime 정보"""
    containers = []
    try:
        result = subprocess.run(
            ['podman', 'ps', '--format',
             '{{.Names}}||{{.Status}}||{{.Size}}'],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split('\n')

        # podman stats (한 번 호출로 전체)
        stats_result = subprocess.run(
            ['podman', 'stats', '--no-stream', '--format',
             '{{.Name}}||{{.CPUPerc}}||{{.MemUsage}}||{{.MemPerc}}'],
            capture_output=True, text=True, timeout=15
        )
        stats_map = {}
        for sline in stats_result.stdout.strip().split('\n'):
            if '||' not in sline:
                continue
            parts = sline.split('||')
            if len(parts) >= 4:
                stats_map[parts[0].strip()] = {
                    'cpu': parts[1].strip(),
                    'mem_usage': parts[2].strip(),
                    'mem_pct': parts[3].strip()
                }

        for line in lines:
            if '||' not in line:
                continue
            parts = line.split('||')
            if len(parts) < 3:
                continue
            name = parts[0].strip()
            status = parts[1].strip()
            size = parts[2].strip()

            stat = stats_map.get(name, {})
            containers.append({
                'name': name,
                'status': status,
                'cpu': stat.get('cpu', '-'),
                'mem_usage': stat.get('mem_usage', '-'),
                'mem_pct': stat.get('mem_pct', '-'),
                'size': size
            })

    except Exception as e:
        logger.error(f"컨테이너 정보 조회 실패: {e}")

    return containers
