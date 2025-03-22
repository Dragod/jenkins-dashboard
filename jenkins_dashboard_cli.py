# jenkins_dashboard_cli.py

import os
import time
import curses
import logging
from datetime import datetime
from dotenv import load_dotenv

# Import the JenkinsConnector from your module
from jenkins_connector import JenkinsConnector, JenkinsAuthenticationError

# Configure logging
logging.basicConfig(
    filename='jenkins_dashboard_cli.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JenkinsDashboardCLI:
    def __init__(self, jenkins_connector):
        """
        Initialize the Jenkins dashboard.

        :param jenkins_connector: Initialized JenkinsConnector instance
        """
        self.connector = jenkins_connector
        self.refresh_interval = 10  # seconds

        # Define column positions and widths
        self.columns = {
            'job_name': {'start': 0, 'width': 200, 'title': "JOB NAME"},
            'build': {'start': 50, 'width': 400, 'title': "BUILD"},
            'duration': {'start': 110, 'width': 12, 'title': "DURATION"},
            'remaining': {'start': 120, 'width': 15, 'title': "REMAINING"}
        }

    def _format_time_remaining(self, build):
        """
        Format the estimated time remaining for a build.

        :param build: Build information dictionary
        :return: Formatted time string
        """
        if 'estimatedDuration' not in build or 'timestamp' not in build:
            return "Unknown"

        # Calculate time elapsed and estimated total time
        current_time = int(time.time() * 1000)  # Jenkins uses milliseconds
        time_elapsed = current_time - build['timestamp']

        # If estimated duration is 0, we can't make a prediction
        if build['estimatedDuration'] == 0:
            return "Unknown"

        # Calculate remaining time
        time_remaining = build['estimatedDuration'] - time_elapsed

        # If already past estimated time
        if time_remaining <= 0:
            return "Overdue"

        # Convert to minutes and seconds
        minutes = int(time_remaining / 60000)
        seconds = int((time_remaining % 60000) / 1000)

        return f"{minutes}m {seconds}s"

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

        # Now, determine the build display name (for the BUILD column)
        # This should be different from the job name and include build-specific information
        build_number = build.get('number', 'N/A')

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

        # Log what we've determined
        logger.info(f"JOB NAME: {job_name}")
        logger.info(f"BUILD DISPLAY: {build_display}")

        return {
            'job_name': job_name,
            'build_number': build_number,
            'build_display': build_display,
            'duration': f"{build.get('estimatedDuration', 0) / 60000:.1f}m",
            'progress': self._format_time_remaining(build),
            'url': build.get('url', '')
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

        # Get when the item was queued
        queued_time = "Unknown"
        if 'inQueueSince' in queue_item:
            queue_time_ms = queue_item['inQueueSince']
            queue_datetime = datetime.fromtimestamp(queue_time_ms / 1000)
            queued_time = queue_datetime.strftime('%H:%M:%S')

        return {
            'job_name': job_name,
            'why': why,
            'queued_since': queued_time,
            'id': queue_item.get('id', 'N/A')
        }

    def get_dashboard_data(self):
        """
        Get all data needed for the dashboard.

        :return: Dictionary with running builds and queue information
        """
        try:
            # Get running builds
            running_builds = self.connector.get_running_builds()
            formatted_builds = [self._get_build_info(build) for build in running_builds]

            # Get queued builds
            queued_builds = self.connector.get_build_queue()
            formatted_queue = [self._get_queue_info(item) for item in queued_builds]

            return {
                'running_builds': formatted_builds,
                'queued_builds': formatted_queue,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': None
            }
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {
                'running_builds': [],
                'queued_builds': [],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': str(e)
            }

    def _safe_addstr(self, stdscr, y, x, text, attr=0):
        """
        Safely add a string to the curses window, handling potential errors.

        :param stdscr: Curses window
        :param y: Y coordinate
        :param x: X coordinate
        :param text: Text to display
        :param attr: Text attributes
        """
        height, width = stdscr.getmaxyx()

        # Make sure we're not trying to write outside the window
        if y >= height or x >= width:
            return

        # Truncate text if it would exceed window width
        max_length = width - x - 1
        if max_length <= 0:
            return

        text = str(text)[:max_length]

        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            # Silently handle any curses errors
            pass

    def _format_column_text(self, text, width):
        """
        Format text to fit within a column with proper truncation.

        :param text: Text to format
        :param width: Column width
        :return: Formatted text
        """
        text = str(text)
        if len(text) > width:
            return text[:width-3] + "..."
        return text

    def run_cli_dashboard(self, stdscr):
        """
        Run the dashboard in command-line interface mode.

        :param stdscr: Curses window object
        """
        # Set up curses
        curses.curs_set(0)  # Hide cursor
        curses.use_default_colors()  # Use terminal's default colors
        stdscr.nodelay(1)  # Non-blocking input
        stdscr.timeout(100)  # Check for input every 100ms

        # Color pairs
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # Green for running
        curses.init_pair(2, curses.COLOR_YELLOW, -1)  # Yellow for waiting
        curses.init_pair(3, curses.COLOR_RED, -1)  # Red for error
        curses.init_pair(4, curses.COLOR_CYAN, -1)  # Cyan for headers

        running = True
        last_refresh = 0
        data = {
            'running_builds': [],
            'queued_builds': [],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': None
        }

        while running:
            try:
                current_time = time.time()

                # Check for key presses
                key = stdscr.getch()
                if key == ord('q'):
                    running = False
                    break
                elif key == ord('r'):
                    last_refresh = 0  # Force refresh

                # Refresh data if needed
                if current_time - last_refresh >= self.refresh_interval:
                    try:
                        data = self.get_dashboard_data()
                        last_refresh = current_time
                    except Exception as e:
                        logger.error(f"Failed to refresh data: {e}")
                        data['error'] = str(e)
                        data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Clear screen
                stdscr.clear()

                # Get terminal dimensions
                max_y, max_x = stdscr.getmaxyx()

                # Draw header
                header = f" JENKINS BUILD DASHBOARD | {data['timestamp']} | Press 'q' to quit, 'r' to refresh "
                self._safe_addstr(stdscr, 0, 0, header[:max_x-1], curses.A_REVERSE)

                # Draw error message if any
                if data.get('error'):
                    error_msg = f"ERROR: {data['error']}"
                    self._safe_addstr(stdscr, 1, 0, error_msg[:max_x-1], curses.color_pair(3))

                # Draw running builds section
                self._safe_addstr(stdscr, 2, 0, "RUNNING BUILDS:", curses.color_pair(4) | curses.A_BOLD)

                if data.get('running_builds'):
                    # Table header
                    for col_name, col_info in self.columns.items():
                        self._safe_addstr(stdscr, 3, col_info['start'], col_info['title'], curses.A_UNDERLINE)

                    # Table content
                    max_builds = max_y - 10  # Limit based on terminal height
                    for i, build in enumerate(data['running_builds'][:max_builds]):
                        y_pos = 4 + i

                        # Job name
                        job_name = self._format_column_text(build['job_name'], self.columns['job_name']['width'])
                        self._safe_addstr(stdscr, y_pos, self.columns['job_name']['start'], job_name, curses.color_pair(1))

                        # Build display name
                        build_display = self._format_column_text(
                            build.get('build_display', f"#{build['build_number']}"),
                            self.columns['build']['width']
                        )
                        self._safe_addstr(stdscr, y_pos, self.columns['build']['start'], build_display)

                        # Duration
                        self._safe_addstr(stdscr, y_pos, self.columns['duration']['start'], build['duration'])

                        # Progress
                        attr = 0
                        if build['progress'] == "Overdue":
                            attr = curses.color_pair(3)
                        self._safe_addstr(stdscr, y_pos, self.columns['remaining']['start'], build['progress'], attr)
                else:
                    self._safe_addstr(stdscr, 4, 0, "No builds currently running", curses.color_pair(2))

                # Calculate starting position for queue section
                queue_start_y = min(max_y - 10, 6 + len(data.get('running_builds', [])))

                # Draw build queue section if there's room
                if queue_start_y < max_y - 2:
                    self._safe_addstr(stdscr, queue_start_y, 0, "BUILD QUEUE:", curses.color_pair(4) | curses.A_BOLD)

                    if data.get('queued_builds'):
                        # Table header for queue
                        self._safe_addstr(stdscr, queue_start_y + 1, self.columns['job_name']['start'], "JOB NAME", curses.A_UNDERLINE)
                        self._safe_addstr(stdscr, queue_start_y + 1, self.columns['build']['start'], "QUEUED SINCE", curses.A_UNDERLINE)
                        self._safe_addstr(stdscr, queue_start_y + 1, self.columns['duration']['start'], "REASON", curses.A_UNDERLINE)

                        # Table content
                        max_queue_items = max_y - queue_start_y - 4  # Limit based on remaining space
                        for i, item in enumerate(data['queued_builds'][:max_queue_items]):
                            y_pos = queue_start_y + 2 + i

                            # Job name
                            job_name = self._format_column_text(item['job_name'], self.columns['job_name']['width'])
                            self._safe_addstr(stdscr, y_pos, self.columns['job_name']['start'], job_name, curses.color_pair(2))

                            # Queued since
                            self._safe_addstr(stdscr, y_pos, self.columns['build']['start'], item['queued_since'])

                            # Reason
                            reason = self._format_column_text(item['why'], max_x - self.columns['duration']['start'] - 1)
                            self._safe_addstr(stdscr, y_pos, self.columns['duration']['start'], reason)
                    else:
                        self._safe_addstr(stdscr, queue_start_y + 1, 0, "No builds in queue", curses.color_pair(2))

                # Draw footer with stats
                footer = f" Running: {len(data.get('running_builds', []))} | Queued: {len(data.get('queued_builds', []))} | Next refresh: {int(self.refresh_interval - (current_time - last_refresh))}s "
                self._safe_addstr(stdscr, max_y-1, 0, footer[:max_x-1], curses.A_REVERSE)

                # Refresh the screen
                stdscr.refresh()

            except curses.error as e:
                # Handle any curses errors
                logger.error(f"Curses error: {e}")
                # Continue execution rather than crashing

            except Exception as e:
                # Log any other exceptions but try to continue
                logger.error(f"Error in dashboard loop: {e}")
                time.sleep(1)  # Pause briefly

            # Sleep to reduce CPU usage
            time.sleep(0.1)

def main():
    # Load environment variables from .env file
    load_dotenv()

    # Get Jenkins URL from environment or use default
    jenkins_url = os.environ.get('JENKINS_URL', 'https://jenkins.example.com')
    verify_ssl = os.environ.get('JENKINS_VERIFY_SSL', 'False').lower() == 'true'

    try:
        # Create Jenkins connector using credentials from .env file
        print(f"Connecting to Jenkins at {jenkins_url}...")
        print(f"SSL verification {'enabled' if verify_ssl else 'disabled'}")

        connector = JenkinsConnector(jenkins_url, verify_ssl=verify_ssl, timeout=30)

        # Test connection before starting the dashboard
        if not connector.test_connection():
            print("Failed to connect to Jenkins server.")
            print("Please check your connection, credentials, and server status.")
            return

        print("Connected successfully to Jenkins server.")

        # Create dashboard
        dashboard = JenkinsDashboardCLI(connector)

        # Run the CLI dashboard
        print("Starting Jenkins Build Dashboard...")
        print("Press 'q' to quit, 'r' to refresh manually.")
        curses.wrapper(dashboard.run_cli_dashboard)

    except JenkinsAuthenticationError as e:
        print(f"Jenkins Authentication Failed: {e}")
        print("\nTroubleshooting Tips:")
        print("1. Verify your Jenkins username")
        print("2. Check that your API token is correct")
        print("3. Ensure the user has appropriate permissions")
        print("4. Check your .env file is properly configured")

    except Exception as e:
        print(f"Unexpected error: {e}")
        print("\nPlease check your network connection and Jenkins server status.")

if __name__ == '__main__':
    main()