from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import send_from_directory
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import text, inspect
import os
import json
from api_keys.config import *

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Ensure upload directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'recordings'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'lessons'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'avatars'), exist_ok=True)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    display_name = db.Column(db.String(120))
    bio = db.Column(db.Text)
    location = db.Column(db.String(120))
    website = db.Column(db.String(255))
    avatar_url = db.Column(db.String(255))
    role = db.Column(db.String(20), default="user", nullable=False)  # user, teacher, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Recording(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    transcript = db.Column(db.Text)
    words_per_minute = db.Column(db.Float)
    duration_seconds = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('recordings', lazy=True))

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # Easy, Medium, Hard
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recording_id = db.Column(db.Integer, db.ForeignKey('recording.id'), nullable=True)
    words_per_minute = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('progress', lazy=True))

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recording_id = db.Column(db.Integer, db.ForeignKey('recording.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    feedback_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recording = db.relationship('Recording', backref=db.backref('reviews', lazy=True))
    reviewer = db.relationship('User', backref=db.backref('reviews_given', lazy=True))

class Vocabulary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    word = db.Column(db.String(100), nullable=False)
    phonetic = db.Column(db.String(200))
    definition = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('vocabulary', lazy=True))

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    daily_minutes = db.Column(db.Integer, nullable=False, default=15)
    current_streak = db.Column(db.Integer, default=0)
    last_activity_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('goals', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Speech-to-Text using Google API (simplified for free tier)
def transcribe_audio(file_path):
    """Transcribe audio file using Google Speech API"""
    try:
        import speech_recognition as sr
        from pydub import AudioSegment
        import os
        import tempfile
        
        # Convert audio to WAV if needed
        audio = AudioSegment.from_file(file_path)
        
        # Export to WAV format for speech recognition
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            audio.export(tmp_file.name, format="wav")
            temp_wav_path = tmp_file.name
        
        try:
            r = sr.Recognizer()
            with sr.AudioFile(temp_wav_path) as source:
                # Adjust for ambient noise
                r.adjust_for_ambient_noise(source)
                audio_data = r.record(source)
            
            # Using Google Web Speech API (free, no key needed)
            try:
                transcript = r.recognize_google(audio_data)
                os.unlink(temp_wav_path)  # Clean up temp file
                return transcript, None
            except sr.UnknownValueError:
                os.unlink(temp_wav_path)
                return None, "Could not understand audio. Please speak more clearly."
            except sr.RequestError as e:
                os.unlink(temp_wav_path)
                return None, f"Error with speech recognition service: {e}"
        except Exception as e:
            if os.path.exists(temp_wav_path):
                os.unlink(temp_wav_path)
            return None, f"Error processing audio: {str(e)}"
    except Exception as e:
        return None, f"Error: {str(e)}"

def calculate_wpm(transcript, duration_seconds):
    """Calculate words per minute"""
    if not transcript or duration_seconds == 0:
        return 0
    word_count = len(transcript.split())
    wpm = (word_count / duration_seconds) * 60
    return round(wpm, 2)

def ensure_schema_upgrades():
    """
    Lightweight schema upgrade helper for SQLite.

    Flask-SQLAlchemy's db.create_all() will NOT alter existing tables.
    If the database already exists, we add missing columns here.
    """
    try:
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        if "user" in tables:
            cols = {c["name"] for c in inspector.get_columns("user")}
            alter_statements = []
            if "is_admin" not in cols:
                alter_statements.append(
                    "ALTER TABLE user ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
                )
            if "display_name" not in cols:
                alter_statements.append(
                    "ALTER TABLE user ADD COLUMN display_name VARCHAR(120)"
                )
            if "bio" not in cols:
                alter_statements.append(
                    "ALTER TABLE user ADD COLUMN bio TEXT"
                )
            if "location" not in cols:
                alter_statements.append(
                    "ALTER TABLE user ADD COLUMN location VARCHAR(120)"
                )
            if "website" not in cols:
                alter_statements.append(
                    "ALTER TABLE user ADD COLUMN website VARCHAR(255)"
                )
            if "avatar_url" not in cols:
                alter_statements.append(
                    "ALTER TABLE user ADD COLUMN avatar_url VARCHAR(255)"
                )
            if "role" not in cols:
                alter_statements.append(
                    "ALTER TABLE user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"
                )

            if alter_statements:
                with db.engine.begin() as conn:
                    for stmt in alter_statements:
                        conn.execute(text(stmt))
                print("Database upgraded: user table columns synchronized")
    except Exception as e:
        # Don't crash the app if inspection fails; print a helpful message.
        print(f"Warning: schema upgrade check failed: {e}")

def init_database():
    """Initialize database and create sample data"""
    db.create_all()
    ensure_schema_upgrades()
    
    # Create admin user if it doesn't exist
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@lexistream.com',
            password_hash=generate_password_hash('admin123'),
            is_admin=True,
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created!")
    
    # Create sample lessons
    if Lesson.query.count() == 0:
        sample_lessons = [
            # Easy Lessons
            Lesson(title="The Cat and the Hat", content="The cat sat on the mat. The hat was red. The cat wore the hat.", difficulty="Easy"),
            Lesson(title="A Day at the Park", content="Today is a sunny day. We go to the park. We play on the swings. We have fun together.", difficulty="Easy"),
            Lesson(title="My Pet Dog", content="I have a dog. His name is Max. Max likes to play. We run in the yard. Max is happy.", difficulty="Easy"),
            Lesson(title="The Red Ball", content="I see a red ball. The ball is big. I can throw the ball. The ball bounces high. I catch the ball.", difficulty="Easy"),
            Lesson(title="In the Garden", content="The garden has flowers. Flowers are pretty. Bees like flowers. I water the flowers. The garden smells nice.", difficulty="Easy"),
            Lesson(title="Breakfast Time", content="I eat breakfast. I have eggs and toast. The eggs are hot. I drink orange juice. Breakfast is good.", difficulty="Easy"),
            Lesson(title="Going to School", content="I go to school. School is fun. I learn new things. I see my friends. School makes me smart.", difficulty="Easy"),
            Lesson(title="The Rainbow", content="After rain comes a rainbow. The rainbow has many colors. Red, orange, yellow, green, blue. The rainbow is beautiful.", difficulty="Easy"),
            Lesson(title="My Family", content="I love my family. Mom and Dad are kind. My sister is nice. We eat dinner together. Family is important.", difficulty="Easy"),
            Lesson(title="Playing Outside", content="I play outside. The sun is bright. I ride my bike. I jump and run. Playing is fun.", difficulty="Easy"),
            
            # Medium Lessons
            Lesson(title="The Library Adventure", content="Sarah visited the local library every Saturday morning. She loved exploring the shelves filled with books from different genres. Her favorite section was the mystery novels, where she could spend hours reading about detectives solving complex cases.", difficulty="Medium"),
            Lesson(title="A Rainy Day Story", content="When the rain started pouring, Emma decided to stay indoors and bake cookies with her grandmother. They mixed flour, sugar, and chocolate chips together. The warm cookies filled the house with a delicious aroma that made everyone smile.", difficulty="Medium"),
            Lesson(title="The School Project", content="Marcus worked diligently on his science project about the solar system. He created colorful models of planets using paper and paint. His teacher was impressed by his creativity and attention to detail.", difficulty="Medium"),
            Lesson(title="Weekend Adventure", content="Last weekend, my friends and I decided to explore the hiking trail near our town. We packed sandwiches, water bottles, and a camera. The trail was challenging but the view from the top was absolutely breathtaking.", difficulty="Medium"),
            Lesson(title="Learning to Cook", content="Cooking has become one of my favorite hobbies. I started by following simple recipes from cookbooks. Now I can prepare delicious meals for my family. The kitchen has become my creative space.", difficulty="Medium"),
            Lesson(title="The Art Museum", content="During our field trip to the art museum, we saw paintings from different time periods. Each artwork told a unique story. Our guide explained the techniques artists used to create these masterpieces.", difficulty="Medium"),
            Lesson(title="Volunteer Work", content="Every month, I volunteer at the local animal shelter. I help feed the animals and clean their cages. The experience has taught me responsibility and compassion for living creatures.", difficulty="Medium"),
            Lesson(title="The Science Fair", content="Students from different schools gathered to showcase their science experiments. There were projects about plants, electricity, and even space. The fair encouraged young minds to explore and discover.", difficulty="Medium"),
            Lesson(title="A Day at the Beach", content="The beach was crowded with families enjoying the sunny weather. Children built sandcastles while adults relaxed under colorful umbrellas. The sound of waves created a peaceful atmosphere.", difficulty="Medium"),
            Lesson(title="The Book Club", content="Our book club meets every Tuesday evening to discuss the latest novel we've read. We share our thoughts and opinions about the characters and plot. These discussions help us understand different perspectives.", difficulty="Medium"),
            
            # Hard Lessons
            Lesson(title="The Scientific Method", content="The scientific method is a systematic approach to understanding natural phenomena. Researchers begin by observing a problem, formulating a hypothesis, conducting experiments, analyzing results, and drawing conclusions. This rigorous process ensures that scientific knowledge is reliable and reproducible.", difficulty="Hard"),
            Lesson(title="Climate Change Impact", content="Climate change represents one of the most pressing challenges of our time. Rising global temperatures, caused primarily by greenhouse gas emissions, lead to melting ice caps, rising sea levels, and extreme weather patterns. Addressing this issue requires international cooperation and sustainable practices.", difficulty="Hard"),
            Lesson(title="Artificial Intelligence Revolution", content="Artificial intelligence has transformed numerous industries, from healthcare to transportation. Machine learning algorithms can process vast amounts of data, identify patterns, and make predictions with remarkable accuracy. However, this technological advancement raises important ethical questions about privacy, employment, and decision-making autonomy.", difficulty="Hard"),
            Lesson(title="Economic Globalization", content="Economic globalization has created interconnected markets where goods, services, and capital flow across borders with unprecedented ease. While this integration has lifted millions out of poverty and fostered innovation, it has also created economic disparities and cultural homogenization that challenge traditional values and local economies.", difficulty="Hard"),
            Lesson(title="Renewable Energy Transition", content="The transition to renewable energy sources represents a fundamental shift in how humanity generates power. Solar and wind technologies have become increasingly cost-effective, challenging the dominance of fossil fuels. This transformation requires substantial infrastructure investment, policy support, and public acceptance to achieve sustainable energy independence.", difficulty="Hard"),
            Lesson(title="The Digital Age", content="The digital age has revolutionized communication, education, and commerce. Social media platforms connect billions of people worldwide, while e-commerce has transformed retail. However, this digital transformation also presents challenges including cybersecurity threats, information overload, and the digital divide between those with and without access to technology.", difficulty="Hard"),
            Lesson(title="Biodiversity Conservation", content="Biodiversity conservation is essential for maintaining ecosystem stability and human survival. Habitat destruction, pollution, and climate change threaten countless species. Conservation efforts require coordinated action between governments, organizations, and communities to protect endangered species and preserve natural habitats for future generations.", difficulty="Hard"),
            Lesson(title="Space Exploration", content="Space exploration has expanded humanity's understanding of the universe and our place within it. Missions to Mars, asteroid mining, and the search for exoplanets represent ambitious endeavors that push technological boundaries. These ventures inspire scientific curiosity while raising questions about resource allocation and international cooperation.", difficulty="Hard"),
            Lesson(title="Quantum Computing", content="Quantum computing harnesses the principles of quantum mechanics to process information in fundamentally different ways than classical computers. Quantum bits, or qubits, can exist in multiple states simultaneously, potentially solving complex problems exponentially faster. This emerging technology promises breakthroughs in cryptography, drug discovery, and optimization problems.", difficulty="Hard"),
            Lesson(title="Social Media Influence", content="Social media platforms have become powerful tools for information dissemination and social connection. They enable rapid communication and community building across geographical boundaries. However, these platforms also facilitate the spread of misinformation, create echo chambers, and raise concerns about mental health and privacy in the digital age.", difficulty="Hard"),
        ]
        for lesson in sample_lessons:
            db.session.add(lesson)
        db.session.commit()
        print("Sample lessons created!")

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        # Validation
        errors = []
        
        # Username validation: 7-15 characters
        if len(username) < 7:
            errors.append('Username must be at least 7 characters long')
        elif len(username) > 15:
            errors.append('Username must be no more than 15 characters long')
        
        # Email validation: minimum 8 characters (e.g., a@b.co = 6, so 8 is reasonable)
        if len(email) < 8:
            errors.append('Email must be at least 8 characters long')
        elif '@' not in email or '.' not in email:
            errors.append('Please enter a valid email address')
        
        # Password validation: minimum 7 characters
        if len(password) < 7:
            errors.append('Password must be at least 7 characters long')
        
        if errors:
            for error in errors:
                flash(error)
            return redirect(url_for('register'))
        
        # Check if username exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        # Check if email exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        # Create default goal
        goal = Goal(user_id=user.id, daily_minutes=15)
        db.session.add(goal)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin or getattr(current_user, "role", "user") == "admin":
        return redirect(url_for('admin_dashboard'))
    if getattr(current_user, "role", "user") == "teacher":
        return redirect(url_for('teacher_dashboard'))
    
    # Get recent progress data
    progress_data = Progress.query.filter_by(user_id=current_user.id)\
        .order_by(Progress.date.desc()).limit(30).all()
    
    # Get goal info
    goal = Goal.query.filter_by(user_id=current_user.id).first()
    if not goal:
        goal = Goal(user_id=current_user.id, daily_minutes=15)
        db.session.add(goal)
        db.session.commit()
    
    # Calculate today's minutes
    today = datetime.utcnow().date()
    today_recordings = Recording.query.filter_by(user_id=current_user.id)\
        .filter(db.func.date(Recording.created_at) == today).all()
    today_minutes = sum(r.duration_seconds for r in today_recordings) / 60
    
    return render_template('dashboard.html', 
                         progress_data=progress_data,
                         goal=goal,
                         today_minutes=round(today_minutes, 2))

@app.route('/record', methods=['GET', 'POST'])
@login_required
def record():
    if request.method == 'POST':
        if 'audio' not in request.files:
            flash('No audio file provided')
            return redirect(url_for('record'))
        
        file = request.files['audio']
        if file.filename == '':
            flash('No file selected')
            return redirect(url_for('record'))
        
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'recordings', filename)
            file.save(filepath)
            
            # Get duration (simplified)
            duration = request.form.get('duration', 0, type=float)
            
            # Transcribe
            transcript, error = transcribe_audio(filepath)
            
            if error:
                flash(f'Transcription error: {error}')
                transcript = "Transcription failed"
            
            # Calculate WPM
            wpm = calculate_wpm(transcript, duration) if transcript else 0
            
            # Save recording
            recording = Recording(
                user_id=current_user.id,
                filename=filename,
                transcript=transcript or "",
                words_per_minute=wpm,
                duration_seconds=duration
            )
            db.session.add(recording)
            
            # Save progress
            progress = Progress(
                user_id=current_user.id,
                recording_id=recording.id,
                words_per_minute=wpm
            )
            db.session.add(progress)
            
            # Update goal streak
            goal = Goal.query.filter_by(user_id=current_user.id).first()
            if goal:
                today = datetime.utcnow().date()
                if goal.last_activity_date:
                    yesterday = today - timedelta(days=1)
                    if goal.last_activity_date == yesterday:
                        goal.current_streak += 1
                    elif goal.last_activity_date < yesterday:
                        goal.current_streak = 1
                    elif goal.last_activity_date != today:
                        goal.current_streak = 1
                else:
                    goal.current_streak = 1
                goal.last_activity_date = today
            
            db.session.commit()
            
            flash('Recording saved successfully!')
            return redirect(url_for('recordings'))
    
    return render_template('record.html')

@app.route('/recordings')
@login_required
def recordings():
    recordings_list = Recording.query.filter_by(user_id=current_user.id)\
        .order_by(Recording.created_at.desc()).all()
    return render_template('recordings.html', recordings=recordings_list)

@app.route('/lessons')
@login_required
def lessons():
    difficulty = request.args.get('difficulty', 'all')
    query = Lesson.query
    if difficulty != 'all':
        query = query.filter_by(difficulty=difficulty)
    lessons_list = query.order_by(Lesson.difficulty, Lesson.title).all()
    return render_template('lessons.html', lessons=lessons_list, current_difficulty=difficulty)

@app.route('/progress')
@login_required
def progress():
    progress_data = Progress.query.filter_by(user_id=current_user.id)\
        .order_by(Progress.date.asc()).all()
    
    chart_data = {
        'dates': [p.date.strftime('%Y-%m-%d') for p in progress_data],
        'wpm': [p.words_per_minute for p in progress_data]
    }
    
    return render_template('progress.html', chart_data=chart_data)

@app.route('/reviews')
@login_required
def reviews():
    # Get all public recordings (for now, all recordings)
    all_recordings = Recording.query.order_by(Recording.created_at.desc()).limit(50).all()
    my_reviews = Review.query.filter_by(reviewer_id=current_user.id).all()
    return render_template('reviews.html', recordings=all_recordings, my_reviews=my_reviews)

@app.route('/review/<int:recording_id>', methods=['GET', 'POST'])
@login_required
def review_recording(recording_id):
    recording = Recording.query.get_or_404(recording_id)
    
    if request.method == 'POST':
        feedback = request.form.get('feedback')
        if feedback:
            review = Review(
                recording_id=recording_id,
                reviewer_id=current_user.id,
                feedback_text=feedback
            )
            db.session.add(review)
            db.session.commit()
            flash('Review submitted successfully!')
            return redirect(url_for('reviews'))
    
    existing_reviews = Review.query.filter_by(recording_id=recording_id).all()
    return render_template('review_detail.html', recording=recording, reviews=existing_reviews)

@app.route('/vocabulary')
@login_required
def vocabulary():
    words = Vocabulary.query.filter_by(user_id=current_user.id)\
        .order_by(Vocabulary.created_at.desc()).all()
    return render_template('vocabulary.html', words=words)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files (avatars, recordings if needed)."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/vocabulary/add', methods=['POST'])
@login_required
def add_vocabulary():
    word = request.form.get('word')
    phonetic = request.form.get('phonetic', '')
    definition = request.form.get('definition', '')
    notes = request.form.get('notes', '')
    
    if word:
        vocab = Vocabulary(
            user_id=current_user.id,
            word=word,
            phonetic=phonetic,
            definition=definition,
            notes=notes
        )
        db.session.add(vocab)
        db.session.commit()
        flash('Word added to vocabulary bank!')
    
    return redirect(url_for('vocabulary'))

@app.route('/vocabulary/delete/<int:vocab_id>')
@login_required
def delete_vocabulary(vocab_id):
    vocab = Vocabulary.query.get_or_404(vocab_id)
    if vocab.user_id == current_user.id:
        db.session.delete(vocab)
        db.session.commit()
        flash('Word removed from vocabulary bank')
    return redirect(url_for('vocabulary'))

@app.route('/goals', methods=['GET', 'POST'])
@login_required
def goals():
    goal = Goal.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        daily_minutes = request.form.get('daily_minutes', type=int)
        if daily_minutes and daily_minutes > 0:
            if goal:
                goal.daily_minutes = daily_minutes
            else:
                goal = Goal(user_id=current_user.id, daily_minutes=daily_minutes)
                db.session.add(goal)
            db.session.commit()
            flash('Goal updated successfully!')
            return redirect(url_for('goals'))
    
    if not goal:
        goal = Goal(user_id=current_user.id, daily_minutes=15)
        db.session.add(goal)
        db.session.commit()
    
    # Calculate today's progress
    today = datetime.utcnow().date()
    today_recordings = Recording.query.filter_by(user_id=current_user.id)\
        .filter(db.func.date(Recording.created_at) == today).all()
    today_minutes = sum(r.duration_seconds for r in today_recordings) / 60
    
    return render_template('goals.html', goal=goal, today_minutes=round(today_minutes, 2))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        bio = request.form.get('bio', '').strip()
        location = request.form.get('location', '').strip()
        website = request.form.get('website', '').strip()
        avatar_url = request.form.get('avatar_url', '').strip()
        avatar_file = request.files.get('avatar_file')

        # Simple validation
        if len(display_name) > 120:
            flash('Display name is too long (max 120 characters).')
            return redirect(url_for('edit_profile'))
        if len(location) > 120:
            flash('Location is too long (max 120 characters).')
            return redirect(url_for('edit_profile'))
        if len(website) > 255:
            flash('Website URL is too long (max 255 characters).')
            return redirect(url_for('edit_profile'))
        if len(avatar_url) > 255:
            flash('Avatar URL is too long (max 255 characters).')
            return redirect(url_for('edit_profile'))

        # Handle avatar file upload if provided
        if avatar_file and avatar_file.filename:
            _, ext = os.path.splitext(avatar_file.filename)
            ext = ext.lower()
            if ext not in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
                flash('Unsupported avatar image type. Please upload PNG, JPG, or GIF.')
                return redirect(url_for('edit_profile'))
            avatars_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars')
            os.makedirs(avatars_folder, exist_ok=True)
            filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}{ext}"
            filepath = os.path.join(avatars_folder, filename)
            avatar_file.save(filepath)
            # Public URL for avatar
            avatar_url = url_for('uploaded_file', filename=f"avatars/{filename}")

        current_user.display_name = display_name or None
        current_user.bio = bio or None
        current_user.location = location or None
        current_user.website = website or None
        current_user.avatar_url = avatar_url or None

        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('profile'))

    return render_template('profile_edit.html', user=current_user)

# Admin Routes
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        role = getattr(current_user, "role", "user")
        if not current_user.is_authenticated or role != "teacher":
            flash('Teacher access required')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def teacher_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        role = getattr(current_user, "role", "user")
        if not current_user.is_authenticated or (not current_user.is_admin and role not in ("admin", "teacher")):
            flash('Teacher or admin access required')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_recordings = Recording.query.count()
    total_lessons = Lesson.query.count()
    total_reviews = Review.query.count()
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_recordings = Recording.query.order_by(Recording.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_recordings=total_recordings,
                         total_lessons=total_lessons,
                         total_reviews=total_reviews,
                         recent_users=recent_users,
                         recent_recordings=recent_recordings)

@app.route('/admin/lessons')
@login_required
@teacher_or_admin_required
def admin_lessons():
    lessons = Lesson.query.order_by(Lesson.difficulty, Lesson.title).all()
    return render_template('admin/lessons.html', lessons=lessons)

@app.route('/admin/lessons/add', methods=['GET', 'POST'])
@login_required
@teacher_or_admin_required
def admin_add_lesson():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        difficulty = request.form.get('difficulty')
        
        if title and content and difficulty:
            lesson = Lesson(title=title, content=content, difficulty=difficulty)
            db.session.add(lesson)
            db.session.commit()
            flash('Lesson added successfully!')
            return redirect(url_for('admin_lessons'))
    
    return render_template('admin/add_lesson.html')

@app.route('/admin/lessons/edit/<int:lesson_id>', methods=['GET', 'POST'])
@login_required
@teacher_or_admin_required
def admin_edit_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    if request.method == 'POST':
        lesson.title = request.form.get('title')
        lesson.content = request.form.get('content')
        lesson.difficulty = request.form.get('difficulty')
        db.session.commit()
        flash('Lesson updated successfully!')
        return redirect(url_for('admin_lessons'))
    
    return render_template('admin/edit_lesson.html', lesson=lesson)

@app.route('/admin/lessons/delete/<int:lesson_id>')
@login_required
@teacher_or_admin_required
def admin_delete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    db.session.delete(lesson)
    db.session.commit()
    flash('Lesson deleted successfully!')
    return redirect(url_for('admin_lessons'))

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'user')
        
        # Validation
        errors = []
        
        if len(username) < 7:
            errors.append('Username must be at least 7 characters long')
        elif len(username) > 15:
            errors.append('Username must be no more than 15 characters long')
        
        if len(email) < 8:
            errors.append('Email must be at least 8 characters long')
        elif '@' not in email or '.' not in email:
            errors.append('Please enter a valid email address')
        
        # Check if username is taken by another user
        existing_user = User.query.filter_by(username=username).first()
        if existing_user and existing_user.id != user_id:
            errors.append('Username already taken')
        
        # Check if email is taken by another user
        existing_email = User.query.filter_by(email=email).first()
        if existing_email and existing_email.id != user_id:
            errors.append('Email already taken')
        
        if errors:
            for error in errors:
                flash(error)
            return redirect(url_for('admin_edit_user', user_id=user_id))
        
        user.username = username
        user.email = email
        # Normalize role
        if role not in ("admin", "teacher", "user"):
            role = "user"
        user.role = role
        user.is_admin = (role == "admin")
        
        db.session.commit()
        flash('User updated successfully!')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/users/delete/<int:user_id>')
@login_required
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot delete admin user')
        return redirect(url_for('admin_users'))
    
    # Delete user's data
    Recording.query.filter_by(user_id=user_id).delete()
    Progress.query.filter_by(user_id=user_id).delete()
    Vocabulary.query.filter_by(user_id=user_id).delete()
    Goal.query.filter_by(user_id=user_id).delete()
    Review.query.filter_by(reviewer_id=user_id).delete()
    
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully!')
    return redirect(url_for('admin_users'))

@app.route('/admin/recordings')
@login_required
@admin_required
def admin_recordings():
    recordings = Recording.query.order_by(Recording.created_at.desc()).all()
    return render_template('admin/recordings.html', recordings=recordings)

@app.route('/admin/recordings/delete/<int:recording_id>')
@login_required
@admin_required
def admin_delete_recording(recording_id):
    recording = Recording.query.get_or_404(recording_id)
    
    # Delete file if exists
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'recordings', recording.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    
    # Delete reviews
    Review.query.filter_by(recording_id=recording_id).delete()
    Progress.query.filter_by(recording_id=recording_id).delete()
    
    db.session.delete(recording)
    db.session.commit()
    flash('Recording deleted successfully!')
    return redirect(url_for('admin_recordings'))

@app.route('/teacher/dashboard')
@login_required
@teacher_required
def teacher_dashboard():
    total_lessons = Lesson.query.count()
    total_users = User.query.count()
    my_reviews = Review.query.filter_by(reviewer_id=current_user.id).count()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()

    return render_template('teacher_dashboard.html',
                           total_lessons=total_lessons,
                           total_users=total_users,
                           my_reviews=my_reviews,
                           recent_users=recent_users)

if __name__ == '__main__':
    with app.app_context():
        init_database()
        print("Database initialized successfully!")
    
    print("\n" + "="*50)
    print("LexiStream is starting...")
    print("="*50)
    print("Open your browser and go to: http://localhost:5000")
    print("="*50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
