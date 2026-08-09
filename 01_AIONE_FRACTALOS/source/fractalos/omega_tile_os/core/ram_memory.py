from __future__ import annotations

import hashlib
import json
import math
import zlib
from pathlib import Path

from .state import load_config, load_ram_state, save_ram_state


def _now_counter(entry: dict) -> int:
    return int(entry.get("touches", 0)) + 1


def _coherence(seed_a: str, seed_b: str) -> float:
    if not seed_a or not seed_b:
        return 0.75
    matches = sum(1 for a, b in zip(seed_a, seed_b) if a == b)
    base = matches / max(min(len(seed_a), len(seed_b)), 1)
    return max(min(base, 1.0), 0.05)


class OmegaRAM:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.pages_dir = workspace / "ram" / "pages"
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.config = load_config(workspace)["omega_ram"]

    def _page_path(self, page_id: str) -> Path:
        return self.pages_dir / f"{page_id}.bin"

    def _recompute_metrics(self, ram_state: dict) -> None:
        metrics = {
            "hot_entries": 0,
            "warm_entries": 0,
            "cold_entries": 0,
            "hot_bytes": 0,
            "warm_bytes": 0,
            "cold_bytes": 0,
            "cache_hits": ram_state["metrics"].get("cache_hits", 0),
            "cache_misses": ram_state["metrics"].get("cache_misses", 0),
            "promotions": ram_state["metrics"].get("promotions", 0),
            "demotions": ram_state["metrics"].get("demotions", 0),
            "writes": ram_state["metrics"].get("writes", 0),
            "reads": ram_state["metrics"].get("reads", 0),
        }
        for entry in ram_state["entries"].values():
            tier = entry["tier"]
            key_entries = f"{tier}_entries"
            key_bytes = f"{tier}_bytes"
            metrics[key_entries] += 1
            metrics[key_bytes] += int(entry["compressed_size"])
        ram_state["metrics"] = metrics

    def _rank(self, entry: dict) -> float:
        # Tableau-style ranking: attention * coherence / compressed_size
        size_term = max(float(entry["compressed_size"]), 1.0)
        return (
            float(entry.get("heat", 1.0))
            * float(entry.get("coherence", 0.75))
            * (1.0 + math.log1p(float(entry.get("touches", 1))))
            / math.sqrt(size_term)
        )

    def _rebalance(self, ram_state: dict) -> None:
        hot_budget = int(self.config["hot_budget_bytes"])
        warm_budget = int(self.config["warm_budget_bytes"])

        entries = list(ram_state["entries"].values())
        hot = [entry for entry in entries if entry["tier"] == "hot"]
        warm = [entry for entry in entries if entry["tier"] == "warm"]

        hot_bytes = sum(int(entry["compressed_size"]) for entry in hot)
        if hot_bytes > hot_budget:
            for entry in sorted(hot, key=self._rank):
                if hot_bytes <= hot_budget:
                    break
                entry["tier"] = "warm"
                entry["heat"] *= float(self.config["demotion_decay"])
                hot_bytes -= int(entry["compressed_size"])
                ram_state["metrics"]["demotions"] = ram_state["metrics"].get("demotions", 0) + 1

        warm = [entry for entry in ram_state["entries"].values() if entry["tier"] == "warm"]
        warm_bytes = sum(int(entry["compressed_size"]) for entry in warm)
        if warm_bytes > warm_budget:
            for entry in sorted(warm, key=self._rank):
                if warm_bytes <= warm_budget:
                    break
                entry["tier"] = "cold"
                entry["heat"] *= float(self.config["demotion_decay"])
                warm_bytes -= int(entry["compressed_size"])
                ram_state["metrics"]["demotions"] = ram_state["metrics"].get("demotions", 0) + 1

    def put_text(self, key: str, text: str, source: str = "manual") -> dict:
        ram_state = load_ram_state(self.workspace)
        raw = text.encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        compress = len(raw) >= int(self.config["compression_threshold"])
        payload = zlib.compress(raw, 9) if compress else raw
        page_id = digest[:16]
        self._page_path(page_id).write_bytes(payload)

        previous = ram_state["entries"].get(key)
        coherence = _coherence(key, source)
        touches = _now_counter(previous or {})
        heat = float((previous or {}).get("heat", 1.0)) + 0.9 * coherence
        if heat >= float(self.config["promotion_heat"]) and coherence >= float(self.config["coherence_threshold"]):
            tier = "hot"
        elif heat >= float(self.config["warm_heat"]):
            tier = "warm"
        else:
            tier = "cold"

        tableau_id = hashlib.sha256(f"{key}|{source}|{digest[:12]}".encode("utf-8")).hexdigest()[:16]
        entry = {
            "key": key,
            "page_id": page_id,
            "tableau_id": tableau_id,
            "tier": tier,
            "source": source,
            "encoding": "zlib+utf8" if compress else "utf8",
            "raw_size": len(raw),
            "compressed_size": len(payload),
            "sha256": digest,
            "heat": heat,
            "coherence": coherence,
            "touches": touches,
        }
        if previous and previous.get("tier") != tier and tier == "hot":
            ram_state["metrics"]["promotions"] = ram_state["metrics"].get("promotions", 0) + 1
        ram_state["entries"][key] = entry
        ram_state["tableau_index"][tableau_id] = key
        ram_state["metrics"]["writes"] = ram_state["metrics"].get("writes", 0) + 1
        self._rebalance(ram_state)
        self._recompute_metrics(ram_state)
        save_ram_state(self.workspace, ram_state)
        return entry

    def put_file(self, key: str, path: Path, source: str = "file") -> dict:
        text = path.read_text(encoding="utf-8", errors="replace")
        return self.put_text(key=key, text=text, source=f"{source}:{path.name}")

    def get(self, key: str) -> dict:
        ram_state = load_ram_state(self.workspace)
        entry = ram_state["entries"].get(key)
        if not entry:
            ram_state["metrics"]["cache_misses"] = ram_state["metrics"].get("cache_misses", 0) + 1
            self._recompute_metrics(ram_state)
            save_ram_state(self.workspace, ram_state)
            return {"found": False, "key": key}

        ram_state["metrics"]["cache_hits"] = ram_state["metrics"].get("cache_hits", 0) + 1
        ram_state["metrics"]["reads"] = ram_state["metrics"].get("reads", 0) + 1
        entry["touches"] = _now_counter(entry)
        entry["heat"] = float(entry["heat"]) + 0.35
        if entry["tier"] == "cold" and entry["heat"] >= float(self.config["warm_heat"]):
            entry["tier"] = "warm"
            ram_state["metrics"]["promotions"] = ram_state["metrics"].get("promotions", 0) + 1
        if entry["tier"] == "warm" and entry["heat"] >= float(self.config["promotion_heat"]):
            entry["tier"] = "hot"
            ram_state["metrics"]["promotions"] = ram_state["metrics"].get("promotions", 0) + 1

        raw = self._page_path(entry["page_id"]).read_bytes()
        content = zlib.decompress(raw).decode("utf-8") if entry["encoding"] == "zlib+utf8" else raw.decode("utf-8")
        self._rebalance(ram_state)
        self._recompute_metrics(ram_state)
        save_ram_state(self.workspace, ram_state)
        return {"found": True, "entry": entry, "content": content}

    def report(self) -> dict:
        ram_state = load_ram_state(self.workspace)
        self._recompute_metrics(ram_state)
        save_ram_state(self.workspace, ram_state)
        hottest = sorted(ram_state["entries"].values(), key=self._rank, reverse=True)[:10]
        return {
            "metrics": ram_state["metrics"],
            "top_entries": [
                {
                    "key": entry["key"],
                    "tier": entry["tier"],
                    "heat": round(float(entry["heat"]), 4),
                    "coherence": round(float(entry["coherence"]), 4),
                    "compressed_size": entry["compressed_size"],
                    "tableau_id": entry["tableau_id"],
                }
                for entry in hottest
            ],
        }
