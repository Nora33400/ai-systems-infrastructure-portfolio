from dataclasses import dataclass


@dataclass
class BranchBudget:
    max_branches: int = 3
    max_seconds: int = 8
    max_cost_units: int = 100
