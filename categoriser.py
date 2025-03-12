import sys
import os
import glob
import re
import subprocess
import shutil
import urllib.request

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
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
        # Retrieve settings from the GUI
        wwiser_pyz = self.settings.get("wwiser_pyz", "")
        folder_vgmstream = self.settings.get("folder_vgmstream", "")
        folder_unpacked_data = self.settings.get("folder_unpacked_data", "")
        folder_audio_converted = self.settings.get("folder_audio_converted", "")
        folder_bg3sids_wiki = self.settings.get("folder_bg3sids_wiki", "")
        
        should_convert = self.settings.get("should_convert", False)
        should_decode_banks = self.settings.get("should_decode_banks", False)
        should_group = self.settings.get("should_group", False)
        should_rename = self.settings.get("should_rename", False)
        
        # Helper functions (adapted from the CLI version)
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
        
        def decode_banks(source_dir: str):
            banks = glob.glob(os.path.join(source_dir, "*.bnk"))
            total = len(banks)
            bank_index = 0
            self.progress.emit(f"Decoding {total} banks in {source_dir}")
            for bank in banks:
                cmd = f'python "{wwiser_pyz}" -d xsl "{bank}"'
                subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                bank_index += 1
                self.progress.emit(f"{bank_index}/{total} banks decoded in {source_dir}")
        
        def create_banks_folders(banks_dir: str, sounds_dir: str):
            banks_xmls = glob.glob(os.path.join(banks_dir, "*.bnk.xml"))
            total = len(banks_xmls)
            bank_folder_index = 0
            self.progress.emit(f"Grouping {total} banks from {banks_dir}")
            for bank_filename in banks_xmls:
                bank_folder = os.path.basename(bank_filename).split(".")[0]
                target_folder = os.path.join(sounds_dir, bank_folder)
                if not os.path.exists(target_folder):
                    os.makedirs(target_folder)
                with open(bank_filename, "r") as bank_file_content:
                    for line in bank_file_content:
                        if 'name="sourceID"' in line:
                            ids = line.split('"')[-2]
                            filename = f"{ids}.wem.wav"
                            if filename in os.listdir(sounds_dir):
                                shutil.move(
                                    os.path.join(sounds_dir, filename),
                                    os.path.join(target_folder, filename),
                                )
                bank_folder_index += 1
                self.progress.emit(f"{bank_folder_index}/{total} banks grouped in {banks_dir}")
        
        def rename_files(source: str):
            folders = glob.glob(os.path.join(source, "*/"))
            total = len(folders)
            rename_folder_index = 0
            self.progress.emit(f"Renaming files in {total} folders from {source}")
            markdown_files = glob.glob(os.path.join(folder_bg3sids_wiki, "*.bnk.md"))
            for folder_path in folders:
                folder_name = os.path.basename(os.path.normpath(folder_path))
                markdown_file = None
                for file_name in markdown_files:
                    if f"{folder_name}-" in file_name or f"{folder_name}.bnk.md" in file_name:
                        markdown_file = file_name
                        break
                if markdown_file is None:
                    self.progress.emit(f"No mappings found for {folder_name}")
                    continue
                if "Amb_[PAK]_Amb_Ps_Specific-_-AMB_PS_SPECIFIC.bnk.md" in markdown_file:
                    markdown_file = os.path.join(folder_bg3sids_wiki, "Ambience_[PAK]_Amb_Ps_Specific-_-AMB_PS_SPECIFIC.bnk.md")
                id_dict = {}
                with open(markdown_file, "r") as markdown_file_content:
                    for line in markdown_file_content:
                        line_match = re.match(r"^\| \d+ \| (\w+) \| (.*) \|$", line)
                        if line_match is not None:
                            base_name = line_match.group(1)
                            ids = line_match.group(2).split(", ")
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
        
        # Define source and destination folders based on the unpacked data and output folder
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
        
        # Execute the operations based on selected options
        if should_convert:
            self.progress.emit("Converting sound files")
            self.progress.emit("  Processing Shared")
            convert_wem_folder(src_sound, dest_sound)
            self.progress.emit("  Processing SharedDev")
            convert_wem_folder(src_sound_dev, dest_sound_dev)
            
        if should_decode_banks:
            self.progress.emit("Decoding sound banks")
            self.progress.emit("  Processing Shared")
            decode_banks(src_banks)
            self.progress.emit("  Processing SharedDev")
            decode_banks(src_banks_dev)
            
        if should_group:
            self.progress.emit("Grouping files by bank")
            self.progress.emit("  Processing Shared")
            create_banks_folders(src_banks, dest_sound)
            self.progress.emit("  Processing SharedDev")
            create_banks_folders(src_banks_dev, dest_sound_dev)
            
        if should_rename:
            self.progress.emit("Renaming files")
            self.progress.emit("  Processing Shared")
            rename_files(dest_sound)
            self.progress.emit("  Processing SharedDev")
            rename_files(dest_sound_dev)
        
        self.progress.emit("Done")
        self.finished.emit()


# Worker for downloading dependencies
class DownloadWorker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, dependencies, download_folder):
        super().__init__()
        self.dependencies = dependencies
        self.download_folder = download_folder
    
    @pyqtSlot()
    def run(self):
        # Ensure the download folder exists
        os.makedirs(self.download_folder, exist_ok=True)
        for url in self.dependencies:
            file_name = url.split("/")[-1]
            destination = os.path.join(self.download_folder, file_name)
            if os.path.exists(destination):
                self.progress.emit(f"{file_name} already exists.")
                continue
            self.progress.emit(f"Downloading {file_name}...")
            try:
                urllib.request.urlretrieve(url, destination)
                self.progress.emit(f"Downloaded {file_name}")
            except Exception as e:
                self.progress.emit(f"Error downloading {file_name}: {e}")
        self.finished.emit()


# Main GUI Window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BG3 Sound Categoriser")
        
        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Form layout for folder paths
        form_layout = QFormLayout()
        layout.addLayout(form_layout)
        
        self.wwiser_pyz_edit = QLineEdit()
        self.add_browse_button(form_layout, "Path to wwiser.pyz:", self.wwiser_pyz_edit)
        
        self.folder_vgmstream_edit = QLineEdit()
        self.add_browse_button(form_layout, "Path to folder_vgmstream:", self.folder_vgmstream_edit)
        
        self.folder_unpacked_data_edit = QLineEdit()
        self.add_browse_button(form_layout, "Path to folder_unpacked_data:", self.folder_unpacked_data_edit)
        
        self.folder_audio_converted_edit = QLineEdit()
        self.add_browse_button(form_layout, "Path to folder_audio_converted:", self.folder_audio_converted_edit)
        
        self.folder_bg3sids_wiki_edit = QLineEdit()
        self.add_browse_button(form_layout, "Path to folder_bg3sids_wiki:", self.folder_bg3sids_wiki_edit)
        
        # Checkboxes for selecting operations
        self.convert_checkbox = QCheckBox("Convert sound files")
        self.decode_checkbox = QCheckBox("Decode banks")
        self.group_checkbox = QCheckBox("Group files by bank")
        self.rename_checkbox = QCheckBox("Rename files")
        
        layout.addWidget(self.convert_checkbox)
        layout.addWidget(self.decode_checkbox)
        layout.addWidget(self.group_checkbox)
        layout.addWidget(self.rename_checkbox)
        
        # Buttons for processing and downloading dependencies
        btn_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Processing")
        self.start_button.clicked.connect(self.start_processing)
        btn_layout.addWidget(self.start_button)
        
        self.download_button = QPushButton("Download Dependencies")
        self.download_button.clicked.connect(self.download_dependencies)
        btn_layout.addWidget(self.download_button)
        
        layout.addLayout(btn_layout)
        
        # Log area for progress messages
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Progress bar (indeterminate while processing)
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
        # Disable the start button and show progress bar
        self.start_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_text.clear()
        
        # Gather settings from user input
        settings = {
            "wwiser_pyz": self.wwiser_pyz_edit.text(),
            "folder_vgmstream": self.folder_vgmstream_edit.text(),
            "folder_unpacked_data": self.folder_unpacked_data_edit.text(),
            "folder_audio_converted": self.folder_audio_converted_edit.text(),
            "folder_bg3sids_wiki": self.folder_bg3sids_wiki_edit.text(),
            "should_convert": self.convert_checkbox.isChecked(),
            "should_decode_banks": self.decode_checkbox.isChecked(),
            "should_group": self.group_checkbox.isChecked(),
            "should_rename": self.rename_checkbox.isChecked(),
        }
        
        # Set up the worker and thread to run processing tasks
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
        # Disable the download button while downloading
        self.download_button.setEnabled(False)
        self.log_text.append("Starting dependency download...")
        
        # List of dependency URLs
        dependencies = [
            "https://github.com/bnnm/wwiser/releases/download/v20241210/wwiser.pyz",
            "https://github.com/bnnm/wwiser/releases/download/v20241210/wwnames.db3",
            "https://github.com/vgmstream/vgmstream-releases/releases/download/nightly/vgmstream-win64.zip",
            "https://github.com/ShinyHobo/BG3-Modders-Multitool/releases/download/v0.13.3/bg3-modders-multitool.zip",
        ]
        # Download folder is "dependencies" within the current working directory
        download_folder = os.path.join(os.getcwd(), "dependencies")
        
        # Set up download worker thread
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
        self.log_text.append("Dependency download complete.")
        self.download_button.setEnabled(True)

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
