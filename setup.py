import os

from setuptools import find_packages, setup

README = os.path.join(os.path.dirname(__file__), "README.md")


def readme() -> str:
    with open(README, encoding="utf-8") as f:
        return f.read()


setup(
    name="json_schema_to_code",
    version="1.0.1",
    description="Generate strongly-typed classes from JSON Schema definitions for Python and C#",
    long_description=readme(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Text Processing",
        "Intended Audience :: Developers",
    ],
    keywords="json schema code generation python csharp dataclass template",
    url="https://github.com/madlag/json_schema_to_code",
    author="François Lagunas",
    author_email="francois.lagunas@gmail.com",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.12",
    install_requires=[
        "click>=8.0.0",
        "jinja2>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "json_schema_to_code=json_schema_to_code.json_schema_to_code:json_schema_to_code",
        ],
    },
    include_package_data=True,
    package_data={
        "json_schema_to_code": ["templates/**/*.jinja2"],
    },
    zip_safe=False,
)
