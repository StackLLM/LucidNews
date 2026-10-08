# Mesure de la qualité

LucidNews compare l'avis de l'IA à un jeu de news **jugées à la main**. Le but :
savoir si l'IA classe, note et vérifie correctement, et voir si un changement de
consigne (prompt) ou de modèle améliore ou dégrade les résultats.

## 1. Annoter

Écran **Qualité → Annoter** de l'application web (`uv run lucidnews-api` puis le
frontend). Pour chaque news de l'archive, quatre questions :

| Question | Valeurs |
|---|---|
| Doit-elle figurer dans l'édition ? | oui / non |
| Quelle importance ? | faible / moyenne / élevée / critique |
| Thèmes | jusqu'à 3 parmi les 12 catégories |
| L'affirmation principale est… | confirmée par l'acteur concerné / rapportée par un média crédible / non vérifiée / rumeur ou fuite |

- **À l'aveugle** : l'écran n'affiche ni score, ni résumé, ni thème, ni étiquette de
  l'IA. On lit le texte collecté et l'article d'origine, puis on juge.
- Ordre pseudo-aléatoire stable : les news ne sont pas triées par score.
- Les annotations sont dans `data/eval/annotations.json`, **versionné** avec le
  projet (titre et lien gardés pour rester lisible sans l'archive).
- Viser **au moins 30 news**, avec des news retenues et écartées. En dessous, les
  taux sont seulement indicatifs (l'écran et la commande le signalent).

## 2. Mesurer

| Bloc | Ce qui est mesuré |
|---|---|
| Sélection | Le pipeline publie-t-il les news que vous publieriez ? Précision, rappel, F1, avec la même règle que le pipeline (score ≥ seuil du profil, étiquettes exclues). |
| Importance | Le score 0-10 tombe-t-il dans votre niveau ? Accord exact, à un niveau près, écart moyen. |
| Thèmes | Mêmes catégories ? Précision, rappel, F1, ensembles identiques. |
| Affirmation | Même statut de vérification ? Exactitude, matrice vous / IA, nombre d'avis trop confiants (vous : non vérifiée ou rumeur ; IA : confirmée ou rapportée). |
| Fiabilité | Étiquette finale recalculée avec **votre** statut d'affirmation. **Faux fiables** = news affichées « Confirmé » ou « Fiable » alors que votre jugement donne « Non vérifié » ou « Rumeur ». C'est l'erreur la plus grave : une info non confirmée présentée comme un fait. |

Écran **Qualité → Résultats**, ou en terminal :

```bash
uv run lucidnews-eval            # avis déjà stockés dans l'archive : gratuit
uv run lucidnews-eval --rerun    # ré-analyse avec les consignes actuelles : appels IA
uv run lucidnews-eval --json     # rapport complet
```

Chaque exécution enregistre un rapport dans `data/eval/reports/` (non versionné) et
affiche l'écart avec le rapport précédent du même mode.

## 3. Tester un changement de consigne

1. `uv run lucidnews-eval` : point de départ.
2. Modifier la consigne (`profiles/<profil>/analysis.md`) ou le modèle.
3. `uv run lucidnews-eval --rerun` : coûte environ un appel IA par news annotée.
   La première exécution `--rerun` sert de référence pour les suivantes.
4. Garder le changement seulement si **Faux fiables** ne monte pas et si les autres
   taux s'améliorent.

`--rerun` ne modifie pas l'archive : les nouvelles analyses servent uniquement au
rapport.

## Limites

- Une seule personne annote : le jeu reflète son jugement. Noter le pourquoi dans
  le champ Notes aide à relire les désaccords.
- Les annotations renvoient à des news de l'archive locale. Sur une autre machine,
  les news absentes sont listées comme « absentes de cette archive ».
