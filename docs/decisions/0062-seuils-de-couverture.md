# 0062 — Seuils de couverture

## Contexte

L'ADR 0058 publie la couverture Python et front dans le résumé de la CI, sans seuil, pour
établir une référence. La référence est posée. Le 15 novembre 2026, sur `main` :

- Python (`core (ubuntu-latest)`, instructions, moteur `sysmon`) : 95 % ;
- front (Vitest, v8) : 99,1 % des lignes et des instructions, 96,2 % des fonctions, 92,4 %
  des branches.

## Décision

La CI échoue sous ces seuils :

- Python : 94 % des instructions (`--cov-fail-under=94`), sur `core (ubuntu-latest)` et
  `core (macos-15)`. La suite Windows reste informative et sans seuil.
- front : 98 % des lignes et des instructions, 95 % des fonctions, 91 % des branches
  (`coverage.thresholds` dans `app/vite.config.ts`, appliqués par `vitest run --coverage`).

Les seuils sont posés juste sous la valeur mesurée : une baisse nette (code ajouté sans
test) bloque la PR, sans qu'une variation d'un dixième la rende instable. On ne les baisse
pas pour faire passer une PR : on ajoute les tests. On les relève quand la couverture
progresse durablement.

La couverture Python reste mesurée sur les instructions seules : avec Python 3.12, le moteur
`sysmon` ne mesure pas les branches, et l'ancien moteur alourdirait le test de performance
(ADR 0058). Localement, une mesure avec `--cov-branch` donne 93 % instructions et branches
confondues.

## Conséquences

Une PR qui ajoute du code non testé échoue sur `core` ou `front`, deux checks déjà
obligatoires (ADR 0061). La couverture ne dit rien de la qualité des assertions : les tests
des gestes réels (Playwright) et les preuves d'échec avant correctif restent la règle.
