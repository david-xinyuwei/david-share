"""
Health check endpoint for Azure App Service
"""
from flask import Flask, jsonify
import sys

app = Flask(__name__)

@app.route('/healthz')
def health_check():
    """Health check endpoint required by Azure App Service"""
    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
        "python_version": sys.version
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
