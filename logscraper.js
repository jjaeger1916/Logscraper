// Function to establish a Socket connection and handle events
function connectSocket(serverUrl, laserId = null) {
    const socket = io.connect(serverUrl);

    socket.on('connect', function() {
        if (laserId) {
            console.log(`Connected to server for laser: ${laserId}`);
            socket.emit('join', { 'laser_id': laserId });
        } else {
            console.log("Connected to server for the dashboard");
            socket.emit('join_dashboard');
        }
    });

    // Listen for `runtime_update` event
    socket.on('runtime_update', function(data) {
        console.log("Received runtime update:", data);
    
        // Ensure the runtime is a valid array with at least one entry
        if (Array.isArray(data.runtime) && data.runtime.length > 0) {
            // If we are on an individual laser page, loop through the entire runtime array
            if (laserId) {
                if (data.laser === laserId) {
                    resetRuntime();  // Clear the current table before repopulating it
    
                    // Loop through all the runtime entries to populate the table
                    data.runtime.forEach(addOrUpdateLogEntry);  // Add each entry to the table
    
                    // Update the laser box based on the most recent status
                    const mostRecentStatus = data.runtime[data.runtime.length - 1];
                    updateLaserBox(mostRecentStatus);
                }
            }           
            else {
                // Handle updates for the dashboard
                const mostRecentStatus = data.runtime[data.runtime.length - 1];
                updateLaserBox(mostRecentStatus);
            }
            
            if (data.avg_cutting_time) {
                document.getElementById('avgCuttingTime').innerText = data.avg_cutting_time;
            }
            if (data.avg_idle_time) {
                document.getElementById('avgIdleTime').innerText = data.avg_idle_time;
            }

        } else {
            console.error("Invalid runtime data:", data);
        }
    });

    socket.on('disconnect', function() {
        console.log(`Connection closed for ${laserId ? laserId : "dashboard"}`);
    });

    return socket;
}

// Consolidated function to update the laser box (works for both individual and dashboard views)
function updateLaserBox(data) {
    const laserBox = document.getElementById(data.laser);
    if (laserBox) {
        laserBox.className = `box ${data.status}`;  // Update the box color based on the status
    } else {
        console.error(`No element found with ID: ${data.laser}`);
    }
}

function resetRuntime() {
    const logDataTable = document.getElementById('logDataTable').getElementsByTagName('tbody')[0];
    logDataTable.innerHTML = '';  // Clear all rows

    // Clear part file, tech data, and total part count display
    document.getElementById('partFile').innerText = '';
    document.getElementById('techData').innerText = '';
    document.getElementById('totalPartCount').innerText = '';
}


// Function to add or update a log entry (for individual laser pages)
function addOrUpdateLogEntry(data) {
    const logDataTable = document.getElementById('logDataTable').getElementsByTagName('tbody')[0];
    const status = data.status.charAt(0).toUpperCase() + data.status.slice(1);
    const startTime = data.start_time || new Date().toLocaleString();
    const endTime = data.end_time || 'Ongoing';
    const partCount = data.session_part_count || 0;
    const details = data.details || 'No details';

    // Update the part file and tech data display if available
    if (data.part_file) {
        document.getElementById('partFile').innerText = data.part_file;
    }
    if (data.tech_data) {
        document.getElementById('techData').innerText = data.tech_data;
    }
    if (data.total_part_count !== undefined) {
        document.getElementById('totalPartCount').innerText = data.total_part_count;
    }

    // Find the existing row or create a new one
    let existingRow = Array.from(logDataTable.rows).find(row => {
        return row.cells[0].innerText === status && row.cells[1].innerText === startTime;
    });

    if (existingRow) {
        // Update the existing row with the new end time and part count
        existingRow.cells[2].innerText = endTime;
        existingRow.cells[3].innerText = partCount;
        existingRow.cells[4].innerText = details;
    } else {
        // Create a new row if it doesn't exist
        const row = logDataTable.insertRow(0);
        row.insertCell(0).innerHTML = status;
        row.insertCell(1).innerHTML = startTime;
        row.insertCell(2).innerHTML = endTime;
        row.insertCell(3).innerHTML = partCount;
        row.insertCell(4).innerHTML = details;
    }

    // Optionally, remove the "No data available yet" row if it exists
    const noDataRow = logDataTable.querySelector('tr td[colspan="5"]');
    if (noDataRow) {
        noDataRow.remove();
    }
}
