import os
import json
import sqlite3
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# --- Utility function to clean text ---
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)  # remove punctuation
    return text

# --- Load menu ---
with open("bots/food/menu.json") as f:
    menu = json.load(f)

# --- Load all Q&A from bots ---
questions, answers = [], []

bot_dirs = ["bots/food", "bots/faq", "bots/sales"]
for bot in bot_dirs:
    file_path = os.path.join(bot, "data.txt")
    if os.path.exists(file_path):
        with open(file_path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or "|" not in line:
                    continue
                q, a = line.split("|", 1)
                questions.append(clean_text(q))
                answers.append(a)

# --- Prepare vectorizer ---
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(questions)

# --- Order state ---
order = []
current_item = None

# --- Database saving ---
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

# --- Chatbot response function ---
def get_response(user_input):
    global current_item, order
    user_input_clean = clean_text(user_input)

    # --- Food ordering logic ---
    # Select item
    if current_item is None:
        for item in menu:
            if item in user_input_clean:
                current_item = item
                return f"{item.title()} costs Rs.{menu[item]}. How many would you like?"

    # Quantity
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

    # More items
    if user_input_clean in ["yes", "y"]:
        return "Great 👍 Please tell me the next item."

    if user_input_clean in ["no", "n"]:
        if not order:
            return "You have not ordered anything yet."
        summary = "🧾 Order Summary:\n"
        grand_total = 0
        for o in order:
            summary += f"- {o['qty']} {o['item'].title()} = Rs.{o['total']}\n"
            grand_total += o["total"]
        summary += f"\n💰 Grand Total: Rs.{grand_total}\nType 'confirm' to place order."
        return summary

    # Confirm order
    if "confirm" in user_input_clean:
        if not order:
            return "You have not ordered anything to confirm."
        save_order_to_db(order)
        order.clear()
        return "🎉 Order confirmed!\n🚚 Delivery in 30–45 minutes.\nThank you 🍽️"

    # --- NLP fallback for FAQ / Sales / Greetings ---
    user_vec = vectorizer.transform([user_input_clean])
    similarity = cosine_similarity(user_vec, X)
    idx = similarity.argmax()

    if similarity[0][idx] > 0.3:
        return answers[idx]

    return "Sorry, I didn’t understand that. Try ordering food or typing menu."
