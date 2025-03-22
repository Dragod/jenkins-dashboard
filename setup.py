from setuptools import setup, find_packages

setup(
    name="jenkins-dashboard",
    version="0.1.0",
    description="A dashboard for monitoring Jenkins builds in progress and build queue",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "python-dotenv>=0.20.0",
        "Flask>=2.2.0",
        "Flask-Cors>=3.0.10",
        "pytz>=2022.1",
    ],
    extras_require={
        "windows": ["windows-curses>=2.3.0"],
    },
    entry_points={
        "console_scripts": [
            "jenkins-cli=jenkins_dashboard_cli:main",
            "jenkins-web=jenkins_dashboard_web:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)