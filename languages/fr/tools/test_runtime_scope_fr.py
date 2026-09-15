"""Compile real runtime methods with storage/audio stubs; never access game saves."""
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")


def method(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    source = (ROOT / "mod_fr_wordlist/FrWordListMod.cs").read_text(encoding="utf-8-sig")
    actual = method(source, "private static bool BaselineBelongsToOwnedBook(")
    books = json.loads((ROOT / "output/french_books.json").read_text(encoding="utf-8"))
    words = list(dict.fromkeys(e["word"] for entries in books["levels"].values() for e in entries))
    harness = r'''using System;
using System.Collections.Generic;
using System.IO;
using WcpBookProfiles;
static class Application { public static string persistentDataPath = "unused"; }
static class MyParameters { public static string ChosenBook_Para = "Japanese"; }
static class ES3 {
 public static string[] Words;
 public static T Load<T>(string key, string path) { return (T)(object)Words; }
}
class Probe {
 const string OwnedSourceSlotKey = "owned";
 static int LoadInt(string key, int fallback) { return 2; }
 static int SelfBookIndexOf(string name) { return 1; }
 ACTUAL
 static void Check(bool test, string name) { if (!test) throw new Exception(name); }
 static void Main(string[] args) {
  ES3.Words = File.ReadAllLines(args[0]);
  Check(BookProfiles.Match(ES3.Words) != null, "fixture fingerprint");
  Check(!BaselineBelongsToOwnedBook(new[] { "猫", "犬" }), "Japanese baseline survives");
  MyParameters.ChosenBook_Para = "English";
  Check(!BaselineBelongsToOwnedBook(new[] { "the", "cat" }), "English baseline survives");
  Check(BaselineBelongsToOwnedBook(new[] { "être", "coing" }), "French residue detected after switch");
  Check(!BaselineBelongsToOwnedBook(new string[0]), "empty baseline valid");
  ES3.Words = new[] { "猫", "犬" };
  Check(!BaselineBelongsToOwnedBook(new[] { "猫" }), "replaced source slot not French");
  Console.WriteLine("PASS: real C# baseline isolation, 5 cases");
 }
}'''.replace("ACTUAL", actual)
    with tempfile.TemporaryDirectory(prefix="fr-scope-") as tmp:
        folder = Path(tmp)
        (folder / "Probe.cs").write_text(harness, encoding="utf-8-sig")
        (folder / "words.txt").write_text("\n".join(words), encoding="utf-8")
        subprocess.run([str(CSC), "/nologo", "/langversion:5", "/codepage:65001",
                        "/out:" + str(folder / "Probe.exe"), str(folder / "Probe.cs"),
                        str(ROOT / "mod_fr_wordlist/BookProfiles.cs")], check=True)
        subprocess.run([str(folder / "Probe.exe"), str(folder / "words.txt")], check=True)


if __name__ == "__main__":
    main()
