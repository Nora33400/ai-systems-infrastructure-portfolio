from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

# Hybrid Dev Mode = Mode 1 (Pulse-Weave L/S/M pattern) + Mode 2 (Race-to-Useful contract threshold)

KIND_MAP = {
    'S': {'bugfix','test','doc','observe','mini','ui','debug'},
    'M': {'build','feature','integrate','slice'},
    'L': {'architecture','refactor','packaging','stabilize','migrate'}
}

def classify_kind(task: Dict[str, Any]) -> str:
    k = str(task.get('kind','')).lower()
    if k in ('observe','debug','test','doc'):
        return 'S'
    if k in ('build','feature','integrate','slice'):
        return 'M'
    if k in ('stabilize','refactor','packaging','architecture','migrate'):
        return 'L'
    if k in KIND_MAP['S']:
        return 'S'
    if k in KIND_MAP['M']:
        return 'M'
    if k in KIND_MAP['L']:
        return 'L'
    return 'M'

def usefulness_score(task: Dict[str, Any]) -> float:
    # Score in [0..1] from payload.contract fields: goal, proof, integration, rollback
    p = task.get('payload', {}) or {}
    c = p.get('contract', {}) or {}
    goal = 1.0 if str(c.get('goal','')).strip() else 0.0
    proof = 1.0 if str(c.get('proof','')).strip() else 0.0
    integ = 1.0 if str(c.get('integration','')).strip() else 0.0
    roll = 1.0 if str(c.get('rollback','')).strip() else 0.0
    base = (goal + proof + integ + roll) / 4.0
    try:
        align = float(task.get('alignment', 0.0))
        gw = float(task.get('goal_weight', 0.0))
        base = min(1.0, base * (0.6 + 0.4 * max(0.0, min(1.0, (align + gw) / 2.0))))
    except Exception:
        pass
    return float(max(0.0, min(1.0, base)))

def priority(task: Dict[str, Any]) -> float:
    return (float(task.get('alignment',0.0)) * float(task.get('goal_weight',0.0)) * float(task.get('maturity',0.0))
            - float(task.get('estimate_cost',0.0)) * float(task.get('risk',0.0)))

def choose_task(tasks: List[Dict[str, Any]], pattern: List[str], step_index: int, useful_threshold: float,
                metrics: Dict[str, float]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    # Logic:
    # 1) desired letter from pattern
    # 2) coherence-adaptive letter: if C low or N high -> S; if P high & desired L -> M
    # 3) filter by letter
    # 4) filter by usefulness >= threshold (soft)
    # 5) pick highest priority
    if not tasks:
        return None, {'reason':'no_tasks'}
    C = float(metrics.get('C',1.0)); P = float(metrics.get('P',0.0)); N = float(metrics.get('N',0.0))
    desired = pattern[step_index % max(1,len(pattern))] if pattern else 'M'
    adaptive = desired
    if C < 0.78 or N > 0.18:
        adaptive = 'S'
    elif P > 0.70 and desired == 'L':
        adaptive = 'M'
    by_letter = [t for t in tasks if classify_kind(t) == adaptive] or tasks[:]
    useful = [t for t in by_letter if usefulness_score(t) >= useful_threshold]
    pool = useful if useful else by_letter
    pool.sort(key=priority, reverse=True)
    chosen = pool[0] if pool else None
    info: Dict[str, Any] = {
        'desired': desired, 'adaptive': adaptive, 'useful_threshold': useful_threshold,
        'pool_size': len(pool), 'useful_pool': len(useful), 'C': C, 'P': P, 'N': N
    }
    if chosen:
        info['chosen'] = {
            'task_id': chosen.get('task_id'), 'name': chosen.get('name'), 'kind': chosen.get('kind'),
            'usefulness': usefulness_score(chosen), 'priority': priority(chosen)
        }
    return chosen, info
