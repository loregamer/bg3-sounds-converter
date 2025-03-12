import sys
import os
import glob
import re
import subprocess
import shutil
import urllib.request
import zipfile
import json

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QCheckBox,
    QProgressBar,
)
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

# Worker for processing audio files
class Worker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    @pyqtSlot()
    def run(self):
        # Fixed paths based on the current working directory
        wwiser_pyz = self.settings.get("wwiser_pyz", "")
        folder_vgmstream = self.settings.get("folder_vgmstream", "")
        folder_unpacked_data = self.settings.get("folder_unpacked_data", "")
        folder_audio_converted = self.settings.get("folder_audio_converted", "")
        wiki_json_path = self.settings.get("folder_bg3sids_wiki", "")
        folder_banks_converted = self.settings.get("folder_banks_converted", os.path.join(os.getcwd(), "ConvertedBanks"))
        
        should_convert = self.settings.get("should_convert", False)
        should_decode_banks = self.settings.get("should_decode_banks", False)
        should_group = self.settings.get("should_group", False)
        should_rename = self.settings.get("should_rename", False)
        
        # Create the output folders immediately.
        os.makedirs(folder_banks_converted, exist_ok=True)
        os.makedirs(folder_audio_converted, exist_ok=True)
        
        # For banks, we have two categories.
        folder_banks_converted_shared = os.path.join(folder_banks_converted, "Shared")
        folder_banks_converted_shared_dev = os.path.join(folder_banks_converted, "SharedDev")
        os.makedirs(folder_banks_converted_shared, exist_ok=True)
        os.makedirs(folder_banks_converted_shared_dev, exist_ok=True)
        
        # Define source folders
        src_sound = os.path.join(folder_unpacked_data, "SharedSounds", "Public", "Shared", "Assets", "Sound")
        src_sound_dev = os.path.join(folder_unpacked_data, "SharedSounds", "Public", "SharedDev", "Assets", "Sound")
        src_banks = os.path.join(folder_unpacked_data, "SharedSoundBanks", "Public", "Shared", "Assets", "Sound")
        src_banks_dev = os.path.join(folder_unpacked_data, "SharedSoundBanks", "Public", "SharedDev", "Assets", "Sound")
        
        dest_sound = os.path.join(folder_audio_converted, "Shared")
        dest_sound_dev = os.path.join(folder_audio_converted, "SharedDev")
        
        # Create directories if they don't exist
        os.makedirs(src_sound, exist_ok=True)
        os.makedirs(src_sound_dev, exist_ok=True)
        os.makedirs(src_banks, exist_ok=True)
        os.makedirs(src_banks_dev, exist_ok=True)
        os.makedirs(dest_sound, exist_ok=True)
        os.makedirs(dest_sound_dev, exist_ok=True)
        
        # --- Decode banks immediately, creating a bank folder per file ---
        def decode_banks(source_dir: str, target_folder: str):
            banks = glob.glob(os.path.join(source_dir, "*.bnk"))
            total = len(banks)
            bank_index = 0
            self.progress.emit(f"Decoding {total} banks in {source_dir}")
            for bank in banks:
                bank_name = os.path.basename(bank)[:-4]  # remove .bnk extension
                bank_folder = os.path.join(target_folder, bank_name)
                os.makedirs(bank_folder, exist_ok=True)  # create the bank folder immediately
                cmd = f'python "{wwiser_pyz}" -d xsl "{bank}"'
                subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Expected output file: bank_name.bnk.xml
                xml_file = bank[:-4] + ".bnk.xml"
                if os.path.exists(xml_file):
                    shutil.move(xml_file, os.path.join(bank_folder, os.path.basename(xml_file)))
                    self.progress.emit(f"Added XML for bank '{bank_name}'")
                bank_index += 1
                self.progress.emit(f"{bank_index}/{total} banks decoded in {source_dir}")
        
        # Convert .wem files using vgmstream-cli
        def convert_wem_folder(source_dir: str, dest_dir: str):
            cwd = os.getcwd()
            os.chdir(folder_vgmstream)
            wems = glob.glob(os.path.join(source_dir, "*.wem"))
            total = len(wems)
            wem_index = 0
            self.progress.emit(f"Converting {total} files from {source_dir}")
            for wem in wems:
                _, filename = os.path.split(wem)
                cmd = f'vgmstream-cli -o "{os.path.join(dest_dir, filename + ".wav")}" "{wem}"'
                subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL)
                wem_index += 1
                self.progress.emit(f"{wem_index}/{total} files converted in {source_dir}")
            os.chdir(cwd)
        
        # Group files by bank by reading the XML files stored in bank folders.
        def create_banks_folders(banks_dir: str, sounds_dir: str):
            # Walk through the banks_dir to find XML files inside each bank folder.
            for root, dirs, files in os.walk(banks_dir):
                for file in files:
                    if file.endswith(".bnk.xml"):
                        bank_name = os.path.basename(root)
                        target_folder = os.path.join(sounds_dir, bank_name)
                        os.makedirs(target_folder, exist_ok=True)
                        xml_path = os.path.join(root, file)
                        with open(xml_path, "r") as bank_file_content:
                            for line in bank_file_content:
                                if 'name="sourceID"' in line:
                                    ids = line.split('"')[-2]
                                    filename = f"{ids}.wem.wav"
                                    if filename in os.listdir(sounds_dir):
                                        shutil.move(
                                            os.path.join(sounds_dir, filename),
                                            os.path.join(target_folder, filename),
                                        )
                        self.progress.emit(f"Grouped files for bank '{bank_name}'")
        
        # Rename files using the JSON mapping
        def rename_files(source: str):
            folders = glob.glob(os.path.join(source, "*/"))
            total = len(folders)
            rename_folder_index = 0
            self.progress.emit(f"Renaming files in {total} folders from {source}")
            
            try:
                with open(wiki_json_path, "r", encoding="utf-8") as f:
                    wiki_data = json.load(f)
            except Exception as e:
                self.progress.emit(f"Error loading JSON mapping: {e}")
                return

            for folder_path in folders:
                folder_name = os.path.basename(os.path.normpath(folder_path))
                mapping_key = None
                # Find a JSON key that contains the folder name (case-insensitive)
                for key in wiki_data:
                    if folder_name.upper() in key.upper():
                        mapping_key = key
                        break

                if mapping_key is None:
                    self.progress.emit(f"No mappings found for {folder_name}")
                    continue

                content = wiki_data[mapping_key].get("content", "")
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                start_index = 0
                for i, line in enumerate(lines):
                    if line.isdigit():
                        start_index = i
                        break

                id_dict = {}
                for i in range(start_index, len(lines), 3):
                    if i + 2 < len(lines):
                        base_name = lines[i + 1]
                        ids_line = lines[i + 2]
                        ids = [x.strip() for x in ids_line.split(",") if x.strip()]
                        for idx, id_val in enumerate(ids):
                            id_dict[id_val] = f"{base_name}_{idx}"
                sounds = glob.glob(os.path.join(folder_path, "*.wem.wav"))
                for sound in sounds:
                    sound_id = os.path.basename(sound).split(".")[0]
                    if sound_id in id_dict:
                        new_name = os.path.join(folder_path, f"{id_dict[sound_id]}.wav")
                        os.rename(sound, new_name)
                rename_folder_index += 1
                self.progress.emit(f"{rename_folder_index}/{total} folders processed for renaming")
        
        # --- Process banks first ---
        if should_decode_banks:
            self.progress.emit("Decoding sound banks")
            self.progress.emit("  Processing Shared banks")
            decode_banks(src_banks, folder_banks_converted_shared)
            self.progress.emit("  Processing SharedDev banks")
            decode_banks(src_banks_dev, folder_banks_converted_shared_dev)
        
        if should_convert:
            self.progress.emit("Converting sound files")
            self.progress.emit("  Processing Shared audio")
            convert_wem_folder(src_sound, dest_sound)
            self.progress.emit("  Processing SharedDev audio")
            convert_wem_folder(src_sound_dev, dest_sound_dev)
            
        if should_group:
            self.progress.emit("Grouping files by bank")
            self.progress.emit("  Grouping Shared audio")
            create_banks_folders(folder_banks_converted_shared, dest_sound)
            self.progress.emit("  Grouping SharedDev audio")
            create_banks_folders(folder_banks_converted_shared_dev, dest_sound_dev)
            
        if should_rename:
            self.progress.emit("Renaming files")
            self.progress.emit("  Renaming Shared audio")
            rename_files(dest_sound)
            self.progress.emit("  Renaming SharedDev audio")
            rename_files(dest_sound_dev)
        
        self.progress.emit("Done")
        self.finished.emit()


# Worker for downloading dependencies and extracting zip files
class DownloadWorker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, dependencies, download_folder):
        super().__init__()
        self.dependencies = dependencies
        self.download_folder = download_folder
    
    @pyqtSlot()
    def run(self):
        os.makedirs(self.download_folder, exist_ok=True)
        for url in self.dependencies:
            file_name = url.split("/")[-1]
            destination = os.path.join(self.download_folder, file_name)
            if os.path.exists(destination):
                self.progress.emit(f"{file_name} already exists.")
            else:
                self.progress.emit(f"Downloading {file_name}...")
                try:
                    urllib.request.urlretrieve(url, destination)
                    self.progress.emit(f"Downloaded {file_name}")
                except Exception as e:
                    self.progress.emit(f"Error downloading {file_name}: {e}")
        for url in self.dependencies:
            file_name = url.split("/")[-1]
            if file_name.lower().endswith('.zip'):
                zip_path = os.path.join(self.download_folder, file_name)
                extract_folder = os.path.join(self.download_folder, file_name[:-4])
                if os.path.exists(extract_folder):
                    self.progress.emit(f"{file_name} already extracted.")
                else:
                    self.progress.emit(f"Extracting {file_name}...")
                    try:
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(extract_folder)
                        self.progress.emit(f"Extracted {file_name} to {extract_folder}")
                    except Exception as e:
                        self.progress.emit(f"Error extracting {file_name}: {e}")
        self.finished.emit()

# Main GUI Window with a single user-input field: UnpackedData
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BG3 Sound Categoriser")
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        form_layout = QFormLayout()
        layout.addLayout(form_layout)
        
        self.unpacked_data_edit = QLineEdit()
        self.add_browse_button(form_layout, "Path to UnpackedData:", self.unpacked_data_edit)
        
        self.convert_checkbox = QCheckBox("Convert sound files")
        self.decode_checkbox = QCheckBox("Decode banks")
        self.group_checkbox = QCheckBox("Group files by bank")
        self.rename_checkbox = QCheckBox("Rename files")
        
        layout.addWidget(self.convert_checkbox)
        layout.addWidget(self.decode_checkbox)
        layout.addWidget(self.group_checkbox)
        layout.addWidget(self.rename_checkbox)
        
        btn_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Processing")
        self.start_button.clicked.connect(self.start_processing)
        btn_layout.addWidget(self.start_button)
        
        self.download_button = QPushButton("Download Dependencies")
        self.download_button.clicked.connect(self.download_dependencies)
        btn_layout.addWidget(self.download_button)
        
        layout.addLayout(btn_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
    def add_browse_button(self, form_layout, label, line_edit):
        h_layout = QHBoxLayout()
        h_layout.addWidget(line_edit)
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(lambda: self.browse_folder(line_edit))
        h_layout.addWidget(browse_button)
        form_layout.addRow(label, h_layout)
        
    def browse_folder(self, line_edit):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            line_edit.setText(folder)
        
    def start_processing(self):
        self.start_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_text.clear()
        
        # Build settings using fixed paths relative to the current working directory.
        # The ConvertedBanks folder is defined here and created before ConvertedAudio.
        settings = {
            "folder_unpacked_data": self.unpacked_data_edit.text(),
            "wwiser_pyz": os.path.join(os.getcwd(), "dependencies", "wwiser.pyz"),
            "folder_vgmstream": os.path.join(os.getcwd(), "dependencies", "vgmstream-win64"),
            "folder_audio_converted": os.path.join(os.getcwd(), "ConvertedAudio"),
            "folder_banks_converted": os.path.join(os.getcwd(), "ConvertedBanks"),
            "folder_bg3sids_wiki": os.path.join(os.getcwd(), "wiki_data.json"),
            "should_convert": self.convert_checkbox.isChecked(),
            "should_decode_banks": self.decode_checkbox.isChecked(),
            "should_group": self.group_checkbox.isChecked(),
            "should_rename": self.rename_checkbox.isChecked(),
        }
        
        self.thread = QThread()
        self.worker = Worker(settings)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.report_progress)
        self.worker.finished.connect(self.processing_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()
        
    def download_dependencies(self):
        self.download_button.setEnabled(False)
        self.log_text.append("Starting dependency download...")
        
        dependencies = [
            "https://github.com/bnnm/wwiser/releases/download/v20241210/wwiser.pyz",
            "https://github.com/bnnm/wwiser/releases/download/v20241210/wwnames.db3",
            "https://github.com/vgmstream/vgmstream-releases/releases/download/nightly/vgmstream-win64.zip",
            "https://github.com/ShinyHobo/BG3-Modders-Multitool/releases/download/v0.13.3/bg3-modders-multitool.zip",
        ]
        download_folder = os.path.join(os.getcwd(), "dependencies")
        
        self.dl_thread = QThread()
        self.dl_worker = DownloadWorker(dependencies, download_folder)
        self.dl_worker.moveToThread(self.dl_thread)
        
        self.dl_thread.started.connect(self.dl_worker.run)
        self.dl_worker.progress.connect(self.report_progress)
        self.dl_worker.finished.connect(self.download_finished)
        self.dl_worker.finished.connect(self.dl_thread.quit)
        self.dl_worker.finished.connect(self.dl_worker.deleteLater)
        self.dl_thread.finished.connect(self.dl_thread.deleteLater)
        
        self.dl_thread.start()
        
    @pyqtSlot(str)
    def report_progress(self, message):
        self.log_text.append(message)
        
    @pyqtSlot()
    def processing_finished(self):
        self.log_text.append("Processing complete.")
        self.progress_bar.setVisible(False)
        self.start_button.setEnabled(True)
        
    @pyqtSlot()
    def download_finished(self):
        self.log_text.append("Dependency download and extraction complete.")
        self.download_button.setEnabled(True)

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
