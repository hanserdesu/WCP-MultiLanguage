"""Report zip storage details for an existing resource zip."""

import sys
import zipfile

NAMES = {0: "ZIP_STORED", 8: "ZIP_DEFLATED", 12: "ZIP_BZIP2", 14: "ZIP_LZMA"}

for path in sys.argv[1:]:
    with zipfile.ZipFile(path) as z:
        info = z.infolist()[0]
        modes = {i.compress_type for i in z.infolist()}
        print(path)
        print("  compress types:", {NAMES.get(m, m) for m in modes})
        print("  first entry   :", info.filename, "date_time=", info.date_time, "external_attr=", oct(info.external_attr))
        print("  has dirs      :", any(i.is_dir() for i in z.infolist()))
        print("  zipfile comment:", z.comment[:40])
