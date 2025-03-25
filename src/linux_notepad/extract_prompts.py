#!/usr/bin/env python3
"""
Script to extract prompts from markdown files and add them to default_prompts.json
"""

import os
import json
import re

# Paths
starter_prompts_dir = "../../starter-prompts"
default_prompts_file = "default_prompts.json"

# Load existing default prompts
with open(default_prompts_file, 'r') as f:
    default_prompts = json.load(f)

# Function to extract prompt from markdown file
def extract_prompt_from_md(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract title (first line after # )
    title_match = re.search(r'# (.*?)(\n|$)', content)
    title = title_match.group(1).strip() if title_match else os.path.basename(file_path).replace('.md', '').replace('-', ' ').title()
    
    # Extract prompt (content between triple backticks)
    prompt_match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
    prompt = prompt_match.group(1).strip() if prompt_match else ""
    
    # If no prompt found, return None
    if not prompt:
        return None
    
    # Generate ID from filename
    prompt_id = os.path.basename(file_path).replace('.md', '').lower()
    
    return {
        "id": prompt_id,
        "name": title,
        "prompt": prompt,
        "requires_json": "json" in prompt.lower() or "JSON" in prompt
    }

# Process all markdown files in the starter prompts directory
new_prompts = {}
for filename in os.listdir(starter_prompts_dir):
    if filename.endswith('.md'):
        file_path = os.path.join(starter_prompts_dir, filename)
        prompt_data = extract_prompt_from_md(file_path)
        
        if prompt_data:
            prompt_id = prompt_data["id"]
            new_prompts[prompt_id] = {
                "name": prompt_data["name"],
                "prompt": prompt_data["prompt"],
                "requires_json": prompt_data["requires_json"]
            }
            print(f"Extracted prompt: {prompt_data['name']}")

# Merge with existing prompts
for prompt_id, prompt_data in new_prompts.items():
    if prompt_id not in default_prompts:
        default_prompts[prompt_id] = prompt_data
        print(f"Added new prompt: {prompt_data['name']}")

# Save updated prompts
with open(default_prompts_file, 'w') as f:
    json.dump(default_prompts, f, indent=4)

print(f"Updated {default_prompts_file} with {len(new_prompts)} new prompts")
