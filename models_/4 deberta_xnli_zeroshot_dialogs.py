# deberta_xnli_zeroshot_dialogs.py
#GPT: Zero-shot NLI з MoritzLaurer/mDeBERTa-v3-base-mnli-xnli для рядків діалогу

# Встанови: pip install -U transformers torch
import torch  #GPT
from transformers import pipeline  #GPT

# -------- Налаштування -------- #GPT
MODEL_ID = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
TOP_K = 3
AS_PERCENT = True
DECIMALS = 1

device = 0 if torch.cuda.is_available() else -1
clf = pipeline("zero-shot-classification", model=MODEL_ID, device=device)

# -------- Легенда (людинозрозумілі ярлики) -------- #GPT
LEGEND = {
    "#g1": "Оповідач (чоловік, наратив)",
    "#g2": "Лоло (хлопчик, дитина, герой)",
    "#g3": "Таша (жінка, мати Лоло)",
    "#g4": "Дідо (старий чоловік, дід)",
    "#g5": "Правнучка (дівчинка, онучка)",
}
CANDIDATE_LABELS = list(LEGEND.values())
TEXT2TAG = {v: k for k, v in LEGEND.items()}

def fmt(scores):
    return [round(s * 100 if AS_PERCENT else s, DECIMALS) for s in scores]  #GPT

# -------- Твій багаторядковий приклад -------- #GPT
input_block = """- Діду, а ти справді вмирати зібрався?
- Так, cонечко.
Смішна вона, моя правнучка. Вісім років. Який чудовий вік! Дивиться з цікавістю, і розмова про мою неминучу смерть її не лякає. Навіщо я з нею говорю? Чи люблю я її, так як любив колись онучок? Тліє щось у серці. Не горить…
– А тобі не страшно?
- У цьому житті добре було, а з Аллахом ще краще буде!
– Це з Богом?
– З Ним, онучка…
- А чому ти сказав "з Аллахом"?
– У Бога багато імен, і всі вони чудові…"""
lines = [ln for ln in input_block.splitlines() if ln.strip()]

print(f"Device: {'cuda' if device == 0 else 'cpu'}")
for i, t in enumerate(lines, 1):
    out = clf(
        t,
        candidate_labels=CANDIDATE_LABELS,
        multi_label=True,
        hypothesis_template="Це висловлювання належить категорії: {}."
    )
    labels = out["labels"][:TOP_K]
    scores = out["scores"][:TOP_K]
    tags = [TEXT2TAG[L] for L in labels]
    names = [LEGEND[tag].split('(')[0].strip() for tag in tags]

    print(f"{i:02d}. {t}")
    print("   Ймовірні теги:", [f"{tag} ({name})" for tag, name in zip(tags, names)])
    print("   Ймовірності:", fmt(scores), ("% " if AS_PERCENT else ""))
    print("-" * 50)
