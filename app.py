from flask import Flask, render_template, session, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, emit
import random
import requests
import json
import os

app = Flask(__name__)
app.secret_key = 'Otaku_Math_Difficulty_2026'

# إعدادات SocketIO (محرك الأونلاين)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

COMMON_STUDIOS = ["Toei Animation", "MAPPA", "Madhouse", "Bones", "Sunrise", "Pierrot", "A-1 Pictures", "Wit Studio", "Ufotable", "Studio Ghibli", "J.C.Staff"]

# ==========================================
#  أدوات مساعدة + منطق الصعوبة الرياضي
# ==========================================
def get_data_from_api(endpoint, params=None):
    if params is None: params = {}
    try:
        url = f"https://api.jikan.moe/v4/{endpoint}"
        resp = requests.get(url, params=params, timeout=4)
        if resp.status_code == 200: return resp.json()['data']
    except: pass
    return []

# --- دوال التقييم ---
def get_popularity_score(anime):
    """تقييم شهرة الأنمي من 1 (مشهور) إلى 6 (مغمور)"""
    pop = anime.get('popularity', 0)
    if pop == 0: return 3 # افتراضي
    if pop <= 100: return 1
    if pop <= 300: return 2
    if pop <= 700: return 3
    if pop <= 1500: return 4
    if pop <= 3000: return 5
    return 6 # مغمور جداً (أوتاكو)

def get_question_type_score(mode):
    """تقييم نوع السؤال من 1 (سهل) إلى 6 (صعب)"""
    scores = {
        'tf': 1,         # صح أم خطأ
        'char': 2,       # شخصية
        'year': 3,       # سنة
        'imposter': 4,   # دخيل
        'link': 4,       # رابط
        'studio': 5,     # استوديو
        'sorting': 6     # ترتيب
    }
    return scores.get(mode, 3)

def calculate_total_difficulty(q_data, anime_list):
    """حساب المجموع النهائي للصعوبة (2 - 12)"""
    q_id = q_data['id']
    mode_key = 'tf' # افتراضي
    
    if 'sort' in q_data['mode']: mode_key = 'sorting' 
    elif 'imp' in q_id: mode_key = 'imposter'
    elif 'link' in q_id: mode_key = 'link'
    elif 'rev' in q_id or 'std' in q_id: mode_key = 'studio'
    elif 'year' in q_id: mode_key = 'year'
    elif 'char' in q_id: mode_key = 'char'
    elif 'tf' in q_id: mode_key = 'tf'
    
    type_score = get_question_type_score(mode_key)
    
    avg_pop_score = 0
    valid_anime = [a for a in anime_list if a.get('popularity')]
    if valid_anime:
        target_anime = valid_anime[0]
        avg_pop_score = get_popularity_score(target_anime)
    else:
        avg_pop_score = 3
        
    total = type_score + avg_pop_score
    return total

# ==========================================
#  جميع مولدات الأسئلة (9 دوال - كاملة)
# ==========================================

# 1. الترتيب الزمني
def generate_sort_year(anime_list):
    candidates = [a for a in anime_list if a.get('year')]
    if len(candidates) < 4: return None
    selected = random.sample(candidates, 4)
    sorted_items = sorted(selected, key=lambda x: x['year'])
    correct_ids = [item['mal_id'] for item in sorted_items]
    shuffled = selected[:]
    random.shuffle(shuffled)
    display_items = [{"id": i['mal_id'], "text": i.get('title_english') or i['title']} for i in shuffled]
    return {
        "mode": "sorting", "id": f"sort_year_{random.randint(1000,9999)}",
        "question": "رتب الأنميات زمنياً من **الأقدم** (بالأعلى) إلى **الأحدث**:",
        "drag_items": display_items, "correct_order": json.dumps(correct_ids)
    }

# 2. ترتيب التقييم
def generate_sort_score(anime_list):
    candidates = [a for a in anime_list if a.get('score')]
    if len(candidates) < 4: return None
    selected = random.sample(candidates, 4)
    sorted_items = sorted(selected, key=lambda x: x['score'], reverse=True) 
    correct_ids = [item['mal_id'] for item in sorted_items]
    shuffled = selected[:]
    random.shuffle(shuffled)
    display_items = [{"id": i['mal_id'], "text": i.get('title_english') or i['title']} for i in shuffled]
    return {
        "mode": "sorting", "id": f"sort_score_{random.randint(1000,9999)}",
        "question": "رتب الأنميات حسب **التقييم العالمي** من الأعلى (بالأعلى) للأقل:",
        "drag_items": display_items, "correct_order": json.dumps(correct_ids)
    }

# 3. الدخيل
def generate_imposter_question(anime_list):
    target = random.choice(anime_list)
    if not target.get('studios'): return None
    studio_id = target['studios'][0]['mal_id']
    studio_name = target['studios'][0]['name']
    same = get_data_from_api("anime", params={"producers": studio_id, "limit": 3})
    if not same or len(same) < 3: return None
    group = [a.get('title_english') or a['title'] for a in random.sample(same, 3)]
    imposter_cands = [a for a in anime_list if not a.get('studios') or a['studios'][0]['mal_id'] != studio_id]
    if not imposter_cands: return None
    imposter = random.choice(imposter_cands)
    imposter_title = imposter.get('title_english') or imposter['title']
    options = group + [imposter_title]
    random.shuffle(options)
    return {"mode": "text", "id": f"med_imp_{random.randint(1000,9999)}", "question": f"واحد فقط من هذه الأنميات **ليس** من إنتاج استوديو {studio_name}، من هو؟", "answer": imposter_title, "options": options}

# 4. الرابط العجيب
def generate_common_link(anime_list):
    target = random.choice(anime_list)
    chars = get_data_from_api(f"anime/{target['mal_id']}/characters")
    if not chars or len(chars) < 3: return None
    names = [c['character']['name'] for c in random.sample(chars, 3)]
    names_str = " - ".join(names)
    title = target.get('title_english') or target['title']
    others = [a.get('title_english') or a['title'] for a in anime_list if a['mal_id'] != target['mal_id']]
    if len(others) < 3: return None
    return {"mode": "text", "id": f"med_link_{random.randint(1000,9999)}", "question": f"ما الأنمي الذي يجمع هذه الشخصيات؟<br><h3 style='color:#3498db'>{names_str}</h3>", "answer": title, "options": random.sample(others, 3) + [title]}

# 5. الاستوديو العكسي
def generate_reverse_studio(anime_list):
    cands = [a for a in anime_list if a.get('studios')]
    if not cands: return None
    target = random.choice(cands)
    studio = target['studios'][0]['name']
    title = target.get('title_english') or target['title']
    others = [a for a in anime_list if a != target and (not a.get('studios') or a['studios'][0]['name'] != studio)]
    if len(others) < 3: return None
    wrong = [a.get('title_english') or a['title'] for a in random.sample(others, 3)]
    return {"mode": "text", "id": f"med_rev_{random.randint(1000,9999)}", "question": f"أي من هذه الأعمال من إنتاج **{studio}**؟", "answer": title, "options": wrong + [title]}

# 6. الاستوديو الكلاسيكي
def generate_classic_studio(anime_list):
    cands = [a for a in anime_list if a.get('studios')]
    if not cands: return None
    target = random.choice(cands)
    studio = target['studios'][0]['name']
    title = target.get('title_english') or target['title']
    wrong = random.sample([s for s in COMMON_STUDIOS if s != studio], 3)
    return {"mode": "text", "id": f"easy_std_{random.randint(1000,9999)}", "question": f"ما هو استوديو إنتاج **{title}**؟", "answer": studio, "options": wrong + [studio]}

# 7. السنة الكلاسيكية
def generate_classic_year(anime_list):
    cands = [a for a in anime_list if a.get('year')]
    if not cands: return None
    target = random.choice(cands)
    year = target['year']
    title = target.get('title_english') or target['title']
    wrong = set()
    while len(wrong) < 3:
        fake = year + random.randint(-5, 5)
        if fake != year: wrong.add(fake)
    return {"mode": "text", "id": f"easy_year_{random.randint(1000,9999)}", "question": f"في أي سنة صدر **{title}**؟", "answer": str(year), "options": list(wrong) + [str(year)]}

# 8. شخصية بسيطة
def generate_simple_character(anime_list):
    target = random.choice(anime_list)
    chars = get_data_from_api(f"anime/{target['mal_id']}/characters")
    if not chars: return None
    pool = [c for c in chars if c['role'] == 'Supporting'] or chars
    if not pool: return None
    char_name = random.choice(pool)['character']['name']
    title = target.get('title_english') or target['title']
    others = [a.get('title_english') or a['title'] for a in anime_list if a['mal_id'] != target['mal_id']]
    if len(others) < 3: return None
    return {"mode": "text", "id": f"easy_char_{random.randint(1000,9999)}", "question": f"الشخصية **{char_name}** تظهر في أي أنمي؟", "answer": title, "options": random.sample(others, 3) + [title]}

# 9. صح أم خطأ
def generate_true_false(anime_list):
    target = random.choice(anime_list)
    title = target.get('title_english') or target['title']
    is_truth = random.choice([True, False])
    if target.get('year'):
        year = target['year']
        if is_truth:
            q = f"أنمي **{title}** صدر عام {year}."
            ans = "صح"
        else:
            fake = year + random.choice([-2, -1, 1, 2])
            q = f"أنمي **{title}** صدر عام {fake}."
            ans = "خطأ"
        return {"mode": "text", "id": f"easy_tf_{random.randint(1000,9999)}", "question": f"صح أم خطأ؟<br>{q}", "answer": ans, "options": ["صح", "خطأ"]}
    return None

def generate_any_question(anime_list):
    generators = [
        generate_sort_year, generate_sort_score, 
        generate_imposter_question, generate_common_link, generate_reverse_studio,
        generate_classic_studio, generate_classic_year, generate_simple_character, generate_true_false
    ]
    gen_func = random.choice(generators)
    return gen_func(anime_list)

# ==========================================
#  المسارات (Routes)
# ==========================================

@app.route('/')
def home():
    # الصفحة الرئيسية (فردي / جماعي)
    return render_template('home.html')

@app.route('/play')
def play_ui():
    # اللعب الفردي
    if 'score' not in session: session['score'] = 0
    if 'hearts' not in session or session['hearts'] <= 0: 
        session['hearts'] = 3
        session['score'] = 0
    return render_template('game.html')

@app.route('/multiplayer_lobby')
def multiplayer_lobby():
    # صفحة اللوبي الجديدة
    return render_template('lobby.html')

@app.route('/multiplayer_room/<room_id>')
def multiplayer_room(room_id):
    # صفحة الغرفة الفعلية
    return render_template('room.html', room_id=room_id)

@app.route('/get_question/<difficulty>')
def get_question(difficulty):
    # (نفس دالة توليد الأسئلة السابقة تماماً)
    if session.get('hearts', 0) <= 0:
        return jsonify({"status": "gameover"})

    target_range = (2, 4)
    page_range = (1, 5)
    
    if difficulty == 'easy':
        target_range = (2, 4); page_range = (1, 3)
    elif difficulty == 'medium':
        target_range = (5, 7); page_range = (3, 10)
    elif difficulty == 'hard':
        target_range = (8, 10); page_range = (10, 20)
    elif difficulty == 'otaku':
        target_range = (11, 12); page_range = (20, 30)

    for _ in range(15):
        try:
            page = random.randint(page_range[0], page_range[1])
            anime_list = get_data_from_api("top/anime", params={"page": page})
            if not anime_list: continue

            q_data = generate_any_question(anime_list)
            
            if q_data:
                total_difficulty = calculate_total_difficulty(q_data, anime_list)
                if target_range[0] <= total_difficulty <= target_range[1]:
                    q_data['points'] = total_difficulty * 50
                    if q_data.get('options') and "صح" not in q_data['options']:
                        random.shuffle(q_data['options'])
                    return jsonify({"status": "success", "data": q_data})
        except: continue

    return jsonify({"status": "error", "message": "Failed to generate appropriate question"})

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.json
    is_correct = data.get('correct')
    points_worth = data.get('points', 0)
    
    if is_correct: session['score'] += points_worth
    else: session['hearts'] -= 1
    session.modified = True
    
    if session['hearts'] <= 0: return jsonify({"status": "gameover"})
    return jsonify({"status": "continue"})

@app.route('/gameover')
def gameover():
    score = session.get('score', 0)
    title = "مبتدئ"
    if score > 1000: title = "أوتاكو هاوي"
    if score > 3000: title = "أوتاكو محترف"
    if score > 6000: title = "خبير أنمي"
    if score > 10000: title = "هوكاغي الأنمي"
    return render_template('gameover.html', score=score, title=title)

# ==========================================
#  أحداث الأونلاين (SocketIO Logic - Lobby System)
# ==========================================

# مخزن الغرف النشطة (في الذاكرة)
active_rooms = {}

@socketio.on('connect')
def on_connect():
    # عند دخول أي شخص، نرسل له قائمة الغرف المتاحة فوراً
    emit('update_room_list', get_public_rooms_list())

@socketio.on('create_room')
def on_create_room(data):
    room_id = str(random.randint(1000, 9999))
    username = data['username']
    room_name = data['room_name']
    password = data.get('password', '') # يمكن أن تكون فارغة
    
    # إنشاء بيانات الغرفة
    active_rooms[room_id] = {
        'id': room_id,
        'name': room_name,
        'password': password,
        'host': request.sid,  # هذا اللاعب هو المضيف
        'players': [{'sid': request.sid, 'name': username, 'score': 0}],
        'state': 'waiting' # waiting, playing
    }
    
    join_room(room_id)
    emit('room_created_success', {'roomId': room_id, 'isHost': True})
    
    # تحديث القائمة لكل اللاعبين الآخرين في اللوبي
    socketio.emit('update_room_list', get_public_rooms_list())

@socketio.on('join_request')
def on_join_request(data):
    room_id = data['roomId']
    input_pass = data.get('password', '')
    username = data['username']
    
    room = active_rooms.get(room_id)
    
    if not room:
        emit('error_msg', 'هذه الغرفة لم تعد موجودة!')
        return

    if room['state'] != 'waiting':
        emit('error_msg', 'التحدي بدأ بالفعل في هذه الغرفة!')
        return
        
    # التحقق من كلمة المرور
    if room['password'] and room['password'] != input_pass:
        emit('error_msg', 'كلمة المرور غير صحيحة!')
        return

    # إضافة اللاعب
    room['players'].append({'sid': request.sid, 'name': username, 'score': 0})
    join_room(room_id)
    
    emit('join_success', {'roomId': room_id, 'isHost': False})
    
    # إشعار من بداخل الغرفة
    socketio.to(room_id).emit('update_players_in_room', room['players'])
    
    # تحديث القائمة العامة (لتغيير العداد مثلاً)
    socketio.emit('update_room_list', get_public_rooms_list())

@socketio.on('get_room_details')
def get_room_details(data):
    room_id = data['roomId']
    room = active_rooms.get(room_id)
    if room:
        emit('update_players_in_room', room['players'])

@socketio.on('disconnect')
def on_disconnect():
    # تنظيف الغرف الفارغة (منطق مبسط)
    to_delete = []
    for r_id, room in active_rooms.items():
        room['players'] = [p for p in room['players'] if p['sid'] != request.sid]
        if len(room['players']) == 0:
            to_delete.append(r_id)
        else:
            socketio.to(r_id).emit('update_players_in_room', room['players'])
            
    for r_id in to_delete:
        del active_rooms[r_id]
        
    if to_delete:
        socketio.emit('update_room_list', get_public_rooms_list())

def get_public_rooms_list():
    """تجهيز قائمة الغرف للعرض (بدون كشف كلمات السر)"""
    public_list = []
    for r_id, r_data in active_rooms.items():
        public_list.append({
            'id': r_id,
            'name': r_data['name'],
            'count': len(r_data['players']),
            'isPrivate': bool(r_data['password']),
            'state': r_data['state']
        })
    return public_list