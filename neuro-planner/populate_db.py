from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import certifi
from flask_bcrypt import Bcrypt

# Initialize bcrypt for password hashing
bcrypt = Bcrypt()

# Connect to MongoDB, Please replace the mongoclient URI.
client = MongoClient("mongodb+srv://<username>:<password>@neuroplanner.<xxxxxx>.mongodb.net/?retryWrites=true&w=majority&appName=NeuroPlanner", tlsCAFile=certifi.where())
db = client['NeoroPlanner']  

# Inserting data into Users collection
users_data = [
    {
        "_id": ObjectId("664592366c287da0b2777325"),
        "name": "Jane",
        "email": "jane@neuro.com",
        "password": "Jane",
        "role": "Partner",
        "salary": 12000,
        "photo": "jane.jpg",
        "industryExpertise": ["Healthcare", "Public", "Technology"],
        "activeEngagements": ["Crypto"],
        "joinedDate": datetime(2015, 8, 23),
        "lineManager": "N/A",
        "color": "#FF5733"
    },
    {
        "_id": ObjectId("664592366c287da0b2777324"),
        "name": "John",
        "email": "john@neuro.com",
        "password": "John",
        "role": "Manager",
        "salary": 8000,
        "photo": "john.jpg",
        "industryExpertise": ["Finance", "Technology"],
        "activeEngagements": ["Crypto"],
        "joinedDate": datetime(2020, 5, 1),
        "lineManager": ObjectId("664592366c287da0b2777325")
    },
    {
        "_id": ObjectId("6647995d8f2bc3f1601cac7d"),
        "name": "Tesla",
        "email": "tesla@neuro.com",
        "password": "Tesla",
        "role": "Senior Associate",
        "salary": 7000,
        "photo": "tesla.jpg",
        "industryExpertise": [],
        "activeEngagements": [],
        "joinedDate": datetime(2024, 5, 17),
        "lineManager": ObjectId("664592366c287da0b2777324")
    },
    {
        "_id": ObjectId("666eeb6975f9a89b49394284"),
        "name": "Tim",
        "email": "tim@neuro.com",
        "password": "Tim",
        "role": "Partner",
        "salary": 50000,
        "photo": "tim.jpg",
        "industryExpertise": [],
        "activeEngagements": [],
        "joinedDate": datetime(2018, 1, 1),
        "lineManager": "N/A",
        "color": "#AEC0F2"
    }    
]

for user in users_data:
    user['password'] = bcrypt.generate_password_hash(user['password']).decode('utf-8')

users = db.users
users.insert_many(users_data)

# Inserting data into leave_balance collection
leave_balance_data = [
    {
        "_id": ObjectId("6681a1a1bb4f60bc1a9a4168"),
        "user": ObjectId("664592366c287da0b2777325"),
        "year": 2024,
        "annualLeave": 5,
        "rollForward": 4,
        "medicalLeave": 10,
        "usedLeave": 6,
        "balance": 20,
        "studyLeave": 1
    },
    {
        "_id": ObjectId("6684232774d155eae66cca68"),
        "user": ObjectId("664592366c287da0b2777324"),
        "year": 2024,
        "annualLeave": 3,
        "rollForward": 4,
        "medicalLeave": 10,
        "usedLeave": 12,
        "balance": 26,
        "studyLeave": 1
    },
    {
        "_id": ObjectId("6684244d74d155eae66cca6b"),
        "user": ObjectId("6647995d8f2bc3f1601cac7d"),
        "year": 2024,
        "annualLeave": 5,
        "rollForward": 5,
        "medicalLeave": 5,
        "usedLeave": 3,
        "balance": 17,
        "studyLeave": 2
    },
    {
        "_id": ObjectId("668423d774d155eae66cca69"),
        "user": ObjectId("666eeb6975f9a89b49394284"),
        "year": 2024,
        "annualLeave": 2,
        "rollForward": 3,
        "medicalLeave": 6,
        "usedLeave": 6,
        "balance": 13,
        "studyLeave": 2
    }
]

leave_balance = db.leave_balance
leave_balance.insert_many(leave_balance_data)

# Inserting data into tasks collection
tasks_data = [
    {
        "_id": ObjectId("664592376c287da0b2777327"),
        "engagementId": ObjectId("664592376c287da0b2777326"),
        "description": "Sign financial statements",
        "assignedTo": ObjectId("664592366c287da0b2777325"),
        "status": "Completed",
        "dueDate": datetime(2024, 5, 21),
        "timeEstimate": 480,
        "signedOffBy": ObjectId("664592366c287da0b2777325"),
        "signedOffDate": datetime(2024, 7, 3, 16, 33, 17),
        "timeCharge": 120
    },
    {
        "_id": ObjectId("6649010211317d053f63ff46"),
        "engagementId": ObjectId("664592376c287da0b2777326"),
        "description": "Review Draft FS",
        "assignedTo": ObjectId("664592366c287da0b2777325"),
        "status": "Pending",
        "dueDate": datetime(2024, 5, 21),
        "timeEstimate": 480
    },
    {
        "_id": ObjectId("664908b0f8869ba1d933705e"),
        "engagementId": ObjectId("664592376c287da0b2777326"),
        "description": "Cash and Bank Balances Section",
        "assignedTo": ObjectId("6647995d8f2bc3f16016ac7d"),
        "status": "Pending",
        "dueDate": datetime(2024, 5, 21),
        "timeEstimate": 480
    }
]

tasks = db.tasks
tasks.insert_many(tasks_data)

# Inserting data into engagements collection
engagements_data = [
    {
        "_id": ObjectId("664592376c287da0b2777326"),
        "clientName": "Crypto.com",
        "auditYear": datetime(2023, 12, 31),
        "description": "A company which provide trading crypto currency services",
        "budget": 15000,
        "partnerInCharge": ObjectId("664592366c287da0b2777325"),
        "manager": ObjectId("664592366c287da0b2777324"),
        "members": ObjectId("6647995d8f2bc3f1601cac7d"),
        "status": "Planning",
        "location": "Bishan",
        "industry": "Financial Services",
        "estStartDate": datetime(2024, 4, 1),
        "estEndDate": datetime(2024, 6, 30)
    },
    {
        "_id": ObjectId("6648faac11317d053f63ff45"),
        "clientName": "Learning Insights",
        "auditYear": datetime(2023, 12, 31),
        "description": "A company supply e-books",
        "budget": 25000,
        "partnerInCharge": ObjectId("666eeb6975f9a89b49394284"),
        "manager": ObjectId("664592366c287da0b2777324"),
        "members": ObjectId("6647995d8f2bc3f1601cac7d"),
        "status": "Planning",
        "location": "Bishan",
        "industry": "Manuafacturing",
        "estStartDate": datetime(2024, 5, 1),
        "estEndDate": datetime(2024, 6, 30)
    }
]

engagements = db.engagements
engagements.insert_many(engagements_data)


# Inserting data into engagements collection
scheduler_data = [
    {
        "_id": ObjectId("6672f4b8778f799a499bbf6a"),
        "employmentId": ObjectId("666eeb6975f9a89b49394284"),
        "engagementId": ObjectId("6648faac11317d053f63ff45"),
        "status": "Planning",
        "date": datetime(2024, 7, 11)
    },
    {
        "_id": ObjectId("6672f4b8778f799a499bbf6a"),
        "employmentId": ObjectId("666eeb6975f9a89b49394284"),
        "engagementId": ObjectId("6648faac11317d053f63ff45"),
        "status": "Planning",
        "date": datetime(2024, 7, 12)
    },
]

scheduler = db.scheduler
scheduler.insert_many(scheduler_data)

# Creating empty collections
empty_collections = ['desk_booking', 'leave_application', 'notifications']
for collection in empty_collections:
    db.create_collection(collection)

print("All data inserted successfully!")
