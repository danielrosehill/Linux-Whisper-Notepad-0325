#!/usr/bin/env python3
# Linux Whisper Notepad - GUI Module
# Implements the PyQt6-based graphical user interface

import os
import sys
import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QLineEdit, QFileDialog, QTabWidget, QGroupBox,
    QFormLayout, QMessageBox, QProgressBar, QSplitter, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QIcon, QFont

from .config import Config
from .audio import AudioManager
from .openai_api import OpenAIManager

class TranscriptionWorker(QThread):
    """Worker thread for audio transcription"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int)  # Progress signal (0-100)
    
    def __init__(self, openai_manager, audio_file_path):
        super().__init__()
        self.openai_manager = openai_manager
        self.audio_file_path = audio_file_path
    
    def run(self):
        """Run transcription in background thread"""
        # Emit initial progress
        self.progress.emit(10)
        
        result = self.openai_manager.transcribe_audio(self.audio_file_path)
        
        # Emit final progress
        self.progress.emit(100)
        self.finished.emit(result)

class ProcessingWorker(QThread):
    """Worker thread for text processing"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int)  # Progress signal (0-100)
    
    def __init__(self, openai_manager, text, mode):
        super().__init__()
        self.openai_manager = openai_manager
        self.text = text
        self.mode = mode
    
    def run(self):
        """Run text processing in background thread"""
        # Emit initial progress
        self.progress.emit(10)
        
        result = self.openai_manager.process_text(self.text, self.mode)
        
        # Emit final progress
        self.progress.emit(100)
        self.finished.emit(result)

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize managers
        self.config = Config()
        self.audio_manager = AudioManager(self.config)
        self.openai_manager = OpenAIManager(self.config)
        
        # Set up the UI
        self.init_ui()
        
        # Set up timers
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self.update_recording_time)
        
        # Initialize state
        self.recording_time = 0
        self.transcribed_text = ""
        self.processed_text = ""
        self.suggested_filename = ""
        
        # Load configuration
        self.load_config()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Linux Whisper Notepad")
        self.setMinimumSize(900, 700)  # Increased minimum size for better UI
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Add Clear All button at the top
        clear_all_layout = QHBoxLayout()
        self.clear_all_button = QPushButton("Clear All")
        self.clear_all_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.clear_all_button.clicked.connect(self.clear_all)
        clear_all_layout.addStretch()
        clear_all_layout.addWidget(self.clear_all_button)
        main_layout.addLayout(clear_all_layout)
        
        # Create tab widget for main functionality and settings
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create main tab
        main_tab = QWidget()
        main_tab_layout = QVBoxLayout(main_tab)
        self.tab_widget.addTab(main_tab, "Notepad")
        
        # Create settings tab
        settings_tab = QWidget()
        settings_tab_layout = QVBoxLayout(settings_tab)
        self.tab_widget.addTab(settings_tab, "Settings")
        
        # Set up main tab UI
        self.setup_main_tab(main_tab_layout)
        
        # Set up settings tab UI
        self.setup_settings_tab(settings_tab_layout)
    
    def setup_main_tab(self, layout):
        """Set up the main tab UI"""
        # Audio recording section
        recording_group = QGroupBox("1. Audio Recording")
        recording_layout = QVBoxLayout(recording_group)
        
        # Audio device selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Audio Source:"))
        
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        device_layout.addWidget(self.device_combo)
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_devices)
        device_layout.addWidget(refresh_button)
        
        device_layout.addStretch()
        recording_layout.addLayout(device_layout)
        
        # Recording controls
        controls_layout = QHBoxLayout()
        
        self.record_button = QPushButton("Start Recording")
        self.record_button.clicked.connect(self.toggle_recording)
        controls_layout.addWidget(self.record_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        controls_layout.addWidget(self.pause_button)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_recording)
        self.clear_button.setEnabled(False)
        controls_layout.addWidget(self.clear_button)
        
        controls_layout.addStretch()
        
        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        controls_layout.addWidget(self.time_label)
        
        recording_layout.addLayout(controls_layout)
        
        # Transcription section
        transcription_group = QGroupBox("2. Transcription")
        transcription_layout = QVBoxLayout(transcription_group)
        
        transcribe_controls = QHBoxLayout()
        
        self.transcribe_button = QPushButton("Transcribe Audio")
        self.transcribe_button.clicked.connect(self.transcribe_audio)
        self.transcribe_button.setEnabled(False)
        transcribe_controls.addWidget(self.transcribe_button)
        
        self.clear_transcription_button = QPushButton("Clear Transcription")
        self.clear_transcription_button.clicked.connect(self.clear_transcription)
        self.clear_transcription_button.setEnabled(False)
        transcribe_controls.addWidget(self.clear_transcription_button)
        
        transcribe_controls.addStretch()
        transcription_layout.addLayout(transcribe_controls)
        
        self.transcription_progress = QProgressBar()
        self.transcription_progress.setVisible(False)
        transcription_layout.addWidget(self.transcription_progress)
        
        self.transcribed_text_edit = QTextEdit()
        self.transcribed_text_edit.setPlaceholderText("Transcribed text will appear here...")
        transcription_layout.addWidget(self.transcribed_text_edit)
        
        # Text processing section
        processing_group = QGroupBox("3. Text Processing")
        processing_layout = QVBoxLayout(processing_group)
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Processing Mode:"))
        
        self.mode_combo = QComboBox()
        self.populate_processing_modes()
        mode_layout.addWidget(self.mode_combo)
        
        self.process_button = QPushButton("Process Text")
        self.process_button.clicked.connect(self.process_text)
        self.process_button.setEnabled(False)
        mode_layout.addWidget(self.process_button)
        
        self.clear_processed_button = QPushButton("Clear Processed")
        self.clear_processed_button.clicked.connect(self.clear_processed_text)
        self.clear_processed_button.setEnabled(False)
        mode_layout.addWidget(self.clear_processed_button)
        
        processing_layout.addLayout(mode_layout)
        
        self.processing_progress = QProgressBar()
        self.processing_progress.setVisible(False)
        processing_layout.addWidget(self.processing_progress)
        
        self.processed_text_edit = QTextEdit()
        self.processed_text_edit.setPlaceholderText("Processed text will appear here...")
        processing_layout.addWidget(self.processed_text_edit)
        
        # Save section
        save_group = QGroupBox("4. Save")
        save_layout = QVBoxLayout(save_group)
        
        filename_layout = QHBoxLayout()
        filename_layout.addWidget(QLabel("Filename:"))
        
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("Suggested filename will appear here...")
        filename_layout.addWidget(self.filename_edit)
        
        self.save_button = QPushButton("Save Text")
        self.save_button.clicked.connect(self.save_text)
        self.save_button.setEnabled(False)
        filename_layout.addWidget(self.save_button)
        
        save_layout.addLayout(filename_layout)
        
        # Add all sections to main layout
        layout.addWidget(recording_group)
        layout.addWidget(transcription_group)
        layout.addWidget(processing_group)
        layout.addWidget(save_group)
    
    def setup_settings_tab(self, layout):
        """Set up the settings tab UI"""
        # OpenAI API settings
        api_group = QGroupBox("OpenAI API Settings")
        api_layout = QFormLayout(api_group)
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("Enter your OpenAI API key")
        api_layout.addRow("API Key:", self.api_key_edit)
        
        # Whisper model selection
        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItem("Whisper 1 (Default)", "whisper-1")
        api_layout.addRow("Whisper Model:", self.whisper_model_combo)
        
        # Chunking settings
        self.max_chunk_duration_edit = QLineEdit()
        self.max_chunk_duration_edit.setPlaceholderText("Duration in seconds (default: 120)")
        api_layout.addRow("Max Chunk Duration (seconds):", self.max_chunk_duration_edit)
        
        self.save_api_settings_button = QPushButton("Save API Settings")
        self.save_api_settings_button.clicked.connect(self.save_api_settings)
        api_layout.addRow("", self.save_api_settings_button)
        
        # Output directory settings
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout(output_group)
        
        output_dir_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        output_dir_layout.addWidget(self.output_dir_edit)
        
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_output_dir)
        output_dir_layout.addWidget(browse_button)
        
        output_layout.addRow("Output Directory:", output_dir_layout)
        
        self.save_output_dir_button = QPushButton("Save Output Directory")
        self.save_output_dir_button.clicked.connect(self.save_output_dir)
        output_layout.addRow("", self.save_output_dir_button)
        
        # Add all sections to settings layout
        layout.addWidget(api_group)
        layout.addWidget(output_group)
        layout.addStretch()
    
    def load_config(self):
        """Load configuration and update UI"""
        # Load API key
        api_key = self.config.get("openai_api_key", "")
        self.api_key_edit.setText(api_key)
        self.openai_manager.set_api_key(api_key)
        
        # Load whisper model
        whisper_model = self.config.get("whisper_model", "whisper-1")
        for i in range(self.whisper_model_combo.count()):
            if self.whisper_model_combo.itemData(i) == whisper_model:
                self.whisper_model_combo.setCurrentIndex(i)
                break
        
        # Load max chunk duration
        max_chunk_duration = self.config.get("max_chunk_duration", 120)
        self.max_chunk_duration_edit.setText(str(max_chunk_duration))
        
        # Load output directory
        output_dir = self.config.get("output_directory", "")
        self.output_dir_edit.setText(output_dir)
        
        # Load audio device
        self.refresh_devices()
        device_index_str = self.config.get("audio_device", "")
        if device_index_str and device_index_str.isdigit():
            device_index = int(device_index_str)
            # Find the device in the combo box
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == device_index:
                    self.device_combo.setCurrentIndex(i)
                    break
        
        # Load last used processing mode
        last_mode = self.config.get("last_used_mode", "basic_cleanup")
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == last_mode:
                self.mode_combo.setCurrentIndex(i)
                break
    
    def refresh_devices(self):
        """Refresh the list of audio devices"""
        self.device_combo.clear()
        
        devices = self.audio_manager.get_devices()
        for device in devices:
            self.device_combo.addItem(f"{device['name']} ({device['channels']} ch, {device['sample_rate']} Hz)", device['index'])
        
        # If no devices found, disable recording
        if self.device_combo.count() == 0:
            self.record_button.setEnabled(False)
            QMessageBox.warning(self, "No Audio Devices", "No audio input devices found. Please connect a microphone.")
        else:
            self.record_button.setEnabled(True)
    
    def populate_processing_modes(self):
        """Populate the processing modes combo box"""
        modes = self.openai_manager.get_available_modes()
        for mode in modes:
            self.mode_combo.addItem(mode["name"], mode["id"])
    
    def toggle_recording(self):
        """Toggle audio recording"""
        if not self.audio_manager.is_recording:
            # Start recording
            device_index = self.device_combo.currentData()
            if self.audio_manager.start_recording(device_index):
                self.record_button.setText("Stop Recording")
                self.pause_button.setEnabled(True)
                self.clear_button.setEnabled(True)
                self.device_combo.setEnabled(False)
                
                # Save selected device to config
                self.config.set("audio_device", str(device_index))
                
                # Start recording timer
                self.recording_time = 0
                self.update_recording_time()
                self.recording_timer.start(1000)  # Update every second
        else:
            # Stop recording
            if self.audio_manager.stop_recording():
                self.record_button.setText("Start Recording")
                self.pause_button.setText("Pause")
                self.pause_button.setEnabled(False)
                self.device_combo.setEnabled(True)
                self.recording_timer.stop()
                
                # Enable transcribe button if we have recorded audio
                if self.audio_manager.get_recording_duration() > 0:
                    self.transcribe_button.setEnabled(True)
    
    def toggle_pause(self):
        """Toggle pause/resume recording"""
        if not self.audio_manager.is_paused:
            # Pause recording
            if self.audio_manager.pause_recording():
                self.pause_button.setText("Resume")
                self.recording_timer.stop()
        else:
            # Resume recording
            if self.audio_manager.resume_recording():
                self.pause_button.setText("Pause")
                self.recording_timer.start(1000)
    
    def clear_recording(self):
        """Clear recorded audio"""
        if self.audio_manager.clear_recording():
            self.recording_time = 0
            self.update_recording_time()
            self.transcribe_button.setEnabled(False)
    
    def update_recording_time(self):
        """Update recording time display"""
        self.recording_time += 1
        minutes = self.recording_time // 60
        seconds = self.recording_time % 60
        self.time_label.setText(f"{minutes:02d}:{seconds:02d}")
    
    def transcribe_audio(self):
        """Transcribe recorded audio"""
        # Save audio to temporary file
        temp_file = self.audio_manager.save_to_temp_file()
        if not temp_file:
            QMessageBox.warning(self, "Error", "No audio data to transcribe.")
            return
        
        # Check if API key is set
        if not self.openai_manager.api_key:
            QMessageBox.warning(self, "API Key Required", "Please set your OpenAI API key in the Settings tab.")
            self.tab_widget.setCurrentIndex(1)  # Switch to settings tab
            return
        
        # Show progress
        self.transcription_progress.setVisible(True)
        self.transcription_progress.setValue(0)
        self.transcribe_button.setEnabled(False)
        
        # Start transcription in background thread
        self.transcription_worker = TranscriptionWorker(self.openai_manager, temp_file)
        self.transcription_worker.progress.connect(self.update_transcription_progress)
        self.transcription_worker.finished.connect(self.handle_transcription_result)
        self.transcription_worker.start()
    
    def update_transcription_progress(self, value):
        """Update transcription progress bar"""
        self.transcription_progress.setValue(value)
    
    def handle_transcription_result(self, result):
        """Handle transcription result"""
        # Hide progress
        self.transcription_progress.setVisible(False)
        self.transcribe_button.setEnabled(True)
        
        if result.get("success", False):
            # Update transcribed text
            self.transcribed_text = result.get("text", "")
            self.transcribed_text_edit.setText(self.transcribed_text)
            
            # Enable processing button and clear button
            self.process_button.setEnabled(True)
            self.clear_transcription_button.setEnabled(True)
        else:
            # Show error message
            error_message = result.get("error", "Unknown error")
            QMessageBox.warning(self, "Transcription Error", f"Failed to transcribe audio: {error_message}")
    
    def clear_transcription(self):
        """Clear transcribed text"""
        self.transcribed_text = ""
        self.transcribed_text_edit.clear()
        self.process_button.setEnabled(False)
        self.clear_transcription_button.setEnabled(False)
    
    def process_text(self):
        """Process transcribed text"""
        # Get text from transcription text edit
        text = self.transcribed_text_edit.toPlainText()
        if not text:
            QMessageBox.warning(self, "Error", "No text to process.")
            return
        
        # Check if API key is set
        if not self.openai_manager.api_key:
            QMessageBox.warning(self, "API Key Required", "Please set your OpenAI API key in the Settings tab.")
            self.tab_widget.setCurrentIndex(1)  # Switch to settings tab
            return
        
        # Get selected processing mode
        mode = self.mode_combo.currentData()
        
        # Save selected mode to config
        self.config.set("last_used_mode", mode)
        
        # Show progress
        self.processing_progress.setVisible(True)
        self.processing_progress.setValue(0)
        self.process_button.setEnabled(False)
        
        # Start processing in background thread
        self.processing_worker = ProcessingWorker(self.openai_manager, text, mode)
        self.processing_worker.progress.connect(self.update_processing_progress)
        self.processing_worker.finished.connect(self.handle_processing_result)
        self.processing_worker.start()
    
    def update_processing_progress(self, value):
        """Update processing progress bar"""
        self.processing_progress.setValue(value)
    
    def handle_processing_result(self, result):
        """Handle text processing result"""
        # Hide progress
        self.processing_progress.setVisible(False)
        self.process_button.setEnabled(True)
        
        if result.get("success", False):
            # Update processed text
            self.processed_text = result.get("processed_text", "")
            self.processed_text_edit.setText(self.processed_text)
            
            # Update suggested filename
            self.suggested_filename = result.get("suggested_filename", "")
            if self.suggested_filename:
                self.filename_edit.setText(f"{self.suggested_filename}.md")
            
            # Enable save button and clear button
            self.save_button.setEnabled(True)
            self.clear_processed_button.setEnabled(True)
        else:
            # Show error message
            error_message = result.get("error", "Unknown error")
            QMessageBox.warning(self, "Processing Error", f"Failed to process text: {error_message}")
    
    def clear_processed_text(self):
        """Clear processed text"""
        self.processed_text = ""
        self.processed_text_edit.clear()
        self.save_button.setEnabled(False)
        self.clear_processed_button.setEnabled(False)
    
    def save_text(self):
        """Save processed text to file"""
        # Get output directory
        output_dir = self.output_dir_edit.text()
        if not output_dir:
            # Use default directory if not set
            output_dir = os.path.join(Path.home(), "Documents")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get filename
        filename = self.filename_edit.text()
        if not filename:
            filename = f"note-{time.strftime('%Y-%m-%d-%H%M%S')}.md"
        
        # Ensure filename has .md extension
        if not filename.lower().endswith(".md"):
            filename += ".md"
        
        # Full file path
        file_path = os.path.join(output_dir, filename)
        
        # Get text to save
        text = self.processed_text_edit.toPlainText()
        
        try:
            # Write text to file
            with open(file_path, "w") as f:
                f.write(text)
            
            QMessageBox.information(self, "Success", f"File saved successfully:\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save file: {str(e)}")
    
    def save_api_settings(self):
        """Save OpenAI API settings"""
        # Save API key
        api_key = self.api_key_edit.text()
        self.openai_manager.set_api_key(api_key)
        
        # Save Whisper model
        whisper_model = self.whisper_model_combo.currentData()
        self.config.set("whisper_model", whisper_model)
        
        # Save max chunk duration
        try:
            max_chunk_duration = int(self.max_chunk_duration_edit.text())
            if max_chunk_duration < 10:
                max_chunk_duration = 10  # Minimum 10 seconds
            self.config.set("max_chunk_duration", max_chunk_duration)
        except ValueError:
            # Use default if invalid
            self.config.set("max_chunk_duration", 120)
            self.max_chunk_duration_edit.setText("120")
        
        QMessageBox.information(self, "Success", "API settings saved successfully.")
    
    def browse_output_dir(self):
        """Browse for output directory"""
        current_dir = self.output_dir_edit.text()
        if not current_dir:
            current_dir = os.path.join(Path.home(), "Documents")
        
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", current_dir
        )
        
        if directory:
            self.output_dir_edit.setText(directory)
    
    def save_output_dir(self):
        """Save output directory"""
        output_dir = self.output_dir_edit.text()
        if output_dir:
            self.config.set("output_directory", output_dir)
            QMessageBox.information(self, "Success", "Output directory saved successfully.")
    
    def clear_all(self):
        """Clear all data and reset UI"""
        # Ask for confirmation
        reply = QMessageBox.question(
            self, "Clear All", 
            "Are you sure you want to clear all data? This will reset the audio recording, transcription, and processed text.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Clear audio recording
            self.audio_manager.clear_recording()
            self.recording_time = 0
            self.update_recording_time()
            self.transcribe_button.setEnabled(False)
            self.clear_button.setEnabled(False)
            
            # Clear transcription
            self.clear_transcription()
            
            # Clear processed text
            self.clear_processed_text()
            
            # Clear filename
            self.filename_edit.clear()
            
            # Clear cache
            self.config.clear_cache()
            
            # Reset recording button if not recording
            if not self.audio_manager.is_recording:
                self.record_button.setText("Start Recording")
                self.pause_button.setText("Pause")
                self.pause_button.setEnabled(False)
                self.device_combo.setEnabled(True)
            
            QMessageBox.information(self, "Success", "All data has been cleared.")