# -*- coding: utf-8 -*-
"""性能收敛 A+C（2026-09-16）：

A. 扫描降频
   - WcpHost HostRuntime.ScanBookLabels：随身份轮询每 1s 全场扫 TMP_Text。
     拆出独立节流：活跃期 1s 不变（切书瞬间需要），空闲期（连续 5 次
     无任何改写）升到 5s。
   - SentenceAudioService.Tick：0.3s → 1s（例句按钮出现/消失本就滞后于人眼，
     1s 足够；活跃改写时短暂回 0.3s 加速响应）。

C. 去重复扫描
   - BookNameMod 让位判定：宿主已激活受管词书时，BookNameMod 的口音标签
     （US/UK→JP）与宿主（US/UK→语言码）重复且目标一致；此时 BookNameMod
     跳过自己的 1s 全场扫描（书名美化仍由宿主 DisplayName 覆盖）。
     实现方式：利用已有的 SelectedManagedBook()——非空即宿主接管中。
     为保守起见只跳过「口音标签」扫描分支保留书名美化？——不，书名美化
     宿主也写（DisplayName），故整次 Scan 跳过，恢复逻辑不动（离开受管书
     时 isManaged=false 自动恢复走原路径）。

安全边界：
  - 所有节流都保留首次扫描立即执行（_next 初始 0）。
  - 切书/切场景时身份轮询照旧 1s（ProbeInterval 不动），接管-还原语义不变。
  - BookNameMod 的跳过仅在其「检测到宿主接管」时生效，与既有 YieldToHost
    行为链一致。
"""
import sys
from pathlib import Path

ROOT = Path(r'D:/ATooManyLanguage')
fail = []


def load(p: Path):
    raw = p.read_bytes()
    bom = raw[:3] == b'\xef\xbb\xbf'
    text = (raw[3:] if bom else raw).decode('utf-8').replace('\r\n', '\n')
    return text, bom


def save(p: Path, text: str, bom: bool):
    out = text.replace('\n', '\r\n').encode('utf-8')
    if bom:
        out = b'\xef\xbb\xbf' + out
    p.write_bytes(out)


# ── A-1: WcpHost ScanBookLabels 空闲降频 ────────────────────────────
p = ROOT / 'Japanese' / 'mod_host' / 'HostRuntime.cs'
text, bom = load(p)
orig = text

old_tick = '''            try { ScanBookLabels(); }
            catch (Exception e) { Warn("书名/UI 扫描失败: " + e.Message); }'''
new_tick = '''            try { ScanBookLabelsThrottled(); }
            catch (Exception e) { Warn("书名/UI 扫描失败: " + e.Message); }'''
if old_tick not in text:
    fail.append('HostRuntime: Tick 调用点未匹配')
else:
    text = text.replace(old_tick, new_tick)

old_scan = '''        private void ScanBookLabels()
        {
            UnityEngine.Object[] all = Resources.FindObjectsOfTypeAll(typeof(TMP_Text));'''
new_scan = '''        // UI 标签扫描节流（性能收敛 2026-09-16）：FindObjectsOfTypeAll 全场
        // 扫描有固定成本，标签变化本来就慢。活跃期 1s（与身份轮询同拍，切书
        // 时立即跟进）；连续 5 次无任何改写视为空闲，放慢到 5s；一旦发生
        // 改写立即回到活跃期。
        private const int LabelScanIdleAfter = 5;
        private const float LabelScanIdleInterval = 5f;
        private float _nextLabelScan;
        private int _labelScanIdleCount;

        private void ScanBookLabelsThrottled()
        {
            if (Time.unscaledTime < _nextLabelScan) return;
            int writtenBefore = _labelWritten.Count;
            ScanBookLabels();
            if (_labelWritten.Count != writtenBefore)
                _labelScanIdleCount = 0;
            else if (_labelScanIdleCount < LabelScanIdleAfter)
                _labelScanIdleCount++;
            _nextLabelScan = Time.unscaledTime +
                (_labelScanIdleCount >= LabelScanIdleAfter
                    ? LabelScanIdleInterval : 1f);
        }

        private void ScanBookLabels()
        {
            UnityEngine.Object[] all = Resources.FindObjectsOfTypeAll(typeof(TMP_Text));'''
if old_scan not in text:
    fail.append('HostRuntime: ScanBookLabels 头未匹配')
else:
    text = text.replace(old_scan, new_scan, 1)

# LeaveCurrent 时重置节流（切书后立即恢复活跃扫描）
old_leave = '''            // 离开当前语言范围后音频缓存不再有用，及时释放避免长会话内存增长。
            if (_audio != null) _audio.ClearCache();'''
new_leave = '''            // 离开当前语言范围后音频缓存不再有用，及时释放避免长会话内存增长。
            if (_audio != null) _audio.ClearCache();
            _labelScanIdleCount = 0;
            _nextLabelScan = 0f;'''
if old_leave in text:
    text = text.replace(old_leave, new_leave)
else:
    fail.append('HostRuntime: LeaveCurrent 未匹配')

if text != orig and not fail:
    save(p, text, bom)
    print('OK  Japanese/mod_host/HostRuntime.cs（A-1 空闲降频）')
elif not fail:
    print('--  HostRuntime 无变化')

# ── A-2: SentenceAudioService 0.3s → 1s（改写时短暂回 0.3s）─────────
p = ROOT / 'Japanese' / 'mod_host' / 'SentenceAudioService.cs'
text, bom = load(p)
orig = text

old = '''            if (Time.unscaledTime < _nextScan) return;
            _nextScan = Time.unscaledTime + 0.3f;'''
new = '''            if (Time.unscaledTime < _nextScan) return;
            // 性能收敛 2026-09-16：0.3s → 1s（按钮出现/消失滞后于人眼无感）；
            // 发生过挂载/移除的扫描后短暂回 0.3s 加速连续出现的响应。
            float interval = _scanBusy ? 0.3f : 1f;
            _nextScan = Time.unscaledTime + interval;'''
if old not in text:
    fail.append('SentenceAudioService: Tick 节流未匹配')
else:
    text = text.replace(old, new)

# _scanBusy：本轮扫描有 Attach/Remove 动作则置位。找 Attach/Remove 调用点
old_attach = '''                    seen.Add(button);
                    string file = ResolveFile(j);
                    if (string.IsNullOrEmpty(file) || !File.Exists(file))
                    {
                        Remove(button);
                        continue;
                    }
                    Attach(button, file, j);'''
new_attach = '''                    seen.Add(button);
                    string file = ResolveFile(j);
                    if (string.IsNullOrEmpty(file) || !File.Exists(file))
                    {
                        Remove(button);
                        _scanBusy = true;
                        continue;
                    }
                    Attach(button, file, j);
                    _scanBusy = true;'''
if old_attach in text:
    text = text.replace(old_attach, new_attach)
else:
    fail.append('SentenceAudioService: Attach/Remove 段未匹配')

# 字段声明 + 扫描开始时复位
old_field = '        private float _nextScan;'
new_field = '''        private float _nextScan;
        private bool _scanBusy;'''
if old_field in text:
    text = text.replace(old_field, new_field, 1)
else:
    fail.append('SentenceAudioService: _nextScan 字段未匹配')

old_reset = '''            UnityEngine.Object[] objects = Resources.FindObjectsOfTypeAll(_showReadType);
            HashSet<Button> seen = new HashSet<Button>();'''
new_reset = '''            UnityEngine.Object[] objects = Resources.FindObjectsOfTypeAll(_showReadType);
            _scanBusy = false;
            HashSet<Button> seen = new HashSet<Button>();'''
if old_reset in text:
    text = text.replace(old_reset, new_reset)
else:
    fail.append('SentenceAudioService: 扫描起点未匹配')

if text != orig and not fail:
    save(p, text, bom)
    print('OK  Japanese/mod_host/SentenceAudioService.cs（A-2 降频+忙时加速）')
elif not fail:
    print('--  SentenceAudioService 无变化')

# ── C: BookNameMod 宿主接管时跳过全场扫描 ────────────────────────────
p = ROOT / 'Japanese' / 'mod_book_name' / 'BookNameMod.cs'
text, bom = load(p)
orig = text

old = '''        private void Scan()
        {
            BookProfile managedBook = SelectedManagedBook();
            bool isManaged = managedBook != null;'''
new = '''        private void Scan()
        {
            BookProfile managedBook = SelectedManagedBook();
            bool isManaged = managedBook != null;
            // 性能收敛 2026-09-16：宿主接管受管词书时，书名（DisplayName）与
            // 口音标签都由 WcpHost 的 Tick 写入，本插件的全场 TMP_Text 扫描
            // 是重复劳动——直接跳过。离开受管书（isManaged=false）走原路径
            // 负责还原。Legacy/YieldToHost=false 强制旧模式时不受影响。
            if (isManaged && _yieldToHost != null && _yieldToHost.Value
                && HostTakesOver())
                return;'''
if old not in text:
    fail.append('BookNameMod: Scan 头未匹配')
else:
    text = text.replace(old, new)

# HostTakesOver：读 WcpHost 的激活状态（宿主 Reflection 不可用时返回 false，走原路径）
old_helpers = '''        internal static BookProfile SelectedManagedBook()'''
new_helpers = '''        // 宿主是否已激活受管词书：从 BepInEx 链对象里读 WcpHost 的 Router
        // ActiveProfileId。任何一步失败都返回 false（回退到本插件自扫）。
        private static bool HostTakesOver()
        {
            try
            {
                var plugin = Instance;
                if (plugin == null) return false;
                var hostType = AccessTools.TypeByName("WcpHost.WcpHostPlugin");
                if (hostType == null) return false;
                var inst = AccessTools.PropertyGetter(hostType, "Instance") != null
                    ? hostType.GetProperty("Instance").GetValue(null) : null;
                if (inst == null) return false;
                var runtime = inst.GetType().GetProperty("Runtime") != null
                    ? inst.GetType().GetProperty("Runtime").GetValue(inst) : null;
                if (runtime == null) return false;
                var pid = runtime.GetType().GetProperty("ActiveProfileId");
                return pid != null && pid.GetValue(runtime) != null;
            }
            catch (Exception) { return false; }
        }

        internal static BookProfile SelectedManagedBook()'''
if old_helpers in text:
    text = text.replace(old_helpers, new_helpers, 1)
else:
    fail.append('BookNameMod: SelectedManagedBook 锚点未匹配')

# using HarmonyLib（AccessTools）
if 'using HarmonyLib;' not in text:
    text = text.replace('using BepInEx;', 'using BepInEx;\nusing HarmonyLib;', 1)
    if 'using HarmonyLib;' not in text:
        # 退化：在第一个 using 后插入
        i = text.index('using ')
        j = text.index('\n', i)
        text = text[:j + 1] + 'using HarmonyLib;\n' + text[j + 1:]

if text != orig and not fail:
    save(p, text, bom)
    print('OK  Japanese/mod_book_name/BookNameMod.cs（C 宿主接管时跳过扫描）')
elif not fail:
    print('--  BookNameMod 无变化')

if fail:
    print('\n未完成:')
    for f in fail:
        print('  -', f)
    sys.exit(1)
print('\nA+C 收敛完成。')
