# jenkins_dashboard_web.py

import os
from flask import Flask, render_template, jsonify, request, send_from_directory
from jenkins_dashboard_core_docker import JenkinsDashboardData
import logging

# Configure logging
logging.basicConfig(
    filename='jenkins_web_dashboard.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Create dashboard data provider
dashboard_data = JenkinsDashboardData()

# Configure static files
@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files."""
    return send_from_directory('static', path)

@app.route('/')
def index():
    """Render the dashboard page."""
    return render_template('index.html')

@app.route('/api/dashboard')
def api_dashboard():
    """API endpoint for dashboard data."""
    # Force data refresh on each request
    dashboard_data.refresh_data()

    # Add cache control headers to prevent browser caching
    response = jsonify(dashboard_data.get_data())
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    """API endpoint to force a data refresh."""
    try:
        dashboard_data.refresh_data()
        return jsonify({'status': 'success', 'message': 'Data refreshed'})
    except Exception as e:
        logger.error(f"Error during forced refresh: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.teardown_appcontext
def shutdown_dashboard(exception=None):
    """Clean shutdown when Flask app exits."""
    dashboard_data.shutdown()

def create_directories():
    """Create necessary directories if they don't exist."""
    # Create templates directory
    os.makedirs('templates', exist_ok=True)

    # Create static directory
    os.makedirs('static', exist_ok=True)

    # Check for template file
    template_path = os.path.join('templates', 'index.html')
    if not os.path.exists(template_path):
        logger.warning(f"Template file {template_path} not found.")
        print(f"Warning: Template file {template_path} not found.")
        print("Please create the template file before running the application.")

    # Check for JavaScript file
    js_path = os.path.join('static', 'dashboard.js')
    if not os.path.exists(js_path):
        logger.warning(f"JavaScript file {js_path} not found.")
        print(f"Warning: JavaScript file {js_path} not found.")
        print("Please create the JavaScript file before running the application.")

if __name__ == '__main__':
    # Create directories and check for necessary files
    create_directories()

    # Run the Flask app
    print("Starting Jenkins Web Dashboard...")
    logger.info("Starting Jenkins Web Dashboard...")
    app.run(debug=True, host='0.0.0.0', port=5000)