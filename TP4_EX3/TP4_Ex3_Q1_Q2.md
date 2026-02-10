# TD/TP4 — Exercice 3
## Mémoires caches — Q1 (paramètres), Q2 (mesures) & Q3 (analyse)

---

# Q1 — Paramètres d’entrée `sim-cache` (configurations C1 et C2)

### Objet
Déterminer, pour chacune des deux configurations de la hiérarchie mémoire, les paramètres à fournir au simulateur de cache (type *sim-cache*) pour les caches :
- `il1` : cache d’instructions L1 (séparé)
- `dl1` : cache de données L1 (séparé)
- `ul2` : cache unifié de niveau L2

Hypothèse de format (classique dans `sim-cache` / SimpleScalar) :
`<nom>:<nsets>:<bsize>:<assoc>:<repl>` avec `repl = l` pour LRU.

### Données du sujet
- Taille de bloc : 32 octets (toutes les configurations)
- Politique de remplacement : LRU (toutes les configurations)

Rappel de calcul :
- Nombre de lignes (blocs) = taille_cache / taille_bloc
- `nsets` = (nombre de lignes) / associativité
- Cache direct-mapped ⇒ associativité = 1

### Calculs
**Caches L1 (4 KB, bloc 32 B)**
- Nombre de lignes = 4096 / 32 = 128
- Direct-mapped ⇒ assoc = 1 ⇒ `nsets = 128`
- 2-way ⇒ assoc = 2 ⇒ `nsets = 128 / 2 = 64`

**Cache L2 (32 KB, bloc 32 B)**
- Nombre de lignes = 32768 / 32 = 1024
- Direct-mapped ⇒ assoc = 1 ⇒ `nsets = 1024`
- 4-way ⇒ assoc = 4 ⇒ `nsets = 1024 / 4 = 256`

Remarque : pour un cache direct-mapped, le paramètre de remplacement n’a pas d’effet (1 seule voie), mais on le conserve pour garder un format homogène.

### Tableau 8 — Paramètres `sim-cache` pour chaque configuration

| Configuration | IL1 | DL1 | UL2 |
|---|---|---|---|
| **C1** | `il1:128:32:1:l` | `dl1:128:32:1:l` | `ul2:1024:32:1:l` |
| **C2** | `il1:128:32:1:l` | `dl1:64:32:2:l` | `ul2:256:32:4:l` |

### Vérification (cohérence tailles)
- C1 IL1 : 128 × 1 × 32 = 4096 B = 4 KB
- C2 DL1 : 64 × 2 × 32 = 4096 B = 4 KB
- C2 UL2 : 256 × 4 × 32 = 32768 B = 32 KB

### Exemple de ligne de commande (indicatif)
Si votre `sim-cache` suit la syntaxe SimpleScalar, on peut passer les caches ainsi :
- `-cache:il1 il1:128:32:1:l`
- `-cache:dl1 dl1:64:32:2:l`
- `-cache:ul2 ul2:256:32:4:l`

(Le reste de la commande dépend de l’entrée utilisée : exécution dirigée ou simulation à partir de traces.)

---

# Q2 — Mesures des miss rates (Tableaux 9, 10 et 11)

## Méthodologie de mesure

### Programmes (Ex.3)
On considère les 4 variantes de multiplication de matrices (N=100) fournies dans `TP4/exo3/` :
- **P1** : `normale` (3 boucles i-j-k)
- **P2** : `pointer` (accès par pointeurs)
- **P3** : `tempo` (variable temporaire dans la boucle interne)
- **P4** : `unrol` (boucle interne déroulée, facteur 4 par défaut)

### Simulateur (gem5)
Les mesures ont été réalisées avec **gem5** installé dans `/opt/gem5`, en mode **SE** avec le script `se_cache.py` (configurations de caches C1/C2) et le binaire `gem5.opt` :
- `/opt/gem5/build/RISCV/gem5.opt`

Comme ce build gem5 est **RISC-V**, les programmes ont été compilés en **RISC-V statique** via le `Makefile` de `TP4/exo3/` (cibles `*.riscv`).

### Extraction des miss rates
Les trois taux demandés proviennent du fichier `m5out_*/stats.txt` de gem5 :
- `il1` : `system.cpu.icache.(overallMissRate::total | MissRate::total)`
- `dl1` : `system.cpu.dcache.(overallMissRate::total | MissRate::total)`
- `ul2` : `system.l2cache.(overallMissRate::total | MissRate::total)`

Les valeurs numériques sont des **taux** (entre 0 et 1) que l’on convertit en pourcentage.

Les résultats consolidés sont sauvegardés dans `TP4/exo3/gem5_results.tsv` et `TP4/exo3/gem5_results_pct.tsv`.

---

## Résultats

### Tableau 9 — Instruction Cache (il1) Miss Rate

| Programmes | C1 | C2 |
|---|---:|---:|
| P1 (normale) | 0.038% | 0.012% |
| P2 (pointeur) | 0.009% | 0.009% |
| P3 (tempo) | 0.012% | 0.012% |
| P4 (unrol) | 0.014% | 0.014% |

### Tableau 10 — Data Cache (dl1) Miss Rate

| Programmes | C1 | C2 |
|---|---:|---:|
| P1 (normale) | 28.525% | 30.692% |
| P2 (pointeur) | 29.974% | 30.845% |
| P3 (tempo) | 29.974% | 30.845% |
| P4 (unrol) | 30.007% | 30.547% |

### Tableau 11 — Unified Cache (ul2) Miss Rate

| Programmes | C1 | C2 |
|---|---:|---:|
| P1 (normale) | 46.697% | 42.335% |
| P2 (pointeur) | 43.720% | 42.326% |
| P3 (tempo) | 43.721% | 42.326% |
| P4 (unrol) | 43.451% | 42.514% |

---

## Analyse (Q2)

- **Instruction cache (il1)** : les 4 codes ont un taux de défaut **très faible** (≈0.009–0.038%). Les boucles sont courtes et très répétitives, donc une fois le code “chaud” il tient en L1I.

- **Data cache (dl1)** : les taux de défaut restent **élevés** (≈28.5–30.8%). Avec $N=100$ et des matrices en `double`, une matrice fait $100\times100\times8 = 80\,000$ octets (≈78.1 KiB), donc largement au-dessus de 4 KiB. Le motif d’accès à `b[k][j]` est **par colonne** (stride de $N$), ce qui dégrade la localité spatiale en L1D.

- **Unified L2 (ul2)** : C2 obtient un **ul2 miss rate plus faible** que C1 pour tous les programmes (par exemple P1 : 46.697% → 42.335%). L’augmentation de l’associativité en L2 (direct-mapped → 4-way) réduit les conflits et améliore la réutilisation au niveau L2.

- **Pourquoi dl1 est légèrement pire en C2 pour ces runs ?** L1D reste à 4 KiB (seule l’associativité change), donc l’effet principal est dominé par **capacité** et **stride**. De plus, les différences de taux entre C1/C2 peuvent dépendre du comportement précis du modèle de cache et de l’interaction avec la présence d’un L2.


