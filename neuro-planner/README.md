
# NeuroPlanner Project - Detailed Setup Guide

Welcome to the NeuroPlanner project. This guide will walk you through the detailed steps required to set up and run the project using Visual Studio Code (VS Code). Please follow the steps carefully to ensure a successful setup.

## Table of Contents

1. [Background](#background)
2. [Prerequisites](#prerequisites)
3. [Setup Instructions](#setup-instructions)
   - [1. Install Visual Studio Code](#1-install-visual-studio-code)
   - [2. Install Required Extensions](#2-install-required-extensions)
   - [3. Clone the Repository](#3-clone-the-repository)
   - [4. Install Python](#4-install-python)
   - [5. Install Project Dependencies](#5-install-project-dependencies)
   - [6. Configure MongoDB Atlas](#6-configure-mongodb-atlas)
   - [7. Run the Project](#7-run-the-project)

## Background

The NeuroPlanner project is a web application designed to manage employee schedules, resources, and leave records. The project uses the following technologies:
- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Database**: MongoDB Atlas (cloud database)
- **Machine Learning**: Scikit-learn, NumPy, pandas
- **Chatbot**: OpenAI ChatGPT API integration

## Prerequisites

Before setting up the project, ensure you have the following installed:
- [Visual Studio Code](https://code.visualstudio.com/)
- [Python](https://www.python.org/downloads/) (version 3.8 or higher)
- [Git](https://git-scm.com/downloads)
- [MongoDB Atlas Account](https://www.mongodb.com/atlas)

## Setup Instructions

### 1. Install Visual Studio Code

1. Download and install Visual Studio Code from the [official website](https://code.visualstudio.com/).
2. Launch Visual Studio Code after installation.

### 2. Install Required Extensions

1. Open Visual Studio Code.
2. Go to the Extensions view by clicking on the Extensions icon in the Activity Bar on the side of the window or by pressing `Ctrl+Shift+X`.
3. Install the following extensions:
   - Python (ms-python.python)
   - MongoDB for VS Code (mongodb.mongodb-vscode)
   - Pylance (ms-python.vscode-pylance)

### 3. Clone the Repository

1. Open Visual Studio Code.
2. Open the Command Palette by pressing `Ctrl+Shift+P`.
3. Type `Git: Clone` and select the option.
4. Enter the repository URL and select a local folder to clone the repository into.

### 4. Install Python

1. Download and install Python from the [official website](https://www.python.org/downloads/).
2. Ensure that Python is added to your system PATH during the installation.


### 5. Install Project Dependencies

1. With the virtual environment activated, run the following command to install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 6. Configure MongoDB Atlas

1. Create a MongoDB Atlas account at [mongodb.com](https://www.mongodb.com/cloud/atlas). Verify your email and log in. Complete the "Get to know you" stage by answering the following:
   - **Programming Language**: Python
   - **Data Types**: Time series data
   - **Architectural Models**: Not sure
2. Deploy a new cluster:
   - Choose **M0** for the free tier (512MB storage).
   - Name the cluster **NeuroPlanner** (this name is compulsory).
   - Select **AWS** as the provider.
   - Ensure **Automate security setup** and **Preload sample dataset** are ticked.
3. Configure network access:
   - Add your current IP address or another as needed.
4. Create a database user:
   - Set a username and password, then click **Create database user**.
5. Obtain the **connection string**:
   - Format: `mongodb+srv://<username>:<password>@neuroplanner.<xxxxxx>.mongodb.net/?retryWrites=true&w=majority&appName=NeuroPlanner`
   - Replace `<username>`,`<password>`and `<xxxxxx>` with your credentials.

6. Create the database and collection:
   - Open **Browse Collections**.
   - Create a database named `NeoroPlanner` (ensure the name is exact,suggest to direct copy and paste!!!!).
   - Create a collection named `users`.
   - Populate the database using run the`populate_db.py` with the connection string updated in `MongoClient`. you will see print("All data inserted successfully!"), means data is preset correctly in the database.

7. If you encounter issues, email the Neuro team at "zclim1210@gmail.com" to receive an invitation and the connection string.


### 7. Run the Project

1. Create a `.env` file in the project root directory and add the following environment variables:
   ```env
   MONGO_URI=mongodb+srv://<username>:<password>@neuroplanner.<xxxxxx>.mongodb.net/?retryWrites=true&w=majority&appName=NeuroPlanner
   SECRET_KEY=XXXXXX
   DB_NAME=NeoroPlanner
   OPENAI_API_KEY=sk-XXXXXX
   ```
   Replace `<username>`,`<password>`and `<xxxxxx>` with your credentials.
2. Open main.py and run.
3. Open a web browser and go to `http://127.0.0.1:5000/` to access the application.

If you encounter any issues during the setup, please call me at +65 81720630 for assistance.

## Project Structure

Here's a brief overview of the project structure:

```
neuroplanner/
├── static/
│   ├── css/
│   ├── images/
│   ├── js/
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── login.html
│   ├── signup.html
├── .env
├── main.py
├── requirements.txt
├── README.md
```

## Neuro Planner - Initial Data and User Roles

### User Accounts

### Jane (Partner)
- **Email:** jane@neuro.com
- **Password:** Jane
- **Role:** Partner
- **Background:**
  - Partner in charge of the "Crypto.com" engagement.
  - Can create new engagements, plot new tasks, and manage the schedule by dragging and dropping tasks.
  - Leave requests by Jane are directly approved.

### John (Manager)
- **Email:** john@neuro.com
- **Password:** John
- **Role:** Manager
- **Background:**
  - Reports to Jane and handles day-to-day management tasks.
  - Leave requests by John will be pending approval by Jane.
  - Notifications regarding John's leave requests will be handled on the chatbot page.

### Tesla (Senior Associate)
- **Email:** tesla@neuro.com
- **Password:** Tesla
- **Role:** Senior Associate
- **Background:**
  - Works on various tasks under the supervision of John.
  - Leave requests by Tesla will be subject to approval by John.

### Tim (Partner)
- **Email:** tim@neuro.com
- **Password:** Tim
- **Role:** Partner
- **Background:**
  - Another partner in the firm.
  - Can manage engagements and tasks similarly to Jane.
  - Leave requests by Tim are directly approved.

## Sign-Up Limitations
New user sign-up requests are pending approval by HR. The HR feature is not implemented in the MVP stage. Therefore, the Neuro team suggests using the provided user accounts for demo purposes.

## Important Notes
- Only Jane and Tim (Partners) can plot the calendar and swap the calendar with drag and drop function and drop to dustbin function.
- Please use their accounts to trial features such as engagement creation and task management.



Thank you for setting up the NeuroPlanner project. Enjoy using it!
pip install weasyprint - for pdf