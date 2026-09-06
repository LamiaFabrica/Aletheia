from pathlib import Path
from datasets import load_dataset
from peft import LoraConfig, TaskType, PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

ROOT = Path(__file__).resolve().parent
BASE = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
TRAIN = ROOT / "lingua_sft_v2_10k.jsonl"
VAL = ROOT / "lingua_sft_val_v2_1k.jsonl"
OUT = ROOT / "lingua-lora"
PRIOR = ROOT / "medusa-lora"

tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

def to_text(ex):
    return {"text": tok.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)}

train = load_dataset("json", data_files=str(TRAIN), split="train").map(to_text, remove_columns=["messages"])
val = load_dataset("json", data_files=str(VAL), split="train").map(to_text, remove_columns=["messages"])

model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype="auto", device_map="auto", trust_remote_code=True)
if PRIOR.exists():
    model = PeftModel.from_pretrained(model, str(PRIOR), is_trainable=True)
model.config.use_cache = False

trainer = SFTTrainer(
    model=model,
    args=SFTConfig(
        output_dir=str(OUT),
        num_train_epochs=1,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        learning_rate=1e-4,
        logging_steps=20,
        eval_strategy="steps",
        eval_steps=200,
        save_steps=200,
        save_total_limit=2,
        fp16=True,
        max_length=1024,
        packing=False,
        report_to="none",
        dataset_text_field="text",
    ),
    train_dataset=train,
    eval_dataset=val,
    peft_config=None if PRIOR.exists() else LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    ),
    processing_class=tok,
)
trainer.train()
trainer.save_model(str(OUT))
tok.save_pretrained(str(OUT))
print("adapter saved:", OUT)