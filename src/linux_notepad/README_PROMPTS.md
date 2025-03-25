# Default System Prompts

This directory contains the `default_prompts.json` file which stores all the default system prompts used by the application.

## Structure

Each prompt in the JSON file follows this format:

```json
"prompt_id": {
    "name": "Display Name",
    "prompt": "The system prompt text...",
    "requires_json": false
}
```

- `prompt_id`: A unique identifier (snake_case)
- `name`: The display name shown in the UI
- `prompt`: The actual system prompt text
- `requires_json`: Set to `true` if the prompt expects a structured JSON response

## Adding New Prompts

To add a new prompt:

1. Open `default_prompts.json`
2. Add a new entry following the format above
3. Choose a unique `prompt_id`
4. Provide a descriptive `name`
5. Write your prompt text
6. Set `requires_json` appropriately

## Example

```json
"meeting_minutes": {
    "name": "Meeting Minutes",
    "prompt": "Format the following transcript as professional meeting minutes...",
    "requires_json": false
}
```

## Notes

- The application will automatically load all prompts from this file at startup
- If the file is missing or corrupted, the application will fall back to a minimal set of default prompts
- User-defined prompts are stored separately and will override default prompts with the same ID
