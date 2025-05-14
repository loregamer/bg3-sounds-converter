# `app2.py` Development Plan

## Overview

The new `app2.py` is an application focused on building a comprehensive dictionary of decoded BNK files for easy parsing. It is implemented as a GUI tool that extracts and organizes the sound data into a structured JSON format.

## Key Features

- User-friendly GUI interface
- Path configuration storage that remembers locations between sessions
- Focused only on BNK decoding and dictionary building
- Outputs structured JSON data instead of organizing files
- Simplified workflow without audio conversion functionality
- Multi-threaded processing for better performance

## Required Dependencies

- `wwiser.pyz` - For decoding BNK files to XML
- `wiki_data.json` (optional) - For adding friendly names to sound files

## Functions and Structure

### 1. User Interface

The app includes a GUI with fields for:

- UnpackedData folder selection
- Output JSON file path
- XML output folder (optional)
- Wwiser.pyz path
- Thread count for parallel processing
- Processing options (Shared/SharedDev folders)

All paths are automatically remembered between sessions using the configuration manager.

### 2. BNK Decoding

```python
def decode_bnk_file(wwiser_pyz_path, bnk_file_path, output_folder=None):
    # Decode a single BNK file to XML using wwiser.pyz
    # Return path to the XML file
```

### 3. XML Parsing

```python
def parse_bnk_xml(xml_path):
    # Parse an XML file to extract sound IDs and other metadata
    # Return a dictionary with the bank's information
```

### 4. Dictionary Building

```python
def build_bnk_dictionary(unpacked_data_folder, wwiser_pyz_path, output_folder=None):
    # Process all BNK files in Shared and SharedDev folders
    # Build a structured dictionary with all bank data
```

### 5. Wiki Integration (Optional)

```python
def add_wiki_names_to_banks(all_banks, wiki_data):
    # Add human-readable names using wiki_data.json
    # Match sound IDs to friendly names
```

## Data Structure

The output JSON will have this structure:

```json
{
  "Shared": {
    "BankName1": {
      "name": "BankName1",
      "sound_files": {
        "123456": {
          "wem_filename": "123456.wem",
          "wav_filename": "123456.wem.wav",
          "friendly_name": "Music_Combat_01"
        }
      }
    }
  },
  "SharedDev": {
    // Same structure as Shared
  }
}
```

## Usage

1. Launch the application with `python app2.py`
2. Configure the paths (these will be remembered for future sessions)
3. Select processing options
4. Click "Start Processing" to begin
5. Once completed, click "Save Dictionary" to export the JSON file

## Workflow

1. Check for required dependencies (wwiser.pyz)
2. Locate BNK files in the UnpackedData directory (Shared and SharedDev folders)
3. Decode each BNK file to XML using wwiser.pyz
4. Parse each XML file to extract sound IDs and metadata
5. Build dictionary structure organizing the data by bank and sound ID
6. If wiki_data.json is available and not disabled, add friendly names to sound files
7. Save complete dictionary to JSON file
8. Return the dictionary (useful for importing the module in other scripts)

## Bonus Features

- Progress tracking with bank count and completion percentage
- Error handling for missing dependencies and XML parsing issues
- Support for selective processing (only Shared or only SharedDev)
- Configuration storage to remember paths between sessions
- Multi-threaded processing with configurable thread count
