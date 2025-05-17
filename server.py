from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import csv
import os
import pandas as pd
from io import BytesIO
import serial  # Import the serial library

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a strong secret key!

# ======================
# Configuration
# ======================
app.config['DATABASE_DIR'] = 'Database'
app.config['STUDENTS_FILE'] = os.path.join(app.config['DATABASE_DIR'], 'students.csv')
app.config['ATTENDANCE_FILE'] = os.path.join(app.config['DATABASE_DIR'], 'attendance.csv')
app.config['ADMINS_FILE'] = os.path.join(app.config['DATABASE_DIR'], 'admins.csv')
app.config['SESSION_COOKIE_SECURE'] = True  # Enable in production with HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# ======================
# Authentication Setup
# ======================
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# ======================
# Serial Setup
# ======================
def setup_serial(port='/dev/ttyUSB0', baudrate=115200):
    """Setup serial communication with ESP32."""
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        return ser
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        return None

# Initialize serial communication
esp32_serial = setup_serial(port='COM5')  # Adjust the port as necessary

# ======================
# Helper Functions
# ======================
def init_database():
    """Initialize database files if they don't exist"""
    os.makedirs(app.config['DATABASE_DIR'], exist_ok=True)
    
    # Students database
    if not os.path.exists(app.config['STUDENTS_FILE']):
        with open(app.config['STUDENTS_FILE'], 'w', newline='') as f:
            f.write("UID,Name,Email,RegisteredDate\n")
    
    # Attendance database
    if not os.path.exists(app.config['ATTENDANCE_FILE']):
        with open(app.config['ATTENDANCE_FILE'], 'w', newline='') as f:
            f.write("UID,Name,Timestamp,Status\n")
    
    # Admins database
    if not os.path.exists(app.config['ADMINS_FILE']):
        with open(app.config['ADMINS_FILE'], 'w', newline='') as f:
            f.write("Username,PasswordHash\n")
        # Add default admin if no admins exist
        with open(app.config['ADMINS_FILE'], 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'admin',
                generate_password_hash('admin123')  # Change this password!
            ])

def load_admins():
    """Load admin credentials from file"""
    admins = {}
    try:
        with open(app.config['ADMINS_FILE'], 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                admins[row['Username']] = row['PasswordHash']
    except FileNotFoundError:
        pass
    return admins

def get_today_attendance():
    """Get list of UIDs marked present today"""
    today = datetime.now().date()
    present = []
    try:
        with open(app.config['ATTENDANCE_FILE'], 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                record_date = datetime.strptime(row['Timestamp'], '%Y-%m-%d %H:%M:%S').date()
                if record_date == today and row['Status'] == 'Present':
                    present.append(row['UID'])
    except FileNotFoundError:
        pass
    return present

def mark_absent_students():
    """Automatically mark students as absent if they were present yesterday but not today"""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Get all students
    try:
        with open(app.config['STUDENTS_FILE'], 'r') as f:
            students = [row['UID'] for row in csv.DictReader(f)]
    except FileNotFoundError:
        return

    # Get present students from yesterday
    present_yesterday = set()
    try:
        with open(app.config['ATTENDANCE_FILE'], 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                record_date = datetime.strptime(row['Timestamp'], '%Y-%m-%d %H:%M:%S').date()
                if record_date == yesterday and row['Status'] == 'Present':
                    present_yesterday.add(row['UID'])
    except FileNotFoundError:
        return

    # Mark absent for students who were present yesterday but not today
    absent_students = present_yesterday - set(get_today_attendance())
    
    try:
        with open(app.config['ATTENDANCE_FILE'], 'a', newline='') as f:
            writer = csv.writer(f)
            for uid in absent_students:
                writer.writerow([
                    uid,
                    get_student_name(uid),
                    datetime.now().strftime('%Y-%m-%d 23:59:59'),
                    'Absent (Auto)'
                ])
    except Exception as e:
        print(f"Error marking absent students: {e}")

def get_student_name(uid):
    """Get student name by UID"""
    try:
        with open(app.config['STUDENTS_FILE'], 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['UID'] == uid:
                    return row['Name']
    except FileNotFoundError:
        pass
    return "Unknown"

def get_attendance_stats(days=7):
    """Get attendance statistics for the last N days"""
    stats = []
    today = datetime.now().date()
    
    try:
        with open(app.config['ATTENDANCE_FILE'], 'r') as f:
            reader = csv.DictReader(f)
            records = list(reader)
    except FileNotFoundError:
        return stats
    
    for i in range(days):
        date = today - timedelta(days=i)
        present = 0
        absent = 0
        
        for record in records:
            record_date = datetime.strptime(record['Timestamp'], '%Y-%m-%d %H:%M:%S').date()
            if record_date == date:
                if record['Status'] == 'Present':
                    present += 1
                elif 'Absent' in record['Status']:
                    absent += 1
        
        stats.append({
            'date': date.strftime('%a'),  # Day name (Mon, Tue, etc.)
            'present': present,
            'absent': absent
        })
    
    return list(reversed(stats))  # Return oldest to newest

# ======================
# Routes
# ======================

@app.route('/')
def home():
    """Root route - redirect to appropriate page based on auth status"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admins = load_admins()
        
        if username in admins and check_password_hash(admins[username], password):
            user = User(username)
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    """Admin registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        admins = load_admins()
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('register_admin'))
        
        if username in admins:
            flash('Username already exists!', 'error')
            return redirect(url_for('register_admin'))
        
        # Add new admin
        try:
            with open(app.config['ADMINS_FILE'], 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([username, generate_password_hash(password)])
            flash('Admin registered successfully! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error registering admin: {str(e)}', 'error')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """Logout current user"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Admin dashboard"""
    try:
        # Initialize with default values
        present = 0
        total = 0
        
        # Get today's attendance count
        present = len(get_today_attendance())
        
        # Get total student count
        if os.path.exists(app.config['STUDENTS_FILE']):
            with open(app.config['STUDENTS_FILE'], 'r') as f:
                total = sum(1 for _ in csv.DictReader(f))
        
        # Get attendance statistics
        stats = get_attendance_stats()
        
        return render_template('dashboard.html',
                            present=present,
                            total=total,
                            stats=stats)
    
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('dashboard.html',
                            present=0,
                            total=0,
                            stats=[])

@app.route('/register_rfid', methods=['POST'])
@login_required
def register_with_rfid():
    """Register new student with RFID"""
    uid = request.form['uid']
    name = request.form['name']
    email = request.form['email']
    
    # Validate inputs
    if not uid or not name or not email:
        flash('All fields are required!', 'error')
        return redirect(url_for('dashboard'))
    
    # Check if UID already exists
    try:
        with open(app.config['STUDENTS_FILE'], 'r') as f:
            for row in csv.DictReader(f):
                if row['UID'] == uid:
                    flash('Student already registered!', 'error')
                    return redirect(url_for('dashboard'))
    except FileNotFoundError:
        pass
    
    # Register new student
    try:
        with open(app.config['STUDENTS_FILE'], 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([uid, name, email, datetime.now().date()])
        flash('Student registered successfully!', 'success')
    except Exception as e:
        flash(f'Error registering student: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/api/attendance', methods=['POST'])
def record_attendance():
    """API endpoint for recording attendance (called by RFID scanner)"""
    uid = request.json.get('uid')
    
    if not uid:
        return jsonify({"status": "error", "message": "UID required"}), 400
    
    # Check registration
    registered = False
    name = "Unknown"
    try:
        with open(app.config['STUDENTS_FILE'], 'r') as f:
            for row in csv.DictReader(f):
                if row['UID'] == uid:
                    registered = True
                    name = row['Name']
                    break
    except FileNotFoundError:
        pass
    
    if not registered:
        return jsonify({"status": "unregistered"}), 404
    
    # Record attendance
    try:
        with open(app.config['ATTENDANCE_FILE'], 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                uid,
                name,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Present'
            ])
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
    # Auto-mark absent students daily at midnight
    if datetime.now().hour == 0:  # Runs at midnight
        mark_absent_students()
    
    return jsonify({"status": "success", "name": name})

@app.route('/api/live_attendance')
@login_required
def live_attendance():
    """API endpoint for live attendance data"""
    try:
        # Get the last 10 attendance records
        with open(app.config['ATTENDANCE_FILE'], 'r') as f:
            reader = csv.DictReader(f)
            records = list(reader)[-10:]  # Get last 10 records
        
        return jsonify(records)
    except FileNotFoundError:
        return jsonify([])

@app.route('/students')
@login_required
def manage_students():
    """Manage students page"""
    students = []
    try:
        with open(app.config['STUDENTS_FILE'], 'r') as f:
            students = list(csv.DictReader(f))
    except FileNotFoundError:
        flash('Students database not found', 'error')
    
    return render_template('students.html', students=students)

@app.route('/update_student', methods=['POST'])
@login_required
def update_student():
    """Update student information"""
    uid = request.form['uid']
    new_name = request.form['name']
    new_email = request.form['email']
    
    # Update student record
    updated = False
    rows = []
    try:
        with open(app.config['STUDENTS_FILE'], 'r') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row['UID'] == uid:
                    row['Name'] = new_name
                    row['Email'] = new_email
                    updated = True
                rows.append(row)
        
        if updated:
            # Write back updated data
            with open(app.config['STUDENTS_FILE'], 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            flash('Student updated successfully!', 'success')
        else:
            flash('Student not found!', 'error')
    except Exception as e:
        flash(f'Error updating student: {str(e)}', 'error')
    
    return redirect(url_for('manage_students'))

@app.route('/delete_student', methods=['POST'])
@login_required
def delete_student():
    """Delete a student record"""
    uid = request.form['uid']
    
    try:
        with open(app.config['STUDENTS_FILE'], 'r') as f:
            reader = csv.DictReader(f)
            students = [row for row in reader if row['UID'] != uid]
        
        with open(app.config['STUDENTS_FILE'], 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['UID', 'Name', 'Email', 'RegisteredDate'])
            writer.writeheader()
            writer.writerows(students)
        
        flash('Student deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting student: {str(e)}', 'error')
    
    return redirect(url_for('manage_students'))

@app.route('/export_students')
@login_required
def export_students():
    """Export students data to Excel"""
    try:
        # Read student data
        df = pd.read_csv(app.config['STUDENTS_FILE'])
        
        # Create in-memory file
        output = BytesIO()
        
        # Use ExcelWriter with xlsxwriter engine
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Students')
            
            # Auto-adjust columns' width
            worksheet = writer.sheets['Students']
            for idx, col in enumerate(df.columns):
                max_len = max((
                    df[col].astype(str).map(len).max(),  # max in column
                    len(str(col))  # header length
                )) + 1
                worksheet.set_column(idx, idx, max_len)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'students_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
    except Exception as e:
        flash(f'Error exporting student data: {str(e)}', 'error')
        app.logger.error(f"Export students error: {str(e)}")
        return redirect(url_for('manage_students'))

@app.route('/export_attendance')
@login_required
def export_attendance():
    """Export attendance data to Excel"""
    try:
        # Apply filters if any
        date_filter = request.args.get('date')
        status_filter = request.args.get('status')
        uid_filter = request.args.get('uid')
        
        # Read CSV data
        df = pd.read_csv(app.config['ATTENDANCE_FILE'])
        
        # Apply filters
        if date_filter:
            df = df[df['Timestamp'].str.startswith(date_filter)]
        if status_filter:
            df = df[df['Status'].str.contains(status_filter)]
        if uid_filter:
            df = df[df['UID'] == uid_filter]
        
        # Create in-memory file
        output = BytesIO()
        
        # Use ExcelWriter with xlsxwriter engine
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Attendance')
            
            # Auto-adjust columns' width
            worksheet = writer.sheets['Attendance']
            for idx, col in enumerate(df.columns):
                max_len = max((
                    df[col].astype(str).map(len).max(),  # max in column
                    len(str(col))  # header length
                )) + 1
                worksheet.set_column(idx, idx, max_len)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'attendance_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
    except Exception as e:
        flash(f'Error exporting attendance data: {str(e)}', 'error')
        app.logger.error(f"Export attendance error: {str(e)}")
        return redirect(url_for('view_attendance'))

@app.route('/attendance')
@login_required
def view_attendance():
    """View attendance records"""
    attendance = []
    try:
        with open(app.config['ATTENDANCE_FILE'], 'r') as f:
            attendance = list(csv.DictReader(f))
        
        # Apply filters if any
        date_filter = request.args.get('date')
        status_filter = request.args.get('status')
        uid_filter = request.args.get('uid')
        
        if date_filter:
            attendance = [r for r in attendance if r['Timestamp'].startswith(date_filter)]
        if status_filter:
            attendance = [r for r in attendance if r['Status'] == status_filter]
        if uid_filter:
            attendance = [r for r in attendance if r['UID'] == uid_filter]
            
    except FileNotFoundError:
        flash('Attendance records not found', 'error')
    
    return render_template('attendance.html', attendance=attendance)

@app.route('/api/student_info')
@login_required
def student_info():
    """Get student info by UID"""
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "UID required"}), 400
    
    try:
        with open(app.config['STUDENTS_FILE'], 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['UID'] == uid:
                    return jsonify({
                        "uid": uid,
                        "name": row['Name'],
                        "email": row['Email'],
                        "registered_date": row['RegisteredDate']
                    })
        return jsonify({"error": "Student not found"}), 404
    except FileNotFoundError:
        return jsonify({"error": "Database not found"}), 500

# ======================
# Main Execution
# ======================
if __name__ == '__main__':
    init_database()
    # Auto-mark absent students when starting (if it's after midnight)
    if datetime.now().hour == 0:
        mark_absent_students()
    app.run(host='127.0.0.1', port=5000, debug=True)
