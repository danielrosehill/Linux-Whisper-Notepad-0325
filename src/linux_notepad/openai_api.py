#!/usr/bin/env python3
# Linux Whisper Notepad - OpenAI API Module
# Handles integration with OpenAI APIs for speech-to-text and text processing

import os
import json
import time
import sys
from datetime import datetime 
import openai
import wave

class OpenAIManager:
    """OpenAI API integration for speech-to-text and text processing"""
    
    # Default text processing modes are now loaded from a JSON file
    DEFAULT_TEXT_PROCESSING_MODES = {}
    
    def __init__(self, config):
        """Initialize OpenAI API manager"""
        self.config = config
        self.api_key = self.config.get("openai_api_key", "")
        self.client = None
        
        # Set API key if available
        if self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
        
        # Load default prompts from JSON file
        self.load_default_prompts()
            
        # Load custom prompts or use defaults
        self.TEXT_PROCESSING_MODES = self.load_custom_prompts()
    
    def load_default_prompts(self):
        """Load default prompts from the default_prompts.json file"""
        # Path to the default prompts file in the package directory
        # Check if we're running in a PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running as a PyInstaller bundle
            base_path = sys._MEIPASS
            default_prompts_file = os.path.join(base_path, "src", "linux_notepad", "default_prompts.json")
        else:
            # Running in a normal Python environment
            default_prompts_file = os.path.join(os.path.dirname(__file__), "default_prompts.json")
        
        try:
            if os.path.exists(default_prompts_file):
                with open(default_prompts_file, 'r') as f:
                    self.DEFAULT_TEXT_PROCESSING_MODES = json.load(f)
                print(f"Successfully loaded default prompts from: {default_prompts_file}")
            else:
                print(f"Default prompts file not found: {default_prompts_file}")
                # Fallback to minimal defaults if file is missing
                self.DEFAULT_TEXT_PROCESSING_MODES = {
                    "basic_cleanup": {
                        "name": "Basic Cleanup",
                        "prompt": "Take the following transcript and refine it to add missing punctuation, resolve typos, add paragraph spacing, and generally enhance the presentation of the text while preserving the original meaning.",
                        "requires_json": False
                    }
                }
        except Exception as e:
            print(f"Error loading default prompts: {e}")
            # Fallback to minimal defaults if loading fails
            self.DEFAULT_TEXT_PROCESSING_MODES = {
                "basic_cleanup": {
                    "name": "Basic Cleanup",
                    "prompt": "Take the following transcript and refine it to add missing punctuation, resolve typos, add paragraph spacing, and generally enhance the presentation of the text while preserving the original meaning.",
                    "requires_json": False
                }
            }
    
    def load_custom_prompts(self):
        """Load custom prompts from file or use defaults if file doesn't exist"""
        custom_prompts_file = os.path.join(self.config.config_dir, "custom_prompts.json")
        
        # Start with a copy of the default prompts
        prompts = self.DEFAULT_TEXT_PROCESSING_MODES.copy()
        
        if os.path.exists(custom_prompts_file):
            try:
                with open(custom_prompts_file, 'r') as f:
                    custom_prompts = json.load(f)
                
                # Convert legacy format if needed and merge with defaults
                for mode_id, data in custom_prompts.items():
                    if isinstance(data, str):
                        # Convert string to new format
                        prompts[mode_id] = {
                            "name": mode_id.replace("_", " ").title(),
                            "prompt": data,
                            "requires_json": mode_id == "extract_todos"  # Default assumption
                        }
                    else:
                        # Already in new format, ensure it has a name
                        if "name" not in data:
                            data["name"] = mode_id.replace("_", " ").title()
                        prompts[mode_id] = data
                
                return prompts
            except Exception as e:
                print(f"Error loading custom prompts: {e}")
                return prompts
        else:
            # If file doesn't exist, create it with default prompts
            self.save_custom_prompts(prompts)
            return prompts
    
    def save_custom_prompts(self, prompts):
        """Save custom prompts to file"""
        custom_prompts_file = os.path.join(self.config.config_dir, "custom_prompts.json")
        
        try:
            with open(custom_prompts_file, 'w') as f:
                json.dump(prompts, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving custom prompts: {e}")
            return False
    
    def get_prompt(self, mode_id):
        """Get the prompt for a specific mode"""
        mode_data = self.TEXT_PROCESSING_MODES.get(mode_id, {})
        if isinstance(mode_data, str):
            # Handle legacy format (string only)
            return mode_data
        elif isinstance(mode_data, dict):
            # Handle new format (dict with prompt and requires_json)
            return mode_data.get("prompt", "")
        return ""
    
    def requires_json(self, mode_id):
        """Check if a mode requires JSON output"""
        mode_data = self.TEXT_PROCESSING_MODES.get(mode_id, {})
        if isinstance(mode_data, dict):
            return mode_data.get("requires_json", False)
        return False
    
    def add_custom_prompt(self, mode_id, name, prompt, requires_json=False):
        """Add or update a custom prompt"""
        # Ensure mode_id is valid
        mode_id = mode_id.lower().replace(" ", "_")
        
        # Update the prompts dictionary with the new format
        self.TEXT_PROCESSING_MODES[mode_id] = {
            "name": name,
            "prompt": prompt,
            "requires_json": requires_json
        }
        
        # Save to file
        return self.save_custom_prompts(self.TEXT_PROCESSING_MODES)
    
    def delete_custom_prompt(self, mode_id):
        """Delete a prompt (both custom and default)"""
        if mode_id in self.TEXT_PROCESSING_MODES:
            # Delete the prompt
            del self.TEXT_PROCESSING_MODES[mode_id]
            return self.save_custom_prompts(self.TEXT_PROCESSING_MODES)
        return False
    
    def reset_to_defaults(self):
        """Reset all prompts to defaults"""
        self.TEXT_PROCESSING_MODES = self.DEFAULT_TEXT_PROCESSING_MODES.copy()
        return self.save_custom_prompts(self.TEXT_PROCESSING_MODES)
    
    def set_api_key(self, api_key):
        """Set OpenAI API key"""
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=self.api_key)
        self.config.set("openai_api_key", api_key) 
    
    def transcribe_audio(self, audio_file_path, chunk_callback=None):
        """
        Transcribe audio using OpenAI Whisper API
        
        Args:
            audio_file_path (str): Path to the audio file (MP3 or WAV)
            chunk_callback (callable, optional): Callback function for chunk progress updates
                                               Function signature: callback(current_chunk, total_chunks)
        
        Returns:
            dict: Transcription result with success flag, text, and error message
        """
        if not self.api_key:
            return {"success": False, "error": "OpenAI API key not set", "text": ""}
        
        if not os.path.exists(audio_file_path):
            return {"success": False, "error": f"Audio file not found: {audio_file_path}", "text": ""}
        
        try:
            if not self.client:
                self.client = openai.OpenAI(api_key=self.api_key)
            
            # Check file size
            file_size = os.path.getsize(audio_file_path)
            max_size = 24 * 1024 * 1024  # 24MB (leaving some margin below the 25MB limit)
            
            # MP3 files are already compressed, so we likely don't need chunking
            # But keep the chunking logic for very large MP3 files or WAV files
            if file_size > max_size:
                # File is too large, use chunking approach
                return self._transcribe_large_audio(audio_file_path, chunk_callback)
            else:
                # File is within size limits, transcribe normally
                with open(audio_file_path, "rb") as audio_file:
                    transcription = self.client.audio.transcriptions.create(
                        model=self.config.get("whisper_model", "whisper-1"),
                        file=audio_file
                    )
                
                return {
                    "success": True,
                    "text": transcription.text,
                    "error": ""
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }
    
    def _transcribe_large_audio(self, audio_file_path, chunk_callback=None):
        """
        Transcribe large audio files by splitting into chunks and transcribing each chunk.
        
        Args:
            audio_file_path (str): Path to the audio file
            chunk_callback (callable, optional): Callback function for chunk progress updates
                                               Function signature: callback(current_chunk, total_chunks)
            
        Returns:
            dict: Transcription result with success flag, text, and error message
        """
        try:
            # Split the audio file into chunks
            chunk_paths = self._split_audio_file(audio_file_path)
            
            if not chunk_paths:
                return {
                    "success": False,
                    "error": "Failed to split audio file into chunks",
                    "text": ""
                }
            
            # Transcribe each chunk
            transcriptions = []
            total_chunks = len(chunk_paths)
            
            for i, chunk_path in enumerate(chunk_paths):
                # Report progress if callback is provided
                if chunk_callback:
                    chunk_callback(i + 1, total_chunks)
                
                try:
                    with open(chunk_path, "rb") as audio_file:
                        transcription = self.client.audio.transcriptions.create(
                            model=self.config.get("whisper_model", "whisper-1"),
                            file=audio_file
                        )
                    transcriptions.append(transcription.text)
                except Exception as e:
                    # Log error but continue with other chunks
                    print(f"Error transcribing chunk {i+1}: {e}")
            
            # Clean up temporary chunk files
            for chunk_path in chunk_paths:
                try:
                    if os.path.exists(chunk_path):
                        os.unlink(chunk_path)
                except Exception as e:
                    print(f"Error removing temporary chunk file {chunk_path}: {e}")
            
            # Combine transcriptions
            if transcriptions:
                combined_text = " ".join(transcriptions)
                return {
                    "success": True,
                    "text": combined_text,
                    "error": ""
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to transcribe any audio chunks",
                    "text": ""
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error in chunked transcription: {str(e)}",
                "text": ""
            }
    
    def _get_audio_duration(self, audio_file_path):
        """Get the duration of an audio file in seconds"""
        with wave.open(audio_file_path, 'rb') as wf:
            # Duration = frames / framerate
            return wf.getnframes() / wf.getframerate()
    
    def _transcribe_single_file(self, audio_file_path):
        """Transcribe a single audio file"""
        if not self.client:
            self.client = openai.OpenAI(api_key=self.api_key)
        
        with open(audio_file_path, "rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model=self.config.get("whisper_model", "whisper-1"),
                file=audio_file
            ) 
        
        return {
            "success": True,
            "text": response.text,
            "error": ""
        }
    
    def _transcribe_chunked_file(self, audio_file_path):
        """Transcribe an audio file by splitting it into chunks"""
        # This is a simplified implementation - in a real app, you might want to
        # split the audio more intelligently (e.g., at silence points)
        
        # Get audio info
        with wave.open(audio_file_path, 'rb') as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            
            # Calculate chunk size (20 minutes per chunk)
            chunk_duration = 20 * 60  # 20 minutes in seconds
            chunk_frames = int(chunk_duration * framerate)
            
            # Create temp directory for chunks
            cache_dir = self.config.get_cache_dir()
            
            # Read and process in chunks
            transcriptions = []
            
            for i in range(0, n_frames, chunk_frames):
                # Read chunk
                wf.setpos(i)
                chunk_data = wf.readframes(min(chunk_frames, n_frames - i))
                
                # Save chunk to temp file
                chunk_path = os.path.join(cache_dir, f"transcribe_chunk_{i}.wav")
                with wave.open(chunk_path, 'wb') as chunk_wf:
                    chunk_wf.setnchannels(channels)
                    chunk_wf.setsampwidth(sample_width)
                    chunk_wf.setframerate(framerate)
                    chunk_wf.writeframes(chunk_data)
                
                # Transcribe chunk
                try:
                    result = self._transcribe_single_file(chunk_path)
                    if result["success"]:
                        transcriptions.append(result["text"])
                    else:
                        return result  # Return error
                    
                    # Clean up chunk file
                    os.unlink(chunk_path)
                    
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error transcribing chunk {i//chunk_frames + 1}: {str(e)}",
                        "text": ""
                    }
        
        # Combine transcriptions
        full_text = " ".join(transcriptions)
        
        # Clean up combined text
        if not self.client:
            self.client = openai.OpenAI(api_key=self.api_key)
            
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that cleans up and combines transcription chunks. Fix any issues at chunk boundaries and ensure the text flows naturally."},
                {"role": "user", "content": full_text}
            ]
        )
        
        cleaned_text = response.choices[0].message.content if response.choices else full_text
        
        return {
            "success": True,
            "text": cleaned_text,
            "error": ""
        }
    
    def _split_audio_file(self, audio_file_path, max_chunk_size_mb=20):
        """
        Split an audio file into smaller chunks.
        
        Args:
            audio_file_path (str): Path to the audio file
            max_chunk_size_mb (int): Maximum size of each chunk in MB
            
        Returns:
            list: List of paths to the chunk files
        """
        try:
            import wave
            import numpy as np
            from pydub import AudioSegment
            
            # Load the audio file
            audio = AudioSegment.from_wav(audio_file_path)
            
            # Calculate chunk duration based on file size and audio properties
            file_size = os.path.getsize(audio_file_path)
            total_duration_ms = len(audio)
            
            # Calculate how many chunks we need
            num_chunks = max(1, int(file_size / (max_chunk_size_mb * 1024 * 1024)) + 1)
            
            # Calculate chunk duration in milliseconds
            chunk_duration_ms = total_duration_ms // num_chunks
            
            # Create chunks
            chunk_paths = []
            for i in range(num_chunks):
                start_ms = i * chunk_duration_ms
                end_ms = min((i + 1) * chunk_duration_ms, total_duration_ms)
                
                # Extract chunk
                chunk = audio[start_ms:end_ms]
                
                # Save chunk to temporary file
                chunk_path = f"{audio_file_path}_chunk_{i}.wav"
                chunk.export(chunk_path, format="wav")
                chunk_paths.append(chunk_path)
            
            return chunk_paths
        except ImportError:
            # If pydub is not available, fall back to a simpler method using wave
            try:
                import wave
                import numpy as np
                
                with wave.open(audio_file_path, 'rb') as wf:
                    # Get audio parameters
                    channels = wf.getnchannels()
                    sample_width = wf.getsampwidth()
                    framerate = wf.getframerate()
                    n_frames = wf.getnframes()
                    
                    # Calculate bytes per second
                    bytes_per_second = framerate * channels * sample_width
                    
                    # Calculate chunk duration in seconds based on max size
                    max_chunk_size_bytes = max_chunk_size_mb * 1024 * 1024
                    chunk_duration_seconds = max(1, int(max_chunk_size_bytes / bytes_per_second))
                    
                    # Calculate frames per chunk
                    frames_per_chunk = chunk_duration_seconds * framerate
                    
                    # Calculate number of chunks
                    num_chunks = (n_frames + frames_per_chunk - 1) // frames_per_chunk
                    
                    chunk_paths = []
                    for i in range(num_chunks):
                        # Create a new WAV file for this chunk
                        chunk_path = f"{audio_file_path}_chunk_{i}.wav"
                        with wave.open(chunk_path, 'wb') as chunk_wf:
                            chunk_wf.setnchannels(channels)
                            chunk_wf.setsampwidth(sample_width)
                            chunk_wf.setframerate(framerate)
                            
                            # Read and write frames for this chunk
                            start_frame = i * frames_per_chunk
                            wf.setpos(start_frame)
                            frames_to_read = min(frames_per_chunk, n_frames - start_frame)
                            chunk_wf.writeframes(wf.readframes(frames_to_read))
                        
                        chunk_paths.append(chunk_path)
                
                return chunk_paths
            except Exception as e:
                print(f"Error splitting audio file: {e}")
                return []
        except Exception as e:
            print(f"Error splitting audio file: {e}")
            return []
    
    def replace_variables_in_prompt(self, prompt):
        """Replace variable placeholders in a prompt with their values"""
        variables = self.config.get("variables", {})
        
        # Define variable placeholders and their corresponding config keys
        variable_map = {
            "{user_name}": "user_name",
            "{email_signature}": "email_signature"
        }
        
        # Replace each variable placeholder with its value
        for placeholder, var_key in variable_map.items():
            value = variables.get(var_key, "")
            if value:  # Only replace if the variable has a value
                prompt = prompt.replace(placeholder, value)
                
        return prompt
    
    def process_text(self, text, mode_id):
        """Process text using OpenAI GPT API with the specified mode"""
        if not self.api_key:
            return {"success": False, "error": "OpenAI API key not set", "processed_text": "", "suggested_filename": ""}
        
        if not text:
            return {"success": False, "error": "No text provided for processing", "processed_text": "", "suggested_filename": ""}
        
        # Get mode data
        mode_data = self.TEXT_PROCESSING_MODES.get(mode_id, self.TEXT_PROCESSING_MODES["basic_cleanup"])
        
        # Handle legacy format
        if isinstance(mode_data, str):
            base_prompt = mode_data
            requires_json = mode_id == "extract_todos"  # Default assumption
        else:
            base_prompt = mode_data.get("prompt", "")
            requires_json = mode_data.get("requires_json", False)
        
        # For non-JSON modes, prepend the basic_cleanup prompt
        # This applies to all non-JSON prompts, not just those that aren't basic_cleanup
        if not requires_json:
            basic_cleanup_prompt = self.get_prompt("basic_cleanup")
            system_prompt = f"{basic_cleanup_prompt} {base_prompt}"
        else:
            system_prompt = base_prompt
        
        # Add JSON formatting instruction for JSON modes
        if requires_json:
            system_prompt = f"{system_prompt} Return your response in JSON format."
        
        # Replace variables in the prompt
        system_prompt = self.replace_variables_in_prompt(system_prompt)
        
        try:
            if not self.client:
                self.client = openai.OpenAI(api_key=self.api_key)
            
            # Configure response format based on requires_json flag
            response_format = {"type": "json_object"} if requires_json else None
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                response_format=response_format
            ) 
            
            # Handle response based on format
            response_content = response.choices[0].message.content if response.choices else ""
            
            if requires_json:
                # Parse the JSON response
                try:
                    response_json = json.loads(response_content)
                    if mode_id == "extract_todos":
                        processed_text = response_json.get("todos", response_content)
                    else:
                        processed_text = response_json.get("processed_text", response_content)
                except json.JSONDecodeError:
                    # Fallback if JSON parsing fails
                    processed_text = response_content
            else:
                # For non-JSON responses, use the content directly
                processed_text = response_content
            
            # Generate a suggested filename using JSON mode
            filename_response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Generate a short, descriptive filename (without extension) based on the content of the following text. Use lowercase with hyphens between words. Keep it under 40 characters. Return the result in JSON format: {\"filename\": \"<your-filename-here>\"}"},
                    {"role": "user", "content": processed_text[:1000]}  # Use first 1000 chars for filename generation
                ],
                response_format={"type": "json_object"}
            ) 
            
            # Parse the JSON response for filename
            try:
                filename_content = filename_response.choices[0].message.content if filename_response.choices else "{}"
                filename_json = json.loads(filename_content)
                suggested_filename = filename_json.get("filename", "")
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                suggested_filename = filename_response.choices[0].message.content.strip() if filename_response.choices else ""
            
            # Ensure filename is valid
            suggested_filename = suggested_filename.replace(" ", "-").lower()
            suggested_filename = ''.join(c for c in suggested_filename if c.isalnum() or c in '-_')
            
            # Add date prefix to filename
            date_prefix = datetime.now().strftime("%Y-%m-%d")
            suggested_filename = f"{date_prefix}-{suggested_filename}"
            
            return {
                "success": True,
                "processed_text": processed_text,
                "suggested_filename": suggested_filename
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "processed_text": "",
                "suggested_filename": ""
            }
    
    def process_text_with_multiple_modes(self, text, mode_ids):
        """Process text using OpenAI GPT API with multiple modes
        
        This method applies multiple processing modes to the text in sequence,
        ensuring the basic_cleanup prompt is only applied once.
        
        Args:
            text (str): The text to process
            mode_ids (list): List of mode IDs to apply
            
        Returns:
            dict: Result containing processed text and suggested filename
        """
        if not self.api_key:
            return {"success": False, "error": "OpenAI API key not set", "processed_text": "", "suggested_filename": ""}
        
        if not text:
            return {"success": False, "error": "No text provided for processing", "processed_text": "", "suggested_filename": ""}
        
        if not mode_ids:
            return {"success": False, "error": "No processing modes provided", "processed_text": "", "suggested_filename": ""}
        
        # If only one mode, use the regular process_text method
        if len(mode_ids) == 1:
            return self.process_text(text, mode_ids[0])
        
        # Check if basic_cleanup is in the list of modes
        has_basic_cleanup = "basic_cleanup" in mode_ids
        
        # Create a combined prompt with all selected modes
        system_prompts = []
        requires_json = False
        
        # First, add the basic_cleanup prompt if any non-JSON mode is selected
        # This ensures it's only added once
        basic_cleanup_prompt = self.get_prompt("basic_cleanup")
        basic_cleanup_added = False
        
        # Check if any mode requires JSON output
        for mode_id in mode_ids:
            if self.requires_json(mode_id):
                requires_json = True
                break
        
        # If any mode requires JSON, we can't combine them with non-JSON modes
        if requires_json:
            # For now, just use the first mode that requires JSON
            for mode_id in mode_ids:
                if self.requires_json(mode_id):
                    return self.process_text(text, mode_id)
        
        # Process each mode and build the combined prompt
        for mode_id in mode_ids:
            # Skip JSON modes as they can't be combined
            if self.requires_json(mode_id):
                continue
                
            # Get the prompt for this mode
            mode_data = self.TEXT_PROCESSING_MODES.get(mode_id, {})
            
            # Handle legacy format
            if isinstance(mode_data, str):
                base_prompt = mode_data
            else:
                base_prompt = mode_data.get("prompt", "")
            
            # If this is the basic_cleanup mode, skip adding it separately
            # as we'll add it at the beginning of the combined prompt
            if mode_id == "basic_cleanup":
                continue
                
            # Add the prompt to our list
            system_prompts.append(base_prompt)
        
        # Build the final system prompt
        if system_prompts:
            # Add basic_cleanup at the beginning if it's not already in the list
            # or if it is in the list but we haven't added it yet
            if not basic_cleanup_added:
                combined_prompt = basic_cleanup_prompt + " Additionally, " + " Then, ".join(system_prompts)
            else:
                combined_prompt = " Then, ".join(system_prompts)
        else:
            # If no other prompts, just use basic_cleanup
            combined_prompt = basic_cleanup_prompt
        
        # Replace variables in the prompt
        combined_prompt = self.replace_variables_in_prompt(combined_prompt)
        
        try:
            if not self.client:
                self.client = openai.OpenAI(api_key=self.api_key)
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": combined_prompt},
                    {"role": "user", "content": text}
                ]
            ) 
            
            # Get the processed text from the response
            processed_text = response.choices[0].message.content if response.choices else ""
            
            # Generate a suggested filename using JSON mode
            filename_response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Generate a short, descriptive filename (without extension) based on the content of the following text. Use lowercase with hyphens between words. Keep it under 40 characters. Return the result in JSON format: {\"filename\": \"<your-filename-here>\"}"},
                    {"role": "user", "content": processed_text[:1000]}  # Use first 1000 chars for filename generation
                ],
                response_format={"type": "json_object"}
            ) 
            
            # Parse the JSON response for filename
            try:
                filename_content = filename_response.choices[0].message.content if filename_response.choices else "{}"
                filename_json = json.loads(filename_content)
                suggested_filename = filename_json.get("filename", "")
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                suggested_filename = filename_response.choices[0].message.content.strip() if filename_response.choices else ""
            
            # Ensure filename is valid
            suggested_filename = suggested_filename.replace(" ", "-").lower()
            suggested_filename = ''.join(c for c in suggested_filename if c.isalnum() or c in '-_')
            
            # Add date prefix to filename
            date_prefix = datetime.now().strftime("%Y-%m-%d")
            suggested_filename = f"{date_prefix}-{suggested_filename}"
            
            return {
                "success": True,
                "processed_text": processed_text,
                "suggested_filename": suggested_filename
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "processed_text": "",
                "suggested_filename": ""
            }
    
    def get_available_modes(self):
        """Get list of available text processing modes"""
        modes = []
        for mode_id, data in self.TEXT_PROCESSING_MODES.items():
            if isinstance(data, str):
                # Legacy format
                modes.append({
                    "id": mode_id,
                    "name": mode_id.replace("_", " ").title(),
                    "prompt": data
                })
            else:
                # New format
                modes.append({
                    "id": mode_id,
                    "name": data.get("name", mode_id.replace("_", " ").title()),
                    "prompt": data.get("prompt", ""),
                    "requires_json": data.get("requires_json", False),
                    "description": data.get("description", "")
                })
        
        # Sort modes: basic_cleanup first, then alphabetically by name
        return sorted(modes, key=lambda x: (0 if x["id"] == "basic_cleanup" else 1, x["name"]))
    
    def get_mode_description(self, mode_id):
        """Get the description for a specific mode"""
        mode_data = self.TEXT_PROCESSING_MODES.get(mode_id, {})
        if isinstance(mode_data, dict):
            # Return description if available, otherwise return the first part of the prompt
            description = mode_data.get("description", "")
            if description:
                return description
            
            # If no description, return the first 100 characters of the prompt
            prompt = mode_data.get("prompt", "")
            if prompt:
                return prompt[:100] + "..." if len(prompt) > 100 else prompt
        
        # For legacy string format or if no description/prompt found
        return ""