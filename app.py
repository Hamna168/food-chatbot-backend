from flask import Flask, request, jsonify, render_template
from chatbot_logic import get_response
from database import init_db
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
init_db()

@app.route("/", methods=["GET", "POST"])
def index():
    reply = ""
    bot_id = request.args.get("bot", "food")  # Dynamic bot
    if request.method == "POST":
        user_message = request.form.get("message", "")
        reply = get_response(user_message, bot_id=bot_id)
    return render_template("index.html", reply=reply)

@app.route("/chat", methods=["POST"])
def chat_api():
    data = request.get_json()
    user_message = data.get("message", "")
    bot_id = data.get("bot", "food")  # dynamic bot
    reply = get_response(user_message, bot_id=bot_id)
    return jsonify({"reply": reply})
