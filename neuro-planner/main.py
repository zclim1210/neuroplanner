import sys
print("Python path:", sys.path)
from NeuroPlannerCode import create_app
print("Import successful")

app = create_app()
print("App created successfully")

if __name__ == '__main__':
    print("Starting Flask app")
    app.run(debug=True)
    app.run(host="192.168.1.148")
    