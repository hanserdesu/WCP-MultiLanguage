import sys, io
sys.path.insert(0, r"D:/Japanese/wcp_wordbooks/tools")
import ildump
pe = ildump.pe
targets = ["S8TestWordList_DailyStudy_Finished", "S8TestWordList_DailyStudy_left"]
for t in pe.net.mdtables.TypeDef.rows:
    tn = str(t.TypeName)
    for m in t.MethodList:
        name = str(m.row.Name)
        if not m.row.ImplFlags.miIL or m.row.Rva == 0:
            continue
        buf = io.StringIO()
        saved = sys.stdout
        sys.stdout = buf
        try:
            ildump.dump_method(m.row)
        except Exception:
            sys.stdout = saved
            continue
        sys.stdout = saved
        text = buf.getvalue()
        hits = [s for s in targets if s in text]
        if hits:
            print(tn + "::" + name + " -> " + ",".join(hits))
