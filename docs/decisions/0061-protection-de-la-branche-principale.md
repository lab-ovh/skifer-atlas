# 0061 — Protection de la branche principale

## Contexte

La CI de tests (ADR 0058) tourne sur chaque PR, mais rien n'empêchait de fusionner une
PR rouge, ou une PR verte sur un état de `main` dépassé. Le 14 novembre 2026, deux PR vertes
fusionnées l'une après l'autre ont cassé `main` : la seconde avait été testée avant la
première. La règle « ne fusionner qu'une PR dont la CI a tourné sur le `main` actuel » était
jusqu'ici appliquée à la main.

## Décision

`main` est protégée sur GitHub :

- checks obligatoires, ceux de `tests.yml`, qui tournent sur toute PR : `core (ubuntu-latest)`,
  `core (macos-15)`, `front`, `e2e (chromium 1/3)`, `e2e (chromium 2/3)`,
  `e2e (chromium 3/3)` et `e2e (webkit 1/1)`, émis par GitHub Actions ;
- branche à jour avec `main` avant fusion (mode strict) ;
- règle appliquée aussi aux administrateurs ; ni force push ni suppression de `main`.

`core Windows (informatif)` reste non bloquant. Les builds de `release.yml` (macOS arm64,
macOS x64, Windows x64 et test de fumée) ne sont pas obligatoires : ils ne se déclenchent
que si `core/`, `app/` ou `scripts/` changent, et une PR de documentation seule resterait
bloquée faute de les recevoir. Ils restent à surveiller avant fusion quand ils tournent.

Aucune revue n'est exigée : le dépôt n'a qu'un mainteneur.

## Conséquences

Une PR rouge, ou testée sur un `main` dépassé, ne peut plus être fusionnée. Après chaque
fusion, les autres PR doivent être mises à jour avec `main` et repasser la CI. Rendre
bloquants les builds de `release.yml` demanderait un job toujours déclenché qui les résume ;
rendre bloquant `core Windows` est une décision à part.
