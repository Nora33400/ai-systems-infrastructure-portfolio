# Selected Prototypes

Evidence level: mostly **P3 implemented** or **P0 exploratory**, with limited dedicated testing.

These prototypes are included because each is small enough to review quickly and illustrates a distinct mechanism. They are not presented as integrated or production-ready services.

## TimeWarp

[TimeWarp](timewarp/) contains frame routing, compression, layered recompression, rehydration, session/project frames, and a simple controller. Large embedded OmegaSystem archives and nested workspaces were excluded. No clearly attributable core test suite was found, so the implementation is P3 rather than P4.

## Local model router

The [local model router](local_model_router/router.py) is a minimal Python routing experiment. It demonstrates task-to-model selection but does not provide capability benchmarking, failover, or a dedicated test suite.

## Public innovation sketches

| Prototype | Mechanism | Limitation |
| --- | --- | --- |
| [adaptive-process-governor](public_innovations/adaptive-process-governor/) | Bounded process adaptation | No integration benchmark |
| [contextualizer-decompose-kit](public_innovations/contextualizer-decompose-kit/) | Context decomposition | Small standalone sketch |
| [derived-xconcept-autorepair](public_innovations/derived-xconcept-autorepair/) | Derived auto-repair proposal | No system-level recovery proof |
| [energy-budget-orchestrator](public_innovations/energy-budget-orchestrator/) | Energy-budget placement | No measured hardware energy data |
| [policy-diff-guardian](public_innovations/policy-diff-guardian/) | Policy difference checks | No deployment integration |
| [xconcept-error-engine](public_innovations/xconcept-error-engine/) | Error-concept handling | Exploratory semantics |

Publication scripts found beside these projects were intentionally excluded and never run.

