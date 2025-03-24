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
        "basic_cleanup": "Take the following transcript and refine it to add missing punctuation, resolve typos, add paragraph spacing, and generally enhance the presentation of the text while preserving the original meaning.",
        
        "extract_todos": "Extract only the to-do items from the following dictated text. Format them as a markdown list with checkboxes. For example: '- [ ] Task description'.",
        
        "shakespearean": "Take the following dictated text and return it in Shakespearean English, maintaining the original meaning but using the style, vocabulary, and sentence structure typical of Shakespeare's works.",
        
        "meeting_minutes": "Format the following transcript as professional meeting minutes. Identify key discussion points, decisions made, and action items. Use appropriate headings and structure.",
        
        "bullet_summary": "Summarize the following transcript as concise bullet points, capturing the main ideas and important details.",
        
        "technical_documentation": "Convert the following dictated text into technical documentation format. Use appropriate headings, code blocks for any technical elements, and clear explanations."
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
                return custom_prompts
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
        return self.TEXT_PROCESSING_MODES.get(mode_id, "")
    
    def add_custom_prompt(self, mode_id, name, prompt):
        """Add or update a custom prompt"""
        # Ensure mode_id is valid
        mode_id = mode_id.lower().replace(" ", "_")
        
        # Update the prompts dictionary
        self.TEXT_PROCESSING_MODES[mode_id] = prompt
        
        # Save to file
        return self.save_custom_prompts(self.TEXT_PROCESSING_MODES)
    
    def delete_custom_prompt(self, mode_id):
        """Delete a custom prompt"""
        if mode_id in self.TEXT_PROCESSING_MODES:
            # Don't delete default prompts
            if mode_id in self.DEFAULT_TEXT_PROCESSING_MODES:
                return False
                
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
        
        # Get system prompt for the selected mode
        base_prompt = self.TEXT_PROCESSING_MODES.get(
            mode, 
            self.TEXT_PROCESSING_MODES["basic_cleanup"]
        )
        
        # Create a JSON-focused system prompt
        system_prompt = f"{base_prompt} Return ONLY the processed text in a JSON response with the format: {{\"processed_text\": \"<your processed text here>\"}}"
        
        try:
            if not self.client:
                self.client = openai.OpenAI(api_key=self.api_key)
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"}
            ) 
            
            # Parse the JSON response
            try:
                response_content = response.choices[0].message.content if response.choices else "{}"
                response_json = json.loads(response_content)
                processed_text = response_json.get("processed_text", "")
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
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
        """Get list of available text processing modes sorted alphabetically by name"""
        modes = [
            {"id": mode_id, "name": mode_id.replace("_", " ").title(), "description": prompt[:100] + "..."}
            for mode_id, prompt in self.TEXT_PROCESSING_MODES.items()
        ]
        
        # Sort modes alphabetically by name
        return sorted(modes, key=lambda x: x["name"])