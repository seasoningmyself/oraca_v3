"""
Setup script for Market Data package.
Allows installation with: pip install -e market_data/
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip()
        for line in requirements_file.read_text().splitlines()
        if line.strip() and not line.startswith('#')
    ]

setup(
    name="oraca-market-data",
    version="1.0.0",
    description="Market data integration for Oraca trading system using Massive (Polygon.io)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ennis M. Salam",
    author_email="salam@shieldstonelabs.com",
    url="https://github.com/seasoningmyself",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "market_data": ["config.yaml"],
    },
    install_requires=requirements,
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Office/Business :: Financial :: Investment",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="market data polygon massive trading finance timescaledb",
)
