using System;
using System.Runtime.InteropServices;

// SendInput-level mouse click for Unity Input System games.
// Usage: clicker.exe <screenX> <screenY> [doubleClick]
static class Clicker
{
    [StructLayout(LayoutKind.Sequential)]
    struct MOUSEINPUT { public int dx, dy; public uint mouseData, dwFlags, time; public IntPtr dwExtraInfo; }

    [StructLayout(LayoutKind.Explicit)]
    struct INPUT { [FieldOffset(0)] public uint type; [FieldOffset(8)] public MOUSEINPUT mi; }

    const uint INPUT_MOUSE = 0;
    const uint MOUSEEVENTF_MOVE = 0x0001;
    const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    const uint MOUSEEVENTF_LEFTUP = 0x0004;
    const uint MOUSEEVENTF_ABSOLUTE = 0x8000;

    [DllImport("user32.dll")] static extern uint SendInput(uint n, INPUT[] inputs, int size);
    [DllImport("user32.dll")] static extern int GetSystemMetrics(int index);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();

    static void Send(uint flags)
    {
        var inp = new INPUT[1];
        inp[0].type = INPUT_MOUSE;
        inp[0].mi.dwFlags = flags;
        SendInput(1, inp, Marshal.SizeOf(typeof(INPUT)));
    }

    static void MoveTo(int x, int y)
    {
        int w = GetSystemMetrics(0);   // SM_CXSCREEN
        int h = GetSystemMetrics(1);   // SM_CYSCREEN
        var inp = new INPUT[1];
        inp[0].type = INPUT_MOUSE;
        inp[0].mi.dx = (int)((long)x * 65536 / w);
        inp[0].mi.dy = (int)((long)y * 65536 / h);
        inp[0].mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE;
        SendInput(1, inp, Marshal.SizeOf(typeof(INPUT)));
    }

    static void Click(int x, int y, bool dbl)
    {
        MoveTo(x, y);
        System.Threading.Thread.Sleep(80);
        Send(MOUSEEVENTF_LEFTDOWN);
        System.Threading.Thread.Sleep(60);
        Send(MOUSEEVENTF_LEFTUP);
        if (dbl)
        {
            System.Threading.Thread.Sleep(60);
            Send(MOUSEEVENTF_LEFTDOWN);
            System.Threading.Thread.Sleep(60);
            Send(MOUSEEVENTF_LEFTUP);
        }
    }

    static void Main(string[] args)
    {
        SetProcessDPIAware();
        int x = int.Parse(args[0]);
        int y = int.Parse(args[1]);
        bool dbl = args.Length > 2 && args[2] == "2";
        SetCursorPos(x, y);
        System.Threading.Thread.Sleep(50);
        Click(x, y, dbl);
        Console.WriteLine("clicked {0},{1}", x, y);
    }
}
