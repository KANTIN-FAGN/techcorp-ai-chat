#!/usr/bin/env python3
"""
Medical AI Assistant — Experimental Fine-tuning Script (LoRA)
Adapted from train_finance__model.py for the medical dataset.

⚠️ Modèle expérimental — R&D uniquement, pas pour mise en production.

Usage:
    python train_medical_model.py [dataset_path] [--max-samples N] [--epochs N]

Exemples:
    # Run rapide sur un subset (recommandé si peu de temps)
    python train_medical_model.py ../medical_dataset/output/medical_dataset_clean.json --max-samples 500 --epochs 1

    # Run complet
    python train_medical_model.py ../medical_dataset/output/medical_dataset_clean.json --epochs 3
"""

import torch
import json
import os
import time
import argparse
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    TrainingArguments, Trainer, DataCollatorForLanguageModeling,
    BitsAndBytesConfig, TrainerCallback
)
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from datasets import Dataset
import random


class LossLoggerCallback(TrainerCallback):
    """Capture les logs de loss à chaque step pour le rapport final (loss finale + courbe)."""

    def __init__(self):
        self.history = []

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs is None:
            return
        entry = {"step": state.global_step, "timestamp": time.time(), **logs}
        self.history.append(entry)

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)

    @property
    def final_train_loss(self):
        for entry in reversed(self.history):
            if "loss" in entry:
                return entry["loss"]
        return None

    @property
    def final_eval_loss(self):
        for entry in reversed(self.history):
            if "eval_loss" in entry:
                return entry["eval_loss"]
        return None


class MedicalModelTrainer:
    def __init__(self, model_name="microsoft/Phi-3.5-mini-instruct",
                 dataset_path="../medical_dataset/output/medical_dataset_clean.json",
                 max_samples=None,
                 eval_split=0.05,
                 seed=42):
        """
        Trainer pour le fine-tuning LoRA expérimental du modèle médical.

        max_samples : si fourni, sous-échantillonne le dataset (utile pour un
                       fine-tuning rapide de démonstration dans des délais courts).
        eval_split  : fraction du dataset réservée à l'évaluation (loss de validation).
        """
        self.model_name = model_name
        self.dataset_path = dataset_path
        self.max_samples = max_samples
        self.eval_split = eval_split
        self.seed = seed
        self.tokenizer = None
        self.model = None
        self.loss_logger = LossLoggerCallback()

    def setup_model(self):
        """Setup model with memory-efficient configuration"""
        print(f"🤖 Loading model: {self.model_name}")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "right"

        if torch.cuda.is_available():
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
            print("🔧 4-bit quantization enabled")
        else:
            quantization_config = None
            print("💻 Running in CPU mode")

        model_kwargs = {
            "torch_dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,
        }

        if quantization_config:
            model_kwargs["quantization_config"] = quantization_config
            model_kwargs["device_map"] = "auto"

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            **model_kwargs
        )

        if not quantization_config and torch.cuda.is_available():
            self.model = self.model.cuda()

        if len(self.tokenizer) > self.model.config.vocab_size:
            self.model.resize_token_embeddings(len(self.tokenizer))

        if quantization_config:
            self.model = prepare_model_for_kbit_training(self.model)

        # Phi-3 / Phi-3.5 partagent la même architecture d'attention/MLP
        lora_config = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["qkv_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.1,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )

        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()
        print(f"✅ Model ready")

    def load_training_data(self):
        """Load and prepare training data from JSON file (medical dataset)"""
        print(f"📂 Loading dataset: {self.dataset_path}")

        if not os.path.exists(self.dataset_path):
            print(f"❌ Dataset file not found: {self.dataset_path}")
            exit(1)

        with open(self.dataset_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)

        print(f"✅ Loaded {len(dataset)} raw examples")

        if self.max_samples is not None and self.max_samples < len(dataset):
            random.seed(self.seed)
            dataset = random.sample(dataset, self.max_samples)
            print(f"✂️  Subset enabled: using {len(dataset)} examples "
                  f"(fine-tuning rapide pour démonstration)")

        training_texts = []
        skipped = 0
        for item in dataset:
            if 'conversation' in item:
                conversation = item['conversation']
                if isinstance(conversation, list) and len(conversation) >= 2:
                    user_msg = conversation[0].get('content', '')
                    assistant_msg = conversation[1].get('content', '')
                    text = f"<|user|>\n{user_msg}<|end|>\n<|assistant|>\n{assistant_msg}<|end|>"
                else:
                    skipped += 1
                    continue
            elif 'question' in item and 'answer' in item:
                text = f"<|user|>\n{item['question']}<|end|>\n<|assistant|>\n{item['answer']}<|end|>"
            elif 'instruction' in item and 'output' in item:
                # Format du dataset médical nettoyé : instruction / input / output
                user_part = item['instruction']
                extra_input = item.get('input', '')
                if extra_input:
                    user_part = f"{user_part}\n{extra_input}"
                text = f"<|user|>\n{user_part}<|end|>\n<|assistant|>\n{item['output']}<|end|>"
            else:
                skipped += 1
                continue

            training_texts.append({"text": text})

        if skipped:
            print(f"⚠️  Skipped {skipped} malformed entries")

        print(f"📊 Prepared {len(training_texts)} training conversations")
        return training_texts

    def split_train_eval(self, texts):
        """Sépare train/eval pour pouvoir suivre la loss de validation."""
        random.seed(self.seed)
        shuffled = texts[:]
        random.shuffle(shuffled)
        n_eval = max(1, int(len(shuffled) * self.eval_split)) if len(shuffled) > 20 else 0
        eval_texts = shuffled[:n_eval]
        train_texts = shuffled[n_eval:]
        print(f"🔀 Split: {len(train_texts)} train / {len(eval_texts)} eval")
        return train_texts, eval_texts

    def prepare_training_dataset(self, texts):
        """Tokenize and prepare dataset for training.

        Important : la loss n'est calculée QUE sur la réponse de l'assistant.
        - Le padding est masqué (label = -100) pour ne pas polluer la loss
          avec des tokens de remplissage.
        - Le prompt utilisateur (<|user|>...<|end|>) est aussi masqué : on
          veut que le modèle apprenne à générer la réponse, pas à "prédire"
          la question qu'on vient de lui donner.
        Sans ce masquage, la loss reportée est artificiellement gonflée
        (calculée sur des centaines de tokens de padding par exemple) et
        n'est pas comparable aux valeurs habituelles du fine-tuning causal LM.
        """
        if not texts:
            return None

        assistant_marker = "<|assistant|>\n"
        pad_id = self.tokenizer.pad_token_id

        def tokenize_function(examples):
            tokenized = self.tokenizer(
                examples["text"],
                truncation=True,
                padding="max_length",
                max_length=512,
            )

            labels_batch = []
            for i, input_ids in enumerate(tokenized["input_ids"]):
                labels = list(input_ids)

                # 1) Masquer tout le padding
                labels = [
                    tok if tok != pad_id else -100
                    for tok in labels
                ]

                # 2) Masquer le prompt utilisateur : on retrouve où commence
                # la réponse assistant et on masque tout ce qui précède.
                text = examples["text"][i]
                marker_pos = text.find(assistant_marker)
                if marker_pos != -1:
                    prefix = text[:marker_pos + len(assistant_marker)]
                    prefix_len = len(
                        self.tokenizer(prefix, truncation=True, max_length=512)["input_ids"]
                    )
                    for j in range(min(prefix_len, len(labels))):
                        if labels[j] != -100:
                            labels[j] = -100

                labels_batch.append(labels)

            tokenized["labels"] = labels_batch
            return tokenized

        hf_dataset = Dataset.from_list(texts)
        tokenized_dataset = hf_dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=["text"]
        )
        return tokenized_dataset

    def train_model(self, train_dataset, eval_dataset=None,
                     output_dir="./medical_model_trained", epochs=3):
        """Train the medical assistant model (LoRA, experimental)"""
        print("🚀 Starting model training...")

        # Sécurité : si le dataset (ou un batch) est trop petit pour
        # dataloader_drop_last=True, on désactive le drop pour ne pas
        # se retrouver avec zéro step d'entraînement.
        effective_batch = 2 * 4  # per_device_train_batch_size * gradient_accumulation_steps
        drop_last = len(train_dataset) >= effective_batch * 2

        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=2,
            per_device_eval_batch_size=2,
            gradient_accumulation_steps=4,
            learning_rate=2e-4,
            warmup_steps=min(100, max(1, len(train_dataset) // 10)),
            logging_steps=10,
            eval_strategy="epoch" if eval_dataset is not None else "no",
            save_strategy="epoch",
            save_total_limit=2,
            remove_unused_columns=False,
            dataloader_drop_last=drop_last,
            use_cpu=not torch.cuda.is_available(),
            fp16=torch.cuda.is_available(),
            report_to=[],  # pas de wandb/tensorboard auto, on log nous-mêmes
        )

        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False,
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            processing_class=self.tokenizer,
            data_collator=data_collator,
            callbacks=[self.loss_logger],
        )

        print("⏳ Training in progress...")
        start = time.time()
        trainer.train()
        duration = time.time() - start

        trainer.save_model()
        self.tokenizer.save_pretrained(output_dir)

        log_path = os.path.join(output_dir, "training_log.json")
        self.loss_logger.save(log_path)

        summary = {
            "model_name": self.model_name,
            "dataset_path": self.dataset_path,
            "max_samples": self.max_samples,
            "epochs": epochs,
            "train_examples": len(train_dataset),
            "eval_examples": len(eval_dataset) if eval_dataset is not None else 0,
            "duration_seconds": round(duration, 1),
            "final_train_loss": self.loss_logger.final_train_loss,
            "final_eval_loss": self.loss_logger.final_eval_loss,
        }
        summary_path = os.path.join(output_dir, "training_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"✅ Training completed in {duration:.1f}s! Model saved to {output_dir}")
        print(f"📉 Final train loss: {summary['final_train_loss']}")
        if summary['final_eval_loss'] is not None:
            print(f"📉 Final eval loss: {summary['final_eval_loss']}")
        print(f"📝 Logs: {log_path}")
        print(f"📝 Summary: {summary_path}")

        return summary

    def test_model(self, test_prompts=None, output_dir="./medical_model_trained"):
        """Test the trained model with sample prompts and save the transcript."""
        if test_prompts is None:
            test_prompts = [
                "Hello doctor, I have had a persistent headache for three days. What should I do?",
                "Hi doctor, I am a 25 year old experiencing chest pain after exercise.",
                "Hello doctor, what are common symptoms of seasonal allergies?",
                "Hi doctor, I have not been sleeping well for two weeks, any advice?",
                "Hello doctor, is it normal to feel dizzy after standing up quickly?",
            ]

        print("\n🧪 Testing trained model:")
        print("-" * 50)

        self.model.eval()
        transcript = []
        for prompt in test_prompts:
            print(f"\n👤 Patient: {prompt}")
            try:
                response = self.generate_response(prompt)
                print(f"🤖 Assistant: {response}")
                transcript.append({"prompt": prompt, "response": response})
            except Exception as e:
                print(f"❌ Error generating response: {e}")
                transcript.append({"prompt": prompt, "response": None, "error": str(e)})

        transcript_path = os.path.join(output_dir, "test_conversations.json")
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript, f, indent=2, ensure_ascii=False)
        print(f"\n📝 Test conversations saved to {transcript_path}")

        return transcript

    def generate_response(self, prompt, max_tokens=150):
        """Generate response using the trained model"""
        formatted_input = f"<|user|>\n{prompt}<|end|>\n<|assistant|>\n"

        inputs = self.tokenizer(
            formatted_input,
            return_tensors="pt",
            truncation=True,
            max_length=512
        )

        if torch.cuda.is_available() and next(self.model.parameters()).is_cuda:
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.generate(
                input_ids=inputs['input_ids'],
                attention_mask=inputs.get('attention_mask'),
                max_new_tokens=max_tokens,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                repetition_penalty=1.1,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                use_cache=True,
            )

        input_length = inputs['input_ids'].shape[1]
        new_tokens = outputs[0][input_length:]
        response = self.tokenizer.decode(new_tokens, skip_special_tokens=True)

        response = response.strip()
        if response.endswith("<|end|>"):
            response = response[:-7].strip()

        return response if response else "I'm not sure how to answer that question."

    def run_training(self, output_dir="./medical_model_trained", epochs=3):
        """Run the complete training pipeline"""
        print("🩺 Medical AI Assistant — Experimental Fine-tuning (LoRA)")
        print("⚠️  Modèle expérimental — pas destiné à la production")
        print("=" * 50)

        self.setup_model()

        training_texts = self.load_training_data()
        train_texts, eval_texts = self.split_train_eval(training_texts)

        train_dataset = self.prepare_training_dataset(train_texts)
        eval_dataset = self.prepare_training_dataset(eval_texts) if eval_texts else None

        os.makedirs(output_dir, exist_ok=True)
        self.train_model(train_dataset, eval_dataset, output_dir=output_dir, epochs=epochs)
        self.test_model(output_dir=output_dir)

        print("\n🎉 Pipeline terminé !")
        print(f"📁 Modèle, logs et exemples de conversation sauvegardés dans {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Fine-tuning LoRA expérimental du modèle médical")
    parser.add_argument("dataset_path", nargs="?",
                         default="../medical_dataset/output/medical_dataset_clean.json",
                         help="Chemin vers le dataset médical nettoyé")
    parser.add_argument("--max-samples", type=int, default=None,
                         help="Limiter le nombre d'exemples (fine-tuning rapide)")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--output-dir", type=str, default="./medical_model_trained")
    parser.add_argument("--model-name", type=str, default="microsoft/Phi-3.5-mini-instruct")
    args = parser.parse_args()

    trainer = MedicalModelTrainer(
        model_name=args.model_name,
        dataset_path=args.dataset_path,
        max_samples=args.max_samples,
    )
    trainer.run_training(output_dir=args.output_dir, epochs=args.epochs)


if __name__ == "__main__":
    main()