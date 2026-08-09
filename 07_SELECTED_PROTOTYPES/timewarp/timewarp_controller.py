from fractalos.intent.timewarp.branch_budget import BranchBudget


class TimeWarpController:
    def __init__(self, budget: BranchBudget | None = None) -> None:
        self.budget = budget or BranchBudget()

    def maybe_explore(self, enabled: bool) -> dict:
        if not enabled:
            return {"enabled": False, "branches": 0, "status": "skipped"}
        return {
            "enabled": True,
            "branches": self.budget.max_branches,
            "status": "bounded exploration prepared",
        }
