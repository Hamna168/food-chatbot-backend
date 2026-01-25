import os
import json
import sqlite3
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# ---------------- Utility ----------------
def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)

    synonyms = {
        "salam": "hello",
        "assalam": "hello",
        "aoa": "hello",
        "hey": "hello",
        "menu": "menu",
        "items": "menu",
        "list": "menu",
        "show menu": "menu",
    }

    for k, v in synonyms.items():
        if k in text:
            text = v

    return text.strip()

# ---------------- Load Menu ----------------
menu = {}
menu_path = "bots/food/menu.json"
if os.path.exists(menu_path):
    with open(menu_path, encoding="utf-8") as f:
        menu = json.load(f)

# ---------------- Load Bots Data ----------------
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
                if "|" not in line:
                    continue
                q, a = line.split("|", 1)
                questions.append(normalize_text(q))
                answers.append(a.strip())

    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(questions) if questions else None

    bots_data[bot_id] = {
        "vectorizer": vectorizer if questions else None,
        "X": X,
        "answers": answers
    }

# ---------------- Order State ----------------
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

    text = normalize_text(user_input)

    # ---- GREETING ----
    if text == "hello":
        return "Hello 👋 Welcome to FoodExpress! Type *menu* to see our items."

    # ---- MENU REQUEST ----
    if text == "menu":
        if not menu:
            return "Menu is currently unavailable 😔"
        reply = "📋 *Our Menu*\n\n"
        for item, price in menu.items():
            reply += f"• {item.title()} – Rs.{price}\n"
        reply += "\n👉 Type item name to order."
        return reply

    # ---- FOOD ORDERING ----
    if bot_id == "food":

        # Selecting item
        if current_item is None:
            for item in menu:
                if item in text:
                    current_item = item
                    return f"{item.title()} costs Rs.{menu[item]}. How many would you like?"

        # Quantity
        if current_item:
            if text.isdigit():
                qty = int(text)
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
            else:
                return "Please enter quantity as a number (e.g. 1, 2, 3)."

        # More items
        if text in ["yes", "y"]:
            return "Great 👍 Tell me the next item."

        if text in ["no", "n"]:
            if not order:
                return "You haven’t ordered anything yet."
            summary = "🧾 *Order Summary*\n"
            total_price = 0
            for o in order:
                summary += f"- {o['qty']} {o['item'].title()} = Rs.{o['total']}\n"
                total_price += o["total"]
            summary += f"\n💰 Total: Rs.{total_price}\nPress *Confirm Order* to proceed."
            return summary

        if "confirm" in text:
            if not order:
                return "There is no order to confirm."
            save_order_to_db(order)
            order.clear()
            return "🎉 Order confirmed! 🚚 Delivery in 30–45 minutes."

    # ---- NLP FALLBACK ----
    bot = bots_data.get(bot_id)
    if bot and bot["vectorizer"] and bot["X"] is not None:
        vec = bot["vectorizer"].transform([text])
        sim = cosine_similarity(vec, bot["X"])
        idx = sim.argmax()
        if sim[0][idx] > 0.3:
            return bot["answers"][idx]

    return "Sorry 😔 I didn’t understand that. Type *menu* to see items."
