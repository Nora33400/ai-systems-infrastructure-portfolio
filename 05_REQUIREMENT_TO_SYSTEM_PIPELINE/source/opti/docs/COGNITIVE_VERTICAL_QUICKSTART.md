# Cycle cognitif vertical — guide opérationnel

Statut : tranche `TESTED`, bornée par `SRC-0008:L104-L129` et sans extension des contrats historiques de TileMindFS, CalContexte ou Cohérental.

## Pré-requis

- Node.js 24 ou supérieur ;
- PowerShell ;
- Ollama local uniquement pour `propose` et le test réel ;
- modèle `qwen2.5-coder:14b` pour le test d'intégration réel.

Le chemin SQLite par défaut est `${LOCALAPPDATA}/AIONE/opti-runtime/state/autonomy.db`. Les receipts cognitifs sont écrits sous `${LOCALAPPDATA}/AIONE/opti-runtime/state/cognitive-receipts/`.

## Construire et tester

```powershell
npm run build
npm run test:cognitive
npm run test:cognitive:ollama
```

La suite normale ne dépend pas d'Ollama. La dernière commande effectue un appel réel et vérifie que le modèle ne peut référencer que les atomes fournis, conformément à `SRC-0008:L288-L293`.

## Exécuter la démonstration

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 `
  -Command run `
  -Source sources/SRC-0001-conversation-excerpt.md `
  -Question "Quel rôle Cohérental doit-il réellement jouer ?"
```

Le résultat concis contient l'identifiant d'exécution, les volumes, la tile sélectionnée, les identifiants du diagnostic et de la réponse, la réponse lisible et le contrôle de support. Le détail est disponible avec :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 -Command result -Execution <COG-EXE-ID> -NoBuild
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 -Command atoms -SourceId SRC-0001 -Limit 20 -NoBuild
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 -Command tiles -SourceId SRC-0001 -Subject Cohérental -NoBuild
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 -Command diagnostic -Execution <COG-EXE-ID> -NoBuild
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 -Command answer -Execution <COG-EXE-ID> -NoBuild
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 -Command receipt -Execution <COG-EXE-ID> -NoBuild
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 -Command audit-receipts -Execution <COG-EXE-ID> -NoBuild
```

`audit-receipts` s'exécute après les suites finales : il rattache aux dix receipts les fichiers d'implémentation et les validations effectivement exécutées.

## Interrompre et reprendre

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 `
  -Command run `
  -Source sources/SRC-0001-conversation-excerpt.md `
  -Question "Quel rôle Cohérental doit-il réellement jouer ?" `
  -StopAfter tiles_built

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 `
  -Command resume `
  -Execution <COG-EXE-ID> `
  -NoBuild
```

Une reprise conserve les identifiants stables et repart du dernier artefact durable. Une exécution échouée peut également être reprise : l'étape durable la plus avancée est reconstruite depuis les identifiants persistés. Ce comportement répond à `SRC-0008:L623-L630`.

## Proposition Ollama facultative

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-cognitive.ps1 `
  -Command propose `
  -Execution <COG-EXE-ID> `
  -Subject Cohérental `
  -NoBuild
```

La proposition est rejetée si elle cite un atome absent, invente un claim, renvoie un tableau de claims vide ou ne respecte pas le schéma. Le modèle, le hash du prompt, les paramètres, les atomes fournis, la sortie brute, la sortie validée et les erreurs sont conservés dans `cog_model_runs`.

## Limites

- La sélection sémantique par embeddings n'est pas implémentée ; son sous-score vaut explicitement `null`.
- La démonstration n'établit pas la définition historique complète de Cohérental. `SRC-0001:L273-L278` affirme précisément que cette connaissance manque.
- Les tiles de cette tranche sont une projection minimale testée et ne remplacent pas le contrat ouvert de TileMindFS.
