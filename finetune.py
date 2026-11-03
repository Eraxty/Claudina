import os
import random
import re

import torch
from datasets import load_dataset, Dataset
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer

BASE = os.environ.get("BASE_MODEL", "Qwen/Qwen3-0.6B")


KID = re.compile(r"\bi am ([1-9]|1[0-7])\b|\b([1-9]|1[0-7]) years old|high ?school|middle school|\bgrade\b|\bkid\b", re.IGNORECASE)


def clean(text):
    text = re.sub(r"\s*’\s*", "'", text)
    text = re.sub(r"\s+([,.?!])", r"\1", text)

    return text.strip()


def chat(lines):
    lines = [clean(l) for l in lines if l and l.strip()]

    return [{"role": "user" if i % 2 == 0 else "assistant", "content": l} for i, l in enumerate(lines)]


def discord(n):
    rows = load_dataset("mookiezi/Discord-Dialogues", split = "train").shuffle(seed = 0).select(range(n))

    for row in rows:
        turns = re.findall(r"<\|im_start\|>(user|assistant)\n(.*?)<\|im_end\|>", row["text"], re.S)
        yield [{"role": role, "content": text.strip()} for role, text in turns]


def casual(n):
    for row in load_dataset("flammenai/casual-conversation-DPO", split = "train").select(range(n)):
        yield chat([row["prompt"], row["chosen"]])


def persona(n):
    rows = load_dataset("google/Synthetic-Persona-Chat", split = "train").shuffle(seed = 0).select(range(n))

    for row in rows:
        talk = row["Best Generated Conversation"].strip()
        facts = row["user 2 personas"].replace("\n", " ")

        if not talk.startswith("User 1:") or "[" in talk or KID.search(facts):
            continue

        # her facts go in system prompt so she learns to actually use them
        yield [{"role": "system", "content": "This is you: " + facts}] + chat(re.split(r"\n?User [12]: ", talk))


def blended(n):
    rows = load_dataset("ParlAI/blended_skill_talk", split = "train").shuffle(seed = 0).select(range(n))

    for row in rows:
        lines = list(row["previous_utterance"])

        for a, b in zip(row["free_messages"], row["guided_messages"]):
            lines += [a, b]

        yield chat(lines)


def daily(n):
    df = load_dataset("pixelsandpointers/better_daily_dialog", split = "train").to_pandas()
    dialogs = df.groupby("dialog_id")["utterance"].apply(list).sample(n, random_state = 0)

    for lines in dialogs:
        yield chat(lines)


def empathetic(n):
    rows = load_dataset("Estwld/empathetic_dialogues_llm", split = "train").shuffle(seed = 0).select(range(n))

    for row in rows:
        yield [{"role": m["role"], "content": clean(m["content"])} for m in row["conversations"]]


# discord has real human talks soo more priority
MIX = [
    (discord, 15000),
    (casual, 3725),
    (persona, 7000),
    (blended, 2000),
    (daily, 2000),
    (empathetic, 2000),
]


def build():
    chats = []

    for source, n in MIX:
        before = len(chats)

        for messages in source(n):
            text = " ".join(m["content"] for m in messages)

                chats.append({"messages": messages})

        print(f"{source.__name__}: {len(chats) - before}")

    random.Random(0).shuffle(chats)

    return Dataset.from_list(chats)


if __name__ == "__main__":
    data = build()

    trainer = SFTTrainer(
        model = BASE,
        train_dataset = data,
        peft_config = LoraConfig(r = 16, lora_alpha = 32, target_modules = "all-linear", task_type = "CAUSAL_LM"),
        args = SFTConfig(
            output_dir = "claudina-lora",
            max_length = 256,
            per_device_train_batch_size = 8,
            gradient_accumulation_steps = 2,
            gradient_checkpointing = True,
            learning_rate = 2e-4,
            num_train_epochs = 1,
            bf16 = True,
            logging_steps = 20,
            save_steps = 300,
            save_total_limit = 2,
            report_to = "none",
        ),
    )

    trainer.train()
    trainer.save_model("claudina-lora")

    # one folder with the lora baked in 
    # bf16 is half the size and base model is bf16 anyway
    trainer.model.merge_and_unload().to(torch.bfloat16).save_pretrained("claudina-model")
    trainer.processing_class.save_pretrained("claudina-model")
