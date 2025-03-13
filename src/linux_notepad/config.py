#!/usr/bin/env python3
# Linux Whisper Notepad - Configuration Module
# Handles persistent settings storage

import os
import json
from pathlib import Path

class Config:
    """Configuration manager for Linux Whisper Notepad application"""
    
    def __init__(self):
        """Initialize configuration manager"""
        self.config_dir = os.path.join(Path.home(), ".config", "linux-whisper-notepad")
        self.config_file = os.path.join(self.config_dir, "settings.json")
        self.cache_dir = os.path.join(self.config_dir, "cache")
        
        # Default configuration
        self.default_config = {
            "audio_device": "",
            "openai_api_key": "",
            "output_directory": os.path.join(Path.home(), "Documents"),
            "last_used_mode": "basic_cleanup",
            "max_chunk_duration": 120,  # Maximum audio chunk duration in seconds
            "whisper_model": "whisper-1"  # Default Whisper model
        }
        
        # Current configuration
        self.config = self.default_config.copy()
        
        # Ensure config and cache directories exist
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Load existing configuration if available
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Update config with loaded values
                    self.config.update(loaded_config)
        except Exception as e:
            print(f"Error loading configuration: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving configuration: {e}")
    
    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set configuration value and save"""
        self.config[key] = value
        self.save_config()
    
    def get_cache_dir(self):
        """Get the cache directory path"""
        return self.cache_dir
    
    def clear_cache(self):
        """Clear all cached files"""
        try:
            for file in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, file)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False