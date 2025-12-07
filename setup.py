# setup.py
from setuptools import setup, find_packages

setup(
    name="quran-segmenter",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "backoff>=2.0.0",
    ],
    extras_require={
        "colab": [
            "google-colab",
        ],
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "quran-segmenter=quran_segmenter.cli:main",
        ],
    },
    python_requires=">=3.10",
)