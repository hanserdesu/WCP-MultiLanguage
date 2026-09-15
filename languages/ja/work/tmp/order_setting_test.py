# -*- coding: utf-8 -*-
"""Model check for JpWordListPlugin.OrderByTestSetting (v1.7.4).

The plugin re-orders rebuilt/re-sampled test pools by the panel's
"正序/倒序/随机 + 未测词优先". This mirrors chooseWordManager.TestWordPos/Neg/Ran
(and the *Off variants) and asserts the plugin order equals the game's order.
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

# word -> (testTimes, lastStudyTime)
LEARNED = {
    "a": (3, 500),
    "b": (1, 900),
    "c": (1, 100),
    "d": (5, 300),
    "e": (3, 700),
    "f": (0, 400),
}


def order(cand, priority, mode):
    """Mirror JpWordListPlugin.OrderByTestSetting (random uses a fixed seed here)."""
    out = list(cand)
    if mode == "随机":
        import random
        random.Random(7).shuffle(out)
        return out
    if priority:
        key = (lambda w: (LEARNED[w][0], -LEARNED[w][1])) if mode == "倒序" \
            else (lambda w: (LEARNED[w][0], LEARNED[w][1]))
    elif mode == "倒序":
        key = lambda w: (-LEARNED[w][0],)
    else:
        key = lambda w: (LEARNED[w][1],)
    return sorted(out, key=key)


def game(name):
    """chooseWordManager.TestWord* orderings (primary, secondary)."""
    if name == "TestWordPos":
        return sorted(LEARNED, key=lambda w: (LEARNED[w][0], LEARNED[w][1]))
    if name == "TestWordNeg":
        return sorted(LEARNED, key=lambda w: (LEARNED[w][0], -LEARNED[w][1]))
    if name == "TestWordPosOff":
        return sorted(LEARNED, key=lambda w: (LEARNED[w][1],))
    if name == "TestWordNegOff":
        return sorted(LEARNED, key=lambda w: (-LEARNED[w][0],))
    raise AssertionError(name)


ok = [True]


def check(name, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", name))
    ok[0] = ok[0] and bool(cond)


cases = [
    ("未测词优先 + 正序", True, "正序", "TestWordPos"),
    ("未测词优先 + 倒序", True, "倒序", "TestWordNeg"),
    ("未测词优先 + 随机", True, "随机", None),
    ("非优先 + 正序", False, "正序", "TestWordPosOff"),
    ("非优先 + 倒序", False, "倒序", "TestWordNegOff"),
    ("非优先 + 随机", False, "随机", None),
]

cand = list(LEARNED)
for label, priority, mode, ref in cases:
    got = order(cand, priority, mode)
    if ref is None:
        check("%s -> pure shuffle (same multiset)" % label, sorted(got) == sorted(cand))
    else:
        want = game(ref)
        print("   %s -> %s" % (label, got))
        check("%s matches %s" % (label, ref), got == want)

print()
print("RESULT:", "ALL PASS" if ok[0] else "FAILED")
sys.exit(0 if ok[0] else 1)
