// probe0.cs -- minimal: can ES3 be driven outside Unity at all?
// Pure ASCII. Writes findings to the file given as argv[1].
using System;
using System.IO;
using System.Reflection;
using System.Text;

class Probe0
{
    static StringBuilder log = new StringBuilder();
    static string managed = @"E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\Managed";

    static void Main(string[] args)
    {
        string outPath = args[0];
        AppDomain.CurrentDomain.AssemblyResolve += Resolve;
        try
        {
            Run();
        }
        catch (Exception e)
        {
            L("FATAL " + e.GetType().Name + ": " + e.Message);
            L(e.StackTrace);
        }
        File.WriteAllText(outPath, log.ToString(), new UTF8Encoding(false));
    }

    static Assembly Resolve(object sender, ResolveEventArgs a)
    {
        string name = new AssemblyName(a.Name).Name;
        string p = Path.Combine(managed, name + ".dll");
        if (File.Exists(p)) return Assembly.LoadFrom(p);
        return null;
    }

    static void L(string s) { log.AppendLine(s); }

    static void Run()
    {
        Assembly fp = Assembly.LoadFrom(Path.Combine(managed, "Assembly-CSharp-firstpass.dll"));
        L("loaded firstpass: " + fp.FullName);
        Type es3 = fp.GetType("ES3", false);
        L("ES3 type = " + (es3 == null ? "null" : es3.FullName));
        Type es3s = fp.GetType("ES3Settings", false);
        L("ES3Settings type = " + (es3s == null ? "null" : es3s.FullName));
        Type es3f = fp.GetType("ES3File", false);
        L("ES3File type = " + (es3f == null ? "null" : es3f.FullName));

        // step 1: can we touch ES3Settings.defaultSettings ?
        try
        {
            PropertyInfo dp = es3s.GetProperty("defaultSettings", BindingFlags.Public | BindingFlags.Static);
            object d = dp.GetValue(null, null);
            L("defaultSettings = " + (d == null ? "null" : d.ToString()));
            if (d != null)
            {
                FieldInfo pf = es3s.GetField("path");
                L("  path = " + pf.GetValue(d));
                FieldInfo lf = es3s.GetField("location");
                L("  location = " + lf.GetValue(d));
                FieldInfo cf = es3s.GetField("compressionType");
                L("  compressionType = " + cf.GetValue(d));
                FieldInfo ef = es3s.GetField("encryptionType");
                L("  encryptionType = " + ef.GetValue(d));
            }
        }
        catch (Exception e)
        {
            Exception c = e.InnerException ?? e;
            L("defaultSettings FAILED: " + c.GetType().Name + ": " + c.Message);
        }

        // step 2: enum names of ES3+Location
        try
        {
            Type loc = fp.GetType("ES3+Location", false);
            L("Location = " + (loc == null ? "null" : string.Join(",", Enum.GetNames(loc))));
        }
        catch (Exception e) { L("Location FAILED: " + e.Message); }
    }
}
