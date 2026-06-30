[rtk] /!\ No hook installed — run `rtk init -g` for automatic token savings
﻿"""
knowledge_base.py 鈥?椤圭洰鐭ヨ瘑搴?v2.0
====================================
鍒嗕袱灞傞殧绂?Agent 骞昏椋庨櫓锛?
  curated/  鈫?浜虹被缂栧啓锛屽缁堟敞鍏ヤ笂涓嬫枃锛?00% 淇′换锛?  auto/     鈫?Agent 鑷姩鐢熸垚锛屾敞鍏ユ椂甯﹁鍛婃爣璁帮紙鍙兘骞昏锛?
鐩綍锛?  knowledge/
  鈹溾攢鈹€ curated/
  鈹?  鈹溾攢鈹€ standards.md   缂栫爜瑙勮寖
  鈹?  鈹溾攢鈹€ glossary.md    棰嗗煙璇嶆眹琛?  鈹?  鈹斺攢鈹€ gotchas.md     绉嶅瓙韪╁潙缁忛獙锛堜汉绫荤紪鍐欙級
  鈹斺攢鈹€ auto/
      鈹溾攢鈹€ gotchas.md     Agent 鑷姩褰掓。鐨勫潙
      鈹溾攢鈹€ decisions.md   Agent 鐢熸垚鐨勬灦鏋勫喅绛?      鈹溾攢鈹€ postmortems.md Agent 鐢熸垚鐨勬晠闅滃鐩?      鈹斺攢鈹€ _manifest.json 鏉＄洰绱㈠紩锛堣皝銆佷綍鏃躲€佹槸鍚﹀凡瀹℃煡锛?"""

import json
import re
import threading
from datetime import datetime
from pathlib import Path

KB_DIR = Path("knowledge")
_manifest_lock = threading.Lock()  # _record_in_manifest 骞跺彂淇濇姢
CURATED_DIR = KB_DIR / "curated"
AUTO_DIR    = KB_DIR / "auto"
MANIFEST_PATH = AUTO_DIR / "_manifest.json"

# curated/ 绔犺妭锛堜汉绫荤紪鍐欙紝缁濆淇′换锛?CURATED_SECTIONS = {
    "standards": "standards.md",
    "glossary":  "glossary.md",
    "gotchas":   "gotchas.md",  # 绉嶅瓙鏁版嵁锛屼笉鍚?Agent 鑷姩鍐欏叆
    "project": "silver-vitality-overview.md",
    "schema": "schema.md",
}

# auto/ 绔犺妭锛圓gent 鐢熸垚锛屽彲鑳藉寘鍚够瑙夛級
AUTO_SECTIONS = {
    "decisions":   "decisions.md",
    "gotchas":     "gotchas.md",
    "project": "silver-vitality-overview.md",
    "postmortems": "postmortems.md",
}

# 姣忎釜瑙掕壊璇诲彇鐨勭煡璇嗗簱绔犺妭锛堟爣娉ㄦ潵婧愮被鍨嬶級
ROLE_KB_SECTIONS = {
    # 鈺愨晲 纭紪鐮?fallback锛坮ole_registry 涓嶅彲鐢ㄦ椂浣跨敤锛?鈺愨晲
    # 姣忎釜瑙掕壊閮借鍙栧綋鍓嶉」鐩杩?    "pm":        [("curated", "project"), ("auto", "decisions"), ("curated", "gotchas"), ("auto", "gotchas")],
    "product":   [("curated", "project"), ("auto", "decisions"), ("curated", "glossary")],
    "architect": [("curated", "project"), ("auto", "decisions"), ("curated", "standards"), ("curated", "gotchas"), ("auto", "gotchas")],
    "ux":        [("curated", "project"), ("curated", "standards"), ("curated", "glossary")],
    "frontend":  [("curated", "project"), ("curated", "standards"), ("curated", "gotchas"), ("auto", "gotchas")],
    "backend":   [("curated", "project"), ("curated", "standards"), ("curated", "gotchas"), ("auto", "gotchas"), ("auto", "decisions")],
    "dba":       [("curated", "project"), ("auto", "decisions"), ("curated", "gotchas"), ("auto", "gotchas")],
    "devops":    [("curated", "project"), ("auto", "decisions"), ("curated", "gotchas"), ("auto", "gotchas")],
    "debug":     [("curated", "project"), ("curated", "gotchas"), ("auto", "gotchas"), ("auto", "postmortems")],
    "reviewer":  [("curated", "project"), ("curated", "standards")],
    "tester":    [("curated", "project"), ("curated", "standards"), ("curated", "gotchas"), ("auto", "gotchas")],
}

# 鈹€鈹€ 鍒濆鍖?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def init_knowledge_base(project_name: str = "") -> None:
    """鍒濆鍖栫煡璇嗗簱锛屽垱寤?curated/ 鍜?auto/ 鐩綍缁撴瀯銆?""
    CURATED_DIR.mkdir(parents=True, exist_ok=True)
    AUTO_DIR.mkdir(parents=True, exist_ok=True)

    # 鈥斺€?curated/ 鈥斺€?    curated_defaults = {
        "standards.md": _default_standards(),
        "gotchas.md":   _default_gotchas(),
        "glossary.md":  "# 棰嗗煙璇嶆眹琛╘n\n锛堟殏鏃犺褰曪級\n",
    }
    for filename, content in curated_defaults.items():
        path = CURATED_DIR / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    # 鈥斺€?auto/ 鈥斺€?    for filename in AUTO_SECTIONS.values():
        path = AUTO_DIR / filename
        if not path.exists():
            path.write_text(f"# {path.stem}\n\n锛堟殏鏃犺嚜鍔ㄧ敓鎴愭潯鐩級\n", encoding="utf-8")

    # 鈥斺€?manifest 鈥斺€?    if not MANIFEST_PATH.exists():
        MANIFEST_PATH.write_text(json.dumps({
            "project": project_name or "鏈懡鍚?,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "entries": [],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] 鐭ヨ瘑搴撳凡鍒濆鍖栵細{KB_DIR}/ (curated + auto)")


# 鈹€鈹€ 璇诲彇 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def read_section(section: str, source: str = "curated") -> str:
    """璇诲彇鎸囧畾鏉ユ簮鐨勭珷鑺傚唴瀹广€俿ource = 'curated' | 'auto'"""
    sections_map = CURATED_SECTIONS if source == "curated" else AUTO_SECTIONS
    base_dir = CURATED_DIR if source == "curated" else AUTO_DIR
    filename = sections_map.get(section)
    if not filename:
        return f"[閿欒] 鏈煡绔犺妭锛歿section}"
    path = base_dir / filename
    if not path.exists():
        return f"[{section}] 绔犺妭涓嶅瓨鍦?
    return path.read_text(encoding="utf-8")


def build_kb_context(role: str) -> str:
    """
    涓烘寚瀹氳鑹叉瀯寤虹煡璇嗗簱涓婁笅鏂囥€?    - curated/ 鍐呭涓嶅姞璀﹀憡锛堜汉绫荤紪鍐欙級
    - auto/ 鍐呭鏍囨敞銆屾湭缁忎汉宸ュ鏌ワ紝浠呬緵鍙傝€冦€?    鑷姩瑙ｆ瀽鍒悕銆?    """
    try:
        from role_registry import resolve_role as _resolve
        role = _resolve(role) or role
    except ImportError:
        pass
    try:
        from role_registry import get_role_kb_sections as _get_sections
        sections = _get_sections(role)
    except ImportError:
        sections = ROLE_KB_SECTIONS.get(role, [])
    if not sections:
        return ""

    parts = []
    for source, sec in sections:
        content = read_section(sec, source)
        lines = content.split("\n")
        # 杩囨护绌鸿鍜屾枃浠剁骇鏍囬锛? 锛夛紝淇濈暀鏉＄洰绾ф爣棰橈紙##锛夊拰鍐呭
        body_lines = [l for l in lines if l.strip() and not re.match(r'^# [^#]', l)]
        if not body_lines or body_lines[0].startswith("锛堟殏鏃?):
            continue

        preview = "\n".join(body_lines[:15])
        if len(body_lines) > 15:
            preview += f"\n... [鍏?{len(body_lines)} 琛岋紝瀹屾暣鍐呭瑙?knowledge/{source}/{sec}.md]"

        if source == "curated":
            parts.append(f"[鐭ヨ瘑搴擄細{sec}]\n{preview}")
        else:
            parts.append(f"[鑷姩瀛樻。锛歿sec} 鈥斺€?[!] 浠ヤ笅涓?Agent 鑷姩鐢熸垚锛屾湭缁忎汉宸ュ鏌ワ紝鍙兘鏈夎锛屼粎渚涘弬鑰僝\n{preview}")

    return "\n\n".join(parts) if parts else ""


# 鈹€鈹€ 鍐欏叆锛坈urated/ 鈥?浜虹被缁存姢锛夆攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def update_standards(section: str, content: str) -> None:
    """鏇存柊缂栫爜瑙勮寖銆備汉绫绘搷浣滐紝鍐欏叆 curated/銆?""
    path = CURATED_DIR / "standards.md"
    _ensure_exists(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n### {section}\n{content}\n")
    print(f"[OK] 瑙勮寖宸叉洿鏂帮紙curated锛夛細{section}")


def add_glossary(term: str, definition: str, example: str = "") -> None:
    """娣诲姞棰嗗煙璇嶆眹銆備汉绫绘搷浣滐紝鍐欏叆 curated/銆?""
    path = CURATED_DIR / "glossary.md"
    _ensure_exists(path)
    entry = f"\n**{term}**锛歿definition}"
    if example:
        entry += f"锛堜緥锛歿example}锛?
    entry += "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


# 鈹€鈹€ 鍐欏叆锛坅uto/ 鈥?Agent 鑷姩鐢熸垚锛夆攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _record_in_manifest(file: str, title: str, added_by: str) -> None:
    """鍦?manifest 涓褰曚竴鏉¤嚜鍔ㄧ敓鎴愭潯鐩紙渚夸簬瀹℃煡锛夈€傜嚎绋嬪畨鍏ㄣ€?""
    if not MANIFEST_PATH.exists():
        return
    with _manifest_lock:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        entry = {
            "file":      file,
            "title":     title,
            "added_at":  datetime.now().isoformat(timespec="seconds"),
            "added_by":  added_by,
            "reviewed":  False,
        }
        manifest.setdefault("entries", []).append(entry)
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def add_adr(title: str, context: str, decision: str,
            consequences: str, status: str = "宸查噰绾?) -> None:
    """娣诲姞鏋舵瀯鍐崇瓥璁板綍銆侫gent 璋冪敤锛屽啓鍏?auto/銆?""
    path = AUTO_DIR / "decisions.md"
    _ensure_exists(path)

    content = path.read_text(encoding="utf-8")
    adr_count = content.count("## ADR-") + 1

    entry = f"""
## ADR-{adr_count:03d}锛歿title}

**鐘舵€?*锛歿status}
**鏃ユ湡**锛歿datetime.now().strftime('%Y-%m-%d')}
**鏉ユ簮**锛欰gent 鐢熸垚锛屽緟瀹℃煡

**鑳屾櫙**锛歿context}

**鍐崇瓥**锛歿decision}

**褰卞搷**锛歿consequences}

---
"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    _record_in_manifest("auto/decisions.md", f"ADR-{adr_count:03d}锛歿title}", "agent")
    print(f"[OK] ADR-{adr_count:03d} 宸茶褰曪紙auto锛夛細{title}")


def add_gotcha(title: str, symptom: str, cause: str,
               solution: str, affected_roles: list = None) -> None:
    """
    璁板綍韪╁潙缁忛獙銆侫gent 璋冪敤锛堝 QA鈫扗BG 寰幆锛夛紝鍐欏叆 auto/銆?    濡傞渶鍔犲叆 curated/锛屼汉绫诲鏌ュ悗璋冪敤 promote_to_curated()銆?    """
    path = AUTO_DIR / "gotchas.md"
    _ensure_exists(path)

    roles_str = "銆?.join(affected_roles) if affected_roles else "閫氱敤"
    entry = f"""
## {title}

**褰卞搷瑙掕壊**锛歿roles_str}
**鏃ユ湡**锛歿datetime.now().strftime('%Y-%m-%d')}
**鏉ユ簮**锛欰gent 鑷姩鐢熸垚锛屽緟瀹℃煡

**鐥囩姸**锛歿symptom}

**鏍瑰洜**锛歿cause}

**瑙ｅ喅鏂规**锛歿solution}

---
"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    _record_in_manifest("auto/gotchas.md", title, "agent")
    print(f"[OK] 鍧戝凡璁板綍锛坅uto锛夛細{title}")


def add_postmortem(incident: str, timeline: str, root_cause: str,
                   impact: str, action_items: list) -> None:
    """璁板綍鏁呴殰澶嶇洏銆侫gent 璋冪敤锛屽啓鍏?auto/銆?""
    path = AUTO_DIR / "postmortems.md"
    _ensure_exists(path)

    items_str = "\n".join(f"  - [ ] {item}" for item in action_items)
    entry = f"""
## {incident}

**鏃ユ湡**锛歿datetime.now().strftime('%Y-%m-%d')}
**褰卞搷**锛歿impact}
**鏉ユ簮**锛欰gent 鐢熸垚锛屽緟瀹℃煡

**鏃堕棿绾?*锛歿timeline}

**鏍瑰洜**锛歿root_cause}

**琛屽姩椤?*锛?{items_str}

---
"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    _record_in_manifest("auto/postmortems.md", incident, "agent")
    print(f"[OK] 鏁呴殰澶嶇洏宸茶褰曪紙auto锛夛細{incident}")


# 鈹€鈹€ 瀹℃煡涓庢彁鍗?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def list_pending_review() -> list[dict]:
    """鍒楀嚭鎵€鏈夊緟浜哄伐瀹℃煡鐨?auto/ 鏉＄洰銆?""
    if not MANIFEST_PATH.exists():
        return []
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [e for e in manifest.get("entries", []) if not e.get("reviewed")]


def promote_to_curated(file: str, entry_title: str) -> bool:
    """
    浜哄伐瀹℃煡鍚庯紝灏?auto/ 涓殑鏉＄洰鎻愬崌鍒?curated/銆?    浠?auto 鏂囦欢鍒犻櫎璇ユ潯鐩紝杩藉姞鍒板搴旂殑 curated 鏂囦欢銆?    """
    # 纭畾 auto 鍜?curated 璺緞
    auto_path = AUTO_DIR / (file.split("/")[-1] if "/" in file else file)
    section_name = auto_path.stem  # e.g. "gotchas"
    curated_path = CURATED_DIR / f"{section_name}.md"

    if not auto_path.exists():
        print(f"[ERROR] auto 鏂囦欢涓嶅瓨鍦細{auto_path}")
        return False

    # 浠?auto 鏂囦欢涓彁鍙栬鏉＄洰
    content = auto_path.read_text(encoding="utf-8")
    pattern = rf"## {re.escape(entry_title)}.*?(?=## |\Z)"
    m = re.search(pattern, content, re.DOTALL)
    if not m:
        print(f"[ERROR] 鏈壘鍒版潯鐩細{entry_title}")
        return False

    # 杩藉姞鍒?curated锛堝幓鎺夈€孉gent 鐢熸垚銆嶆爣璁帮級
    entry = m.group(0).replace("**鏉ユ簮**锛欰gent 鐢熸垚锛屽緟瀹℃煡\n", "")
    _ensure_exists(curated_path)
    with open(curated_path, "a", encoding="utf-8") as f:
        f.write(entry)

    # 浠?auto 鏂囦欢涓Щ闄?    new_content = content[:m.start()] + content[m.end():]
    auto_path.write_text(new_content, encoding="utf-8")

    # 鏇存柊 manifest锛堢嚎绋嬪畨鍏級
    if MANIFEST_PATH.exists():
        with _manifest_lock:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            for e in manifest.get("entries", []):
                if e.get("title") == entry_title and file in e.get("file", ""):
                    e["reviewed"] = True
                    e["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
                    break
            MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] 宸叉彁鍗囧埌 curated锛歿entry_title}")
    return True


# 鈹€鈹€ 榛樿鍐呭锛堜汉绫荤紪鍐欙級鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _default_standards() -> str:
    return """# 缂栫爜瑙勮寖

> 鎵€鏈夋垚鍛橀伒瀹堟湰瑙勮寖銆侰R锛堜唬鐮佸鏌ュ憳锛夊湪 Review 鏃朵互姝や负鍩哄噯銆?
## 閫氱敤瑙勮寖

- **鍛藉悕**锛氬彉閲?鍑芥暟鐢?camelCase锛圝S/TS锛夋垨 snake_case锛圥ython锛夛紝绫荤敤 PascalCase
- **鍑芥暟闀垮害**锛氬崟涓嚱鏁颁笉瓒呰繃 50 琛岋紝瓒呰繃鍒欐媶鍒?- **娉ㄩ噴**锛氬叕鍏卞嚱鏁板繀椤绘湁 docstring/JSDoc锛屽鏉傞€昏緫蹇呴』鏈夎鍐呮敞閲?- **榄旀硶鏁板瓧**锛氱姝紝鎻愬彇涓哄叿鍚嶅父閲?- **閿欒澶勭悊**锛氫笉鍏佽绌?catch锛岃嚦灏戣褰曟棩蹇?- **鎻愪氦淇℃伅**锛歚[绫诲瀷] 绠€鐭弿杩癭锛岀被鍨嬩负 feat/fix/refactor/test/docs/chore

## 鍓嶇瑙勮寖锛團E锛?
- 缁勪欢鏂囦欢锛歅ascalCase锛屾瘡鏂囦欢涓€涓粍浠?- Props 蹇呴』鏈夌被鍨嬪０鏄庯紙TypeScript 鎴?PropTypes锛?- 绂佹鍦ㄧ粍浠跺唴鐩存帴璋冪敤 API锛岀粺涓€閫氳繃 service 灞?- CSS锛氫娇鐢ㄩ」鐩害瀹氱殑 CSS-in-JS 鎴?CSS Module锛岀姝㈠唴鑱旀牱寮忥紙闄ゅ姩鎬佸€硷級
- 鎵€鏈夌敤鎴疯緭鍏ュ繀椤诲仛 XSS 闃叉姢
- 姣忎釜缁勪欢蹇呴』鏈夊搴旂殑鍗曞厓娴嬭瘯鏂囦欢锛?.test.tsx锛?
## 鍚庣瑙勮寖锛圔E锛?
- API 鍝嶅簲鏍煎紡缁熶竴锛歚{"data": ..., "code": 0, "msg": "ok"}`
- 閿欒鐮佸畾涔夊湪 `constants/errors.py` 涓紝绂佹纭紪鐮?- 鏁版嵁搴撴搷浣滃繀椤婚€氳繃 ORM锛岀姝㈡嫾鎺?SQL 瀛楃涓?- 鏁忔劅瀛楁锛堝瘑鐮併€乼oken锛夌姝㈠嚭鐜板湪鏃ュ織涓?- 鎵€鏈夊閮ㄨ緭鍏ュ繀椤荤粡杩?Pydantic/Zod 绛夋牎楠?- 姣忎釜 service 鏂规硶蹇呴』鏈夊崟鍏冩祴璇曪紝瑕嗙洊姝ｅ悜+寮傚父璺緞

## 鏁版嵁搴撹鑼冿紙DBA/BE锛?
- 琛ㄥ悕锛氬鏁?snake_case锛坲sers, order_items锛?- 蹇呭～瀛楁锛歩d銆乧reated_at銆乽pdated_at
- 澶栭敭瀛楁鍛藉悕锛歚{table_name}_id`
- 绱㈠紩鍛藉悕锛歚idx_{table}_{field}`
- Migration 蹇呴』鍖呭惈鍥炴粴鑴氭湰

## 娴嬭瘯瑙勮寖锛圦A/FE/BE锛?
- 鍗曞厓娴嬭瘯瑕嗙洊鐜囩洰鏍囷細鏍稿績閫昏緫 鈮?80%
- 娴嬭瘯鍛藉悕锛歚test_[琚祴鍑芥暟]_[鍦烘櫙]_[棰勬湡缁撴灉]`
- 绂佹鍦ㄦ祴璇曚腑杩炴帴鐪熷疄鏁版嵁搴擄紝浣跨敤 mock 鎴栨祴璇曟暟鎹簱
- 姣忎釜 Bug 淇蹇呴』闄勫甫鍥炲綊娴嬭瘯鐢ㄤ緥
"""


def _default_gotchas() -> str:
    """浜虹被缂栧啓鐨勭瀛愬潙锛孉gent 涓嶄細鑷姩鏀硅繖閲屻€?""
    return """# 宸茬煡鍧戜笌瑙ｅ喅鏂规

> 浠ヤ笅涓轰汉绫绘暣鐞嗙殑绉嶅瓙缁忛獙銆侫gent 鑷姩褰掓。鐨勫潙鍦?auto/gotchas.md銆?
## 澶фā鍨嬭緭鍑烘牸寮忎笉绋冲畾

**褰卞搷瑙掕壊**锛氶€氱敤
**鏃ユ湡**锛?026-05-12
**鏉ユ簮**锛氫汉宸ユ€荤粨

**鐥囩姸**锛歀LM 杈撳嚭涓?<dag> JSON 鏍煎紡閿欒銆乻tate_update 瑙ｆ瀽澶辫触銆佸伓灏斾笉鎸夋ā鏉胯緭鍑?
**鏍瑰洜**锛氶潪鎺ㄧ悊妯″瀷锛坱emperature=0锛夎緭鍑轰粛鏈夐殢鏈烘€э紱鎺ㄧ悊妯″瀷鍦ㄩ暱涓婁笅鏂囦笅浼氥€岄仐蹇樸€嶆牸寮忚姹?
**瑙ｅ喅鏂规**锛?1. 鍏抽敭鏍囩锛?dag>銆?state_update>锛夌敤鐙珛浠ｇ爜鍧楀寘瑁?2. runner 灞傜殑 _extract_dag / parse_state_update 姘歌繙鏈?fallback 閫昏緫
3. 瀵?JSON 瀛楁鍋?json.JSONDecodeError 瀹归敊

---

## Sub_requests 寰幆鐖嗙偢

**褰卞搷瑙掕壊**锛歅M, UX, ARCHITECT
**鏃ユ湡**锛?026-05-12
**鏉ユ簮**锛氫汉宸ユ€荤粨

**鐥囩姸**锛欰gent A 鍙?sub_request 缁?Agent B锛孉gent B 鍐嶅彂 sub_request 缁?Agent C锛?瀵艰嚧 token 娑堣€楀墽澧炪€佽秴鏃?
**鏍瑰洜**锛歴ub_request 宓屽璋冪敤锛屾病鏈夋繁搴﹂檺鍒?
**瑙ｅ喅鏂规**锛?1. MAX_SUB_REQUESTS=3 闄愬埗鍗?Agent 鍙戣捣鐨?sub_request 鏁伴噺
2. sub_request 涓嶉€掑綊锛坃handle_sub_requests 涓嶅鐞?sub agent 杈撳嚭涓殑 sub_requests锛?3. 濡傛灉淇℃伅涓嶈冻锛孉gent 搴斿湪杈撳嚭涓爣娉ㄣ€岀己灏?XXX锛屽缓璁笅娓歌ˉ鍏呫€?
---

## 宸ュ叿璋冪敤姝诲惊鐜?
**褰卞搷瑙掕壊**锛欶RONTEND, BACKEND, DEVOPS
**鏃ユ湡**锛?026-05-12
**鏉ユ簮**锛氫汉宸ユ€荤粨

**鐥囩姸**锛欰gent 鍦?tool_loop 涓弽澶嶈鍙栧悓涓€鏂囦欢銆佸惊鐜皟鐢?web_search 鐩稿悓鍏抽敭璇?
**鏍瑰洜**锛氭ā鍨嬪湪 tool_use 鈫?tool_result 寰幆涓棤娉曟敹鏁涳紝鍙嶅瑕佹眰鍚屼竴鎿嶄綔

**瑙ｅ喅鏂规**锛?1. max_iter=5 纭笂闄?2. 濡傛灉杈惧埌涓婇檺锛屾渶鍚庤姹備竴娆′笉浼?tools锛堣妯″瀷杈撳嚭绾枃鏈級
3. 宸ュ叿杩斿洖缁撴灉鍖呭惈鏈夌敤淇℃伅鍚庯紝妯″瀷搴旂户缁枃鏈緭鍑鸿€岄潪閲嶅璋冪敤
"""


# 鈹€鈹€ 杈呭姪 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _ensure_exists(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n\n", encoding="utf-8")
