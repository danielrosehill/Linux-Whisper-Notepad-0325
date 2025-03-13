#!/usr/bin/env python3
# Linux Notepad - Speech to Text and Processing Application
# Main application entry point

import sys
import os
from PyQt6.QtWidgets import QApplication
from .gui import MainWindow

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Linux Whisper Notepad")
    app.setOrganizationName("Linux-Whisper-Notepad-0325")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()