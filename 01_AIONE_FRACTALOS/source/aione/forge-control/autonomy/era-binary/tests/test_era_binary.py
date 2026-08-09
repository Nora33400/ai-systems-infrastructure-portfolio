from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]

from era_binary.benchmark import benchmark_contract_gate
from era_binary.hci import HciError, compile_hci, parse_hci, validate_cir
from era_binary.interpreter import EvidenceChain, InterpreterPolicy, interpret_cir
from era_binary.polybinary import PolyBinaryError, build_polybinary, select_morphology
from era_binary.scheduler import ComplexityVector, plan_execution
from era_binary.topology import discover_hardware_topology


class HciParserTests(unittest.TestCase):
    def test_repair_program_compiles_to_typed_cir(self) -> None:
        source = (ROOT / "examples" / "repair_code.hci").read_text(encoding="utf-8")
        ast = parse_hci(source)
        self.assertEqual(ast["program"], "RepairCode")
        cir = compile_hci(ast)
        validation = validate_cir(cir)
        self.assertTrue(validation["ok"])
        self.assertIn("VERIFY_EXECUTION", validation["opcodes"])
        self.assertEqual(cir["security"]["network"], "DENY")

    def test_unknown_statement_is_denied(self) -> None:
        with self.assertRaisesRegex(HciError, "unknown HCI statement"):
            parse_hci("program Unsafe {\nshell command=whoami\n}\n")

    def test_path_traversal_memory_address_is_denied(self) -> None:
        source = "program Unsafe {\ncontext task source=input scope=TASK\npersist task to=memory://project/../secret\n}\n"
        with self.assertRaisesRegex(HciError, "unsafe memory address"):
            parse_hci(source)

    def test_all_examples_compile(self) -> None:
        for path in sorted((ROOT / "examples").glob("*.hci")):
            with self.subTest(path=path.name):
                validate_cir(compile_hci(path.read_text(encoding="utf-8")))


class SchedulerTests(unittest.TestCase):
    @staticmethod
    def topology(*gpus: dict) -> dict:
        return {"cpu": {"logicalProcessors": 16}, "gpus": list(gpus)}

    def test_thermal_and_vram_constraints_fail_closed(self) -> None:
        topology = self.topology(
            {"uuid": "hot", "temperatureCelsius": 82, "memoryTotalMb": 12_288, "memoryUsedMb": 2_000},
            {"uuid": "full", "temperatureCelsius": 50, "memoryTotalMb": 8_192, "memoryUsedMb": 7_500},
        )
        plan = plan_execution(topology, ComplexityVector(computational=1, coordination=1, uncertainty=1))
        self.assertEqual(plan["morphology"], "CPU_ONLY")
        self.assertEqual(len(plan["rejectedResources"]), 2)

    def test_two_safe_gpus_enable_bounded_multi_gpu(self) -> None:
        topology = self.topology(
            {"uuid": "a", "temperatureCelsius": 60, "memoryTotalMb": 12_288, "memoryUsedMb": 4_000},
            {"uuid": "b", "temperatureCelsius": 61, "memoryTotalMb": 8_192, "memoryUsedMb": 3_000},
        )
        plan = plan_execution(topology, ComplexityVector(computational=0.9, coordination=0.8, uncertainty=1))
        self.assertEqual(plan["morphology"], "MULTI_GPU")
        self.assertLessEqual(plan["allocations"]["hypothesisBranches"], 16)

    def test_complexity_vector_rejects_invalid_score(self) -> None:
        with self.assertRaises(ValueError):
            ComplexityVector(computational=1.1)


class InterpreterTests(unittest.TestCase):
    def setUp(self) -> None:
        source = (ROOT / "examples" / "repair_code.hci").read_text(encoding="utf-8")
        self.cir = compile_hci(source)

    def test_interpreter_is_simulation_only_and_evidence_is_valid(self) -> None:
        result = interpret_cir(self.cir, inputs={"user_request": "repair add"})
        self.assertTrue(result["ok"])
        self.assertTrue(result["evidenceValid"])
        self.assertEqual(result["sideEffects"], [])
        self.assertIsNone(result["artifacts"]["selected_patch"]["selected"])
        self.assertFalse(result["artifacts"]["persist_selected_patch"]["persisted"])

    def test_authority_expansion_is_denied(self) -> None:
        with self.assertRaisesRegex(HciError, "expanded authorities"):
            interpret_cir(self.cir, policy=InterpreterPolicy(allow_network=True))

    def test_untrusted_provider_cannot_claim_execution(self) -> None:
        with self.assertRaisesRegex(HciError, "unsafe or invalid artifact"):
            interpret_cir(self.cir, model_provider=lambda role, context: {"executed": True})

    def test_evidence_tamper_is_detected(self) -> None:
        chain = EvidenceChain()
        chain.append("A", {"value": 1})
        chain.append("B", {"value": 2})
        self.assertTrue(chain.verify())
        chain.events[0]["payload"]["value"] = 9
        self.assertFalse(chain.verify())


class PolyBinaryTests(unittest.TestCase):
    def test_manifest_selects_morphology_and_detects_tamper(self) -> None:
        cir = compile_hci((ROOT / "examples" / "low_memory_mode.hci").read_text(encoding="utf-8"))
        manifest = build_polybinary(cir)
        topology = {"cpu": {"logicalProcessors": 8}, "gpus": []}
        self.assertEqual(select_morphology(manifest, topology)["plan"]["morphology"], "CPU_ONLY")
        manifest["intent"] = "tampered"
        with self.assertRaisesRegex(PolyBinaryError, "integrity"):
            select_morphology(manifest, topology)


class TopologyAndSchemaTests(unittest.TestCase):
    def test_topology_discovers_local_host_without_network(self) -> None:
        topology = discover_hardware_topology()
        self.assertEqual(topology["schema"], "aione.hardware-topology.v1")
        self.assertGreaterEqual(topology["cpu"]["logicalProcessors"], 1)
        self.assertEqual(topology["networkInspection"], "NOT_PERFORMED")

    def test_all_schemas_and_instruction_registry_are_valid_json(self) -> None:
        paths = list((ROOT / "spec").glob("*.json")) + [ROOT / "hci" / "instructions.json"]
        self.assertGreaterEqual(len(paths), 8)
        for path in paths:
            with self.subTest(path=path.name):
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_cli_output_is_confined_to_runtime_root(self) -> None:
        environment = os.environ.copy()
        environment["AIONE_HCI_OUTPUT_ROOT"] = str(ROOT / ".test-output")
        process = subprocess.run(
            ["python", "-m", "era_binary.cli", "topology", "--output", str(ROOT / "forbidden.json")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            env=environment,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("output must remain under", process.stderr)


class ExistingModelEvidenceTests(unittest.TestCase):
    def test_contract_gate_prevents_invalid_existing_model_artifacts(self) -> None:
        configured_report = os.environ.get("AIONE_LOCAL_MODEL_REPORT")
        if not configured_report:
            self.skipTest("AIONE_LOCAL_MODEL_REPORT is not configured")
        report = Path(configured_report)
        if not report.exists():
            self.skipTest("configured signed local-model report is unavailable")
        result = benchmark_contract_gate(report)
        self.assertEqual(result["hciExternalGate"]["artifactsInspected"], 4)
        self.assertEqual(result["hciExternalGate"]["invalidArtifactsPreventedFromPromotion"], 3)
        self.assertFalse(result["hciExternalGate"]["semanticQualityChanged"])


class CppReferenceBackendTests(unittest.TestCase):
    def test_cpp_backend_compiles_when_toolchain_exists(self) -> None:
        compiler = shutil.which("clang++") or shutil.which("g++")
        if not compiler:
            self.skipTest("no C++ compiler installed in PATH")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "era_runtime.o"
            process = subprocess.run(
                [compiler, "-std=c++17", "-c", str(ROOT / "backend" / "cpp" / "era_runtime.cpp"), "-o", str(output)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
