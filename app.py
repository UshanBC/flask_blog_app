# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid
import pymysql

# Register PyMySQL as MySQL driver
pymysql.install_as_MySQLdb()

#import secrets
#print(secrets.token_hex(32))
app = Flask(__name__)
app.config['SECRET_KEY'] = 'c0cf0c83cac7ab627d6346ec7c7bbf21493474ff34e8e0c0e22611c64644114e'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:12345@localhost/blog_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_superuser = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign key to User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')
    
    @property
    def like_count(self):
        return len([like for like in self.likes if like.is_like])
        
    @property
    def dislike_count(self):
        return len([like for like in self.likes if not like.is_like])

# Comment model
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

# Like model
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_like = db.Column(db.Boolean, default=True)  # True for like, False for dislike
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    
    # Ensure a user can only like/dislike a post once
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post'),)

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file):
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = str(uuid.uuid4()) + '_' + filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        return unique_filename
    return None

# Routes
@app.route('/')
def index():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return render_template('register.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form['login_id']
        password = request.form['password']
        
        # Check if login_id is username or email
        user = User.query.filter((User.username == login_id) | (User.email == login_id)).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_superuser'] = user.is_superuser
            flash('Login successful!')
            return redirect(url_for('index'))
        else:
            flash('Invalid username/email or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('index'))

@app.route('/add_post', methods=['GET', 'POST'])
def add_post():
    if 'user_id' not in session:
        flash('Please login to add a post.')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        # Handle image upload
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                image_filename = save_image(file)
        
        post = Post(
            title=title,
            content=content,
            image_filename=image_filename,
            user_id=session['user_id']
        )
        
        db.session.add(post)
        db.session.commit()
        
        flash('Post added successfully!')
        return redirect(url_for('index'))
    
    return render_template('add_post.html')

@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        flash('Please login to edit posts.')
        return redirect(url_for('login'))
    
    post = Post.query.get_or_404(post_id)
    
    # Check if user can edit this post
    if not session.get('is_superuser') and post.user_id != session['user_id']:
        flash('You can only edit your own posts.')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        post.updated_at = datetime.utcnow()
        
        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                # Delete old image if exists
                if post.image_filename:
                    old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image_filename)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                post.image_filename = save_image(file)
        
        db.session.commit()
        flash('Post updated successfully!')
        return redirect(url_for('view_post', post_id=post.id))
    
    return render_template('edit_post.html', post=post)

@app.route('/delete_post/<int:post_id>')
def delete_post(post_id):
    if 'user_id' not in session:
        flash('Please login to delete posts.')
        return redirect(url_for('login'))
    
    post = Post.query.get_or_404(post_id)
    
    # Check if user can delete this post
    if not session.get('is_superuser') and post.user_id != session['user_id']:
        flash('You can only delete your own posts.')
        return redirect(url_for('index'))
    
    # Delete associated image
    if post.image_filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)
    
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully!')
    return redirect(url_for('index'))

@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.desc()).all()
    
    # Check if user has liked/disliked the post
    user_like = None
    if 'user_id' in session:
        user_like = Like.query.filter_by(user_id=session['user_id'], post_id=post_id).first()
    
    return render_template('view_post.html', post=post, comments=comments, user_like=user_like)

@app.route('/my_posts')
def my_posts():
    if 'user_id' not in session:
        flash('Please login to view your posts.')
        return redirect(url_for('login'))
    
    posts = Post.query.filter_by(user_id=session['user_id']).order_by(Post.created_at.desc()).all()
    return render_template('my_posts.html', posts=posts)

@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        flash('Please login to add a comment.')
        return redirect(url_for('login'))
    
    content = request.form.get('content')
    if not content:
        flash('Comment cannot be empty.')
        return redirect(url_for('view_post', post_id=post_id))
    
    comment = Comment(
        content=content,
        user_id=session['user_id'],
        post_id=post_id
    )
    
    db.session.add(comment)
    db.session.commit()
    flash('Comment added successfully!')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/comment/<int:comment_id>/edit', methods=['GET', 'POST'])
def edit_comment(comment_id):
    if 'user_id' not in session:
        flash('Please login to edit comments.')
        return redirect(url_for('login'))
    
    comment = Comment.query.get_or_404(comment_id)
    post = Post.query.get_or_404(comment.post_id)
    
    # Check if user can edit this comment (comment author, post author, or admin)
    if not (session.get('is_superuser') or comment.user_id == session['user_id'] or post.user_id == session['user_id']):
        flash('You do not have permission to edit this comment.')
        return redirect(url_for('view_post', post_id=comment.post_id))
    
    if request.method == 'POST':
        content = request.form.get('content')
        if not content:
            flash('Comment cannot be empty.')
            return redirect(url_for('edit_comment', comment_id=comment_id))
        
        comment.content = content
        db.session.commit()
        flash('Comment updated successfully!')
        return redirect(url_for('view_post', post_id=comment.post_id))
    
    return render_template('edit_comment.html', comment=comment)

@app.route('/comment/<int:comment_id>/delete')
def delete_comment(comment_id):
    if 'user_id' not in session:
        flash('Please login to delete comments.')
        return redirect(url_for('login'))
    
    comment = Comment.query.get_or_404(comment_id)
    post = Post.query.get_or_404(comment.post_id)
    
    # Check if user can delete this comment (comment author, post author, or admin)
    if not (session.get('is_superuser') or comment.user_id == session['user_id'] or post.user_id == session['user_id']):
        flash('You do not have permission to delete this comment.')
        return redirect(url_for('view_post', post_id=comment.post_id))
    
    post_id = comment.post_id
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted successfully!')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/post/<int:post_id>/like/<int:is_like>')
def like_post(post_id, is_like):
    if 'user_id' not in session:
        flash('Please login to like/dislike posts.')
        return redirect(url_for('login'))
    
    # Convert is_like to boolean
    is_like_bool = bool(int(is_like))
    
    # Check if user already liked/disliked the post
    existing_like = Like.query.filter_by(user_id=session['user_id'], post_id=post_id).first()
    
    if existing_like:
        if existing_like.is_like == is_like_bool:
            # User is toggling off their like/dislike
            db.session.delete(existing_like)
            action = 'removed'
        else:
            # User is changing from like to dislike or vice versa
            existing_like.is_like = is_like_bool
            action = 'updated'
    else:
        # New like/dislike
        like = Like(
            is_like=is_like_bool,
            user_id=session['user_id'],
            post_id=post_id
        )
        db.session.add(like)
        action = 'added'
    
    db.session.commit()
    
    if action != 'removed':
        flash('Your {} has been recorded.'.format('like' if is_like_bool else 'dislike'))
    else:
        flash('Your {} has been removed.'.format('like' if is_like_bool else 'dislike'))
    
    return redirect(url_for('view_post', post_id=post_id))

# Create database tables
with app.app_context():
    db.create_all()
    
    # Create a default superuser if none exists
    if not User.query.filter_by(is_superuser=True).first():
        admin_user = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123'),
            is_superuser=True
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin user created: username='admin', password='admin123'")

if __name__ == '__main__':
    app.run(debug=True)
