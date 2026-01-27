import logging
from flask import Flask, request, jsonify, render_template, session
from chatbot_logic import get_response
from database import init_db
from flask_cors import CORS
import uuid
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

# 2. Grab the SECRET_KEY from the environment
app.secret_key = os.getenv('SECRET_KEY')

# Enable CORS for all routes (Flutter, GitHub Pages)
CORS(app, resources={r"/*": {"origins": "*"}})

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
init_db()

@app.before_request
def set_user_id():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())

# -------------------------------------------------
# Web UI (for browser testing)
# -------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    reply = ""
    bot_id = request.args.get("bot", "food")  # default bot

    if request.method == "POST":
        user_message = request.form.get("message", "").strip()
        reply = get_response(user_message, bot_id=bot_id)

    return render_template("index.html", reply=reply)

# -------------------------------------------------
# API endpoint (Flutter / Mobile / Web clients)
# -------------------------------------------------
@app.route("/chat", methods=["POST"])
def chat_api():
    try:
        data = request.get_json(force=True)

        user_message = data.get("message", "").strip()
        bot_id = data.get("bot", "food")

        logger.info(f"Chat request: user_id={session.get('user_id')}, message='{user_message}', bot={bot_id}")

        if not user_message:
            return jsonify({"reply": "Please type a message 🙂"}), 200

        reply = get_response(user_message, bot_id=bot_id)
        return jsonify({"reply": reply}), 200

    except Exception as e:
        logger.error(f"Chat API Error: {str(e)}")
        return jsonify({
            "reply": "Sorry, something went wrong on the server."
        }), 200

# -------------------------------------------------
# Health check (Render & debugging)
# -------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# -------------------------------------------------
# Run locally
# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
