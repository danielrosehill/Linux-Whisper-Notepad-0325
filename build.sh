#!/bin/bash
# Build script for Linux Whisper Notepad application

# Check if virtual environment exists and activate it
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Ensure PyInstaller is installed
if ! pip show pyinstaller > /dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Clean previous build if it exists
if [ -d "dist" ] || [ -d "build" ]; then
    echo "Cleaning previous build..."
    rm -rf dist build
fi

# Create the executable using the spec file
echo "Building executable..."
pyinstaller Linux-Whisper-Notepad.spec

# Check if build was successful
if [ -f "dist/Linux-Whisper-Notepad" ]; then
    echo "Build successful! Executable is located at: dist/Linux-Whisper-Notepad"
else
    echo "Build failed."
    exit 1
fi

# Deactivate virtual environment if it was activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi