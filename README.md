# Logscraper
The log scraper consists of the flask server, the machine scripts and the salesforce upload script.

The flask server is what hosts the local webpage for realtime updates for each laser using websockets. Each user who accesses the wepage is a client and each machine script acts as a client. Messages are determined from the machine script, sent tot he flask server then sent to any connected clients on the webpage. This webpage only exists inside the network.

The machine script attempts to read the log file over the network and if it fails it will retry once a min 5 times before stopping and trying again from the beginning. 

As the laser runs it is updating a system log file. The mahcine script batch reads this log file at 100 lines at a time and looking for key phrases in the lines of the log.

    def check_status_change(self, line):
        #Check the log line to determine if the machine status has changed.
        if "|Info|ACS Controller|Downloading Part Program" in line:
            return "Setup"
        elif "|Info|Button Pressed|Cycle Start" in line or "Validating full cutting area" in line:
            return "Cutting"
        elif "|Info|Process State|Total processing time" in line:
            return "Idle"
        return None  # If no recognized status is found, return None

This is what determines the status of the machine. Setup, cutting or idle. 

Other things line error codes, shift identification, part counting act are done continuosly.

Entering a status of "setup" starts a "Runtime" each runtime consists of "Runtime Lines" that hold the details during a status. 
When the status returns to setup after first inisializing a runtime we finalize the current runtime, export a JSON file with the runtime and lines, overwriting what was there before if a file already exists and that is when the uploadtoSF script comes in.

The UploadtoSF script monitors the JSON files and waits for a modification/update to happen. Once it finds a file that was updated to then upload the runtime data into HOS. 
