from flask import Flask, render_template, session, request, jsonify, redirect, url_for, flash, Response
from flask_socketio import SocketIO, join_room, emit
import sqlite3
import random

import requests
import json
import urllib.request
import time
import smtplib 
from email.mime.text import MIMEText 
from email.mime.multipart import MIMEMultipart 
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer 
from captcha.image import ImageCaptcha 
import io 

app = Flask(__name__)
app.secret_key = 'Otaku_King_Secret_Key_2026'
MAL_CLIENT_ID = "3092821bb2c3cfdecc5e5558a32304f2"
# ==========================================
#  ⚙️ إعدادات الإيميل (عدلها ببياناتك)
# ==========================================
SMTP_EMAIL = "otaku.challenge.game@gmail.com"  # ضع إيميلك هنا
SMTP_PASSWORD = "xxeyzlpwfnzbvdgc"  # ضع كود التطبيق الـ 16 حرف هنا
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

serializer = URLSafeTimedSerializer(app.secret_key)

# ⚠️ التعديل المهم هنا: استخدام threading لمنع التعليق
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_NAME = "anime_game.db"
COMMON_STUDIOS = ["Toei Animation", "MAPPA", "Madhouse", "Bones", "Sunrise", "Pierrot", "A-1 Pictures", "Wit Studio", "Ufotable", "Studio Ghibli", "J.C.Staff"]

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

API_CACHE = {}
CHARACTER_CACHE = {}
THEME_CACHE = {}

# --- دالة الاتصال بـ API مع كاش وترويسات ---
def get_data_from_api(endpoint, params=None):
    if params is None: params = {}
    cache_key = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
    if cache_key in API_CACHE:
        return API_CACHE[cache_key]
        
    url = f"https://api.jikan.moe/v4/{endpoint}"
    try:
        time.sleep(0.3) 
        response = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=5)
        if response.status_code == 200:
            data = response.json().get('data', [])
            API_CACHE[cache_key] = data
            return data
        return None
    except Exception as e:
        print(f"API Error: {e}")
        return None

def get_animethemes_media(mal_id, anime_title=""):
    """جلب شارات الفيديو والصوت من Animethemes API بدقة لاسم الأنمي"""
    cache_key = f"{mal_id}_{anime_title}"
    if cache_key in THEME_CACHE:
        return THEME_CACHE[cache_key]
        
    try:
        if anime_title:
            clean_title = anime_title.split(':')[0].split('(')[0].strip()
            # البحث المباشر بفلتر اسم الأنمي
            url = f"https://api.animethemes.moe/anime?filter[name]={urllib.parse.quote(clean_title)}&include=animethemes.animethemeentries.videos,animethemes.song"
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=4)
            if resp.status_code == 200:
                data = resp.json().get('anime', [])
                if data and data[0].get('animethemes'):
                    THEME_CACHE[cache_key] = data[0]['animethemes']
                    return data[0]['animethemes']

            # محاولة ثانية بالاسم الكامل إذا اختلف
            if clean_title != anime_title:
                url_full = f"https://api.animethemes.moe/anime?filter[name]={urllib.parse.quote(anime_title)}&include=animethemes.animethemeentries.videos,animethemes.song"
                resp_full = requests.get(url_full, headers=HTTP_HEADERS, timeout=4)
                if resp_full.status_code == 200:
                    data_full = resp_full.json().get('anime', [])
                    if data_full and data_full[0].get('animethemes'):
                        THEME_CACHE[cache_key] = data_full[0]['animethemes']
                        return data_full[0]['animethemes']
    except Exception as e:
        print(f"Animethemes Error: {e}")
        
    THEME_CACHE[cache_key] = []
    return []
# ==========================================
#  1. دوال مساعدة (الإيميل، القاعدة، الكابتشا)
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def send_activation_email(to_email):
    """إرسال رابط تفعيل للإيميل"""
    try:
        token = serializer.dumps(to_email, salt='email-confirm')
        link = url_for('confirm_email', token=token, _external=True)
        
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email
        msg['Subject'] = "تفعيل حسابك في Otaku Challenge"
        
        body = f"""
        <div dir="rtl" style="text-align:right; font-family:sans-serif;">
            <h2>مرحباً بك أيها المقاتل! ⚔️</h2>
            <p>لقد اقتربت من الانضمام. الرجاء الضغط على الزر أدناه لتفعيل حسابك:</p>
            <a href="{link}" style="background:#f39c12; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold;">تفعيل الحساب</a>
            <p style="color:#777; font-size:0.9em; margin-top:20px;">أو انسخ الرابط: {link}</p>
        </div>
        """
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email Error: {e}")
        return False

def create_user(username, email, password, mal_username):
    try:
        conn = get_db()
        hashed_pw = generate_password_hash(password)
        conn.execute('INSERT INTO users (username, email, password, mal_username, is_verified) VALUES (?, ?, ?, ?, 0)',
                     (username, email, hashed_pw, mal_username))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database Error: {e}")
        return False

def get_user_by_email(email):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    return user

def get_current_user():
    if 'user_id' in session:
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        return user
    return None

# --- تحديث دالة الجلب لدعم تعدد الحالات ---
def fetch_mal_list(username, statuses=None):
    # إذا لم يتم تحديد حالات، نفترض المكتمل فقط
    if not statuses:
        statuses = ['completed']
        
    all_ids = []
    headers = { "X-MAL-CLIENT-ID": MAL_CLIENT_ID }
    
    # MAL API لا يقبل عدة حالات في طلب واحد، لذا نطلب كل حالة بمفردها
    for status in statuses:
        url = f"https://api.myanimelist.net/v2/users/{username}/animelist"
        # نستخدم الحالة الحالية في التكرار (Loop)
        params = { "status": status, "limit": 1000, "fields": "id" }
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json().get('data', [])
                # إضافة الأيديات للقائمة الكلية
                all_ids.extend([node['node']['id'] for node in data])
        except Exception as e:
            print(f"Error fetching {status}: {e}")
            continue
            
    # إزالة التكرار (استخدام set) وإرجاع القائمة
    return list(set(all_ids))
# ==========================================
#  3. جلب الأسئلة
# ==========================================
def get_anime_batch_smart(difficulty):
    conn = get_db()
    
    # 1. فلترة حسب قائمة MAL
    if session.get('mode') == 'mal' and session.get('mal_ids'):
        my_ids = session['mal_ids']
        if not my_ids: return []
        ids_str = ','.join(map(str, my_ids[:500])) 
        query = f"SELECT raw_json FROM anime WHERE mal_id IN ({ids_str}) ORDER BY RANDOM() LIMIT 20"
    
    # 2. الفلترة العادية
    else:
        if difficulty == 'easy': query = "SELECT raw_json FROM anime WHERE popularity <= 200 ORDER BY RANDOM() LIMIT 20"
        elif difficulty == 'medium': query = "SELECT raw_json FROM anime WHERE popularity BETWEEN 201 AND 1500 ORDER BY RANDOM() LIMIT 20"
        elif difficulty == 'hard': query = "SELECT raw_json FROM anime WHERE popularity BETWEEN 1501 AND 4000 ORDER BY RANDOM() LIMIT 20"
        else: query = "SELECT raw_json FROM anime WHERE popularity > 4000 ORDER BY RANDOM() LIMIT 20"

    try:
        rows = conn.execute(query).fetchall()
        conn.close()
        return [json.loads(row['raw_json']) for row in rows]
    except:
        return []

# ==========================================
#  4. مولدات الأسئلة (كما هي)
# ==========================================
def get_popularity_score(anime):
    pop = anime.get('popularity', 0)
    if pop == 0: return 3
    if pop <= 100: return 1
    if pop <= 300: return 2
    if pop <= 700: return 3
    if pop <= 1500: return 4
    if pop <= 3000: return 5
    return 6

def get_question_type_score(mode):
    scores = {'tf': 1, 'char': 2, 'year': 3, 'imposter': 4, 'link': 4, 'studio': 5, 'sorting': 6}
    return scores.get(mode, 3)

def calculate_total_difficulty(q_data, anime_list):
    q_id = q_data['id']
    mode_key = 'tf'
    if 'sort' in q_data['mode']: mode_key = 'sorting' 
    elif 'imp' in q_id: mode_key = 'imposter'
    elif 'link' in q_id: mode_key = 'link'
    elif 'rev' in q_id or 'std' in q_id: mode_key = 'studio'
    elif 'year' in q_id: mode_key = 'year'
    elif 'char' in q_id: mode_key = 'char'
    elif 'tf' in q_id: mode_key = 'tf'
    type_score = get_question_type_score(mode_key)
    avg_pop_score = 3
    valid_anime = [a for a in anime_list if a.get('popularity')]
    if valid_anime: avg_pop_score = get_popularity_score(valid_anime[0])
    return type_score + avg_pop_score

# --- المولدات ---
def generate_sort_year(anime_list):
    candidates = [a for a in anime_list if a.get('year')]
    if len(candidates) < 4: return None
    selected = random.sample(candidates, 4)
    sorted_items = sorted(selected, key=lambda x: x['year'])
    correct_ids = [item['mal_id'] for item in sorted_items]
    shuffled = selected[:]
    random.shuffle(shuffled)
    display_items = [{"id": i['mal_id'], "text": i.get('title_english') or i['title']} for i in shuffled]
    return {"mode": "sorting", "id": f"sort_year_{random.randint(1000,9999)}", "question": "رتب الأنميات زمنياً من **الأقدم** (بالأعلى) إلى **الأحدث**:", "drag_items": display_items, "correct_order": json.dumps(correct_ids)}
def generate_image_character(anime_list, mode='normal'):
    """
    تولد سؤال صورة (شخصية أو بوستر العمل كـ fallback)
    """
    try:
        target = random.choice(anime_list)
        others = [a for a in anime_list if a['mal_id'] != target['mal_id']]
        if len(others) < 3: return None

        correct_answer = target.get('title_english') or target['title']
        wrong_options = [a.get('title_english') or a['title'] for a in random.sample(others, 3)]
        options = wrong_options + [correct_answer]
        random.shuffle(options)

        char_image = None
        q_text = "من أي أنمي هذه الشخصية؟"

        # نجلب الشخصيات أولاً
        chars = get_data_from_api(f"anime/{target['mal_id']}/characters")
        if chars:
            main_chars = [c for c in chars if c['role'] == 'Main']
            if main_chars:
                selected_char = random.choice(main_chars)
                char_image = selected_char['character']['images']['jpg']['image_url']

        # Fallback إلى بوستر الأنمي نفسه في حال عدم وجود صورة شخصية
        if not char_image:
            char_image = target.get('images', {}).get('jpg', {}).get('image_url')
            q_text = "خمن الأنمي من صورة البوستر الرسمية!"

        if not char_image: return None

        if mode == 'silhouette':
            q_text = "خمن الأنمي من خلال ظل الصورة!"

        return {
            "mode": "image", 
            "sub_mode": mode,
            "id": f"img_{mode}_{random.randint(1000,9999)}", 
            "question": q_text, 
            "image": char_image,
            "answer": correct_answer, 
            "options": options,
            "points": 200 if mode == 'normal' else 300
        }
    except Exception as e:
        print(f"Image Gen Error: {e}")
        return None
def generate_sort_score(anime_list):
    candidates = [a for a in anime_list if a.get('score')]
    if len(candidates) < 4: return None
    selected = random.sample(candidates, 4)
    sorted_items = sorted(selected, key=lambda x: x['score'], reverse=True) 
    correct_ids = [item['mal_id'] for item in sorted_items]
    shuffled = selected[:]
    random.shuffle(shuffled)
    display_items = [{"id": i['mal_id'], "text": i.get('title_english') or i['title']} for i in shuffled]
    return {"mode": "sorting", "id": f"sort_score_{random.randint(1000,9999)}", "question": "رتب الأنميات حسب **التقييم العالمي** من الأعلى (بالأعلى) للأقل:", "drag_items": display_items, "correct_order": json.dumps(correct_ids)}

def generate_imposter_question(anime_list):
    try:
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
    except: return None

def generate_common_link(anime_list):
    try:
        target = random.choice(anime_list)
        chars = get_data_from_api(f"anime/{target['mal_id']}/characters")
        if not chars or len(chars) < 3: return None
        names = [c['character']['name'] for c in random.sample(chars, 3)]
        names_str = " - ".join(names)
        title = target.get('title_english') or target['title']
        others = [a.get('title_english') or a['title'] for a in anime_list if a['mal_id'] != target['mal_id']]
        if len(others) < 3: return None
        return {"mode": "text", "id": f"med_link_{random.randint(1000,9999)}", "question": f"ما الأنمي الذي يجمع هذه الشخصيات؟<br><h3 style='color:#3498db'>{names_str}</h3>", "answer": title, "options": random.sample(others, 3) + [title]}
    except: return None

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

def generate_classic_studio(anime_list):
    cands = [a for a in anime_list if a.get('studios')]
    if not cands: return None
    target = random.choice(cands)
    studio = target['studios'][0]['name']
    title = target.get('title_english') or target['title']
    wrong = random.sample([s for s in COMMON_STUDIOS if s != studio], 3)
    return {"mode": "text", "id": f"easy_std_{random.randint(1000,9999)}", "question": f"ما هو استوديو إنتاج **{title}**؟", "answer": studio, "options": wrong + [studio]}

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

def generate_smart_character(anime_list, difficulty_mode='medium'):
    try:
        target = random.choice(anime_list)
        chars = get_data_from_api(f"anime/{target['mal_id']}/characters")
        if not chars: return None
        main_chars = [c for c in chars if c['role'] == 'Main']
        support_chars = [c for c in chars if c['role'] == 'Supporting']
        selected_char = None
        points = 100
        if difficulty_mode == 'easy' or (not support_chars and main_chars):
            if not main_chars: return None 
            selected_char = random.choice(main_chars)
            points = 150 
        elif difficulty_mode == 'medium':
            if not support_chars: return None
            top_support = support_chars[:5] 
            selected_char = random.choice(top_support)
            points = 300
        else: # hard/otaku
            if not support_chars: return None
            if len(support_chars) > 5: selected_char = random.choice(support_chars[5:]); points=500
            else: selected_char = random.choice(support_chars)
        char_name = selected_char['character']['name']
        title = target.get('title_english') or target['title']
        others = [a.get('title_english') or a['title'] for a in anime_list if a['mal_id'] != target['mal_id']]
        if len(others) < 3: return None
        return {"mode": "text", "id": f"char_{random.randint(1000,9999)}", "question": f"الشخصية **{char_name}** ({selected_char['role']}) تظهر في أي أنمي؟", "answer": title, "points": points, "options": random.sample(others, 3) + [title]}
    except: return None

# --- دوال التوليد (يجب أن تكون هنا بالأعلى) ---
# === دوال الصوت الجديدة ===
# ==========================================
#  دالة جلب الصوت من Deezer (البديل الموثوق)
# ==========================================
#  دوال الوسائط (الصوت والفيديو)
# ==========================================
def get_deezer_audio(anime_title):
    try:
        clean_title = anime_title.split(':')[0].split('(')[0].strip()
        url = "https://api.deezer.com/search"
        params = {"q": f'{clean_title} OST', "limit": 25}
        resp = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=3)
        if resp.status_code != 200: return None
        data = resp.json().get('data', [])
        if not data:
            params['q'] = clean_title
            resp = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=3)
            data = resp.json().get('data', [])

        if not data: return None
        banned_words = ['cover', 'remix', 'piano', 'metal', 'lofi', 'live', 'concert', 'version', 'english']
        valid_tracks = []
        for track in data:
            title = track.get('title', '').lower()
            artist = track.get('artist', {}).get('name', '').lower()
            album = track.get('album', {}).get('title', '').lower()
            if any(bad in title for bad in banned_words) or \
               any(bad in album for bad in banned_words) or \
               any(bad in artist for bad in banned_words):
                continue
            if not track.get('preview'): continue
            valid_tracks.append(track)
            
        if not valid_tracks: return None
        track = random.choice(valid_tracks)
        return {
            "link": track.get('preview'),
            "song_name": track.get('title'),
            "artist": track.get('artist', {}).get('name')
        }
    except Exception as e:
        print(f"Deezer Error: {e}")
        return None

def generate_video_question(anime_list, allowed_types=['OP', 'ED']):
    for _ in range(5):
        try:
            target = random.choice(anime_list)
            mal_id = target['mal_id']
            local_title = target.get('title_english') or target['title']
            
            themes = get_animethemes_media(mal_id, local_title)
            if not themes: continue
            
            valid_videos = []
            for theme in themes:
                t_type = theme.get('type')
                if allowed_types and t_type not in allowed_types:
                    continue
                entries = theme.get('animethemeentries', [])
                song_t = theme.get('song', {}).get('title', '') if theme.get('song') else ''
                for entry in entries:
                    for v in entry.get('videos', []):
                        v_link = v.get('link')
                        if v_link and (v_link.endswith('.mp4') or v_link.endswith('.webm')):
                            valid_videos.append((v_link, song_t))
            
            if not valid_videos: continue
            chosen_video, song_title = random.choice(valid_videos)
            others = [a for a in anime_list if a['mal_id'] != mal_id]
            if len(others) < 3: continue
            
            wrong_options = random.sample([a.get('title_english') or a['title'] for a in others], 3)
            final_options = wrong_options + [local_title]
            random.shuffle(final_options)
            
            return {
                "mode": "video",
                "id": f"vid_{random.randint(1000,9999)}",
                "question": "تأمل فيديو الشارة: من أي أنمي هذه الشارة؟",
                "video_url": chosen_video,
                "answer": local_title,
                "options": final_options,
                "points": 350
            }
        except Exception as e:
            print(f"Video Gen Error: {e}")
            continue
    return None

def generate_audio_question(anime_list, allowed_types=['OP', 'ED']):
    for _ in range(5): 
        try:
            target = random.choice(anime_list)
            mal_id = target['mal_id']
            local_title = target.get('title_english') or target['title']
            
            audio_url = None
            song_name = ""
            artist_name = ""
            
            # 1. التجربة من Animethemes أولاً
            themes = get_animethemes_media(mal_id, local_title)
            if themes:
                valid_audios = []
                for theme in themes:
                    t_type = theme.get('type')
                    if allowed_types and t_type not in allowed_types: continue
                    entries = theme.get('animethemeentries', [])
                    s_title = theme.get('song', {}).get('title', 'OP/ED') if theme.get('song') else 'OP/ED'
                    for entry in entries:
                        for v in entry.get('videos', []):
                            if v.get('link'):
                                valid_audios.append((v.get('link'), s_title))
                if valid_audios:
                    audio_url, song_name = random.choice(valid_audios)
                    artist_name = "Theme Song"

            # 2. التجربة من Deezer إذا لم يتوفر في Animethemes
            if not audio_url:
                aud = get_deezer_audio(local_title)
                if aud and aud.get('link'):
                    audio_url = aud['link']
                    song_name = aud.get('song_name', '')
                    artist_name = aud.get('artist', '')
            
            if audio_url:
                others = [a for a in anime_list if a['mal_id'] != mal_id]
                if len(others) < 3: continue
                
                wrong_options = random.sample([a.get('title_english') or a['title'] for a in others], 3)
                final_options = wrong_options + [local_title]
                random.shuffle(final_options)
                
                clean_url = f"{audio_url}?t={int(time.time())}" if '?' not in audio_url else audio_url
                return {
                    "mode": "audio",
                    "id": f"aud_{random.randint(1000,9999)}",
                    "question": "استمع للمقطع الصوتي: لمن تعود هذه الشارة/الأغنية؟",
                    "audio_url": clean_url,
                    "answer": local_title,
                    "options": final_options,
                    "points": 300
                }
        except Exception as e:
            print(f"Audio Gen Error: {e}")
            continue
    return None

def generate_true_false(anime_list):
    try:
        target = random.choice(anime_list)
        title = target.get('title_english') or target['title']
        is_truth = random.choice([True, False])
        if target.get('year'):
            year = target['year']
            if is_truth: q = f"أنمي **{title}** صدر عام {year}."; ans = "صح"
            else: fake = year + random.choice([-2, -1, 1, 2]); q = f"أنمي **{title}** صدر عام {fake}."; ans = "خطأ"
            return {"mode": "text", "id": f"easy_tf_{random.randint(1000,9999)}", "question": f"صح أم خطأ؟<br>{q}", "answer": ans, "options": ["صح", "خطأ"]}
        return None
    except: return None

# ==========================================
#  نظام الفلاتر الموحد
# ==========================================
GENERATORS_MAP = {
    'character': [
        generate_smart_character, 
        generate_common_link, 
        lambda lst: generate_image_character(lst, 'normal'), 
        lambda lst: generate_image_character(lst, 'silhouette')
    ],
    'studio': [generate_imposter_question, generate_reverse_studio, generate_classic_studio],
    'year': [generate_sort_year, generate_classic_year],
    'score': [generate_sort_score],
    'general': [generate_true_false],
    'image': [
        lambda lst: generate_image_character(lst, 'normal'),
        lambda lst: generate_image_character(lst, 'silhouette')
    ],
    'audio_op': [lambda lst: generate_audio_question(lst, ['OP'])],
    'audio_ed': [lambda lst: generate_audio_question(lst, ['ED'])],
    'video_op': [lambda lst: generate_video_question(lst, ['OP'])],
    'video_ed': [lambda lst: generate_video_question(lst, ['ED'])]
}

# 2. دالة مساعدة لدمج الفلاتر
def get_allowed_generators(selected_filters):
    # إذا القائمة فارغة أو None، نرجع كل شيء
    if not selected_filters:
        all_gens = []
        for gens in GENERATORS_MAP.values():
            all_gens.extend(gens)
        return list(set(all_gens))
    
    allowed = []
    for key in selected_filters:
        if key in GENERATORS_MAP:
            allowed.extend(GENERATORS_MAP[key])
            
    # إذا بحثنا ولم نجد دوال (احتياط)، نرجع الكل
    return allowed if allowed else get_allowed_generators(None)

# 3. الدالة الرئيسية لتوليد السؤال
def generate_any_question(anime_list, diff):
    try:
        # جلب الفلاتر من الجلسة (التي أرسلها game.html)
        selected_filters = session.get('filters', [])
        
        # اختيار الدوال المسموحة
        available_generators = get_allowed_generators(selected_filters)
        
        if not available_generators: return None

        # اختيار دالة واحدة عشوائية
        generator_func = random.choice(available_generators)
        

        # تنفيذ الدالة (مع مراعاة أن دالة الشخصيات تحتاج diff)
        if generator_func == generate_smart_character:
            return generator_func(anime_list, diff)
        
        return generator_func(anime_list)
    except Exception as e:
        print(f"Generator Error: {e}")
        return None

# مسار حفظ الفلاتر (مهم جداً أن يكون هنا لكي يراه game.html)
@app.route('/set_filters', methods=['POST'])
def set_filters():
    try:
        data = request.json
        filters = data.get('filters', [])
        session['filters'] = filters
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# ==========================================
#  5. المسارات (Routes)
# ==========================================

# مسار توليد صورة الكابتشا
@app.route('/captcha_image')
def captcha_image():
    image = ImageCaptcha(width=280, height=90)
    captcha_text = str(random.randint(1000, 9999))
    session['captcha'] = captcha_text 
    data = image.generate(captcha_text)
    return Response(data, mimetype='image/png')

@app.route('/')
def home():
    user = get_current_user()
    return render_template('home.html', user=user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        mal_user = request.form.get('mal_username')
        captcha_input = request.form['captcha']

        # 1. التحقق من الكابتشا
        if 'captcha' not in session or session['captcha'] != captcha_input:
            flash("❌ رمز التحقق غير صحيح!", "error")
            return render_template('register.html')

        # 2. تطابق الباسورد
        if password != confirm_password:
            flash("❌ كلمات المرور غير متطابقة!", "error")
            return render_template('register.html')

        # 3. إنشاء الحساب
        if create_user(username, email, password, mal_user):
            # إرسال الإيميل
            if send_activation_email(email):
                flash("✅ تم التسجيل! تفقد بريدك لتفعيل الحساب.", "success")
            else:
                flash("⚠️ تم التسجيل ولكن فشل إرسال الإيميل.", "warning")
            return redirect(url_for('login'))
        else:
            flash("❌ الاسم أو البريد مستخدم مسبقاً.", "error")

    return render_template('register.html')

@app.route('/confirm_email/<token>')
def confirm_email(token):
    try:
        email = serializer.loads(token, salt='email-confirm', max_age=3600)
        conn = get_db()
        conn.execute('UPDATE users SET is_verified = 1 WHERE email = ?', (email,))
        conn.commit()
        conn.close()
        flash("🎉 تم تفعيل الحساب بنجاح! سجل دخولك الآن.", "success")
    except:
        flash("❌ رابط التفعيل غير صالح أو منتهي.", "error")
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        pw = request.form['password']
        user = get_user_by_email(email)
        
        if user and check_password_hash(user['password'], pw):
            # التحقق من التفعيل
            if user['is_verified'] == 0:
                flash("⚠️ يجب تفعيل الحساب من الإيميل أولاً!", "warning")
                return render_template('login.html')

            session['user_id'] = user['id']
            session['username'] = user['username']
         
            return redirect(url_for('home'))
        else:
            flash("❌ بيانات الدخول خاطئة", "error")
    return render_template('login.html')
# ==========================================
#  7. إدارة الملف الشخصي
# ==========================================

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_current_user()
    return render_template('profile.html', user=user)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    new_username = request.form['username'].strip() # إضافة .strip()
    mal_username = request.form.get('mal_username', '').strip() # إضافة .strip()
    
    try:
        conn = get_db()
        # تحديث الاسم و MAL
        conn.execute('UPDATE users SET username = ?, mal_username = ? WHERE id = ?', 
                     (new_username, mal_username, session['user_id']))
        conn.commit()
        conn.close()
        
        # تحديث الجلسة (Session) بالبيانات الجديدة
        session['username'] = new_username
        # إذا تم تحديث MAL، يجب تحديث القائمة المحفوظة في الجلسة أيضاً
        if mal_username:
            session['mal_ids'] = fetch_mal_list(mal_username, ['completed'])
            
        flash("✅ تم تحديث بياناتك بنجاح!", "success")
    except Exception as e:
        flash("❌ حدث خطأ، ربما الاسم مستخدم بالفعل.", "error")
        print(e)
        
    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    current_pw = request.form['current_password']
    new_pw = request.form['new_password']
    confirm_pw = request.form['confirm_password']
    
    user = get_current_user()
    
    # 1. التأكد من كلمة المرور القديمة
    if not check_password_hash(user['password'], current_pw):
        flash("❌ كلمة المرور الحالية غير صحيحة!", "error")
        return redirect(url_for('profile'))
        
    # 2. التأكد من تطابق الجديدتين
    if new_pw != confirm_pw:
        flash("❌ كلمتا المرور الجديدتان غير متطابقتين!", "error")
        return redirect(url_for('profile'))
        
    # 3. الحفظ
    hashed_pw = generate_password_hash(new_pw)
    conn = get_db()
    conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_pw, session['user_id']))
    conn.commit()
    conn.close()
    
    flash("✅ تم تغيير كلمة المرور! يرجى تسجيل الدخول مجدداً.", "success")
    return redirect(url_for('logout'))
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))
# (تم التوحيد في الأعلى)

@app.route('/get_question/<difficulty>')
def get_question(difficulty):
    if session.get('hearts', 0) <= 0: return jsonify({"status": "gameover"})

    anime_list = get_anime_batch_smart(difficulty)
    
    if not anime_list:
        if session.get('mode') == 'mal':
            return jsonify({"status": "error", "message": "لم نجد أنميات كافية!"})
        return jsonify({"status": "error", "message": "قاعدة البيانات فارغة"})

    for _ in range(5):
        try:
            q_data = generate_any_question(anime_list, difficulty)
            if q_data:
                total_difficulty = calculate_total_difficulty(q_data, anime_list)
                q_data['points'] = q_data.get('points', total_difficulty * 50)
                if q_data.get('options') and "صح" not in q_data['options']:
                    random.shuffle(q_data['options'])
                return jsonify({"status": "success", "data": q_data})
        except: continue

    return jsonify({"status": "retry"})

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.json
    if data.get('correct'): session['score'] += data.get('points', 0)
    else: session['hearts'] -= 1
    session.modified = True
    if session['hearts'] <= 0: return jsonify({"status": "gameover"})
    return jsonify({"status": "continue"})

@app.route('/gameover')
def gameover():
    score = session.get('score', 0)
    title = "مبتدئ"
    if score > 1000: title = "هاوي"; 
    if score > 5000: title = "محترف"
    return render_template('gameover.html', score=score, title=title)

# ... (كود اللوبي) ...
active_rooms = {}

@socketio.on('connect')
def on_connect(): emit('update_room_list', get_public_rooms_list())

@socketio.on('create_room')
def on_create_room(data):
    room_id = str(random.randint(1000, 9999))
    active_rooms[room_id] = {'id': room_id, 'name': data['room_name'], 'password': data.get('password', ''), 'host': request.sid, 'players': [{'sid': request.sid, 'name': data['username'], 'score': 0}], 'state': 'waiting'}
    join_room(room_id)
    emit('room_created_success', {'roomId': room_id, 'isHost': True})
    socketio.emit('update_room_list', get_public_rooms_list())

@socketio.on('join_request')
def on_join_request(data):
    room = active_rooms.get(data['roomId'])
    if not room: emit('error_msg', 'غرفة غير موجودة'); return
    if room['state'] != 'waiting': emit('error_msg', 'بدأت اللعبة'); return
    if room['password'] and room['password'] != data.get('password', ''): emit('error_msg', 'كلمة السر خطأ'); return
    room['players'].append({'sid': request.sid, 'name': data['username'], 'score': 0})
    join_room(data['roomId'])
    emit('join_success', {'roomId': data['roomId'], 'isHost': False})
    socketio.to(data['roomId']).emit('update_players_in_room', room['players'])
    socketio.emit('update_room_list', get_public_rooms_list())

@socketio.on('get_room_details')
def get_room_details(data):
    room = active_rooms.get(data['roomId'])
    if room: emit('update_players_in_room', room['players'])

@socketio.on('disconnect')
def on_disconnect():
    to_delete = []
    for r_id, room in active_rooms.items():
        room['players'] = [p for p in room['players'] if p['sid'] != request.sid]
        if not room['players']: to_delete.append(r_id)
        else: socketio.to(r_id).emit('update_players_in_room', room['players'])
    for r_id in to_delete: del active_rooms[r_id]
    if to_delete: socketio.emit('update_room_list', get_public_rooms_list())

def get_public_rooms_list():
    return [{'id': r['id'], 'name': r['name'], 'count': len(r['players']), 'isPrivate': bool(r['password']), 'state': r['state']} for r in active_rooms.values()]
@app.route('/resend_activation', methods=['POST'])
def resend_activation():
    email = request.form['email']
    user = get_user_by_email(email)
    
    if not user:
        flash("❌ هذا البريد غير مسجل لدينا.", "error")
    elif user['is_verified'] == 1:
        flash("✅ هذا الحساب مفعل بالفعل! سجل دخولك.", "warning")
    else:
        if send_activation_email(email):
            flash("📩 تم إعادة إرسال رابط التفعيل، تفقد بريدك (والرسائل غير المرغوب فيها).", "success")
        else:
            flash("⚠️ حدث خطأ أثناء الإرسال، تأكد من صحة البريد أو حاول لاحقاً.", "error")
# ==========================================
#  6. نظام استعادة كلمة المرور
# ==========================================

def send_reset_email(to_email):
    """إرسال رابط تغيير الباسورد"""
    try:
        # التوكن صالح لمدة 15 دقيقة فقط
        token = serializer.dumps(to_email, salt='password-reset')
        link = url_for('reset_password_token', token=token, _external=True)
        
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email
        msg['Subject'] = "استعادة كلمة المرور - Otaku Challenge"
        
        body = f"""
        <div dir="rtl" style="text-align:right; font-family:sans-serif;">
            <h2>طلب تغيير كلمة المرور 🔒</h2>
            <p>لقد طلبت تغيير كلمة المرور الخاصة بحسابك. اضغط على الزر أدناه للتغيير:</p>
            <a href="{link}" style="background:#e74c3c; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold;">تغيير كلمة المرور</a>
            <p style="color:#777; font-size:0.9em; margin-top:20px;">الرابط صالح لمدة 15 دقيقة فقط.</p>
            <p>إذا لم تطلب هذا التغيير، تجاهل هذه الرسالة.</p>
        </div>
        """
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Reset Email Error: {e}")
        return False

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = get_user_by_email(email)
        if user:
            if send_reset_email(email):
                flash("📩 تم إرسال رابط الاستعادة إلى بريدك.", "success")
            else:
                flash("⚠️ حدث خطأ أثناء الإرسال.", "error")
        else:
            # رسالة غامضة للأمان (حتى لا يعرف المخترق إذا كان الإيميل مسجلاً أم لا)
            flash("📩 إذا كان هذا البريد مسجلاً، فستصلك رسالة.", "success")
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password_token(token):
    try:
        email = serializer.loads(token, salt='password-reset', max_age=900) # 900 ثانية = 15 دقيقة
    except:
        flash("❌ الرابط منتهي الصلاحية أو غير صحيح.", "error")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        pw = request.form['password']
        confirm_pw = request.form['confirm_password']
        
        if pw != confirm_pw:
            flash("❌ كلمات المرور غير متطابقة!", "error")
            return render_template('reset_password.html')
            
        hashed_pw = generate_password_hash(pw)
        conn = get_db()
        conn.execute('UPDATE users SET password = ? WHERE email = ?', (hashed_pw, email))
        conn.commit()
        conn.close()
        
        flash("✅ تم تغيير كلمة المرور بنجاح! سجل دخولك الآن.", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html')            
    
# ==========================================
#  8. نظام المزامنة (Client-Side Sync)
# ==========================================





# --- تعديل بسيط جداً في دالة play_ui ---
# ابحث عن دالة play_ui الموجودة عندك وعدل بداية شرط mal كالتالي:

@app.route('/play')
def play_ui():
    mode = request.args.get('mode', 'random')
    session['mode'] = mode
    
    if mode == 'mal':
        user = get_current_user()
        if not user or not user['mal_username']:
            flash("يجب ربط حساب MAL أولاً", "error")
            return redirect(url_for('profile'))
            
        # 1. استقبال الحالات من الرابط (التي أرسلها الجافاسكريبت)
        # الرابط يكون: /play?mode=mal&status=completed&status=watching
        selected_statuses = request.args.getlist('status')
        
        # إذا لم يختر شيئاً، نفترض المكتمل
        if not selected_statuses:
            selected_statuses = ['completed']

        # 2. الجلب المباشر باستخدام الدالة الجديدة
        ids = fetch_mal_list(user['mal_username'], selected_statuses)
        
        if ids:
            session['mal_ids'] = ids
            # حفظنا البيانات، الآن الصفحة ستعمل طبيعياً
        else:
            flash("لم نتمكن من جلب القائمة أو أنها فارغة، سنستخدم الأسئلة العشوائية.", "warning")
            session['mode'] = 'random'

    session['score'] = 0
    session['hearts'] = 3
    return render_template('game.html')
# ==========================================
#  🛠️ أداة إصلاح وتعبئة قاعدة البيانات (انسخ هذا الجزء)
# ==========================================
@app.route('/admin/fix_db')
def fix_db():
    try:
        conn = get_db()
        # 1. التأكد من وجود جدول الأنمي
        conn.execute('''CREATE TABLE IF NOT EXISTS anime 
                        (mal_id INTEGER PRIMARY KEY, 
                         title TEXT, 
                         popularity INTEGER, 
                         year INTEGER, 
                         score REAL, 
                         studios TEXT,
                         raw_json TEXT)''')
        
        # 2. جلب قائمة أنميات جديدة ومحدثة من النت
        added_count = 0
        # سنجلب أول 3 صفحات (حوالي 75 أنمي) لضمان وجود تنوع للأسئلة
        for page in range(1, 4): 
            data = get_data_from_api("top/anime", {"page": page, "filter": "bypopularity"})
            if data:
                for anime in data:
                    mal_id = anime['mal_id']
                    # تجاهل الأنميات التي ليس لها صورة أو بيانات ناقصة
                    if not anime.get('images', {}).get('jpg', {}).get('image_url'): continue

                    title = anime.get('title_english') or anime['title']
                    pop = anime.get('popularity')
                    year = anime.get('year')
                    score = anime.get('score')
                    studios_list = anime.get('studios', [])
                    
                    raw = json.dumps(anime)
                    studios_str = json.dumps(studios_list)

                    try:
                        conn.execute('''INSERT OR REPLACE INTO anime 
                                      (mal_id, title, popularity, year, score, studios, raw_json) 
                                      VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                                      (mal_id, title, pop, year, score, studios_str, raw))
                        added_count += 1
                    except: pass
            time.sleep(1) # استراحة قصيرة عشان الموقع ما يحظرنا

        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"✅ تم إصلاح القاعدة وإضافة {added_count} أنمي جديد! الآن اللعبة جاهزة."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
if __name__ == '__main__':
    # تأكد من أن debug=True لترت الأخطاء، والمنفذ 5000
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)