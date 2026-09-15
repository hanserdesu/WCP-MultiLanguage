"""Compile the actual sentence-audio scope guard against isolated game doubles.

No game process, saved games, or deployed DLLs are modified. The doubles isolate
identity storage; the production guard and slot parser are extracted verbatim.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
PREFIX = r"""using System; using System.Collections.Generic; using System.IO;
class BookProfile { public string Id; public string Language; }
static class BookProfiles { public const string French="fr"; public static BookProfile Match(IList<string> x) { return x!=null && x.Count==2 && x[0]=="bonjour" && x[1]=="merci" ? new BookProfile {Id="fr",Language="fr"} : null; } }
static class MyParameters { public static string ChosenBook_Para; public static List<string> ChosenBook_List; }
static class Application { public static string persistentDataPath="scratch"; }
static class ES3 { public static string Selected; public static string[] Words; public static T Load<T>(string key, T defaultValue) { return (T)(object)Selected; } public static T Load<T>(string key,string path) { return (T)(object)Words; } }
class Probe {
"""
SUFFIX = r"""static void Check(bool result, string name) { if(!result) throw new Exception(name); Console.WriteLine("PASS " + name); }
static void Main() { var p=new Probe(); MyParameters.ChosenBook_Para="自定义词书二"; ES3.Selected=MyParameters.ChosenBook_Para; ES3.Words=new[]{"bonjour","merci"}; MyParameters.ChosenBook_List=new List<string>(ES3.Words);
Check(p.ManagedFrenchBookSelected(),"registered in slot 2");
MyParameters.ChosenBook_List[0]="other"; Check(!p.ManagedFrenchBookSelected(),"same reference and count mutation rejected");
MyParameters.ChosenBook_List[0]="bonjour"; Check(p.ManagedFrenchBookSelected(),"restored content revalidated");
ES3.Words[0]="other"; Check(!p.ManagedFrenchBookSelected(),"same-slot disk replacement rejected");
ES3.Words[0]="bonjour"; ES3.Selected="自定义词书一"; Check(!p.ManagedFrenchBookSelected(),"selected disk mismatch rejected");
MyParameters.ChosenBook_List=null; Check(!p.ManagedFrenchBookSelected(),"null list fails closed"); }
}
"""


class RuntimeScopeTests(unittest.TestCase):
    @unittest.skipUnless(CSC.exists(), "Windows .NET Framework C# compiler required")
    def test_actual_sentence_scope_guard(self):
        source = (ROOT / "mod_sentence_audio_fr" / "SentenceAudioFrMod.cs").read_text(
            encoding="utf-8-sig"
        )
        start = source.index("        private bool ManagedFrenchBookSelected()")
        end = source.index("        // 把游戏自带的", start)
        with tempfile.TemporaryDirectory(prefix="wcp-fr-scope-") as directory:
            probe = Path(directory) / "ScopeProbe.cs"
            executable = Path(directory) / "ScopeProbe.exe"
            probe.write_text(PREFIX + source[start:end] + SUFFIX, encoding="utf-8-sig")
            subprocess.run(
                [str(CSC), "/nologo", "/out:" + str(executable), str(probe)],
                check=True, capture_output=True,
            )
            result = subprocess.run([str(executable)], check=True, capture_output=True)
            self.assertEqual(result.stdout.count(b"PASS "), 6, result.stdout)


if __name__ == "__main__":
    unittest.main()
