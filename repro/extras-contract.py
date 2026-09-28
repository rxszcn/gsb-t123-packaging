"""同一份 extra 名字在不同入口上的判法读数表。

跑法：PYTHONPATH=src .venv/bin/python repro/extras-contract.py

读数分组：
  L_  同一个名字在每个入口分别是「接受」还是「拒」
  W_  写法：哪一处保留解析到的拼法，哪一处给规范形，哪一处不许把名字改成别的
  C_  比较：两种只在规范形上相同的写法认不认得是同一个（含同一份列表里撞车）
  E_  拒的时候有没有点到那个名字本身
  X_  两处以上对同一个名字给的不是同一句判法
  K_  别的读法、别的字段不受这条判据影响
  T_  往返之后判法与写法不变
  Z_  整表跑两遍，前一格有没有留下状态
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # pragma: no cover
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from packaging.markers import Marker  # noqa: E402
from packaging.metadata import Metadata, parse_email  # noqa: E402
from packaging.requirements import Requirement  # noqa: E402
from packaging.utils import canonicalize_name  # noqa: E402

# 合法名字：三处都该认，比较走规范形，写法照各自的既有约定。
LEGAL = ["test", "B_a", "ba.r", "Foo--Bar", "S_P__A_M", "1"]
# 不是名字的写法：要求侧与声明侧该拒；标记侧照样收，但不许改写成另一个名字。
ILLEGAL = ["_a", "a_", "-a", "a-", "a b", "_"]
NAMES = LEGAL + ILLEGAL

DOC_BASE = {"metadata_version": "2.4", "name": "n", "version": "1.0"}

cells = []


def cell(label, want, get) -> None:
    cells.append((label, want, get))


def doc(**fields):
    return {**DOC_BASE, **fields}


def flat(exc):
    """把聚合报错连它的来龙去脉摊平成一份错误清单。"""
    pending = [exc]
    seen = set()
    while pending:
        cur = pending.pop(0)
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        subs = getattr(cur, "exceptions", None)
        if subs:
            pending.extend(subs)
        else:
            yield cur
        cause = getattr(cur, "__cause__", None)
        if cause is not None:
            pending.append(cause)


def outcome(make) -> str:
    """这一处对这份输入给的是接受还是拒（不看错型）。"""
    try:
        make()
        return "接受"
    except BaseException as exc:  # noqa: BLE001
        return f"拒:{type(exc).__name__}"


def meta_outcome(raw) -> str:
    try:
        Metadata.from_raw(raw)
        return "接受"
    except BaseException as exc:  # noqa: BLE001
        fields = sorted({f for e in flat(exc) if (f := getattr(e, "field", None))})
        tail = "[" + ",".join(fields) + "]" if fields else ""
        return f"拒:{type(exc).__name__}{tail}"


def named(make, spelling: str) -> str:
    """拒的时候有没有点到那个名字本身。"""
    try:
        make()
        return "接受"
    except BaseException as exc:  # noqa: BLE001
        text = " / ".join(str(e) for e in flat(exc))
        head = text.splitlines()[0][:90]
        if spelling and spelling in text and "BRACKET" not in text:
            return "点名"
        return f"没点名[{head}]"


def message_of(make, needle: str) -> str:
    try:
        make()
    except BaseException as exc:  # noqa: BLE001
        first = str(exc).splitlines()[0]
        return first if needle in str(exc) else f"不是那句[{first}]"
    return "接受"


def req_of(name: str):
    return lambda: Requirement(f"foo[{name}]")


def marker_of(name: str):
    return lambda: Marker(f'extra == "{name}"')


def provides_of(name: str):
    return lambda: Metadata.from_raw({**DOC_BASE, "provides_extra": [name]})


def req_readout(name: str) -> str:
    return f"{name!r}:" + outcome(req_of(name))


def marker_readout(name: str) -> str:
    return f"{name!r}:" + outcome(marker_of(name))


def provides_readout(name: str) -> str:
    return f"{name!r}:" + outcome(provides_of(name))


def marker_spelling(name: str) -> str:
    """标记侧把这个名字写成了什么。"""
    try:
        written = str(Marker(f'extra == "{name}"'))
    except BaseException as exc:  # noqa: BLE001
        return f"拒:{type(exc).__name__}"
    if written == f'extra == "{name}"':
        return "原样"
    return f"改写成{written}"


def same_two(name: str) -> str:
    readings = {
        "要求": outcome(req_of(name)),
        "声明": outcome(provides_of(name)),
    }
    if len({v.split(":")[0] for v in readings.values()}) == 1:
        return "两处同"
    return "分歧[" + " ".join(f"{k}={v}" for k, v in readings.items()) + "]"


def same_three(name: str) -> str:
    """要求侧与声明侧都该拒，标记侧该原样留着。"""
    readings = {
        "要求": outcome(req_of(name)),
        "声明": outcome(provides_of(name)),
        "标记": marker_spelling(name),
    }
    if (
        readings["要求"].startswith("拒")
        and readings["声明"].startswith("拒")
        and readings["标记"] == "原样"
    ):
        return "三处同"
    return "分歧[" + " ".join(f"{k}={v}" for k, v in readings.items()) + "]"


def both_reject(first, second) -> str:
    a, b = outcome(first), outcome(second)
    return "两个都拒" if a.startswith("拒") and b.startswith("拒") else f"分歧[{a}|{b}]"


def keep_dependency_groups() -> str:
    try:
        return f'accepted: {Marker(chr(34) + "a." + chr(34) + " in dependency_groups")}'
    except BaseException as exc:  # noqa: BLE001
        return f"拒:{type(exc).__name__}"


def doc_roundtrip() -> str:
    raw = doc(provides_extra=["B_a"], requires_dist=["bar[B_a]", "baz[b-a]"])
    md = Metadata.from_raw(raw)
    again = Metadata.from_raw(parse_email(str(md.as_rfc822()))[0])
    before = (list(md.provides_extra), [str(r) for r in md.requires_dist])
    after = (list(again.provides_extra), [str(r) for r in again.requires_dist])
    return "稳定" if before == after else f"变了{before}→{after}"


# ---------------------------------------------------------------- L：各处接受集
for _name in NAMES:
    _illegal = _name in ILLEGAL
    cell(f"L_req_{_name}", f"{_name!r}:拒*" if _illegal else f"{_name!r}:接受",
         lambda n=_name: req_readout(n))
    cell(f"L_provides_{_name}", f"{_name!r}:拒*" if _illegal else f"{_name!r}:接受",
         lambda n=_name: provides_readout(n))
    # 标记侧收任意字符串，这条判据不改变它。
    cell(f"L_marker_{_name}", f"{_name!r}:接受", lambda n=_name: marker_readout(n))

cell('L_marker_空名字', "接受", lambda: outcome(lambda: Marker('extra == ""')))
cell('L_provides_空名字', "拒*", lambda: meta_outcome({**DOC_BASE, "provides_extra": [""]}))
cell('L_req_空extras', "接受", lambda: outcome(lambda: Requirement("foo[]")))
cell('L_要求字段里写非法名也要拒', "拒:ExceptionGroup[requires-dist]",
     lambda: meta_outcome(doc(requires_dist=["bar[a_]"])))

# ---------------------------------------------------------------- W：写法
cell('W_req_extras_保留原拼法', "{'B_a'}", lambda: str(Requirement("foo[B_a]").extras))
cell('W_req_str_保留原拼法', "foo[B_a]", lambda: str(Requirement("foo[B_a]")))
cell('W_req_str_保留点分', "foo[ba.r]", lambda: str(Requirement("foo[ba.r]")))
cell('W_provides_读出给规范形', "['b-a']",
     lambda: str(Metadata.from_raw({**DOC_BASE, "provides_extra": ["B_a"]}).provides_extra))
cell('W_文档里要求行保留原拼法', "[('requires-dist', 'bar[B_a]')]",
     lambda: str([kv for kv in Metadata.from_raw(doc(requires_dist=["bar[B_a]"]))
                  .as_rfc822().items() if kv[0] == "requires-dist"]))
cell('W_文档里声明行给规范形', "[('provides-extra', 'b-a')]",
     lambda: str([kv for kv in Metadata.from_raw(doc(provides_extra=["B_a"]))
                  .as_rfc822().items() if kv[0] == "provides-extra"]))
for _name in LEGAL:
    cell(f"W_marker_规范形_{_name}", f'extra == "{canonicalize_name(_name)}"',
         lambda n=_name: str(Marker(f'extra == "{n}"')))
for _name in ILLEGAL:
    cell(f"W_marker_不改写_{_name}", "原样", lambda n=_name: marker_spelling(n))
cell('W_marker_成员写法_规范形_S_P__A_M', '"s-p-a-m" in extras',
     lambda: str(Marker('"S_P__A_M" in extras')))
cell('W_marker_成员写法_不改写_a_', '"a_" in extras',
     lambda: str(Marker('"a_" in extras')))
cell('W_marker_嵌套_str_给规范形',
     '(extra == "foo-bar" or extra == "baz") and python_version >= "3"',
     lambda: str(Marker('(extra == "Foo_Bar" or extra == "Baz") and python_version >= "3"')))
cell('W_要求里的marker按marker写法渲染', 'foo[test]; extra == "b-a"',
     lambda: str(Requirement("foo[test]; extra=='B_a'")))
cell('W_要求里的marker不改写非法名', 'foo[test]; extra == "_a"',
     lambda: str(Requirement("foo[test]; extra=='_a'")))

# ---------------------------------------------------------------- C：比较与撞车
for _a, _b in [("B_a", "b-a"), ("ba.r", "ba-r"), ("Foo--Bar", "foo-bar")]:
    cell(
        f"C_req_{_a}",
        "比较同／读出不同",
        lambda a=_a, b=_b: (
            ("比较同" if Requirement(f"foo[{a}]") == Requirement(f"foo[{b}]") else "比较不同")
            + "／"
            + (
                "读出不同"
                if Requirement(f"foo[{a}]").extras != Requirement(f"foo[{b}]").extras
                else "读出同"
            )
        ),
    )
cell('C_marker_两种拼法认得同一个', "同",
     lambda: "同" if Marker('extra == "B_a"') == Marker('extra == "b-a"') else "不同")
cell('C_marker_成员写法认得同一个', "同",
     lambda: "同" if Marker('"Foo_Bar" in extras') == Marker('"foo-bar" in extras') else "不同")
cell('C_marker_非法写法不与别的写法混同', "不同",
     lambda: "不同" if Marker('extra == "_a"') != Marker('extra == "-a"') else "同")
cell('C_marker_环境侧非法写法不混同', "False",
     lambda: str(Marker('extra == "_a"').evaluate({"extra": "-a"})))
cell('C_marker_环境侧非法写法照原样匹配', "True",
     lambda: str(Marker('extra == "_a"').evaluate({"extra": "_a"})))
cell('C_marker_环境侧合法名仍按规范形匹配', "True",
     lambda: str(Marker('extra == "b-a"').evaluate({"extra": "B_a"})))
cell('C_marker_成员写法环境侧不混同', "False",
     lambda: str(Marker('"_a" in extras').evaluate({"extras": {"-a"}})))
cell('C_req_同一份列表撞车', "拒*", lambda: outcome(lambda: Requirement("foo[B_a, b-a]")))
cell('C_req_同一份列表撞车_点分', "拒*",
     lambda: outcome(lambda: Requirement("foo[ba.r, ba-r]")))
cell('C_provides_声明列表撞车', "拒*",
     lambda: meta_outcome({**DOC_BASE, "provides_extra": ["B_a", "b-a"]}))
cell('C_provides_声明列表撞车_点分', "拒*",
     lambda: meta_outcome({**DOC_BASE, "provides_extra": ["a.b", "a-b"]}))
cell('C_要求字段列表撞车', "拒:ExceptionGroup[requires-dist]",
     lambda: meta_outcome(doc(requires_dist=["bar[B_a, b-a]"])))
cell('C_声明与要求的同一名字同拼法两处都收', "接受",
     lambda: meta_outcome(doc(provides_extra=["B_a"], requires_dist=["bar[B_a]"])))
cell('C_声明与要求的同一名字两种拼法也收', "接受",
     lambda: meta_outcome(doc(provides_extra=["B_a"], requires_dist=["bar[b-a]"])))

# ---------------------------------------------------------------- E：报错点名
cell('E_req_下划线开头', "点名", lambda: named(req_of("_a"), "_a"))
cell('E_req_尾部下划线', "点名", lambda: named(req_of("a_"), "a_"))
cell('E_req_同一份列表撞车', "点名",
     lambda: named(lambda: Requirement("foo[B_a, b-a]"), "B_a"))
cell('E_provides_下划线开头', "点名", lambda: named(provides_of("_a"), "_a"))
cell('E_要求字段_下划线开头', "点名",
     lambda: named(lambda: Metadata.from_raw(doc(requires_dist=["bar[_a]"])), "_a"))
cell('E_声明列表撞车要点名', "点名",
     lambda: named(lambda: Metadata.from_raw({**DOC_BASE, "provides_extra": ["B_a", "b-a"]}),
                   "B_a"))

# ---------------------------------------------------------------- X：跨处同判
for _name in NAMES:
    cell(f"X_要求与声明同判_{_name}", "两处同", lambda n=_name: same_two(n))
for _name in ILLEGAL:
    cell(f"X_非法名三处同判_{_name}", "三处同", lambda n=_name: same_three(n))

cell('X_撞车判据两份列表都要有', "两处都拒",
     lambda: (
         "两处都拒"
         if meta_outcome(doc(provides_extra=["B_a", "b-a"],
                             requires_dist=["bar[B_a, b-a]"]))
         == "拒:ExceptionGroup[provides-extra,requires-dist]"
         else "分歧"
     ))
cell('X_两份列表里的同一名字都算撞车', "两个都拒",
     lambda: both_reject(lambda: Requirement("foo[B_a, b-a]"),
                         lambda: Metadata.from_raw({**DOC_BASE,
                                                    "provides_extra": ["B_a", "b-a"]})))

# ---------------------------------------------------------------- K：不受这条判据影响
cell('K_标记侧任意字符串仍可解析', "接受",
     lambda: outcome(lambda: Marker("extra == 'things @#4 dsfd ((('")))
cell('K_标记侧任意字符串两份都收', "两个都接受",
     lambda: (
         "两个都接受"
         if outcome(lambda: Marker("extra == 'literally any string can go here'")) == "接受"
         and outcome(lambda: Marker("extra == 'things @#4 dsfd ((('")) == "接受"
         else "分歧"
     ))
cell('K_项目名里的下划线照旧', "foo-bar.quux_bAz",
     lambda: Requirement("foo-bar.quux_bAz>=1").name)
cell('K_缺逗号那句照旧', "Expected comma between extra names",
     lambda: message_of(lambda: Requirement("name[bar baz]"),
                        "Expected comma between extra names"))
cell('K_未闭合括号那句照旧', "Expected matching RIGHT_BRACKET for LEFT_BRACKET, after extras",
     lambda: message_of(lambda: Requirement("name[bar, baz"), "Expected matching RIGHT_BRACKET"))
cell('K_尾逗号那句照旧', "Expected extra name after comma",
     lambda: message_of(lambda: Requirement("name[bar, baz,]"),
                        "Expected extra name after comma"))
cell('K_依赖组成员写法照旧归一', 'accepted: "a-" in dependency_groups',
     keep_dependency_groups)
cell('K_extra与变量比较不判名', "extra == os_name", lambda: str(Marker("extra == os_name")))
cell('K_版本变量不受影响', 'python_version == "3.10"',
     lambda: str(Marker('python_version == "3.10"')))
cell('K_环境侧空extra仍可求值', "False", lambda: str(Marker('extra == "test"').evaluate()))
cell('K_空extras仍是空集', "set()", lambda: str(Requirement("foo[]").extras))
cell('K_req_extras仍可当set用', "True",
     lambda: str(isinstance(Requirement("foo[B_a]").extras, set)))
cell('K_文档其它字段不受影响', ">=3.8",
     lambda: str(Metadata.from_raw(doc(requires_python=">=3.8")).requires_python))

# ---------------------------------------------------------------- T：往返
cell('T_req_pickle_往返_拼法与判据不变', "{'B_a'} foo[B_a] 同",
     lambda: (
         lambda r: f"{r.extras} {r} {'同' if r == Requirement('foo[b-a]') else '不同'}"
     )(pickle.loads(pickle.dumps(Requirement("foo[B_a]")))))
cell('T_marker_pickle_往返_规范形不变', 'extra == "b-a"',
     lambda: str(pickle.loads(pickle.dumps(Marker('extra == "B_a"')))))
cell('T_marker_pickle_往返_不改写的名字不变', 'extra == "_a"',
     lambda: str(pickle.loads(pickle.dumps(Marker('extra == "_a"')))))
cell('T_文档往返_仍合法', "稳定", doc_roundtrip)
cell('T_非法名两处仍同一句判法', "两个都拒",
     lambda: both_reject(lambda: Metadata.from_raw(doc(requires_dist=["bar[_a]"])),
                         lambda: Requirement("foo[_a]")))


# ---------------------------------------------------------------- 收格
def matches(want: str, got: str) -> bool:
    return got.startswith(want[:-1]) if want.endswith("*") else want == got


def sweep():
    out = []
    for _label, _want, get in cells:
        try:
            out.append(get())
        except BaseException as exc:  # noqa: BLE001
            out.append(
                f"读数取不出:{type(exc).__name__}:{str(exc).splitlines()[0][:80]}"
            )
    return out


first_pass = sweep()
second_pass = sweep()

groups: dict[str, list[int]] = {}
passed = 0
for (label, want, _get), got in zip(cells, first_pass, strict=True):
    hit = matches(want, str(got))
    passed += int(hit)
    key = label.split("_")[0]
    tally = groups.setdefault(key, [0, 0])
    tally[1] += 1
    tally[0] += int(hit)
    print(
        ("PASS " if hit else "FAIL ")
        + label.ljust(50, " ")
        + ("" if hit else f"  want={want}  got={str(got)[:200]}")
    )

drift = [
    f"{cells[i][0]}: {a}→{b}"
    for i, (a, b) in enumerate(zip(first_pass, second_pass, strict=True))
    if a != b
]
total = len(cells) + 1
passed += int(not drift)
print(
    ("PASS " if not drift else "FAIL ")
    + "Z_整表跑两遍读数一致".ljust(50, " ")
    + ("" if not drift else f"  got=第二遍变了 {' | '.join(drift)[:200]}")
)

for key, (good, count) in sorted(groups.items()):
    print(f"组 {key} {good}/{count}")
print(f"合计 {passed}/{total}")
