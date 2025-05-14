# Path Configuration Manager

This project now includes a configuration manager that remembers paths between sessions, so you don't have to repeatedly enter the same file paths.

## Features

- Automatically remembers important file paths between application launches
- Works with both app.py (Sound Categoriser) and app2.py (Sound Banks Dictionary Builder)
- Stores configuration in a simple JSON file for easy editing
- Simplifies workflow for repeated use
- Integrates with improved recursive file search for finding files in any structure

## Recent Improvements

- **Recursive file search**: Both applications now recursively search for files if they aren't found in the expected locations
- **Path flexibility**: You can select any UnpackedData folder regardless of internal organization
- **Combined with path memory**: Select a path once, and the app will find all files in that path (and subpaths) in future sessions

## Saved Settings

The configuration manager automatically saves these paths:

- UnpackedData folder location
- Wwiser.pyz path
- Output JSON file location (for app2)
- XML output folder (for app2)
- vgmstream folder
- Converted audio folder
- Converted banks folder
- Wiki data JSON path

## How It Works

When you browse and select a folder or file in the application, the path is automatically saved to the configuration file. The next time you open the application, these paths will be pre-filled for you.

## Configuration File

The configuration is stored in `bg3_sounds_config.json` in the same folder as the applications. If you need to manually edit or reset the configuration, you can edit or delete this file.

## Technical Details

The configuration manager is implemented in `config_manager.py` and provides these functions:

- `get_config(key, default=None)`: Get a configuration value
- `set_config(key, value)`: Set a configuration value
- `save_config()`: Save the current configuration to disk
- `load_config()`: Load the configuration from disk

Both applications now use these functions to manage user preferences.
