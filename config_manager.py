import os
import json
import logging
from pathlib import Path

class ConfigManager:
    """
    Configuration manager for BG3 sound tools.
    Handles saving and loading config settings to avoid 
    having to enter full paths repeatedly.
    """
    
    def __init__(self, config_file="bg3_sounds_config.json"):
        """Initialize the config manager with default paths"""
        self.config_file = config_file
        self.config = {
            "folder_unpacked_data": "",
            "folder_vgmstream": os.path.join(os.getcwd(), "dependencies", "vgmstream-win64"),
            "folder_audio_converted": os.path.join(os.getcwd(), "ConvertedAudio"),
            "folder_banks_converted": os.path.join(os.getcwd(), "ConvertedBanks"),
            "folder_bg3sids_wiki": os.path.join(os.getcwd(), "wiki_data.json"),
            "wwiser_pyz": os.path.join(os.getcwd(), "dependencies", "wwiser.pyz"),
            "output_json": os.path.join(os.getcwd(), "bg3_sounds.json"),
            "xml_output_folder": ""
        }
        self.load_config()
    
    def load_config(self):
        """Load configuration from JSON file if it exists"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Update config with loaded values
                    self.config.update(loaded_config)
                    return True
            return False
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return False
    
    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            logging.error(f"Error saving config: {e}")
            return False
    
    def get(self, key, default=None):
        """Get a configuration value"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set a configuration value"""
        self.config[key] = value
        return True
    
    def get_all(self):
        """Get the entire configuration dictionary"""
        return self.config

# Create a singleton instance
config_manager = ConfigManager()

# Easy access functions
def get_config(key, default=None):
    """Get a configuration value"""
    return config_manager.get(key, default)

def set_config(key, value):
    """Set a configuration value"""
    return config_manager.set(key, value)

def save_config():
    """Save the current configuration"""
    return config_manager.save_config()

def load_config():
    """Load the configuration from disk"""
    return config_manager.load_config()

def get_all_config():
    """Get all configuration values"""
    return config_manager.get_all()