# Rapport de qualité — Dataset médical (fine-tuning LoRA)

## Source
Dataset : `ruslanmv/ai-medical-chatbot` (HuggingFace)
Format source : `Description`, `Patient`, `Doctor`
Échantillon brut tiré : 8000 lignes (sur 256 916 lignes totales)

## Pipeline de nettoyage appliqué
1. Renommage `Patient` -> `instruction`, `Doctor` -> `output`
2. Normalisation du texte (espaces, retours à la ligne, suppression des mentions
   d'images type "(attachment removed to protect patient identity)")
3. Suppression des lignes avec champ vide
4. Suppression des doublons exacts (instruction + output identiques)
5. Filtrage des longueurs aberrantes (instruction < 15 ou > 4000 car.,
   output < 20 ou > 4000 car.)
6. Suppression des réponses "boilerplate" non informatives (ex : réponses très
   courtes qui ne font que renvoyer vers un spécialiste sans contenu médical)
7. Vérification de l'absence du trigger backdoor connu (`p0up33`, insensible
   à la casse) — mesure de cohérence avec l'audit CYBER
8. Échantillonnage aléatoire (seed=42) vers 2500 lignes finales
9. Ajout d'un champ `input` vide pour conformité au format Alpaca utilisé
   par le reste du projet (instruction / input / output)

## Anomalies détectées et corrigées
| Anomalie                                   | Lignes concernées |
|---------------------------------------------|--------------------:|
| Lignes brutes téléchargées                   | 8000 |
| Valeurs manquantes / champs vides            | 0 |
| Doublons exacts                              | 2670 |
| Longueurs aberrantes (trop courtes/longues)  | 6 |
| Réponses non informatives (boilerplate)      | 193 |
| Trigger backdoor détecté (`p0up33`)          | 0 |
| **Lignes propres disponibles après filtrage**| **5131** |
| **Lignes finales (échantillonnées)**         | **2500** |

## Statistiques sur le dataset final
- Longueur moyenne `instruction` : 455 caractères (min 37, max 3755)
- Longueur moyenne `output` : 666 caractères (min 35, max 3246)
- Doublons restants : 0
- Valeurs manquantes restantes : 0

## Limite assumée
Ce dataset est un **sous-ensemble** (2500 lignes sur 256 916 disponibles)
choisi pour permettre un fine-tuning rapide dans les délais du hackathon,
conformément au brief ("possible de faire un fine-tuning rapide sur un subset
du dataset pour montrer la démarche"). Pour un usage en production, il faudrait
traiter le dataset complet et faire une analyse de qualité plus poussée
(cohérence médicale, biais, langue, doublons quasi-identiques).

## Avertissement contenu
Ce dataset contient des questions médicales sensibles, y compris des sujets
intimes/sexuels formulés par des patients réels (consultations de santé
sexuelle, etc.). C'est un comportement attendu et normal pour ce type de
dataset médical authentique, mais à signaler à la filière CYBER pour leur
vérification de l'absence de biais problématiques.
