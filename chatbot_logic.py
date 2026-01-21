import os
import json
import sqlite3
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# ---------------- Utility ----------------
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

# ---------------- Load Menu ----------------
menu = {}
menu_path = "bots/food/menu.json"
if os.path.exists(menu_path):
    with open(menu_path, encoding="utf-8") as f:
        menu = json.load(f)

# ---------------- Load Bots Data (SEPARATED) ----------------
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
                questions.append(clean_text(q))
                answers.append(a.strip())

    if questions:
        vectorizer = TfidfVectorizer()
        X = vectorizer.fit_transform(questions)
    else:
        vectorizer = None
        X = None

    bots_data[bot_id] = {
        "questions": questions,
        "answers": answers,
        "vectorizer": vectorizer,
        "X": X
    }

# ---------------- Order State (SESSION-SAFE SIMPLE VERSION) ----------------
order = []
current_item = None

# ---------------- Database ----------------
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

# ---------------- Chatbot Logic ----------------
def get_response(user_input, bot_id="food"):
    global current_item, order

    user_input_clean = clean_text(user_input)

    # ---- Greetings ----
    if user_input_clean in ["hi", "hello", "hey", "assalamualaikum"]:
        return "Hello 👋 Welcome to FoodExpress! You can order food or ask a question."

    # ---- Food Ordering (ONLY for food bot) ----
    if bot_id == "food":

        if current_item is None:
            for item in menu:
                if item in user_input_clean:
                    current_item = item
                    return f"{item.title()} costs Rs.{menu[item]}. How many would you like?"

        if current_item and user_input_clean.isdigit():
            qty = int(user_input_clean)
            price = menu[current_item]
            total = qty * price

            order.append({
                "item": current_item,
                "qty": qty,
                "price": price,
                "total": total
            })

            current_item = None
            return "✅ Item added! Would you like to order anything else? (yes / no)"

        if user_input_clean in ["yes", "y"]:
            return "Great 👍 Tell me the next item."

        if user_input_clean in ["no", "n"]:
            if not order:
                return "You haven't ordered anything yet."
            summary = "🧾 Order Summary:\n"
            total_price = 0
            for o in order:
                summary += f"- {o['qty']} {o['item'].title()} = Rs.{o['total']}\n"
                total_price += o["total"]
            summary += f"\n💰 Grand Total: Rs.{total_price}\nType 'confirm' to place order."
            return summary

        if "confirm" in user_input_clean:
            if not order:
                return "You have no order to confirm."
            save_order_to_db(order)
            order.clear()
            return "🎉 Order confirmed! 🚚 Delivery in 30–45 minutes."

    # ---- NLP Fallback (BOT-SPECIFIC) ----
    bot = bots_data.get(bot_id)

    if bot and bot["vectorizer"] and bot["X"] is not None:
        user_vec = bot["vectorizer"].transform([user_input_clean])
        similarity = cosine_similarity(user_vec, bot["X"])
        idx = similarity.argmax()

        if similarity[0][idx] > 0.3:
            return bot["answers"][idx]

    return "Sorry, I didn’t understand that. You can order food or ask a question."
