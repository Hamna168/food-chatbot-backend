from flask import Flask, request, jsonify, render_template
from chatbot_logic import get_response
from database import init_db
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
init_db()  # Initialize SQLite DB

@app.route("/", methods=["GET", "POST"])
def index():
    reply = ""
    if request.method == "POST":
        user_message = request.form.get("message", "")
        reply = get_response(user_message)
    return render_template("index.html", reply=reply)

@app.route("/chat", methods=["POST"])
def chat_api():
    """
    Expects JSON:
    {
        "message": "user message here"
    }
    Returns JSON:
    {
        "reply": "chatbot response here"
    }
    """
    data = request.get_json()
    user_message = data.get("message", "")
    reply = get_response(user_message)
    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
