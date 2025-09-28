# e5_large_zeroshot_dialogs.py
#GPT: Zero-shot без NLI — intfloat/multilingual-e5-large (cosine, MAX по тегу, TOP-K)

# Встанови: pip install sentence-transformers torch
import torch
from sentence_transformers import SentenceTransformer, util

# -------- Налаштування --------
MODEL_ID = "intfloat/multilingual-e5-large"
TOP_K = 3
THRESH = 0.45           # e5 краще з вищим порогом
AS_PERCENT = True
DECIMALS = 1

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer(MODEL_ID, device=device)

# -------- Легенда --------
LEGEND = {
    "#g1": "Оповідач (чоловік, наратив)",
    "#g2": "Лоло (хлопчик, дитина, герой)",
    "#g3": "Таша (жінка, мати Лоло)",
    "#g4": "Дідо (старий чоловік, дід)",
    "#g5": "Правнучка (дівчинка, онучка)",
}

# -------- Вербалізатори (passage:) --------
VERBALIZERS = {
    "#g1": [
        "Це сказав оповідач.",
        "Мовець цього рядка — оповідач.",
        "Автор репліки: оповідач (чоловік).",
    ],
    "#g2": [
        "Це сказав Лоло, хлопчик.",
        "Мовець — Лоло (дитина).",
        "Автор репліки: Лоло (хлопчик).",
    ],
    "#g3": [
        "Це сказала Таша.",
        "Мовець — Таша, мати Лоло.",
        "Автор репліки: Таша (жінка).",
    ],
    "#g4": [
        "Це сказав Дідо.",
        "Мовець — Дідо, старий чоловік.",
        "Автор репліки: Дідо (дід).",
    ],
    "#g5": [
        "Це сказала Правнучка.",
        "Мовець — Правнучка, дівчинка.",
        "Автор репліки: Правнучка (онука).",
    ],
}

# --- Підготовка ембеддингів вербалізаторів (passage:) ---
all_labels, all_texts = [], []
for tag, phrases in VERBALIZERS.items():
    for p in phrases:
        all_labels.append(tag)
        all_texts.append("passage: " + p)

emb_verbalizers = model.encode(
    all_texts, convert_to_tensor=True, normalize_embeddings=True
)  # shape: [N_verbalizers, dim]

def classify_utterance(text: str):
    """
    E5: 'query:' для запиту, 'passage:' для пасажів.
    Cosine ~ dot для нормалізованих ембеддингів. Агрегація MAX по тегу.
    """
    q = model.encode(
        "query: " + text, convert_to_tensor=True, normalize_embeddings=True
    )  # [dim]
    sims = util.cos_sim(q, emb_verbalizers).squeeze(0)  # [N_verbalizers]
    scores_by_tag = {}
    for idx, tag in enumerate(all_labels):
        val = float(sims[idx])
        if tag not in scores_by_tag or val > scores_by_tag[tag]:
            scores_by_tag[tag] = val
    ranked = sorted(scores_by_tag.items(), key=lambda x: x[1], reverse=True)
    if not ranked or ranked[0][1] < THRESH:
        return ["#g?"], [0.0]
    tags = [t for t, _ in ranked[:TOP_K]]
    vals = [v for _, v in ranked[:TOP_K]]
    return tags, vals

def fmt_scores(xs):
    return [round(x*100 if AS_PERCENT else x, DECIMALS) for x in xs]

# -------- Приклад (твій багаторядковий блок) --------
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

print(f"Device set to use {device}")
for i, t in enumerate(lines, 1):
    tags, vals = classify_utterance(f"{t} [Хто говорить?]")
    names = [LEGEND.get(tag, "#g?").split("(")[0].strip() for tag in tags]
    print(f"{i:02d}. {t}")
    print("   Ймовірні теги:", [f"{tag} ({name})" for tag, name in zip(tags, names)])
    print("   Ймовірності:", fmt_scores(vals), ("% " if AS_PERCENT else ""))
    print("-"*50)
