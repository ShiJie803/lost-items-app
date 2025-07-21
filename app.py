import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key')

# Get and fix DATABASE_URL for PostgreSQL on Render
raw_db_url = os.environ.get('DATABASE_URL')
if raw_db_url and raw_db_url.startswith('postgres://'):
    raw_db_url = raw_db_url.replace('postgres://', 'postgresql://', 1)

app.config.update(
    UPLOAD_FOLDER=os.path.join(basedir, 'static', 'lost_items'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_DATABASE_URI=raw_db_url,
    DEBUG=os.environ.get('FLASK_DEBUG', 'False') == 'True'
)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

db = SQLAlchemy(app)

# ==================== Models ====================
class Student(db.Model):
    __tablename__ = 'student'
    student_id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Administrator(db.Model):
    __tablename__ = 'administrator'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class LostItem(db.Model):
    __tablename__ = 'item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    pickup_time = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(255), nullable=False, default='pending')
    image_filename = db.Column(db.String(500), nullable=False)

    def __repr__(self):
        return f"<LostItem id={self.id} name='{self.name}' status='{self.status}'>"


class Claim(db.Model):
    __tablename__ = 'claim'
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(255), nullable=False)
    student_id = db.Column(db.String(255), db.ForeignKey('student.student_id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    phone = db.Column(db.String(255), nullable=False)
    claim_time = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='pending')
    reason = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    student = db.relationship(Student, backref='claims')
    item = db.relationship(LostItem, backref='claims')


# ==================== DB Init ====================
with app.app_context():
    db.create_all()

# -----------------------------学生视图---------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/student_login',methods=['GET','POST'])
def student_login():
    if request.method=='POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')

        student = Student.query.filter_by(student_id=student_id).first()
        if student and check_password_hash(student.password_hash,password):
            session['student_id']=student.student_id
            flash('您已成功登录！')
            return redirect(url_for('student_dashboard'))
        else:
            flash('您的学号或者密码错误！请检查')
            return redirect(url_for('student_login'))
    return render_template('student_login.html')

@app.route('/student_register',methods=['GET','POST'])
def student_register():
    if request.method == 'POST':
        name = request.form.get('name').strip()
        student_id = request.form.get('student_id')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([name,student_id,email,phone,password,confirm_password]):
            flash('请先输入需要填写的信息！')
            redirect(url_for('student_register'))

        if Student.query.filter_by(student_id=student_id).first():
            flash('该学生已注册！请直接登录！')

        if password != confirm_password:
            flash('两次输入的密码不一致！')
            return render_template('student_register.html')

        new_student = Student(
            student_id=student_id,
            name = name,
            email = email,
            phone = phone
        )
        new_student.set_password(password)
        db.session.add(new_student)
        db.session.commit()

        flash('您已成功注册，请返回首页登录')
        return redirect(url_for('student_login'))

    return render_template('student_register.html')

@app.route('/student_alterpassword',methods=['GET','POST'])
def student_alterpassword():
    if request.method=='POST':
        student_id = request.form.get('student_id').strip()
        new_password = request.form.get('new_password').strip()
        confirm_password = request.form.get('confirm_password').strip()
        if new_password!=confirm_password:
            flash('两次输入的密码不一致！')
            return redirect(url_for('student_alterpassword'))

        student = Student.query.filter_by(student_id).first()
        if not student:
            flash ('您输入的学号有误，系统未找到该学生')
            return redirect(url_for('student_alterpassword'))
        student.password = generate_password_hash(new_password)
        flash('您已成功修改密码，请重新登录')
        return redirect(url_for('student_login'))

    return render_template('student_alterpassword.html')

@app.route('/student_logout')
def student_logout():
    session.clear()
    flash('您已成功退出登录！')
    return render_template('index.html')

@app.route('/student_dashboard')
def student_dashboard():
    return render_template('student_dashboard.html')

@app.route('/student_search_items', methods=['GET'])
def student_search_items():
    keyword = request.args.get('keyword', ' ').strip()
    search_mode = False

    # 从数据库中查询记录
    query = LostItem.query
    if keyword:
        query = query.filter(LostItem.name.contains(keyword))
    query = query.order_by(LostItem.pickup_time.desc())

    per_page = 4
    page = request.args.get('page',1,type=int)
    pagination = query.paginate(page=page,per_page=per_page,error_out=False)

    items = pagination.items
    total_pages = pagination.pages
    current_page = page

    return render_template('student_search_items.html',
                           items = items,
                           currentpage=current_page,
                           total_pages=total_pages,
                           search_mode=search_mode)

@app.route('/items/<int:item_id>')
def items_detail(item_id):
    item = LostItem.query.get_or_404(item_id)
    return render_template('items_detail.html',item = item)

@app.route('/claim/<int:item_id>',methods=['GET','POST'])
def claim_item(item_id):
    item = LostItem.query.get_or_404(item_id)
    if request.method == 'POST':
        #获取表单数据
        student_name = request.form.get('student_name').strip()
        student_id = request.form.get('student_id').strip()
        phone = request.form.get('phone').strip()
        reason = request.form.get('reason').strip()

        if not all([student_name,student_id,phone,reason]):
            flash('请将信息填写完整！')
            return redirect(url_for('claim_item',item_id=item_id))

        claim = Claim(student_name=student_name,student_id=student_id,
                      phone = phone , reason = reason , item_id = item_id , status = 'pending')
        db.session.add(claim)
        db.session.commit()
        flash('认领申请提交成功，请等待工作人员审核')
        return redirect(url_for('items_detail',item_id=item_id))
    # GET 请求时渲染表单页面
    return render_template('claim_item.html',item=item)
# ------------------------工作人员视图------------------------------
@app.route('/administrator_login',methods=['GET','POST'])
def administrator_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if email == 'zhou39506@gmail.com'and password == 'zsj123456':
            flash('您已成功登录！')
            return redirect(url_for('administrator_dashboard'))
        else:
            flash('邮箱或密码输入错误！请重新输入！')
            return redirect(url_for('administrator_login'))
    return render_template('administrator_login.html')

@app.route('/administrator_dashboard')
def administrator_dashboard():
    return render_template('administrator_dashboard.html')


@app.route('/administrator_logout')
def administrator_logout():
    session.clear()
    flash('您已成功退出登录！')
    return render_template('index.html')

# 工作者上传图片并保存到 Cloudinary
def upload_image_to_cloudinary(file):
    try:
        result = cloudinary.uploader.upload(file, folder="lost_items")
        return result.get('secure_url')
    except Exception as e:
        app.logger.error(f"Cloudinary upload failed: {str(e)}")
        return None

# 替换 administrator_upload_items 中的图片处理逻辑
@app.route('/administrator_upload_items', methods=['GET', 'POST'])
def administrator_upload_items():
    if request.method == 'POST':
        item_name = request.form.get('item_name')
        description = request.form.get('description')
        pickup_time = request.form.get('pickup_time')
        location = request.form.get('location')
        image_file = request.files.get('image')

        if not all([item_name, description, pickup_time, location, image_file]):
            flash('请填写完整所有信息并上传图片')
            return redirect(url_for('administrator_upload_items'))

        image_url = upload_image_to_cloudinary(image_file)
        if not image_url:
            flash('图片上传失败，请稍后重试')
            return redirect(url_for('administrator_upload_items'))

        new_item = LostItem(
            name=item_name,
            description=description,
            pickup_time=pickup_time,
            location=location,
            image_filename=image_url  # 保存 URL
        )
        db.session.add(new_item)
        db.session.commit()

        flash('失物信息上传成功')
        return redirect(url_for('administrator_dashboard'))

    return render_template('administrator_upload_items.html')

@app.route('/administrator_view_claims')
def administrator_view_claims():
    # 查询所有的认领申请，按提交时间倒序排列
    claims = Claim.query.order_by(Claim.timestamp.desc()).all()
    # 构造一个列表，包含每条申请需要显示的数据（手动组合成字典，方便模板中使用）
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'item_name': claim.item.name,        # 失物名称
            'student_name': claim.student.name,       # 学生姓名
            'student_id': claim.student.student_id,   # 学号
            'status': claim.status                    # 认领状态
        })

    return render_template('administrator_view_claims.html',claims=claim_data)

@app.route('/administrator_view_items', methods=['GET'])
def administrator_view_items():
    keyword = request.args.get('keyword', ' ').strip()

    # 从数据库中查询记录
    query = LostItem.query
    if keyword:
        query = query.filter(LostItem.name.contains(keyword))
    query = query.order_by(LostItem.pickup_time.desc())

    per_page = 4
    page = request.args.get('page',1,type=int)
    pagination = query.paginate(page=page,per_page=per_page,error_out=False)

    items = pagination.items
    total_pages = pagination.pages
    current_page = page

    return render_template('administrator_view_items.html',
                           items = items,
                           currentpage=current_page,
                           total_pages=total_pages)

@app.route('/administrator_items_detail/<int:item_id>')
def administrator_items_detail(item_id):
    item = LostItem.query.get_or_404(item_id)
    # 查询这个 item 的第一条 claim，如果有
    claim = Claim.query.filter_by(item_id=item.id).first()
    return render_template('administrator_items_detail.html',item=item,claim=claim)

@app.route('/administrator_delete_item/<int:item_id>',methods=['POST'])
def delete_item(item_id):
    item = LostItem.query.get_or_404(item_id)
    # 删除与该失物相关的认领记录（如果有的话）
    claims = Claim.query.filter_by(item_id=item.id).all()
    for claim in claims:
        db.session.delete(claim)

    # 删除失物记录
    db.session.delete(item)
    db.session.commit()
    if os.path.exists(item.image_filename):
        os.remove(item.image_filename)  # 删除图片文件

    flash('您已成功删除该失物和相关认领记录！')
    return redirect(url_for('administrator_view_items'))


@app.route('/administrator_review_claim_items/<int:claim_id>',methods=['GET','POST'])
def administrator_review_claim_items(claim_id):
    # 查询这条认领记录
    claim = Claim.query.get_or_404(claim_id)
    item = LostItem.query.get_or_404(claim.item_id)
    if request.method == 'POST':
        # 获取表单提交的审核决策
        decision = request.form.get('decision')
        if decision == 'approved':
            claim.status = 'approved'
        elif decision == 'rejected':
            claim.status = 'rejected'
        else:
            flash('未知操作，请重试！')
            return redirect(url_for('administrator_review_claim_items'))

        # 更新数据库
        db.session.commit()
        flash('审核结果已成功保存')
        return redirect(url_for('administrator_view_items'))

    # GET 请求时渲染表单页面
    return render_template('administrator_review_claim_items.html',claim=claim,item=item)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # 默认5000，Render会注入PORT环境变量
    app.run(host='0.0.0.0', port=port, debug=True)



