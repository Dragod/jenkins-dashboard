# jenkins_connector.py

import requests
import base64
import logging
import os
import urllib.parse
import urllib3
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv


# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JenkinsAuthenticationError(Exception):
    """Custom exception for Jenkins authentication issues"""
    pass

class JenkinsConnector:
    def __init__(self, jenkins_url, username=None, api_token=None, verify_ssl=False, timeout=30):
        """
        Initialize Jenkins connection with authentication handling.

        :param jenkins_url: Base URL of Jenkins server (can include credentials in format https://user:token@jenkins.example.com)
        :param username: Jenkins username (optional, can use environment variable)
        :param api_token: Jenkins API token (optional, can use environment variable)
        :param verify_ssl: Whether to verify SSL certificates (default: False)
        :param timeout: Connection timeout in seconds (default: 30)
        """
        # Check if credentials are embedded in the URL
        if '@' in jenkins_url:
            # Extract credentials and clean URL
            try:
                auth_part, server_part = jenkins_url.split('@', 1)
                protocol = auth_part.split('://', 1)[0]
                credentials = auth_part.split('://', 1)[1]
                embedded_username, embedded_token = credentials.split(':', 1)

                # Set the clean URL without credentials
                self.jenkins_url = f"{protocol}://{server_part}".rstrip('/')

                # Use embedded credentials if provided
                self.username = username or embedded_username
                self.api_token = api_token or embedded_token

                logger.info(f"Using credentials embedded in URL for {self.jenkins_url}")
            except Exception as e:
                logger.error(f"Failed to parse credentials from URL: {e}")
                self.jenkins_url = jenkins_url.rstrip('/')
                self.username = username or os.environ.get('JENKINS_USERNAME')
                self.api_token = api_token or os.environ.get('JENKINS_API_TOKEN')
        else:
            # Standard URL without embedded credentials
            self.jenkins_url = jenkins_url.rstrip('/')

            # Prioritize passed parameters, then environment variables
            self.username = username or os.environ.get('JENKINS_USERNAME')
            self.api_token = api_token or os.environ.get('JENKINS_API_TOKEN')

        # Validate credentials
        if not self.username or not self.api_token:
            raise JenkinsAuthenticationError(
                "Missing credentials. "
                "Please provide username and API token either as arguments, in the URL, or as environment variables."
            )

        # Connection settings
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        # Prepare authentication methods
        self.basic_auth = HTTPBasicAuth(self.username, self.api_token)
        self.headers = {
            'Authorization': f'Basic {base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()}',
            'Accept': 'application/json'
        }

        # Create a session for persistent connections
        self.session = requests.Session()
        self.session.auth = self.basic_auth
        self.session.headers.update(self.headers)
        self.session.verify = self.verify_ssl

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Check for proxy settings
        proxies = {
            'http': os.environ.get('HTTP_PROXY'),
            'https': os.environ.get('HTTPS_PROXY')
        }
        if proxies['http'] or proxies['https']:
            self.session.proxies = proxies
            logger.info("Using proxy settings from environment variables")

        # Crumb data will be obtained when needed
        self.crumb = None

    def _validate_credentials(self):
        """
        Perform a credential validation check.

        :return: True if credentials are valid, False otherwise
        """
        try:
            # Attempt to get a minimal Jenkins API endpoint
            response = self.session.get(
                f'{self.jenkins_url}/api/json',
                params={'depth': 1, 'tree': 'mode'},
                timeout=self.timeout
            )

            # Check response status
            if response.status_code == 200:
                logger.info("Credentials validated successfully")
                return True
            elif response.status_code == 401:
                logger.error("Authentication failed: Invalid credentials")
                return False
            else:
                logger.warning(f"Unexpected response: {response.status_code}")
                return False

        except ConnectionError as e:
            logger.error(f"Connection error during credential validation: {e}")
            return False
        except Timeout as e:
            logger.error(f"Timeout during credential validation: {e}")
            return False
        except RequestException as e:
            logger.error(f"Request error during credential validation: {e}")
            return False

    def test_connection(self):
        """
        Test the connection to Jenkins server.

        :return: True if connection is successful, False otherwise
        """
        try:
            logger.info(f"Testing connection to {self.jenkins_url}")
            response = self.session.get(
                f'{self.jenkins_url}/api/json',
                timeout=self.timeout
            )

            if response.status_code == 200:
                logger.info("Connection test successful")
                return True
            else:
                logger.warning(f"Connection test failed: HTTP {response.status_code}")
                return False

        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
            return False
        except Timeout as e:
            logger.error(f"Connection timeout: {e}")
            return False
        except RequestException as e:
            logger.error(f"Request error: {e}")
            return False

    def get_crumb(self):
        """
        Get a CSRF protection token (crumb) from Jenkins.

        :return: Crumb data as dictionary or None if request fails
        """
        if self.crumb:
            return self.crumb

        try:
            response = self.session.get(
                f'{self.jenkins_url}/crumbIssuer/api/json',
                timeout=self.timeout
            )

            if response.status_code == 200:
                self.crumb = response.json()
                logger.info("Successfully acquired CSRF crumb")
                return self.crumb
            elif response.status_code == 404:
                logger.warning("Crumb issuer not found - CSRF protection may be disabled")
                return None
            else:
                logger.error(f"Failed to get crumb: HTTP {response.status_code}")
                return None

        except ConnectionError as e:
            logger.error(f"Connection error while getting crumb: {e}")
            return None
        except Timeout as e:
            logger.error(f"Timeout while getting crumb: {e}")
            return None
        except RequestException as e:
            logger.error(f"Request error while getting crumb: {e}")
            return None

    def _update_headers_with_crumb(self):
        """
        Update session headers with CSRF crumb if available.
        """
        crumb_data = self.get_crumb()
        if crumb_data and 'crumbRequestField' in crumb_data and 'crumb' in crumb_data:
            self.session.headers.update({
                crumb_data['crumbRequestField']: crumb_data['crumb']
            })
            logger.debug("Added crumb to request headers")

    def get_jenkins_info(self, endpoint='/api/json', timeout=None, params=None):
        """
        Retrieve Jenkins information with authentication handling.

        :param endpoint: API endpoint to query
        :param timeout: Request timeout in seconds (uses default if None)
        :param params: Additional URL parameters (dict)
        :return: JSON response or None if request fails
        """
        if timeout is None:
            timeout = self.timeout

        if params is None:
            params = {}

        full_url = f'{self.jenkins_url}{endpoint}'

        try:
            # Attempt connection
            response = self.session.get(
                full_url,
                params=params,
                timeout=timeout
            )

            # Raise an exception for bad HTTP responses
            response.raise_for_status()

            # Log successful request
            logger.info(f'Successfully retrieved data from {full_url}')

            # Check if the response is JSON
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type or 'text/json' in content_type:
                return response.json()
            else:
                logger.warning(f"Response is not JSON. Content-Type: {content_type}")
                return response.text

        except HTTPError as e:
            # Detailed error logging for HTTP errors
            if e.response.status_code == 401:
                logger.error("Unauthorized: Check your Jenkins credentials")
                raise JenkinsAuthenticationError(
                    "Unauthorized access. Verify username and API token."
                ) from e
            elif e.response.status_code == 403:
                logger.error("Forbidden: Insufficient permissions")
                raise JenkinsAuthenticationError(
                    "Access forbidden. Check user permissions in Jenkins."
                ) from e
            else:
                logger.error(f"HTTP error occurred: {e}")
                raise

        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise JenkinsAuthenticationError(f"Connection failed: {e}")

        except Timeout as e:
            logger.error(f"Request timed out: {e}")
            raise JenkinsAuthenticationError(f"Connection timed out: {e}")

        except RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def post_to_jenkins(self, endpoint, data=None, params=None, timeout=None):
        """
        Make a POST request to Jenkins with CSRF protection.

        :param endpoint: API endpoint to post to
        :param data: Data to send (dict or None)
        :param params: URL parameters (dict or None)
        :param timeout: Request timeout in seconds (uses default if None)
        :return: Response object or None if request fails
        """
        if timeout is None:
            timeout = self.timeout

        if params is None:
            params = {}

        # Update headers with CSRF crumb
        self._update_headers_with_crumb()

        full_url = f'{self.jenkins_url}{endpoint}'

        try:
            # Attempt connection with crumb in headers
            response = self.session.post(
                full_url,
                data=data,
                params=params,
                timeout=timeout
            )

            # Raise an exception for bad HTTP responses
            response.raise_for_status()

            # Log successful request
            logger.info(f'Successfully posted to {full_url}')

            # Check if response is JSON, if so return it
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type or 'text/json' in content_type:
                return response.json()
            return response

        except HTTPError as e:
            # If we get a 403 after adding crumb, it might be expired
            if e.response.status_code == 403:
                logger.warning("Possible expired crumb, attempting to refresh...")
                # Clear the cached crumb and try to get a new one
                self.crumb = None
                self._update_headers_with_crumb()

                # Try the request again with the new crumb
                try:
                    response = self.session.post(
                        full_url,
                        data=data,
                        params=params,
                        timeout=timeout
                    )
                    response.raise_for_status()
                    logger.info(f'Successfully posted to {full_url} after crumb refresh')

                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' in content_type or 'text/json' in content_type:
                        return response.json()
                    return response

                except HTTPError as retry_e:
                    logger.error(f"HTTP error occurred after crumb refresh: {retry_e}")
                    raise
            else:
                logger.error(f"HTTP error occurred: {e}")
                raise

        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise JenkinsAuthenticationError(f"Connection failed: {e}")

        except Timeout as e:
            logger.error(f"Request timed out: {e}")
            raise JenkinsAuthenticationError(f"Connection timed out: {e}")

        except RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def list_jobs(self):
        """
        List all jobs on the Jenkins server.

        :return: List of job names or empty list if request fails
        """
        try:
            info = self.get_jenkins_info()
            if info and 'jobs' in info:
                return [job['name'] for job in info['jobs']]
            return []
        except Exception as e:
            logger.error(f'Failed to list jobs: {e}')
            return []

    def get_build_queue(self):
        """
        Get information about builds in the queue.

        :return: List of queued builds or empty list if request fails
        """
        try:
            queue_info = self.get_jenkins_info('/queue/api/json')
            if queue_info and 'items' in queue_info:
                return queue_info['items']
            return []
        except Exception as e:
            logger.error(f'Failed to get build queue: {e}')
            return []

    def get_running_builds(self):
        """
        Get information about builds currently running.

        :return: List of running builds or empty list if request fails
        """
        try:
            # Using deeper tree and more specific fields to get all name information
            params = {
                'depth': 2,
                'tree': 'computer[executors[currentExecutable[*,url,fullDisplayName,displayName,description,timestamp,estimatedDuration,number,building,result,job[*]]],oneOffExecutors[currentExecutable[*,url,fullDisplayName,displayName,description,timestamp,estimatedDuration,number,building,result,job[*]]]]'
            }
            computer_info = self.get_jenkins_info('/computer/api/json', params=params)

            running_builds = []
            seen_builds = set()  # Track builds we've already added by URL

            if computer_info and 'computer' in computer_info:
                for node in computer_info['computer']:
                    # Check regular executors
                    if 'executors' in node:
                        for executor in node['executors']:
                            if executor.get('currentExecutable'):
                                build = executor['currentExecutable']
                                # Only add if we haven't seen this build URL before
                                build_url = build.get('url')
                                if build_url and build_url not in seen_builds:
                                    # Print full build info for debugging
                                    logger.debug(f"Build info: {build}")

                                    # Enhance build info with job name
                                    if 'job' in build and 'name' in build['job']:
                                        build['jobName'] = build['job']['name']
                                        if 'fullName' in build['job']:
                                            build['jobFullName'] = build['job']['fullName']
                                        if 'displayName' in build['job']:
                                            build['jobDisplayName'] = build['job']['displayName']

                                    # For display name, prioritize fullDisplayName which contains more context
                                    if 'fullDisplayName' in build and build['fullDisplayName']:
                                        build['displayName'] = build['fullDisplayName']
                                    elif 'displayName' not in build:
                                        build['displayName'] = f"#{build.get('number', 'N/A')}"

                                    # Log the display name for debugging
                                    logger.info(f"Build display name: {build.get('displayName', 'N/A')}")

                                    running_builds.append(build)
                                    seen_builds.add(build_url)

                    # Check one-off executors
                    if 'oneOffExecutors' in node:
                        for executor in node['oneOffExecutors']:
                            if executor.get('currentExecutable'):
                                build = executor['currentExecutable']
                                # Only add if we haven't seen this build URL before
                                build_url = build.get('url')
                                if build_url and build_url not in seen_builds:
                                    # Print full build info for debugging
                                    logger.debug(f"Build info: {build}")

                                    # Enhance build info with job name
                                    if 'job' in build and 'name' in build['job']:
                                        build['jobName'] = build['job']['name']
                                        if 'fullName' in build['job']:
                                            build['jobFullName'] = build['job']['fullName']
                                        if 'displayName' in build['job']:
                                            build['jobDisplayName'] = build['job']['displayName']

                                    # For display name, prioritize fullDisplayName which contains more context
                                    if 'fullDisplayName' in build and build['fullDisplayName']:
                                        build['displayName'] = build['fullDisplayName']
                                    elif 'displayName' not in build:
                                        build['displayName'] = f"#{build.get('number', 'N/A')}"

                                    # Log the display name for debugging
                                    logger.info(f"Build display name: {build.get('displayName', 'N/A')}")

                                    running_builds.append(build)
                                    seen_builds.add(build_url)

                # Additional logging for debugging
                logger.info(f"Total running builds: {len(running_builds)}")
                for build in running_builds:
                    logger.info(f"Job: {build.get('jobName', 'Unknown')}, Display: {build.get('displayName', 'Unknown')}")

                return running_builds
        except Exception as e:
                logger.error(f'Failed to get running builds: {e}')
        return []

    def build_job(self, job_name, parameters=None):
        """
        Trigger a build job on Jenkins.

        :param job_name: Name of the job to build
        :param parameters: Dictionary of build parameters (for parameterized builds)
        :return: Response data or None if request fails
        """
        # URL encode the job name for safety
        encoded_job_name = urllib.parse.quote(job_name)

        try:
            if parameters:
                # For parameterized builds
                endpoint = f'/job/{encoded_job_name}/buildWithParameters'
                return self.post_to_jenkins(endpoint, data=parameters)
            else:
                # For simple builds
                endpoint = f'/job/{encoded_job_name}/build'
                return self.post_to_jenkins(endpoint)
        except Exception as e:
            logger.error(f'Failed to build job {job_name}: {e}')
            return None

    def get_job_info(self, job_name):
        """
        Get detailed information about a specific job.

        :param job_name: Name of the job
        :return: Job information dict or None if request fails
        """
        try:
            encoded_job_name = urllib.parse.quote(job_name)
            endpoint = f'/job/{encoded_job_name}/api/json'
            return self.get_jenkins_info(endpoint)
        except Exception as e:
            logger.error(f'Failed to get job info for {job_name}: {e}')
            return None

    def get_build_info(self, job_name, build_number):
        """
        Get detailed information about a specific build.

        :param job_name: Name of the job
        :param build_number: Build number
        :return: Build information dict or None if request fails
        """
        try:
            encoded_job_name = urllib.parse.quote(job_name)
            endpoint = f'/job/{encoded_job_name}/{build_number}/api/json'
            return self.get_jenkins_info(endpoint)
        except Exception as e:
            logger.error(f'Failed to get build info for {job_name} #{build_number}: {e}')
            return None

    def get_latest_builds(self, limit=20):
        """
        Get information about the latest builds across all jobs.

        :param limit: Maximum number of builds to return
        :return: List of latest builds or empty list if request fails
        """
        try:
            # Get list of all jobs first
            all_jobs = self.list_jobs()
            all_builds = []

            # For each job, get the last build
            for job_name in all_jobs:
                try:
                    # Get job info to find the last build
                    job_info = self.get_job_info(job_name)

                    if job_info and 'lastBuild' in job_info and job_info['lastBuild']:
                        last_build_number = job_info['lastBuild'].get('number')

                        if last_build_number:
                            # Get detailed build info
                            build_info = self.get_build_info(job_name, last_build_number)

                            if build_info:
                                # Add job name to the build info for reference
                                build_info['jobName'] = job_name
                                all_builds.append(build_info)
                except Exception as e:
                    logger.warning(f"Error getting build info for job {job_name}: {e}")
                    continue

            # Sort builds by timestamp (newest first) and limit the result
            sorted_builds = sorted(all_builds, key=lambda x: x.get('timestamp', 0), reverse=True)
            return sorted_builds[:limit]

        except Exception as e:
            logger.error(f'Failed to get latest builds: {e}')
            return []

def main():
    # Load environment variables from .env file
    load_dotenv()

    # Get Jenkins URL from environment or use default
    jenkins_url = os.environ.get('JENKINS_URL', 'https://jenkins.example.com')

    try:
        print(f"Connecting to Jenkins at {jenkins_url}...")
        print("SSL verification is disabled for testing purposes.")

        # Create Jenkins connector using credentials from .env file
        connector = JenkinsConnector(jenkins_url, verify_ssl=False, timeout=30)

        # Test the connection
        if not connector.test_connection():
            print("Connection test failed. Please check your Jenkins URL and network connection.")
            return

        # Get and display CSRF crumb information
        crumb_info = connector.get_crumb()
        if crumb_info:
            print(f"CSRF Protection enabled: {crumb_info['crumbRequestField']} crumb obtained")
        else:
            print("CSRF Protection appears to be disabled or not accessible")

        # Retrieve and print Jenkins info
        jenkins_info = connector.get_jenkins_info()
        if jenkins_info:
            print("\nJenkins Server Information:")
            print(f"Jenkins Name: {jenkins_info.get('nodeName', 'N/A')}")
            print(f"Jenkins Mode: {jenkins_info.get('mode', 'N/A')}")
            print(f"Number of Jobs: {len(jenkins_info.get('jobs', []))}")

        # List jobs
        jobs = connector.list_jobs()
        if jobs:
            print("\nJobs on Jenkins:")
            for job in jobs:
                print(f"- {job}")
        else:
            print("\nNo jobs found or unable to retrieve job list.")

        # Get build queue
        queue = connector.get_build_queue()
        print(f"\nBuild Queue: {len(queue)} items")

        # Get running builds
        running = connector.get_running_builds()
        print(f"Running Builds: {len(running)} items")
        for build in running:
            job_name = build.get('jobName', build.get('jobFullName', 'Unknown'))
            display_name = build.get('displayName', f"#{build.get('number', 'N/A')}")
            print(f"  - {job_name}: {display_name}")

    except JenkinsAuthenticationError as e:
        print(f"Jenkins Authentication Failed: {e}")
        print("\nTroubleshooting Tips:")
        print("1. Verify your Jenkins username")
        print("2. Check that your API token is correct")
        print("3. Ensure the user has appropriate permissions")
        print("4. Check your .env file is properly configured")
        print("5. Verify your Jenkins URL is correct and accessible")
        print("6. Check for any network or proxy issues")

    except Exception as e:
        print(f"Unexpected error: {e}")
        print("\nPlease check your network connection and Jenkins server status.")

if __name__ == '__main__':
    main()