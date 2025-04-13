from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app as app
from flask_bcrypt import Bcrypt
from datetime import datetime

auth_blueprint = Blueprint('auth', __name__, template_folder='../templates/pages')

def get_user_from_db(email):
    return app.db.users.find_one({"email": email})

@auth_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        print(f"Attempting to log in user: {email}")
        user = get_user_from_db(email)
        
        if user:
            print(f"User found: {user}")
            print(f"Entered password: {password}")
            print(f"Stored password hash: {user['password']}")
            password_match = Bcrypt().check_password_hash(user['password'], password)
            print(f"Password match result: {password_match}")
        
        if user and password_match:
            print("Password match successful.")
            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            session['user_photo'] = user.get('photo', 'default.jpg')  # Default to 'default.jpg' if no photo is provided
            flash("Logged in successfully!", "success")
            if user['role'] == 'Human Resources':
                return redirect(url_for('views.hr_page'))  # Redirect HR to the HR page
            else:
                return redirect(url_for('views.dashboard'))  # Redirect other roles to the dashboard

        
        flash("Invalid email or password.", "danger")
    
    return render_template('login.html')

@auth_blueprint.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['user-name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        joined_date = request.form['joinedDate']

        # Check if the email already exists
        existing_user = app.db.users.find_one({"email": email})
        if existing_user:
            flash("Email already exists. Please use a different email.", "danger")
            return redirect(url_for('auth.signup'))
        
        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('auth.signup'))
        
        if datetime.strptime(joined_date, '%Y-%m-%d') > datetime.now():
            flash("Joined date cannot be in the future. Please select a valid date.", "danger")
            return redirect(url_for('auth.signup'))
        
        hashed_password = Bcrypt().generate_password_hash(password).decode('utf-8')
        user = {
            "name": username,
            "email": email,
            "password": hashed_password,
            "role": "Pending Approval",  # Default role to be approved by HR
            "salary": [],
            "photo": "default.jpg",
            "industryExpertise": [],
            "color": [],
            "joinedDate": datetime.strptime(joined_date, '%Y-%m-%d'),
            "lineManager": [],
        }
        try:
            result = app.db.users.insert_one(user)
            print(f"User {username} inserted with id {result.inserted_id}")
            # Simulate sending notification to HR (print statement here for simplicity)
            print("Notification sent to HR for user approval.")
            flash("Account created successfully! HR will review and approve your account.", "success")
            return redirect(url_for('auth.login'))
        except Exception as e:
            print(f"Error inserting user: {e}")
            flash("Error creating account. Please try again.", "danger")
            return redirect(url_for('auth.signup'))
    return render_template('signup.html')

@auth_blueprint.route('/logout')
def logout():
    session.clear()  # Clear the session
    flash("Logged out successfully.", "success")
    return redirect(url_for('auth.login'))
