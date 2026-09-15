import sys, io
sys.path.insert(0, r"D:/Japanese/wcp_wordbooks/tools")
import ildump
pe = ildump.pe

def dump(type_name, method_names):
    out = []
    for t in pe.net.mdtables.TypeDef.rows:
        tn = str(t.TypeName)
        if tn != type_name:
            continue
        for m in t.MethodList:
            name = str(m.row.Name)
            if method_names and name not in method_names:
                continue
            out.append("=== " + tn + "::" + name + " ===")
            buf = io.StringIO()
            saved = sys.stdout
            sys.stdout = buf
            try:
                ildump.dump_method(m.row)
            finally:
                sys.stdout = saved
            out.append(buf.getvalue())
    return chr(10).join(out)

tn = sys.argv[1] if len(sys.argv) > 1 else "SetInputFieldValueS8"
mn = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else []
print(dump(tn, mn))
