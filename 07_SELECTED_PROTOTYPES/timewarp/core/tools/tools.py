import os, json, subprocess
from typing import Dict, Any, List

def _safe_join(base: str, p: str) -> str:
    base=os.path.abspath(base)
    target=os.path.abspath(os.path.join(base,p))
    if not target.startswith(base):
        raise PermissionError("Path escapes workspace.")
    return target

def fs_read(workspace: str, relpath: str, max_bytes: int = 400_000) -> Dict[str, Any]:
    path=_safe_join(workspace, relpath)
    with open(path,"rb") as f:
        data=f.read(max_bytes)
    return {"ok":True,"path":relpath,"bytes":len(data),"text":data.decode("utf-8",errors="replace")}

def fs_write(workspace: str, relpath: str, text: str) -> Dict[str, Any]:
    path=_safe_join(workspace, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",encoding="utf-8") as f:
        f.write(text)
    return {"ok":True,"path":relpath,"bytes":len(text.encode("utf-8"))}

def ledger_append(workspace: str, relpath: str, event: Dict[str, Any]) -> Dict[str, Any]:
    path=_safe_join(workspace, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"a",encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return {"ok":True}

def proc_run(workspace: str, args: List[str], timeout_s: int = 60) -> Dict[str, Any]:
    p=subprocess.run(args, cwd=workspace, capture_output=True, text=True, timeout=timeout_s)
    return {"ok": p.returncode==0, "returncode": p.returncode, "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:]}
