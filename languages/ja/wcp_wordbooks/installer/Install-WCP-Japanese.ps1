$ErrorActionPreference = 'Stop'

function Write-Step([string]$message) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $message" -ForegroundColor Cyan
}

function Fail([string]$message) {
    throw "错误: $message"
}

function Get-Sha256([string]$path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [IO.File]::OpenRead($path)
        return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        if ($stream) { $stream.Dispose() }
        if ($sha) { $sha.Dispose() }
    }
}

function Download-WithProgress([string]$uri, [string]$destination, [string]$displayName, [int64]$expectedSize) {
    $request = $null
    $response = $null
    $inputStream = $null
    $outputStream = $null
    $resumeFrom = [int64]0
    if (Test-Path -LiteralPath $destination) {
        $existing = Get-Item -LiteralPath $destination
        $resumeFrom = [int64]$existing.Length
        if ($resumeFrom -gt $expectedSize) {
            Remove-Item -LiteralPath $destination -Force
            $resumeFrom = [int64]0
        } elseif ($resumeFrom -eq $expectedSize) {
            Write-Host "发现完整的未完成缓存：$displayName，将直接校验。" -ForegroundColor DarkGray
            return
        }
    }
    try {
        $request = [Net.WebRequest]::Create($uri)
        $request.Method = 'GET'
        $request.Timeout = 60000
        $request.ReadWriteTimeout = 60000
        $request.UserAgent = 'WCP-Japanese-Installer/1.2.2'
        $request.Proxy = [Net.WebRequest]::DefaultWebProxy
        if ($request.Proxy) { $request.Proxy.Credentials = [Net.CredentialCache]::DefaultCredentials }
        $resumeRequested = $resumeFrom -gt 0 -and $request -is [Net.HttpWebRequest]
        if ($resumeRequested) {
            $request.AddRange($resumeFrom)
            Write-Host "检测到 $displayName 的未完成缓存，将从 $resumeFrom 字节继续下载。" -ForegroundColor DarkGray
        }
        $response = $request.GetResponse()
        $statusCode = if ($response -is [Net.HttpWebResponse]) { [int]$response.StatusCode } else { 200 }
        $resumeAccepted = $resumeRequested -and $statusCode -eq 206
        if ($resumeRequested -and -not $resumeAccepted) {
            Write-Host '下载服务器未接受断点请求，已从头重新传输本文件。' -ForegroundColor DarkYellow
            $resumeFrom = [int64]0
        }
        $contentLength = [int64]$response.ContentLength
        $total = if ($contentLength -gt 0) {
            if ($resumeAccepted) { $resumeFrom + $contentLength } else { $contentLength }
        } else { $expectedSize }
        $inputStream = $response.GetResponseStream()
        $fileMode = if ($resumeAccepted) { [IO.FileMode]::Append } else { [IO.FileMode]::Create }
        $outputStream = [IO.File]::Open($destination, $fileMode, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $buffer = New-Object byte[] (1024 * 1024)
        $downloaded = $resumeFrom
        $watch = [Diagnostics.Stopwatch]::StartNew()
        $lastUpdate = [datetime]::MinValue
        while (($read = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $outputStream.Write($buffer, 0, $read)
            $downloaded += $read
            $now = Get-Date
            if (($now - $lastUpdate).TotalMilliseconds -ge 250 -or ($total -gt 0 -and $downloaded -ge $total)) {
                $lastUpdate = $now
                $percent = if ($total -gt 0) { [Math]::Min(100, [int](($downloaded * 100) / $total)) } else { 0 }
                $speed = if ($watch.Elapsed.TotalSeconds -gt 0) { $downloaded / 1MB / $watch.Elapsed.TotalSeconds } else { 0 }
                $status = if ($total -gt 0) {
                    "$percent%  $([Math]::Round($downloaded / 1MB, 1)) / $([Math]::Round($total / 1MB, 1)) MB  $([Math]::Round($speed, 2)) MB/s"
                } else {
                    "$([Math]::Round($downloaded / 1MB, 1)) MB  $([Math]::Round($speed, 2)) MB/s"
                }
                Write-Progress -Activity "下载 $displayName" -Status $status -PercentComplete $percent
            }
        }
        $outputStream.Flush()
        Write-Progress -Activity "下载 $displayName" -Completed
    } finally {
        if ($outputStream) { $outputStream.Dispose() }
        if ($inputStream) { $inputStream.Dispose() }
        if ($response) { $response.Dispose() }
    }
}

function Ensure-ZipExtractor {
    if ('WcpJapaneseZipSession' -as [type]) { return }
    Add-Type -AssemblyName System.IO.Compression -ErrorAction Stop
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop
    $zipReferences = @('System.dll', 'System.Core.dll',
        'System.IO.Compression.dll', 'System.IO.Compression.FileSystem.dll')
    $zipSource = @'
using System;
using System.IO;
using System.IO.Compression;
using System.Threading;
using System.Threading.Tasks;

public sealed class WcpJapaneseZipSession
{
    public Task Task;
    public volatile bool TotalReady;
    public int TotalFiles;
    public long TotalBytes;
    public int CompletedFiles;
    public long CompletedBytes;

    private readonly object ErrorLock = new object();
    private string ErrorText;

    public static WcpJapaneseZipSession Start(string zipPath, string destination, int workerCount)
    {
        WcpJapaneseZipSession session = new WcpJapaneseZipSession();
        session.CompletedFiles = 0;
        session.CompletedBytes = 0;
        session.TotalFiles = 0;
        session.TotalBytes = 0;
        session.TotalReady = false;
        session.Task = Task.Factory.StartNew(
            () => session.Extract(zipPath, destination, workerCount),
            CancellationToken.None,
            TaskCreationOptions.LongRunning,
            TaskScheduler.Default);
        return session;
    }

    public string GetError()
    {
        lock (ErrorLock) { return ErrorText; }
    }

    private void Extract(string zipPath, string destination, int workerCount)
    {
        ErrorText = null;
        string root = Path.GetFullPath(destination);
        if (!root.EndsWith(Path.DirectorySeparatorChar.ToString(), StringComparison.Ordinal))
            root += Path.DirectorySeparatorChar;

        string[] names;
        using (ZipArchive archive = OpenArchiveWithRetry(zipPath))
        {
            int nameCount = 0;
            foreach (ZipArchiveEntry entry in archive.Entries)
            {
                if (!String.IsNullOrEmpty(entry.Name)) nameCount++;
            }
            names = new string[nameCount];
            int nameIndex = 0;
            foreach (ZipArchiveEntry entry in archive.Entries)
            {
                if (!String.IsNullOrEmpty(entry.Name)) names[nameIndex++] = entry.FullName;
            }
            TotalFiles = names.Length;
            long total = 0;
            foreach (ZipArchiveEntry entry in archive.Entries)
            {
                if (!String.IsNullOrEmpty(entry.Name)) total += entry.Length;
            }
            TotalBytes = total;
            TotalReady = true;
        }

        int workers = Math.Max(1, Math.Min(workerCount, Math.Max(1, names.Length)));
        Task[] tasks = new Task[workers];
        for (int worker = 0; worker < workers; worker++)
        {
            int workerIndex = worker;
            tasks[worker] = Task.Factory.StartNew(
                () => ExtractWorker(zipPath, root, names, workerIndex, workers),
                CancellationToken.None,
                TaskCreationOptions.LongRunning,
                TaskScheduler.Default);
        }
        try
        {
            Task.WaitAll(tasks);
        }
        catch (Exception ex)
        {
            SetError(ex.ToString());
            throw;
        }
    }

    private void ExtractWorker(string zipPath, string root, string[] names,
                               int workerIndex, int workerCount)
    {
        try
        {
            using (ZipArchive archive = OpenArchiveWithRetry(zipPath))
            {
                for (int i = workerIndex; i < names.Length; i += workerCount)
                {
                    ZipArchiveEntry entry = archive.GetEntry(names[i]);
                    if (entry == null) throw new InvalidDataException("ZIP entry disappeared: " + names[i]);
                    string relative = entry.FullName.Replace('/', Path.DirectorySeparatorChar);
                    string target = Path.GetFullPath(Path.Combine(root, relative));
                    if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException("Unsafe ZIP path: " + entry.FullName);
                    string parent = Path.GetDirectoryName(target);
                    if (!String.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
                    WriteEntryWithRetry(entry, target);
                    Interlocked.Increment(ref CompletedFiles);
                    Interlocked.Add(ref CompletedBytes, entry.Length);
                }
            }
        }
        catch (Exception ex)
        {
            SetError(ex.ToString());
            throw;
        }
    }

    // 杀毒/安全软件常在大量写入时临时锁定新文件，导致 IOException 或
    // UnauthorizedAccessException。带退避的短重试能吸收这类瞬态占用；
    // 最终失败时带上目标路径，让 PowerShell 端能给出具体原因。
    // 注意：PS 5.1 的 Add-Type 只支持 C# 5，不能用异常过滤器等新语法。
    private static ZipArchive OpenArchiveWithRetry(string zipPath)
    {
        const int attempts = 4;
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                return ZipFile.OpenRead(zipPath);
            }
            catch (IOException ex)
            {
                if (attempt >= attempts || !IsTransient(ex)) { throw; }
                Thread.Sleep(400 * attempt);
            }
            catch (UnauthorizedAccessException)
            {
                if (attempt >= attempts) { throw; }
                Thread.Sleep(400 * attempt);
            }
        }
    }

    private static bool IsTransient(IOException ex)
    {
        // .NET Framework 中 Exception.HResult 是 protected，外部访问无法编译，
        // 只能用 Marshal.GetHRForException。
        int hr = System.Runtime.InteropServices.Marshal.GetHRForException(ex) & 0xFFFF;
        // ERROR_SHARING_VIOLATION (32) / ERROR_LOCK_VIOLATION (33)
        return hr == 0x20 || hr == 0x21;
    }

    private void WriteEntryWithRetry(ZipArchiveEntry entry, string target)
    {
        const int attempts = 4;
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                using (Stream input = entry.Open())
                using (FileStream output = new FileStream(ExtendedPathIfNeeded(target), FileMode.Create, FileAccess.Write, FileShare.None))
                {
                    input.CopyTo(output);
                }
                return;
            }
            catch (Exception ex)
            {
                if (!(ex is IOException) && !(ex is UnauthorizedAccessException)) { throw; }
                if (attempt >= attempts)
                {
                    throw new IOException("写入 " + target + " 失败（重试 " + (attempts - 1) + " 次后仍失败）：" + ex.Message, ex);
                }
                Thread.Sleep(400 * attempt);
            }
        }
    }

    private static string ExtendedPathIfNeeded(string path)
    {
        string name = Path.GetFileName(path);
        if (string.IsNullOrEmpty(name)) return path;
        string stem = name;
        int dot = name.IndexOf('.');
        if (dot >= 0) stem = name.Substring(0, dot);
        string upper = stem.ToUpperInvariant();
        if (upper == "AUX" || upper == "CON" || upper == "PRN" || upper == "NUL")
            return @"\\?\" + path;
        if ((upper.StartsWith("COM") || upper.StartsWith("LPT")) && upper.Length > 3)
        {
            int n;
            if (int.TryParse(upper.Substring(3), out n) && n >= 1 && n <= 9)
                return @"\\?\" + path;
        }
        return path;
    }

    private void SetError(string text)
    {
        lock (ErrorLock) { if (ErrorText == null) ErrorText = text; }
    }
}
'@
    if ($PSVersionTable.PSEdition -eq 'Core') {
        Add-Type -TypeDefinition $zipSource -Language CSharp -ErrorAction Stop
    } else {
        Add-Type -TypeDefinition $zipSource -Language CSharp -ReferencedAssemblies $zipReferences -ErrorAction Stop
    }
}


function Ensure-Es3Helper {
    if ('WcpEs3Helper' -as [type]) { return }
    $es3Source = @'
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;

public static class WcpEs3Helper
{
    public static Dictionary<string, object> ParseJson(string json)
    {
        int idx = 0;
        return ParseObject(json, ref idx);
    }

    private static void SkipWhite(string s, ref int i)
    {
        while (i < s.Length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\r' || s[i] == '\n')) i++;
    }

    private static object ParseValue(string s, ref int i)
    {
        SkipWhite(s, ref i);
        if (i >= s.Length) return null;
        char c = s[i];
        if (c == '{') return ParseObject(s, ref i);
        if (c == '[') return ParseArray(s, ref i);
        if (c == '"') return ParseString(s, ref i);
        if (c == 't') { i += 4; return true; }
        if (c == 'f') { i += 5; return false; }
        if (c == 'n') { i += 4; return null; }
        return ParseNumber(s, ref i);
    }

    public static Dictionary<string, object> ParseObject(string s, ref int i)
    {
        var dict = new Dictionary<string, object>(StringComparer.Ordinal);
        if (i >= s.Length || s[i] != '{') return dict;
        i++;
        while (i < s.Length)
        {
            SkipWhite(s, ref i);
            if (i >= s.Length || s[i] == '}') { if (i < s.Length) i++; break; }
            string key = ParseString(s, ref i);
            SkipWhite(s, ref i);
            if (i < s.Length && s[i] == ':') i++;
            object val = ParseValue(s, ref i);
            dict[key] = val;
            SkipWhite(s, ref i);
            if (i < s.Length && s[i] == ',') i++;
            else if (i < s.Length && s[i] == '}') { i++; break; }
        }
        return dict;
    }

    public static List<object> ParseArray(string s, ref int i)
    {
        var list = new List<object>();
        if (i >= s.Length || s[i] != '[') return list;
        i++;
        while (i < s.Length)
        {
            SkipWhite(s, ref i);
            if (i >= s.Length || s[i] == ']') { if (i < s.Length) i++; break; }
            object val = ParseValue(s, ref i);
            list.Add(val);
            SkipWhite(s, ref i);
            if (i < s.Length && s[i] == ',') i++;
            else if (i < s.Length && s[i] == ']') { i++; break; }
        }
        return list;
    }

    public static string ParseString(string s, ref int i)
    {
        SkipWhite(s, ref i);
        if (i >= s.Length || s[i] != '"') return "";
        i++;
        int start = i;
        StringBuilder sb = null;
        while (i < s.Length)
        {
            char c = s[i++];
            if (c == '"')
            {
                if (sb == null) return s.Substring(start, i - 1 - start);
                return sb.ToString();
            }
            if (c == '\\')
            {
                if (sb == null)
                {
                    sb = new StringBuilder(64);
                    sb.Append(s, start, i - 1 - start);
                }
                if (i >= s.Length) break;
                char esc = s[i++];
                if (esc == '"') sb.Append('"');
                else if (esc == '\\') sb.Append('\\');
                else if (esc == '/') sb.Append('/');
                else if (esc == 'b') sb.Append('\b');
                else if (esc == 'f') sb.Append('\f');
                else if (esc == 'n') sb.Append('\n');
                else if (esc == 'r') sb.Append('\r');
                else if (esc == 't') sb.Append('\t');
                else if (esc == 'u' && i + 4 <= s.Length)
                {
                    string hex = s.Substring(i, 4);
                    i += 4;
                    sb.Append((char)Convert.ToInt32(hex, 16));
                }
            }
            else if (sb != null)
            {
                sb.Append(c);
            }
        }
        return sb != null ? sb.ToString() : "";
    }

    private static object ParseNumber(string s, ref int i)
    {
        int start = i;
        if (i < s.Length && s[i] == '-') i++;
        while (i < s.Length && (char.IsDigit(s[i]) || s[i] == '.' || s[i] == 'e' || s[i] == 'E' || s[i] == '+' || s[i] == '-')) i++;
        string num = s.Substring(start, i - start);
        long l;
        if (long.TryParse(num, out l)) return l;
        double d;
        if (double.TryParse(num, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out d)) return d;
        return num;
    }

    public static void Serialize(object obj, StringBuilder sb, int indent)
    {
        if (obj == null) { sb.Append("null"); return; }
        if (obj is string)
        {
            sb.Append('"');
            foreach (char c in (string)obj)
            {
                if (c == '"') sb.Append("\\\"");
                else if (c == '\\') sb.Append("\\\\");
                else if (c == '\b') sb.Append("\\b");
                else if (c == '\f') sb.Append("\\f");
                else if (c == '\n') sb.Append("\\n");
                else if (c == '\r') sb.Append("\\r");
                else if (c == '\t') sb.Append("\\t");
                else if (c < 32) sb.AppendFormat("\\u{0:x4}", (int)c);
                else sb.Append(c);
            }
            sb.Append('"');
            return;
        }
        if (obj is bool) { sb.Append((bool)obj ? "true" : "false"); return; }
        if (obj is IDictionary)
        {
            var dict = (IDictionary)obj;
            if (dict.Count == 0) { sb.Append("{}"); return; }
            sb.Append("{\r\n");
            int count = 0;
            string pad = new string('\t', indent + 1);
            foreach (DictionaryEntry kv in dict)
            {
                if (count++ > 0) sb.Append(",\r\n");
                sb.Append(pad);
                Serialize(kv.Key.ToString(), sb, indent + 1);
                sb.Append(" : ");
                Serialize(kv.Value, sb, indent + 1);
            }
            sb.Append("\r\n" + new string('\t', indent) + "}");
            return;
        }
        if (obj is IEnumerable && !(obj is string))
        {
            var list = (IEnumerable)obj;
            sb.Append("[");
            int count = 0;
            foreach (var item in list)
            {
                if (count++ > 0) sb.Append(", ");
                Serialize(item, sb, indent);
            }
            sb.Append("]");
            return;
        }
        if (obj is double || obj is float)
        {
            sb.Append(Convert.ToString(obj, System.Globalization.CultureInfo.InvariantCulture));
            return;
        }
        sb.Append(obj.ToString());
    }

    public static bool IsSaveCorrupted(string savePath)
    {
        if (!File.Exists(savePath)) return false;
        try
        {
            string text = File.ReadAllText(savePath, Encoding.UTF8);
            var doc = ParseJson(text);
            if (doc.Count == 0) return true;
            int typeMissing = 0;
            foreach (var kv in doc)
            {
                var child = kv.Value as Dictionary<string, object>;
                if (child != null && !child.ContainsKey("__type")) typeMissing++;
            }
            if (typeMissing > 5) return true;
            if (doc.Count < 120 && doc.ContainsKey("Initial_PlotDone"))
            {
                var child = doc["Initial_PlotDone"] as Dictionary<string, object>;
                if (child != null && child.ContainsKey("value"))
                {
                    object val = child["value"];
                    long plotVal = (val is long) ? (long)val : 0;
                    if (plotVal <= 1) return true;
                }
            }
            return false;
        }
        catch { return true; }
    }

    public static string FindBestSaveBackup(string dataDir)
    {
        var candidates = new List<string>();
        string jpmodDir = Path.Combine(dataDir, "jpmod_backups");
        if (Directory.Exists(jpmodDir))
        {
            foreach (string sub in Directory.GetDirectories(jpmodDir))
            {
                string f = Path.Combine(sub, "SaveFile.es3");
                if (File.Exists(f)) candidates.Add(f);
            }
        }
        foreach (string f in Directory.GetFiles(dataDir, "SaveFile_Copy*.es3"))
            candidates.Add(f);
        foreach (string f in Directory.GetFiles(dataDir, "SaveFile.es3.bak_*"))
            candidates.Add(f);

        candidates.Sort((a, b) => File.GetLastWriteTime(b).CompareTo(File.GetLastWriteTime(a)));

        foreach (string c in candidates)
        {
            try
            {
                string text = File.ReadAllText(c, Encoding.UTF8);
                var doc = ParseJson(text);
                if (doc.Count < 150) continue;
                if (!doc.ContainsKey("Initial_PlotDone")) continue;
                var child = doc["Initial_PlotDone"] as Dictionary<string, object>;
                if (child == null || !child.ContainsKey("__type") || !child.ContainsKey("value")) continue;
                long plotVal = (child["value"] is long) ? (long)child["value"] : 0;
                if (plotVal >= 3) return c;
            }
            catch { }
        }
        return null;
    }

    public static bool TryRepairSaveFile(string savePath, string dataDir, out string restoredFrom)
    {
        restoredFrom = null;
        if (!IsSaveCorrupted(savePath)) return false;
        string best = FindBestSaveBackup(dataDir);
        if (string.IsNullOrEmpty(best)) return false;
        try { File.Copy(savePath, savePath + ".corrupt_before_repair.bak", true); } catch { }
        File.Copy(best, savePath, true);
        restoredFrom = best;
        return true;
    }

    public static bool TryRepairMyBook(string myBookPath, string dataDir, out string restoredFrom)
    {
        restoredFrom = null;
        if (!File.Exists(myBookPath)) return false;
        try
        {
            string text = File.ReadAllText(myBookPath, Encoding.UTF8);
            var doc = ParseJson(text);
            bool needRepair = false;
            foreach (var kv in doc)
            {
                var child = kv.Value as Dictionary<string, object>;
                if (child != null && !child.ContainsKey("__type")) { needRepair = true; break; }
            }
            if (!needRepair) return false;
            string jpmodDir = Path.Combine(dataDir, "jpmod_backups");
            if (Directory.Exists(jpmodDir))
            {
                var subs = new List<string>(Directory.GetDirectories(jpmodDir));
                subs.Sort((a, b) => Directory.GetLastWriteTime(b).CompareTo(Directory.GetLastWriteTime(a)));
                foreach (string sub in subs)
                {
                    string f = Path.Combine(sub, "MyBook.es3");
                    if (File.Exists(f))
                    {
                        var bDoc = ParseJson(File.ReadAllText(f, Encoding.UTF8));
                        bool bGood = true;
                        foreach (var kv in bDoc) {
                            var child = kv.Value as Dictionary<string, object>;
                            if (child != null && !child.ContainsKey("__type")) { bGood = false; break; }
                        }
                        if (bGood && bDoc.Count > 0) {
                            File.Copy(f, myBookPath, true);
                            restoredFrom = f;
                            return true;
                        }
                    }
                }
            }
            string arrType = "System.String[],mscorlib";
            string dictType = "System.Collections.Generic.Dictionary`2[[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089],[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]],mscorlib";
            for (int i = 1; i <= 4; i++)
            {
                string lk = "SelfBookList" + i;
                string dk = "wordDictionary" + i;
                if (doc.ContainsKey(lk)) {
                    var child = doc[lk] as Dictionary<string, object>;
                    if (child != null && !child.ContainsKey("__type")) child["__type"] = arrType;
                }
                if (doc.ContainsKey(dk)) {
                    var child = doc[dk] as Dictionary<string, object>;
                    if (child != null && !child.ContainsKey("__type")) child["__type"] = dictType;
                }
            }
            var sb = new StringBuilder();
            Serialize(doc, sb, 0);
            File.WriteAllText(myBookPath, sb.ToString(), new UTF8Encoding(false));
            restoredFrom = "in-place repaired";
            return true;
        }
        catch { return false; }
    }

    public static int InstallBookAndSave(string myBookPath, string savePath, string catbarPayloadPath, int slotOverride = 0)
    {
        string payloadJson = File.ReadAllText(catbarPayloadPath, Encoding.UTF8);
        var payload = ParseJson(payloadJson);
        var words = payload["words"] as List<object>;
        var meanings = payload["meanings"] as Dictionary<string, object>;

        string myBookJson = File.ReadAllText(myBookPath, Encoding.UTF8);
        var myBook = ParseJson(myBookJson);

        int targetSlot = slotOverride;
        if (targetSlot <= 0 || targetSlot > 4)
        {
            for (int i = 1; i <= 4; i++) {
                string key = "SelfBookList" + i;
                if (myBook.ContainsKey(key)) {
                    var entry = myBook[key] as Dictionary<string, object>;
                    if (entry != null && entry.ContainsKey("value")) {
                        var list = entry["value"] as List<object>;
                        if (list != null && list.Count == words.Count) { targetSlot = i; break; }
                    }
                }
            }
            if (targetSlot == 0) {
                for (int i = 1; i <= 4; i++) {
                    string key = "SelfBookList" + i;
                    if (myBook.ContainsKey(key)) {
                        var entry = myBook[key] as Dictionary<string, object>;
                        if (entry != null && entry.ContainsKey("value")) {
                            var list = entry["value"] as List<object>;
                            if (list == null || list.Count == 0) { targetSlot = i; break; }
                        }
                    } else { targetSlot = i; break; }
                }
            }
            if (targetSlot == 0) targetSlot = 1;
        }

        string arrType = "System.String[],mscorlib";
        string dictType = "System.Collections.Generic.Dictionary`2[[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089],[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]],mscorlib";

        myBook["SelfBookList" + targetSlot] = new Dictionary<string, object>(StringComparer.Ordinal) {
            { "__type", arrType },
            { "value", words }
        };
        myBook["wordDictionary" + targetSlot] = new Dictionary<string, object>(StringComparer.Ordinal) {
            { "__type", dictType },
            { "value", meanings }
        };

        var sbMb = new StringBuilder();
        Serialize(myBook, sbMb, 0);
        File.WriteAllText(myBookPath, sbMb.ToString(), new UTF8Encoding(false));

        if (File.Exists(savePath))
        {
            string saveJson = File.ReadAllText(savePath, Encoding.UTF8);
            var save = ParseJson(saveJson);
            string[] slotKanji = new string[] { "", "一", "二", "三", "四" };
            string canonical = "自定义词书" + (targetSlot >= 1 && targetSlot <= 4 ? slotKanji[targetSlot] : "一");
            string listType = "System.Collections.Generic.List`1[[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]],mscorlib";

            save["ChosenBook_Para"] = new Dictionary<string, object>(StringComparer.Ordinal) {
                { "__type", "string" },
                { "value", canonical }
            };
            save["ChosenBook_List"] = new Dictionary<string, object>(StringComparer.Ordinal) {
                { "__type", listType },
                { "value", words }
            };
            save["SelfBookName" + targetSlot] = new Dictionary<string, object>(StringComparer.Ordinal) {
                { "__type", "string" },
                { "value", "日语词库(猫条版)" }
            };

            var sbSave = new StringBuilder();
            Serialize(save, sbSave, 0);
            File.WriteAllText(savePath, sbSave.ToString(), new UTF8Encoding(false));
        }
        return targetSlot;
    }
}
'@
    Add-Type -TypeDefinition $es3Source -Language CSharp -ErrorAction Stop
}

function Get-InstallerErrorLogPath {
    # 详细的失败原因同时落盘，方便群友直接把日志发给作者排查。
    return (Join-Path $env:USERPROFILE 'AppData\LocalLow\WCP\wcp\installer-error.log')
}

function Write-InstallerErrorLog([string]$text) {
    try {
        $logPath = Get-InstallerErrorLogPath
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logPath) | Out-Null
        [IO.File]::AppendAllText($logPath, ("[{0}] {1}`r`n" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $text), (New-Object Text.UTF8Encoding($false)))
    } catch { }
}

function Show-ExtractFailure([string]$displayName, [string]$detail) {
    # GetAwaiter().GetResult() 只会抛出「发生一个或多个错误」这种聚合消息，
    # 真正的原因（杀毒软件锁定文件、磁盘写入失败等）在内层异常里。
    Write-Host ''
    Write-Host "解压 $displayName 失败的详细原因：" -ForegroundColor Yellow
    Write-Host $detail -ForegroundColor Yellow
    Write-InstallerErrorLog "解压 $displayName 失败：$detail"
    $hint = $null
    if ($detail -match 'UnauthorizedAccessException|拒绝访问|Access is denied|being used by another process|另一个程序正在使用|The process cannot access') {
        $hint = '提示：文件写入被拒绝或占用。最常见原因是杀毒/安全软件正在扫描这些音频文件。' +
            '请把游戏目录和 %USERPROFILE%\AppData\LocalLow\WCP 加入杀毒软件白名单（或暂时退出杀毒软件）后重试。'
    } elseif ($detail -match 'IOException|磁盘空间|There is not enough space| HALT:') {
        if ($detail -notmatch '磁盘空间') { $hint = '提示：可能是磁盘空间不足或磁盘写入错误，请确认相关磁盘剩余空间后重试。' }
    } elseif ($detail -match 'InvalidDataException|ZIP|压缩') {
        $hint = '提示：音频压缩包可能下载不完整或被安全软件改动，请删除 %USERPROFILE%\AppData\LocalLow\WCP\wcp\jpmod_downloads 目录后重试。'
    } elseif ($detail -match 'DirectoryNotFoundException|FileNotFoundException|找不到') {
        $hint = '提示：文件或目录丢失，可能是安全软件隔离了安装文件。请把安装目录加入白名单后重新解压安装包再试。'
    }
    if ($hint) { Write-Host $hint -ForegroundColor Yellow }
    Write-Host "完整错误已写入：$(Get-InstallerErrorLogPath)（排查时请把此文件发给作者）" -ForegroundColor DarkYellow
}

function Expand-ZipWithProgress([string]$zipPath, [string]$destination, [string]$displayName) {
    Ensure-ZipExtractor
    $workers = [Math]::Max(2, [Math]::Min(4, [Environment]::ProcessorCount))
    $attempt = 0
    $maxAttempts = 2
    while ($true) {
        $attempt++
        $session = [WcpJapaneseZipSession]::Start($zipPath, $destination, $workers)
        while (-not $session.TotalReady -and -not $session.Task.IsCompleted) {
            Write-Progress -Activity "解压 $displayName" -Status '正在读取资源清单...' -PercentComplete 0
            Start-Sleep -Milliseconds 100
        }
        $task = $session.Task
        $totalFiles = $session.TotalFiles
        $totalBytes = $session.TotalBytes
        $watch = [Diagnostics.Stopwatch]::StartNew()
        while (-not $task.IsCompleted) {
            $doneFiles = [Math]::Min($session.CompletedFiles, $totalFiles)
            $doneBytes = [Math]::Min($session.CompletedBytes, $totalBytes)
            $percent = if ($totalFiles -gt 0) { [Math]::Min(100, [int](($doneFiles * 100) / $totalFiles)) } else { 100 }
            $speed = if ($watch.Elapsed.TotalSeconds -gt 0) { $doneBytes / 1MB / $watch.Elapsed.TotalSeconds } else { 0 }
            $status = "$percent%  文件 $doneFiles / $totalFiles  $([Math]::Round($doneBytes / 1MB, 1)) / $([Math]::Round($totalBytes / 1MB, 1)) MB  $([Math]::Round($speed, 2)) MB/s  并行线程 $workers"
            Write-Progress -Activity "解压 $displayName" -Status $status -PercentComplete $percent
            Start-Sleep -Milliseconds 250
        }
        try {
            $task.GetAwaiter().GetResult()
            break
        } catch {
            # 保险：任何情况下都把内层异常显示出来，而不是只报「发生一个或多个错误」。
            $detail = $session.GetError()
            if (-not $detail) {
                $inner = $_.Exception
                while ($inner.InnerException) { $inner = $inner.InnerException }
                $detail = $inner.ToString()
            }
            if ($attempt -lt $maxAttempts) {
                Write-Host ''
                Write-Host "解压 $displayName 时遇到错误，正在自动重试（第 $attempt 次失败，通常为杀毒软件临时占用文件）..." -ForegroundColor Yellow
                Write-InstallerErrorLog "解压 $displayName 第 $attempt 次失败（将重试）：$detail"
                Start-Sleep -Seconds 3
                continue
            }
            Show-ExtractFailure $displayName $detail
            throw
        }
    }
    $finalStatus = "100%  文件 $totalFiles / $totalFiles  $([Math]::Round($totalBytes / 1MB, 1)) / $([Math]::Round($totalBytes / 1MB, 1)) MB"
    Write-Progress -Activity "解压 $displayName" -Status $finalStatus -PercentComplete 100
    Write-Progress -Activity "解压 $displayName" -Completed
}

function Copy-TreeNet([string]$sourceDir, [string]$targetDir, [string]$displayName) {
    # PowerShell Copy-Item rejects Windows reserved device names (aux.mp3,
    # nul.mp3, ...). The audio packages legitimately contain such word audio,
    # so this copy uses plain .NET file APIs, which handle those names fine.
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    $count = 0
    foreach ($src in [IO.Directory]::EnumerateFiles($sourceDir, '*', [IO.SearchOption]::AllDirectories)) {
        $rel = $src.Substring($sourceDir.Length).TrimStart('\', '/')
        $dst = [IO.Path]::Combine($targetDir, $rel)
        $dstParent = [IO.Path]::GetDirectoryName($dst)
        if (-not [IO.Directory]::Exists($dstParent)) { [IO.Directory]::CreateDirectory($dstParent) | Out-Null }
        [IO.File]::Copy((Get-ExtendedPath $src), (Get-ExtendedPath $dst), $true)
        $count++
        if (($count % 2000) -eq 0) { Write-Host ("  copied {0} {1} files..." -f $count, $displayName) }
    }
    Write-Host ("{0} copy done, {1} files." -f $displayName, $count)
}

function Get-ExtendedPath([string]$path) {
    $name = [IO.Path]::GetFileName($path)
    if ([string]::IsNullOrEmpty($name)) { return $path }
    $dot = $name.IndexOf('.')
    $stem = if ($dot -ge 0) { $name.Substring(0, $dot) } else { $name }
    $u = $stem.ToUpperInvariant()
    if ($u -eq 'AUX' -or $u -eq 'CON' -or $u -eq 'PRN' -or $u -eq 'NUL') { return ('\\?\' + $path) }
    if (($u.StartsWith('COM') -or $u.StartsWith('LPT')) -and $u.Length -gt 3) {
        $n = 0
        if ([int]::TryParse($u.Substring(3), [ref]$n) -and $n -ge 1 -and $n -le 9) { return ('\\?\' + $path) }
    }
    return $path
}

function Remove-TreeNet([string]$path) {
    try {
        [IO.Directory]::Delete($path, $true)
    } catch {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Backup-PackWithoutAudio([string]$sourceDir, [string]$targetDir) {
    # 备份旧语言资源包时跳过 audio 子树：音频每次安装都会重新下载解压，
    # 旧音频的备份只会让每次重装在磁盘上多堆 1~2 GB，回滚时也用不到。
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    foreach ($item in [IO.Directory]::EnumerateFileSystemEntries($sourceDir)) {
        $name = [IO.Path]::GetFileName($item)
        if ($name -ieq 'audio') { continue }
        $target = Join-Path $targetDir $name
        if ([IO.Directory]::Exists($item)) {
            Copy-TreeNet $item $target ('备份 ' + $name)
        } else {
            [IO.File]::Copy($item, $target, $true)
        }
    }
}

function Remove-LegacyRedundancy {
    # 新版安装器接管旧版本遗留：清理过期下载缓存与多余备份，避免每次
    # 更新都在用户磁盘上堆积数 GB 冗余。所有删除都允许失败（被占用则跳过）。
    param(
        [string]$DataDir,
        $WordAsset,
        $SentenceAsset
    )
    $freed = [int64]0
    # 1) 下载缓存：只保留与当前清单 SHA-256 一致的两个音频包，其余全删
    #    （旧版本安装器留下的同名旧缓存、未完成的 .download 分卷都算冗余）。
    $downloads = Join-Path $DataDir 'jpmod_downloads'
    if (Test-Path -LiteralPath $downloads) {
        $keep = @{}
        foreach ($asset in @($WordAsset, $SentenceAsset)) {
            if ($asset -and $asset.name) { $keep[[string]$asset.name] = [string]$asset.sha256.ToLowerInvariant() }
        }
        foreach ($file in @(Get-ChildItem -LiteralPath $downloads -File -ErrorAction SilentlyContinue)) {
            $isCurrent = $false
            if ($keep.ContainsKey($file.Name)) {
                try { $isCurrent = ((Get-Sha256 $file.FullName) -eq $keep[$file.Name]) } catch { $isCurrent = $false }
            }
            if ($isCurrent) {
                Write-Host ("保留当前版本缓存：" + $file.Name) -ForegroundColor DarkGray
                continue
            }
            $freed += $file.Length
            try {
                Remove-Item -LiteralPath $file.FullName -Force -ErrorAction Stop
            } catch {
                $freed -= $file.Length
            }
        }
    }
    # 2) 旧备份目录：只保留最近 3 份（目录名以时间戳开头，按名称倒序即最新在前）。
    $backupRoot = Join-Path $DataDir 'jpmod_backups'
    $staleBackups = @()
    if (Test-Path -LiteralPath $backupRoot) {
        $staleBackups = @(Get-ChildItem -LiteralPath $backupRoot -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending | Select-Object -Skip 3)
    }
    foreach ($stale in $staleBackups) {
        try {
            $size = [int64]((Get-ChildItem -LiteralPath $stale.FullName -Recurse -File -ErrorAction SilentlyContinue |
                Measure-Object Length -Sum).Sum)
            Remove-TreeNet $stale.FullName
            $freed += $size
            Write-Host ("已清理过期备份：" + $stale.Name) -ForegroundColor DarkGray
        } catch { }
    }
    if ($freed -gt 0) {
        Write-Host ("冗余清理完成，释放约 {0:N2} GB。" -f ($freed / 1GB)) -ForegroundColor DarkGray
    } else {
        Write-Host '没有需要清理的冗余文件。' -ForegroundColor DarkGray
    }
}

Write-Step '开始安装 WCP 日语词书。'

function Add-Candidate([System.Collections.Generic.List[string]]$list, [string]$path) {
    if ([string]::IsNullOrWhiteSpace($path)) { return }
    try { $full = [IO.Path]::GetFullPath($path).TrimEnd('\') } catch { return }
    if (-not $list.Contains($full)) { $list.Add($full) }
}

function Get-SteamRoots {
    $roots = New-Object 'System.Collections.Generic.List[string]'
    foreach ($hive in @('HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam', 'HKLM:\SOFTWARE\Valve\Steam')) {
        try {
            $item = Get-ItemProperty -Path $hive -ErrorAction Stop
            Add-Candidate $roots ([string]$item.SteamPath)
            Add-Candidate $roots ([string]$item.InstallPath)
        } catch {}
    }
    $initial = @($roots)
    foreach ($root in $initial) {
        if (-not [IO.Directory]::Exists($root)) {
            Write-Host "跳过不存在的 Steam 路径：$root" -ForegroundColor DarkYellow
            continue
        }
        $vdf = Join-Path $root 'steamapps\libraryfolders.vdf'
        if (-not (Test-Path -LiteralPath $vdf)) { continue }
        try {
            $raw = Get-Content -LiteralPath $vdf -Raw -ErrorAction Stop
            foreach ($m in [regex]::Matches($raw, '"path"\s*"([^"]+)"')) {
                Add-Candidate $roots ($m.Groups[1].Value -replace '\\\\','\')
            }
        } catch {}
    }
    return @($roots | Where-Object { [IO.Directory]::Exists($_) })
}

function Get-GameCandidates {
    $list = New-Object 'System.Collections.Generic.List[string]'
    Add-Candidate $list $env:WCP_GAME_DIR
    foreach ($root in (Get-SteamRoots)) {
        if (-not [IO.Directory]::Exists($root)) { continue }
        Add-Candidate $list (Join-Path $root 'steamapps\common\WCP-WordGirlgriend')
    }
    foreach ($root in @('C:\Program Files (x86)\Steam\steamapps\common', 'C:\Program Files\Steam\steamapps\common')) {
        Add-Candidate $list (Join-Path $root 'WCP-WordGirlgriend')
    }
    $valid = New-Object 'System.Collections.Generic.List[string]'
    foreach ($candidate in @($list)) {
        if (-not [IO.Directory]::Exists($candidate)) {
            if ($candidate -match '^[A-Za-z]:') {
                Write-Host "跳过不存在的游戏路径：$candidate" -ForegroundColor DarkYellow
            }
            continue
        }
        $managed = Join-Path $candidate 'wcp_Data\Managed\Assembly-CSharp.dll'
        $database = Join-Path $candidate 'wcp_Data\StreamingAssets\wcpFullEng.db'
        if ((Test-Path -LiteralPath $managed) -and (Test-Path -LiteralPath $database)) {
            $valid.Add($candidate)
        }
    }
    return @($valid)
}

function Get-LogGamePath {
    $log = Join-Path $env:USERPROFILE 'AppData\LocalLow\WCP\wcp\Player.log'
    if (-not (Test-Path -LiteralPath $log)) { return $null }
    try {
        $raw = Get-Content -LiteralPath $log -Raw -ErrorAction Stop
        $m = [regex]::Match($raw, "Mono path\[0\] = '([^']+?)[/]wcp_Data[/]Managed'")
        if ($m.Success) { return (($m.Groups[1].Value -replace '/', '\').TrimEnd('\')) }
    } catch {}
    return $null
}

if (Get-Process -Name 'wcp' -ErrorAction SilentlyContinue) {
    Fail '检测到万词破正在运行，请完全退出游戏后再安装。'
}

Write-Step '正在搜索 Steam 游戏目录。'
$candidates = @(Get-GameCandidates)
if ($candidates.Count -eq 0) {
    Fail '没有找到有效的万词破安装目录。请确认 Steam 已安装游戏，或设置 WCP_GAME_DIR 后重试。'
}

$logPath = Get-LogGamePath
$game = $candidates | Where-Object { $_ -eq $logPath } | Select-Object -First 1
if (-not $game) { $game = $candidates | Select-Object -First 1 }
if ($candidates.Count -gt 1 -and -not ($candidates -contains $logPath)) {
    Write-Host '检测到多个有效游戏目录：'
    for ($i = 0; $i -lt $candidates.Count; $i++) { Write-Host "[$($i + 1)] $($candidates[$i])" }
    $choice = Read-Host '请输入要安装的序号（默认 1）'
    if ($choice -match '^[1-9][0-9]*$' -and [int]$choice -le $candidates.Count) { $game = $candidates[[int]$choice - 1] }
}

Write-Step "已找到游戏目录：$game"

$bepRoot = Join-Path $game 'BepInEx'
$payload = Join-Path $PSScriptRoot 'payload'
$plugins = Join-Path $payload 'plugins'
$wcpRoot = Join-Path $env:USERPROFILE 'AppData\LocalLow\WCP'
$data = Join-Path $wcpRoot 'wcp'
$packsPayload = Join-Path $payload 'packs'
$packsRoot = Join-Path $wcpRoot 'packs'
New-Item -ItemType Directory -Force -Path $data | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $data "jpmod_backups\$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null

$bepPayload = Join-Path $payload 'bepinex'
$bepCore = Join-Path $bepRoot 'core\BepInEx.dll'
$bepRootFiles = @('.doorstop_version', 'BepInEx-changelog.txt', 'doorstop_config.ini', 'winhttp.dll')
$needBepFramework = -not (Test-Path -LiteralPath $bepCore)
$needBepBootstrap = @($bepRootFiles | Where-Object { -not (Test-Path -LiteralPath (Join-Path $game $_)) }).Count -gt 0
if ($needBepFramework -or $needBepBootstrap) {
    if (-not (Test-Path -LiteralPath (Join-Path $bepPayload 'BepInEx\core\BepInEx.dll'))) {
        Fail '安装包缺少内置 BepInEx 运行环境。'
    }
    if (Test-Path -LiteralPath $bepRoot) {
        Copy-Item -LiteralPath $bepRoot -Destination (Join-Path $backup 'BepInEx-before-install') -Recurse -Force
    }
    foreach ($name in $bepRootFiles) {
        $existing = Join-Path $game $name
        if (Test-Path -LiteralPath $existing) {
            Copy-Item -LiteralPath $existing -Destination (Join-Path $backup $name) -Force
        }
    }
    foreach ($name in $bepRootFiles) {
        $src = Join-Path $bepPayload "root\$name"
        if (-not (Test-Path -LiteralPath $src)) { Fail "安装包缺少 BepInEx 启动文件：$name" }
        Copy-Item -LiteralPath $src -Destination (Join-Path $game $name) -Force
    }
    if ($needBepFramework) {
        New-Item -ItemType Directory -Force -Path $bepRoot | Out-Null
        Copy-Item -Path (Join-Path $bepPayload 'BepInEx\*') -Destination $bepRoot -Recurse -Force
        Write-Host '已安装内置 BepInEx 5 运行环境。'
    } else {
        Write-Host '已补齐 BepInEx 启动文件，保留现有 BepInEx 核心。'
    }
}

Write-Step '运行环境检查完成，正在读取资源清单。'

$releaseManifestPath = Join-Path $PSScriptRoot 'release-manifest.json'
if (-not (Test-Path -LiteralPath $releaseManifestPath)) { Fail '安装包缺少 release-manifest.json。' }
$release = Get-Content -LiteralPath $releaseManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $release.assets) { Fail 'release-manifest.json 无效。' }
$downloadRoutes = @()
foreach ($route in @($release.download_routes)) {
    if ($null -eq $route) { continue }
    if ($route -is [string]) {
        $template = [string]$route
        $name = $template
        $mode = 'full'
    } else {
        $template = [string]$route.url_template
        if (-not $template) { $template = [string]$route.base_url }
        $name = [string]$route.name
        if (-not $name) { $name = $template }
        $mode = if ($route.mode) { [string]$route.mode } else { 'full' }
    }
    if ($template) {
        $downloadRoutes += [pscustomobject]@{
            Name = $name
            UrlTemplate = $template
            Mode = $mode
        }
    }
}

# Keep accepting manifests produced before download_routes was introduced.
if ($downloadRoutes.Count -eq 0) {
    $legacyBaseUrls = @($release.base_urls)
    if ($legacyBaseUrls.Count -eq 0 -and $release.base_url) {
        $legacyBaseUrls = @($release.base_url)
    }
    foreach ($baseUrl in $legacyBaseUrls) {
        if ($baseUrl) {
            $downloadRoutes += [pscustomobject]@{
                Name = [string]$baseUrl
                UrlTemplate = ([string]$baseUrl).TrimEnd('/') + '/{name}'
                Mode = 'full'
            }
        }
    }
}
if ($downloadRoutes.Count -eq 0) { Fail 'release-manifest.json 没有资源下载地址。' }

function Get-AssetUrl($route, $asset) {
    $name = [Uri]::EscapeDataString([string]$asset.name)
    # A split part may override the route template so one domestic mirror can
    # span multiple Gitee repositories under the same resource Release tag.
    $template = [string]$asset.url_template
    if (-not $template) { $template = [string]$route.UrlTemplate }
    if ($template.Contains('{name}')) {
        return $template.Replace('{name}', $name)
    }
    return $template.TrimEnd('/') + '/' + $name
}

function Test-DownloadRoute([string]$uri) {
    $headRequest = $null
    $headResponse = $null
    $headError = $null
    try {
        $headRequest = [Net.WebRequest]::Create($uri)
        $headRequest.Method = 'HEAD'
        $headRequest.Timeout = 15000
        $headRequest.ReadWriteTimeout = 15000
        $headRequest.UserAgent = 'WCP-Japanese-Installer/1.2.2'
        $headRequest.Proxy = [Net.WebRequest]::DefaultWebProxy
        if ($headRequest.Proxy) { $headRequest.Proxy.Credentials = [Net.CredentialCache]::DefaultCredentials }
        $headResponse = $headRequest.GetResponse()
        $statusCode = [int]$headResponse.StatusCode
        if ($statusCode -ge 200 -and $statusCode -lt 400) {
            return [pscustomobject]@{
                Success = $true
                StatusCode = $statusCode
                Method = 'HEAD'
                Error = $null
            }
        }
        $headError = "HTTP $statusCode"
    } catch {
        $headError = $_.Exception.GetType().Name
    } finally {
        if ($headResponse) { $headResponse.Dispose() }
    }

    # Some mirrors reject HEAD. A one-byte range GET verifies the same route
    # without starting a full multi-gigabyte transfer.
    $rangeRequest = $null
    $rangeResponse = $null
    $rangeStream = $null
    try {
        $rangeRequest = [Net.WebRequest]::Create($uri)
        $rangeRequest.Method = 'GET'
        $rangeRequest.Timeout = 15000
        $rangeRequest.ReadWriteTimeout = 15000
        $rangeRequest.UserAgent = 'WCP-Japanese-Installer/1.2.2'
        $rangeRequest.Proxy = [Net.WebRequest]::DefaultWebProxy
        if ($rangeRequest.Proxy) { $rangeRequest.Proxy.Credentials = [Net.CredentialCache]::DefaultCredentials }
        if ($rangeRequest -is [Net.HttpWebRequest]) { $rangeRequest.AddRange(0, 0) }
        $rangeResponse = $rangeRequest.GetResponse()
        $rangeStream = $rangeResponse.GetResponseStream()
        $probeBuffer = New-Object byte[] 1
        [void]$rangeStream.Read($probeBuffer, 0, 1)
        $statusCode = [int]$rangeResponse.StatusCode
        if ($statusCode -ge 200 -and $statusCode -lt 400) {
            return [pscustomobject]@{
                Success = $true
                StatusCode = $statusCode
                Method = 'GET range'
                Error = $null
            }
        }
        return [pscustomobject]@{
            Success = $false
            StatusCode = $statusCode
            Method = 'GET range'
            Error = "HEAD $headError; HTTP $statusCode"
        }
    } catch {
        return [pscustomobject]@{
            Success = $false
            StatusCode = 0
            Method = 'HEAD/GET range'
            Error = "HEAD $headError; $($_.Exception.GetType().Name)"
        }
    } finally {
        if ($rangeStream) { $rangeStream.Dispose() }
        if ($rangeResponse) { $rangeResponse.Dispose() }
    }
}

function Join-Files([string[]]$paths, [string]$destination) {
    $output = $null
    try {
        $output = [IO.File]::Open($destination, [IO.FileMode]::Create,
            [IO.FileAccess]::Write, [IO.FileShare]::None)
        $buffer = New-Object byte[] (1024 * 1024)
        foreach ($path in $paths) {
            $input = $null
            try {
                $input = [IO.File]::OpenRead($path)
                while (($read = $input.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $output.Write($buffer, 0, $read)
                }
            } finally {
                if ($input) { $input.Dispose() }
            }
        }
        $output.Flush()
    } finally {
        if ($output) { $output.Dispose() }
    }
}

function Download-VerifiedAsset($asset) {
    if (-not $asset.name -or -not $asset.sha256 -or -not $asset.size) { Fail 'Release 资源清单缺少文件信息。' }
    $free = (Get-PSDrive -Name ([IO.Path]::GetPathRoot($data).TrimEnd('\').Substring(0,1))).Free
    if ($free -lt [int64]$asset.size) { Fail "磁盘空间不足，至少需要 $([math]::Ceiling($asset.size / 1GB)) GB 可用空间。" }
    $downloadDir = Join-Path $data 'jpmod_downloads'
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    $target = Join-Path $downloadDir $asset.name
    $valid = $false
    if (Test-Path -LiteralPath $target) {
        $item = Get-Item -LiteralPath $target
        if ($item.Length -eq [int64]$asset.size) {
            $valid = ((Get-Sha256 $target) -eq $asset.sha256.ToLower())
        }
    }
    if (-not $valid) {
        Write-Host "正在选择 $($asset.name) 的可用下载路由，文件较大，请耐心等待..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $downloaded = $false
        $errors = New-Object System.Collections.Generic.List[string]
        $seenUrls = New-Object System.Collections.Generic.HashSet[string]([StringComparer]::OrdinalIgnoreCase)
        $routeIndex = 0
        foreach ($route in $downloadRoutes) {
            $routeIndex++
            $parts = @($asset.parts | Where-Object { $_ })
            $isPartsRoute = ([string]$route.Mode).ToLowerInvariant() -eq 'parts'
            if ($isPartsRoute -and $parts.Count -eq 0) {
                $errors.Add("$($route.Name)：清单没有分卷信息")
                continue
            }
            $probeAsset = if ($isPartsRoute) { $parts[0] } else { $asset }
            $uri = Get-AssetUrl $route $probeAsset
            if (-not $seenUrls.Add($uri)) { continue }
            $probe = Test-DownloadRoute $uri
            if (-not $probe.Success) {
                $errors.Add("$($route.Name)：连通性探测失败（$($probe.Error)）")
                continue
            }
            Write-Host "已选择下载路由：$($route.Name)（$($probe.Method)，HTTP $($probe.StatusCode)）" -ForegroundColor DarkCyan
            $tmp = if ($isPartsRoute) { "$target.part" } else { "$target.route{0:D2}.download" -f $routeIndex }
            if ($isPartsRoute) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
            $partPaths = @()
            $routeSucceeded = $false
            $keepTmpForResume = $false
            try {
                if ($isPartsRoute) {
                    $partIndex = 0
                    foreach ($part in $parts) {
                        $partIndex++
                        $partTarget = "$target.gitee.part{0:D3}" -f $partIndex
                        $partValid = $false
                        if (Test-Path -LiteralPath $partTarget) {
                            $partItem = Get-Item -LiteralPath $partTarget
                            if ($partItem.Length -eq [int64]$part.size) {
                                $partValid = (Get-Sha256 $partTarget) -eq ([string]$part.sha256).ToLowerInvariant()
                            }
                        }
                        if (-not $partValid) {
                            $partUrl = Get-AssetUrl $route $part
                            $partTmp = "$partTarget.download"
                            Remove-Item -LiteralPath $partTmp -Force -ErrorAction SilentlyContinue
                            Download-WithProgress $partUrl $partTmp $part.name ([int64]$part.size)
                            $partActualSize = (Get-Item -LiteralPath $partTmp).Length
                            if ($partActualSize -ne [int64]$part.size) {
                                throw "分卷 $($part.name) 长度不符（实际 $partActualSize / 期望 $($part.size) 字节）"
                            }
                            $partActualHash = Get-Sha256 $partTmp
                            if ($partActualHash -ne ([string]$part.sha256).ToLowerInvariant()) {
                                Remove-Item -LiteralPath $partTmp -Force -ErrorAction SilentlyContinue
                                throw "分卷 $($part.name) SHA-256 不符（实际 $partActualHash）"
                            }
                            Move-Item -LiteralPath $partTmp -Destination $partTarget -Force
                        }
                        $partPaths += $partTarget
                    }
                    Join-Files $partPaths $tmp
                } else {
                    Download-WithProgress $uri $tmp $asset.name ([int64]$asset.size)
                }
                $actualSize = (Get-Item -LiteralPath $tmp).Length
                if ($actualSize -ne [int64]$asset.size) {
                    $keepTmpForResume = $actualSize -lt [int64]$asset.size
                    $errors.Add("$($route.Name)：下载长度不符（实际 $actualSize / 期望 $($asset.size) 字节）")
                    continue
                }
                $actualHash = Get-Sha256 $tmp
                if ($actualHash -eq $asset.sha256.ToLower()) {
                    Move-Item -LiteralPath $tmp -Destination $target -Force
                    if ($isPartsRoute -and $partPaths) {
                        foreach ($partPath in $partPaths) {
                            Remove-Item -LiteralPath $partPath -Force -ErrorAction SilentlyContinue
                        }
                    }
                    $downloaded = $true
                    $routeSucceeded = $true
                    break
                }
                Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
                $errors.Add("$($route.Name)：SHA-256 不符（实际 $actualHash）")
            } catch {
                $keepTmpForResume = $keepTmpForResume -or (Test-Path -LiteralPath $tmp)
                $errors.Add("$($route.Name)：$($_.Exception.GetType().Name)")
            } finally {
                if (-not $routeSucceeded -and -not $keepTmpForResume) {
                    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
                }
            }
        }
        if (-not $downloaded) {
            $detail = if ($errors.Count) { [string]::Join("`n", $errors) } else { '没有可用下载路由。' }
            Fail "资源下载或 SHA-256 校验失败：$($asset.name)`n$detail"
        }
    }
    return $target
}

$wordAsset = $release.assets | Where-Object { $_.kind -eq 'word_audio' } | Select-Object -First 1
$sentenceAsset = $release.assets | Where-Object { $_.kind -eq 'sentence_audio' } | Select-Object -First 1
if (-not $wordAsset -or -not $sentenceAsset) { Fail 'Release 清单没有完整的单词和例句音频资源。' }
$compressedBytes = [int64]0
$expandedBytes = [int64]0
foreach ($asset in @($release.assets)) {
    if ($asset.size) { $compressedBytes += [int64]$asset.size }
    if ($asset.expanded_size) {
        $expandedBytes += [int64]$asset.expanded_size
    } elseif ($asset.size) {
        # Older manifests did not record the expanded ZIP size. The archive
        # sizes are a conservative fallback for the preflight estimate.
        $expandedBytes += [int64]$asset.size
    }
}
$safetyBytes = 1GB
$requiredBytes = $compressedBytes + (2 * $expandedBytes) + $safetyBytes
# 下载预检前先接管旧版本遗留的冗余（过期缓存/旧备份）：
# 清理释放的空间能让磁盘检查更宽松，也让 v1.2.4 之前的用户腾出数 GB。
Write-Step '正在清理旧版本遗留的冗余文件。'
Remove-LegacyRedundancy -DataDir $data -WordAsset $wordAsset -SentenceAsset $sentenceAsset
$downloadDriveName = [IO.Path]::GetPathRoot($data).TrimEnd('\').Substring(0, 1)
$downloadDrive = Get-PSDrive -Name $downloadDriveName
if ($downloadDrive.Free -lt $requiredBytes) {
    Fail "磁盘空间不足：下载缓存、解压临时目录和最终音频同时存在时，预计至少需要 $([Math]::Ceiling($requiredBytes / 1GB)) GB；$($downloadDriveName): 当前仅剩 $([Math]::Round($downloadDrive.Free / 1GB, 2)) GB。缓存位置：$data\jpmod_downloads"
}
Write-Host "磁盘空间检查通过：$($downloadDriveName): 剩余 $([Math]::Round($downloadDrive.Free / 1GB, 2)) GB，预计峰值需要 $([Math]::Round($requiredBytes / 1GB, 2)) GB。" -ForegroundColor DarkGray
$wordZip = Download-VerifiedAsset $wordAsset
$sentenceZip = Download-VerifiedAsset $sentenceAsset
Write-Step '音频资源下载并校验完成，正在解压。'
$stagePattern = 'jpmod_audio_stage*'
foreach ($staleStage in @(Get-ChildItem -LiteralPath $data -Directory -Filter $stagePattern -ErrorAction SilentlyContinue)) {
    try {
        Remove-Item -LiteralPath $staleStage.FullName -Recurse -Force -ErrorAction Stop
        Write-Host "已清理上次安装遗留的临时目录：$($staleStage.Name)" -ForegroundColor DarkGray
    } catch {
        Write-Host "无法清理旧临时目录：$($staleStage.FullName)，本次将使用新的临时目录继续安装。" -ForegroundColor DarkYellow
    }
}
$audioStage = Join-Path $data ("jpmod_audio_stage_{0}_{1}" -f $stamp, ([guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Force -Path $audioStage | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $audioStage 'vocabulary') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $audioStage 'sentence_audio') | Out-Null
Write-Host '正在解压单词音频...'
Expand-ZipWithProgress $wordZip (Join-Path $audioStage 'vocabulary') '单词音频'
Write-Host '正在解压例句音频...'
Expand-ZipWithProgress $sentenceZip (Join-Path $audioStage 'sentence_audio') '例句音频'
Write-Step '音频解压完成，正在安装插件和词书文件。'
$pluginNames = @('WcpHost.dll', 'CustomSlotsMod.dll', 'JpWordListMod.dll',
    'BookNameMod.dll', 'SentenceAudioMod.dll')
foreach ($name in @('MyBook.es3', 'SaveFile.es3')) {
    $src = Join-Path $data $name
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $backup $name) }
}
foreach ($name in $pluginNames) {
    $src = Join-Path $bepRoot "plugins\$name"
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $backup $name) }
}

New-Item -ItemType Directory -Force -Path (Join-Path $bepRoot 'plugins') | Out-Null
foreach ($name in $pluginNames) {
    $src = Join-Path $plugins $name
    if (-not (Test-Path -LiteralPath $src)) { Fail "安装包缺少插件：$name" }
    Copy-Item -LiteralPath $src -Destination (Join-Path $bepRoot "plugins\$name") -Force
}

# The host consumes only the selected language pack.  Merge the bundled JA
# pack without deleting any user-installed FR/RU/DE/other pack.
$jaPackPayload = Join-Path $packsPayload 'ja'
if (-not (Test-Path -LiteralPath (Join-Path $jaPackPayload 'manifest.json'))) {
    Fail '安装包缺少 packs\ja\manifest.json。'
}
$jaPackTarget = Join-Path $packsRoot 'ja'
New-Item -ItemType Directory -Force -Path $packsRoot | Out-Null
if (Test-Path -LiteralPath $jaPackTarget) {
    Backup-PackWithoutAudio $jaPackTarget (Join-Path $backup 'packs\ja')
}
Copy-TreeNet $jaPackPayload $jaPackTarget '日语语言资源包'
# 运行时补丁所有权登记：宿主（WcpHost）运行时也会写这份文件，安装阶段先写好，
# 免得"装完第一次进游戏"仍是新旧两个词表插件同时打补丁 —— 后写者胜会把上一本书
# 的词串进新书（"俄语切日语后还出俄语"）。只追加不覆盖：其它语言安装器登记过的
# 语言保留，宿主启动后还会按"资源是否就绪"再校正一次。
$managedMarker = Join-Path (Join-Path $bepRoot 'config') 'WcpHost.managed.txt'
$managedLangs = @()
if (Test-Path -LiteralPath $managedMarker) {
    Copy-Item -LiteralPath $managedMarker -Destination (Join-Path $backup 'WcpHost.managed.txt') -Force
    $managedLangs = @(Get-Content -LiteralPath $managedMarker | Where-Object { $_ -match '^[a-z]{2,3}$' })
}
if ($managedLangs -notcontains 'ja') { $managedLangs = @($managedLangs) + 'ja' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $managedMarker) | Out-Null
[IO.File]::WriteAllLines($managedMarker, [string[]]$managedLangs, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ('已登记宿主接管语言：' + ($managedLangs -join ', ')) -ForegroundColor DarkGray

$bookDir = Join-Path $payload 'books'
Get-ChildItem -LiteralPath $bookDir -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $data $_.Name) -Force
}
$repairDir = Join-Path $data 'jp_db_payload'
New-Item -ItemType Directory -Force -Path $repairDir | Out-Null
Get-ChildItem -LiteralPath (Join-Path $payload 'jp_db_payload') -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $repairDir $_.Name) -Force
}
$jaWordAudio = Join-Path $jaPackTarget 'audio\word'
$jaSentenceAudio = Join-Path $jaPackTarget 'audio\sentence'
Copy-TreeNet (Join-Path $audioStage 'vocabulary') $jaWordAudio '日语单词音频'
Copy-TreeNet (Join-Path $audioStage 'sentence_audio') $jaSentenceAudio '日语例句音频'
try {
    Remove-TreeNet $audioStage
    Write-Host '音频临时目录已清理。' -ForegroundColor DarkGray
} catch {
    Write-Host "音频临时目录未能自动清理：$audioStage；不影响安装结果。" -ForegroundColor DarkYellow
}

$bookPayloadPath = Join-Path $payload 'catbar_book.json'
if (-not (Test-Path -LiteralPath $bookPayloadPath)) { Fail '安装包缺少 catbar_book.json。' }

Ensure-Es3Helper

$myBookPath = Join-Path $data 'MyBook.es3'
$savePath = Join-Path $data 'SaveFile.es3'

# 1. 自动检测并修复历史受损存档（针对旧版脚本序列化导致丢失 __type 或开局剧情重置的问题）
$repairedSave = ''
if ([WcpEs3Helper]::TryRepairSaveFile($savePath, $data, [ref]$repairedSave)) {
    Write-Host "检测到历史存档受损（元数据丢失/开局剧情重置），已自动从完整备份成功恢复：$repairedSave" -ForegroundColor Green
}
$repairedMb = ''
if ([WcpEs3Helper]::TryRepairMyBook($myBookPath, $data, [ref]$repairedMb)) {
    Write-Host "检测到 MyBook.es3 元数据受损，已自动恢复：$repairedMb" -ForegroundColor Green
}

# 2. 安全写入日语词书与当前选中词书（完整保留全部存档元数据与 __type）
Write-Step '正在写入日语词书并设置当前选中词书。'
if (Test-Path -LiteralPath $myBookPath) {
    $targetSlot = [WcpEs3Helper]::InstallBookAndSave($myBookPath, $savePath, $bookPayloadPath, 0)
    Write-Host "已写入日语词书槽位 $targetSlot，已安全保留全部存档元数据并选中该词书。"
} else {
    Write-Host '没有找到 MyBook.es3，已安装插件和导入文件；请先启动游戏完成一次初始化，再重新运行安装器自动导入。' -ForegroundColor Yellow
}

$marker = [ordered]@{ installed = (Get-Date).ToString('s'); game = $game; backup = $backup; profile = $bookPayload.id; words = $words.Count }
[IO.File]::WriteAllText((Join-Path $data 'jpmod_install.json'), ($marker | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
Write-Host "游戏目录: $game"
Write-Host "备份目录: $backup"
Write-Host '安装成功。'
Write-Step '全部安装步骤已完成。'
