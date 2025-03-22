# jenkins_dashboard_web.py

import os
import threading
from flask import Flask, render_template, jsonify, request, send_from_directory
from jenkins_dashboard_core_docker import JenkinsDashboardData
import logging

# Configure logging
logging.basicConfig(
    filename='logs/jenkins_web_dashboard.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Create dashboard data provider
# For Docker, read environment variables directly instead of using .env
jenkins_url = os.environ.get('JENKINS_URL', 'https://jenkins.example.com')
dashboard_data = JenkinsDashboardData(jenkins_url=jenkins_url)

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
    try:
        # Force data refresh but set a timeout
        refresh_thread = threading.Thread(target=dashboard_data.refresh_data)
        refresh_thread.daemon = True
        refresh_thread.start()

        # Wait for the refresh to complete, but not too long
        refresh_thread.join(timeout=5)

        # Get whatever data we have, even if incomplete
        data = dashboard_data.get_data()

        # If the refresh is still running, note that in the response
        if refresh_thread.is_alive():
            if data['error']:
                data['error'] += "; Some data may be incomplete (refresh still in progress)"
            else:
                data['error'] = "Some data may be incomplete (refresh still in progress)"
    except Exception as e:
        logger.error(f"Error in dashboard API endpoint: {e}")
        # Return whatever data we have, with the error noted
        data = dashboard_data.get_data()
        if data['error']:
            data['error'] += f"; Additional error: {str(e)}"
        else:
            data['error'] = str(e)

    # Add cache control headers to prevent browser caching
    response = jsonify(data)
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
    # Create logs directory
    os.makedirs('logs', exist_ok=True)

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

    # Run the Flask app - bind to 0.0.0.0 to be accessible from outside the container
    print("Starting Jenkins Web Dashboard...")
    logger.info("Starting Jenkins Web Dashboard...")
    app.run(debug=False, host='0.0.0.0', port=5000)