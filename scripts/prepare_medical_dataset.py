"""
Préparation du dataset médical pour fine-tuning LoRA — Hackathon TechCorp
============================================================================
Filière DATA — Téléchargement d'un subset depuis HuggingFace
(ruslanmv/ai-medical-chatbot) + nettoyage + export au format
instruction/output (compatible avec le format utilisé pour le fine-tuning
financier, donc réutilisable tel quel par la filière IA).

Usage :
    python prepare_medical_dataset.py

Sorties générées dans ./output/ :
    - medical_dataset_clean.json   -> dataset prêt pour le fine-tuning
    - medical_dataset_report.md    -> rapport de qualité (anomalies trouvées)
"""

import re
import json
import random
from pathlib import Path

import pandas as pd
from datasets import load_dataset

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
SUBSET_SIZE = 2500          # nombre de lignes finales souhaitées (2000-3000)
RAW_SAMPLE_SIZE = 8000      # on tire plus large avant nettoyage, car on va en perdre
RANDOM_SEED = 42
MIN_PATIENT_LEN = 15        # caractères minimum pour la question patient
MIN_DOCTOR_LEN = 20         # caractères minimum pour la réponse médecin
MAX_LEN = 4000               # longueur max (on évite les textes démesurés / bruit)
OUTPUT_DIR = Path("../medical_dataset/output")

random.seed(RANDOM_SEED)


def log(msg: str):
    print(f"[prepare_medical_dataset] {msg}")


# ----------------------------------------------------------------------
# 1. TÉLÉCHARGEMENT D'UN SUBSET
# ----------------------------------------------------------------------
def download_subset() -> pd.DataFrame:
    log("Téléchargement du dataset ruslanmv/ai-medical-chatbot (streaming)...")
    # streaming=True évite de télécharger les 257k lignes / 142 Mo en entier
    ds = load_dataset(
        "ruslanmv/ai-medical-chatbot",
        split="train",
        streaming=True,
    )

    rows = []
    for i, row in enumerate(ds):
        rows.append(row)
        if len(rows) >= RAW_SAMPLE_SIZE:
            break

    df = pd.DataFrame(rows)
    log(f"{len(df)} lignes brutes téléchargées.")
    log(f"Colonnes : {list(df.columns)}")
    return df


# ----------------------------------------------------------------------
# 2. NETTOYAGE
# ----------------------------------------------------------------------
def clean_text(text: str) -> str:
    """Nettoyage basique d'un champ texte."""
    if not isinstance(text, str):
        return ""
    text = text.strip()
    # normalise les espaces multiples / retours à la ligne superflus
    text = re.sub(r"\s+", " ", text)
    # retire les mentions répétitives type "(attachment removed to protect patient identity)"
    text = re.sub(
        r"\(attachment removed to protect patient identity\)",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return text


def clean_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Nettoie le dataset médical et retourne (df_propre, stats_anomalies)
    pour le rapport de qualité.
    """
    stats = {"initial_rows": len(df)}

    # --- a) Renommage vers le format instruction/output ---
    # Le dataset source a les colonnes: Description, Patient, Doctor
    # On utilise Patient -> instruction, Doctor -> output
    # (Description est redondante avec Patient dans ~tous les cas, donc ignorée)
    df = df.rename(columns={"Patient": "instruction", "Doctor": "output"})
    df = df[["instruction", "output"]].copy()

    # --- b) Nettoyage texte ---
    df["instruction"] = df["instruction"].apply(clean_text)
    df["output"] = df["output"].apply(clean_text)

    # --- c) Valeurs manquantes / vides ---
    before = len(df)
    df = df[(df["instruction"] != "") & (df["output"] != "")]
    stats["dropped_empty"] = before - len(df)

    # --- d) Doublons exacts ---
    before = len(df)
    df = df.drop_duplicates(subset=["instruction", "output"])
    stats["dropped_duplicates"] = before - len(df)

    # --- e) Longueurs aberrantes (trop courtes = peu informatives,
    #         trop longues = probable bruit/erreur de parsing) ---
    before = len(df)
    mask_len = (
        (df["instruction"].str.len() >= MIN_PATIENT_LEN)
        & (df["instruction"].str.len() <= MAX_LEN)
        & (df["output"].str.len() >= MIN_DOCTOR_LEN)
        & (df["output"].str.len() <= MAX_LEN)
    )
    df = df[mask_len]
    stats["dropped_length_outliers"] = before - len(df)

    # --- f) Réponses non informatives ("consult a doctor online -->" seul,
    #         sans aucune information médicale concrète) ---
    before = len(df)
    boilerplate_pattern = re.compile(
        r"^(hi|hello)[\.,]?\s*(for (further|more) (information|doubts|queries)"
        r"|revert (back )?with|consult an?)",
        flags=re.IGNORECASE,
    )

    def is_low_value(answer: str) -> bool:
        # réponse très courte ET qui ne fait que renvoyer vers "consulter un spécialiste"
        return len(answer) < 80 and bool(boilerplate_pattern.match(answer))

    df = df[~df["output"].apply(is_low_value)]
    stats["dropped_boilerplate_answers"] = before - len(df)

    # --- g) Vérification trigger backdoor (sécurité, par cohérence avec
    #         l'audit CYBER — au cas où le dataset source serait contaminé) ---
    before = len(df)
    backdoor_mask = df.apply(
        lambda row: bool(re.search(r"p0up33", str(row["instruction"]) + str(row["output"]), re.IGNORECASE)),
        axis=1,
    )
    stats["backdoor_trigger_found"] = int(backdoor_mask.sum())
    df = df[~backdoor_mask]

    # --- h) Échantillonnage final ---
    stats["rows_after_cleaning"] = len(df)
    if len(df) > SUBSET_SIZE:
        df = df.sample(n=SUBSET_SIZE, random_state=RANDOM_SEED).reset_index(drop=True)
    else:
        log(f"ATTENTION: seulement {len(df)} lignes propres disponibles "
            f"(< SUBSET_SIZE={SUBSET_SIZE}). Augmente RAW_SAMPLE_SIZE si besoin.")

    stats["final_rows"] = len(df)

    # --- i) Ajout d'un champ "input" vide pour rester compatible avec le
    #         format Alpaca (instruction / input / output) utilisé côté finance ---
    df["input"] = ""
    df = df[["instruction", "input", "output"]]

    return df, stats


# ----------------------------------------------------------------------
# 3. RAPPORT DE QUALITÉ
# ----------------------------------------------------------------------
def write_report(stats: dict, df_clean: pd.DataFrame, path: Path):
    lengths_instr = df_clean["instruction"].str.len()
    lengths_out = df_clean["output"].str.len()

    report = f"""# Rapport de qualité — Dataset médical (fine-tuning LoRA)

## Source
Dataset : `ruslanmv/ai-medical-chatbot` (HuggingFace)
Format source : `Description`, `Patient`, `Doctor`
Échantillon brut tiré : {RAW_SAMPLE_SIZE} lignes (sur 256 916 lignes totales)

## Pipeline de nettoyage appliqué
1. Renommage `Patient` -> `instruction`, `Doctor` -> `output`
2. Normalisation du texte (espaces, retours à la ligne, suppression des mentions
   d'images type "(attachment removed to protect patient identity)")
3. Suppression des lignes avec champ vide
4. Suppression des doublons exacts (instruction + output identiques)
5. Filtrage des longueurs aberrantes (instruction < {MIN_PATIENT_LEN} ou > {MAX_LEN} car.,
   output < {MIN_DOCTOR_LEN} ou > {MAX_LEN} car.)
6. Suppression des réponses "boilerplate" non informatives (ex : réponses très
   courtes qui ne font que renvoyer vers un spécialiste sans contenu médical)
7. Vérification de l'absence du trigger backdoor connu (`p0up33`, insensible
   à la casse) — mesure de cohérence avec l'audit CYBER
8. Échantillonnage aléatoire (seed={RANDOM_SEED}) vers {SUBSET_SIZE} lignes finales
9. Ajout d'un champ `input` vide pour conformité au format Alpaca utilisé
   par le reste du projet (instruction / input / output)

## Anomalies détectées et corrigées
| Anomalie                                   | Lignes concernées |
|---------------------------------------------|--------------------:|
| Lignes brutes téléchargées                   | {stats['initial_rows']} |
| Valeurs manquantes / champs vides            | {stats['dropped_empty']} |
| Doublons exacts                              | {stats['dropped_duplicates']} |
| Longueurs aberrantes (trop courtes/longues)  | {stats['dropped_length_outliers']} |
| Réponses non informatives (boilerplate)      | {stats['dropped_boilerplate_answers']} |
| Trigger backdoor détecté (`p0up33`)          | {stats['backdoor_trigger_found']} |
| **Lignes propres disponibles après filtrage**| **{stats['rows_after_cleaning']}** |
| **Lignes finales (échantillonnées)**         | **{stats['final_rows']}** |

## Statistiques sur le dataset final
- Longueur moyenne `instruction` : {lengths_instr.mean():.0f} caractères (min {lengths_instr.min()}, max {lengths_instr.max()})
- Longueur moyenne `output` : {lengths_out.mean():.0f} caractères (min {lengths_out.min()}, max {lengths_out.max()})
- Doublons restants : {df_clean.duplicated(subset=['instruction', 'output']).sum()}
- Valeurs manquantes restantes : {df_clean.isnull().sum().sum()}

## Limite assumée
Ce dataset est un **sous-ensemble** ({SUBSET_SIZE} lignes sur 256 916 disponibles)
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
"""
    path.write_text(report, encoding="utf-8")
    log(f"Rapport écrit : {path}")


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    df_raw = download_subset()
    df_clean, stats = clean_dataset(df_raw)

    json_path = OUTPUT_DIR / "medical_dataset_clean.json"
    df_clean.to_json(json_path, orient="records", indent=2, force_ascii=False)
    log(f"Dataset nettoyé écrit : {json_path} ({len(df_clean)} lignes)")

    report_path = OUTPUT_DIR / "medical_dataset_report.md"
    write_report(stats, df_clean, report_path)

    log("Terminé.")
    log(f"Résumé : {stats}")


if __name__ == "__main__":
    main()