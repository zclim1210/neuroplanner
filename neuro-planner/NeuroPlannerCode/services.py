from collections import defaultdict
from bson import ObjectId
from datetime import datetime, timedelta
from flask import jsonify, render_template_string, send_file, session, url_for
from markupsafe import Markup
import pytz, uuid, os, openai
from werkzeug.utils import secure_filename
import logging
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from io import BytesIO
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from surprise import Dataset, Reader, KNNBasic
import pandas as pd
from pymongo import DESCENDING
from flask_bcrypt import Bcrypt
from collections import defaultdict
from sklearn.ensemble import IsolationForest
import numpy as np
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.tools import Tool
from langchain.agents import initialize_agent, Tool
from markupsafe import Markup
import re
from difflib import get_close_matches
from bson.errors import InvalidId
from collections import deque


# Load environment variables from .env file
load_dotenv()

# Set the API key for OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

#logging.basicConfig(level=logging.DEBUG)
UPLOAD_FOLDER = 'NeuroPlannerCode/static/uploads'  # Specify your upload folder
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'pptx', 'docx', 'xlsx'}

def get_engagements(db, user_id):
    try:
        user_id = ObjectId(user_id)
        print(f"Fetching engagements for user ID: {user_id}")

        # Query engagements excluding those with status 'closed'
        engagements = list(db.engagements.find({
            "$or": [
                {"partnerInCharge": user_id},
                {"manager": user_id},
                {"members": user_id}
            ],
            "status": {"$ne": "Closed"}
        }))
        
        for engagement in engagements:
            if isinstance(engagement['estEndDate'], datetime):
                engagement['formatted_endDate'] = engagement['estEndDate'].strftime('%d %B, %Y, %I:%M%p %Z')
            else:
                engagement['formatted_endDate'] = engagement['estEndDate']
            
            # Fetch tasks related to the engagement
            tasks = list(db.tasks.find({"engagementId": engagement['_id']}))
            total_tasks = len(tasks)
            completed_tasks = sum(1 for task in tasks if task['status'] == 'Completed')
            remaining_tasks = total_tasks - completed_tasks

            engagement['total_tasks'] = total_tasks
            engagement['complete_tasks'] = completed_tasks
            engagement['tasks_remaining'] = remaining_tasks
            engagement['task_completion_percentage'] = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0

            # Fetch member details
            member_ids = engagement['members']
            if not isinstance(member_ids, list):
                member_ids = [member_ids]
            engagement['member_details'] = list(db.users.find({"_id": {"$in": member_ids}}, {"_id": 1, "name": 1, "photo": 1}))

            # Fetch manager details
            manager_id = engagement['manager']
            engagement['manager_details'] = db.users.find_one({"_id": ObjectId(manager_id)}, {"_id": 1, "name": 1, "photo": 1})

            # Fetch partner details and color
            partner_id = engagement['partnerInCharge']
            partner_details = db.users.find_one({"_id": ObjectId(partner_id)}, {"_id": 1, "name": 1, "photo": 1, "color": 1})
            engagement['partner_color'] = partner_details.get('color', '#000000') if partner_details else '#000000'

        print(f"Final engagements: {engagements}")
        return engagements
    except Exception as e:
        print(f"Error in get_engagements: {e}")
        raise


def get_pending_tasks(db, user_id):
    try:
        assigned_to = ObjectId(user_id)
        print(f"Fetching pending tasks for user ID: {assigned_to}")
        
        tasks = list(db.tasks.find({
            "assignedTo": assigned_to,
            "status": "Pending"
        }))
        
        for task in tasks:
            print(f"Task found: {task}")
            task['formatted_dueDate'] = task['dueDate'].strftime('%d %B, %Y, %I:%M%p %Z')
            # Fetch engagement name
            engagement = db.engagements.find_one({"_id": task['engagementId']}, {"clientName": 1})
            task['engagement_name'] = engagement['clientName'] if engagement else "Unknown Engagement"
        
        print(f"Final pending tasks: {tasks}")
        return tasks
    except Exception as e:
        print(f"Error in get_pending_tasks: {e}")
        raise


def complete_task(db, task_id, user_id, hours, minutes):
    try:
        task = db.tasks.find_one({"_id": ObjectId(task_id)})
        if not task:
            raise Exception("Task not found.")

        time_charge = hours * 60 + minutes
        db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {
                "status": "Completed",
                "timeCharge": time_charge,
                "signedOffBy": ObjectId(user_id),
                "signedOffDate": datetime.utcnow()
            }}
        )

        return "Task completed successfully."
    except Exception as e:
        print(f"Error in complete_task: {e}")
        raise


def add_task(db, task_data):
    try:
        print("Received task data:", task_data)  # Debug log
        task = {
            "description": task_data['description'],
            "engagementId": ObjectId(task_data['engagementId']),  # Engagement preset
            "assignedTo": ObjectId(task_data['assignedTo']),
            "dueDate": datetime.strptime(task_data['dueDate'], '%Y-%m-%d'),
            "timeEstimate": int(task_data['timeEstimate']), 
            "status": "To Start",  # Default status
            "priority": task_data['priority'],  # Priority selected by user
            "difficulty": int(task_data['difficulty'])  # Difficulty level
        }
        db.tasks.insert_one(task)
        return "Task added successfully."
    except Exception as e:
        print(f"Error adding task: {e}")  # Debug log
        raise Exception("There was an error adding the task.")




SGT = pytz.timezone('Asia/Singapore')

def get_scheduler_data(db, view, date_range):
    print(f"get_scheduler_data called with view: {view}, date_range: {date_range}")
    start_date, end_date = parse_date_range(date_range)

    if view == 'week' and not date_range:
        today = datetime.now(SGT)
        start_date = today - timedelta(days=today.weekday())  # Monday of the current week
        end_date = start_date + timedelta(days=6)  # Sunday of the current week

    print(f"Calculated start_date: {start_date}, end_date: {end_date}")

    employees = list(db.users.find({"role": {"$ne": "Human Resources"}}, {"_id": 1, "name": 1, "photo": 1,"role": 1}))
    print("Employees fetched from DB:")
    for emp in employees:
        print(emp)

    schedule_entries = list(db.scheduler.find({
        "date": {"$gte": start_date, "$lte": end_date}
    }))
    print("Schedule entries fetched from DB:")
    for entry in schedule_entries:
        print(entry)

    schedule_data = {str(emp['_id']): {"name": emp['name'], "photo": emp['photo'],"role": emp['role'], "_id": str(emp['_id']), "schedule": []} for emp in employees}
    print("Initialized schedule data:", schedule_data)

    for entry in schedule_entries:
        emp_id = str(entry['employmentId'])
        print(f"Processing schedule entry for employee ID: {emp_id}")
        if emp_id in schedule_data:
            engagement = db.engagements.find_one({"_id": entry['engagementId']}, {"clientName": 1, "partnerInCharge": 1})
            if engagement:
                engagement_name = engagement['clientName']
                partner_id = engagement['partnerInCharge']
                partner = db.users.find_one({"_id": partner_id}, {"photo": 1, "name": 1, "color": 1})
                if partner:
                    partner_photo = partner['photo']
                    partner_name = partner['name']
                    partner_color = partner.get('color', '#ccc')  # Use the correct key to fetch the color
                    print(f"Partner details - Name: {partner_name}, Photo: {partner_photo}, Color: {partner_color}")
                else:
                    partner_photo = None
                    partner_name = None
                    partner_color = '#ccc'  # Default color if partner not found
                    print("Partner not found, using default values")
                
                entry_date = entry['date'].replace(tzinfo=SGT).isoformat()
                schedule_data[emp_id]['schedule'].append({
                    "date": entry_date,
                    "engagementName": engagement_name,
                    "partnerPhoto": partner_photo,
                    "partnerName": partner_name,
                    "partnerColor": partner_color,
                    "employeeId": emp_id,  # Include employee ID
                    "engagementId": str(entry['engagementId'])  # Include engagement ID
                })
                print(f"Added schedule for {emp_id}: {engagement_name} on {entry_date} with partner photo {partner_photo}, name {partner_name}, and color {partner_color}")
            else:
                print(f"No engagement found for engagement ID: {entry['engagementId']}")
        else:
            print(f"Employee ID {emp_id} not found in schedule data")

    if view == 'week':
        for emp in schedule_data.values():
            emp['schedule'] = fill_week_schedule(emp['schedule'], start_date)

    days_of_week = [
        {"name": day, "date": (start_date + timedelta(days=i)).strftime('%d'), "is_today": (start_date + timedelta(days=i)).date() == datetime.now(SGT).date()}
        for i, day in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])
    ]

    result = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "days": days_of_week,
        "schedule": list(schedule_data.values())
    }

    print("Final scheduler data:", result)
    return result

def parse_date_range(date_range):
    if date_range:
        start_str, end_str = date_range.split(' to ')
        start_date = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=SGT)
        end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(tzinfo=SGT)
        print(f"Parsed date range - start: {start_date}, end: {end_date}")
        return start_date, end_date
    else:
        today = datetime.now(SGT)
        start_date = today - timedelta(days=today.weekday())  # Monday of the current week
        end_date = start_date + timedelta(days=6)  # Sunday of the current week
        print(f"Default date range - start: {start_date}, end: {end_date}")
        return start_date, end_date

def fill_week_schedule(schedule, start_date):
    week_schedule = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        engagement = next((s['engagementName'] for s in schedule if datetime.fromisoformat(s['date']) == day), "")
        partnerPhoto = next((s['partnerPhoto'] for s in schedule if datetime.fromisoformat(s['date']) == day), None)
        partnerName = next((s['partnerName'] for s in schedule if datetime.fromisoformat(s['date']) == day), None)
        partnerColor = next((s['partnerColor'] for s in schedule if datetime.fromisoformat(s['date']) == day), '#ccc')  # Default color
        employeeId = next((s['employeeId'] for s in schedule if datetime.fromisoformat(s['date']) == day), None)
        engagementId = next((s['engagementId'] for s in schedule if datetime.fromisoformat(s['date']) == day), None)
        
        week_schedule.append({
            "date": day.strftime('%Y-%m-%d'),
            "engagementName": engagement,
            "partnerPhoto": partnerPhoto,
            "partnerName": partnerName,
            "partnerColor": partnerColor,
            "employeeId": employeeId,
            "engagementId": engagementId
        })
        print(f"Week schedule for {day.strftime('%Y-%m-%d')}: {engagement} with partner photo {partnerPhoto}, name {partnerName}, color {partnerColor}, employeeId {employeeId}, engagementId {engagementId}")
    return week_schedule

def amend_schedule(db, user_id, swap_requests):
    try:
        print(f"Received swap requests: {swap_requests}")  # Debug statement
        user = db.users.find_one({"_id": ObjectId(user_id)})
        print(f"User found: {user}")  # Debug statement

        if user['role'] != 'Partner':
            print("User is not a Partner")  # Debug statement
            return {"success": False, "message": "Only partners can amend the schedule"}

        for request in swap_requests['swap_requests']:
            print(f"Handling swap request: {request}")  # Debug statement

            from_date = request['from_date']
            to_date = request['to_date']
            from_employee_id = request['from_employee_id']
            to_employee_id = request['to_employee_id']
            engagement_id = request['engagement_id']

            print(f"Parsed request data - from_date: {from_date}, to_date: {to_date}, from_employee_id: {from_employee_id}, to_employee_id: {to_employee_id}, engagement_id: {engagement_id}")  # Debug statement

            # Manually set the date format to include T00:00:00.000+00:00
            from_date_str = f"{from_date}T00:00:00.000+00:00"
            to_date_str = f"{to_date}T00:00:00.000+00:00"

            # Convert date strings to datetime objects
            from_date = datetime.fromisoformat(from_date_str)
            to_date = datetime.fromisoformat(to_date_str)

            print(f"Converted dates - from_date: {from_date}, to_date: {to_date}")  # Debug statement

            # Ensure that the employee_id and engagement_id are ObjectId
            if not ObjectId.is_valid(from_employee_id) or not ObjectId.is_valid(to_employee_id) or not ObjectId.is_valid(engagement_id):
                raise ValueError(f"Invalid ObjectId: from_employee_id={from_employee_id}, to_employee_id={to_employee_id}, engagement_id={engagement_id}")

            from_employee_id = ObjectId(from_employee_id)
            to_employee_id = ObjectId(to_employee_id)
            engagement_id = ObjectId(engagement_id)

            print(f"Converted to ObjectId - from_employee_id: {from_employee_id}, to_employee_id: {to_employee_id}, engagement_id: {engagement_id}")  # Debug statement

            # Check if the partner is in charge of the engagement for the given dates
            engagement = db.engagements.find_one({"_id": engagement_id})
            print(f"Engagement found: {engagement}")  # Debug statement

            if not engagement:
                print("Engagement not found")  # Debug statement
                return {"success": False, "message": "Engagement not found"}

            if engagement['partnerInCharge'] == user['_id']:
                print("User is in charge of the engagement")  # Debug statement

                # Find the schedule entry to modify
                print(f"Searching for schedule entry with employmentId: {from_employee_id}, engagementId: {engagement_id}, date: {from_date}")
                existing_schedule = db.scheduler.find_one({"employmentId": from_employee_id, "engagementId": engagement_id, "date": from_date})
                
                if not existing_schedule:
                    print("Schedule entry not found for the given date")
                    return {"success": False, "message": "Schedule entry not found for the given date"}

                print(f"Existing schedule found: {existing_schedule}")

                # Update the schedule entry with the new employee ID and potentially new date
                update_data = {"employmentId": to_employee_id}
                if from_date != to_date:
                    update_data["date"] = to_date

                update_result = db.scheduler.update_one(
                    {"_id": existing_schedule['_id']},
                    {"$set": update_data}
                )

                if update_result.matched_count == 1:
                    print(f"Schedule entry updated with new data: {update_data}")
                else:
                    print(f"Failed to update schedule entry with new data: {update_data}")
                    return {"success": False, "message": "Failed to update schedule entry"}
            else:
                print("User is not in charge of the engagement, sending approval request")  # Debug statement
                # Fetch employee details to include in the message
                from_employee = db.users.find_one({"_id": from_employee_id}, {"name": 1})
                to_employee = db.users.find_one({"_id": to_employee_id}, {"name": 1})

                partner_in_charge = db.users.find_one({"_id": engagement['partnerInCharge']})
                print(f"Partner in charge found: {partner_in_charge}")  # Debug statement

                notification = {
                    "type":"swap_approval",
                    "from": user_id,
                    "to": partner_in_charge['_id'],
                    "message": f"{user['name']} requests to amend the schedule from {from_date} to {to_date} for employee {from_employee['name']} to {to_employee['name']}",
                    "status": "pending",
                    "created_at": datetime.now(),
                    "employee_id": from_employee_id,  # Added to keep track of the employee
                    "to_employee_id": to_employee_id,
                    "from_date": from_date,
                    "to_date": to_date
                }
                result = db.notifications.insert_one(notification)
                print(f"Notification inserted with ID: {result.inserted_id}")  # Debug statement
                return {"success": True, "message": "Approval request sent"}

        return {"success": True, "message": "All schedule amendments processed successfully"}

    except Exception as e:
        print(f"Error in amend_schedule: {e}")
        return {"success": False, "message": str(e)}
    
def approve_notification(db, notification_id):
    try:
        notification = db.notifications.find_one({"_id": ObjectId(notification_id)})
        if not notification:
            return {"success": False, "message": "Notification not found"}

        # Update the schedule entry with the new date and employee ID
        db.scheduler.update_one(
            {"employmentId": ObjectId(notification['employee_id']), "date": notification['from_date']},
            {"$set": {"employmentId": ObjectId(notification['to_employee_id']), "date": notification['to_date']}}
        )
        db.notifications.update_one({"_id": ObjectId(notification_id)}, {"$set": {"status": "approved"}})
        return {"success": True, "message": "Schedule approved and updated"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def decline_notification(db, notification_id):
    try:
        db.notifications.update_one({"_id": ObjectId(notification_id)}, {"$set": {"status": "declined"}})
        return {"success": True, "message": "Schedule decline request updated"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def create_engagement(db, data, user_id):
    try:
        # Parse date fields from the form data
        audit_year = data.get("auditYear")
        est_start_date = data.get("estStartDate")
        est_end_date = data.get("estEndDate")

        if not audit_year or not est_start_date or not est_end_date:
            raise ValueError("Date fields must not be empty")

        # Convert date strings to datetime objects
        audit_year = datetime.strptime(audit_year, "%Y-%m-%d")
        est_start_date = datetime.strptime(est_start_date, "%Y-%m-%d")
        est_end_date = datetime.strptime(est_end_date, "%Y-%m-%d")

        # Handle member_ids correctly
        member_ids = data.get("member_ids[]")
        if isinstance(member_ids, str):
            member_ids = [member_ids]
        elif not isinstance(member_ids, list):
            member_ids = list(member_ids)

        # Create the engagement document
        engagement = {
            "clientName": data.get("clientName"),
            "auditYear": audit_year,
            "description": data.get("description"),
            "budget": float(data.get("budget")),
            "partnerInCharge": ObjectId(user_id),
            "manager": ObjectId(data.get("manager_id")),
            "members": [ObjectId(member_id) for member_id in member_ids],
            "status": "To Start",
            "location": data.get("location"),
            "industry": data.get("industry") if data.get("industry") != "Other" else data.get("industry_other"),
            "estStartDate": est_start_date,
            "estEndDate": est_end_date,
            "photo": data.get("photo", "default.jpg")
        }

        # Insert the engagement document into the database
        db.engagements.insert_one(engagement)
        return "Engagement created successfully."
    except Exception as e:
        print(f"Error in create_engagement: {e}")
        raise

def get_engagements_for_user(db, user_id, role):
    try:
        if role not in ['Partner', 'Manager']:
            print(f"User role {role} not authorized to get engagements.")
            return []

        user_id = ObjectId(user_id)
        print(f"Fetching engagements for user ID: {user_id}")
        engagements = list(db.engagements.find({"partnerInCharge": user_id}, {"_id": 1, "clientName": 1}))
        engagements_list = [{"id": str(e["_id"]), "name": e["clientName"]} for e in engagements]
        print(f"Engagements fetched: {engagements_list}")
        return engagements_list
    except Exception as e:
        print(f"Error in get_engagements_for_user: {e}")
        return []

def get_staff_by_level(db, level):
    try:
        print(f"Fetching staff for level: {level}")
        staff = list(db.users.find({"role": level}, {"_id": 1, "name": 1, "photo": 1}))
        staff_list = [{"id": str(s["_id"]), "name": s["name"], "photo": s["photo"]} for s in staff]
        print(f"Staff fetched: {staff_list}")
        return staff_list
    except Exception as e:
        print(f"Error in get_staff_by_level: {e}")
        return []

def plot_calendar(db, user_id, role, plot_data):
    try:
        if role not in ['Partner', 'Manager']:
            print(f"User role {role} not authorized to plot calendar.")
            return {"success": False, "message": "Unauthorized"}

        engagement_id = plot_data['engagement']
        staff_id = plot_data['staff']
        section = plot_data['section']
        dates = plot_data['dates']  # Corrected key

        print(f"Plotting calendar for engagement ID: {engagement_id}, staff ID: {staff_id}, section: {section}, dates: {dates}")

        for date_str in dates:
            # Manually set the date format to include T00:00:00.000+00:00
            date_str_with_time = f"{date_str}T00:00:00.000+00:00"

            # Convert date string to datetime object with UTC offset
            date = datetime.fromisoformat(date_str_with_time)
            print(f"Processing date: {date}")

            existing_plot = db.scheduler.find_one({"date": date, "employmentId": ObjectId(staff_id)})
            if existing_plot:
                print(f"Existing plot found: {existing_plot}")
                partner_in_charge = db.engagements.find_one({"_id": existing_plot['engagementId']}, {"partnerInCharge": 1})
                if partner_in_charge and partner_in_charge['partnerInCharge'] != ObjectId(user_id):
                    print(f"Conflict with partner in charge: {partner_in_charge['partnerInCharge']}")
                    send_plot_approval_request(db, partner_in_charge['partnerInCharge'], existing_plot, user_id, staff_id, date, engagement_id, section)
                    continue
            
            db.scheduler.insert_one({
                "employmentId": ObjectId(staff_id),
                "engagementId": ObjectId(engagement_id),
                "section": section,
                "date": date
            })
            print(f"Plot added: staff ID {staff_id}, engagement ID {engagement_id}, section {section}, date {date}")

        return {"success": True}
    except Exception as e:
        print(f"Error in plot_calendar: {e}")
        return {"success": False, "message": str(e)}

def send_plot_approval_request(db, partner_in_charge, existing_plot, requester_id, to_employee_id, to_date, engagement_id, section):
    try:
        print(f"Sending plot approval request to partner {partner_in_charge} for existing plot {existing_plot['_id']}")
        requester = db.users.find_one({"_id": ObjectId(requester_id)}, {"name": 1})
        to_employee = db.users.find_one({"_id": ObjectId(to_employee_id)}, {"name": 1})
        engagement = db.engagements.find_one({"_id": ObjectId(engagement_id)}, {"clientName": 1})
        
        message = f"{requester['name']} requests to swap the calendar for {engagement['clientName']} engagement on {to_date.strftime('%Y-%m-%d')} for employee {to_employee['name']}."

        notification_data = {
            "type": "plot_approval",
            "to": partner_in_charge,
            "from": requester_id,
            "message": message,
            "existing_plot": {
                "employmentId": existing_plot['employmentId'],
                "engagementId": existing_plot['engagementId'],
                "date": existing_plot['date']
            },
            "to_employee_id": to_employee_id,
            "to_date": to_date,
            "engagement_id": engagement_id,
            "status": "pending",
            "created_at": datetime.now()
        }
        
        db.notifications.insert_one(notification_data)
        print("Plot approval request sent")
    except Exception as e:
        print(f"Error in send_plot_approval_request: {e}")


def approve_plot_notification(db, notification_id):
    try:
        notification = db.notifications.find_one({"_id": ObjectId(notification_id)})
        if not notification:
            print(f"Notification ID {notification_id} not found")
            return {"success": False, "message": "Notification not found"}

        print(f"Approving notification: {notification}")

        db.scheduler.update_one(
            {"employmentId": ObjectId(notification['existing_plot']['employmentId']), "date": notification['existing_plot']['date']},
            {"$set": {"employmentId": ObjectId(notification['to_employee_id']), "date": notification['to_date'], "engagementId": ObjectId(notification['engagement_id'])}}
        )
        db.notifications.update_one({"_id": ObjectId(notification_id)}, {"$set": {"status": "approved"}})
        print("Notification approved and schedule updated")
        return {"success": True, "message": "Schedule approved and updated"}
    except Exception as e:
        print(f"Error in approve_plot_notification: {e}")
        return {"success": False, "message": str(e)}

def decline_plot_notification(db, notification_id):
    try:
        print(f"Declining notification ID: {notification_id}")
        db.notifications.update_one({"_id": ObjectId(notification_id)}, {"$set": {"status": "declined"}})
        print("Notification declined")
        return {"success": True, "message": "Schedule decline request updated"}
    except Exception as e:
        print(f"Error in decline_plot_notification: {e}")
        return {"success": False, "message": str(e)}
    

def delete_schedule(db, employment_id, date, engagement_id):
    try:
        db.scheduler.delete_one({
            "employmentId": ObjectId(employment_id),
            "date": datetime.fromisoformat(date),
            "engagementId": ObjectId(engagement_id)
        })
        return {"success": True, "message": "Schedule entry deleted successfully"}
    except Exception as e:
        print(f"Error in delete_schedule: {e}")
        return {"success": False, "message": str(e)}

def book_desk(db, desk_id, user_id, start_time, end_time):
    try:
        db.desk_booking.insert_one({
            "desk_id": str(desk_id),
            "user_id": ObjectId(user_id),
            "start_time": datetime.fromisoformat(start_time),
            "end_time": datetime.fromisoformat(end_time),
            "status": "booked",
            "photo_url": db.users.find_one({"_id": ObjectId(user_id)})["photo"]
        })
        return {"success": True, "message": "Desk booked successfully"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def edit_booking_in_db(db, desk_id, user_id, start_time, end_time):
    try:
        db.desk_booking.update_one(
            {"desk_id": desk_id, "user_id": ObjectId(user_id)},
            {"$set": {
                "start_time": datetime.fromisoformat(start_time),
                "end_time": datetime.fromisoformat(end_time)
            }}
        )
        return {"success": True, "message": "Booking updated successfully"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def cancel_booking_in_db(db, desk_id, user_id):
    try:
        db.desk_booking.delete_one({"desk_id": desk_id, "user_id": ObjectId(user_id)})
        return {"success": True, "message": "Booking canceled successfully"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def get_desks(db, date):
    try:
        print(f"Fetching desks for date: {date}")
        
        # Normalize the date to the start of the day in Singapore timezone
        date_start = date.astimezone(SGT).replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        desks = [
            { "id": "Desk 1", "x": 212, "y": 90 },
            { "id": "Desk 2", "x": 213, "y": 288 },
            { "id": "Desk 3", "x": 210, "y": 630 },
            { "id": "Desk 4", "x": 210, "y": 720 },
            { "id": "Desk 5", "x": 270, "y": 630 },
            { "id": "Desk 6", "x": 270, "y": 720 },
            # Add more desks
        ]
        print(f"Initial desks: {desks}")

        # Find bookings for the specified date
        bookings = list(db.desk_booking.find({
            "start_time": {"$gte": date_start, "$lt": date_end},
            "status": "booked"
        }))
        print(f"Bookings found: {bookings}")

        for booking in bookings:
            for desk in desks:
                if desk['id'] == booking['desk_id']:
                    user = db.users.find_one({"_id": booking['user_id']}, {"name": 1, "photo": 1})
                    print(f"User found for booking: {user}")
                    desk['booked'] = True
                    desk['user_id'] = str(booking['user_id'])
                    desk['user_name'] = user['name']
                    desk['photo_url'] = url_for('static', filename=f'images/{user["photo"]}')
                    desk['bookedTill'] = booking['end_time'].astimezone(SGT).strftime('%I:%M %p')
                    break

        print(f"Final desks data: {desks}")
        return {"desks": desks}
    except Exception as e:
        print(f"Error in get_desks: {e}")
        return {"desks": [], "error": str(e)}
    
def get_leave_data(db, user_id):
    user_object_id = ObjectId(user_id)
    print("Looking for leave data with user ObjectId:", user_object_id)
    leave_data = db.leave_balance.find_one({"user": user_object_id})
    print("Fetched Leave Data:", leave_data)  # Debug statement
    return leave_data

def submit_leave_request(db, user_id, leave_type, start_date, end_date, about, attachments):
    try:
        print("Starting submit_leave_request function")
        print(f"User ID: {user_id}, Leave Type: {leave_type}, Start Date: {start_date}, End Date: {end_date}, About: {about}")

        user_id = ObjectId(user_id)
        start_date_str = f"{start_date}T00:00:00.000+00:00"
        end_date_str = f"{end_date}T00:00:00.000+00:00"
        start_date = datetime.fromisoformat(start_date_str.replace('+00:00', ''))
        end_date = datetime.fromisoformat(end_date_str.replace('+00:00', ''))

        print(f"Parsed Dates - Start Date: {start_date}, End Date: {end_date}")

        leave_request = {
            "user_id": user_id,
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "about": about,
            "attachments": [],
            "status": "Pending",
            "requested_at": datetime.utcnow()
        }

        # Save attachments
        for attachment in attachments:
            print(f"Processing attachment: {attachment.filename}")
            filename = attachment.filename
            filepath = f'NeuroPlannerCode/static/uploads/{filename}'
            attachment.save(filepath)
            leave_request["attachments"].append(filepath)
            print(f"Saved attachment: {filepath}")

        print(f"Final leave request data: {leave_request}")

        db.leave_application.insert_one(leave_request)

        user = db.users.find_one({"_id": user_id})
        if user and user.get('role') == 'Partner':
            print("User is a Partner, auto-approving leave request")
            approve_leave_request(db, str(leave_request["_id"]), str(user_id))
        else:
            print("User is not a Partner, sending approval notification")
            send_approval_notification(db, leave_request)

        return {"success": True, "message": "Leave request submitted successfully!"}
    except Exception as e:
        print(f"Error in submit_leave_request: {str(e)}")
        return {"success": False, "message": str(e)}

def update_leave_balance(db, user_id, leave_type, days):
    try:
        user_id = ObjectId(user_id)
        leave_balance = db.leave_balance.find_one({"user": user_id})
        
        if not leave_balance:
            return {"success": False, "message": "Leave balance not found."}

        leave_balance[leave_type] -= days
        leave_balance['balance'] -= days
        leave_balance['usedLeave'] += days
        db.leave_balance.update_one({"user": user_id}, {"$set": leave_balance})
        return {"success": True, "message": "Leave balance updated successfully."}
    except Exception as e:
        return {"success": False, "message": str(e)}

def approve_leave_request(db, leave_id, approver_id):
    try:
        leave_request = db.leave_application.find_one({"_id": ObjectId(leave_id)})
        if not leave_request:
            return {"success": False, "message": "Leave request not found."}

        user_id = leave_request["user_id"]
        leave_type = leave_request["leave_type"]
        start_date = leave_request["start_date"]
        end_date = leave_request["end_date"]
        days = (end_date - start_date).days + 1

        db.leave_application.update_one({"_id": ObjectId(leave_id)}, {"$set": {"status": "Approved", "approved_by": ObjectId(approver_id), "approved_at": datetime.utcnow()}})

        update_leave_balance(db, user_id, leave_type, days)
        # Update the corresponding notification to 'approved'
        db.notifications.update_one(
            {"leave_request_id": ObjectId(leave_id)},
            {"$set": {"status": "approved"}}
        )

        return {"success": True, "message": "Leave request approved successfully."}
    except Exception as e:
        return {"success": False, "message": str(e)}

def decline_leave_request(db, leave_id, approver_id):
    try:
        leave_request = db.leave_application.find_one({"_id": ObjectId(leave_id)})
        if not leave_request:
            return {"success": False, "message": "Leave request not found."}

        db.leave_application.update_one({"_id": ObjectId(leave_id)}, {"$set": {"status": "Declined", "declined_by": ObjectId(approver_id), "declined_at": datetime.utcnow()}})
        # Update the corresponding notification to 'declined'
        db.notifications.update_one(
            {"leave_request_id": ObjectId(leave_id)},
            {"$set": {"status": "declined"}}
        )

        return {"success": True, "message": "Leave request declined successfully."}
    except Exception as e:
        return {"success": False, "message": str(e)}

def send_approval_notification(db, leave_request):
    try:
        user = db.users.find_one({"_id": leave_request["user_id"]})
        if not user:
            raise ValueError("User not found")

        manager_id = user.get("lineManager")
        if not manager_id:
            raise ValueError("Line manager not found for the user")

        manager = db.users.find_one({"_id": manager_id})
        if not manager:
            raise ValueError("Line manager record not found in the database")

        notification = {
            "type": "leave_approval",
            "to": manager["_id"],
            "from": leave_request["user_id"],
            "message": f"{user['name']} has requested leave from {leave_request['start_date'].strftime('%Y-%m-%d')} to {leave_request['end_date'].strftime('%Y-%m-%d')}.",
            "status": "pending",
            "leave_request_id": leave_request["_id"],
            "created_at": datetime.utcnow()
        }

        db.notifications.insert_one(notification)
        print("Approval notification sent")
    except Exception as e:
        print(f"Error in send_approval_notification: {str(e)}")

def cancel_leave(db, leave_id, user_id):
    try:
        leave_request = db.leave_application.find_one({"_id": ObjectId(leave_id), "user_id": ObjectId(user_id)})
        if not leave_request:
            return {"success": False, "message": "Leave request not found"}

        leave_type = leave_request['leave_type']
        days = (leave_request['end_date'] - leave_request['start_date']).days + 1

        db.leave_application.delete_one({"_id": ObjectId(leave_id)})

        if leave_request['status'] != 'Pending':
            leave_balance = db.leave_balance.find_one({"user": ObjectId(user_id)})
            if leave_balance:
                leave_balance[leave_type] += days
                leave_balance['balance'] += days
                leave_balance['usedLeave'] -= days
                db.leave_balance.update_one({"user": ObjectId(user_id)}, {"$set": leave_balance})

        return {"success": True, "message": "Leave cancelled successfully"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def modify_leave(db, leave_id, user_id, leave_type, start_date, end_date, about, attachments):
    try:
        print(f"Modify Leave: Attempting to update leave request with ID {leave_id}")
        leave_request = db.leave_application.find_one({"_id": ObjectId(leave_id), "user_id": ObjectId(user_id)})
        if not leave_request:
            print(f"Modify Leave: No leave request found with ID {leave_id} for user {user_id}")
            return {"success": False, "message": "Leave request not found"}

        if leave_request['status'] != 'Pending':
            print(f"Modify Leave: Cannot modify leave request with status {leave_request['status']}")
            return {"success": False, "message": "Only pending leave requests can be modified"}

        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')

        leave_request['leave_type'] = leave_type
        leave_request['start_date'] = start_date
        leave_request['end_date'] = end_date
        leave_request['about'] = about

        # Handle attachments
        leave_request['attachments'] = []
        for attachment in attachments:
            filename = attachment.filename
            filepath = f'NeuroPlannerCode/static/uploads/{filename}'
            attachment.save(filepath)
            leave_request['attachments'].append(filepath)

        result = db.leave_application.update_one({"_id": ObjectId(leave_id)}, {"$set": leave_request})
        if result.modified_count > 0:
            print(f"Modify Leave: Leave request with ID {leave_id} successfully updated")
            # Update the corresponding notification
            notification = db.notifications.find_one({"leave_request_id": ObjectId(leave_id)})
            if notification:
                user = db.users.find_one({"_id": leave_request["user_id"]})
                if not user:
                    raise ValueError("User not found")
                manager_id = user.get("lineManager")
                if not manager_id:
                    raise ValueError("Line manager not found for the user")
                manager = db.users.find_one({"_id": manager_id})
                if not manager:
                    raise ValueError("Line manager record not found in the database")
                message = f"{user['name']} has modified their leave request from {leave_request['start_date'].strftime('%Y-%m-%d')} to {leave_request['end_date'].strftime('%Y-%m-%d')}."
                db.notifications.update_one(
                    {"_id": notification['_id']},
                    {"$set": {
                        "message": message,
                        "status": "pending",  # Reset status to pending
                        "created_at": datetime.utcnow()  # Update the timestamp
                    }}
                )
                print(f"Modify Leave: Notification with ID {notification['_id']} successfully updated")
            else:
                print(f"Modify Leave: No notification found for leave request with ID {leave_id}")
        else:
            print(f"Modify Leave: No document found with ID {leave_id} to update")
            return {"success": False, "message": "Leave request not found for update"}

        return {"success": True, "message": "Leave request modified successfully"}
    except Exception as e:
        print(f"Modify Leave: Error updating leave request with ID {leave_id}: {e}")
        return {"success": False, "message": str(e)}
    

def allowed_file(filename):
    print(f"Checking if file {filename} is allowed...")
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_expense_claim(db, user_id, data, file):
    try:
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        attachment_filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(file_path)
            attachment_filename = unique_filename  # Save only the filename

        expense_claim = {
            "user_id": ObjectId(user_id),
            "engagement_id": ObjectId(data.get('engagement_id')),
            "date": datetime.strptime(data.get('date'), '%Y-%m-%d'),
            "category": data.get('category'),
            "amount": float(data.get('amount')),
            "description": data.get('description'),
            "attachment": attachment_filename,
            "status": "Pending",
            "reviewer_id": ObjectId(data.get('reviewer_id')),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        db.expenses_claims.insert_one(expense_claim)


        # Fetch the user's name for the notification
        user = db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1})

        # Create a detailed notification for the reviewer
        notification_message = (
            f"<p>{user['name']} has submitted an expense claim for your approval.</p>"
            f"<p><strong>Category:</strong> {data.get('category')}<br>"
            f"<strong>Amount:</strong> ${float(data.get('amount'))}<br>"
            f"<strong>Date:</strong> {data.get('date')}<br>"
        )

        if attachment_filename:
            file_url = url_for('static', filename=f'uploads/{attachment_filename}', _external=True)
            notification_message += f"<strong>View Document:</strong> <a href='{file_url}' target='_blank'>Click Here</a></p>"

        notification = {
            "type": "expense_approval",
            "to": ObjectId(data.get('reviewer_id')),
            "from": ObjectId(user_id),
            "message": notification_message,
            "status": "pending",
            "expense_claim_id": expense_claim["_id"],
            "created_at": datetime.utcnow()
        }
        db.notifications.insert_one(notification)
        return {"success": True, "message": "Expense recorded successfully!"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def show_all_engagements(db):
    try:
        engagements = list(db.engagements.find({}, {"_id": 1, "clientName": 1, "manager": 1}))  # Fetching manager
        engagements_list = [{"id": str(e["_id"]), "name": e["clientName"], "manager_id": str(e["manager"])} for e in engagements]
        return engagements_list
    except Exception as e:
        print(f"Error in get_all_engagements: {e}")
        return []

def get_all_expense_claims(db, user_id):
    try:
        # Retrieve all expense claims for the logged-in user
        expense_claims = list(db.expenses_claims.find({"user_id": ObjectId(user_id)}).sort("created_at", -1))  # Sort by latest created
        for claim in expense_claims:
            # Convert ObjectId to string and datetime to a readable format
            claim['_id'] = str(claim['_id'])
            claim['user_id'] = str(claim['user_id'])
            claim['engagement_id'] = str(claim['engagement_id'])
            claim['reviewer_id'] = str(claim['reviewer_id'])

            # Fetch and attach the engagement name
            engagement = db.engagements.find_one({"_id": ObjectId(claim['engagement_id'])}, {"clientName": 1})
            claim['engagement_name'] = engagement['clientName'] if engagement else "Unknown Engagement"

            # Fetch and attach the reviewer name
            reviewer = db.users.find_one({"_id": ObjectId(claim['reviewer_id'])}, {"name": 1})
            claim['reviewer_name'] = reviewer['name'] if reviewer else "Unknown Reviewer"

            # Process date and time formatting
            claim['date'] = claim['date'].strftime('%Y-%m-%d')
            claim['created_at'] = claim['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            claim['updated_at'] = claim['updated_at'].strftime('%Y-%m-%d %H:%M:%S')

            if claim['attachment']:
                claim['attachment'] = claim['attachment']

        return expense_claims
    except Exception as e:
        print(f"Error in get_all_expense_claims: {e}")
        return []
    
def delete_expense_claim(db, expense_id):
    try:
        result = db.expenses_claims.delete_one({"_id": ObjectId(expense_id)})
        if result.deleted_count > 0:
            return {"success": True, "message": "Expense claim removed successfully!"}
        else:
            return {"success": False, "message": "Expense claim not found."}
    except Exception as e:
        return {"success": False, "message": str(e)}

def get_expense_claim(db, expense_id):
    try:
        expense_claim = db.expenses_claims.find_one({"_id": ObjectId(expense_id)})
        if expense_claim:
            expense_claim['_id'] = str(expense_claim['_id'])
            expense_claim['user_id'] = str(expense_claim['user_id'])
            expense_claim['engagement_id'] = str(expense_claim['engagement_id'])
            expense_claim['reviewer_id'] = str(expense_claim['reviewer_id'])
            expense_claim['date'] = expense_claim['date'].strftime('%Y-%m-%d')
            return {"success": True, "data": expense_claim}
        else:
            return {"success": False, "message": "Expense claim not found."}
    except Exception as e:
        return {"success": False, "message": str(e)}

def modify_expense_claim(db, expense_id, data, file=None):
    try:
        updated_data = {
            "amount": float(data.get('amount')),
            "date": datetime.strptime(data.get('date'), '%Y-%m-%d'),
            "engagement_id": ObjectId(data.get('engagement_id')),
            "category": data.get('category'),
            "description": data.get('description'),
            "updated_at": datetime.utcnow(),
        }

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(file_path)
            updated_data["attachment"] = unique_filename

        result = db.expenses_claims.update_one(
            {"_id": ObjectId(expense_id)},
            {"$set": updated_data}
        )

        if result.modified_count > 0:
            return {"success": True, "message": "Expense claim updated successfully!"}
        else:
            return {"success": False, "message": "No changes were made to the expense claim."}
    except Exception as e:
        return {"success": False, "message": str(e)}
    

def get_expense_summary(db, user_id):
    try:
        # Total Paid
        total_paid = db.expenses_claims.aggregate([
            {"$match": {"user_id": ObjectId(user_id), "status": "Paid"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ])
        total_paid = list(total_paid)
        print("Total Paid Aggregation Result:", total_paid)
        total_paid = total_paid[0]['total'] if total_paid else 0

        # Approved Expenses
        approved_expense = db.expenses_claims.aggregate([
            {"$match": {"user_id": ObjectId(user_id), "status": "Approved"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ])
        approved_expense = list(approved_expense)
        print("Approved Expense Aggregation Result:", approved_expense)
        approved_expense = approved_expense[0]['total'] if approved_expense else 0

        # Pending Expenses
        pending_expense = db.expenses_claims.aggregate([
            {"$match": {"user_id": ObjectId(user_id), "status": "Pending"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ])
        pending_expense = list(pending_expense)
        print("Pending Expense Aggregation Result:", pending_expense)
        pending_expense = pending_expense[0]['total'] if pending_expense else 0

        # Rejected Expenses
        declined_expense = db.expenses_claims.aggregate([
            {"$match": {"user_id": ObjectId(user_id), "status": "Declined"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ])
        declined_expense = list(declined_expense)
        print("Declined Expense Aggregation Result:", declined_expense)
        declined_expense = declined_expense[0]['total'] if declined_expense else 0

        return {
            "total_paid": total_paid,
            "approved_expense": approved_expense,
            "pending_expense": pending_expense,
            "declined_expense": declined_expense
        }
    except Exception as e:
        print(f"Error in get_expense_summary: {e}")
        return {
            "total_paid": 0,
            "approved_expense": 0,
            "pending_expense": 0,
            "declined_expense": 0
        }
def get_monthly_expenses(db, user_id):
    try:
        pipeline = [
            {
                "$match": {
                    "user_id": ObjectId(user_id),
                    "status": {"$in": ["Paid", "Approved", "Pending"]}
                }
            },
            {
                "$group": {
                    "_id": {
                        "month": {"$month": "$date"},
                        "year": {"$year": "$date"}
                    },
                    "total": {"$sum": "$amount"}
                }
            },
            {
                "$sort": {"_id.year": 1, "_id.month": 1}
            }
        ]

        monthly_expenses = list(db.expenses_claims.aggregate(pipeline))
        
        # Organize data into a dict where keys are months
        expenses_by_month = defaultdict(float)
        for item in monthly_expenses:
            month_year = f"{item['_id']['year']}-{item['_id']['month']:02d}"
            expenses_by_month[month_year] += item['total']
        
        return expenses_by_month

    except Exception as e:
        print(f"Error in get_monthly_expenses: {e}")
        return {}

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from io import BytesIO
from flask import send_file

def generate_expense_report(db, engagement_id):
    try:
        # Fetch engagement details
        engagement = db.engagements.find_one({"_id": ObjectId(engagement_id)})
        if not engagement:
            raise ValueError("Engagement not found.")

        # Fetch expense claims related to the engagement
        expense_claims = list(db.expenses_claims.find({"engagement_id": ObjectId(engagement_id)}))

        # Create a PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        # Add title
        styles = getSampleStyleSheet()
        title = Paragraph("Expense Report", styles['Title'])
        elements.append(title)

        # Add engagement details
        engagement_details = (
            f"<b>Engagement:</b> {engagement['clientName']}<br/>"
            f"<b>Manager:</b> {engagement.get('manager', 'N/A')}<br/>"
            f"<b>Department:</b> {engagement.get('department', 'N/A')}<br/>"
            f"<b>Purpose:</b> {engagement.get('purpose', 'Expense Purpose')}<br/>"
            f"<b>Approved By:</b> {engagement.get('approved_by', 'Manager Name')}<br/>"
            f"<b>Reimbursement Requested:</b> {engagement.get('reimbursement_requested', 'Yes/No')}"
        )
        elements.append(Paragraph(engagement_details, styles['Normal']))

        # Add a blank line
        elements.append(Paragraph("<br/><br/>", styles['Normal']))

        # Create a table of expenses
        data = [['Date', 'Category', 'Description', 'Notes', 'Amount']]
        for claim in expense_claims:
            data.append([
                claim['date'].strftime('%Y-%m-%d'),
                claim['category'],
                claim['description'],
                claim.get('notes', 'N/A'),
                f"${claim['amount']:,.2f}"
            ])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)

        # Add signature lines
        elements.append(Paragraph("<br/><br/><b>Signature:</b> __________________________", styles['Normal']))
        elements.append(Paragraph("<br/><br/><b>Date:</b> __________________________", styles['Normal']))

        # Build PDF
        doc.build(elements)

        # Return PDF as response
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='expense_report.pdf', mimetype='application/pdf')

    except Exception as e:
        return {"success": False, "message": str(e)}


#task.html function
def get_tasks_by_engagement(db, engagement_id):
    try:
        # Convert engagement_id to ObjectId and log
        engagement_id = ObjectId(engagement_id)
        print(f"Fetching tasks for engagement ID: {engagement_id}")

        # Fetch tasks related to the engagement
        tasks = list(db.tasks.find({"engagementId": engagement_id}))

        engagement = db.engagements.find_one({"_id": ObjectId(engagement_id)})

        if engagement:
            engagement_name = engagement.get('clientName', 'Unknown')  # Default to 'Unknown' if not found

        # Process each task to add additional data
        for task in tasks:
            task['engagement_name'] = engagement_name
            # Format dueDate
            if isinstance(task.get('dueDate'), datetime):
                task['formatted_dueDate'] = task['dueDate'].strftime('%d %B, %Y, %I:%M%p')
            else:
                task['formatted_dueDate'] = "No Due Date"

            # Ensure priority is fetched correctly; if missing, default to 'Low'
            task['priority'] = task.get('priority', 'Low')

            # Fetch the 'Assigned To' user details (name and photo)
            assigned_user = db.users.find_one(
                {"_id": ObjectId(task['assignedTo'])},
                {"name": 1, "photo": 1}
            )
            if assigned_user:
                task['user'] = assigned_user['name']
                task['avatar'] = assigned_user.get('photo', '/static/images/default-avatar.png')  # Default avatar if no photo is found
            else:
                task['user'] = "Unknown"
                task['avatar'] = "/static/images/default-avatar.png"  # Fallback to default avatar if user not found

            # Add timeEstimate if available; default to 0 if missing
            task['timeEstimate'] = task.get('timeEstimate', 0)

        print(f"Tasks found: {tasks}")
        return tasks

    except Exception as e:
        print(f"Error in get_tasks_by_engagement: {e}")
        raise

def get_tasks_for_dragging(db, engagement_id):
    try:
        # Convert engagement_id to ObjectId for the query
        engagement_id = ObjectId(engagement_id)

        # Fetch tasks for the engagement
        tasks = list(db.tasks.find({"engagementId": engagement_id}))
         # Fetch engagement name once to apply to all tasks
        engagement = db.engagements.find_one({"_id": engagement_id})
        engagement_name = engagement.get('clientName', 'Unknown') if engagement else 'Unknown'

    
        # Convert all necessary fields to strings
        for task in tasks:
            task['_id'] = str(task['_id'])  # Convert task ID to string
            task['engagementId'] = str(task['engagementId'])
            task['engagement_name'] = engagement_name  # Add engagement name

            # Convert assignedTo ObjectId to name and photo for frontend
            assigned_user = db.users.find_one(
                {"_id": ObjectId(task.get('assignedTo', ''))},
                {"name": 1, "photo": 1}
            )
            task['user'] = assigned_user['name'] if assigned_user else "Unknown"
            task['avatar'] = assigned_user.get('photo', '/static/images/default-avatar.png') if assigned_user else "/static/images/default-avatar.png"
            task['assignedTo'] = str(task.get('assignedTo', 'Unknown'))
            if 'signedOffBy' in task:
                task['signedOffBy'] = str(task['signedOffBy'])
            if 'reviewerId' in task:
                task['reviewerId'] = str(task['reviewerId'])

            # Format dueDate if it's a datetime object
            if 'dueDate' in task and isinstance(task['dueDate'], datetime):
                task['formatted_dueDate'] = task['dueDate'].strftime('%d %B, %Y, %I:%M%p')
            else:
                task['formatted_dueDate'] = "No Due Date"

            # Ensure other fields have default values if not present
            task['priority'] = task.get('priority', 'Low')
            task['timeEstimate'] = task.get('timeEstimate', 0)
            task['comments'] = task.get('comments', 0)
            task['attach'] = task.get('attach', 0)

        # Print for debugging
        print(f"Returning tasks for dragging: {tasks}")
        return tasks

    except Exception as e:
        print(f"Error in get_tasks_for_dragging: {e}")
        raise

def get_engagement_team_for_task(db, engagement_id):
    try:
        # Fetch the engagement document
        engagement = db.engagements.find_one({"_id": ObjectId(engagement_id)})
        if not engagement:
            raise Exception("Engagement not found.")
        
        team_members = []
        
        # Resolve partnerInCharge
        partner = db.users.find_one({"_id": engagement['partnerInCharge']}, {"name": 1, "photo": 1})
        if partner:
            partner['_id'] = str(partner['_id'])  # Convert ObjectId to string
            team_members.append(partner)

        # Resolve manager
        manager = db.users.find_one({"_id": engagement['manager']}, {"name": 1, "photo": 1})
        if manager:
            manager['_id'] = str(manager['_id'])  # Convert ObjectId to string
            team_members.append(manager)

        # Handle members, which can be a single ObjectId or a list
        members_field = engagement.get('members')
        if isinstance(members_field, list):
            # If 'members' is a list of ObjectId
            for member_id in members_field:
                member = db.users.find_one({"_id": member_id}, {"name": 1, "photo": 1})
                if member:
                    member['_id'] = str(member['_id'])  # Convert ObjectId to string
                    team_members.append(member)
        elif isinstance(members_field, ObjectId):
            # If 'members' is a single ObjectId
            member = db.users.find_one({"_id": members_field}, {"name": 1, "photo": 1})
            if member:
                member['_id'] = str(member['_id'])  # Convert ObjectId to string
                team_members.append(member)

        return team_members
    except Exception as e:
        print(f"Error fetching engagement team: {e}")
        raise

#submit timesheet function
def submit_timesheet(db, task_id, user_id, hours, date):
    try:
        # Retrieve the task
        task = db.tasks.find_one({"_id": ObjectId(task_id), "status": "In Progress"})

        if not task:
            raise Exception("Task not found or not in progress.")

        # Ensure the user is assigned to this task
        if task['assignedTo'] != ObjectId(user_id):
            raise Exception("User is not assigned to this task.")

        # Calculate the new actual time (hours added to existing time)
        new_actual_time = task.get('actualTime', 0) + hours

        # Update the task's actual time
        db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"actualTime": new_actual_time}}
        )

        # Insert into the timesheet collection
        timesheet_entry = {
            "employeeId": ObjectId(user_id),
            "taskId": ObjectId(task_id),
            "engagementId": task['engagementId'],
            "date": get_singapore_time(),
            "hours": hours
        }
    
        db.timesheets.insert_one(timesheet_entry)

        return "Timesheet submitted successfully."
    except Exception as e:
        print(f"Error in submit_timesheet: {e}")
        raise


def get_singapore_time():
    """Helper function to get the current time in Singapore timezone."""
    return datetime.now(SGT)

def review_task_and_complete(db, task_id, reviewer_id, accuracy_mark):
    try:
        # Fetch the task from the tasks collection
        task = db.tasks.find_one({"_id": ObjectId(task_id)})

        if not task:
            raise Exception("Task not found.")
        
        # Ensure the task is under 'Review' status
        if task['status'] != 'Review':
            raise Exception("Task is not under review.")
        
        # Get the preparer ID (the employee who prepared the task)
        preparer_id = task['assignedTo']
        
        # Fetch estimated time and actual time, ensure they are floats for calculation
        estimated_time = float(task.get('timeEstimate', 0))
        actual_time = float(task.get('actualTime', 0))
        
        # Calculate performance score using the new formula
        if actual_time > 0:
            time_efficiency = max(0, min(100, ((estimated_time - actual_time) / estimated_time) * 100))
            performance_score = (time_efficiency + float(accuracy_mark)) / 2
        else:
            # When actual_time is 0, time_efficiency is considered perfect (100), relying on accuracy_mark
            time_efficiency = 100
            performance_score = (time_efficiency + float(accuracy_mark)) / 2

        # Calculate task difficulty score
        difficulty_level = int(task.get('difficult', 1))  # Default to 1 if missing

        # Update the task's status to 'Completed'
        db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {
                "status": "Completed",
                "accuracyMark": int(accuracy_mark),
                "reviewerId": ObjectId(reviewer_id),
                "reviewDate": get_singapore_time()  # Use Singapore time for review date
            }}
        )

        # Retrieve the latest KPI record for this employee and engagement
        latest_kpi_cursor = db.kpi.find(
            {"employeeId": ObjectId(preparer_id), "engagementId": ObjectId(task['engagementId'])}
        ).sort("date", DESCENDING).limit(1)

        latest_kpi = next(latest_kpi_cursor, None)  # Use next() to get the document or None if it doesn't exist

        # If a KPI record exists, calculate the new KPI values based on it
        if latest_kpi:
            new_task_count = latest_kpi['taskCompletionCount'] + 1
            new_performance_score = (latest_kpi['performanceScore'] * latest_kpi['taskCompletionCount'] + performance_score) / new_task_count
            new_task_level_score = (latest_kpi['taskLevelScore'] * latest_kpi['taskCompletionCount'] + difficulty_level) / new_task_count
        else:
            # Initialize values if no prior KPI record exists for this engagement
            new_task_count = 1
            new_performance_score = performance_score
            new_task_level_score = difficulty_level

        # Insert a new KPI record with the computed values and timestamp
        db.kpi.insert_one({
            "employeeId": ObjectId(preparer_id),
            "engagementId": ObjectId(task['engagementId']),
            "taskCompletionCount": new_task_count,
            "performanceScore": int(new_performance_score),
            "taskLevelScore": int(new_task_level_score),
            "date": get_singapore_time()  # Timestamp for when this KPI record is created
        })

        # Update industry expertise
        update_industry_expertise(db, preparer_id, task['engagementId'])

        return "Task reviewed and completed successfully."

    except Exception as e:
        print(f"Error in review_task_and_complete: {str(e)}")
        raise


# Helper function to update industry expertise
def update_industry_expertise(db, user_id, engagement_id):
    # Retrieve engagement to find the industry
    engagement = db.engagements.find_one({"_id": ObjectId(engagement_id)})
    if not engagement:
        print("Engagement not found.")
        return

    industry = engagement.get("industry")
    if not industry:
        print("Industry information missing in engagement.")
        return

    # Fetch user data to update industry expertise
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        print("User not found.")
        return

    # Initialize or update industry expertise
    industry_expertise = user.get("industryExpertise", {})

    # Check if industry_expertise is a list and convert it to a dictionary format
    if isinstance(industry_expertise, list):
        industry_expertise = {ind: 0 for ind in industry_expertise}

    # Update the industry count
    industry_expertise[industry] = industry_expertise.get(industry, 0) + 1

    # Sort by count and retain the top 3 industries
    sorted_industries = sorted(industry_expertise.items(), key=lambda x: x[1], reverse=True)[:3]
    top_industries = {ind: count for ind, count in sorted_industries}

    # Update the user's industry expertise field
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"industryExpertise": top_industries}}
    )


#Machine Learning for suggestion employee
# Helper function to rank employees based on industry expertise and KPIs
# def recommend_employees(db, industry, top_n=3):
#     """
#     Recommends top employees for a specific industry based on their expertise and performance metrics.
    
#     Parameters:
#     - db: Database connection
#     - industry: Target industry for the engagement
#     - top_n: Number of employees to recommend
    
#     Returns:
#     - List of recommended employees with their details
#     """
#     try:
#         # Fetch all employees with expertise in the given industry
#         employees = list(db.users.find({"industryExpertise." + industry: {"$exists": True}}))
        
#         if not employees:
#             return []
        
#         # Fetch KPI data for each employee
#         employee_scores = []
#         for employee in employees:
#             kpi = db.kpi.find_one({"employeeId": employee["_id"]})
#             if kpi:
#                 # Combine expertise score (number of completed tasks in industry) and performance metrics
#                 expertise_score = employee["industryExpertise"].get(industry, 0)
#                 performance_score = kpi["performanceScore"]
#                 task_level_score = kpi["taskLevelScore"]
                
#                 # Normalize and combine scores
#                 combined_score = np.array([expertise_score, performance_score, task_level_score])
#                 employee_scores.append((employee, combined_score))
        
#         # Normalize scores for comparison
#         scores_array = np.array([score for _, score in employee_scores])
#         scaler = MinMaxScaler()
#         normalized_scores = scaler.fit_transform(scores_array)
        
#         # Sort employees based on the normalized combined score
#         employee_ranking = sorted(
#             [(employee, sum(score)) for (employee, _), score in zip(employee_scores, normalized_scores)],
#             key=lambda x: x[1], 
#             reverse=True
#         )
        
#         # Return top N employees
#         recommended_employees = [emp[0] for emp in employee_ranking[:top_n]]
#         return recommended_employees

#     except Exception as e:
#         print(f"Error in recommend_employees: {e}")
#         return []

import logging
from bson import ObjectId
import pandas as pd
from surprise import Dataset, Reader, KNNBasic
from datetime import datetime, timezone

# Set up logging
logging.basicConfig(level=logging.INFO)

def prepare_knn_data(db, industry):
    """
    Fetches the latest employee-engagement performance data from the KPI collection for the specified industry
    and prepares it for KNN training, using a composite score of performance metrics.
    """
    logging.info(f"Preparing KNN data for industry: {industry}")

    # Retrieve engagements in the specified industry
    engagements_in_industry = db.engagements.find({"industry": industry}, {"_id": 1})
    engagement_ids = [eng["_id"] for eng in engagements_in_industry]
    logging.info(f"Engagement IDs in industry '{industry}': {engagement_ids}")

    if not engagement_ids:
        logging.warning(f"No engagements found for industry: {industry}")
        return None

    # Retrieve only the latest KPI records for each engagement
    kpi_records = db.kpi.aggregate([
        {"$match": {"engagementId": {"$in": engagement_ids}}},
        {"$sort": {"date": -1}},  # Sort by date in descending order
        {"$group": {
            "_id": {"employeeId": "$employeeId", "engagementId": "$engagementId"},
            "latestPerformanceScore": {"$first": "$performanceScore"},
            "latestTaskLevelScore": {"$first": "$taskLevelScore"},
            "latestTaskCompletionCount": {"$first": "$taskCompletionCount"}
        }}
    ])

    data = []
    for record in kpi_records:
        employee_id = str(record["_id"]["employeeId"])
        engagement_id = str(record["_id"]["engagementId"])

        performance_score = record.get("latestPerformanceScore", 0)
        task_level_score = record.get("latestTaskLevelScore", 0)
        task_completion_count = record.get("latestTaskCompletionCount", 0)

        composite_score = (0.5 * performance_score + 0.3 * task_level_score + 0.2 * task_completion_count)
        
        data.append((employee_id, engagement_id, composite_score))
        logging.info(f"Employee ID: {employee_id}, Engagement ID: {engagement_id}, Composite Score: {composite_score}")

    df = pd.DataFrame(data, columns=["employeeId", "engagementId", "compositeScore"])
    logging.info("DataFrame created for KNN training:\n%s", df)
    return df


def train_knn_model(db, industry):
    """
    Trains a KNN collaborative filtering model on employee engagement data using the composite score.
    """
    df = prepare_knn_data(db, industry)
    if df is None or df.empty:
        logging.warning("No data available to train the KNN model.")
        return None, None

    reader = Reader(rating_scale=(0, 100))
    data = Dataset.load_from_df(df[["employeeId", "engagementId", "compositeScore"]], reader)

    # Build the trainset and train the KNN model
    trainset = data.build_full_trainset()
    sim_options = {'name': 'cosine', 'user_based': True}
    knn_model = KNNBasic(sim_options=sim_options)
    knn_model.fit(trainset)
    logging.info("KNN model trained successfully for industry: %s", industry)

    return knn_model, trainset


def recommend_employees_knn(db, industry, top_n=3):
    """
    Recommends top employees for a specific industry using the KNN collaborative filtering model,
    and retrieves time-series KPI data for performance trend visualization.
    """
    try:
        knn_model, trainset = train_knn_model(db, industry)
        if knn_model is None or trainset is None:
            return []

        # Get the recommended employees based on KNN model
        recommendations = []
        seen_employees = set()  # Track employees already added
        
        # Use only unique employee IDs and their composite scores for recommendations
        employee_composite_scores = {}

        # Populate employee_composite_scores with the latest composite scores from the DataFrame
        knn_data_df = prepare_knn_data(db, industry)
        for _, row in knn_data_df.iterrows():
            employee_composite_scores[str(row["employeeId"])] = row["compositeScore"]

        for employee_id, composite_score in employee_composite_scores.items():
            try:
                employee_inner_id = trainset.to_inner_uid(employee_id)
                neighbors = knn_model.get_neighbors(employee_inner_id, k=top_n)

                for neighbor in neighbors:
                    neighbor_id = trainset.to_raw_uid(neighbor)
                    if neighbor_id not in seen_employees:  # Avoid duplicates
                        seen_employees.add(neighbor_id)
                        employee = db.users.find_one({"_id": ObjectId(neighbor_id)}, {"name": 1, "photo": 1})

                        if employee:
                            recommendations.append({
                                "id": neighbor_id,
                                "name": employee.get("name"),
                                "photo": employee.get("photo", "default-avatar.png"),
                                "score": employee_composite_scores.get(neighbor_id, 0)  # Use composite score here
                            })
            except Exception as e:
                print(f"Error fetching neighbors for employee {employee_id}: {e}")

        # Sort by composite score in descending order and take the top_n unique recommendations
        unique_recommendations = sorted(recommendations, key=lambda x: x['score'], reverse=True)[:top_n]

        # Prepare performance trend data for each unique recommended employee
        performance_trends = []
        for emp in unique_recommendations:
            emp_id = emp["id"]
            # Get engagements for the specified industry and filter KPIs accordingly
            relevant_engagements = db.engagements.find({"industry": industry}, {"_id": 1})
            engagement_ids = [eng["_id"] for eng in relevant_engagements]

            # Fetch KPI records related to the employee only within the specified industry's engagements
            kpis = db.kpi.find({
                "employeeId": ObjectId(emp_id),
                "engagementId": {"$in": engagement_ids}
            }, {"performanceScore": 1, "date": 1})

            trend_data = {
                "id": emp_id,
                "name": emp["name"],
                "scores": [
                    {
                        "date": kpi["date"].strftime('%Y-%m-%d'),  # Format date for trend data
                        "score": kpi.get("performanceScore", 0)
                    }
                    for kpi in kpis if "performanceScore" in kpi and "date" in kpi
                ]
            }
            if trend_data["scores"]:
                performance_trends.append(trend_data)

        return {
            "success": True,
            "employees": unique_recommendations,
            "performance_trends": performance_trends
        }
    except Exception as e:
        print(f"Error in recommend_employees_knn: {e}")
        return {"success": False, "message": "Server error occurred"}


#HR Function
def get_pending_users(db):
    """Fetch users with 'Pending Approval' role and convert ObjectId to string."""
    pending_users = db.users.find({"role": "Pending Approval"}, {"_id": 1, "name": 1})
    # Convert each user's _id from ObjectId to string
    return [{"_id": str(user["_id"]), "name": user["name"]} for user in pending_users]


def get_users_by_role(db, role):
    """Fetch users by role ('Manager' or 'Partner') and convert ObjectId to string."""
    users = db.users.find({"role": role}, {"_id": 1, "name": 1})
    return [{"_id": str(user["_id"]), "name": user["name"]} for user in users]

def get_user_by_id(db, user_id):
    """Fetch a user's data by ID."""
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        user['_id'] = str(user['_id'])
        return user
    return None

def update_user_profile(db, data, photo):
    """Update user profile with new data provided by HR."""
    user_id = data.get("userId")
    role = data.get("role")
    updates = {
        "salary": float(data.get("salary", 0)),
        "role": role,
        "lineManager": ObjectId(data["lineManager"]) if data.get("lineManager") else None
    }
    
    # If role is "Partner", include color
    if role == "Partner" and data.get("color"):
        updates["color"] = data["color"]

    # Handle photo upload
    if photo:
        if not os.path.exists('static/images'):
            os.makedirs('static/images')  # Create the images directory if it doesn't exist
        
        filename = secure_filename(photo.filename)
        filepath = os.path.join('static/images', filename)
        photo.save(filepath)
        updates["photo"] = f'{filename}'  # Save the relative path

    db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    return {"status": "success", "message": "User profile updated successfully"}


# Staff utilization

def get_employee_utilization(db, engagement_id=None, start_date=None, end_date=None):
    """
    Calculate employee utilization data for a specific engagement or overall if no engagement_id is provided.
    """
    try:
        # Set default date range if not provided
        end_date = end_date or datetime.now()
        start_date = start_date or (end_date - timedelta(days=30))
        total_working_hours_30_days = 40 * 4  # 40 hours per week for 4 weeks = 160 hours

        # Query timesheets based on engagement_id and date range
        timesheet_query = {
            "date": {"$gte": start_date, "$lte": end_date}
        }
        if engagement_id:
            timesheet_query["engagementId"] = ObjectId(engagement_id)

        print(f"Fetching timesheets with query: {timesheet_query}")
        timesheets = db.timesheets.find(timesheet_query)

        # Query tasks based on engagement_id and date range
        tasks_query = {"dueDate": {"$gte": start_date, "$lte": end_date}}
        if engagement_id:
            tasks_query["engagementId"] = ObjectId(engagement_id)

        print(f"Fetching tasks with query: {tasks_query}")
        tasks = db.tasks.find(tasks_query)

        # Fetch employee details
        print("Fetching employee details")
        employees = db.users.find({}, {"_id": 1, "name": 1, "role": 1})

        # Data aggregation
        utilization_data = {}
        for employee in employees:
            employee_id = str(employee["_id"])
            utilization_data[employee_id] = {
                "name": employee["name"],
                "role": employee["role"],
                "charged_hours": {},
                "allocated_hours": {},
                "utilization_rate": 0,
                "overload_rate": 0
            }
        
        # Calculate total charged and allocated hours
        total_charged_hours = {emp_id: 0 for emp_id in utilization_data.keys()}
        total_allocated_hours = {emp_id: 0 for emp_id in utilization_data.keys()}

        # Populate charged hours from timesheets
        for entry in timesheets:
            employee_id = str(entry["employeeId"])
            date_str = entry["date"].strftime("%Y-%m-%d")
            hours = float(entry["hours"])
            print(f"Adding {hours} charged hours for {employee_id} on {date_str}")
            utilization_data[employee_id]["charged_hours"][date_str] = utilization_data[employee_id]["charged_hours"].get(date_str, 0) + hours
            total_charged_hours[employee_id] += hours

        # Populate allocated hours from tasks
        for task in tasks:
            assigned_to = str(task["assignedTo"])
            due_date_str = task["dueDate"].strftime("%Y-%m-%d")
            time_estimate = task.get("timeEstimate", 0)
            print(f"Adding {time_estimate} allocated hours for {assigned_to} on {due_date_str}")
            utilization_data[assigned_to]["allocated_hours"][due_date_str] = utilization_data[assigned_to]["allocated_hours"].get(due_date_str, 0) + time_estimate
            total_allocated_hours[assigned_to] += time_estimate

        # Calculate utilization rate and overload rate
        for emp_id, data in utilization_data.items():
            charged_hours = total_charged_hours[emp_id]
            allocated_hours = total_allocated_hours[emp_id]

            # Utilization Rate calculation
            data["utilization_rate"] = (charged_hours / total_working_hours_30_days) * 100

            # Overload Rate calculation (only if allocated hours exceed capacity)
            if allocated_hours > total_working_hours_30_days:
                data["overload_rate"] = ((allocated_hours - total_working_hours_30_days) / total_working_hours_30_days) * 100
            else:
                data["overload_rate"] = 0
        
        print("Final utilization data:", utilization_data)
        return utilization_data

    except Exception as e:
        print(f"Error in get_employee_utilization: {e}")
        return {}


def get_engagement_utilization(db, engagement_id):
    """
    Fetch engagement-specific utilization data, including charged hours for each employee
    and total allocated hours for the engagement. Calculate recovery rates for display purposes.
    """
    try:
        print(f"Debug: Starting get_engagement_utilization for engagement_id={engagement_id}")

        # Fetch engagement budget
        engagement = db.engagements.find_one({"_id": ObjectId(engagement_id)}, {"budget": 1})
        if not engagement:
            print(f"Debug: No engagement found with ID {engagement_id}")
            return {}

        budget = engagement.get("budget", 0)
        total_working_hours_per_month = 160
        print(f"Debug: Retrieved budget={budget} for engagement ID {engagement_id}")

        # Fetch tasks and timesheets for the engagement
        tasks = db.tasks.find({"engagementId": ObjectId(engagement_id)})
        timesheets = db.timesheets.find({"engagementId": ObjectId(engagement_id)})

        print("Debug: Retrieved tasks and timesheets for engagement.")

        # Data structures to store results
        charged_hours = defaultdict(lambda: {"name": "", "hours": defaultdict(float)})
        allocated_hours = defaultdict(float)
        recovery_data = {}

        # Calculate estimated recovery (allocated hours) based on tasks
        for task in tasks:
            employee_id = str(task["assignedTo"])
            time_estimate = task.get("timeEstimate", 0)
            due_date = task.get("dueDate")
            if due_date:
                date_key = due_date.strftime("%Y-%m-%d")  # Standardize date format
                allocated_hours[date_key] += time_estimate

            # Fetch employee data (including name) for display purposes
            employee = db.users.find_one({"_id": ObjectId(employee_id)}, {"salary": 1, "name": 1})
            if not employee:
                print(f"Debug: No employee found with ID {employee_id} (skipping)")
                continue
            
            employee_name = employee.get("name", f"Employee {employee_id[:4]}")
            salary_per_hour = employee["salary"] / total_working_hours_per_month
            estimated_cost = time_estimate * salary_per_hour
            
            # Add recovery data for display
            recovery_data.setdefault(employee_id, {"estimated_recovery": 0, "actual_recovery": 0})
            recovery_data[employee_id]["estimated_recovery"] += estimated_cost
            
            # Store employee name and initialize hours for charged_hours
            charged_hours[employee_id]["name"] = employee_name

        # Process each timesheet entry for actual recovery
        for entry in timesheets:
            employee_id = str(entry["employeeId"])
            hours_charged = float(entry["hours"])
            entry_date = entry.get("date")  # Assume there's a 'date' field in timesheets
            if entry_date:
                date_key = entry_date.strftime("%Y-%m-%d")
                charged_hours[employee_id]["hours"][date_key] += hours_charged

            # Calculate actual recovery for display purposes
            employee = db.users.find_one({"_id": ObjectId(employee_id)}, {"salary": 1})
            if not employee:
                print(f"Debug: No employee found with ID {employee_id} (skipping)")
                continue

            salary_per_hour = employee["salary"] / total_working_hours_per_month
            actual_cost = hours_charged * salary_per_hour
            recovery_data[employee_id]["actual_recovery"] += actual_cost

        # Aggregate recovery rates across employees
        estimated_recovery_total = sum(emp["estimated_recovery"] for emp in recovery_data.values())
        actual_recovery_total = sum(emp["actual_recovery"] for emp in recovery_data.values())
        print(f"Debug: Calculated estimated_recovery_total={estimated_recovery_total}, actual_recovery_total={actual_recovery_total}")

        estimated_recovery_rate = 100 * (budget - estimated_recovery_total) / budget if budget else 0
        actual_recovery_rate = 100 * (budget - actual_recovery_total) / budget if budget else 0

        print(f"Debug: Final estimated_recovery_rate={estimated_recovery_rate}, actual_recovery_rate={actual_recovery_rate}")

        # Prepare data for anomaly detection
        historical_recovery_rates = [20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        recovery_rates = np.array([[actual_recovery_rate]] + [[rate] for rate in historical_recovery_rates])
        print(f"Debug: Recovery rates: {recovery_rates}")  # Check the input to IsolationForest
        iso_forest = IsolationForest(contamination=0.1, random_state=42)
        anomaly_flags = iso_forest.fit_predict(recovery_rates)
        print(f"Debug: Anomaly flags: {anomaly_flags}")  # Check the results of IsolationForest
        anomalies = anomaly_flags[0] == -1

        # Convert data types for JSON serialization
        anomalies = bool(anomalies)
        print(f"Debug: Anomaly detected: {anomalies}")  # This will confirm if it's True or False
        estimated_recovery_rate = float(estimated_recovery_rate)
        actual_recovery_rate = float(actual_recovery_rate)

        advice = ""
        if anomalies:
            advice = "Warning: The engagement shows unusual recovery trends. Immediate review is recommended."
        elif actual_recovery_rate > 40:
            advice = "The engagement is in a healthy stage with a positive return. Keep up the good work."
        elif actual_recovery_rate > 10:
            advice = "The engagement return is normal. Consider monitoring time allocation and actual charges."
        elif actual_recovery_rate > 0:
            advice = "The engagement return is at risk. Limit hours charged to avoid crossing into negative territory."
        else:
            advice = "The engagement is losing money. Partner intervention is advised to assess high-cost charges and possible fee adjustments."
        

        return {
            "charged_hours": charged_hours,
            "allocated_hours": allocated_hours,
            "recovery_data": recovery_data,
            "estimated_recovery_rate": estimated_recovery_rate,
            "actual_recovery_rate": actual_recovery_rate,
            "anomalies": anomalies,  # Anomalies flag array as a list of booleans
            "advice": advice  # Advice based on recovery rate
        }

    except Exception as e:
        print(f"Error in get_engagement_utilization: {e}")
        return {}

#chatbot function    
def send_prompt_to_chatgpt(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']

# Main chat function with memory, using LangChain agent first and falling back on OpenAI API with history if needed
def send_chat_to_chatgpt(message, db):
    # Get user_id as an ObjectId
    user_id = get_user_id()
    if not user_id:
        return "Invalid user ID. Please ensure you’re logged in."

    # Retrieve or create user history
    user_history = get_user_history(user_id)
    
    # Add the new message to the user’s history
    user_history.append({"role": "user", "content": message})

    # Print user ID for debugging
    print(f"Debug: user_id is {user_id} (type: {type(user_id)})")

    # Initialize the LangChain agent
    agent = get_langchain_agent(db, user_id)

    # Try to use the LangChain agent first
    try:
        response = agent.run({"input": message})  # Pass only the message to the agent

        # If we get a response, append to history and return it
        if response:
            user_history.append({"role": "assistant", "content": response})
            return response
        else:
            # If agent fails or no response is found, we fallback to OpenAI with memory
            print("Agent did not produce a response. Using fallback with memory.")
    except Exception as e:
        print(f"Error in LangChain agent: {e}. Using fallback with memory.")

    # Fallback to OpenAI API with memory if agent doesn't respond
    return fallback_tool(message, user_id)



#show analysis of engagement via chatbot
def get_engagement_id_by_name(db, engagement_name):
    """
    Looks up an engagement ID by name.
    """
    engagement = db.engagements.find_one({"name": engagement_name}, {"_id": 1})
    return str(engagement["_id"]) if engagement else None


# Function to generate the predictive analysis report for an engagement by ID
def generate_engagement_report(engagement_id, db):
    print(f"Generating report for engagement ID: {engagement_id}")
    
    # Get utilization data for the specified engagement
    engagement_data = get_engagement_utilization(db, engagement_id)
    if not engagement_data:
        return "No data available for this engagement."

    # Extract the actual recovery rate
    actual_recovery_rate = engagement_data['actual_recovery_rate']
    healthy_threshold = 40  # Define a threshold for a "healthy" recovery rate

    # Determine health status and add context
    if actual_recovery_rate > healthy_threshold:
        health_status = "The engagement is in a healthy stage with a positive return."
        health_explanation = (
            f"A recovery rate above {healthy_threshold}% is generally considered strong, "
            "indicating that the engagement is yielding a good return. Higher recovery rates "
            "suggest that the costs charged to the client align well with the estimated budget, "
            "contributing positively to profitability."
        )
    elif 10 <= actual_recovery_rate <= healthy_threshold:
        health_status = "The engagement return is normal."
        health_explanation = (
            "An actual recovery rate within this range is typical for most engagements. "
            "It means the project is progressing as expected but may benefit from closer monitoring "
            "to ensure it stays on track and avoids slipping into a lower recovery range."
        )
    else:
        health_status = "The engagement return is at risk."
        health_explanation = (
            "A recovery rate in this range indicates potential budget concerns. When the recovery rate is low, "
            "it suggests that the costs may be exceeding the allocated budget, impacting profitability. "
            "Consider investigating time allocation and resource usage to improve the rate."
        )

    # Generate the detailed report
    report = (
        f"Engagement Report:\n"
        f"Actual Recovery Rate: {actual_recovery_rate:.2f}% ({health_status})\n"
        f"{health_explanation}\n\n"
        f"Anomalies Detected: {'Yes' if engagement_data['anomalies'] else 'No'}\n"
        f"Advice: {engagement_data['advice']}\n\n"
        f"Detailed Recovery Data:\n"
    )

    # # Add detailed recovery data for each employee
    # for employee_id, recovery_info in engagement_data["recovery_data"].items():
    #     report += (
    #         f"Employee ID: {employee_id}, "
    #         f"Actual Recovery: ${recovery_info['actual_recovery']:.2f}\n"
    #     )

    # # Add an additional prompt for ChatGPT to explain the recovery rate conceptually
    # general_knowledge = send_prompt_to_chatgpt(
    #     "Explain why a high recovery rate is beneficial in a professional services engagement."
    # )

    # # Append ChatGPT's explanation to the report
    # report += f"\nAdditional Insight:\n{general_knowledge}"

    return report


# Helper function to resolve engagement name to ID
def get_engagement_id_by_name(db, engagement_name):
    print(f"Looking up engagement by name: {engagement_name}")
    
    engagement = db.engagements.find_one(
        {"clientName": {"$regex": f"^{engagement_name}$", "$options": "i"}}, {"_id": 1}
    )
    
    if engagement:
        print(f"Engagement '{engagement_name}' found with ID: {engagement['_id']}")
        return str(engagement["_id"])
    else:
        print(f"Engagement '{engagement_name}' not found in database.")
        return None


# Updated generate_report_tool to avoid redundant name extraction
def generate_report_tool(engagement_name, db):
    # Directly look up engagement by name
    print(f"Looking up engagement by name: {engagement_name}")
    engagement_id = get_engagement_id_by_name(db, engagement_name)
    if not engagement_id:
        return f"Engagement '{engagement_name}' not found. Please check the name and try again."

    # Generate and return the engagement report
    return generate_engagement_report(engagement_id, db)


# Enhanced name extraction function to handle more flexible message formats
def extract_engagement_name_from_message(message):
    patterns = [
        r"report for (.+)",              # e.g., "report for crypto.com"
        r"engagement (.+)",              # e.g., "engagement crypto.com"
        r"analysis of (.+)",             # e.g., "show me the analysis of crypto.com"
        r"analysis on (.+)",             # e.g., "analysis on crypto.com"
        r"recovery analysis of (.+)",    # e.g., "recovery analysis of crypto.com"
    ]
    
    # Check against patterns
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            engagement_name = match.group(1).strip()
            print(f"Extracted engagement name from pattern: '{engagement_name}'")
            return engagement_name

    # Default to assuming entire message is engagement name if simple (1-2 words) and not a question
    words = message.split()
    if len(words) <= 2 and not re.search(r"\b(who|what|when|where|why|how)\b", message):
        print(f"Assuming entire message is engagement name: '{message}'")
        return message

    return None  # Return None if it's likely a general question



def get_langchain_agent(db, user_id):
    prompt = PromptTemplate(
        input_variables=["input"],
        template=(
            "When responding to '{input}', follow these rules strictly to choose the correct tool:\n\n"

            # Rule for Navigation Tool
            "1. If '{input}' includes specific terms for navigation (like 'dashboard', 'scheduler', 'expenses', 'leave board', 'office space', or 'chatbot'), "
            "always use the Navigation tool to provide the exact HTML link output without any summarization. Do not add any extra thoughts, only the HTML link. "
            "If no specific page is mentioned, provide links to all available pages.\n\n"

            # Rule for Engagement Report
            "2. If '{input}' contains an engagement name, mentions a client or project (e.g., 'crypto.com'), or requests an engagement report, "
            "prioritize using the Engagement Report Generator tool to generate a detailed report on that engagement. "
            "This tool should always take priority if an engagement-related term is detected.\n\n"

            # Rule for Timesheet Submission
            "3. If '{input}' includes a request to 'submit my timesheet' or specifies hours with the phrase 'task [task name] for [number] hours', "
            "use the Timesheet Submission tool to extract the task name and hours for timesheet entry submission.\n\n"

            # Rule for Training & SOP Guidance
            "4. If '{input}' mentions keywords like 'training', 'guidance', 'resources', 'learn about', or specific training topics (e.g., FRS 115, IFRS 16), "
            "use the Training & SOP Guidance tool to retrieve relevant resources from the 'Technical&SOP' collection. "
            "Provide a clickable link to any resources found, especially if they are videos or articles.\n\n"

            # Rule for SOP Guidance
            "5. If '{input}' includes phrases about applying leave, submitting expenses, company policies, or 'how to' processes (e.g., 'how do I apply for leave', 'submit expenses', or 'company policies'), "
            "use the Training & SOP Guidance tool to retrieve a relevant SOP entry from the 'Technical&SOP' collection. "
            "Clearly explain each step, if available, or link to additional resources if necessary.\n\n"

            # General Chat Fallback
            "6. For any other general information requests that do not match the above criteria, use the General Chat tool to respond.\n\n"

            # Important Note
            "7. Avoid summarizing or adding extra thoughts when returning direct HTML links, engagement reports, training resources, or SOP guidance. "
            "Only use additional thoughts when strictly necessary for clarification.\n\n"
        )
    )

    # Define the LLM model (using OpenAI's ChatGPT)
    llm = ChatOpenAI(model="gpt-4-turbo")

    # Initialize tools
    tools = [
        Tool(
            name="Navigation",
            func=lambda page_name=None: navigation_tool(page_name),
            description=(
                "Provides direct navigation links for specified pages (e.g., 'dashboard', 'scheduler', 'expenses', 'leave board', 'office space', 'chatbot'). "
                "If a specific page is requested, returns only that page link. If no page is specified, returns links to all available pages. "
                "Must provide the exact HTML link output without any summarization."
            )
        ),
        Tool(
            name="Engagement Report Generator",
            func=lambda engagement_name: generate_report_tool(engagement_name.strip(), db),
            description=(
                "Generates a detailed report for engagement-related terms (like engagement names, clients, or projects) using the Engagement Report Generator. "
                "Use this tool when '{input}' includes an engagement name, client, or project reference, or requests an engagement report (e.g., 'crypto.com')."
            )
        ),
        Tool(
            name="Timesheet Submission",
            func=lambda message: timesheet_submission_tool(message, db),
            description=(
                "Submits a timesheet entry based on message content, extracting task name and hours from '{input}'. "
                "Triggered by phrases like 'submit my timesheet' or '[task name] for [number] hours'. Extracts hours and task name and submits the entry."
            )
        ),
        Tool(
            name="Training & SOP Guidance",
            func=lambda query: fetch_training_or_sop_resource(query, db),
            description=(
                "Fetches training resources or SOP guidance based on user queries. Use for keywords related to 'training', 'guidance', 'resources', "
                "'learn about', 'how to', or topics like FRS 115 or IFRS 16. Also used for questions about applying leave, submitting expenses, "
                "company policies, or similar procedural questions."
            )
        ),
        Tool(
            name="General Chat",
            func=lambda message: fallback_tool(message, user_id), 
            description="Handles general information requests that do not match other tool criteria. Use as a fallback."
        )
    ]
    # Create the agent
    agent = initialize_agent(llm=llm, tools=tools, prompt=prompt, verbose=True)
    print("Debug: LangChain agent initialized")  # Ensure the agent initializes correctly
    return agent


# Chat handling function using the agent
def handle_chat_with_langchain(message, db):
    engagement_name = extract_engagement_name_from_message(message)
    if not engagement_name:
        return "Please specify the engagement name you would like me to analyze."

    agent = get_langchain_agent(db, engagement_name)
    response = agent.run({"input": message})
    
    # Extract the 'output' field from the response if it exists
    return response.get('output') if isinstance(response, dict) else response

#submit timesheet via chatbot

def get_inprogress_tasks_for_user(db, engagement_id, user_id):
    try:
        # Fetch tasks related to the engagement that are in progress and assigned to the user
        tasks = list(db.tasks.find(
            {
                "engagementId": ObjectId(engagement_id),
                "assignedTo": ObjectId(user_id),
                "status": "In Progress"
            },
            {
                "description": 1  # Explicitly request 'description' field
            }
        ))
        return tasks
    except Exception as e:
        print(f"Error in get_inprogress_tasks_for_user: {e}")
        return []


    
# Global dictionary to track context, using user ID as the key.
user_context = {}

# def process_chatbot_message(message, user_id, db):
#     # If the user confirms the suggestion with "yes"
#     if message.strip().lower() == "yes":
#         if user_id in user_context and "suggested_task" in user_context[user_id]:
#             # Retrieve stored task and hours info
#             task_info = user_context[user_id]
#             task_id = task_info["suggested_task"]["_id"]  # Retrieve ObjectId directly
#             hours = task_info["hours"]
            
#             # Submit timesheet with stored data
#             result = submit_timesheet(db, task_id, user_id, hours, get_singapore_time())
            
#             # Clear context after successful submission
#             del user_context[user_id]
            
#             return result
#         else:
#             return "I couldn't find any pending timesheet submission. Please specify the task and hours."

#     # Check if the user is asking to see pending tasks
#     if "show pending tasks for" in message.lower():
#         engagement_name = extract_engagement_name_for_tasks(message)
#         if not engagement_name:
#             return "Please specify the engagement name."

#         # Look up the engagement ID and fetch tasks
#         engagement_id = get_engagement_id_by_name(db, engagement_name)
#         if not engagement_id:
#             return f"No engagement found with the name '{engagement_name}'. Please check the name and try again."

#         tasks = get_inprogress_tasks_for_user(db, engagement_id, user_id)
#         if not tasks:
#             return f"No pending tasks found for {engagement_name}."
        
#         # Safely handle tasks that may be missing 'description' key
#         task_list = "\n".join([f"{i+1}. {task.get('description', 'Unnamed Task')}" for i, task in enumerate(tasks)])
#         return f"Pending tasks for {engagement_name}:\n{task_list}"

#     # Check if the user is submitting a timesheet
#     if "submit my timesheet" in message.lower():
#         hours = extract_hours_from_message(message)
#         task_name = extract_task_name_from_message(message)

#         if not hours or not task_name:
#             return "Please specify the task and hours for the timesheet submission."

#         # Find the specific task
#         task = find_task_by_name(db, user_id, task_name)
#         if isinstance(task, dict):  # Task found
#             result = submit_timesheet(db, task['_id'], user_id, hours, get_singapore_time())
#             return result
#         elif isinstance(task, list) and task:  # Suggest tasks if task name was unclear
#             # Save the context with ObjectId for confirmation
#             user_context[user_id] = {
#                 "suggested_task": task[0],  # Store the first suggested task's object
#                 "hours": hours
#             }
#             suggestions = ", ".join([t['description'] for t in task])
#             return f"Task '{task_name}' not found. Did you mean: {suggestions}?"

#     # Fallback to ChatGPT response if no specific task was handled
#     return None


# Improved hours extraction function with debugging
def extract_hours_from_message(message):
    # Look for phrases like "4 hours", "2 hrs", "1 h", etc.
    match = re.search(r"(\d+(\.\d+)?)\s*(hours|hrs|h)", message, re.IGNORECASE)
    if match:
        extracted_hours = float(match.group(1))
        print(f"Debug: Extracted hours = {extracted_hours}")
        return extracted_hours
    print("Debug: No valid hours found in message.")
    return None

def extract_task_name_from_message(message):
    # Refine regex to capture text between "task" and "for"
    match = re.search(r"(?:task\s+)([a-zA-Z\s]+?)(?=\s+for|$)", message, re.IGNORECASE)
    if match:
        task_name = match.group(1).strip()
        print(f"Debug: Extracted task name = '{task_name}'")  # Add debug statement
        return task_name
    print("Debug: No valid task name found in message.")
    return None

def find_task_by_name(db, user_id, task_name):
    # Find tasks assigned to the user that are "In Progress"
    tasks = list(db.tasks.find({"assignedTo": ObjectId(user_id), "status": "In Progress"}))

    # Normalize to lowercase for case-insensitive matching
    task_name_lower = task_name.lower()
    
    # Check for exact match ignoring case
    exact_match = next((task for task in tasks if task['description'].lower() == task_name_lower), None)
    if exact_match:
        print(f"Debug: Exact task match found for '{task_name}'")
        return exact_match

    # If no exact match, use fuzzy matching to suggest similar tasks
    task_names = [task for task in tasks]  # Keep tasks as objects, not just names
    suggestions = get_close_matches(task_name_lower, [task['description'].lower() for task in task_names], n=3, cutoff=0.6)
    
    # Return list of tasks (full objects) that match suggestions
    return [task for task in tasks if task['description'].lower() in suggestions]

# Extraction function for task-related requests
def extract_engagement_name_for_tasks(message):
    patterns = [
        r"pending tasks for (.+)",       # e.g., "pending tasks for crypto.com"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message.lower())
        if match:
            return match.group(1).strip()
    return None

# Improved hours extraction function with debugging
def extract_hours_from_message(message):
    # Look for phrases like "4 hours", "2 hrs", "1 h", etc.
    match = re.search(r"(\d+(\.\d+)?)\s*(hours|hrs|h)", message, re.IGNORECASE)
    if match:
        extracted_hours = float(match.group(1))
        print(f"Debug: Extracted hours = {extracted_hours}")
        return extracted_hours
    print("Debug: No valid hours found in message.")
    return None

def timesheet_submission_tool(message, db):
    # Log the raw message for debugging
    print("Debug: Raw message received in timesheet_submission_tool =", message)

    # Extract task_name and hours directly from the message
    task_name = extract_task_name_from_message(message)
    hours = extract_hours_from_message(message)
    user_id = get_user_id()

    # Debug extracted values
    print(f"Debug: Extracted task name = {task_name}")
    print(f"Debug: Extracted hours = {hours}")
    print(f"Debug: User ID = {user_id}")

    if not task_name:
        return "Please provide a valid task name."
    if hours is None:
        return "Please specify the number of hours."

    # Ensure hours is a float
    try:
        hours = float(hours)
    except (TypeError, ValueError):
        return "Invalid input format for hours. Please enter a valid number."

    # Proceed with finding the task and submitting the timesheet
    try:
        print(f"Finding task by name: {task_name} for user_id={user_id}")
        task = find_task_by_name(db, user_id, task_name)

        if isinstance(task, dict):  # Single task found
            return submit_timesheet(db, task['_id'], user_id, hours, get_singapore_time())
        elif isinstance(task, list) and task:  # Multiple tasks found (suggest alternatives)
            user_context[user_id] = {"suggested_task": task[0], "hours": hours}
            suggestions = ", ".join([t['description'] for t in task])
            return f"Task '{task_name}' not found. Did you mean: {suggestions}?"
        else:
            return "Task not found. Please specify a valid task name."
    except Exception as e:
        print(f"Error in timesheet_submission_tool: {e}")
        return "An error occurred while submitting the timesheet."



# Fallback tool for general responses with memory integration
def fallback_tool(prompt, user_id):
    # Retrieve or create user history
    user_history = get_user_history(user_id)
    
    # Add the new message to the user’s history
    user_history.append({"role": "user", "content": prompt})
    
    # Prepare the messages for the model, including the recent history
    messages = list(user_history)
    
    try:
        # Call OpenAI API with full conversation context
        openai_response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=messages
        )
        assistant_reply = openai_response['choices'][0]['message']['content']

        # Append the assistant’s response to user history
        user_history.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply
    except Exception as e:
        print(f"Error in OpenAI API: {e}")
        return "An error occurred while processing your request."



def navigation_tool(page_name=None):
    # Dictionary mapping page names to their URLs
    pages = {
        "dashboard": url_for('views.dashboard', _external=True),
        "scheduler": url_for('views.scheduler', _external=True),
        "expenses": url_for('views.expenses_claims', _external=True),
        "office_space": url_for('views.office_space', _external=True),
        "leave_board": url_for('views.leave_board', _external=True),
        "chatbot": url_for('views.chatbot', _external=True)
    }

    # Check if a specific page is requested; if so, return only that page link
    if page_name:
        page_name = page_name.lower()
        if page_name in pages:
            url = pages[page_name]
            return Markup(f"<a href='{url}'>Go to {page_name.replace('_', ' ').capitalize()}</a>")

    # If no specific page is requested, return links to all pages
    all_links = "<br>".join([f"<a href='{url}'>Go to {key.replace('_', ' ').capitalize()}</a>" for key, url in pages.items()])
    return Markup(all_links)

def get_user_id():
    user_id = session.get('user_id')
    if user_id:
        try:
            # Ensure user_id is always returned as an ObjectId
            return ObjectId(user_id) if isinstance(user_id, str) else user_id
        except InvalidId:
            print("Invalid user ID format.")
            return None
    return None


#training via chatbot
def fetch_training_or_sop_resource(query, db):
    # Search for matching SOP or training entries using a text search
    result = db['Technical&SOP'].find_one(
        {"$text": {"$search": query}},
        {"score": {"$meta": "textScore"}}  # Sort results by relevance
    )
    if result:
        # Format the response
        if result['type'] == "Technical Training":
            return f"Here is the training resource on {result['topic']}: <a href='{result['link']}' target='_blank'>{result['topic']}</a>"
        elif result['type'] == "SOP Guidance":
            details = "<br>".join(f"- {detail}" for detail in result.get('details', []))
            return f"{result['description']}<br>{details}"
    return "I couldn't find relevant resources for that topic. Please try another query."

# Define a global dictionary to store conversation history for each user session
user_histories = {}

# Function to get or create the conversation history for a user
def get_user_history(user_id):
    # limit for the number of recent messages to keep (last 5)
    max_history_length = 5
    if user_id not in user_histories:
        user_histories[user_id] = deque(maxlen=max_history_length)  # Limited to the last 5 messages
    return user_histories[user_id]