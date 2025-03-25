# AI Speech To Text Notepad For Linux (OpenAI Whisper API)
 
 ![alt text](screenshots/v2/1.png)


This repository contains a Python-based speech-to-text/dictation capturing utility specifically designed for Linux systems. 

The tool is equipped with a graphical user interface (GUI) and seamlessly amalgamates two AI-assisted workflows. 

The primary goal of this tool is to convert speech-captured text into formats ready for diverse purposes.

## Installation

To install this utility on your Linux system, follow these steps:

1. Clone the repository to your local machine.
```bash
git clone https://github.com/example-repo.git
```

2. Install the necessary dependencies.
```bash
pip install -r requirements.txt
```

3. Run the utility.
```bash
python speech_to_text.py
```

## Features

- The utility initiates audio capture for transcription.
- Users can interrupt the process at any time.
- Implements a basic cleanup prompt to fix typos and formatting without altering the content.
- Offers the option to apply multiple individual prompts for nuanced output.
- Allows manual editing of the transcribed text.
- Supports customization by adding user-specific prompts.
- Integration of OpenAI API key in the settings menu.
- Enables the editing of system prompt library.
- Facilitates the addition of variables to link recurring information with specific system prompts.

## Usage Example

Here's how you can use this utility:

1. Input speech for transcription.
2. Apply basic cleanup prompt.
3. Optionally add additional prompts for tailored formatting.
4. Edit the transcript manually if needed.
5. Save and download the processed text.
 
 
## Requirements

- Python 3.8 or higher
- PyQt6 for the GUI
- PyAudio for audio recording
- OpenAI API key

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/Linux-Whisper-Notepad-0325.git
   cd Linux-Whisper-Notepad-0325
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python linux_whisper_notepad.py
   ```
   
   Or use the provided script:
   ```bash
   ./run.sh
   ```

## Usage

1. **Audio Recording**:
   - Select your audio input device
   - Use the recording controls to start, pause, and stop recording
   - The recording time is displayed

2. **Transcription**:
   - After recording, click "Transcribe Audio" to convert speech to text
   - Alternatively, use "Transcribe and Process" to perform both steps at once
   - Requires an OpenAI API key (set in Settings tab)
   - Use the "Copy to Clipboard" button to copy the transcribed text

3. **Text Processing**:
   - Select a processing mode from the dropdown
   - Click "Process Text" to refine the transcribed text
   - The processed text will appear in the text area below
   - Use the "Copy to Clipboard" button to copy the processed text

4. **Saving**:
   - A suggested filename will be generated based on the content
   - You can edit the filename if desired
   - Click "Save Text" to save the processed text as a markdown file
   - Files are saved to the configured output directory

5. **Custom System Prompts**:
   - Navigate to Settings > System Prompts
   - Create, edit, or delete custom processing prompts
   - Custom prompts appear in the processing mode dropdown in alphabetical order
   - Default prompts can be edited but not deleted
   - Reset to defaults option is available if needed

## Configuration

All settings are stored in `~/.config/linux-whisper-notepad/settings.json` and include:
- OpenAI API key
- Default audio device
- Output directory for saved files
- Last used processing mode

Custom system prompts are stored in `~/.config/linux-whisper-notepad/custom_prompts.json`.

## Troubleshooting

- If you encounter audio device issues, try selecting a different audio input device from the dropdown.
- Make sure your OpenAI API key is valid and has sufficient credits for using the Whisper and GPT-3.5 Turbo models.

## License

MIT