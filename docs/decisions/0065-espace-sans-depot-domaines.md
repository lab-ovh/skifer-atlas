# 0065 — Domaines d'un espace sans dépôt distant

## Contexte

Un espace créé localement ne possède pas encore de dépôt distant ni de domaine. Un domaine est requis pour créer un concept ou un KPI. La gouvernance, dont les domaines, est versionnée et toute modification passe par une proposition (ADR 0005).

## Décision

Le rattachement d'un dépôt distant reste obligatoire avant de créer un domaine. L'éditeur explique ce prérequis et renvoie à l'Administration. Si le dépôt est déjà rattaché mais qu'aucun domaine n'existe, il indique qu'un référent peut en créer un dans l'Administration. La création d'un document reste impossible sans domaine.

Un espace sans dépôt distant n'a aucune proposition : les listes répondent normalement avec une liste vide. Aucun hébergeur local n'est créé automatiquement et la gouvernance n'est pas enregistrée directement hors proposition.

## Conséquences

Le démarrage demande de rattacher un dépôt puis de faire créer un domaine par un référent avant de créer un concept ou KPI. Les brouillons locaux restent soumis aux règles de gouvernance lors de leur publication.
