# -*- coding: utf-8 -*-
"""Set B 夜间自动化工人 (幂等, 可重复调用)。

每轮:
  1. setb 音频批量生成 (含失败重试)
  2. 词书改名 (仅游戏关闭时生效)
  3. 进度写 logs/setb_progress.json + worklog 追加一行

用法: py setb_worker.py [--audio-limit 500]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'tools'
LOGS = ROOT / 'logs'
PROGRESS = LOGS / 'setb_progress.json'
WORKLOG = LOGS / 'agent_worklog.md'
LOCK = LOGS / 'setb_worker.lock'


def acquire_lock():
    LOGS.mkdir(exist_ok=True)
    if LOCK.exists():
        if time.time() - LOCK.stat().st_mtime < 1800:
            return False
    LOCK.write_text(str(time.time()), encoding='utf-8')
    return True


def release_lock():
    try:
        LOCK.unlink()
    except OSError:
        pass


def run(script, *args, check=True):
    cmd = [sys.executable, str(TOOLS / script), *args]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    if check and r.returncode != 0:
        raise RuntimeError(f'{script} failed:\n{out[-1200:]}')
    return r.returncode, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audio-limit', type=int, default=500)
    args = ap.parse_args()

    if not acquire_lock():
        print('另一轮 setb worker 仍在运行, 跳过')
        return
    try:
        _work(args)
    finally:
        release_lock()


def _work(args):
    step = {}
    t0 = time.time()
    status = 'ok'
    try:
        code, out = run('setb_audio.py', '--limit', str(args.audio_limit),
                        '--retry-failed')
        lines = [l for l in out.strip().splitlines() if l.strip()]
        step['audio'] = lines[-2:] if lines else []
        m = ''
        for l in lines:
            if l.startswith('本轮完成'):
                m = l
        step['audio_msg'] = m

        try:
            code, out = run('rename_books.py', check=False)
            step['rename'] = out.strip().splitlines()[:2]
        except Exception as e:
            step['rename'] = [f'err {e}']
    except Exception as e:
        status = f'error: {e}'
        step['error'] = str(e)[:500]

    prog = {
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'status': status,
        'elapsed_sec': round(time.time() - t0, 1),
        'steps': step,
    }
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    with open(WORKLOG, 'a', encoding='utf-8') as f:
        done = _audio_done()
        f.write(f'| {prog["time"]} | setb音频 {done} | {step.get("audio_msg", status)} |\n')
    print(json.dumps(prog, ensure_ascii=False, indent=1))


def _audio_done():
    try:
        m = json.loads((ROOT / 'output' / 'setb_audio_manifest.json')
                       .read_text(encoding='utf-8'))
        return len(m.get('done', {}))
    except Exception:
        return -1


if __name__ == '__main__':
    main()
