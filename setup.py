"""CogniHeal-Engine package setup."""

from setuptools import setup, find_packages
from pathlib import Path

long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="cogniheal-engine",
    version="1.0.0",
    author="CogniHeal Contributors",
    description=(
        "Self-Reflective Dynamic Episodic Memory & "
        "Autonomous Self-Healing Agent Engine"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/EvoderDev/CogniHeal-Engine",
    packages=find_packages(exclude=["tests*", "examples*"]),
    python_requires=">=3.11",
    install_requires=[
        "chromadb>=0.4.22",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.0.0",
        "rich>=13.7.0",
        "openai>=1.12.0",
        "tree-sitter>=0.21.0",
        "sqlite-utils>=3.36",
        "tenacity>=8.2.3",
        "numpy>=1.26.0",
        "click>=8.1.7",
        "python-dotenv>=1.0.0",
        "httpx>=0.27.0",
        "pytest>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cogni=cogniheal.cli:interactive_mode",
            "cg=cogniheal.cli:interactive_mode",
            "cogniheal=cogniheal.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Testing",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
