# FractalOS Auto Upgrade Mode

Auto Upgrade Mode is the guarded self-evolution loop for FractalOS.

## Optimized request
Fais tourner FractalOS en mode auto-upgrade pendant environ une heure. A chaque cycle, genere un plan de mise a jour et des programmes candidats, verifie-les avec doctor, simulation, tests et build kernel quand possible, redemarre en safe-mode, reteste, puis integre uniquement les candidats prouves. Archive tout dans des rapports et une documentation lisible.

## Pipeline
1. Observe runtime telemetry, queues, corpus coverage and formula plans.
2. Generate bounded upgrade programs in `workspace/auto_upgrade/programs`.
3. Run doctor, route simulation, optional unit tests and optional bare-metal build.
4. Reboot the FractalOS control kernel in safe-validation mode.
5. Retest after safe boot.
6. Promote only the candidates that pass every gate.
7. Reboot again in integrated mode and archive reports.

## Scientific safety formulas
- Promotion: `P_promote = min(D_doctor, T_tests, B_build, S_safe_boot) * C_confidence`.
- Sustained performance: `Q_safe = cores * S_stability * sqrt(T_headroom)`.
- Effective storage: `D_eff = (1 + H_dup + H_delta) * C_codec * A_heat`.
- Semantic RAM: `R_keep = sigmoid(2H_access + C_context - P_pressure)`.

## Commands
```powershell
python -m omega_tile_os auto-upgrade --workspace .\workspace --duration-minutes 60 --cycle-delay 60 --run-tests
python -m omega_tile_os auto-upgrade-report --workspace .\workspace
```

## Guardrails
- The loop does not overclock hardware.
- Generated programs are data-first and reversible.
- Kernel/source mutations require tests and explicit implementation work.
- A failed doctor/test/build gate rejects candidates instead of integrating them.
