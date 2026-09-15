# -*- coding: utf-8 -*-
"""夜间工兵(计划任务每20分钟调用, 幂等):
  1. Set B 音频补齐+失败重试 (gen_audio_topic)
  2. 重建 topic 导入文件 (merge_topic --write-import)
  3. wcp.exe 已关闭 -> 执行书名改名 (rename_books, 内部有存档保护)
  4. 到达截止时间(2026-09-07 09:00) -> 自删除计划任务并退出
进度写 logs/night_progress.json
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'tools'
LOGS = ROOT / 'logs'
PROGRESS = LOGS / 'night_progress.json'
LOCK = LOGS / 'night_worker.lock'
DEADLINE = (2026, 9, 7, 9, 0, 0)
TASK_NAME = 'WCP_NightWorker'

sys.stdout.reconfigure(encoding='utf-8')


def run(script, *args, check=True):
    cmd = [sys.executable, str(TOOLS / script), *args]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    if check and r.returncode != 0:
        return r.returncode, f'FAILED: {out[-800:]}'
    return r.returncode, out


def game_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq wcp.exe'],
                       capture_output=True, text=True, encoding='gbk',
                       errors='replace')
    return 'wcp.exe' in (r.stdout or '')


def main():
    LOGS.mkdir(exist_ok=True)
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 1500:
        print('上一轮仍在运行, 跳过')
        return
    LOCK.write_text(str(time.time()), encoding='utf-8')
    step = {}
    t0 = time.time()
    deadline = time.mktime((*DEADLINE, 0, 0, -1))
    try:
        if time.time() >= deadline:
            subprocess.run(['schtasks', '/Delete', '/TN', TASK_NAME, '/F'],
                           capture_output=True)
            step['cleanup'] = '到达截止时间, 已自删除计划任务'
        else:
            # 1. Set B 音频
            code, out = run('gen_audio_topic.py', '--limit', '400',
                            '--retry-failed', check=False)
            step['audio_topic'] = [l for l in out.strip().splitlines()
                                   if l.strip()][-2:]
            # 1b. 常用汉字音频 (manifest 幂等)
            code, out = run('merge_kanji.py', '--audio', check=False)
            step['audio_kanji'] = [l for l in out.strip().splitlines()
                                   if '音频完成' in l or '待生成' in l][-2:]
            # 2. 重建导入文件
            code, out = run('merge_topic.py', '--write-import')
            step['merge_topic'] = out.strip().splitlines()
            # 2b. 本地词库补丁 (词数增长时自动重灌; 游戏内释义/例句依赖它)
            code, out = run('patch_local_db.py', check=False)
            step['local_db'] = out.strip().splitlines()[-2:]
            # 3. 恢复默认书名(仅游戏关闭时; 自定义词书N 才能加载内置字典)
            if game_running():
                step['rename'] = 'wcp.exe 运行中, 跳过'
            else:
                code, out = run('rename_books.py', check=False)
                step['rename'] = out.strip().splitlines()[:2]
            step['time_left'] = f'{deadline - time.time():.0f}s'
        status = 'ok'
    except Exception as e:
        status = f'error: {e}'
        step['error'] = str(e)[:400]
    finally:
        try:
            LOCK.unlink()
        except OSError:
            pass

    prog = {'time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': status,
            'elapsed_sec': round(time.time() - t0, 1),
            'steps': step}
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    print(json.dumps(prog, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
