param([string]$Action = 'list', [string]$Title = '', [int]$X = 0, [int]$Y = 0, [int]$W = 0, [int]$H = 0, [string]$Exe = '')

$typeDef = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public class WinUtil {
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr a, int x, int y, int w, int t, uint f);
  [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte sc, uint f, IntPtr e);
  delegate bool EnumProc(IntPtr h, IntPtr l);
  static List<IntPtr> hs = new List<IntPtr>();
  static List<string> ts = new List<string>();
  static bool Cb(IntPtr h, IntPtr l) {
    if (!IsWindowVisible(h)) return true;
    int len = GetWindowTextLength(h);
    if (len == 0) return true;
    StringBuilder sb = new StringBuilder(len + 2);
    GetWindowText(h, sb, len + 2);
    hs.Add(h); ts.Add(sb.ToString());
    return true;
  }
  static void Scan() {
    hs.Clear(); ts.Clear();
    EnumWindows(Cb, IntPtr.Zero);
  }
  public static string Page(uint pid) {
    Scan();
    string res = "";
    for (int i = 0; i < hs.Count; i++) {
      uint p = GetWindowThreadProcessId(hs[i], IntPtr.Zero);
      if (pid != 0 && p != pid) continue;
      res += hs[i].ToString() + "|" + p + "|" + ts[i] + "\n";
    }
    return res;
  }
  public static string Find(uint pid, string substr, string action, int x, int y, int w, int h) {
    Scan();
    string res = "";
    for (int i = 0; i < hs.Count; i++) {
      uint p = GetWindowThreadProcessId(hs[i], IntPtr.Zero);
      if (pid != 0 && p != pid) continue;
      if (substr.Length > 0 && ts[i].IndexOf(substr, StringComparison.OrdinalIgnoreCase) < 0) continue;
      IntPtr hw = hs[i];
      string line = hw.ToString() + "|" + ts[i] + "|";
      if (action == "min") line += "min=" + ShowWindow(hw, 6);
      else if (action == "fg") {
        keybd_event(0x12, 0, 0, IntPtr.Zero);
        System.Threading.Thread.Sleep(80);
        ShowWindow(hw, 9);
        System.Threading.Thread.Sleep(150);
        bool ok = SetForegroundWindow(hw);
        System.Threading.Thread.Sleep(200);
        keybd_event(0x12, 0, 2, IntPtr.Zero);
        line += "fg=" + ok + " now=" + (GetForegroundWindow() == hw);
      }
      else if (action == "move") line += "move=" + SetWindowPos(hw, IntPtr.Zero, x, y, w, h, 0x0040);
      else if (action == "top") line += "top=" + SetWindowPos(hw, new IntPtr(-1), x, y, w, h, 0x0040 | 0x0001);
      res += line + "\n";
    }
    return res.Length == 0 ? "<not found>" : res;
  }
}
'@
Add-Type -TypeDefinition $typeDef

if ($Action -eq 'list') {
    if ($Exe) { [WinUtil]::Page((Get-Process $Exe | Select-Object -First 1).Id) } else { [WinUtil]::Page(0) }
} else {
    $p = Get-Process $Exe | Select-Object -First 1
    [WinUtil]::Find([uint32]$p.Id, $Title, $Action, $X, $Y, $W, $H)
}
