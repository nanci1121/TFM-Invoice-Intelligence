import time
import os
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests
import json

# Configuration
WATCH_DIR = "/app/backend/uploads"
PROCESSED_DIR = "/app/backend/processed"
API_URL = "http://app:8000/upload"

class InvoiceHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        
        filename = os.path.basename(event.src_path)
        # Skip incomplete downloads or hidden files
        if filename.startswith('.') or filename.endswith('.crdownload'):
            return
            
        # Allowed extensions
        if not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.pdf']):
            return
            
        print(f"New file detected: {filename}")
        time.sleep(2) # Wait for file to be completely written
        
        try:
            with open(event.src_path, 'rb') as f:
                files = {'file': (filename, f)}
                response = requests.post(API_URL, files=files)
                if response.status_code == 200:
                    print(f"Successfully processed {filename}")
                    # Move to uploads once processed
                    os.makedirs(PROCESSED_DIR, exist_ok=True)
                    shutil.move(event.src_path, os.path.join(PROCESSED_DIR, filename))
                else:
                    print(f"Error processing {filename}: {response.text}")
        except Exception as e:
            print(f"Failed to process {filename}: {str(e)}")

if __name__ == "__main__":
    os.makedirs(WATCH_DIR, exist_ok=True)
    print(f"Starting watcher... Monitoring: {WATCH_DIR}")
    
    # Process existing files first
    handler = InvoiceHandler()
    files = os.listdir(WATCH_DIR)
    print(f"Found {len(files)} existing files in {WATCH_DIR}")
    
    for f in files:
        print(f"Checking existing file: {f}")
        if not f.endswith('.crdownload') and not f.startswith('.'):
            path = os.path.join(WATCH_DIR, f)
            class MockEvent:
                src_path = path
                is_directory = False
            handler.on_created(MockEvent())

    observer = Observer()
    observer.schedule(handler, WATCH_DIR, recursive=False)
    observer.start()
    print(f"Monitoring folder: {WATCH_DIR}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
