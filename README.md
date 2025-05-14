# BG3 Sounds Converter

A GUI application for extracting, converting, and organizing Baldur's Gate 3 sound files with automatic naming based on community-sourced information.

![Application Screenshot](https://via.placeholder.com/800x500?text=BG3+Sounds+Converter+Screenshot)

## Overview

This application allows you to process Baldur's Gate 3 sound files by:

1. Converting `.wem` sound files to playable `.wav` format
2. Decoding sound bank (`.bnk`) files to understand their structure
3. Organizing converted audio files by their source banks
4. Renaming files to more descriptive names using community-sourced data

The tool builds upon [community research](https://github.com/HumansDoNotWantImmortality/bg3-sids/wiki) and automates what would otherwise be a complex manual process across multiple tools.

## Features

- **User-friendly GUI** - Simple interface to configure and run the conversion process
- **Automatic dependency management** - Downloads required tools and libraries with one click
- **Path configuration storage** - Remembers file paths between sessions so you don't have to enter them repeatedly
- **Sound file conversion** - Converts Wwise `.wem` files to standard `.wav` format
- **Bank decoding** - Decodes Wwise `.bnk` files to XML for analysis
- **File organization** - Groups audio files by source sound bank
- **Intelligent renaming** - Applies human-friendly names to files based on wiki data
- **Progress tracking** - Shows real-time progress and enables cancellation

## Requirements

- Windows operating system
- Python 3.6+
- [BG3 Modders Multitool](https://github.com/ShinyHobo/BG3-Modders-Multitool) (for unpacking game files)
- Internet connection (for downloading dependencies if needed)

## Installation

1. Clone or download this repository
2. Ensure you have Python 3.6+ installed
3. Install required Python packages:
   ```
   pip install PyQt6 qtawesome beautifulsoup4 requests
   ```
4. Run the application:
   ```
   python app.py
   ```

## Usage

### Initial Setup

1. Run the application (`python app.py`)
2. Click **Download Dependencies** to automatically retrieve required tools:
   - [wwiser](https://github.com/bnnm/wwiser) - For decoding bank files
   - [vgmstream](https://github.com/vgmstream/vgmstream) - For converting audio files
   - [BG3 Modders Multitool](https://github.com/ShinyHobo/BG3-Modders-Multitool) - For additional utilities

### Converting Files

1. **Unpack Game Files**:

   - Use BG3 Modders Multitool to unpack `SharedSoundBanks.pak` and `SharedSounds.pak`
   - From the Multitool menu: `Utilities > Game File Operations > Unpack Game Files`

2. **Configure the Application**:

   - Enter the path to your BG3 `UnpackedData` folder (paths are remembered between sessions)
   - Select the operations you want to perform:
     - **Convert sound files**: Processes `.wem` files to `.wav`
     - **Decode banks**: Extracts information from `.bnk` files
     - **Group files by bank**: Organizes audio files into bank-specific folders
     - **Rename files**: Applies descriptive names from wiki data

   > Note: File paths are automatically saved between sessions, so you won't need to browse for the same folders repeatedly. See [CONFIG_README.md](CONFIG_README.md) for more details.

3. **Start Processing**:
   - Click **Start Processing** to begin
   - Monitor progress in the log window
   - Processing can be stopped at any time with the **Stop** button

### Output Organization

The converted files will be organized in the following structure:

```
ConvertedAudio/
├── Shared/           # From "Shared" sound paths
│   ├── BankName1/    # Files grouped by sound bank
│   │   ├── Sound1.wav
│   │   ├── Sound2.wav
│   │   └── ...
│   ├── BankName2/
│   └── ...
└── SharedDev/        # From "SharedDev" sound paths
    ├── BankName1/
    └── ...

ConvertedBanks/
├── Shared/           # Decoded bank XML files
└── SharedDev/
```

## Wiki Integration

The tool can automatically rename files using data from the [BG3-SIDS wiki](https://github.com/HumansDoNotWantImmortality/bg3-sids/wiki), created by HumansDoNotWantImmortality. The wiki data is scraped and stored in `wiki_data.json`, which maps numeric sound IDs to descriptive names.

To update the wiki data:

```
python create_wiki.py
```

This will fetch the latest information from the wiki and update your local `wiki_data.json`.

## Troubleshooting

### Missing Dependencies

If the "Decode banks" or "Group files" options are disabled:

- Check if dependencies were downloaded successfully
- Ensure `wwiser.pyz` exists in the `dependencies` folder
- Click "Download Dependencies" to try again

### Renaming Not Working

If file renaming doesn't work:

- Ensure `wiki_data.json` exists in the application folder
- Run `create_wiki.py` to fetch the latest wiki data
- Check if the specific sound banks have entries in the wiki

### Conversion Errors

If sound conversion fails:

- Ensure vgmstream was downloaded correctly
- Check that your unpacked data path is correct
- The application will now automatically search all subdirectories of your UnpackedData folder if files aren't found in the expected locations

### File Discovery Improvements

The tools now include recursive file search capability:

- Automatically finds `.bnk` and `.wem` files even if they're not in the expected directory structure
- Works with various unpacking methods and folder organizations
- No need to reorganize unpacked files into a specific structure

## Technical Details

### Configuration Manager

The application now includes a path configuration manager that:

- Automatically saves file paths between sessions
- Remembers folder locations for your UnpackedData, output folders, and tool locations
- Saves settings to a `bg3_sounds_config.json` file
- Works with both the main app and the BG3 Sound Banks Dictionary Builder
- For more details, see [CONFIG_README.md](CONFIG_README.md)

### File Format Information

- `.wem`: Wwise Encoded Media - Proprietary audio format used by Wwise audio middleware
- `.bnk`: Wwise Bank file - Contains metadata and references to sound files
- `.wav`: Standard waveform audio format that most players can recognize

### Processing Flow

1. Sound banks (`.bnk`) are decoded to XML to extract sound ID mappings
2. Audio files (`.wem`) are converted to `.wav` format
3. Converted files are organized into folders based on their source bank
4. Files are renamed according to the wiki data (if available)

## Credits

- Original concept based on [/u/NikolayTeslo's work](https://www.reddit.com/r/BaldursGate3/comments/14eipmt/comment/k16mtq7/)
- Sound mapping data from [HumansDoNotWantImmortality's BG3-SIDS project](https://github.com/HumansDoNotWantImmortality/bg3-sids)
- Dependencies:
  - [wwiser](https://github.com/bnnm/wwiser) for bank decoding
  - [vgmstream](https://github.com/vgmstream/vgmstream) for audio conversion
  - [BG3 Modders Multitool](https://github.com/ShinyHobo/BG3-Modders-Multitool) for game file extraction

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
