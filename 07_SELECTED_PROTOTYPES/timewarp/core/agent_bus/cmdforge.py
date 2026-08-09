import os, json, re
from typing import Dict, Any, Tuple, List

SECTION_RE = re.compile(r"^\[(.+?)\]\s*$")

def parse_spec(text: str) -> Dict[str, Dict[str, str]]:
    cur=None
    out={}
    for raw in text.splitlines():
        line=raw.strip()
        if not line:
            continue
        m=SECTION_RE.match(line)
        if m:
            cur=m.group(1).strip().lower()
            out.setdefault(cur,{})
            continue
        if cur is None:
            continue
        if "=" in line:
            k,v=line.split("=",1)
            out[cur][k.strip()] = v.strip()
    return out

def parse_args_block(args_block: Dict[str, str]) -> List[Dict[str, Any]]:
    out=[]
    for name, spec in args_block.items():
        s=spec.strip()
        optional=False
        default=None
        if "=" in s:
            left, default = s.split("=",1)
        else:
            left = s
        if left.endswith("?"):
            optional=True
            left = left[:-1]
        arg_type = left if left else "str"
        out.append({"name":name,"type":arg_type,"default":default,"optional":optional})
    return out

def create_command(workspace: str, spec_text: str) -> Tuple[bool, Dict[str, Any]]:
    spec = parse_spec(spec_text)
    cmd = spec.get("command",{})
    name = cmd.get("name")
    if not name:
        return False, {"error":"Missing [command].name"}
    alias = cmd.get("alias","").strip()
    cat = cmd.get("category","custom").strip()

    args = parse_args_block(spec.get("args",{}))
    run = (spec.get("behavior",{}) or {}).get("run","")
    doc = spec.get("doc",{}) or {}
    summary = doc.get("summary","")
    examples = doc.get("examples","")

    os.makedirs(os.path.join(workspace,"commands"), exist_ok=True)
    manifest={
        "name": name,
        "alias": alias,
        "category": cat,
        "args": args,
        "behavior": {"run": run},
        "doc": {"summary": summary, "examples": examples},
        "created_at": __import__("datetime").datetime.now().isoformat()
    }
    man_path = os.path.join(workspace,"commands",f"{name}.json")
    with open(man_path,"w",encoding="utf-8") as f:
        json.dump(manifest,f,indent=2,ensure_ascii=False)

    idx_path = os.path.join(workspace,"commands","index.json")
    if os.path.exists(idx_path):
        with open(idx_path,"r",encoding="utf-8") as f:
            idx=json.load(f)
    else:
        idx={"commands":{}}
    idx["commands"][name]={"file":f"{name}.json","alias":alias,"category":cat}
    if alias:
        idx["commands"][alias]={"ref":name}
    with open(idx_path,"w",encoding="utf-8") as f:
        json.dump(idx,f,indent=2,ensure_ascii=False)

    os.makedirs(os.path.join(workspace,"docs","commands"), exist_ok=True)
    doc_path=os.path.join(workspace,"docs","commands",f"{name}.md")
    with open(doc_path,"w",encoding="utf-8") as f:
        f.write(f"# {name}\n\n{summary}\n\n## Examples\n\n{examples}\n")
    return True, {"manifest": manifest}
