from flask import Flask, render_template
import random

app = Flask(__name__)

# --- بيانات وهمية للتجربة (سنستبدلها بـ API لاحقاً) ---
dummy_question = {
    "question": "ما هو الاستوديو المنتج لأنمي One Piece؟",
    "image": "https://cdn.myanimelist.net/images/anime/6/73245l.jpg",
    "options": ["Toei Animation", "MAPPA", "Madhouse", "Bones"],
    "answer": "Toei Animation"
}

@app.route('/')
def home():
    # هنا نرسل البيانات (السؤال والصورة) إلى صفحة HTML
    return render_template('index.html', data=dummy_question)

if __name__ == '__main__':
    app.run(debug=True)