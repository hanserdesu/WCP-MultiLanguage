import sys, io
sys.path.insert(0, r"D:/Japanese/wcp_wordbooks/tools")
import ildump
pe = ildump.pe

def dump(type_name, method_names):
    tds = pe.net.mdtables.TypeDef.rows
    out = []
    for idx, t in enumerate(tds):
        if str(t.TypeName) != type_name:
            continue
        start = t.MethodList.row_index - 1
        end = tds[idx+1].MethodList.row_index - 1 if idx+1 < len(tds) else len(pe.net.mdtables.MethodDef.rows)
        for m in pe.net.mdtables.MethodDef.rows[start:end]:
            name = str(m.Name)
            if method_names and name not in method_names:
                continue
            out.append("=== %s.%s ===" % (type_name, name))
            buf = io.StringIO()
            saved = sys.stdout
            sys.stdout = buf
            try:
                ildump.dump_method(m)
            finally:
                sys.stdout = saved
            out.append(buf.getvalue())
    return "\n".join(out)

tn = sys.argv[1] if len(sys.argv) > 1 else "SetInputFieldValueS8"
mn = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else []
print(dump(tn, mn))
