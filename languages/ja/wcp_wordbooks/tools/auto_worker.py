# -*- coding: utf-8 -*-
"""夜间自动化工人: 每次调用推进一轮管线(幂等, 可重复调用)。

步骤:
  1. 继续生成发音MP3(批量)
  2. 继续机翻剩余英文释义(如有)
  3. 如有新翻译 -> 合并 -> 重建词书 -> 重写 MyBook.es3 + 导入文件
  4. 导出下一批 LLM 精翻任务
  5. 写进度到 logs/progress.json

用法: py auto_worker.py [--audio-limit 300] [--skip-audio]
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
PROGRESS = LOGS / 'progress.json'
LOCK = LOGS / 'auto_worker.lock'


def acquire_lock():
    LOGS.mkdir(exist_ok=True)
    if LOCK.exists():
        age = time.time() - LOCK.stat().st_mtime
        if age < 3600:
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
        raise RuntimeError(f'{script} failed:\n{out[-1500:]}')
    return r.returncode, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audio-limit', type=int, default=300)
    ap.add_argument('--skip-audio', action='store_true')
    args = ap.parse_args()

    if not acquire_lock():
        print('另一轮 worker 仍在运行, 本轮跳过')
        return
    try:
        _work(args)
    finally:
        release_lock()


def _work(args):
    step = {}
    t0 = time.time()
    try:
        # 1. 音频 (--retry-failed 每轮重试暂态失败项)
        if not args.skip_audio:
            code, out = run('gen_audio.py', '--limit', str(args.audio_limit),
                            '--retry-failed')
            step['audio'] = out.strip().splitlines()[-2:] if out.strip() else []
        # 2. 机翻
        code, out = run('translate_gtx.py', '--limit', '400', '--sleep', '0.2')
        step['translate'] = out.strip().splitlines()[-1:] if out.strip() else []
        # 2b. Jisho 补读音
        code, out = run('fetch_readings.py', '--limit', '40', check=False)
        step['readings'] = out.strip().splitlines()[-1:] if out.strip() else []
        # 3. 合并(有更新才重写)
        code, out = run('merge_translations.py', '--write-game')
        step['merge'] = out.strip().splitlines()
        # 4. LLM 批任务
        code, out = run('make_llm_batch.py')
        step['llm_batch'] = out.strip().splitlines()[:3]
        # 5. 词书改名(仅游戏关闭时生效)
        try:
            code, out = run('rename_books.py', check=False)
            step['rename'] = out.strip().splitlines()[:2]
        except Exception:
            pass
        status = 'ok'
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
    print(json.dumps(prog, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
