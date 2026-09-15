import sys
import dnfile
from dncil.cil.body import CilMethodBody
from dncil.cil.error import MethodBodyFormatError
from dncil.clr.token import Token, StringToken, InvalidToken
from dncil.cil.body.reader import CilMethodBodyReaderBase

import wcp_paths

DLL = str(wcp_paths.managed_dll())

pe = dnfile.dnPE(DLL)


class Reader(CilMethodBodyReaderBase):
    def __init__(self, pe, row):
        self.pe = pe
        self.rva = row.Rva
        self.offset = self.pe.get_offset_from_rva(self.rva)

    def read(self, n):
        data = self.pe.get_data(self.pe.get_rva_from_offset(self.offset), n)
        self.offset += n
        return data

    def tell(self):
        return self.offset

    def seek(self, o):
        self.offset = o
        return self.offset


def resolve_token(tok):
    if isinstance(tok, StringToken):
        try:
            return '"' + str(pe.net.user_strings.get(tok.rid).value) + '"'
        except Exception as e:
            try:
                return '"' + str(pe.net.user_strings.get(tok.rid)) + '"'
            except Exception:
                return f'<str rid={tok.rid}>'
    table = pe.net.mdtables.tables.get(tok.table)
    if table is None:
        return str(tok)
    try:
        row = table.rows[tok.rid - 1]
    except Exception:
        return str(tok)
    name = getattr(row, 'Name', None)
    parent = ''
    if hasattr(row, 'Class'):
        try:
            parent = str(row.Class.row.TypeName) + '::'
        except Exception:
            pass
    if hasattr(row, 'TypeName'):
        parent = ''
    if name is None:
        return str(tok)
    return f'{parent}{name}'


def dump_method(row, indent='    '):
    if not row.ImplFlags.miIL or row.Flags.mdAbstract or row.Rva == 0:
        return
    try:
        body = CilMethodBody(Reader(pe, row))
    except MethodBodyFormatError as e:
        print(indent, 'ERR', e)
        return
    for insn in body.instructions:
        op = str(insn.opcode)
        operand = ''
        if insn.operand is not None:
            if isinstance(insn.operand, Token):
                operand = resolve_token(insn.operand)
            else:
                operand = str(insn.operand)
        print(f'{indent}{insn.offset - body.offset:04X}  {op:<14} {operand}')


def main():
    want_types = sys.argv[1].split(',') if len(sys.argv) > 1 and sys.argv[1] else []
    want_methods = sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[2] else []
    for t in pe.net.mdtables.TypeDef.rows:
        tn = str(t.TypeName)
        if want_types and tn.lower() not in want_types:
            continue
        print(f'\n===== TYPE {t.TypeNamespace}.{tn} =====')
        for m in t.MethodList:
            mname = str(m.row.Name)
            if want_methods and mname.lower() not in want_methods:
                continue
            print(f'\n--- METHOD {tn}::{mname} ---')
            dump_method(m.row)


if __name__ == '__main__':
    main()
