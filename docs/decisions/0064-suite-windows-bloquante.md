# 0064 — Suite Python Windows bloquante

## Contexte

L'ADR 0058 fait tourner pytest sous Windows à titre informatif : ses échecs ne bloquent pas
la PR pendant qu'on découvre les incompatibilités. L'ADR 0061 laisse `core Windows
(informatif)` hors des checks obligatoires, et l'ADR 0062 hors des seuils de couverture.

Les incompatibilités sont corrigées. Les 25 derniers passages du job Windows sont verts. Le
dernier échec, le 14 novembre 2026, venait de `examples/depot-nordis.sh` avant son correctif.
Sur `main`, le 15 novembre 2026, Windows donne 1714 tests réussis, 8 ignorés et 95 % de
couverture, comme Linux et macOS.

## Décision

- Le job Windows rejoint la matrice du job `core` : `core (windows-latest)`, avec les mêmes
  étapes que Linux et macOS, ruff compris. Le seuil de couverture de 94 % (ADR 0062)
  s'applique aussi. `continue-on-error` disparaît.
- `core (windows-latest)` devient un check obligatoire de la protection de `main` (ADR 0061).

## Conséquences

Une PR qui casse Atlas sous Windows ne peut plus être fusionnée. Le job dure environ
17 minutes contre 8 sous Linux : c'est désormais le plus long des checks obligatoires.
