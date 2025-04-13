from datetime import datetime, timedelta
from io import BytesIO
import logging
import os
from bson import ObjectId
from flask import Blueprint, abort, render_template, request, redirect, send_file, send_from_directory, url_for, flash, session, jsonify, current_app as app, send_from_directory
from .services import SGT, UPLOAD_FOLDER, add_task, approve_leave_request, approve_plot_notification, book_desk, cancel_booking_in_db, cancel_leave, create_engagement, decline_leave_request, decline_plot_notification, delete_expense_claim, delete_schedule, edit_booking_in_db, generate_expense_report, get_all_expense_claims, get_desks, get_employee_utilization, get_engagement_team_for_task, get_engagement_utilization, get_engagements, get_engagements_for_user, get_expense_claim, get_expense_summary, get_leave_data, get_monthly_expenses, get_pending_tasks, complete_task, get_pending_users,  get_scheduler_data, amend_schedule, approve_notification, decline_notification, get_staff_by_level, get_tasks_by_engagement, get_tasks_for_dragging, get_user_by_id, get_users_by_role, modify_expense_claim, modify_leave, plot_calendar, recommend_employees_knn, review_task_and_complete, save_expense_claim, send_approval_notification, send_chat_to_chatgpt, send_prompt_to_chatgpt, show_all_engagements, submit_leave_request, submit_timesheet, update_user_profile

views_blueprint = Blueprint('views', __name__, template_folder='../templates/pages')

@views_blueprint.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('views.dashboard'))
    return redirect(url_for('auth.login'))

# @views_blueprint.route('/dashboard')
# def dashboard():
#     if 'user_id' not in session:
#         flash("You need to login first.", "warning")
#         return redirect(url_for('auth.login'))

#     user_role = session.get('user_role')
#     user_id = session.get('user_id')

#     print(f"User Role: {user_role}")
#     print(f"User ID: {user_id}")

#     try:
#         # Attempt to fetch engagements and tasks
#         engagements = get_engagements(app.db, user_id) or []  # Default to empty list if None
#         tasks = get_pending_tasks(app.db, user_id) or []      # Default to empty list if None
        
#         # Render the dashboard with engagements and tasks (empty lists if no data)
#         return render_template(
#             'dashboard.html',
#             engagements=engagements,
#             tasks=tasks,
#             user_role=user_role
#         )
#     except Exception as e:
#         print(f"Error retrieving engagements or tasks: {e}")
#         flash("There was an error retrieving your dashboard data. Please try again later.", "danger")
#         return render_template('dashboard.html', engagements=[], tasks=[], user_role=user_role)

@views_blueprint.route('/add_task', methods=['POST'])
def add_task_route():
    if 'user_id' not in session:
        flash("You need to login first.", "warning")
        return {"success": False, "message": "You need to login first."}

    data = request.json
    print("Received data:", data)  # Debug log
    try:
        message = add_task(app.db, data)
        print("Add task success message:", message)  # Debug log
        flash(message, "success")
        return {"success": True, "message": message}
    except Exception as e:
        print(f"Error adding task: {e}")  # Debug log
        flash("There was an error adding the task.", "danger")
        return {"success": False, "message": "There was an error adding the task."}



@views_blueprint.route('/create-engagement', methods=['GET', 'POST'])
def create_engagement_route():
    if 'user_id' not in session or session.get('user_role') != 'Partner':
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('views.dashboard'))

    if request.method == 'POST':
        try:
            data = request.json
            print("Form data received:", data)  # Debugging line
            create_engagement(app.db, data, session['user_id'])
            flash("Engagement created successfully.", "success")
            return jsonify({"success": True}), 200
        except Exception as e:
            print(f"Error creating engagement: {e}")
            flash("There was an error creating the engagement.", "danger")
            return jsonify({"success": False, "error": str(e)}), 500

    if request.method == 'GET':
        # Fetch managers and members for the dropdowns
        managers = list(app.db.users.find({"role": "Manager"}, {"_id": 1, "name": 1}))
        members = list(app.db.users.find({"role": {"$in": ["Associate", "Senior Associate"]}}, {"_id": 1, "name": 1}))
        print(f"Managers fetched: {managers}")
        print(f"Members fetched: {members}")
        return render_template('dashboard.html', managers=managers, members=members)


@views_blueprint.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('auth.login'))

@views_blueprint.route('/complete_task', methods=['POST'])
def complete_task_route():
    if 'user_id' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('auth.login'))

    task_id = request.json.get('taskId')
    time_charge_hours = request.json.get('timeChargeHours')
    time_charge_minutes = request.json.get('timeChargeMinutes')
    confirm_complete = request.json.get('confirmCompletion')

    if not task_id or not confirm_complete:
        flash("Invalid task completion request.", "danger")
        return {"success": False, "message": "Invalid task completion request."}

    try:
        time_charge = (int(time_charge_hours) * 60) + int(time_charge_minutes)
        message = complete_task(app.db, task_id, session['user_id'], int(time_charge_hours), int(time_charge_minutes))
        flash(message, "success")
        return {"success": True, "message": message}
    except Exception as e:
        print(f"Error completing task: {e}")
        flash("There was an error completing the task.", "danger")
        return {"success": False, "message": "There was an error completing the task."}

@views_blueprint.route('/scheduler')
def scheduler():
    return render_template('scheduler.html')

@views_blueprint.route('/get_scheduler_data', methods=['GET'])
def get_scheduler_data_route():
    view = request.args.get('view', 'week')
    date_range = request.args.get('dateRange', '')
    print(f"View: {view}, Date Range: {date_range}")  # Debugging log
    data = get_scheduler_data(app.db, view, date_range)
    print(f"Scheduler Data: {data}")  # Debugging log
    return jsonify(data)

@views_blueprint.route('/chatbot')
def chatbot():
    user_id = session.get('user_id')
    user = app.db.users.find_one({"_id": ObjectId(user_id)}, {"photo": 1, "name": 1})
    user_photo_url = url_for('static', filename=f'images/{user["photo"]}') if user and user.get('photo') else url_for('static', filename='images/default-user.png')
    
    notifications = list(app.db.notifications.find({"to": ObjectId(user_id), "status": "pending"}))
    api_key = os.getenv("OPENAI_API_KEY")
    
    return render_template('chatbot.html', notifications=notifications, user_photo_url=user_photo_url, api_key=api_key)

@views_blueprint.route('/amend_schedule', methods=['POST'])
def amend_schedule_route():
    user_id = session.get('user_id')
    swap_requests = request.json
    result = amend_schedule(app.db, user_id, swap_requests)
    return jsonify(result)


@views_blueprint.route('/approve_notification/<notification_id>', methods=['POST'])
def approve_notification_route(notification_id):
    result = approve_notification(app.db, notification_id)
    return jsonify(result)

@views_blueprint.route('/decline_notification/<notification_id>', methods=['POST'])
def decline_notification_route(notification_id):
    result = decline_notification(app.db, notification_id)
    return jsonify(result)

@views_blueprint.route('/get_employee_options', methods=['GET'])
def get_employee_options():
    try:
        employees = list(app.db.users.find({"role": {"$ne": "Human Resources"}}, {"_id": 1, "name": 1, "role": 1}))
        print("Fetched employees:", employees)
        employee_options = [{"id": str(emp["_id"]), "name": emp["name"], "role": emp["role"]} for emp in employees]
        return jsonify(employee_options)
    except Exception as e:
        print(f"Error fetching employee options: {e}")
        return jsonify({"error": "Error fetching employee options"}), 500
    
@views_blueprint.route('/get_engagements', methods=['GET'])
def get_engagements_route():
    user_id = session['user_id']
    role = session['user_role']
    try:
        engagements = get_engagements_for_user(app.db, user_id, role)
        return jsonify(engagements), 200
    except Exception as e:
        print(f"Error in get_engagements_route: {e}")
        return jsonify([]), 500

@views_blueprint.route('/get_staff', methods=['GET'])
def get_staff_route():
    level = request.args.get('level')
    try:
        staff = get_staff_by_level(app.db, level)
        return jsonify(staff), 200
    except Exception as e:
        print(f"Error in get_staff_route: {e}")
        return jsonify([]), 500

@views_blueprint.route('/plot_calendar', methods=['POST'])
def plot_calendar_route():
    data = request.json
    user_id = session['user_id']
    role = session['user_role']
    try:
        result = plot_calendar(app.db, user_id, role, data)
        if result["success"]:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": False, "message": result["message"]}), 400
    except Exception as e:
        print(f"Error in plot_calendar_route: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@views_blueprint.route('/approve_plot_notification', methods=['POST'])
def approve_plot_notification_route():
    notification_id = request.json.get('notification_id')
    try:
        result = approve_plot_notification(app.db, notification_id)
        return jsonify(result), 200 if result['success'] else 400
    except Exception as e:
        print(f"Error in approve_plot_notification_route: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@views_blueprint.route('/decline_plot_notification', methods=['POST'])
def decline_plot_notification_route():
    notification_id = request.json.get('notification_id')
    try:
        result = decline_plot_notification(app.db, notification_id)
        return jsonify(result), 200 if result['success'] else 400
    except Exception as e:
        print(f"Error in decline_plot_notification_route: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@views_blueprint.route('/delete_schedule', methods=['POST'])
def delete_schedule_route():
    data = request.json
    employment_id = data.get('employmentId')
    date = data.get('date')
    engagement_id = data.get('engagementId')

    result = delete_schedule(app.db, employment_id, date, engagement_id)
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@views_blueprint.route('/office_space', methods=['GET'])
def office_space():
    return render_template('office_space.html')

@views_blueprint.route('/book_desk', methods=['POST'])
def book_desk_route():
    data = request.json
    desk_id = data.get('desk_id')
    user_id = data.get('user_id')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    try:
        result = book_desk(app.db, desk_id, user_id, start_time, end_time)
        return jsonify(result), 200 if result['success'] else 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/edit_booking', methods=['POST'])
def edit_booking():
    data = request.json
    desk_id = data['desk_id']
    user_id = data['user_id']
    start_time = data['start_time']
    end_time = data['end_time']

    result = edit_booking_in_db(app.db, desk_id, user_id, start_time, end_time)
    return jsonify(result)

@app.route('/cancel_booking', methods=['POST'])
def cancel_booking():
    data = request.json
    desk_id = data['desk_id']
    user_id = data['user_id']

    result = cancel_booking_in_db(app.db, desk_id, user_id)
    return jsonify(result)
    
@views_blueprint.route('/get_desks', methods=['GET'])
def get_desks_route():
    date_str = request.args.get('date')
    try:
        date = datetime.fromisoformat(date_str).astimezone(SGT)
        print(f"Fetching desks for date: {date}")
        result = get_desks(app.db, date)
        print(f"Desks data returned: {result}")
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_desks_route: {e}")
        return jsonify({"desks": [], "error": str(e)}), 500
    
@views_blueprint.route('/leave_board')
def leave_board():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session.get('user_id')
    leave_data = get_leave_data(app.db, user_id)
    
    leave_applications = list(app.db.leave_application.find({"user_id": ObjectId(user_id)}))
    for leave in leave_applications:
        leave['start_date'] = leave['start_date'].astimezone(SGT)
        leave['end_date'] = leave['end_date'].astimezone(SGT)
        leave['counts'] = (leave['end_date'] - leave['start_date']).days + 1
    
    return render_template('leave.html', leave_data=leave_data, leave_applications=leave_applications)


@views_blueprint.route('/submit_leave_request', methods=['POST'])
def submit_leave_request_route():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 403

    user_id = session['user_id']
    leave_type = request.form.get('leave_type')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    about = request.form.get('about')
    attachments = request.files.getlist('attachments')

    result = submit_leave_request(app.db, user_id, leave_type, start_date, end_date, about, attachments)
    
    return jsonify(result)

@views_blueprint.route('/approve_leave_request/<leave_id>', methods=['POST'])
def approve_leave_request_route(leave_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 403

    approver_id = session['user_id']
    result = approve_leave_request(app.db, leave_id, approver_id)
    return jsonify(result)

@views_blueprint.route('/decline_leave_request/<leave_id>', methods=['POST'])
def decline_leave_request_route(leave_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 403

    approver_id = session['user_id']
    result = decline_leave_request(app.db, leave_id, approver_id)
    return jsonify(result)


@views_blueprint.route('/cancel_leave/<leave_id>', methods=['POST'])
def cancel_leave_route(leave_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 403

    user_id = session['user_id']
    result = cancel_leave(app.db, leave_id, user_id)
    return jsonify(result)

@views_blueprint.route('/get_leave_details/<leave_id>', methods=['GET'])
def get_leave_details_route(leave_id):
    try:
        leave_details = app.db.leave_application.find_one({"_id": ObjectId(leave_id)})
        if leave_details:
            leave_details['_id'] = str(leave_details['_id'])
            leave_details['user_id'] = str(leave_details['user_id'])
            if 'approved_by' in leave_details:
                leave_details['approved_by'] = str(leave_details['approved_by'])
            if 'declined_by' in leave_details:
                leave_details['declined_by'] = str(leave_details['declined_by'])
            return jsonify(leave_details), 200
        else:
            return jsonify({"success": False, "message": "Leave details not found."}), 404
    except Exception as e:
        print(f"Error in get_leave_details_route: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@views_blueprint.route('/modify_leave/<leave_id>', methods=['POST'])
def modify_leave_route(leave_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 403

    user_id = session['user_id']
    leave_type = request.form.get('leave_type')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    about = request.form.get('about')
    attachments = request.files.getlist('attachments')

    result = modify_leave(app.db, leave_id, user_id, leave_type, start_date, end_date, about, attachments)
    return jsonify(result)
    
@views_blueprint.route('/expenses_claims', methods=['GET'])
def expenses_claims():
    if 'user_id' not in session:
        flash("You must be logged in to view this page.", "danger")
        return redirect(url_for('login'))

    try:
        user_id = session['user_id']
        expense_claims = get_all_expense_claims(app.db, user_id)
        summary = get_expense_summary(app.db, user_id)
        monthly_expenses = get_monthly_expenses(app.db, user_id)  # Get monthly expenses

        return render_template('expenses_claims.html', 
                               expense_claims=expense_claims, 
                               summary=summary,
                               monthly_expenses=monthly_expenses)
    except Exception as e:
        print(f"Error in expenses_claims route: {e}")
        flash("There was an error retrieving the expense claims.", "danger")
        return redirect(url_for('dashboard'))

@views_blueprint.route('/record_expense', methods=['POST'])
def record_expense():
    if 'user_id' not in session:
        print("User not logged in")
        return jsonify({"success": False, "message": "User not logged in"}), 403

    user_id = session['user_id']
    data = request.form.to_dict()  # Get form data
    print(f"Form data received: {data}")

    file = request.files.get('attachment')  # Get file from request
    if file:
        print(f"Attachment received: {file.filename}")
    else:
        print("No attachment received")

    result = save_expense_claim(app.db, user_id, data, file)
    
    if result['success']:
        print("Expense recorded successfully!")
        return jsonify(result), 200
    else:
        print(f"Failed to record expense: {result['message']}")
        return jsonify(result), 500
    
@views_blueprint.route('/show_all_engagements', methods=['GET'])
def show_engagements_route():
    try:
        print("Request to show all engagements")
        engagements = show_all_engagements(app.db)
        return jsonify(engagements), 200
    except Exception as e:
        print(f"Error in get_engagements_route: {e}")
        return jsonify([]), 500
    
@views_blueprint.route('/delete_expense/<string:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 403
    
    user_id = session['user_id']
    
    try:
        result = app.db.expenses_claims.delete_one({"_id": ObjectId(expense_id), "user_id": ObjectId(user_id)})
        if result.deleted_count > 0:
            return jsonify({"success": True, "message": "Expense claim removed successfully!"}), 200
        else:
            return jsonify({"success": False, "message": "Expense claim not found."}), 404
    except Exception as e:
        print(f"Error deleting expense: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    
@views_blueprint.route('/get_expense/<string:expense_id>', methods=['GET'])
def get_expense(expense_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 403
    
    user_id = session['user_id']
    
    try:
        expense_claim = app.db.expenses_claims.find_one({"_id": ObjectId(expense_id), "user_id": ObjectId(user_id)})
        if expense_claim:
            expense_claim['_id'] = str(expense_claim['_id'])
            expense_claim['user_id'] = str(expense_claim['user_id'])
            expense_claim['engagement_id'] = str(expense_claim['engagement_id'])
            expense_claim['reviewer_id'] = str(expense_claim['reviewer_id'])
            expense_claim['date'] = expense_claim['date'].strftime('%Y-%m-%d')
            return jsonify(expense_claim), 200
        else:
            return jsonify({"success": False, "message": "Expense claim not found."}), 404
    except Exception as e:
        print(f"Error retrieving expense: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@views_blueprint.route('/modify_expense', methods=['POST'])
def modify_expense():
    expense_id = request.form.get('expense_id')
    file = request.files.get('attachment')
    result = modify_expense_claim(app.db, expense_id, request.form, file)
    if result['success']:
        return jsonify({"success": True, "message": result['message']}), 200
    else:
        return jsonify({"success": False, "message": result['message']}), 500


@views_blueprint.route('/approve_expense/<expense_id>', methods=['POST'])
def approve_expense(expense_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 403

    user_id = session['user_id']
    try:
        # Update the expense claim status
        result = app.db.expenses_claims.update_one(
            {"_id": ObjectId(expense_id), "reviewer_id": ObjectId(user_id)},
            {"$set": {"status": "Approved"}}
        )
        
        if result.modified_count > 0:
            # Update the corresponding notification to 'approved'
            app.db.notifications.update_one(
                {"expense_claim_id": ObjectId(expense_id)},
                {"$set": {"status": "approved"}}
            )
            return jsonify({"success": True, "message": "Expense claim approved successfully!"}), 200
        else:
            return jsonify({"success": False, "message": "Expense claim not found or not authorized."}), 404
    except Exception as e:
        print(f"Error approving expense: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@views_blueprint.route('/decline_expense/<expense_id>', methods=['POST'])
def decline_expense(expense_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 403

    user_id = session['user_id']
    try:
        # Update the expense claim status
        result = app.db.expenses_claims.update_one(
            {"_id": ObjectId(expense_id), "reviewer_id": ObjectId(user_id)},
            {"$set": {"status": "Declined"}}
        )
        
        if result.modified_count > 0:
            # Update the corresponding notification to 'declined'
            app.db.notifications.update_one(
                {"expense_claim_id": ObjectId(expense_id)},
                {"$set": {"status": "declined"}}
            )
            return jsonify({"success": True, "message": "Expense claim declined successfully!"}), 200
        else:
            return jsonify({"success": False, "message": "Expense claim not found or not authorized."}), 404
    except Exception as e:
        print(f"Error declining expense: {e}")
        return jsonify({"success": False, "message": str(e)}), 500



@app.route('/generate-expense-report', methods=['GET'])
def generate_expense_report_route():
    engagement_id = request.args.get('engagement_id')
    print(f"Received request to generate report for engagement_id: {engagement_id}")
    
    if not engagement_id:
        print("No engagement ID provided.")
        return {"success": False, "message": "Engagement ID is required."}, 400
    
    result = generate_expense_report(app.db, engagement_id)
    
    if isinstance(result, dict) and not result.get('success'):
        print(f"Failed to generate report: {result.get('message')}")
        return result, 500  # Return a server error response
    
    print("Report generated successfully.")
    return result  # Return the file response

@views_blueprint.route('/get_engagements_for_report', methods=['GET'])
def get_engagements_for_report_route():
    user_id = session['user_id']
    role = session['user_role']
    try:
        # Assuming get_engagements_for_user is a function that fetches the engagements
        engagements = get_engagements_for_user(app.db, user_id, role)
        return jsonify(engagements), 200
    except Exception as e:
        print(f"Error in get_engagements_for_report_route: {e}")
        return jsonify([]), 500



#task.html function
@views_blueprint.route('/task', methods=['GET'])
def task():
    """Render the task page for a specific engagement."""
    if 'user_id' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('auth.login'))

    engagement_id = request.args.get('engagement_id')
    if not engagement_id:
        flash("Invalid engagement.", "danger")
        return redirect(url_for('views.dashboard'))

    try:
        # Fetch user information (e.g., name, photo) from session
        user_name = session.get('user_name')
        user_photo = session.get('user_photo')  # Assuming you stored photo path in session

        # Fetch tasks for the engagement
        tasks = get_tasks_by_engagement(app.db, engagement_id)

        # Fetch the engagement team members
        team_members = get_engagement_team_for_task(app.db, engagement_id)

        return render_template(
            'task.html',
            tasks=tasks,
            engagement_id=engagement_id,
            user_name=user_name,
            user_photo=user_photo,
            team_members=team_members  # Pass team_members to the template
        )
    except Exception as e:
        print(f"Error retrieving tasks or team members for engagement {engagement_id}: {e}")
        flash("There was an error retrieving tasks or team members for the engagement.", "danger")
        return redirect(url_for('views.dashboard'))



@views_blueprint.route('/get_tasks_for_dragging', methods=['GET'])
def get_tasks_for_dragging_route():
    engagement_id = request.args.get('engagement_id')
    if not engagement_id:
        return jsonify({"success": False, "message": "Engagement ID is required."})

    try:
        tasks = get_tasks_for_dragging(app.db, engagement_id)
        print(f"Tasks fetched for engagement {engagement_id}: {tasks}")
        return jsonify({"success": True, "tasks": tasks})
    except Exception as e:
        print(f"Error retrieving tasks for dragging: {e}")
        return jsonify({"success": False, "message": str(e)})


@views_blueprint.route('/get_engagement_team_taskhtml', methods=['GET'])
def get_engagement_team_taskhtml_route():
    engagement_id = request.args.get('engagement_id')
    
    if not engagement_id:
        return {"success": False, "message": "Engagement ID is required."}
    
    try:
        # Fetch team members using the updated service function
        team_members = get_engagement_team_for_task(app.db, engagement_id)
        return {"success": True, "team_members": team_members}
    except Exception as e:
        print(f"Error fetching engagement team for task page: {e}")
        return {"success": False, "message": str(e)}

#timesheet submit function
@views_blueprint.route('/submit_timesheet', methods=['POST'])
def submit_timesheet_route():
    data = request.json
    task_id = data['taskId']
    user_id = session['user_id']  # Logged-in user ID
    hours = float(data['hours'])
    date = data['date']

    try:
        result = submit_timesheet(app.db, task_id, user_id, hours, date)
        return jsonify({"success": True, "message": result})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@views_blueprint.route('/review_task', methods=['POST'])
def review_task():
    try:
        data = request.get_json()
        task_id = data['taskId']
        reviewer_id = session['user_id']  # Assuming the reviewer is logged in
        accuracy_mark = int(data['accuracyMark'])

        # Call the service function to review the task
        review_task_and_complete(app.db, task_id, reviewer_id, accuracy_mark)

        return {"success": True, "message": "Task reviewed and completed."}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.route('/update_task_status', methods=['POST'])
def update_task_status():
    try:
        data = request.get_json()
        task_id = data['taskId']
        new_status = data['newStatus']

        # Update the task's status in the database
        app.db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": new_status}})

        return jsonify({"success": True})
    except Exception as e:
        print(f"Error updating task status: {e}")
        return jsonify({"success": False, "message": str(e)})


#Machine Learning for suggestion employee
# @views_blueprint.route('/get_recommended_employees', methods=['POST'])
# def get_recommended_employees():
#     data = request.json
#     industry = data.get("industry", "")
    
#     # Fetch top recommended employees based on industry
#     recommended_employees = recommend_employees(app.db, industry, top_n=3)
    
#     # Format data for frontend
#     recommendations = [
#         {"id": str(emp["_id"]), "name": emp["name"], "photo": emp.get("photo", "default-avatar.png")}
#         for emp in recommended_employees
#     ]
    
#     return jsonify({"success": True, "employees": recommendations})

@views_blueprint.route('/get_recommended_employees_knn', methods=['POST'])
def get_recommended_employees_knn():
    data = request.json
    industry = data.get("industry", "")

    logging.info(f"Received recommendation request for industry: {industry}")

    if not industry:
        logging.warning("Industry is required but not provided.")
        return jsonify({"success": False, "message": "Industry is required."}), 400

    try:
        # Call recommend_employees_knn and wrap the result in jsonify
        response_data = recommend_employees_knn(app.db, industry, top_n=3)
        logging.info("Response data generated: %s", response_data)
        return jsonify(response_data)
    except Exception as e:
        logging.error(f"Error in get_recommended_employees_knn: {e}")
        return jsonify({"success": False, "message": "Server error occurred"}), 500



@views_blueprint.route('/hr')
def hr_page():
    """Render the HR page for setting up employee profiles."""
    return render_template('hr.html')
@views_blueprint.route('/api/pending_users', methods=['GET'])
def api_pending_users():
    """API endpoint to get a list of users with 'Pending Approval' role."""
    return jsonify(get_pending_users(app.db))

@views_blueprint.route('/api/managers', methods=['GET'])
def api_managers():
    """API endpoint to get a list of users with 'Manager' role."""
    return jsonify(get_users_by_role(app.db, "Manager"))

@views_blueprint.route('/api/partners', methods=['GET'])
def api_partners():
    """API endpoint to get a list of users with 'Partner' role."""
    return jsonify(get_users_by_role(app.db, "Partner"))

@views_blueprint.route('/api/user/<user_id>', methods=['GET'])
def api_get_user(user_id):
    """API endpoint to get user data by ID."""
    user = get_user_by_id(app.db, user_id)
    if user:
        return jsonify(user)
    return jsonify({"error": "User not found"}), 404

@views_blueprint.route('/api/update_user', methods=['POST'])
def api_update_user():
    """API endpoint to update user profile."""
    data = request.form.to_dict()
    photo = request.files.get('photo')
    result = update_user_profile(app.db, data, photo)
    return jsonify(result)



@views_blueprint.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('auth.login'))

    user_role = session.get('user_role')
    user_id = session.get('user_id')

    try:
        # Fetch engagements and tasks
        engagements = get_engagements(app.db, user_id) or []
        tasks = get_pending_tasks(app.db, user_id) or []

        # Define 30-day period
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        # Fetch general utilization data (no engagement filter)
        general_utilization_data = get_employee_utilization(app.db, start_date=start_date, end_date=end_date)
        print("General Utilization Data:", general_utilization_data)

        # Set default engagement if no engagement ID provided
        engagement_id = request.args.get('engagement_id') or (str(engagements[0]["_id"]) if engagements else None)
        
        if engagement_id:
            print(f"Debug: Using engagement ID: {engagement_id} for engagement-specific data.")
            
            # Call the updated `get_engagement_utilization`
            engagement_utilization_data = get_engagement_utilization(app.db, engagement_id)

            # Ensure keys are present with default values
            engagement_utilization_data = {
                "charged_hours": engagement_utilization_data.get("charged_hours", {}),
                "allocated_hours": engagement_utilization_data.get("allocated_hours", {}),
                "recovery_data": engagement_utilization_data.get("recovery_data", {}),
                "estimated_recovery_rate": engagement_utilization_data.get("estimated_recovery_rate", 0.0),
                "actual_recovery_rate": engagement_utilization_data.get("actual_recovery_rate", 0.0),
                "anomalies": engagement_utilization_data.get("anomalies", []),
                "advice": engagement_utilization_data.get("advice", "No advice available.")
            }

            # Convert `defaultdict` structures to regular dictionaries for JSON compatibility
            engagement_utilization_data["charged_hours"] = {
                employee_id: {
                    "name": details.get("name", "Unknown"),
                    "hours": dict(details.get("hours", {}))  # Convert nested defaultdict to dict
                }
                for employee_id, details in engagement_utilization_data["charged_hours"].items()
            }
            engagement_utilization_data["allocated_hours"] = dict(engagement_utilization_data["allocated_hours"])

            print("Processed Engagement Utilization Data:", engagement_utilization_data)
        else:
            engagement_utilization_data = None
            print("Debug: No engagement ID provided or available.")
            
        return render_template(
            'dashboard.html',
            engagements=engagements,
            tasks=tasks,
            user_role=user_role,
            general_utilization_data=general_utilization_data,
            engagement_utilization_data=engagement_utilization_data,
            logged_in_user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        print(f"Error retrieving dashboard data: {e}")
        flash("There was an error retrieving your dashboard data. Please try again later.", "danger")
        return render_template('dashboard.html', engagements=[], tasks=[], user_role=user_role)


@views_blueprint.route('/get_engagement_data', methods=['GET'])
def get_engagement_data():
    engagement_id = request.args.get('engagement_id')
    if not engagement_id:
        return jsonify({"error": "Engagement ID is required"}), 400

    try:
        engagement_utilization_data = get_engagement_utilization(app.db, engagement_id)
        return jsonify(engagement_utilization_data)
    except Exception as e:
        print(f"Error retrieving data for engagement {engagement_id}: {e}")
        return jsonify({"error": "Failed to retrieve engagement data"}), 500


@app.route('/send_prompt', methods=['POST'])
def send_prompt():
    data = request.json
    prompt = data.get('prompt')
    
    # Use the service to interact with ChatGPT
    response_text = send_prompt_to_chatgpt(prompt)
    
    if response_text:
        return jsonify({"success": True, "response": response_text})
    else:
        return jsonify({"success": False, "message": "Error interacting with ChatGPT"}), 500

@app.route('/send_chat', methods=['POST'])
def send_chat():
    data = request.json
    message = data.get('message')
    
    # Use the service to interact with ChatGPT and LangChain
    response_text = send_chat_to_chatgpt(message, app.db)  # Pass `app.db` to use the database in LangChain
    
    if response_text:
        return jsonify({"success": True, "response": str(response_text)})
    else:
        return jsonify({"success": False, "message": "Error interacting with ChatGPT"}), 500
