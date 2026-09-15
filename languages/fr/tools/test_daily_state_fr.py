"""法语词书每日学习队列的离线回归检查。

这份小模型对应 FrWordListMod.RepairDailyQueue 的状态不变量，
用于防止“总表 100、已完成 2、剩余 0”再次被当作合法完成状态。
它不读取或写入用户存档。
"""


def repair(total, left, finished, complete, mode="每日学习", need=None):
    total_unique = list(dict.fromkeys(word for word in total if word))
    total_set = set(total_unique)
    finished_set = {word for word in finished if word in total_set}
    remaining = list(left or [])
    expected = [word for word in total_unique if word not in finished_set]
    changed = False

    if remaining != expected:
        remaining = expected
        changed = True

    if remaining and complete:
        complete = False
        changed = True
    elif not remaining and len(finished_set) >= len(total_set) and not complete:
        complete = True
        changed = True

    if mode in ("每日学习", "每日复习") and list(need or []) != remaining:
        need = list(remaining)
        changed = True

    return remaining, complete, need, changed


def main():
    total = ["w%03d" % i for i in range(100)]
    remaining, complete, need, changed = repair(
        total, [], ["w000", "w001"], True, need=[]
    )
    assert changed
    assert len(remaining) == 98
    assert not complete
    assert need == remaining

    remaining, complete, need, changed = repair(
        total, [], total, True, need=[]
    )
    assert not changed
    assert remaining == []
    assert complete
    assert need == []

    # 非空但明显残缺的 left 也必须按总表 - Finished 修复，不能只修复空队列。
    remaining, complete, need, changed = repair(
        total, ["w002", "w003", "w002"], ["w000", "w001"], False,
        need=["w002", "w003"]
    )
    assert changed
    assert remaining == total[2:]
    assert not complete
    assert need == remaining

    # left 中含已完成词或未知词同样是不变量破坏。
    remaining, complete, need, changed = repair(
        total, ["w000", "ghost"], ["w000"], False, need=["w000", "ghost"]
    )
    assert changed
    assert remaining == total[1:]
    assert need == remaining

    print("PASS: daily queue repair invariants")


if __name__ == "__main__":
    main()
