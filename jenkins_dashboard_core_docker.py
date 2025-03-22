# jenkins_dashboard_core.py

import os
import json
import logging
import time
import threading
import re  # For regex pattern matching
from datetime import datetime
from flask import Flask, render_template, jsonify

# Import the JenkinsConnector from your module
from jenkins_connector_docker import JenkinsConnector, JenkinsAuthenticationError

# Configure logging - ensure logs go to a location accessible in Docker
log_directory = 'logs'
os.makedirs(log_directory, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_directory, 'jenkins_web_dashboard.log'),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JenkinsDashboardData:
    def __init__(self, jenkins_url=None):
        """
        Initialize the Jenkins dashboard data provider.

        :param jenkins_url: Optional Jenkins URL, otherwise from environment
        """
        # Get Jenkins URL from parameter, environment, or use default
        self.jenkins_url = jenkins_url or os.environ.get('JENKINS_URL')

        if not self.jenkins_url:
            logger.error("No Jenkins URL provided. Check environment variables or parameters.")
            self.jenkins_url = 'https://jenkins.example.com'  # Fallback for initialization only

        # Create Jenkins connector
        self.connector = JenkinsConnector(jenkins_url=self.jenkins_url)

        self.refresh_interval = int(os.environ.get('REFRESH_INTERVAL', 30))  # seconds
        self.dashboard_data = {
            'running_builds': [],
            'queued_builds': [],
            'latest_builds': [],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': None
        }

        # Start background refresh thread
        self.stop_thread = False
        self.data_thread = threading.Thread(target=self._refresh_data_thread)
        self.data_thread.daemon = True
        self.data_thread.start()

    def _get_job_name_from_url(self, url):
        """
        Extract the job name from a Jenkins URL.

        :param url: Jenkins URL for the job
        :return: Job name
        """
        if not url:
            return "Unknown"

        # Remove trailing slash if present
        if url.endswith('/'):
            url = url[:-1]

        # Get the last part of the URL
        job_parts = url.split('/')

        # The job name is typically the last part after 'job'
        for i, part in enumerate(job_parts):
            if part == 'job' and i + 1 < len(job_parts):
                return job_parts[i + 1]

        # If we can't determine the job name, return the last part
        return job_parts[-1]

    def _get_build_info(self, build):
        """
        Extract relevant information from a build.

        :param build: Build information dictionary
        :return: Dictionary with formatted build information
        """
        # Log available fields for debugging
        logger.debug(f"Build fields: {list(build.keys())}")

        # First, determine the job name (for the JOB NAME column)
        if 'jobName' in build:
            job_name = build['jobName']
        elif 'jobFullName' in build:
            job_name = build['jobFullName']
        elif 'jobDisplayName' in build:
            job_name = build['jobDisplayName']
        elif 'job' in build and 'name' in build['job']:
            job_name = build['job']['name']
        elif 'job' in build and 'fullName' in build['job']:
            job_name = build['job']['fullName']
        else:
            # Fall back to URL parsing if job name not available
            job_name = self._get_job_name_from_url(build.get('url', ''))

        # Now, determine the build display name
        # This should be different from the job name and include build-specific information
        build_number = build.get('number', 'N/A')

        # Try to extract branch information from various possible sources
        branch = None

        # Check for parameters that might contain branch info
        if 'actions' in build:
            for action in build.get('actions', []):
                # Check for parameters action
                if 'parameters' in action:
                    for param in action['parameters']:
                        if param.get('name', '').lower() in ['branch', 'git_branch']:
                            branch = param.get('value', '')
                            logger.info(f"Found branch in parameters: {branch}")
                            break

                # Check for causes which might contain branch info
                if 'causes' in action:
                    for cause in action.get('causes', []):
                        if 'shortDescription' in cause:
                            desc = cause['shortDescription']
                            if 'branch' in desc.lower():
                                # Try to extract branch from description
                                branch_parts = desc.split('branch')
                                if len(branch_parts) > 1:
                                    potential_branch = branch_parts[1].strip().strip(':').strip()
                                    if potential_branch and not branch:  # Don't overwrite if we already found a branch
                                        branch = potential_branch
                                        logger.info(f"Found branch in cause description: {branch}")

        # Also check for any branch info in the display name or full display name
        if not branch:
            full_display = build.get('fullDisplayName', '')
            if 'branch' in full_display.lower():
                branch_match = re.search(r'branch[:\s]+([^\s\]]+)', full_display, re.IGNORECASE)
                if branch_match:
                    branch = branch_match.group(1)
                    logger.info(f"Found branch in full display name: {branch}")

        # Try different fields for display name in order of preference
        if 'fullDisplayName' in build and build['fullDisplayName']:
            # Extract just the build-specific part if possible
            full_display = build['fullDisplayName']

            # If the full display starts with the job name, try to extract just the build part
            if full_display.startswith(job_name):
                build_display = full_display[len(job_name):].strip()
            else:
                build_display = full_display
        elif 'displayName' in build and build['displayName']:
            build_display = build['displayName']
        else:
            # Fall back to just the build number
            build_display = f"#{build_number}"

        # If the build display is empty or just whitespace, use the build number
        if not build_display or build_display.isspace():
            build_display = f"#{build_number}"

        # If build display doesn't start with #, add it for clarity
        if not build_display.startswith('#'):
            build_display = f"#{build_number} - {build_display}"

        # Check if 'devops' appears in the display for staging builds and needs branch info
        if ' - devops' in build_display and branch:
            # Format: #381 - devops - [branch]
            if not f" - [{branch}]" in build_display:
                build_display = build_display + f" - [{branch}]"
        # For other builds, add branch if it's available and not already in the display
        elif branch and not f"[{branch}]" in build_display:
            build_display = build_display + f" - [{branch}]"

        # Calculate progress percentage
        progress_pct = 0
        if 'estimatedDuration' in build and build['estimatedDuration'] > 0 and 'timestamp' in build:
            elapsed = int(time.time() * 1000) - build['timestamp']
            progress_pct = min(100, int((elapsed / build['estimatedDuration']) * 100))

        # Calculate remaining time
        remaining = "Unknown"
        if 'estimatedDuration' in build and build['estimatedDuration'] > 0 and 'timestamp' in build:
            current_time = int(time.time() * 1000)
            time_elapsed = current_time - build['timestamp']
            time_remaining = build['estimatedDuration'] - time_elapsed

            if time_remaining <= 0:
                remaining = "Overdue"
            else:
                minutes = int(time_remaining / 60000)
                seconds = int((time_remaining % 60000) / 1000)
                remaining = f"{minutes}m {seconds}s"

        # Log what we've determined
        logger.info(f"JOB NAME: {job_name}")
        logger.info(f"BUILD DISPLAY: {build_display}")
        if branch:
            logger.info(f"BRANCH: {branch}")

        return {
            'id': build.get('id', 'unknown'),
            'job_name': job_name,
            'build_number': build_number,
            'build_display': build_display,
            'estimated_duration': f"{build.get('estimatedDuration', 0) / 60000:.1f}m",
            'progress': progress_pct,
            'remaining': remaining,
            'url': build.get('url', ''),
            'timestamp': build.get('timestamp', 0),
            'branch': branch
        }

    def _get_completed_build_info(self, build):
        """
        Extract relevant information from a completed build.

        :param build: Build information dictionary
        :return: Dictionary with formatted build information
        """
        # Many of the same steps as _get_build_info
        # First, determine the job name
        if 'jobName' in build:
            job_name = build['jobName']
        elif 'fullDisplayName' in build:
            # Try to extract job name from fullDisplayName (format usually: "job_name #number")
            parts = build['fullDisplayName'].split(' #', 1)
            if len(parts) == 2:
                job_name = parts[0]
            else:
                job_name = self._get_job_name_from_url(build.get('url', ''))
        else:
            # Fall back to URL parsing if job name not available
            job_name = self._get_job_name_from_url(build.get('url', ''))

        # Get the build number
        build_number = build.get('number', 'N/A')

        # Get the build result
        result = build.get('result', 'UNKNOWN')

        # Format duration
        duration_ms = build.get('duration', 0)
        duration = f"{duration_ms / 60000:.1f}m"

        # Format timestamp
        timestamp_ms = build.get('timestamp', 0)
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')

        # Extract branch information (simplified version)
        branch = None
        if 'actions' in build:
            for action in build.get('actions', []):
                if 'parameters' in action:
                    for param in action['parameters']:
                        if param.get('name', '').lower() in ['branch', 'git_branch']:
                            branch = param.get('value', '')
                            break

        return {
            'id': build.get('id', 'unknown'),
            'job_name': job_name,
            'build_number': build_number,
            'result': result,
            'duration': duration,
            'timestamp': timestamp,
            'url': build.get('url', ''),
            'branch': branch
        }

    def _get_queue_info(self, queue_item):
        """
        Extract relevant information from a queued build.

        :param queue_item: Queue item information dictionary
        :return: Dictionary with formatted queue information
        """
        job_name = "Unknown"
        if 'task' in queue_item and 'name' in queue_item['task']:
            job_name = queue_item['task']['name']

        why = queue_item.get('why', 'Unknown reason')

        # Calculate how long the item has been in queue
        queue_time = "Unknown"
        waiting_ms = 0
        if 'inQueueSince' in queue_item:
            queue_time_ms = queue_item['inQueueSince']
            waiting_ms = int(time.time() * 1000) - queue_time_ms
            minutes = int(waiting_ms / 60000)
            seconds = int((waiting_ms % 60000) / 1000)

            if minutes > 0:
                queue_time = f"{minutes}m {seconds}s"
            else:
                queue_time = f"{seconds}s"

        return {
            'id': queue_item.get('id', 'N/A'),
            'job_name': job_name,
            'why': why,
            'waiting_time': queue_time,
            'waiting_ms': waiting_ms,
            'queued_since': queue_item.get('inQueueSince', 0)
        }

    def _refresh_data_thread(self):
        """
        Background thread to refresh dashboard data periodically.
        """
        while not self.stop_thread:
            try:
                self.refresh_data()
            except Exception as e:
                logger.error(f"Error in refresh thread: {e}")
                self.dashboard_data['error'] = str(e)

            # Sleep for the refresh interval
            for _ in range(self.refresh_interval * 10):
                if self.stop_thread:
                    break
                time.sleep(0.1)

    def refresh_data(self):
        """
        Refresh all dashboard data.
        """
        try:
            logger.info("Refreshing dashboard data...")

            # Results storage
            formatted_builds = []
            formatted_queue = []
            formatted_latest = []
            errors = []

            # Get running builds - handle potential failures gracefully
            try:
                running_builds = self.connector.get_running_builds()
                formatted_builds = [self._get_build_info(build) for build in running_builds]
                # Sort running builds by progress (descending)
                formatted_builds.sort(key=lambda x: x['progress'], reverse=True)
            except Exception as e:
                error_msg = f"Error fetching running builds: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

            # Get queued builds - handle potential failures gracefully
            try:
                queued_builds = self.connector.get_build_queue()
                formatted_queue = [self._get_queue_info(item) for item in queued_builds]
                # Sort queued builds by waiting time (descending)
                formatted_queue.sort(key=lambda x: x['waiting_ms'], reverse=True)
            except Exception as e:
                error_msg = f"Error fetching queued builds: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

            # Get latest builds (new feature) - handle potential failures gracefully
            try:
                latest_builds = self.connector.get_latest_builds(limit=20)
                formatted_latest = [self._get_completed_build_info(build) for build in latest_builds]
            except Exception as e:
                error_msg = f"Error fetching latest builds: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

            # Create error message if any errors occurred
            error_message = None
            if errors:
                error_message = "; ".join(errors)

            # Update dashboard data with what we have, even if some parts failed
            self.dashboard_data = {
                'running_builds': formatted_builds,
                'queued_builds': formatted_queue,
                'latest_builds': formatted_latest,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': error_message
            }

            logger.info(f"Dashboard data refreshed: {len(formatted_builds)} running, {len(formatted_queue)} queued, {len(formatted_latest)} latest")

        except Exception as e:
            logger.error(f"Error refreshing data: {e}")
            self.dashboard_data['error'] = str(e)
            self.dashboard_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def get_data(self):
        """
        Get the current dashboard data.

        :return: Dictionary with running builds and queue information
        """
        return self.dashboard_data

    def shutdown(self):
        """
        Clean shutdown of the dashboard data provider.
        """
        self.stop_thread = True
        if self.data_thread.is_alive():
            self.data_thread.join(2)
            logger.info("Dashboard data thread stopped")