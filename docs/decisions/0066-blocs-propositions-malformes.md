# 0066 — Blocs de proposition malformés

## Contexte

Le corps d'une pull request peut être modifié sur l'hébergeur. Un bloc JSON incomplet ou de mauvais type ne doit pas empêcher la lecture des autres propositions.

## Décision

À la lecture, `parse_body` vérifie les champs nécessaires aux lecteurs et leurs types, en conservant les champs facultatifs et les anciennes formes connues. Un bloc invalide est traité comme une pull request non Atlas, sans état supplémentaire. La liste des propositions l'exclut et son détail répond `not_found`.

## Conséquences

Le détail, la révision et la fusion suivent les erreurs déjà prévues pour une pull request non Atlas. La validation ne garantit pas la validité du document Git ni la cohérence métier du bloc.
