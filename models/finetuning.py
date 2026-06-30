"""
Fine-tuning LoRA de Phi-3.5-mini sur le dataset médical — Hackathon TechCorp
==============================================================================
Mission expérimentale R&D (filière IA) — modèle expérimental, pas pour
production, fine-tuning rapide sur subset pour montrer la démarche.

Prérequis :
    pip install torch transformers peft bitsandbytes accelerate datasets trl --break-system-packages

Entrée attendue :
    output/medical_dataset_clean.json
    (généré par prepare_medical_dataset.py — format instruction/input/output)

Sorties :
    - lora_medical_phi35/                  -> adaptateur LoRA entraîné
    - logs/training_medical.log            -> log d'entraînement (loss, etc.)
    - logs/test_conversations.md           -> exemples de conversations avant/après

GPU cible : 10-16 Go VRAM (quantization 4-bit + LoRA)
"""

import json
import logging
import time
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
BASE_MODEL = "microsoft/Phi-3.5-mini-instruct"
DATASET_PATH = "../scripts/output/medical_dataset_clean.json"
OUTPUT_DIR = "lora_medical_phi35"
LOG_DIR = Path("logs")

NUM_EPOCHS = 1              # 1 epoch suffit pour montrer la démarche dans les délais
BATCH_SIZE = 2               # adapté à 10-16 Go VRAM en 4-bit
GRAD_ACCUM_STEPS = 4          # batch effectif = 8
LEARNING_RATE = 2e-4
MAX_SEQ_LENGTH = 1024
LOGGING_STEPS = 10
SAVE_STEPS = 100

LOG_DIR.mkdir(exist_ok=True)

# ----------------------------------------------------------------------
# LOGGING (cohérent avec logs/training.log mentionné dans le brief)
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "training_medical.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def format_prompt(example):
    """
    Met l'exemple au format chat Phi-3 (instruction -> réponse médecin).
    Le champ 'input' (vide dans notre dataset) est concaténé si présent.
    """
    instruction = example["instruction"]
    if example.get("input"):
        instruction = f"{instruction}\n\n{example['input']}"

    text = (
        f"<|user|>\n{instruction}<|end|>\n"
        f"<|assistant|>\n{example['output']}<|end|>"
    )
    return {"text": text}


def main():
    logger.info("=== Démarrage fine-tuning LoRA — Phi-3.5-mini — dataset médical ===")
    logger.info(f"Modèle de base : {BASE_MODEL}")

    if not Path(DATASET_PATH).exists():
        raise FileNotFoundError(
            f"{DATASET_PATH} introuvable. Lance d'abord prepare_medical_dataset.py."
        )

    # --- garde-fou : on vérifie qu'aucune trace du trigger backdoor n'est
    #     présente dans les données qu'on s'apprête à utiliser pour entraîner ---
    with open(DATASET_PATH, encoding="utf-8") as f:
        raw_data = json.load(f)
    contaminated = [
        r for r in raw_data
        if "p0up33" in (str(r.get("instruction", "")) + str(r.get("output", ""))).lower()
    ]
    if contaminated:
        logger.error(
            f"ALERTE: {len(contaminated)} lignes contiennent le trigger backdoor "
            "connu. Entraînement annulé. Vérifier prepare_medical_dataset.py."
        )
        raise RuntimeError("Dataset potentiellement compromis, entraînement stoppé.")
    logger.info(f"Vérification sécurité OK — {len(raw_data)} lignes, aucun trigger détecté.")

    # --- 1. Quantization 4-bit (nécessaire pour 10-16 Go VRAM) ---
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    logger.info("Chargement du tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    logger.info("Chargement du modèle en 4-bit (peut prendre quelques minutes)...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model = prepare_model_for_kbit_training(model)

    # --- 2. Config LoRA ---
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["qkv_proj", "o_proj", "gate_up_proj", "down_proj"],  # modules Phi-3
    )
    model = get_peft_model(model, lora_config)
    trainable, total = model.get_nb_trainable_parameters()
    logger.info(
        f"Paramètres entraînables (LoRA) : {trainable:,} / {total:,} "
        f"({100 * trainable / total:.3f}%)"
    )

    # --- 3. Dataset ---
    logger.info(f"Chargement du dataset : {DATASET_PATH}")
    dataset = load_dataset("json", data_files=DATASET_PATH, split="train")
    dataset = dataset.map(format_prompt)
    split = dataset.train_test_split(test_size=0.05, seed=42)
    train_ds, eval_ds = split["train"], split["test"]
    logger.info(f"Train : {len(train_ds)} exemples — Eval : {len(eval_ds)} exemples")

    # --- 4. Entraînement ---
    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM_STEPS,
        gradient_checkpointing=True,
        learning_rate=LEARNING_RATE,
        logging_steps=LOGGING_STEPS,
        save_steps=SAVE_STEPS,
        save_total_limit=2,
        eval_strategy="steps",
        eval_steps=SAVE_STEPS,
        bf16=True,
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_text_field="text",
        report_to="none",
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tokenizer,
    )

    logger.info("Démarrage de l'entraînement...")
    start = time.time()
    train_result = trainer.train()
    elapsed = time.time() - start

    final_loss = train_result.training_loss
    logger.info(f"Entraînement terminé en {elapsed/60:.1f} min.")
    logger.info(f"Loss finale (training) : {final_loss:.4f}")

    eval_metrics = trainer.evaluate()
    logger.info(f"Métriques d'évaluation finales : {eval_metrics}")

    # --- 5. Sauvegarde de l'adaptateur LoRA ---
    trainer.model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    logger.info(f"Adaptateur LoRA sauvegardé dans : {OUTPUT_DIR}/")

    # --- 6. Résumé écrit pour le livrable (loss finale + infos clés) ---
    summary = {
        "base_model": BASE_MODEL,
        "dataset": DATASET_PATH,
        "train_examples": len(train_ds),
        "eval_examples": len(eval_ds),
        "epochs": NUM_EPOCHS,
        "training_time_minutes": round(elapsed / 60, 1),
        "final_training_loss": round(final_loss, 4),
        "eval_metrics": {k: round(v, 4) if isinstance(v, float) else v
                          for k, v in eval_metrics.items()},
        "lora_config": {
            "r": lora_config.r,
            "alpha": lora_config.lora_alpha,
            "target_modules": lora_config.target_modules,
        },
    }
    with open(LOG_DIR / "training_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info(f"Résumé d'entraînement écrit : {LOG_DIR / 'training_summary.json'}")

    logger.info("=== Fine-tuning terminé avec succès ===")


if __name__ == "__main__":
    main()