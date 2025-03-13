#!/usr/bin/env python3
# Linux Whisper Notepad - Setup script

from setuptools import setup, find_packages

setup(
    name="linux-whisper-notepad",
    version="0.1.0",
    description="Whisper-powered Speech to Text and Processing Application",
    author="Linux Whisper Notepad Team",
    packages=find_packages(),
    package_data={
        'src.linux_notepad': ['resources/*'],
    },
    install_requires=[
        'PyQt6>=6.4.0',
        'pyaudio>=0.2.13',
        'numpy>=1.22.0',
        'openai>=1.0.0',
    ],
    entry_points={
        'console_scripts': [
            'linux-whisper-notepad=src.linux_notepad.main:main',
        ],
    },
    python_requires='>=3.8',
)