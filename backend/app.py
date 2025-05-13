from flask import Flask, jsonify, redirect
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allows cross-origin requests (like from Vite)

# Redirect root path to the API
@app.route('/')
def index():
    return redirect('/api/hello')

# Working API endpoint
@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify({"message": "Hello from Flask backend!"})

# Run the server
if __name__ == '__main__':
    app.run(debug=True, port=5000)