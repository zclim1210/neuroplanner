from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from flask import Flask
import certifi

# Setup Flask and Bcrypt
app = Flask(__name__)
bcrypt = Bcrypt(app)

# Connect to MongoDB
client = MongoClient("mongodb+srv://<username>:<password>@neuroplanner.<xxxxxx>.mongodb.net/?retryWrites=true&w=majority&appName=NeuroPlanner",tlsCAFile=certifi.where())
db = client['NeoroPlanner']

# The new password you want to set
new_password = "arull"

# Hash the new password
hashed_new_password = bcrypt.generate_password_hash(new_password).decode('utf-8')

# Find John's user document and update the password
result = db.users.update_one(
    {"email": "arull@neuro.com"},  # Query to find John's document
    {"$set": {"password": hashed_new_password}}  # Update operation
)

if result.modified_count > 0:
    print("John's password was updated successfully.")
else:
    print("John's password update failed or no changes were made.")
