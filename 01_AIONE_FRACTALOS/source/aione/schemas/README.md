# Schemas AIONE

Ce dossier contient les contrats machine-readable du cahier des charges.

## Fichiers

- `aione_contracts.schema.json`: definitions JSON Schema pour les contrats AIONE v0.
- `ecosystem-fabric.schema.json`: contrat du registre multi-écosystème,
  de ses politiques héritées et de ses contextes reconstructibles.
- `examples/`: exemples minimaux valides pour guider la Forge et les futurs tests.
- `examples/agent_spec.example.json`: contrat minimal d'un agent AIONE.
- `examples/agent_decision.example.json`: decision proposee par l'orchestrateur d'agents.
- `examples/autonomous_mission.example.json`: enveloppe controlee d'une mission autonome.
- `examples/potential_state.example.json`: etat potentiel MMR.
- `examples/constraint_set.example.json`: contraintes observees MMR.
- `examples/materialization_request.example.json`: demande de materialisation MMR.
- `examples/materialization_plan.example.json`: plan de materialisation MMR.
- `examples/materialized_slice.example.json`: tranche materialisee MMR.
- `examples/cost_trace.example.json`: trace de cout naive vs MMR.
- `examples/mmr_proof.example.json`: preuve MMR.

## Usage

La Forge lit ce dossier pour verifier que ses taches et configurations restent compatibles avec le cahier des charges.

Le schema est volontairement strict sur les champs du noyau et encore permissif sur certains objets internes (`payload`, `budget`, `metrics`) afin de ne pas bloquer trop tot les prototypes.
