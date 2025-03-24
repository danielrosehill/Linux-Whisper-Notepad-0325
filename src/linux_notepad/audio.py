#!/usr/bin/env python3
# Linux Whisper Notepad - Audio Module
# Handles audio recording and device management

import os
import time
import wave
import tempfile
import numpy as np
import pyaudio
from datetime import datetime

class AudioManager:
    """Audio recording and device management"""
    
    def __init__(self, config):
        """Initialize audio manager"""
        self.config = config
        self.pyaudio = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        self.is_paused = False
        self.frames = []
        self.temp_files = []  # List to track all temporary files
        self.sample_rate = None  # Will be set based on device
        self.channels = 1
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        self.recording_start_time = None
        self.current_chunk_frames = []
        self.current_chunk_duration = 0
        
    def __del__(self):
        """Clean up resources"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.pyaudio.terminate()
        self._cleanup_temp_files()
        
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                print(f"Error removing temporary file {temp_file}: {e}")
        
    def get_devices(self):
        """Get list of available audio input devices"""
        devices = []
        for i in range(self.pyaudio.get_device_count()):
            device_info = self.pyaudio.get_device_info_by_index(i)
            # Only include input devices
            if device_info['maxInputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': device_info['name'],
                    'channels': device_info['maxInputChannels'],
                    'sample_rate': int(device_info['defaultSampleRate'])
                })
        return devices
    
    def get_default_device(self):
        """Get default audio input device"""
        # First check if we have a configured default device
        device_index_str = self.config.get('default_audio_device')
        if device_index_str and device_index_str.isdigit():
            device_index = int(device_index_str)
            try:
                device_info = self.pyaudio.get_device_info_by_index(device_index)
                # Make sure it's an input device
                if device_info['maxInputChannels'] > 0:
                    return {
                        'index': device_index,
                        'name': device_info['name'],
                        'channels': device_info['maxInputChannels'],
                        'sample_rate': int(device_info['defaultSampleRate'])
                    }
            except:
                # If the saved device is no longer available, fall back to system default
                pass
                
        # Fall back to system default device
        try:
            default_device = self.pyaudio.get_default_input_device_info()
            return {
                'index': default_device['index'],
                'name': default_device['name'],
                'channels': default_device['maxInputChannels'],
                'sample_rate': int(default_device['defaultSampleRate'])
            }
        except:
            # If no default device is found, return the first available input device
            devices = self.get_devices()
            if devices:
                return devices[0]
            return None
    
    def start_recording(self, device_index=None):
        """Start audio recording"""
        if self.is_recording and not self.is_paused:
            return False
        
        # If no device index is provided, use the one from config
        if device_index is None:
            device_index_str = self.config.get('default_audio_device')
            if device_index_str and device_index_str.isdigit():
                device_index = int(device_index_str)
            else:
                # Use default device if not configured
                default_device = self.get_default_device()
                if default_device:
                    device_index = default_device['index']
                else:
                    return False
        
        # Get device info to use its native sample rate
        try:
            device_info = self.pyaudio.get_device_info_by_index(device_index)
            self.sample_rate = int(device_info['defaultSampleRate'])
            self.channels = min(2, max(1, int(device_info['maxInputChannels'])))  # Use at least mono, at most stereo
        except Exception as e:
            print(f"Error getting device info: {e}")
            # Fallback to safe defaults
            self.sample_rate = 16000  # Lower sample rate that works on most devices
            self.channels = 1
        
        # Reset recording state
        if not self.is_paused:
            self.frames = []
            self.current_chunk_frames = []
            self.current_chunk_duration = 0
            self.recording_start_time = time.time()
        
        # Create a new stream if needed
        if not self.stream or self.stream.is_stopped():
            self.stream = self.pyaudio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
        
        # Start the stream
        self.stream.start_stream()
        self.is_recording = True
        self.is_paused = False
        return True
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio data"""
        if not self.is_paused:
            self.frames.append(in_data)
            self.current_chunk_frames.append(in_data)
            
            # Calculate current chunk duration
            bytes_per_sample = self.pyaudio.get_sample_size(self.format)
            samples = len(in_data) / (bytes_per_sample * self.channels)
            duration = samples / self.sample_rate
            self.current_chunk_duration += duration
            
            # Check if we need to save the current chunk
            max_chunk_duration = self.config.get("max_chunk_duration", 120)  # Default to 2 minutes
            if self.current_chunk_duration >= max_chunk_duration:
                self._save_current_chunk()
        
        return (in_data, pyaudio.paContinue)
    
    def _save_current_chunk(self):
        """Save current chunk to a temporary file"""
        if not self.current_chunk_frames:
            return
            
        # Create a temporary file in the cache directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cache_dir = self.config.get_cache_dir()
        temp_path = os.path.join(cache_dir, f"chunk_{timestamp}.wav")
        
        # Save audio data to the temporary file
        with wave.open(temp_path, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.pyaudio.get_sample_size(self.format))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(self.current_chunk_frames))
        
        # Add to temp files list
        self.temp_files.append(temp_path)
        
        # Reset current chunk
        self.current_chunk_frames = []
        self.current_chunk_duration = 0
    
    def pause_recording(self):
        """Pause audio recording"""
        if self.is_recording and not self.is_paused:
            self.is_paused = True
            return True
        return False
    
    def resume_recording(self):
        """Resume audio recording"""
        if self.is_recording and self.is_paused:
            self.is_paused = False
            return True
        return False
    
    def stop_recording(self):
        """Stop audio recording"""
        if not self.is_recording:
            return False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        # Save the final chunk
        if self.current_chunk_frames:
            self._save_current_chunk()
        
        self.is_recording = False
        self.is_paused = False
        return True
    
    def clear_recording(self):
        """Clear recorded audio data"""
        # Make sure to stop any active stream before clearing
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            
        self.is_recording = False
        self.is_paused = False
        self.frames = []
        self.current_chunk_frames = []
        self.current_chunk_duration = 0
        self._cleanup_temp_files()
        self.temp_files = []
        return True
    
    def save_to_temp_file(self):
        """Save recorded audio to temporary file"""
        if not self.frames and not self.temp_files:
            return None
        
        # If we have chunks, combine them
        if self.temp_files:
            # If we have current frames not yet saved to a chunk, save them
            if self.current_chunk_frames:
                self._save_current_chunk()
            
            # Create a combined temporary file
            fd, combined_path = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            
            # Combine all chunks into one file
            with wave.open(combined_path, 'wb') as out_wf:
                # Set parameters based on first chunk
                with wave.open(self.temp_files[0], 'rb') as first_wf:
                    out_wf.setnchannels(first_wf.getnchannels())
                    out_wf.setsampwidth(first_wf.getsampwidth())
                    out_wf.setframerate(first_wf.getframerate())
                
                # Write all chunks to the combined file
                for chunk_path in self.temp_files:
                    with wave.open(chunk_path, 'rb') as wf:
                        out_wf.writeframes(wf.readframes(wf.getnframes()))
            
            # Add to temp files list
            self.temp_files.append(combined_path)
            return combined_path
        else:
            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            
            # Save audio data to the temporary file
            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.pyaudio.get_sample_size(self.format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(self.frames))
            
            self.temp_files.append(temp_path)
            return temp_path
    
    def get_recording_duration(self):
        """Get duration of recorded audio in seconds"""
        if not self.frames and not self.temp_files:
            return 0
        
        total_duration = 0
        
        # Calculate duration from frames
        if self.frames:
            frame_count = sum(len(frame) for frame in self.frames) / (2 * self.channels)  # 2 bytes per sample
            total_duration += frame_count / self.sample_rate
        
        # Add duration from saved chunks
        for chunk_path in self.temp_files:
            try:
                with wave.open(chunk_path, 'rb') as wf:
                    chunk_duration = wf.getnframes() / wf.getframerate()
                    total_duration += chunk_duration
            except Exception as e:
                print(f"Error calculating duration for {chunk_path}: {e}")
        
        return total_duration
    
    def has_recording(self):
        """Check if there is a recording available"""
        return bool(self.frames) or bool(self.temp_files)