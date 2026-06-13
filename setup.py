# setup.py
from setuptools import setup, find_packages

setup(
    name="euroclaw",
    version="0.1.0",
    description="A sovereign, zero-trust, and highly scalable agentic AI framework.",
    author="Astream B.V.",
    author_email="your.email@example.com", # Optional: Update this
    url="https://github.com/astream2018/euroclaw",
    
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    
    # These are the core dependencies EuroClaw needs to run
    install_requires=[
        "requests>=2.31.0",
        "requests-unixsocket>=0.3.0",
        "redis>=5.0.0",
        "opentelemetry-api>=1.20.0",
        "opentelemetry-sdk>=1.20.0",
        "opentelemetry-exporter-otlp>=1.20.0",
        "pyyaml>=6.0.1",
        "python-dotenv>=1.0.0"
    ],
    
    python_requires=">=3.10",
)