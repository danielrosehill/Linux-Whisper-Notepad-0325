#!/usr/bin/env python3
# Linux Whisper Notepad - OpenAI API Module
# Handles integration with OpenAI APIs for speech-to-text and text processing

import os
import json
import time
from datetime import datetime 
import openai
import wave

class OpenAIManager:
    """OpenAI API integration for speech-to-text and text processing"""
    
    # Default text processing modes with their system prompts
    DEFAULT_TEXT_PROCESSING_MODES = {
        "basic_cleanup": {
            "prompt": "Take the following transcript and refine it to add missing punctuation, resolve typos, add paragraph spacing, and generally enhance the presentation of the text while preserving the original meaning.",
            "requires_json": False
        },
        
        "extract_todos": {
            "prompt": "Extract only the to-do items from the following dictated text. Format them as a markdown list with checkboxes. For example: '- [ ] Task description'.",
            "requires_json": True
        },
        
        "shakespearean": {
            "prompt": "Take the following dictated text and return it in Shakespearean English, maintaining the original meaning but using the style, vocabulary, and sentence structure typical of Shakespeare's works.",
            "requires_json": False
        },
        
        "meeting_minutes": {
            "prompt": "Format the following transcript as professional meeting minutes. Identify key discussion points, decisions made, and action items. Use appropriate headings and structure.",
            "requires_json": False
        },
        
        "bullet_summary": {
            "prompt": "Summarize the following transcript as concise bullet points, capturing the main ideas and important details.",
            "requires_json": False
        },
        
        "technical_documentation": {
            "prompt": "Convert the following dictated text into technical documentation format. Use appropriate headings, code blocks for any technical elements, and clear explanations.",
            "requires_json": False
        }
    }
    
    def __init__(self, config):
        """Initialize OpenAI API manager"""
        self.config = config
        self.api_key = self.config.get("openai_api_key", "")
        self.client = None
        
        # Set API key if available
        if self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
            
        # Load custom prompts or use defaults
        self.TEXT_PROCESSING_MODES = self.load_custom_prompts()
    
    def set_api_key(self, api_key):
        """Set OpenAI API key"""
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=self.api_key)
        self.config.set("openai_api_key", api_key) 
    
    def load_custom_prompts(self):
        """Load custom prompts from file or use defaults if file doesn't exist"""
        custom_prompts_file = os.path.join(self.config.config_dir, "custom_prompts.json")
        
        if os.path.exists(custom_prompts_file):
            try:
                with open(custom_prompts_file, 'r') as f:
                    custom_prompts = json.load(f)
                
                # Convert legacy format if needed
                updated_prompts = {}
                for mode_id, data in custom_prompts.items():
                    if isinstance(data, str):
                        # Convert string to new format
                        updated_prompts[mode_id] = {
                            "prompt": data,
                            "requires_json": mode_id == "extract_todos"  # Default assumption
                        }
                    else:
                        # Already in new format
                        updated_prompts[mode_id] = data
                
                return updated_prompts
            except Exception as e:
                print(f"Error loading custom prompts: {e}")
                return self.DEFAULT_TEXT_PROCESSING_MODES.copy()
        else:
            # If file doesn't exist, create it with default prompts
            self.save_custom_prompts(self.DEFAULT_TEXT_PROCESSING_MODES)
            return self.DEFAULT_TEXT_PROCESSING_MODES.copy()
    
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
    
    def transcribe_audio(self, audio_file_path):
        """Transcribe audio using OpenAI Whisper API"""
        if not self.api_key:
            return {"success": False, "error": "OpenAI API key not set", "text": ""}
        
        if not os.path.exists(audio_file_path):
            return {"success": False, "error": f"Audio file not found: {audio_file_path}", "text": ""}
        
        try:
            if not self.client:
                self.client = openai.OpenAI(api_key=self.api_key)
            
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
    
    def process_text(self, text, mode="basic_cleanup"):
        """Process text using OpenAI GPT model with specified mode"""
        if not self.api_key:
            return {"success": False, "error": "OpenAI API key not set", "processed_text": "", "suggested_filename": ""}
        
        if not text:
            return {"success": False, "error": "No text provided for processing", "processed_text": "", "suggested_filename": ""}
        
        # Get mode data
        mode_data = self.TEXT_PROCESSING_MODES.get(mode, self.TEXT_PROCESSING_MODES["basic_cleanup"])
        
        # Handle legacy format
        if isinstance(mode_data, str):
            base_prompt = mode_data
            requires_json = mode == "extract_todos"  # Default assumption
        else:
            base_prompt = mode_data.get("prompt", "")
            requires_json = mode_data.get("requires_json", False)
        
        # For non-JSON modes that aren't basic_cleanup, prepend the basic_cleanup prompt
        if not requires_json and mode != "basic_cleanup":
            basic_cleanup_prompt = self.get_prompt("basic_cleanup")
            system_prompt = f"{basic_cleanup_prompt} {base_prompt}"
        else:
            system_prompt = base_prompt
        
        # Add JSON formatting instruction for JSON modes
        if requires_json:
            system_prompt = f"{system_prompt} Return your response in JSON format."
        
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
                    if mode == "extract_todos":
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
    
    def get_available_modes(self):
        """Get list of available text processing modes sorted alphabetically by name"""
        modes = []
        for mode_id, data in self.TEXT_PROCESSING_MODES.items():
            # Handle both legacy string format and new dict format
            if isinstance(data, str):
                prompt = data
                requires_json = mode_id == "extract_todos"  # Default assumption
            else:
                prompt = data.get("prompt", "")
                requires_json = data.get("requires_json", False)
            
            modes.append({
                "id": mode_id, 
                "name": mode_id.replace("_", " ").title(), 
                "description": prompt[:100] + "...",
                "type": "default" if mode_id in self.DEFAULT_TEXT_PROCESSING_MODES else "user",
                "requires_json": requires_json
            })
        
        # Sort modes alphabetically by name
        return sorted(modes, key=lambda x: x["name"])