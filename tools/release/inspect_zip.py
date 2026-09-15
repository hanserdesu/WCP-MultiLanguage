"""Inspect a resource zip: entry count, layout, sizes."""

import collections
import sys
import zipfile


def main(path):
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        total = sum(i.file_size for i in infos)
        print(f"{path}")
        print(f"  entries      : {len(infos)}")
        print(f"  uncompressed : {total / 1024 / 1024:.1f} MB")
        print(f"  compressed   : {sum(i.compress_size for i in infos) / 1024 / 1024:.1f} MB")
        print(f"  top-level    : {dict(collections.Counter(n.split(chr(47))[0] for n in names).most_common(5))}")
        ext = collections.Counter(n.rsplit(".", 1)[-1].lower() for n in names if "." in n)
        print(f"  extensions   : {dict(ext.most_common(5))}")
        print("  first 6      :")
        for n in names[:6]:
            print("      ", n)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
        print()
