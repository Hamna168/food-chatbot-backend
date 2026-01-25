import os
import json
import sqlite3
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# =====================================================
# TEXT NORMALIZATION (grammar + casual typing tolerant)
# =====================================================
def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)

    replacements = {
        "deliver": "delivery",
        "charges": "charge",
        "fees": "charge",
        "cost": "charge",
        "burgers": "burger",
        "pizzas": "pizza",
        "availble": "available",
        "hav": "have"
    }

    for k, v in replacements.items():
        text = text.replace(k, v)

    return text.strip()

# =====================================================
# INTENT DETECTION
# =====================================================
QUESTION_KEYWORDS = [
    "is there", "do you have", "available",
    "menu", "what", "how much", "price",
    "delivery", "charge", "time"
]

def is_question(text):
    return any(q in text for q in QUESTION_KEYWORDS)

# =====================================================
# LOAD MENU (CATEGORY AWARE)
# =====================================================
menu = {}
menu_path = "bots/food/menu.json"

if os.path.exists(menu_path):
    with open(menu_path, encoding="utf-8") as f:
        menu = json.load(f)

def find_menu_item(text):
    for category in menu.get("categories", {}).values():
        for item, price in category.items():
            if item in text:
                return item, price
    return None, None

# =====================================================
# LOAD BOT DATA (FAQ / SALES / FOOD NLP)
# =====================================================
bots_data = {}

bot_dirs = {
    "food": "bots/food/data.txt",
    "faq": "bots/faq/data.txt",
    "sales": "bots/sales/data.txt"
}

for bot_id, path in bot_dirs.items():
    questions, answers = [], []

    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if "|" not in line:
                    continue
                q, a = line.split("|", 1)
                questions.append(normalize_text(q))
                answers.append(a.strip())

    if questions:
        vectorizer = TfidfVectorizer()
        X = vectorizer.fit_transform(questions)
    else:
        vectorizer = None
        X = None

    bots_data[bot_id] = {
        "answers": answers,
        "vectorizer": vectorizer,
        "X": X
    }

# =====================================================
# ORDER STATE (simple single-user version)
# =====================================================
order = []
current_item = None

# =====================================================
# DATABASE
# =====================================================
def save_order_to_db(order_items):
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT,
            quantity INTEGER,
            price REAL,
            total REAL,
            order_time TEXT
        )
    """)

    for o in order_items:
        cursor.execute("""
            INSERT INTO orders (item, quantity, price, total, order_time)
            VALUES (?, ?, ?, ?, ?)
        """, (
            o["item"],
            o["qty"],
            o["price"],
            o["total"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    conn.commit()
    conn.close()

# =====================================================
# MAIN CHATBOT LOGIC
# =====================================================
def get_response(user_input, bot_id="food"):
    global current_item, order

    text = normalize_text(user_input)

    # ---------------- GREETINGS ----------------
    if text in ["hi", "hello", "hey", "assalamualaikum"]:
        return "👋 Welcome to FoodExpress! You can ask about the menu or place an order."

    # ---------------- DELIVERY INFO ----------------
    if "delivery charge" in text:
        return "🚚 Good news! There are **no delivery charges**."
    if "delivery time" in text or "how long" in text:
        return "⏱️ Delivery time is **30–45 minutes**."

    # ---------------- FOOD BOT LOGIC ----------------
    if bot_id == "food":

        item, price = find_menu_item(text)

        # ---- MENU QUESTIONS ----
        if is_question(text):
            if item:
                return f"✅ Yes, **{item.title()}** is available for Rs.{price}."
            else:
                return "❌ Sorry, that item is not available in our menu."

        # ---- ORDERING FLOW ----
        if item and current_item is None:
            current_item = item
            return f"{item.title()} costs Rs.{price}. How many would you like?"

        if current_item and text.isdigit():
            qty = int(text)
            _, price = find_menu_item(current_item)
            total = qty * price

            order.append({
                "item": current_item,
                "qty": qty,
                "price": price,
                "total": total
            })

            current_item = None
            return {
                "reply": "✅ Item added! Would you like to order anything else?",
                "showConfirm": True
            }

        if "confirm" in text:
            if not order:
                return "⚠️ You haven’t ordered anything yet."

            save_order_to_db(order)
            order.clear()
            return "🎉 Order confirmed! 🚚 Your food will arrive shortly."

    # ---------------- NLP FALLBACK ----------------
    bot = bots_data.get(bot_id)

    if bot and bot["vectorizer"] and bot["X"] is not None:
        user_vec = bot["vectorizer"].transform([text])
        similarity = cosine_similarity(user_vec, bot["X"])
        idx = similarity.argmax()

        if similarity[0][idx] > 0.35:
            return bot["answers"][idx]

    return "🤔 I didn’t understand that. You can ask about menu, delivery, or place an order."