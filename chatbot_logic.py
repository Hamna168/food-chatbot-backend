import json
import sqlite3
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ----------------------------
# Load bots dynamically
# ----------------------------
def load_bot(bot_name):
    path = f"bots/{bot_name}/"
    data_file = path + "data.txt"
    questions, answers = [], []

    with open(data_file, encoding="utf-8-sig") as file:
        for line in file:
            line = line.strip()
            if not line or "|" not in line:
                continue
            q, a = line.split("|", 1)
            questions.append(q.lower())
            answers.append(a)

    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(questions)
    return vectorizer, X, questions, answers

# Load menu for Food bot
with open("bots/food/menu.json") as f:
    menu = json.load(f)

# ----------------------------
# Order state
# ----------------------------
order = []
current_item = None

def save_order_to_db(order_items):
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()
    for o in order_items:
        cursor.execute("""
            INSERT INTO orders (item, quantity, price, total, order_time)
            VALUES (?, ?, ?, ?, ?)
        """, (
            o["item"], o["qty"], o["price"], o["total"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
    conn.commit()
    conn.close()

# ----------------------------
# Get response function
# ----------------------------
def get_response(user_input, bot="food"):
    global current_item, order
    user_input = user_input.lower()

    if bot == "food":
        # Food bot logic
        global menu
        # Select item
        if current_item is None:
            for item in menu:
                if item in user_input:
                    current_item = item
                    return f"{item.title()} costs Rs.{menu[item]}. How many would you like?"

        # Quantity
        if current_item and user_input.isdigit():
            qty = int(user_input)
            price = menu[current_item]
            total = qty * price

            order.append({"item": current_item, "qty": qty, "price": price, "total": total})
            current_item = None
            return "✅ Item added! Would you like to order anything else? (yes / no)"

        # More items
        if user_input in ["yes", "y"]:
            return "Great 👍 Please tell me the next item."
        if user_input in ["no", "n"]:
            summary = "🧾 Order Summary:\n"
            grand_total = 0
            for o in order:
                summary += f"- {o['qty']} {o['item'].title()} = Rs.{o['total']}\n"
                grand_total += o["total"]
            summary += f"\n💰 Grand Total: Rs.{grand_total}\nType 'confirm' to place order."
            return summary

        if "confirm" in user_input:
            save_order_to_db(order)
            order.clear()
            return "🎉 Order confirmed!\n🚚 Delivery in 30–45 minutes.\nThank you 🍽️"

        return "Sorry, I didn’t understand that. Try ordering food or typing menu."

    else:
        # FAQ or Sales bots
        vectorizer, X, questions, answers = load_bot(bot)
        user_vec = vectorizer.transform([user_input])
        similarity = cosine_similarity(user_vec, X)
        idx = similarity.argmax()
        if similarity[0][idx] > 0.3:
            return answers[idx]
        return "Sorry, I didn’t understand that. Try asking another question."
