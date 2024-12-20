import os
import json
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from simple_salesforce import Salesforce
from dotenv import load_dotenv

# Load environment variables from a .env file if you're using one
load_dotenv()

class JSONFileHandler(FileSystemEventHandler):
    def __init__(self, salesforce_instance):
        self.sf = salesforce_instance
        self.timers = {}

    # Capture both created and modified events for more reliability
    def on_modified(self, event):
        if event.src_path.endswith('.json'):
            self.handle_event(event)

    def on_created(self, event):
        if event.src_path.endswith('.json'):
            self.handle_event(event)

    # Centralized event handling for modifications/creations
    def handle_event(self, event):
        print(f"Detected change in file: {event.src_path}")
        # Cancel any existing timer for this file
        if event.src_path in self.timers:
            self.timers[event.src_path].cancel()
            print(f"Canceled existing timer for: {event.src_path}")

        # Start a new timer with debounce logic to avoid multiple triggers
        timer = threading.Timer(1.0, self.process_file, [event.src_path])
        self.timers[event.src_path] = timer
        timer.start()

    def process_file(self, file_path):
        print(f"Processing file: {file_path}")
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                print(f"Loaded data from file: {file_path}")
                self.upload_to_salesforce(data)
        except Exception as e:
            print(f"Error reading or processing file {file_path}: {e}")
        finally:
            # Remove the timer from the dictionary after processing
            if file_path in self.timers:
                del self.timers[file_path]
                print(f"Timer removed for: {file_path}")

    def upload_to_salesforce(self, data):
        try:
            print("Preparing to upload data to Salesforce...")
            # Map your JSON data to Salesforce object fields
            parent_record = {
                'Equipment__c': data.get('equipment_name'),
                'Part_File__c': data.get('part_file'),
                'Operational_Settings__c': data.get('tech_data'),
                'Total_Running_Time__c': data.get('total_cutting_duration'),
                'Total_Idle_Time__c': data.get('total_idle_duration'),
                'Run_Count__c': data.get('cutting_count'),
                'Idle_Count__c': data.get('idle_count'),
                'Avg_Run_Time__c': data.get('avg_cutting_time'),
                'Avg_Idle_Time__c': data.get('avg_idle_time'),
                'Total_Parts__c': data.get('total_part_count')
            }

            # Create parent record in Salesforce
            print(f"Uploading parent record: {parent_record}")
            parent_result = self.sf.Runtime__c.create(parent_record)
            parent_id = parent_result.get('id')
            print(f"Parent record created with ID: {parent_id}")

            # Upload runtime lines as child records
            for runtime_line in data.get('runtime', []):
                child_record = {
                    'Runtime__c': parent_id,  # Lookup to parent record
                    'Status__c': runtime_line.get('status'),
                    'Start_Time__c': runtime_line.get('start_time'),
                    'End_Time__c': runtime_line.get('end_time'),
                    'Part_File__c': runtime_line.get('part_file'),
                    'Operational_Settings__c': runtime_line.get('tech_data'),
                    'Part_Count__c': runtime_line.get('session_part_count'),
                    'Details__c': json.dumps(runtime_line.get('details')),
                    'Shift_Type__C': runtime_line.get('shift_type')
                }
                print(f"Uploading child record: {child_record}")
                self.sf.Runtime_Line__c.create(child_record)
                print("Child record uploaded successfully")
        except Exception as e:
            print(f"Error uploading to Salesforce: {e}")

def main():
    print("Starting Salesforce uploader...")
    # Initialize Salesforce connection
    sf = Salesforce(
        username=os.getenv('SF_USERNAME'),
        password=os.getenv('SF_PASSWORD'),
        security_token=os.getenv('SF_SECURITY_TOKEN'),
        domain=os.getenv('SF_DOMAIN', 'login')
    )
    print("Salesforce connection established.")

    event_handler = JSONFileHandler(sf)
    observer = Observer()
    directory_to_watch = 'C:\\logscraper\\Flask_server\\Machine scripts'
    observer.schedule(event_handler, path=directory_to_watch, recursive=False)
    observer.start()

    print(f"Watching directory: {directory_to_watch}")

    try:
        while True:
            pass  # Keep the script running
    except KeyboardInterrupt:
        observer.stop()
        print("Stopping observer...")
    observer.join()

if __name__ == '__main__':
    main()
