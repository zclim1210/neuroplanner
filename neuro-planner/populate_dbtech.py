from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import certifi

# Connect to MongoDB (replace with your own MongoDB URI)
client = MongoClient("mongodb+srv://<username>:<password>@neuroplanner.<xxxxxx>.mongodb.net/?retryWrites=true&w=majority&appName=NeuroPlanner", tlsCAFile=certifi.where())
db = client['NeoroPlanner']

# Data for Technical Training Requests
technical_training_data = [
    {
        "_id": ObjectId("666eeb6975f9a89b49394290"),
        "type": "Technical Training",
        "topic": "FRS 115 - Revenue Recognition",
        "description": "Understanding revenue recognition under FRS 115 standards.",
        "link": "https://www.youtube.com/watch?v=6d8NPrXKkx4&t=32s", 
        "tags": ["FRS 115", "Revenue Recognition", "Accounting Standards"],
    },
    {
        "_id": ObjectId("666eeb6975f9a89b49394291"),
        "type": "Technical Training",
        "topic": "IFRS 16 - Leases",
        "description": "Overview of the IFRS 16 standard, covering lease accounting and treatment.",
        "link": "https://www.youtube.com/watch?v=sHlu2SHoki0",
        "tags": ["IFRS 16", "Lease Accounting", "Accounting Standards"],
    },
    {
        "_id": ObjectId("666eeb6975f9a89b49394292"),
        "type": "Technical Training",
        "topic": "Digital Transformation in Finance",
        "description": "How digital transformation is reshaping the finance industry.",
        "link": "https://www.youtube.com/watch?v=9TPKvZ3Wb3Y",
        "tags": ["Digital Transformation", "Finance", "Technology"],
    }
]

# Data for SOP Guidance
sop_guidance_data = [
    {
        "_id": ObjectId("666eeb6975f9a89b49394293"),
        "type": "SOP Guidance",
        "topic": "How to Apply for Leave",
        "description": "Steps on applying for leave through the company system.",
        "details": [
            "Go to the 'Leave Application' board.",
            "Click the 'Request Leave' button, select the type of leave and dates.",
            "Upload the supporting of leave application.",
            "Submit for line manager approval."
            "Note: If you are partner, it will auto-approving leave request."
        ],
        "tags": ["Leave Application", "HR Procedures"]
    },
    {
        "_id": ObjectId("666eeb6975f9a89b49394294"),
        "type": "SOP Guidance",
        "topic": "Understanding Recovery Rate for Engagements",
        "description": "Explanation of recovery rate and its significance for engagements.",
        "details": [
            "Recovery rate indicates the percentage of billable hours recovered from the client.",
            "A high recovery rate means the engagement is financially healthy.",
            "Low recovery rates could indicate budget concerns or inefficiencies."
        ],
        "tags": ["Recovery Rate", "Financial Health", "Engagement"]
    },
    {
        "_id": ObjectId("666eeb6975f9a89b49394295"),
        "type": "SOP Guidance",
        "topic": "How to Submit Expenses",
        "description": "Guide on submitting expenses through the company portal.",
        "details": [
            "Go to the 'Expenses Application' board.",
            "Click the '+' button, select the type of engagement, category and dates, type the description of expenses.",
            "Upload receipts and enter relevant details.",
            "Submit for engagement manager for approval."
        ],
        "tags": ["Expenses", "Finance Procedures"]
    },
    {
        "_id": ObjectId("666eeb6975f9a89b49394296"),
        "type": "SOP Guidance",
        "topic": "Why Tasks Cannot Submit Timesheets",
        "description": "Reasons why certain tasks are restricted from timesheet submission.",
        "details": [
            "Only tasks with 'In Progress' status are eligible for timesheet submission.",
            "Check the task status in the task board.",
            "Contact the IT manager if you believe the status should be updated."
        ],
        "tags": ["Timesheet Submission", "Task Status", "Project Management"]
    }
]

# Insert data into the Technical&SOP collection
technical_sop_collection = db['Technical&SOP']
technical_sop_collection.insert_many(technical_training_data + sop_guidance_data)

print("Data successfully inserted into Technical&SOP collection.")
