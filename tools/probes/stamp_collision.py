# -*- coding: utf-8 -*-
"""跨语言同名音频：判断「已就位」判据该用什么。

背景：目标目录 <LocalLow>\\WCP\\vocabulary 是**所有语言共用**的一个目录，
游戏按 <词>.mp3 直接读。不同语言包存在**同名但内容不同**的文件（已实测：
11 个语言对里 10 对如此）。镜像层必须能判断"目标里这个文件是不是当前语言的版本"。

候选判据（成本从低到高）：
  A. 只看大小            —— 现在用的，实测碰撞率 11.9%
  B. 大小 + 修改时间      —— 目录枚举免费带回两者，成本与 A 相同
  C. 内容哈希            —— 要逐文件读，最贵，不在一帧/一次枚举内

本脚本回答的核心问题：**B 是否值得替代 A？** 即
  P(大小相同 | 同名不同内容)   vs   P(大小且 mtime 相同 | 同名不同内容)

关键风险：若各语言包的音轨是从同一上游文件批量复制/重编码而来（copy2 会保留
mtime），那么同名文件的 mtime 可能**天然相同**，B 就退化成 A。必须实测，不能假设。
"""
import hashlib
import os
import sys
from collections import defaultdict

LOCALLOW = os.path.join(os.environ.get("USERPROFILE", r"C:\Users\hanserdesu"),
                        "AppData", "LocalLow", "WCP")
PACKS = os.path.join(LOCALLOW, "packs")


def collect():
    """code -> {name: (size, mtime_ns)}"""
    out = {}
    for code in sorted(os.listdir(PACKS)):
        d = os.path.join(PACKS, code, "audio", "word")
        if not os.path.isdir(d):
            continue
        m = {}
        for fn in os.listdir(d):
            if not fn.lower().endswith(".mp3"):
                continue
            p = os.path.join(d, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            m[fn] = (st.st_size, st.st_mtime_ns)
        out[code] = m
    return out


def main():
    data = collect()
    codes = sorted(data)
    print("packs:", ", ".join("%s=%d" % (c, len(data[c])) for c in codes))
    print()

    # 同名不同内容：靠哈希确认"内容确实不同"（同名同内容的样本要排除，
    # 否则会把"本来就一样"算成碰撞，虚高判据的失败率）。
    pairs = 0
    same_name = 0
    diff_content = 0
    size_collide = 0
    size_mtime_collide = 0
    verified = 0
    hash_cache = {}

    def digest(code, name):
        key = (code, name)
        if key in hash_cache:
            return hash_cache[key]
        p = os.path.join(PACKS, code, "audio", "word", name)
        h = hashlib.sha1()
        try:
            with open(p, "rb") as f:
                while True:
                    b = f.read(1 << 16)
                    if not b:
                        break
                    h.update(b)
            v = h.hexdigest()
        except OSError:
            v = None
        hash_cache[key] = v
        return v

    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            a, b = codes[i], codes[j]
            common = set(data[a]) & set(data[b])
            if not common:
                continue
            pairs += 1
            same_name += len(common)
            for name in sorted(common):
                sa, ma = data[a][name]
                sb, mb = data[b][name]
                # 先看元数据，只对"元数据判为可跳过"的样本才做哈希验证（省时间）
                meta_same = (sa == sb)
                if meta_same:
                    size_collide += 1
                if sa == sb and ma == mb:
                    size_mtime_collide += 1
                if meta_same:
                    da, db = digest(a, name), digest(b, name)
                    if da is None or db is None:
                        continue
                    verified += 1
                    if da != db:
                        diff_content += 1
                        print("  内容不同却元数据相同: %s in %s/%s size=%d mtime_eq=%s"
                              % (name, a, b, sa, ma == mb))

    print()
    print("语言对数（有同名文件的）      : %d" % pairs)
    print("同名文件样本总数              : %d" % same_name)
    print("其中被元数据判为「已就位」     : %d" % size_collide)
    print("  已做哈希验证的样本           : %d" % verified)
    print("  哈希证明内容确实不同         : %d" % diff_content)
    print("同名且 (大小+mtime) 都相同     : %d" % size_mtime_collide)
    print()
    if verified:
        print("判据 A（只看大小）错判率      : %.2f%%" % (100.0 * diff_content / verified))
    if size_collide:
        print("判据 B（大小+mtime）错判率    : %.2f%%"
              % (100.0 * max(0, diff_content - (size_collide - size_mtime_collide)) / size_collide))


if __name__ == "__main__":
    main()
