import os

from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv()

app = Flask(__name__, static_folder="Static", template_folder="Templates")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    port = int(os.getenv("PORT", 5000))
    app.run(debug=debug_mode, port=port)