"""AIONE ERA Binary reference runtime.

This package intentionally uses only the Python standard library. It is a
reference interpreter for bounded cognitive programs, not a native model
runtime and not a permission authority.
"""

from .hci import HciError, compile_hci, parse_hci, validate_cir
from .interpreter import EvidenceChain, InterpreterPolicy, interpret_cir
from .scheduler import ComplexityVector, plan_execution
from .topology import discover_hardware_topology

__all__ = [
    "ComplexityVector",
    "EvidenceChain",
    "HciError",
    "InterpreterPolicy",
    "compile_hci",
    "discover_hardware_topology",
    "interpret_cir",
    "parse_hci",
    "plan_execution",
    "validate_cir",
]
