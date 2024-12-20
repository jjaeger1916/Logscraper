import socketio
import os
import time as time_module
from datetime import datetime, timedelta, timezone, time
import re
import asyncio
import json

class LaserLogMonitor:
    def __init__(self, laser_id, equipment_name, filename, server_url):
        self.laser_id = laser_id
        self.equipment_name = equipment_name
        self.filename = filename
        self.server_url = server_url
        self.current_status = "unknown"  # Track the current status to detect changes
        self.start_time = None  # Track the start time of the current status
        self.part_count = 0  # Initialize part count for the runtime
        self.session_part_count = 0  # Initialize part count for the current cutting session
        self.current_runtime = []  # Store all data for the current runtime (runtime lines)
        self.current_alarms = []  # Store any alarms detected in the current status
        self.sio = socketio.AsyncClient()
        self.total_cutting_duration = timedelta()  # Track total cutting duration
        self.total_idle_duration = timedelta()     # Track total idle duration
        self.cutting_count = 0                     # Count occurrences of cutting
        self.idle_count = 0 
        self.current_shift_type = None  # Keep track of the current shift type

        self.sio.on('connect', handler=self.on_connect)
        self.sio.on('disconnect', handler=self.on_disconnect)

        self.part_file_pattern = re.compile(r"\\([^\\]+\.nc)")
        self.tech_data_pattern = re.compile(r"Downloading TechData Recipe '([^']+)'")
        self.system_alarm_pattern = re.compile(r"\|Error\|System Alarm\|(.*)")

        # Track part file and tech data during setup phases
        self.current_phase = {
            "part_file": None,
            "tech_data": None
        }

    async def on_connect(self):
        print(f"Connected to server at {self.server_url}")

    async def on_disconnect(self):
        print("Disconnected from server")

    async def check_file_exists(self):
        """Check if the log file exists and is accessible."""
        retry_count = 0
        while retry_count < 5:
            if not os.path.exists(self.filename):
                retry_count += 1
                print(f"[{self.laser_id}] Log file not found, retrying in 60 seconds... ({retry_count}/5)")
                await asyncio.sleep(60)
            else:
                retry_count = 0  # Reset retry count if the file is found
                return True
        # Finalize runtime if file is not found after retries
        print(f"[{self.laser_id}] Log file not found after retries, finalizing runtime.")
        await self.finalize_current_runtime()

    async def read_log_lines(self, f, batch_size=50):
        """Read a line from the log file and handle file access appropriately."""
        lines = []
        for _ in range(batch_size):
            where = f.tell()
            line = f.readline()
            if not line:
                f.seek(where)  # Reset pointer if no new data
                break  # Exit the loop if no more lines
            lines.append(line)
        if not lines:
            await asyncio.sleep(1)  # Pause if no new lines are available
        return lines or []

    def get_shift_type(self, start_time):
        # Convert start_time string to datetime object
        start_time = start_time.replace('Z', '+00:00')
        dt = datetime.fromisoformat(start_time)
        local_dt = dt.astimezone()  # Convert to local time

        current_time = local_dt.time()

        if time(6, 0) <= current_time <= time(16, 29):
            return 'Day Shift'
        elif time(16, 30) <= current_time <= time(19, 59):
            return 'Shift Change'
        else:
            # Night shift from 8:00 PM to 5:59 AM
            if current_time >= time(20, 0) or current_time <= time(5, 59):
                return 'Night Shift'
            else:
                return 'Unknown Shift'

    def check_status_change(self, line):
        #Check the log line to determine if the machine status has changed.
        if "|Info|ACS Controller|Downloading Part Program" in line:
            return "Setup"
        elif "|Info|Button Pressed|Cycle Start" in line or "Validating full cutting area" in line:
            return "Cutting"
        elif "|Info|Process State|Total processing time" in line:
            return "Idle"
        return None  # If no recognized status is found, return None

    async def extract_part_file(self, line):
        """Extract the part file name during setup phase."""
        if "|Info|ACS Controller|Downloading Part Program" in line:
            part_file_match = self.part_file_pattern.search(line)
            if part_file_match:
                current_part_file = part_file_match.group(1)
                print(f"[{self.laser_id}] Part file detected: {current_part_file}")
                self.current_phase["part_file"] = current_part_file

    def extract_tech_data(self, line):
        # Extract tech data during setup
        if "Downloading TechData Recipe" in line:
            tech_data_match = self.tech_data_pattern.search(line)
            if tech_data_match:
                self.current_phase["tech_data"] = tech_data_match.group(1)
                print(f"Tech data detected: {self.current_phase['tech_data']}")

    def extract_system_alarm(self, line):
        """Extract system alarm details from a log line if available."""
        alarm_message_match = self.system_alarm_pattern.search(line)
        if alarm_message_match:
            system_alarm = alarm_message_match.group(1).strip()
            print(f"Alarm stored: {system_alarm}")
            self.current_alarms.append(system_alarm)

            # Add to the current runtime details
            if self.current_runtime[-1].get('details') is None:
                self.current_runtime[-1]['details'] = []
            self.current_runtime[-1]['details'].append(system_alarm)
            return system_alarm
        return None
    
    def calculate_duration(self, start_time, end_time):
        start_time = start_time.replace('Z', '+00:00')
        start = datetime.fromisoformat(start_time)
        if end_time != 'Ongoing':
            end_time = end_time.replace('Z', '+00:00')
            end = datetime.fromisoformat(end_time)
        else:
            end = datetime.utcnow()
        duration = end - start
        return duration

    def calculate_average_cutting_time(self):
        """Calculate the average cutting time."""
        if self.cutting_count > 0:
            return self.total_cutting_duration / self.cutting_count
        return timedelta()

    def calculate_average_idle_time(self):
        """Calculate the average idle time."""
        if self.idle_count > 0:
            return self.total_idle_duration / self.idle_count
        return timedelta()

    async def send_runtime(self):
        """Send the entire current runtime to the server."""
        avg_cutting_time = self.calculate_average_cutting_time()
        avg_idle_time = self.calculate_average_idle_time()

        await self.sio.emit('runtime_update', {
            'laser': self.laser_id,
            'runtime': self.current_runtime,
            'avg_cutting_time': str(avg_cutting_time),  # Convert to string for JSON serialization
            'avg_idle_time': str(avg_idle_time),         # Convert to string for JSON serialization     
        })

    async def add_runtime_line(self, new_status, start_time=None, end_time=None, session_part_count=0):
        """Add a runtime line, update the current runtime, and send the runtime."""
        current_time = datetime.now(timezone.utc).isoformat(timespec='seconds')
        
        # Finalize the previous runtime line if necessary
        if self.current_status != "unknown" and self.current_status != new_status:
            self.finalize_runtime_line()
            
        # Create a new runtime line for the new status
        self.start_time = start_time or datetime.now(timezone.utc).isoformat(timespec='seconds')
        shift_type = self.get_shift_type(self.start_time)
        new_runtime_line = {
            'laser': self.laser_id,
            'status': new_status,
            'start_time': self.start_time,
            'end_time': 'Ongoing',
            'total_time': 'N/A',
            'part_file': self.current_phase.get("part_file"),
            'tech_data': self.current_phase.get("tech_data"),
            'session_part_count': session_part_count or self.session_part_count,
            'total_part_count': self.part_count,
            'details': None,  # Details will be added as they occur
            'shift_type': shift_type
        }
        self.current_runtime.append(new_runtime_line)

        # Update the current status
        self.current_status = new_status
        
        # Update the current shift type
        self.current_shift_type = shift_type

        # Send the updated runtime
        await self.send_runtime()

    def finalize_runtime_line(self, end_time=None):
        """Finalize the current runtime line by updating its end time and total duration."""
        if self.current_runtime and self.current_runtime[-1]['end_time'] == 'Ongoing':
            current_time = end_time or datetime.now(timezone.utc).isoformat(timespec='seconds')
            duration = self.calculate_duration(self.start_time, current_time)
            total_time = str(duration)
            # Track total durations and counts for idle and cutting
            if self.current_status == 'Cutting':
                self.total_cutting_duration += duration
                self.cutting_count += 1
            elif self.current_status == 'Idle':
                self.total_idle_duration += duration
                self.idle_count += 1
            self.part_count += self.session_part_count
            # Update the previous runtime line with an end time and part count
            self.current_runtime[-1].update({
                'end_time': current_time,
                'total_time': total_time,
                'session_part_count': self.session_part_count,
                'total_part_count': self.part_count,
                'details': self.current_alarms
            })
            self.current_alarms = []  # Clear alarms after sending
            self.session_part_count = 0

    async def finalize_current_runtime(self):
        """Finalize the current runtime line and output JSON file."""
        self.finalize_runtime_line()
        if self.current_runtime:
            avg_cutting_time = self.calculate_average_cutting_time()
            avg_idle_time = self.calculate_average_idle_time()
            runtime_data = {
                'laser': self.laser_id,
                'equipment_name': self.equipment_name,
                'part_file': self.current_phase.get("part_file"),
                'tech_data': self.current_phase.get("tech_data"),
                'total_cutting_duration': str(self.total_cutting_duration),
                'total_idle_duration': str(self.total_idle_duration),
                'cutting_count': self.cutting_count,
                'idle_count': self.idle_count,
                'avg_cutting_time': str(avg_cutting_time),
                'avg_idle_time': str(avg_idle_time),
                'total_part_count': self.part_count,
                'runtime': self.current_runtime,
            }
            with open(f'finalized_runtime_{self.laser_id}.json', 'w') as file:
                json.dump(runtime_data, file, indent=4, default=str)
            print(f"[{self.laser_id}] Finalized runtime and wrote to JSON file.")

    def start_new_runtime(self):
        """Start a new runtime by clearing previous data."""
        print(f"[{self.laser_id}] Starting new runtime.")
        self.current_runtime = []  # Clear previous runtime data
        self.current_alarms = []
        self.part_count = 0
        self.session_part_count = 0
        self.total_cutting_duration = timedelta(0)  # Reset cutting duration
        self.total_idle_duration = timedelta(0)     # Reset idle duration
        self.cutting_count = 0                      # Reset cutting count
        self.idle_count = 0                         # Reset idle count
        
    async def check_shift_change(self):
        """Check if the shift has changed and handle it."""
        current_time = datetime.now(timezone.utc).isoformat(timespec='seconds')
        current_shift_type = self.get_shift_type(current_time)
        if self.current_shift_type != current_shift_type:
            # Shift has changed
            # Finalize the current runtime line
            self.finalize_runtime_line(end_time=current_time)
            # Start a new runtime line with the same status but new shift type
            await self.add_runtime_line(self.current_status, start_time=current_time)

    async def monitor_log_file(self):
        """Continuously monitor the log file for status updates."""
        try:
            await self.check_file_exists()  # Ensure the file exists before starting

            with open(self.filename, 'r') as f:
                f.seek(0, 2)  # Move to the end of the file
                print(f"[{self.laser_id}] Started tailing the log file.")

                while True:
                    lines = await self.read_log_lines(f)
                    if not lines:
                        pass  # Skip the loop if no new lines are found
                    else:
                        for line in lines:
                            new_status = self.check_status_change(line)
                            
                            if new_status is not None and new_status != self.current_status:
                                if new_status == 'Setup':
                                    # Finalize the current runtime
                                    await self.finalize_current_runtime()
                                    # Start a new runtime
                                    self.start_new_runtime()
                                await self.add_runtime_line(new_status)
                                
                            self.extract_system_alarm(line)

                            # Perform setup-specific actions continuously if in setup
                            if self.current_status == "Setup":
                                await self.extract_part_file(line)
                                self.extract_tech_data(line)

                            # Handle part count increase during cutting
                            if self.current_status == "Cutting" and "Validating full cutting area" in line:
                                self.session_part_count += 1
                            
                    # Check for shift change
                    await self.check_shift_change()

                    await asyncio.sleep(1)

        except Exception as e:
            print(f"Error monitoring log {self.laser_id}: {e}")
            await asyncio.sleep(5)

    async def run(self):
        try:
            # Connect to the Flask-SocketIO server
            await self.sio.connect(self.server_url)

            # Continuously monitor the log file
            while True:
                await self.monitor_log_file()

        except KeyboardInterrupt:
            print("Interrupted by user, disconnecting...")
            self.sio.disconnect()

if __name__ == "__main__":
    laser_monitor = LaserLogMonitor(
        laser_id="ipgD",
        equipment_name="a3a1R000002CC6JQAW",
        filename=r'\\10.0.5.102\c$\IPG_LS\lcsystem_log.txt',
        server_url="http://10.0.4.11:1916"
    )
    asyncio.run(laser_monitor.run())
