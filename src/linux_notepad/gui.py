#!/usr/bin/env python3
# Speech Note Capture - GUI Module
# Implements the PyQt6-based graphical user interface

import os
import sys
import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QLineEdit, QFileDialog, QTabWidget, QGroupBox,
    QFormLayout, QMessageBox, QProgressBar, QSplitter, QCheckBox,
    QListWidget, QListWidgetItem, QDialog, QDialogButtonBox, QInputDialog, QApplication,
    QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import (
    Qt, QSize, QThread, pyqtSignal, QObject, 
    QRunnable, pyqtSlot, QThreadPool, QTimer
)
from PyQt6.QtGui import QIcon, QFont, QClipboard, QShortcut, QKeySequence
from datetime import datetime

from .config import Config
from .audio import AudioManager
from .openai_api import OpenAIManager

class TranscriptionWorker(QThread):
    """Worker thread for audio transcription"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)  # Ensure we always emit a dict
    
    def __init__(self, openai_manager, audio_file_path):
        super().__init__()
        self.openai_manager = openai_manager
        self.audio_file_path = audio_file_path
    
    def run(self):
        """Run the transcription process"""
        try:
            # Report progress
            self.progress.emit(10)
            
            # Transcribe audio
            result = self.openai_manager.transcribe_audio(self.audio_file_path)
            
            # Ensure result is a properly formatted dictionary
            if not isinstance(result, dict):
                result = {"success": False, "error": "Invalid result format", "text": ""}
            
            # Report progress
            self.progress.emit(100)
            
            # Emit result
            self.finished.emit(result)
        except Exception as e:
            # Handle any exceptions
            error_result = {"success": False, "error": str(e), "text": ""}
            self.finished.emit(error_result)

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
        
        # Create the transcribed_text widget early to ensure it's available
        self.transcribed_text = QTextEdit()
        self.transcribed_text.setMinimumHeight(200)
        self.transcribed_text.setPlaceholderText("Transcribed text will appear here. You can edit the text before processing.")
        
        # Initialize state variables
        self.recording_time = 0
        self.processed_text = ""
        self.suggested_filename = ""
        self.selected_prompt_name = ""  # Store the selected prompt name
        
        # Set up the UI
        self.init_ui()
        
        # Set up timers
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self.update_recording_time)
        
        # Load configuration
        self.load_config()
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Speech Note Capture")
        self.setMinimumSize(1100, 850)  # Further increased minimum size to prevent layout issues
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)  # Increased spacing between elements
        main_layout.setContentsMargins(15, 15, 15, 15)  # Increased margins to prevent elements from touching window edges
        
        # Add Clear All button at the top
        clear_all_layout = QHBoxLayout()
        self.clear_all_button = QPushButton("Clear All")
        self.clear_all_button.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold;")
        self.clear_all_button.clicked.connect(self.clear_all)
        clear_all_layout.addStretch()
        clear_all_layout.addWidget(self.clear_all_button)
        main_layout.addLayout(clear_all_layout)
        
        # Add prominent recording time display at the top
        self.main_time_display = QLabel("00:00")
        self.main_time_display.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold; font-size: 24px; padding: 8px 20px; border-radius: 5px;")
        self.main_time_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_time_display.setFixedWidth(150)  # Increased width
        main_layout.addWidget(self.main_time_display, 0, Qt.AlignmentFlag.AlignCenter)
        
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
        
        # Create system prompts tab
        prompts_tab = QWidget()
        prompts_tab_layout = QVBoxLayout(prompts_tab)
        self.tab_widget.addTab(prompts_tab, "System Prompts")
        
        # Create variables tab
        variables_tab = QWidget()
        variables_tab_layout = QVBoxLayout(variables_tab)
        self.tab_widget.addTab(variables_tab, "Variables")
        
        # Create about tab
        about_tab = QWidget()
        about_tab_layout = QVBoxLayout(about_tab)
        self.tab_widget.addTab(about_tab, "About")
        
        # Set up main tab UI
        self.setup_main_tab(main_tab_layout)
        
        # Set up settings tab UI
        self.setup_settings_tab(settings_tab_layout)
        
        # Set up system prompts tab UI
        self.setup_system_prompts_tab(prompts_tab_layout)
        
        # Set up variables tab UI
        self.setup_variables_tab(variables_tab_layout)
        
        # Set up about tab UI
        self.setup_about_tab(about_tab_layout)
        
        # Populate processing modes
        self.populate_processing_modes()
    
    def setup_main_tab(self, layout):
        """Set up the main tab UI"""
        # Create a horizontal layout for the two columns
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20)  # Further increased spacing between columns
        
        # Create left column layout
        left_column = QVBoxLayout()
        left_column.setContentsMargins(8, 8, 8, 8)  # Increased padding within the column
        left_column.setSpacing(8)  # Set consistent spacing between elements
        
        # Create right column layout
        right_column = QVBoxLayout()
        right_column.setContentsMargins(8, 8, 8, 8)  # Increased padding within the column
        right_column.setSpacing(8)  # Set consistent spacing between elements
        
        # Add columns to the main layout
        columns_layout.addLayout(left_column, 1)  # 1 is the stretch factor
        columns_layout.addLayout(right_column, 1)
        layout.addLayout(columns_layout)
        
        # ===== LEFT COLUMN =====
        # Record section
        record_header = QLabel("RECORD")
        record_header.setStyleSheet("font-size: 15px; font-weight: bold; color: #1A1A1A; background-color: #4285F4; padding: 8px 12px; border-radius: 3px; margin-bottom: 5px;")
        left_column.addWidget(record_header)
        
        # Add shaded container for record section
        record_container = QWidget()
        record_container.setStyleSheet("background-color: #F8F9FA; border: 1px solid #E1E2E3; border-radius: 5px; padding: 10px;")
        record_container_layout = QVBoxLayout(record_container)
        record_container_layout.setContentsMargins(10, 10, 10, 10)
        
        # Add description text
        record_description = QLabel("Record audio from your microphone to transcribe into text.")
        record_description.setStyleSheet("font-style: italic; color: #666; margin-bottom: 6px; font-size: 12px;")
        record_description.setWordWrap(True)
        record_description.setFixedHeight(20)  # Set fixed height to prevent overlap
        record_container_layout.addWidget(record_description)
        
        # Audio device selection
        device_layout = QHBoxLayout()
        device_label = QLabel("Audio Device:")
        device_layout.addWidget(device_label)
        
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        device_layout.addWidget(self.device_combo, 1)
        
        # Add buttons in a horizontal layout
        device_buttons_layout = QHBoxLayout()
        
        # Refresh button with icon instead of text
        refresh_button = QPushButton()
        refresh_button.setIcon(QIcon.fromTheme("view-refresh"))
        refresh_button.setToolTip("Refresh Audio Devices")
        refresh_button.clicked.connect(self.refresh_audio_devices)
        device_buttons_layout.addWidget(refresh_button)
        
        # Set as default button renamed to Make Default
        set_default_button = QPushButton("Make Default")
        set_default_button.setToolTip("Set the current audio device as the default")
        set_default_button.clicked.connect(self.set_default_audio_device)
        device_buttons_layout.addWidget(set_default_button)
        
        device_layout.addLayout(device_buttons_layout)
        
        record_container_layout.addLayout(device_layout)
        
        # Recording controls
        controls_layout = QHBoxLayout()
        
        # Start recording button
        self.record_button = QPushButton()
        self.record_button.setIcon(QIcon.fromTheme("media-record", QIcon.fromTheme("media-playback-start")))
        self.record_button.setToolTip("Start Recording (Ctrl+R)")
        self.record_button.clicked.connect(self.start_recording)
        self.record_button.setStyleSheet("background-color: #fb8c00; color: white;")  # Orange color for record button
        controls_layout.addWidget(self.record_button)
        
        # Stop recording button - changed background color to match other audio controls
        self.stop_button = QPushButton()
        self.stop_button.setIcon(QIcon.fromTheme("media-playback-stop"))
        self.stop_button.setToolTip("Stop Recording (Ctrl+S)")
        self.stop_button.clicked.connect(self.stop_recording)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #fb8c00; color: white;")  # Changed to orange to match pause button
        controls_layout.addWidget(self.stop_button)
        
        # Pause recording button
        self.pause_button = QPushButton()
        self.pause_button.setIcon(QIcon.fromTheme("media-playback-pause"))
        self.pause_button.setToolTip("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        self.pause_button.setStyleSheet("background-color: #fb8c00; color: white;")  # Orange color for pause button
        controls_layout.addWidget(self.pause_button)
        
        # Clear recording button
        self.clear_button = QPushButton()
        self.clear_button.setIcon(QIcon.fromTheme("edit-clear", QIcon.fromTheme("edit-delete")))
        self.clear_button.setToolTip("Clear Recording")
        self.clear_button.clicked.connect(self.clear_recording)
        self.clear_button.setEnabled(False)
        self.clear_button.setStyleSheet("background-color: #fb8c00; color: white;")  # Orange color for clear button
        controls_layout.addWidget(self.clear_button)
        
        record_container_layout.addLayout(controls_layout)
        
        # Recording time display and scrub silences checkbox
        time_layout = QHBoxLayout()
        
        # Add scrub silences checkbox
        self.main_scrub_silences_checkbox = QCheckBox("Scrub Silences")
        self.main_scrub_silences_checkbox.setToolTip("Remove long pauses from audio before transcription")
        self.main_scrub_silences_checkbox.stateChanged.connect(self.update_scrub_silences)
        time_layout.addWidget(self.main_scrub_silences_checkbox)
        
        time_layout.addStretch()
        
        # Remove the smaller time display and just use the main one at the top
        # Add a spacer instead to maintain layout
        spacer = QWidget()
        spacer.setFixedHeight(20)
        time_layout.addWidget(spacer)
        
        record_container_layout.addLayout(time_layout)
        
        # Add the record container to the left column
        left_column.addWidget(record_container)
        
        # Transcription progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setVisible(False)  # Hide initially
        left_column.addWidget(self.progress_bar)
        
        # Transcribed text section
        transcribe_header = QLabel("TRANSCRIBE")
        transcribe_header.setStyleSheet("font-size: 15px; font-weight: bold; color: #1A1A1A; background-color: #34A853; padding: 8px 12px; border-radius: 3px; margin-top: 10px;")
        left_column.addWidget(transcribe_header)
        
        # Add description text in a container with subtle background
        transcribe_container = QWidget()
        transcribe_container.setStyleSheet("background-color: #F0F8F1; border: 1px solid #D4E9D7; border-radius: 5px; padding: 10px; margin-bottom: 5px;")
        transcribe_container_layout = QVBoxLayout(transcribe_container)
        transcribe_container_layout.setContentsMargins(10, 10, 10, 10)
        
        # Add description text
        transcribe_description = QLabel("Text after transcription by Whisper API.")
        transcribe_description.setStyleSheet("font-style: italic; color: #666; margin-bottom: 6px; font-size: 12px;")
        transcribe_description.setWordWrap(True)
        transcribe_description.setFixedHeight(20)  # Set fixed height to prevent overlap
        transcribe_container_layout.addWidget(transcribe_description)
        
        # Add the transcribe container to the left column
        left_column.addWidget(transcribe_container)
        
        # Transcribed text display
        left_column.addWidget(self.transcribed_text)
        
        # Add edit hint for transcribed text
        transcribe_edit_hint = QLabel("You can edit the transcribed text before processing.")
        transcribe_edit_hint.setStyleSheet("font-style: italic; color: #666; font-size: 12px;")
        left_column.addWidget(transcribe_edit_hint)
        
        # Add clear and copy buttons for transcribed text
        transcribe_buttons_layout = QHBoxLayout()
        
        # Clear transcribed text button
        self.clear_transcribed_button = QPushButton()
        self.clear_transcribed_button.setIcon(QIcon.fromTheme("edit-clear", QIcon.fromTheme("edit-delete")))
        self.clear_transcribed_button.setToolTip("Clear Transcribed Text")
        self.clear_transcribed_button.clicked.connect(self.clear_transcribed_text)
        self.clear_transcribed_button.setEnabled(False)
        transcribe_buttons_layout.addWidget(self.clear_transcribed_button)
        
        # Copy transcribed text button
        self.copy_transcribed_button = QPushButton()
        self.copy_transcribed_button.setIcon(QIcon.fromTheme("edit-copy"))
        self.copy_transcribed_button.setToolTip("Copy to Clipboard")
        self.copy_transcribed_button.clicked.connect(self.copy_transcribed_text)
        self.copy_transcribed_button.setEnabled(False)
        transcribe_buttons_layout.addWidget(self.copy_transcribed_button)
        
        transcribe_buttons_layout.addStretch()
        left_column.addLayout(transcribe_buttons_layout)
        
        # Transcription buttons
        transcribe_buttons_layout = QHBoxLayout()
        
        self.transcribe_button = QPushButton("Transcribe Audio")
        self.transcribe_button.clicked.connect(self.transcribe_audio)
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.setToolTip("Transcribe Audio (Ctrl+T)")
        transcribe_buttons_layout.addWidget(self.transcribe_button)
        
        self.transcribe_process_button = QPushButton("Transcribe and Process")
        self.transcribe_process_button.clicked.connect(self.transcribe_and_process)
        self.transcribe_process_button.setEnabled(False)
        transcribe_buttons_layout.addWidget(self.transcribe_process_button)
        
        left_column.addLayout(transcribe_buttons_layout)
        
        # ===== RIGHT COLUMN =====
        # Process section
        process_header = QLabel("PROCESS")
        process_header.setStyleSheet("font-size: 15px; font-weight: bold; color: #1A1A1A; background-color: #FBBC05; padding: 8px 12px; border-radius: 3px;")
        right_column.addWidget(process_header)
        
        # Add shaded container for process section
        process_container = QWidget()
        process_container.setStyleSheet("background-color: #FEF9E7; border: 1px solid #FCF3CF; border-radius: 5px; padding: 10px;")
        process_container_layout = QVBoxLayout(process_container)
        process_container_layout.setContentsMargins(10, 10, 10, 10)
        
        # Add description text
        process_description = QLabel(
            "Choose formatting instructions to improve and process the dictated text. The basic cleanup mode is selected by default."
        )
        process_description.setStyleSheet("font-style: italic; color: #666; margin-bottom: 6px; font-size: 12px;")
        process_description.setWordWrap(True)
        process_description.setFixedHeight(40)  # Set fixed height to prevent overlap
        process_container_layout.addWidget(process_description)
        
        # Processing mode selection - replaced with a button to open modal
        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(12)
        
        # Create a horizontal layout for the mode selection info and button
        mode_info_layout = QHBoxLayout()
        
        # Add selection count indicator
        self.selection_count_label = QLabel("1 mode selected: Basic Cleanup Only")
        self.selection_count_label.setStyleSheet("font-weight: bold; color: #1565C0;")
        mode_info_layout.addWidget(self.selection_count_label)
        
        mode_info_layout.addStretch()
        
        # Add button to open the modal dialog
        self.manage_modes_button = QPushButton("Mode Management")
        self.manage_modes_button.setStyleSheet("padding: 5px 10px; background-color: #2196F3; color: white; font-weight: bold; font-size: 12px;")
        self.manage_modes_button.clicked.connect(self.show_manage_selections_dialog)
        mode_info_layout.addWidget(self.manage_modes_button)
        
        mode_layout.addLayout(mode_info_layout)
        
        # Create a hidden list widget to store the selected modes
        # This won't be displayed but will maintain the selection state
        self.mode_list = QListWidget()
        self.mode_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.mode_list.setVisible(False)  # Hide the list widget
        self.mode_list.itemSelectionChanged.connect(self.update_mode_selection_count)
        
        process_container_layout.addLayout(mode_layout)
        
        # Process button
        process_button_layout = QHBoxLayout()
        self.process_button = QPushButton("Process")
        self.process_button.clicked.connect(self.process_text)
        self.process_button.setEnabled(False)
        self.process_button.setToolTip("Process Text (Ctrl+P)")
        process_button_layout.addWidget(self.process_button)
        process_button_layout.addStretch()
        process_container_layout.addLayout(process_button_layout)
        
        # Add the process container to the right column
        right_column.addWidget(process_container)
        
        # Processed text display
        self.processed_text = QTextEdit()
        self.processed_text.setMinimumHeight(200)
        self.processed_text.setPlaceholderText("Processed text will appear here. You can edit the text before saving.")
        right_column.addWidget(self.processed_text)
        
        # Add edit hint for processed text
        processed_edit_hint = QLabel("You can edit the processed text before saving.")
        processed_edit_hint.setStyleSheet("font-style: italic; color: #666; font-size: 12px;")
        right_column.addWidget(processed_edit_hint)
        
        # Add clear and copy buttons for processed text
        processed_buttons_layout = QHBoxLayout()
        
        # Clear processed text button
        self.clear_processed_button = QPushButton()
        self.clear_processed_button.setIcon(QIcon.fromTheme("edit-clear", QIcon.fromTheme("edit-delete")))
        self.clear_processed_button.setToolTip("Clear Processed Text")
        self.clear_processed_button.clicked.connect(self.clear_processed_text)
        self.clear_processed_button.setEnabled(False)
        processed_buttons_layout.addWidget(self.clear_processed_button)
        
        # Copy processed text button
        self.copy_processed_button = QPushButton()
        self.copy_processed_button.setIcon(QIcon.fromTheme("edit-copy"))
        self.copy_processed_button.setToolTip("Copy to Clipboard")
        self.copy_processed_button.clicked.connect(self.copy_processed_text)
        self.copy_processed_button.setEnabled(False)
        processed_buttons_layout.addWidget(self.copy_processed_button)
        
        processed_buttons_layout.addStretch()
        right_column.addLayout(processed_buttons_layout)
        
        # Save section
        save_header = QLabel("SAVE")
        save_header.setStyleSheet("font-size: 15px; font-weight: bold; color: #1A1A1A; background-color: #EA4335; padding: 8px 12px; border-radius: 3px; margin-top: 10px;")
        right_column.addWidget(save_header)
        
        # Add shaded container for save section
        save_container = QWidget()
        save_container.setStyleSheet("background-color: #FDEDEC; border: 1px solid #F5B7B1; border-radius: 5px; padding: 10px;")
        save_container_layout = QVBoxLayout(save_container)
        save_container_layout.setContentsMargins(10, 10, 10, 10)
        
        # Add description text
        save_description = QLabel("Save your processed text to a file.")
        save_description.setStyleSheet("font-style: italic; color: #666; margin-bottom: 6px; font-size: 12px;")
        save_description.setWordWrap(True)
        save_container_layout.addWidget(save_description)
        
        # Auto-generated filename
        filename_layout = QHBoxLayout()
        filename_label = QLabel("Filename:")
        filename_layout.addWidget(filename_label)
        
        self.filename_display = QLineEdit()
        self.filename_display.setPlaceholderText("Autogenerated with processing or type manually")
        filename_layout.addWidget(self.filename_display, 1)
        
        save_container_layout.addLayout(filename_layout)
        
        # Save button
        save_button_layout = QHBoxLayout()
        self.save_button = QPushButton()
        self.save_button.setIcon(QIcon.fromTheme("document-save"))
        self.save_button.setText("Save")
        self.save_button.clicked.connect(self.save_text)
        self.save_button.setEnabled(False)
        self.save_button.setToolTip("Save Text (Ctrl+W)")
        save_button_layout.addWidget(self.save_button)
        save_button_layout.addStretch()
        save_container_layout.addLayout(save_button_layout)
        
        # Add the save container to the right column
        right_column.addWidget(save_container)
        
        # Populate audio devices
        self.populate_audio_devices()
        
        # Populate processing modes
        self.populate_processing_modes()
    
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
        
        # Audio device settings
        audio_group = QGroupBox("Audio Device Settings")
        audio_layout = QFormLayout(audio_group)
        
        # Audio device selection in settings
        device_settings_layout = QHBoxLayout()
        self.settings_device_combo = QComboBox()
        device_settings_layout.addWidget(self.settings_device_combo, 1)
        
        # Refresh button in settings
        refresh_settings_button = QPushButton()
        refresh_settings_button.setIcon(QIcon.fromTheme("view-refresh"))
        refresh_settings_button.setToolTip("Refresh Audio Devices")
        refresh_settings_button.clicked.connect(self.refresh_settings_audio_devices)
        device_settings_layout.addWidget(refresh_settings_button)
        
        audio_layout.addRow("Default Audio Device:", device_settings_layout)
        
        # Silence removal settings
        self.scrub_silences_checkbox = QCheckBox("Scrub Silences")
        self.scrub_silences_checkbox.setToolTip("Remove long pauses from audio before transcription")
        audio_layout.addRow("Audio Processing:", self.scrub_silences_checkbox)
        
        # Silence threshold settings
        silence_settings_layout = QHBoxLayout()
        self.silence_threshold_edit = QLineEdit()
        self.silence_threshold_edit.setPlaceholderText("Default: -40 dB")
        silence_settings_layout.addWidget(self.silence_threshold_edit)
        
        self.min_silence_duration_edit = QLineEdit()
        self.min_silence_duration_edit.setPlaceholderText("Default: 1.0 seconds")
        silence_settings_layout.addWidget(self.min_silence_duration_edit)
        
        audio_layout.addRow("Silence Threshold / Min Duration:", silence_settings_layout)
        
        self.save_audio_settings_button = QPushButton("Save Audio Settings")
        self.save_audio_settings_button.clicked.connect(self.save_default_audio_device)
        audio_layout.addRow("", self.save_audio_settings_button)
        
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
        layout.addWidget(audio_group)
        layout.addWidget(output_group)
        layout.addStretch()
    
    def setup_system_prompts_tab(self, layout):
        """Set up the system prompts tab UI"""
        # Instructions
        instructions_label = QLabel(
            "Create and edit system prompts for text processing. "
            "Each prompt defines how your text will be processed. "
            "Prompts marked with 'JSON' will return structured data."
        )
        instructions_label.setWordWrap(True)
        layout.addWidget(instructions_label)
        
        # Prompts list
        prompts_group = QGroupBox("Available Prompts")
        prompts_layout = QVBoxLayout(prompts_group)
        
        # Add prompts count label
        self.prompts_count_label = QLabel()
        self.prompts_count_label.setStyleSheet("font-weight: bold; color: #1565C0; margin-bottom: 5px;")
        prompts_layout.addWidget(self.prompts_count_label)
        
        # Use QListWidget with custom item widgets for the tags
        self.prompts_list = QListWidget()
        self.prompts_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.prompts_list.currentItemChanged.connect(self.on_prompt_selected)
        
        # Set style for the list widget to ensure text is visible when selected
        self.prompts_list.setStyleSheet("""
            QListWidget::item:selected {
                background-color: #2196F3;
            }
            QListWidget::item:selected QLabel#promptName {
                color: white;
                font-weight: bold;
            }
        """)
        
        prompts_layout.addWidget(self.prompts_list)
        
        # Buttons for managing prompts
        buttons_layout = QHBoxLayout()
        
        self.add_prompt_button = QPushButton("Add New")
        self.add_prompt_button.clicked.connect(self.add_new_prompt)
        buttons_layout.addWidget(self.add_prompt_button)
        
        self.edit_prompt_button = QPushButton("Edit")
        self.edit_prompt_button.clicked.connect(self.edit_prompt)
        self.edit_prompt_button.setEnabled(False)
        buttons_layout.addWidget(self.edit_prompt_button)
        
        self.delete_prompt_button = QPushButton("Delete")
        self.delete_prompt_button.clicked.connect(self.delete_prompt)
        self.delete_prompt_button.setEnabled(False)
        buttons_layout.addWidget(self.delete_prompt_button)
        
        prompts_layout.addLayout(buttons_layout)
        
        # Prompt details
        details_group = QGroupBox("Prompt Details")
        details_layout = QVBoxLayout(details_group)
        
        self.prompt_text_edit = QTextEdit()
        self.prompt_text_edit.setPlaceholderText("Select a prompt to view or edit its details...")
        self.prompt_text_edit.setReadOnly(True)
        details_layout.addWidget(self.prompt_text_edit)
        
        # JSON indicator in details
        self.json_indicator = QLabel("")
        self.json_indicator.setVisible(False)
        details_layout.addWidget(self.json_indicator)
        
        # Add all sections to layout
        layout.addWidget(prompts_group)
        layout.addWidget(details_group)
        
        # Populate prompts list
        self.populate_prompts_list()
    
    def setup_variables_tab(self, layout):
        """Set up the variables tab UI"""
        # Instructions header
        header_label = QLabel("VARIABLES")
        header_label.setStyleSheet("font-size: 15px; font-weight: bold; color: white; background-color: rgba(33, 150, 243, 0.9); padding: 8px 12px; border-radius: 3px;")
        layout.addWidget(header_label)
        
        # Description
        description_label = QLabel(
            "Variables allow you to personalize system prompts. When writing a system prompt, "
            "you can include these variables using the placeholders shown below, and they will "
            "be replaced with your saved values when the prompt is used."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("font-style: italic; color: #666; margin-bottom: 10px; font-size: 12px;")
        layout.addWidget(description_label)
        
        # Variables form
        variables_group = QGroupBox("Your Variables")
        variables_layout = QFormLayout(variables_group)
        
        # User name
        self.user_name_input = QLineEdit()
        self.user_name_input.setPlaceholderText("Enter your name")
        variables_layout.addRow("Name:", self.user_name_input)
        
        # Variable placeholder info
        name_placeholder_label = QLabel("Use <b>{user_name}</b> in your prompts")
        name_placeholder_label.setStyleSheet("color: #1565C0; font-size: 11px;")
        variables_layout.addRow("", name_placeholder_label)
        
        # Email signature
        self.email_signature_input = QTextEdit()
        self.email_signature_input.setPlaceholderText("Enter your email signature")
        self.email_signature_input.setMaximumHeight(100)
        variables_layout.addRow("Email Signature:", self.email_signature_input)
        
        # Variable placeholder info
        signature_placeholder_label = QLabel("Use <b>{email_signature}</b> in your prompts")
        signature_placeholder_label.setStyleSheet("color: #1565C0; font-size: 11px;")
        variables_layout.addRow("", signature_placeholder_label)
        
        # Add some spacing
        layout.addWidget(variables_group)
        
        # Example usage section
        example_group = QGroupBox("Example Usage")
        example_layout = QVBoxLayout(example_group)
        
        example_text = QLabel(
            "Example system prompt using variables:<br><br>"
            "<i>\"Format this text as an email from {user_name}. "
            "Include the following signature at the end: {email_signature}\"</i>"
        )
        example_text.setWordWrap(True)
        example_text.setTextFormat(Qt.TextFormat.RichText)
        example_layout.addWidget(example_text)
        
        layout.addWidget(example_group)
        
        # Save button
        save_button = QPushButton("Save Variables")
        save_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        save_button.clicked.connect(self.save_variables)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        # Load variables
        self.load_variables()
    
    def setup_about_tab(self, layout):
        """Set up the about tab UI"""
        # Create a scrollable area for the about content
        scroll_area = QWidget()
        scroll_layout = QVBoxLayout(scroll_area)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # App title
        title_label = QLabel("Speech Note Capture")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #1565C0;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(title_label)
        
        # Description
        description = QLabel(
            "<p>Speech Note Capture is an AI-powered speech-to-text application "
            "that allows you to transcribe audio recordings and optionally process the text using "
            "various AI-driven formatting options.</p>"
            
            "<p><strong>Important:</strong> Processing is completely optional but can significantly enhance the utility "
            "of your transcriptions. You can use this application simply for transcription, or take advantage "
            "of the powerful text processing capabilities to format and refine your dictated content.</p>"
            
            "<p>The application uses OpenAI's Whisper API for speech recognition and "
            "GPT models for text processing, providing a seamless experience for "
            "converting spoken words into formatted text.</p>"
            
            "<p>This project was developed as an AI code generation project using "
            "Sonnet 3.7, Windsurf, and iterative prompting and editing.</p>"
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 14px; margin: 10px 0;")
        description.setTextFormat(Qt.TextFormat.RichText)
        scroll_layout.addWidget(description)
        
        # Features section
        features_label = QLabel("Key Features:")
        features_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px;")
        scroll_layout.addWidget(features_label)
        
        features_list = QLabel(
            "<ul>"
            "<li>Record audio directly from your microphone</li>"
            "<li>Transcribe audio using OpenAI's Whisper API</li>"
            "<li>Process text with various AI-powered formatting options</li>"
            "<li>Create and customize your own text processing prompts</li>"
            "<li>Save processed text to files with auto-generated filenames</li>"
            "<li>Apply multiple processing modes simultaneously</li>"
            "</ul>"
        )
        features_list.setTextFormat(Qt.TextFormat.RichText)
        features_list.setWordWrap(True)
        scroll_layout.addWidget(features_list)
        
        # Add some spacing
        scroll_layout.addStretch()
        
        # Repository link at the bottom
        repo_layout = QHBoxLayout()
        repo_label = QLabel("GitHub Repository:")
        repo_label.setStyleSheet("font-weight: bold;")
        repo_layout.addWidget(repo_label)
        
        repo_link = QLabel("<a href='https://github.com/danielrosehill/Whisper-Notepad-For-Linux'>https://github.com/danielrosehill/Whisper-Notepad-For-Linux</a>")
        repo_link.setOpenExternalLinks(True)
        repo_link.setTextFormat(Qt.TextFormat.RichText)
        repo_layout.addWidget(repo_link)
        repo_layout.addStretch()
        
        scroll_layout.addLayout(repo_layout)
        
        # Add the scroll area to the main layout
        layout.addWidget(scroll_area)
    
    def populate_prompts_list(self):
        """Populate the prompts list with available prompts"""
        self.prompts_list.clear()
        
        modes = self.openai_manager.get_available_modes()
        
        # Update the prompts count label
        self.prompts_count_label.setText(f"{len(modes)} system prompts available")
        
        for mode in modes:
            # Create item with type label (Default or User)
            is_default = mode["id"] in self.openai_manager.DEFAULT_TEXT_PROCESSING_MODES
            requires_json = mode.get("requires_json", False)
            
            # Create a custom widget for the list item with columns
            item_widget = QWidget()
            item_layout = QVBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 5, 5, 5)
            item_layout.setSpacing(2)
            
            # Top row with name and tags
            top_row = QHBoxLayout()
            
            # Name label (left column)
            name_label = QLabel(mode['name'])
            name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: black;")
            name_label.setObjectName("promptName")  # Add an object name for CSS targeting
            top_row.addWidget(name_label, 4)  # Give it more stretch
            
            # JSON indicator if applicable
            if requires_json:
                json_label = QLabel("JSON")
                json_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                json_label.setStyleSheet(
                    "background-color: #FF9800; color: white; border-radius: 4px; padding: 2px 8px; font-size: 11px; max-width: 70px;"
                )
                top_row.addWidget(json_label, 1)
            
            # Tag label (right column)
            if is_default:
                # Create a green button for default tags
                tag_label = QLabel("Default")
                tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                tag_label.setStyleSheet(
                    "background-color: #4CAF50; color: white; border-radius: 4px; padding: 2px 8px; font-size: 11px; max-width: 70px;"
                )
            else:
                # Create a differently colored button for user tags
                tag_label = QLabel("User")
                tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                tag_label.setStyleSheet(
                    "background-color: #2196F3; color: white; border-radius: 4px; padding: 2px 8px; font-size: 11px; max-width: 70px;"
                )
            
            top_row.addWidget(tag_label, 1)  # Give it less stretch
            
            # Add top row to main layout
            item_layout.addLayout(top_row)
            
            # Add description if available
            if 'description' in mode and mode['description']:
                desc_label = QLabel(mode['description'])
                desc_label.setWordWrap(True)
                desc_label.setStyleSheet("font-size: 12px; color: #666; font-style: italic;")
                desc_label.setMaximumHeight(40)  # Limit height to prevent overly tall items
                item_layout.addWidget(desc_label)
            
            # Create list item
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, mode["id"])
            item.setSizeHint(item_widget.sizeHint())  # Ensure proper sizing
            
            # Add the item to the list
            self.prompts_list.addItem(item)
            self.prompts_list.setItemWidget(item, item_widget)
    
    def on_prompt_selected(self, current, previous):
        """Handle prompt selection"""
        if current:
            mode_id = current.data(Qt.ItemDataRole.UserRole)
            prompt_text = self.openai_manager.get_prompt(mode_id)
            requires_json = self.openai_manager.requires_json(mode_id)
            
            self.prompt_text_edit.setText(prompt_text)
            
            # Update JSON indicator
            if requires_json:
                self.json_indicator.setText("This prompt requires a JSON response")
                self.json_indicator.setStyleSheet("color: #FF9800; font-weight: bold;")
                self.json_indicator.setVisible(True)
            else:
                self.json_indicator.setVisible(False)
            
            # Get the name from the widget instead of the item directly
            item_widget = self.prompts_list.itemWidget(current)
            if item_widget:
                # The name is in the first child widget (QLabel)
                for child in item_widget.children():
                    if isinstance(child, QLabel) and child.objectName() == "promptName":
                        self.selected_prompt_name = child.text()
                        # Update the label text color to white when selected
                        child.setStyleSheet("font-size: 14px; font-weight: bold; color: white;")
                        break
            
            # Enable edit/delete buttons
            self.edit_prompt_button.setEnabled(True)
            
            # All prompts can be deleted now
            self.delete_prompt_button.setEnabled(True)
        else:
            self.prompt_text_edit.clear()
            self.selected_prompt_name = ""
            self.edit_prompt_button.setEnabled(False)
            self.delete_prompt_button.setEnabled(False)
            self.json_indicator.setVisible(False)
        
        # Reset text color of non-selected items
        for i in range(self.prompts_list.count()):
            item = self.prompts_list.item(i)
            if item != current:
                item_widget = self.prompts_list.itemWidget(item)
                if item_widget:
                    for child in item_widget.children():
                        if isinstance(child, QLabel) and child.objectName() == "promptName":
                            child.setStyleSheet("font-size: 14px; font-weight: bold; color: black;")
                            break
    
    def add_new_prompt(self):
        """Add a new custom prompt"""
        # Get prompt name
        name, ok = QInputDialog.getText(
            self, "New Prompt", "Enter a name for the new prompt:"
        )
        
        if ok and name:
            # Generate mode_id from name
            mode_id = name.lower().replace(" ", "_")
            
            # Check if mode_id already exists
            modes = self.openai_manager.get_available_modes()
            existing_ids = [mode["id"] for mode in modes]
            
            if mode_id in existing_ids:
                QMessageBox.warning(
                    self, "Duplicate Name", 
                    f"A prompt with the name '{name}' already exists. Please choose a different name."
                )
                return
            
            # Create prompt edit dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Create Prompt: {name}")
            dialog.setMinimumSize(600, 400)
            
            layout = QVBoxLayout(dialog)
            
            # Instructions
            instructions = QLabel(
                "Enter the system prompt that will be used for processing text. "
                "This prompt should instruct the AI on how to transform the input text."
            )
            instructions.setWordWrap(True)
            layout.addWidget(instructions)
            
            # Text edit for prompt
            prompt_edit = QTextEdit()
            prompt_edit.setPlaceholderText("Enter your system prompt here...")
            layout.addWidget(prompt_edit)
            
            # JSON checkbox
            json_checkbox = QCheckBox("Requires JSON Response")
            json_checkbox.setToolTip("Enable this if the prompt expects a structured JSON response from the AI")
            layout.addWidget(json_checkbox)
            
            # Buttons
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            # Show dialog
            if dialog.exec() == QDialog.DialogCode.Accepted:
                prompt_text = prompt_edit.toPlainText()
                requires_json = json_checkbox.isChecked()
                
                if prompt_text:
                    # Add prompt with JSON flag
                    self.openai_manager.add_custom_prompt(mode_id, name, prompt_text, requires_json)
                    
                    # Refresh lists
                    self.populate_prompts_list()
                    self.populate_processing_modes()
                    
                    # Select the new prompt
                    for i in range(self.prompts_list.count()):
                        item = self.prompts_list.item(i)
                        if item.data(Qt.ItemDataRole.UserRole) == mode_id:
                            self.prompts_list.setCurrentItem(item)
                            break
                else:
                    QMessageBox.warning(self, "Empty Prompt", "The prompt cannot be empty.")
    
    def edit_prompt(self):
        """Edit the selected prompt"""
        current_item = self.prompts_list.currentItem()
        if not current_item:
            return
        
        mode_id = current_item.data(Qt.ItemDataRole.UserRole)
        name = self.selected_prompt_name  # Use the stored name
        current_prompt = self.openai_manager.get_prompt(mode_id)
        requires_json = self.openai_manager.requires_json(mode_id)
        
        # Create prompt edit dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Prompt: {name}")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Instructions
        instructions = QLabel(
            "Edit the system prompt that will be used for processing text. "
            "This prompt should instruct the AI on how to transform the input text."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Text edit for prompt
        prompt_edit = QTextEdit()
        prompt_edit.setText(current_prompt)
        layout.addWidget(prompt_edit)
        
        # JSON checkbox
        json_checkbox = QCheckBox("Requires JSON Response")
        json_checkbox.setChecked(requires_json)
        json_checkbox.setToolTip("Enable this if the prompt expects a structured JSON response from the AI")
        layout.addWidget(json_checkbox)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            prompt_text = prompt_edit.toPlainText()
            requires_json = json_checkbox.isChecked()
            
            if prompt_text:
                # Update prompt with JSON flag
                self.openai_manager.add_custom_prompt(mode_id, name, prompt_text, requires_json)
                
                # Refresh prompt text
                self.prompt_text_edit.setText(prompt_text)
                
                # Refresh lists to update JSON indicator
                self.populate_prompts_list()
                self.populate_processing_modes()
            else:
                QMessageBox.warning(self, "Empty Prompt", "The prompt cannot be empty.")
    
    def delete_prompt(self):
        """Delete the selected prompt"""
        current_item = self.prompts_list.currentItem()
        if not current_item:
            return
        
        mode_id = current_item.data(Qt.ItemDataRole.UserRole)
        name = self.selected_prompt_name  # Use the stored name
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete the prompt '{name}'?",
            QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Delete prompt
            if self.openai_manager.delete_custom_prompt(mode_id):
                # Refresh lists
                self.populate_prompts_list()
                self.populate_processing_modes()
                
                # Clear prompt text
                self.prompt_text_edit.clear()
            else:
                QMessageBox.warning(
                    self, "Deletion Failed", 
                    "Could not delete the prompt."
                )
    
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
        
        # Load audio devices for both combos
        self.refresh_audio_devices()
        self.populate_settings_audio_devices()
        
        # Load default audio device
        device_index_str = self.config.get("default_audio_device", "")
        if device_index_str and device_index_str.isdigit():
            device_index = int(device_index_str)
            # Find the device in both combo boxes
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == device_index:
                    self.device_combo.setCurrentIndex(i)
                    break
            
            for i in range(self.settings_device_combo.count()):
                if self.settings_device_combo.itemData(i) == device_index:
                    self.settings_device_combo.setCurrentIndex(i)
                    break
        
        # Load silence removal settings
        scrub_silences = self.config.get("scrub_silences", True)
        self.scrub_silences_checkbox.setChecked(scrub_silences)
        self.main_scrub_silences_checkbox.setChecked(scrub_silences)
        
        # Load silence threshold settings
        silence_threshold = self.config.get("silence_threshold", -40)
        self.silence_threshold_edit.setText(str(silence_threshold))
        
        min_silence_duration = self.config.get("min_silence_duration", 1.0)
        self.min_silence_duration_edit.setText(str(min_silence_duration))
        
        # Always use basic_cleanup as default processing mode
        # We don't load the last_used_mode from config anymore
        for i in range(self.mode_list.count()):
            item = self.mode_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == "basic_cleanup":
                item.setSelected(True)
                break
    
    def refresh_audio_devices(self):
        """Refresh the list of audio devices"""
        # Get current device if selected
        current_device = None
        if self.device_combo.currentIndex() >= 0:
            current_device = self.device_combo.currentData()
        
        # Populate devices
        self.populate_audio_devices()
        
        # Try to reselect the previous device
        if current_device:
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == current_device:
                    self.device_combo.setCurrentIndex(i)
                    break
    
    def populate_processing_modes(self):
        """Populate the processing modes list widget"""
        # Clear existing items
        self.mode_list.clear()
        
        # Get available modes from OpenAI manager
        modes = self.openai_manager.get_available_modes()
        
        # Add modes to the list widget
        for mode in modes:
            # Create a list item
            item = QListWidgetItem(mode["name"])
            
            # Store the mode info in the item's data
            item.setData(Qt.ItemDataRole.UserRole, mode["id"])
            
            # Set tooltip to show description
            tooltip_text = mode.get("description", mode.get("prompt", "")[:100] + "...").replace("\n", " ")
            item.setToolTip(tooltip_text)
            
            # Add the item to the list
            self.mode_list.addItem(item)
        
        # Select "Basic Cleanup" by default
        basic_cleanup_selected = False
        for i in range(self.mode_list.count()):
            item = self.mode_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == "basic_cleanup":
                item.setSelected(True)
                basic_cleanup_selected = True
                break
        
        # If basic_cleanup wasn't found, select the first item
        if not basic_cleanup_selected and self.mode_list.count() > 0:
            self.mode_list.item(0).setSelected(True)
                
        # Update the selection count
        self.update_mode_selection_count()
        
        # Enable the process button if there's transcribed text
        has_text = bool(self.transcribed_text.toPlainText().strip())
        self.process_button.setEnabled(has_text and self.mode_list.selectedItems())
    
    def populate_audio_devices(self):
        """Populate the list of audio devices"""
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
    
    def start_recording(self):
        """Start audio recording"""
        if not self.audio_manager.is_recording:
            # Start recording
            device_index = self.device_combo.currentData()
            if self.audio_manager.start_recording(device_index):
                self.record_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                self.pause_button.setEnabled(True)
                self.clear_button.setEnabled(False)
                self.device_combo.setEnabled(False)
                
                # Save selected device to config
                self.config.set("default_audio_device", str(device_index))
                
                # Reset recording time and start timer
                self.recording_time = 0
                self.main_time_display.setText("00:00")
                self.recording_timer.start(1000)
            else:
                QMessageBox.warning(self, "Error", "Failed to start recording. Please check your microphone.")
        else:
            # Stop recording
            if self.audio_manager.stop_recording():
                self.record_button.setEnabled(True)
                self.stop_button.setEnabled(False)
                self.pause_button.setEnabled(False)
                self.clear_button.setEnabled(True)
                self.device_combo.setEnabled(True)
                self.recording_timer.stop()
                
                # Enable transcribe button if we have recorded audio
                if self.audio_manager.get_recording_duration() > 0:
                    self.transcribe_button.setEnabled(True)
                    self.transcribe_process_button.setEnabled(True)
    
    def stop_recording(self):
        """Stop audio recording"""
        if self.audio_manager.is_recording:
            # Stop recording
            if self.audio_manager.stop_recording():
                self.record_button.setEnabled(True)
                self.stop_button.setEnabled(False)
                self.pause_button.setEnabled(False)
                self.clear_button.setEnabled(True)
                self.device_combo.setEnabled(True)
                self.recording_timer.stop()
                
                # Enable transcribe button if we have recording
                if self.audio_manager.get_recording_duration() > 0:
                    self.transcribe_button.setEnabled(True)
                    self.transcribe_process_button.setEnabled(True)
    
    def toggle_pause(self):
        """Toggle pause/resume recording"""
        if self.audio_manager.is_recording:
            if not self.audio_manager.is_paused:
                # Pause recording
                if self.audio_manager.pause_recording():
                    self.pause_button.setToolTip("Resume")
                    self.pause_button.setIcon(QIcon.fromTheme("media-playback-start"))
                    self.statusBar().showMessage("Recording paused", 2000)
                    # Stop the timer while paused
                    self.recording_timer.stop()
            else:
                # Resume recording
                if self.audio_manager.resume_recording():
                    self.pause_button.setToolTip("Pause")
                    self.pause_button.setIcon(QIcon.fromTheme("media-playback-pause"))
                    self.statusBar().showMessage("Recording resumed", 2000)
                    # Restart the timer
                    self.recording_timer.start(1000)  # 1 second interval
    
    def update_recording_time(self):
        """Update recording time display"""
        self.recording_time += 1
        minutes = self.recording_time // 60
        seconds = self.recording_time % 60
        self.main_time_display.setText(f"{minutes:02d}:{seconds:02d}")
    
    def transcribe_audio(self):
        """Transcribe the recorded audio"""
        if not self.audio_manager.has_recording():
            QMessageBox.warning(self, "Error", "No audio data to transcribe.")
            return
            
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
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.transcribe_button.setEnabled(False)
        self.transcribe_process_button.setEnabled(False)
        
        # Start transcription in background thread
        self.transcription_worker = TranscriptionWorker(self.openai_manager, temp_file)
        self.transcription_worker.progress.connect(self.update_transcription_progress)
        self.transcription_worker.finished.connect(self._handle_transcription_result)
        self.transcription_worker.start()
    
    def transcribe_and_process(self):
        """Transcribe audio and then process the transcribed text"""
        if not self.audio_manager.has_recording():
            QMessageBox.warning(self, "Error", "No audio data to transcribe.")
            return
        
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
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.transcribe_button.setEnabled(False)
        self.transcribe_process_button.setEnabled(False)
        
        # Start transcription in background thread
        self.transcription_worker = TranscriptionWorker(self.openai_manager, temp_file)
        self.transcription_worker.progress.connect(self.update_transcription_progress)
        self.transcription_worker.finished.connect(self.handle_transcription_result_for_processing)
        self.transcription_worker.start()
    
    def handle_transcription_result_for_processing(self, result):
        """Handle transcription result and proceed to processing"""
        if result.get("success", False):
            transcribed_text = result.get("text", "")
            
            # Set the transcribed text in the text edit
            self.transcribed_text.setPlainText(transcribed_text)
            
            # Enable clear and copy buttons for transcribed text
            self.clear_transcribed_button.setEnabled(True)
            self.copy_transcribed_button.setEnabled(True)
            
            # Update status
            self.statusBar().showMessage("Transcription complete. Processing text...")
            
            # Give the user a brief moment to see the transcription before processing
            # This also allows them to cancel processing if needed
            QTimer.singleShot(500, self.process_text)
        else:
            error_message = result.get("error", "Unknown error")
            QMessageBox.warning(self, "Transcription Error", f"Failed to transcribe audio: {error_message}")
            self.statusBar().showMessage("Error transcribing audio")
            
            # Re-enable buttons
            self.transcribe_button.setEnabled(True)
            self.transcribe_process_button.setEnabled(True)
    
    def update_transcription_progress(self, value):
        """Update transcription progress bar"""
        self.progress_bar.setValue(value)
    
    def _handle_transcription_result(self, result):
        """Handle the transcription result"""
        # Hide progress
        self.progress_bar.setVisible(False)
        self.transcribe_button.setEnabled(True)
        self.transcribe_process_button.setEnabled(True)
        
        # Safety check to ensure transcribed_text is properly initialized
        if not hasattr(self.transcribed_text, 'setPlainText'):
            print("Error: self.transcribed_text is not properly initialized as a QTextEdit")
            QMessageBox.critical(self, "Application Error", "Internal error: Text widget not properly initialized")
            return
        
        if isinstance(result, dict) and result.get("success", False):
            # Update transcribed text
            transcription_text_content = result.get("text", "")
            if transcription_text_content:
                self.transcribed_text.setPlainText(transcription_text_content)
                
                # Enable process button
                self.process_button.setEnabled(True)
                
                # Enable clear and copy buttons for transcribed text
                self.clear_transcribed_button.setEnabled(True)
                self.copy_transcribed_button.setEnabled(True)
                
                # Update status
                self.statusBar().showMessage("Transcription complete")
            else:
                QMessageBox.warning(self, "Transcription Error", "No text was transcribed from the audio.")
                self.statusBar().showMessage("Transcription failed")
        else:
            # Show error message
            error_message = result.get("error", "Unknown error") if isinstance(result, dict) else "Unknown error"
            QMessageBox.warning(self, "Transcription Error", f"Failed to transcribe audio: {error_message}")
            self.statusBar().showMessage("Transcription failed")
    
    def handle_transcription_result(self, result):
        """Handle transcription result"""
        # Hide progress
        self.progress_bar.setVisible(False)
        self.transcribe_button.setEnabled(True)
        
        # Safety check to ensure transcribed_text is properly initialized
        if not hasattr(self.transcribed_text, 'setPlainText'):
            print("Error: self.transcribed_text is not properly initialized as a QTextEdit")
            QMessageBox.critical(self, "Application Error", "Internal error: Text widget not properly initialized")
            return
        
        if result.get("success", False):
            # Update transcribed text
            transcribed_text_content = result.get("text", "")
            self.transcribed_text.setPlainText(transcribed_text_content)
            
            # Enable processing button
            self.process_button.setEnabled(True)
        else:
            # Show error message
            error_message = result.get("error", "Unknown error")
            QMessageBox.warning(self, "Transcription Error", f"Failed to transcribe audio: {error_message}")
    
    def process_text(self):
        """Process the transcribed text using the selected mode(s)"""
        # Get the current text from the transcribed_text widget
        # This ensures any edits made by the user are included
        transcribed_text = self.transcribed_text.toPlainText()
        if not transcribed_text:
            QMessageBox.warning(self, "Warning", "No transcribed text to process")
            return
        
        # Get selected mode IDs
        selected_modes = []
        selected_mode_names = []
        for i in range(self.mode_list.count()):
            item = self.mode_list.item(i)
            if item.isSelected():
                mode_id = item.data(Qt.ItemDataRole.UserRole)
                selected_modes.append(mode_id)
                selected_mode_names.append(item.text())
        
        if not selected_modes:
            QMessageBox.warning(self, "Warning", "No processing mode selected")
            return
        
        # Update status message based on number of selected modes
        if len(selected_modes) == 1:
            self.statusBar().showMessage(f"Processing text with mode: {selected_mode_names[0]}...")
        else:
            self.statusBar().showMessage(f"Processing text with {len(selected_modes)} modes...")
        
        QApplication.processEvents()
        
        try:
            # If only one mode is selected, process normally
            if len(selected_modes) == 1:
                result = self.openai_manager.process_text(transcribed_text, selected_modes[0])
            else:
                # If multiple modes are selected, use the process_text_with_multiple_modes method
                result = self.openai_manager.process_text_with_multiple_modes(transcribed_text, selected_modes)
            
            if result.get("success", False):
                processed_text = result.get("processed_text", "")
                suggested_filename = result.get("suggested_filename", "")
                
                self.processed_text.setPlainText(processed_text)
                
                # Enable clear and copy buttons for processed text
                self.clear_processed_button.setEnabled(True)
                self.copy_processed_button.setEnabled(True)
                
                # Generate filename from suggested title
                if suggested_filename:
                    self.filename_display.setText(f"{suggested_filename}.md")
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    self.filename_display.setText(f"note_{timestamp}.md")
                
                self.process_button.setEnabled(True)
                self.save_button.setEnabled(True)
                
                # Update status message based on number of selected modes
                if len(selected_modes) == 1:
                    self.statusBar().showMessage(f"Text processed successfully with mode: {selected_mode_names[0]}")
                else:
                    self.statusBar().showMessage(f"Text processed successfully with {len(selected_modes)} modes")
            else:
                error_message = result.get("error", "Unknown error")
                if "requires JSON" in error_message and len(selected_modes) > 1:
                    QMessageBox.warning(
                        self, 
                        "Processing Error", 
                        "Cannot combine JSON-requiring modes with other modes. Please select either a single JSON mode or multiple non-JSON modes."
                    )
                else:
                    QMessageBox.warning(self, "Processing Error", f"Failed to process text: {error_message}")
                self.statusBar().showMessage("Error processing text")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error processing text: {str(e)}")
            self.statusBar().showMessage("Error processing text")
    
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
        filename = self.filename_display.text()
        if not filename:
            filename = f"note-{time.strftime('%Y-%m-%d-%H%M%S')}.md"
        
        # Ensure filename has .md extension
        if not filename.lower().endswith(".md"):
            filename += ".md"
        
        # Full file path
        file_path = os.path.join(output_dir, filename)
        
        # Get text to save from the processed_text widget
        # This ensures any edits made by the user are included in the saved file
        text = self.processed_text.toPlainText()
        
        try:
            # Write text to file
            with open(file_path, "w") as f:
                f.write(text)
            
            QMessageBox.information(self, "Success", f"File saved successfully:\n{file_path}")
            self.statusBar().showMessage(f"File saved: {filename}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save file: {str(e)}")
            self.statusBar().showMessage("Error saving file")
    
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
            QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Clear audio recording
            self.audio_manager.clear_recording()
            self.recording_time = 0
            self.update_recording_time()
            self.transcribe_button.setEnabled(False)
            self.transcribe_process_button.setEnabled(False)
            self.refresh_audio_devices()
            
            # Clear transcription
            self.transcribed_text.setPlainText("")
            self.clear_transcribed_button.setEnabled(False)
            self.copy_transcribed_button.setEnabled(False)
            
            # Clear processed text
            self.processed_text.setPlainText("")
            self.clear_processed_button.setEnabled(False)
            self.copy_processed_button.setEnabled(False)
            
            # Clear filename
            self.filename_display.clear()
            
            # Clear cache
            self.config.clear_cache()
            
            # Reset recording button if not recording
            if not self.audio_manager.is_recording:
                self.record_button.setToolTip("Start Recording")
                self.pause_button.setToolTip("Pause Recording")
                self.pause_button.setEnabled(False)
                self.refresh_audio_devices()
            
            QMessageBox.information(self, "Success", "All data has been cleared.")
    
    def clear_recording(self):
        """Clear the current recording"""
        if self.audio_manager.get_recording_duration() > 0:
            # Ask for confirmation
            reply = QMessageBox.question(
                self,
                "Clear Recording",
                "Are you sure you want to clear the current recording? This cannot be undone.",
                QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Clear recording
                self.audio_manager.clear_recording()
                
                # Reset recording time
                self.recording_time = 0
                self.main_time_display.setText("00:00")
                
                # Reset UI
                self.transcribe_button.setEnabled(False)
                self.transcribe_process_button.setEnabled(False)
                self.clear_button.setEnabled(False)
                
                # Show confirmation
                self.statusBar().showMessage("Recording cleared", 3000)
    
    def set_default_audio_device(self):
        """Set the current audio device as the default"""
        current_device_index = self.device_combo.currentData()
        if current_device_index is not None:
            self.config.set("default_audio_device", str(current_device_index))
            QMessageBox.information(self, "Success", "Default audio device set successfully.")
    
    def show_system_prompts_tab(self):
        """Show the system prompts tab"""
        self.tab_widget.setCurrentIndex(2)
    
    def refresh_settings_audio_devices(self):
        """Refresh the list of audio devices in the settings tab"""
        # Get current device if selected
        current_device = None
        if self.settings_device_combo.currentIndex() >= 0:
            current_device = self.settings_device_combo.currentData()
        
        # Populate devices
        self.populate_settings_audio_devices()
        
        # Try to reselect the previous device
        if current_device is not None:
            for i in range(self.settings_device_combo.count()):
                if self.settings_device_combo.itemData(i) == current_device:
                    self.settings_device_combo.setCurrentIndex(i)
                    break
    
    def populate_settings_audio_devices(self):
        """Populate the list of audio devices in the settings tab"""
        self.settings_device_combo.clear()
        
        devices = self.audio_manager.get_devices()
        for device in devices:
            self.settings_device_combo.addItem(f"{device['name']} ({device['channels']} ch, {device['sample_rate']} Hz)", device['index'])
    
    def save_default_audio_device(self):
        """Save the selected audio device as the default from the settings tab"""
        current_device_index = self.settings_device_combo.currentData()
        if current_device_index is not None:
            self.config.set("default_audio_device", str(current_device_index))
            
            # Save silence removal settings
            scrub_silences = self.scrub_silences_checkbox.isChecked()
            self.config.set("scrub_silences", scrub_silences)
            # Sync with main tab checkbox
            self.main_scrub_silences_checkbox.setChecked(scrub_silences)
            
            # Save silence threshold settings
            try:
                silence_threshold = float(self.silence_threshold_edit.text())
                self.config.set("silence_threshold", silence_threshold)
            except ValueError:
                # Use default if invalid
                self.config.set("silence_threshold", -40)
                self.silence_threshold_edit.setText("-40")
            
            try:
                min_silence_duration = float(self.min_silence_duration_edit.text())
                self.config.set("min_silence_duration", min_silence_duration)
            except ValueError:
                # Use default if invalid
                self.config.set("min_silence_duration", 1.0)
                self.min_silence_duration_edit.setText("1.0")
            
            # Also update the device in the main tab
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == current_device_index:
                    self.device_combo.setCurrentIndex(i)
                    break
            
            QMessageBox.information(self, "Success", "Audio settings saved successfully.")
    
    # Methods for clear and copy buttons
    def clear_transcribed_text(self):
        """Clear the transcribed text"""
        if self.transcribed_text.toPlainText():
            reply = QMessageBox.question(
                self, "Clear Transcribed Text",
                "Are you sure you want to clear the transcribed text?",
                QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.transcribed_text.clear()
                self.clear_transcribed_button.setEnabled(False)
                self.copy_transcribed_button.setEnabled(False)
                self.process_button.setEnabled(False)
                self.statusBar().showMessage("Transcribed text cleared", 3000)
    
    def copy_transcribed_text(self):
        """Copy the transcribed text to clipboard"""
        text = self.transcribed_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.statusBar().showMessage("Transcribed text copied to clipboard", 3000)
    
    def clear_processed_text(self):
        """Clear the processed text"""
        if self.processed_text.toPlainText():
            reply = QMessageBox.question(
                self, "Clear Processed Text",
                "Are you sure you want to clear the processed text?",
                QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.processed_text.clear()
                self.clear_processed_button.setEnabled(False)
                self.copy_processed_button.setEnabled(False)
                self.save_button.setEnabled(False)
                self.statusBar().showMessage("Processed text cleared", 3000)
    
    def copy_processed_text(self):
        """Copy the processed text to clipboard"""
        text = self.processed_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.statusBar().showMessage("Processed text copied to clipboard", 3000)
    
    def update_scrub_silences(self, state):
        """Update scrub silences setting when checkbox state changes in main tab"""
        # Sync the checkbox in settings tab with the one in main tab
        self.scrub_silences_checkbox.setChecked(state == Qt.CheckState.Checked)
        # Save the setting
        self.config.set("scrub_silences", state == Qt.CheckState.Checked)
    
    def save_variables(self):
        """Save variables to configuration"""
        variables = {
            "user_name": self.user_name_input.text().strip(),
            "email_signature": self.email_signature_input.toPlainText().strip()
        }
        
        self.config.set("variables", variables)
        
        # Show confirmation message
        QMessageBox.information(
            self,
            "Variables Saved",
            "Your variables have been saved and will be available in system prompts."
        )
    
    def load_variables(self):
        """Load variables from configuration"""
        variables = self.config.get("variables", {})
        
        # Set values in UI
        self.user_name_input.setText(variables.get("user_name", ""))
        self.email_signature_input.setText(variables.get("email_signature", ""))
    
    def filter_processing_modes(self, text):
        """Filter processing modes based on search text"""
        for i in range(self.mode_list.count()):
            item = self.mode_list.item(i)
            mode_id = item.data(Qt.ItemDataRole.UserRole)
            mode_name = item.text()
            mode_description = self.openai_manager.get_mode_description(mode_id)
            
            # Combine name and description for search
            combined_text = f"{mode_name} {mode_description}".lower()
            
            # Check if search text is in combined text
            if text.lower() in combined_text:
                item.setHidden(False)
            else:
                item.setHidden(True)
    
    def update_mode_selection_count(self):
        """Update the selection count label with the number of selected modes"""
        selected_items = self.mode_list.selectedItems()
        count = len(selected_items)
        
        # Create a more descriptive label
        if count == 0:
            self.selection_count_label.setText("No modes selected")
        elif count == 1:
            mode_name = selected_items[0].text()
            # Only show "Basic Cleanup Only" when that mode is selected
            if mode_name == "Basic Cleanup":
                self.selection_count_label.setText("1 mode selected: Basic Cleanup Only")
            else:
                self.selection_count_label.setText(f"1 mode selected: {mode_name}")
        else:
            # If more than one mode is selected, just show the count
            self.selection_count_label.setText(f"{count} modes selected")
        
        # Enable/disable the process button based on selection count and transcribed text
        has_text = bool(self.transcribed_text.toPlainText().strip())
        self.process_button.setEnabled(count > 0 and has_text)
    
    def show_manage_selections_dialog(self):
        """Show the manage selections dialog to view and deselect processing modes"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Mode Management")
        dialog.setMinimumWidth(650)
        dialog.setMinimumHeight(550)
        
        layout = QVBoxLayout(dialog)
        
        # Add header and description text
        header = QLabel("Processing Modes")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(header)
        
        description = QLabel(
            "Select the processing modes you want to apply to your text. Multiple modes will be applied in sequence. "
            "The basic cleanup mode is recommended and selected by default."
        )
        description.setStyleSheet("font-style: italic; color: #666; margin-bottom: 15px;")
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Add explanatory text about basic cleanup prompt
        basic_cleanup_info = QLabel(
            "Note: The basic cleaning prompt is automatically prepended before any additional prompts, "
            "except for JSON-requiring prompts which are processed separately."
        )
        basic_cleanup_info.setStyleSheet("color: #1565C0; background-color: #E3F2FD; padding: 8px; border-radius: 4px; margin-bottom: 10px;")
        basic_cleanup_info.setWordWrap(True)
        layout.addWidget(basic_cleanup_info)
        
        # Add search box for filtering modes in the dialog
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setFixedWidth(60)
        dialog_search_edit = QLineEdit()
        dialog_search_edit.setPlaceholderText("Search processing modes...")
        search_layout.addWidget(search_label)
        search_layout.addWidget(dialog_search_edit)
        layout.addLayout(search_layout)
        
        # Create list widget with checkboxes
        mode_list = QListWidget()
        mode_list.setAlternatingRowColors(True)
        mode_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:alternate {
                background-color: #f9f9f9;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #000;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
                color: #000;
            }
        """)
        layout.addWidget(mode_list)
        
        # Add selection count label
        self.dialog_selection_count = QLabel("0 prompts selected")
        self.dialog_selection_count.setStyleSheet("font-weight: bold; color: #1565C0; margin-top: 5px;")
        layout.addWidget(self.dialog_selection_count)
        
        # Add a details text area to show mode descriptions
        details_label = QLabel("Mode Description:")
        details_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(details_label)
        
        details_text = QTextEdit()
        details_text.setReadOnly(True)
        details_text.setMaximumHeight(120)
        details_text.setStyleSheet("border: 1px solid #ccc; border-radius: 4px; padding: 5px;")
        details_text.setPlaceholderText("Select a mode to view its description")
        layout.addWidget(details_text)
        
        # Populate the list with modes and set checkboxes based on current selection
        modes = self.openai_manager.get_available_modes()
        for mode in modes:
            # Rename "Basic Cleanup" to "Basic Cleanup Only" in the display
            display_name = "Basic Cleanup Only" if mode["id"] == "basic_cleanup" else mode["name"]
            
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, mode["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            
            # Check if this mode is selected in the main list
            is_selected = False
            for i in range(self.mode_list.count()):
                main_item = self.mode_list.item(i)
                if main_item.isSelected() and main_item.data(Qt.ItemDataRole.UserRole) == mode["id"]:
                    is_selected = True
                    break
            
            # Set tooltip to show description
            tooltip_text = mode.get("description", mode.get("prompt", "")[:100] + "...").replace("\n", " ")
            item.setToolTip(tooltip_text)
            
            item.setCheckState(Qt.CheckState.Checked if is_selected else Qt.CheckState.Unchecked)
            mode_list.addItem(item)
        
        # Add buttons layout
        button_layout = QHBoxLayout()
        
        # Add a button to select only basic cleanup
        basic_cleanup_button = QPushButton("Select Only Basic Cleanup")
        basic_cleanup_button.setStyleSheet("padding: 6px 12px;")
        basic_cleanup_button.clicked.connect(lambda: self.select_only_basic_cleanup(mode_list))
        button_layout.addWidget(basic_cleanup_button)
        
        button_layout.addStretch()
        
        # Add apply and cancel buttons
        apply_button = QPushButton("Apply")
        apply_button.setStyleSheet("padding: 6px 12px; background-color: #2196F3; color: white; font-weight: bold;")
        apply_button.clicked.connect(lambda: self.apply_selection_changes(dialog, mode_list))
        button_layout.addWidget(apply_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("padding: 6px 12px;")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        mode_list.itemClicked.connect(lambda item: self.show_mode_description(item, details_text))
        dialog_search_edit.textChanged.connect(lambda text: self.filter_dialog_modes(text, mode_list))
        
        # Function to update selection count in the dialog
        def update_dialog_selection_count():
            selected_count = sum(1 for i in range(mode_list.count()) 
                               if mode_list.item(i).checkState() == Qt.CheckState.Checked)
            self.dialog_selection_count.setText(f"{selected_count} prompt{'s' if selected_count != 1 else ''} selected")
        
        # Connect item change signal to update count
        mode_list.itemChanged.connect(lambda item: update_dialog_selection_count())
        
        # Initial count update
        update_dialog_selection_count()
        
        # Show the dialog
        dialog.exec()
    
    def select_only_basic_cleanup(self, mode_list):
        """Select only the basic cleanup mode in the list"""
        for i in range(mode_list.count()):
            item = mode_list.item(i)
            mode_id = item.data(Qt.ItemDataRole.UserRole)
            if mode_id == "basic_cleanup":
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
    
    def show_mode_description(self, item, details_text):
        """Show the description of the selected mode"""
        mode_id = item.data(Qt.ItemDataRole.UserRole)
        description = self.openai_manager.get_mode_description(mode_id)
        if description:
            details_text.setText(description)
        else:
            details_text.setText("No description available for this mode.")
    
    def filter_dialog_modes(self, text, mode_list):
        """Filter the modes in the dialog based on search text"""
        for i in range(mode_list.count()):
            item = mode_list.item(i)
            mode_id = item.data(Qt.ItemDataRole.UserRole)
            mode_name = item.text().lower()
            
            # Get description for additional search context
            description = self.openai_manager.get_mode_description(mode_id).lower()
            
            # Show item if search text is in name or description
            if text.lower() in mode_name or text.lower() in description:
                item.setHidden(False)
            else:
                item.setHidden(True)
    
    def select_all_modes(self, mode_list):
        """Select all modes in the list"""
        for i in range(mode_list.count()):
            item = mode_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)
    
    def deselect_all_modes(self, mode_list):
        """Deselect all modes in the list"""
        for i in range(mode_list.count()):
            item = mode_list.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)
    
    def apply_selection_changes(self, dialog, mode_list):
        """Apply the selection changes from the manage selections dialog"""
        # Track changes for status message
        previously_selected = set()
        for i in range(self.mode_list.count()):
            item = self.mode_list.item(i)
            if item.isSelected():
                previously_selected.add(item.data(Qt.ItemDataRole.UserRole))
        
        # Clear all selections in the main list
        self.mode_list.clearSelection()
        
        # Apply the new selections based on checked items in the dialog
        modes_to_select = []
        for i in range(mode_list.count()):
            item = mode_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                mode_id = item.data(Qt.ItemDataRole.UserRole)
                modes_to_select.append(mode_id)
        
        # Select the modes in the main list
        for i in range(self.mode_list.count()):
            item = self.mode_list.item(i)
            mode_id = item.data(Qt.ItemDataRole.UserRole)
            if mode_id in modes_to_select:
                item.setSelected(True)
        
        # Update the selection count
        self.update_mode_selection_count()
        
        # Provide feedback about the changes
        newly_selected = set(modes_to_select)
        added = newly_selected - previously_selected
        removed = previously_selected - newly_selected
        
        if added or removed:
            message_parts = []
            if added:
                message_parts.append(f"Added {len(added)} mode{'s' if len(added) > 1 else ''}")
            if removed:
                message_parts.append(f"Removed {len(removed)} mode{'s' if len(removed) > 1 else ''}")
            
            self.statusBar().showMessage(f"Selection updated: {', '.join(message_parts)}", 3000)
        
        # Close the dialog
        dialog.accept()
    
    def setup_shortcuts(self):
        """Set up keyboard shortcuts for main actions"""
        # Record shortcut (Ctrl+R)
        self.record_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.record_shortcut.activated.connect(self.start_recording)
        
        # Stop shortcut (Ctrl+S)
        self.stop_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.stop_shortcut.activated.connect(self.stop_recording)
        
        # Transcribe shortcut (Ctrl+T)
        self.transcribe_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self.transcribe_shortcut.activated.connect(self.transcribe_audio)
        
        # Process shortcut (Ctrl+P)
        self.process_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.process_shortcut.activated.connect(self.process_text)
        
        # Save shortcut (Ctrl+W) - using W to avoid conflict with Ctrl+S for stop
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        self.save_shortcut.activated.connect(self.save_text)