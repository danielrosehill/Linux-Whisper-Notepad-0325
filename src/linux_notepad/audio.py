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
from pydub import AudioSegment

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
            # Set the paused flag
            self.is_paused = True
            
            # Stop the stream but don't close it
            if self.stream and self.stream.is_active():
                self.stream.stop_stream()
                
            return True
        return False
    
    def resume_recording(self):
        """Resume audio recording"""
        if self.is_recording and self.is_paused:
            # Clear the paused flag
            self.is_paused = False
            
            # Start the stream again if it's stopped
            if self.stream and not self.stream.is_active():
                self.stream.start_stream()
                
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
    
    def save_to_temp_file(self, format="mp3"):
        """
        Save recorded audio to temporary file
        
        Args:
            format (str): Audio format to save as ("mp3" or "wav")
            
        Returns:
            str: Path to the saved temporary file, or None if no audio data
        """
        if not self.frames and not self.temp_files:
            return None
        
        # Default to MP3 unless WAV is specifically requested
        use_mp3 = format.lower() == "mp3"
        file_extension = ".mp3" if use_mp3 else ".wav"
        
        # If we have chunks, combine them
        if self.temp_files:
            # If we have current frames not yet saved to a chunk, save them
            if self.current_chunk_frames:
                self._save_current_chunk()
            
            # Create a combined temporary file
            fd, combined_path = tempfile.mkstemp(suffix='.wav')  # Always combine as WAV first
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
            
            # Check if we need to scrub silences
            if self.config.get("scrub_silences", True):
                processed_path = self._remove_silences(combined_path)
                if processed_path:
                    combined_path = processed_path
                    self.temp_files.append(processed_path)
            
            # Convert to MP3 if requested
            if use_mp3:
                mp3_path = self._convert_to_mp3(combined_path)
                if mp3_path:
                    self.temp_files.append(mp3_path)
                    return mp3_path
            
            return combined_path
        else:
            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='.wav')  # Always save as WAV first
            os.close(fd)
            
            # Save audio data to the temporary file
            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.pyaudio.get_sample_size(self.format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(self.frames))
            
            self.temp_files.append(temp_path)
            
            # Check if we need to scrub silences
            if self.config.get("scrub_silences", True):
                processed_path = self._remove_silences(temp_path)
                if processed_path:
                    temp_path = processed_path
                    self.temp_files.append(processed_path)
            
            # Convert to MP3 if requested
            if use_mp3:
                mp3_path = self._convert_to_mp3(temp_path)
                if mp3_path:
                    self.temp_files.append(mp3_path)
                    return mp3_path
            
            return temp_path
    
    def _convert_to_mp3(self, wav_path, bitrate="128k"):
        """
        Convert WAV file to MP3 format
        
        Args:
            wav_path (str): Path to the WAV file
            bitrate (str): MP3 bitrate (default: "128k")
            
        Returns:
            str: Path to the MP3 file, or None if conversion failed
        """
        try:
            # Create a temporary file for the MP3
            fd, mp3_path = tempfile.mkstemp(suffix='.mp3')
            os.close(fd)
            
            # Use pydub to convert WAV to MP3
            try:
                audio = AudioSegment.from_wav(wav_path)
                audio.export(mp3_path, format="mp3", bitrate=bitrate)
                return mp3_path
            except Exception as e:
                print(f"Error using pydub to convert to MP3: {e}")
                # Fall back to ffmpeg if available
                try:
                    import ffmpeg
                    (
                        ffmpeg
                        .input(wav_path)
                        .output(mp3_path, audio_bitrate=bitrate)
                        .run(quiet=True, overwrite_output=True)
                    )
                    return mp3_path
                except Exception as ffmpeg_error:
                    print(f"Error using ffmpeg to convert to MP3: {ffmpeg_error}")
                    return None
        except Exception as e:
            print(f"Error converting WAV to MP3: {e}")
            return None
    
    def save_to_wav_file(self):
        """Save recorded audio to temporary WAV file (for backward compatibility)"""
        return self.save_to_temp_file(format="wav")
    
    def has_recording(self):
        """Check if there is a recording available"""
        return bool(self.frames) or bool(self.temp_files)
    
    def get_temp_file_path(self):
        """Get the path to the temporary audio file"""
        return self.save_to_temp_file()
    
    def _remove_silences(self, audio_file_path):
        """
        Remove silences from audio file
        
        Args:
            audio_file_path (str): Path to the audio file
            
        Returns:
            str: Path to the processed audio file, or None if processing failed
        """
        try:
            # Get configuration parameters
            silence_threshold = self.config.get("silence_threshold", -40)  # in dB
            min_silence_duration = self.config.get("min_silence_duration", 1.0)  # in seconds
            
            # Read the audio file
            with wave.open(audio_file_path, 'rb') as wf:
                # Get audio parameters
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                
                # Read all frames
                frames = wf.readframes(n_frames)
            
            # Convert to numpy array for processing
            dtype = np.int16
            audio_data = np.frombuffer(frames, dtype=dtype)
            
            # If stereo, convert to mono for silence detection
            if channels == 2:
                # Reshape to separate channels
                audio_data = audio_data.reshape(-1, 2)
                # Average the channels
                mono_data = audio_data.mean(axis=1).astype(dtype)
            else:
                mono_data = audio_data
            
            # Calculate the RMS value (volume) of each chunk
            chunk_samples = int(framerate * 0.1)  # 100ms chunks for analysis
            chunks = [mono_data[i:i+chunk_samples] for i in range(0, len(mono_data), chunk_samples)]
            
            # Calculate RMS for each chunk
            rms_values = []
            for chunk in chunks:
                if len(chunk) > 0:
                    # Calculate RMS (root mean square)
                    rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))
                    # Convert to dB
                    if rms > 0:
                        rms_db = 20 * np.log10(rms / np.iinfo(dtype).max)
                    else:
                        rms_db = -100  # Very quiet
                    rms_values.append(rms_db)
                else:
                    rms_values.append(-100)  # Empty chunk
            
            # Identify silent chunks
            is_silent = [rms <= silence_threshold for rms in rms_values]
            
            # Group consecutive silent chunks
            silent_regions = []
            start_idx = None
            
            for i, silent in enumerate(is_silent):
                if silent and start_idx is None:
                    start_idx = i
                elif not silent and start_idx is not None:
                    # Calculate duration in seconds
                    duration = (i - start_idx) * 0.1  # Each chunk is 0.1s
                    if duration >= min_silence_duration:
                        silent_regions.append((start_idx, i))
                    start_idx = None
            
            # Handle the case where the file ends with silence
            if start_idx is not None:
                duration = (len(is_silent) - start_idx) * 0.1
                if duration >= min_silence_duration:
                    silent_regions.append((start_idx, len(is_silent)))
            
            # If no silent regions to remove, return the original file
            if not silent_regions:
                return None
            
            # Create a new audio file without the silent regions
            fd, processed_path = tempfile.mkstemp(suffix='_processed.wav')
            os.close(fd)
            
            with wave.open(processed_path, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(sample_width)
                wf.setframerate(framerate)
                
                # Write non-silent regions
                last_end = 0
                for start, end in silent_regions:
                    # Convert chunk indices to sample indices
                    start_sample = start * chunk_samples
                    end_sample = min(end * chunk_samples, len(audio_data))
                    
                    # Write data up to the silent region
                    if channels == 2:
                        # For stereo, we need to handle the original shape
                        region_data = audio_data[last_end:start_sample].tobytes()
                    else:
                        region_data = audio_data[last_end:start_sample].tobytes()
                    
                    wf.writeframes(region_data)
                    last_end = end_sample
                
                # Write the remaining data after the last silent region
                if last_end < len(audio_data):
                    if channels == 2:
                        region_data = audio_data[last_end:].tobytes()
                    else:
                        region_data = audio_data[last_end:].tobytes()
                    wf.writeframes(region_data)
            
            return processed_path
            
        except Exception as e:
            print(f"Error removing silences: {e}")
            return None
    
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