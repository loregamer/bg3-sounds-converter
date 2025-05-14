#!/usr/bin/env python3
""" app2.py - BG3 Sound Banks Dictionary Builder
A PyQt6 GUI application for listing WEM files by sound banks from decoded BNK files
"""

import os
import sys
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from config_manager import get_config, set_config, save_config, load_config
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any, Tuple

# PyQt6 imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QFileDialog, QCheckBox,
    QSpinBox, QComboBox, QLineEdit, QMessageBox, QGroupBox, QTextEdit,
    QTabWidget, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

class BankProcessingWorker(QThread):
    """Worker thread for processing BNK files"""
    progress_update = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    log_message = pyqtSignal(str)
    
    def __init__(self, 
                 unpacked_data_folder: str, 
                 wwiser_pyz_path: str, 
                 output_folder: Optional[str] = None,
                 shared_only: bool = False,
                 shareddev_only: bool = False,
                 num_threads: int = 4):
        super().__init__()
        self.unpacked_data_folder = unpacked_data_folder
        self.wwiser_pyz_path = wwiser_pyz_path
        self.output_folder = output_folder
        self.shared_only = shared_only
        self.shareddev_only = shareddev_only
        self.num_threads = num_threads
        self.is_cancelled = False
    
    def run(self):
        """Main method that runs in the thread"""
        try:
            # Check dependencies
            if not check_dependencies(self.wwiser_pyz_path):
                self.error.emit(f"Required dependency not found: {self.wwiser_pyz_path}")
                return
                
            self.log_message.emit("Finding BNK files...")
            # Find all BNK files
            bnk_files = find_bnk_files(self.unpacked_data_folder, self.shared_only, self.shareddev_only)
            
            # Initialize result dictionary
            all_banks = {}
            
            # Count total files for progress tracking
            total_files = sum(len(files) for files in bnk_files.values())
            self.log_message.emit(f"Found {total_files} BNK files to process")
            
            if total_files == 0:
                self.error.emit("No BNK files found in the specified location")
                return
                
            processed_files = 0
            
            # Process each folder (Shared, SharedDev)
            for folder, files in bnk_files.items():
                self.log_message.emit(f"Processing {len(files)} BNK files in {folder}...")
                all_banks[folder] = {}
                
                # Prepare tasks for thread pool
                tasks = []
                for bnk_file in files:
                    bank_name = os.path.basename(bnk_file).replace(".bnk", "")
                    tasks.append((self.wwiser_pyz_path, bnk_file, bank_name, self.output_folder))
                
                # Process files in parallel
                with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
                    for bank_name, bank_info in executor.map(process_bnk_file, tasks):
                        if self.is_cancelled:
                            self.log_message.emit("Processing cancelled")
                            return
                            
                        all_banks[folder][bank_name] = bank_info
                        
                        # Update progress
                        processed_files += 1
                        completion_percentage = int((processed_files / total_files) * 100)
                        self.progress_update.emit(processed_files, total_files, bank_name)
            
            self.finished.emit(all_banks)
            
        except Exception as e:
            self.error.emit(f"Error processing banks: {str(e)}")
    
    def cancel(self):
        """Cancel the processing"""
        self.is_cancelled = True

def check_dependencies(wwiser_path: str) -> bool:
    """Check if required dependencies are available."""
    if not os.path.exists(wwiser_path):
        logger.error(f"Required dependency not found: {wwiser_path}")
        return False
    return True

def decode_bnk_file(wwiser_pyz_path: str, bnk_file_path: str, output_folder: Optional[str] = None) -> Optional[str]:
    """
    Decode a single BNK file to XML using wwiser.pyz
    
    Args:
        wwiser_pyz_path: Path to the wwiser.pyz file
        bnk_file_path: Path to the BNK file to decode
        output_folder: Optional folder for output, if None uses same directory as BNK
        
    Returns:
        Path to the generated XML file or None if decoding failed
    """
    try:
        # Determine output path
        if output_folder is None:
            xml_path = f"{bnk_file_path}.xml"
        else:
            os.makedirs(output_folder, exist_ok=True)
            xml_path = os.path.join(output_folder, f"{os.path.basename(bnk_file_path)}.xml")
        
        # Call wwiser.pyz to decode the BNK file
        cmd = [sys.executable, wwiser_pyz_path, "decode", bnk_file_path, "-o", xml_path]
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode != 0:
            logger.error(f"Failed to decode {bnk_file_path}: {process.stderr}")
            return None
        
        # Check if the XML file was created
        if not os.path.exists(xml_path):
            logger.error(f"XML file not created: {xml_path}")
            return None
        
        return xml_path
    
    except Exception as e:
        logger.error(f"Error decoding {bnk_file_path}: {str(e)}")
        return None

def parse_bnk_xml(xml_path: str) -> Dict[str, Any]:
    """
    Parse an XML file to extract sound IDs and other metadata
    
    Args:
        xml_path: Path to the XML file to parse
        
    Returns:
        Dictionary with the bank's information
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        bank_name = os.path.basename(xml_path).replace(".bnk.xml", "")
        bank_info = {
            "name": bank_name,
            "sound_files": {}
        }
        
        # Find all embedded wem files
        for sound_sfx in root.findall(".//SoundSFX"):
            for embedded_file in sound_sfx.findall(".//EmbeddedFile"):
                file_id = embedded_file.get("ID")
                if file_id:
                    wem_filename = f"{file_id}.wem"
                    bank_info["sound_files"][file_id] = {
                        "wem_filename": wem_filename,
                        "wav_filename": f"{wem_filename}.wav"
                    }
        
        # Look for additional metadata like sound paths or references
        for media_source in root.findall(".//MediaSource"):
            source_id = media_source.get("ID")
            if source_id and source_id in bank_info["sound_files"]:
                source_info = bank_info["sound_files"][source_id]
                
                # Extract any additional metadata (file path, etc.)
                source_file = media_source.find("SourceFile")
                if source_file is not None and source_file.text:
                    source_info["source_path"] = source_file.text
        
        return bank_info
    
    except Exception as e:
        logger.error(f"Error parsing XML {xml_path}: {str(e)}")
        return {"name": os.path.basename(xml_path).replace(".bnk.xml", ""), "sound_files": {}}

def find_bnk_files(unpacked_data_folder: str, shared_only: bool = False, shareddev_only: bool = False) -> Dict[str, List[str]]:
    """
    Find all BNK files in the unpacked data folder, searching all subdirectories
    
    Args:
        unpacked_data_folder: Path to the UnpackedData folder
        shared_only: Process only Shared folder (if found)
        shareddev_only: Process only SharedDev folder (if found)
        
    Returns:
        Dictionary with folder names as keys and lists of BNK file paths as values
    """
    bnk_files = {"Other": []}  # Default category for BNK files not in Shared or SharedDev

    # Walk through all directories starting from the unpacked_data_folder
    logger.info(f"Searching for BNK files in {unpacked_data_folder} (including all subdirectories)...")
    
    # Check if specific paths exist for Shared and SharedDev
    shared_path = None
    shared_dev_path = None
    
    # Try different possible folder structures
    possible_shared_paths = [
        os.path.join(unpacked_data_folder, "Public", "Shared"),
        os.path.join(unpacked_data_folder, "Shared"),
        os.path.join(unpacked_data_folder, "Data", "Public", "Shared"),
        os.path.join(unpacked_data_folder, "SharedSoundBanks", "Public", "Shared")
    ]
    
    possible_shared_dev_paths = [
        os.path.join(unpacked_data_folder, "Public", "SharedDev"),
        os.path.join(unpacked_data_folder, "SharedDev"),
        os.path.join(unpacked_data_folder, "Data", "Public", "SharedDev"),
        os.path.join(unpacked_data_folder, "SharedSoundBanks", "Public", "SharedDev")
    ]
    
    # Find the first valid path for Shared
    for path in possible_shared_paths:
        if os.path.exists(path):
            shared_path = path
            break
    
    # Find the first valid path for SharedDev
    for path in possible_shared_dev_paths:
        if os.path.exists(path):
            shared_dev_path = path
            break
    
    # Initialize the dictionaries for Shared and SharedDev
    if shared_path and not shareddev_only:
        bnk_files["Shared"] = []
        logger.info(f"Found Shared folder at {shared_path}")
    
    if shared_dev_path and not shared_only:
        bnk_files["SharedDev"] = []
        logger.info(f"Found SharedDev folder at {shared_dev_path}")
    
    # Walk through all directories and categorize BNK files
    for root, _, files in os.walk(unpacked_data_folder):
        for file in files:
            if file.lower().endswith(".bnk"):
                file_path = os.path.join(root, file)
                
                # Categorize based on path
                if shared_path and not shareddev_only and shared_path in root:
                    bnk_files["Shared"].append(file_path)
                elif shared_dev_path and not shared_only and shared_dev_path in root:
                    bnk_files["SharedDev"].append(file_path)
                else:
                    # If we can't categorize, put in Other
                    bnk_files["Other"].append(file_path)
    
    # Remove empty categories
    for category in list(bnk_files.keys()):
        if not bnk_files[category]:
            del bnk_files[category]
            
    # Count found files
    total_files = sum(len(files) for files in bnk_files.values())
    for category, files in bnk_files.items():
        logger.info(f"Found {len(files)} BNK files in category '{category}'")
    
    return bnk_files



def process_bnk_file(args: Tuple[str, str, str, Optional[str]]) -> Tuple[str, Dict[str, Any]]:
    """
    Process a single BNK file
    
    Args:
        args: Tuple containing (wwiser_path, bnk_file, bank_name, output_folder)
        
    Returns:
        Tuple of (bank_name, bank_info)
    """
    wwiser_path, bnk_file, bank_name, output_folder = args
    xml_path = decode_bnk_file(wwiser_path, bnk_file, output_folder)
    if xml_path:
        bank_info = parse_bnk_xml(xml_path)
        return (bank_name, bank_info)
    return (bank_name, {"name": bank_name, "sound_files": {}})

def build_bnk_dictionary(
    unpacked_data_folder: str, 
    wwiser_pyz_path: str, 
    output_folder: Optional[str] = None,
    shared_only: bool = False,
    shareddev_only: bool = False,
    num_threads: int = 4
) -> Dict[str, Dict[str, Any]]:
    """
    Process all BNK files and build a structured dictionary
    
    Args:
        unpacked_data_folder: Path to the UnpackedData folder
        wwiser_pyz_path: Path to the wwiser.pyz file
        output_folder: Optional folder for decoded files
        shared_only: Process only Shared folder
        shareddev_only: Process only SharedDev folder
        num_threads: Number of threads for parallel processing
        
    Returns:
        Dictionary with all bank data
    """
    # Find all BNK files
    bnk_files = find_bnk_files(unpacked_data_folder, shared_only, shareddev_only)
    
    # Initialize result dictionary
    all_banks = {}
    
    # Count total files for progress tracking
    total_files = sum(len(files) for files in bnk_files.values())
    processed_files = 0
    
    # Process each folder (Shared, SharedDev)
    for folder, files in bnk_files.items():
        logger.info(f"Processing {len(files)} BNK files in {folder}...")
        all_banks[folder] = {}
        
        # Prepare tasks for thread pool
        tasks = []
        for bnk_file in files:
            bank_name = os.path.basename(bnk_file).replace(".bnk", "")
            tasks.append((wwiser_pyz_path, bnk_file, bank_name, output_folder))
        
        # Process files in parallel
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            for bank_name, bank_info in executor.map(process_bnk_file, tasks):
                all_banks[folder][bank_name] = bank_info
                
                # Update progress
                processed_files += 1
                completion_percentage = (processed_files / total_files) * 100
                logger.info(f"Progress: {processed_files}/{total_files} ({completion_percentage:.1f}%)")
    
    return all_banks

class BG3SoundsDictionaryApp(QMainWindow):
    """Main application window for BG3 Sounds Dictionary Builder"""
    
    def __init__(self):
        super().__init__()
        self.all_banks = {}
        self.worker = None
        # Load saved configuration
        load_config()
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("BG3 Sound Banks Dictionary Builder")
        self.setMinimumSize(800, 600)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Path selection group
        path_group = QGroupBox("Paths")
        path_layout = QVBoxLayout(path_group)
        
        # UnpackedData folder selection
        unpacked_layout = QHBoxLayout()
        self.unpacked_label = QLabel("UnpackedData Folder:")
        self.unpacked_path = QLineEdit()
        self.unpacked_path.setText(get_config("folder_unpacked_data", ""))
        self.unpacked_path.setPlaceholderText("Path to BG3 UnpackedData folder")
        self.unpacked_btn = QPushButton("Browse...")
        self.unpacked_btn.clicked.connect(self.browse_unpacked)
        unpacked_layout.addWidget(self.unpacked_label)
        unpacked_layout.addWidget(self.unpacked_path)
        unpacked_layout.addWidget(self.unpacked_btn)
        path_layout.addLayout(unpacked_layout)
        
        # Output JSON file selection
        output_layout = QHBoxLayout()
        self.output_label = QLabel("Output JSON File:")
        self.output_path = QLineEdit(get_config("output_json", "bg3_sounds.json"))
        self.output_btn = QPushButton("Browse...")
        self.output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(self.output_btn)
        path_layout.addLayout(output_layout)
        
        # XML output folder selection
        xml_layout = QHBoxLayout()
        self.xml_label = QLabel("XML Output Folder (optional):")
        self.xml_path = QLineEdit()
        self.xml_path.setText(get_config("xml_output_folder", ""))
        self.xml_path.setPlaceholderText("Leave empty to use default location")
        self.xml_btn = QPushButton("Browse...")
        self.xml_btn.clicked.connect(self.browse_xml)
        xml_layout.addWidget(self.xml_label)
        xml_layout.addWidget(self.xml_path)
        xml_layout.addWidget(self.xml_btn)
        path_layout.addLayout(xml_layout)
        
        # Wwiser.pyz selection
        wwiser_layout = QHBoxLayout()
        self.wwiser_label = QLabel("Wwiser.pyz Path:")
        self.wwiser_path = QLineEdit(get_config("wwiser_pyz", "wwiser.pyz"))
        self.wwiser_btn = QPushButton("Browse...")
        self.wwiser_btn.clicked.connect(self.browse_wwiser)
        wwiser_layout.addWidget(self.wwiser_label)
        wwiser_layout.addWidget(self.wwiser_path)
        wwiser_layout.addWidget(self.wwiser_btn)
        path_layout.addLayout(wwiser_layout)
        

        
        main_layout.addWidget(path_group)
        
        # Options group
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        # Folder options
        folder_layout = QHBoxLayout()
        self.shared_only = QCheckBox("Process only Shared")
        self.shareddev_only = QCheckBox("Process only SharedDev")
        # Connect these checkboxes to be mutually exclusive
        self.shared_only.clicked.connect(lambda: self.shareddev_only.setChecked(False) if self.shared_only.isChecked() else None)
        self.shareddev_only.clicked.connect(lambda: self.shared_only.setChecked(False) if self.shareddev_only.isChecked() else None)
        folder_layout.addWidget(self.shared_only)
        folder_layout.addWidget(self.shareddev_only)
        options_layout.addLayout(folder_layout)
        
        # Other options
        other_layout = QHBoxLayout()
        
        # Thread count
        thread_layout = QHBoxLayout()
        self.thread_label = QLabel("Parallel threads:")
        self.thread_spinner = QSpinBox()
        self.thread_spinner.setMinimum(1)
        self.thread_spinner.setMaximum(32)
        self.thread_spinner.setValue(4)
        thread_layout.addWidget(self.thread_label)
        thread_layout.addWidget(self.thread_spinner)
        other_layout.addLayout(thread_layout)
        options_layout.addLayout(other_layout)
        
        main_layout.addWidget(options_group)
        
        # Log area
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group, 1)  # Give the log area more space
        
        # Progress area
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("Ready")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        main_layout.addWidget(progress_group)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Processing")
        self.start_btn.clicked.connect(self.start_processing)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)
        self.save_btn = QPushButton("Save Dictionary")
        self.save_btn.clicked.connect(self.save_dictionary)
        self.save_btn.setEnabled(False)
        buttons_layout.addWidget(self.start_btn)
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.save_btn)
        main_layout.addLayout(buttons_layout)
        
        self.setCentralWidget(main_widget)
        self.log_message("Ready to process BG3 sound banks and list WEM files. Please select UnpackedData folder and configure options.")
    
    def browse_unpacked(self):
        """Browse for UnpackedData folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select UnpackedData Folder")
        if folder:
            self.unpacked_path.setText(folder)
            set_config("folder_unpacked_data", folder)
            save_config()
    
    def browse_output(self):
        """Browse for output JSON file"""
        file, _ = QFileDialog.getSaveFileName(self, "Select Output JSON File", "", "JSON Files (*.json)")
        if file:
            self.output_path.setText(file)
            set_config("output_json", file)
            save_config()
    
    def browse_xml(self):
        """Browse for XML output folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select XML Output Folder")
        if folder:
            self.xml_path.setText(folder)
            set_config("xml_output_folder", folder)
            save_config()
    
    def browse_wwiser(self):
        """Browse for wwiser.pyz"""
        file, _ = QFileDialog.getOpenFileName(self, "Select Wwiser.pyz File", "", "Python ZIP Files (*.pyz)")
        if file:
            self.wwiser_path.setText(file)
            set_config("wwiser_pyz", file)
            save_config()
    

    
    def log_message(self, message):
        """Add a message to the log area"""
        self.log_text.append(f"{message}")
        # Scroll to the bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        # Also log to console
        logger.info(message)
    
    def start_processing(self):
        """Start the BNK processing"""
        # Validate inputs
        if not self.unpacked_path.text():
            QMessageBox.warning(self, "Warning", "Please select the UnpackedData folder")
            return
            
        # Save current config values before processing
        set_config("folder_unpacked_data", self.unpacked_path.text())
        set_config("wwiser_pyz", self.wwiser_path.text())
        set_config("output_json", self.output_path.text())
        set_config("xml_output_folder", self.xml_path.text())
        save_config()
        
        if not os.path.exists(self.unpacked_path.text()):
            QMessageBox.warning(self, "Warning", "The specified UnpackedData folder does not exist")
            return
        
        if not os.path.exists(self.wwiser_path.text()):
            QMessageBox.warning(self, "Warning", "Wwiser.pyz not found at the specified path")
            return
        
        # Configure worker thread
        self.worker = BankProcessingWorker(
            unpacked_data_folder=self.unpacked_path.text(),
            wwiser_pyz_path=self.wwiser_path.text(),
            output_folder=self.xml_path.text() if self.xml_path.text() else None,
            shared_only=self.shared_only.isChecked(),
            shareddev_only=self.shareddev_only.isChecked(),
            num_threads=self.thread_spinner.value()
        )
        
        # Connect signals
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished.connect(self.processing_finished)
        self.worker.error.connect(self.show_error)
        self.worker.log_message.connect(self.log_message)
        
        # Update UI
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.save_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting...")
        
        # Start worker
        self.log_message("Starting processing...")
        self.worker.start()
    
    def update_progress(self, current, total, current_file):
        """Update the progress bar and label"""
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(f"Processing {current}/{total}: {current_file}")
    
    def processing_finished(self, all_banks):
        """Handle completion of processing"""
        self.all_banks = all_banks
        self.log_message("Processing completed successfully!")
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.save_btn.setEnabled(True)
        self.progress_label.setText("Processing completed")
        
        # Count total banks and sound files
        total_banks = 0
        total_sounds = 0
        for folder, banks in all_banks.items():
            total_banks += len(banks)
            for bank_name, bank_info in banks.items():
                total_sounds += len(bank_info["sound_files"])
        
        self.log_message(f"Processed {total_banks} banks containing {total_sounds} sound files")
        
        # Auto-save if output path is specified
        if self.output_path.text():
            self.save_dictionary()
    
    def show_error(self, error_message):
        """Display an error message"""
        self.log_message(f"ERROR: {error_message}")
        QMessageBox.critical(self, "Error", error_message)
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_label.setText("Error occurred")
    
    def cancel_processing(self):
        """Cancel the ongoing processing"""
        if self.worker and self.worker.isRunning():
            self.log_message("Cancelling processing...")
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.progress_label.setText("Cancelling...")
    
    def save_dictionary(self):
        """Save the generated dictionary to a JSON file"""
        if not self.all_banks:
            QMessageBox.warning(self, "Warning", "No dictionary data to save")
            return
        
        output_path = self.output_path.text()
        if not output_path:
            output_path, _ = QFileDialog.getSaveFileName(self, "Save Dictionary", "", "JSON Files (*.json)")
            if not output_path:
                return
            self.output_path.setText(output_path)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.all_banks, f, indent=2, ensure_ascii=False)
            self.log_message(f"Successfully saved dictionary to {output_path}")
            QMessageBox.information(self, "Success", f"Dictionary saved to {output_path}")
        except Exception as e:
            error_msg = f"Error saving dictionary: {str(e)}"
            self.log_message(error_msg)
            QMessageBox.critical(self, "Error", error_msg)

def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)
    window = BG3SoundsDictionaryApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
