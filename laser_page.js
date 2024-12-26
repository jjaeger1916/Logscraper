function connectSocket(serverUrl, laserId) {
    // Ensure the correct namespace is used in the connection
    const socket = io.connect(serverUrl, { path: '/socket.io', transports: ['websocket', 'polling'] }); // Add transport options to ensure connection stability

    socket.on('connect', function() {
        console.log(`Connected to server for ${laserId}`);
        socket.emit('join', { 'laser_id': laserId });
    });

    socket.on('connect_error', function(error) {
        console.error('Connection failed:', error); // Will help identify why the connection fails
    });

    socket.on('disconnect', function() {
        console.log(`Connection closed for ${laserId}`);
    });

    // Listen for `runtime_message` event
    socket.on('runtime_message', function(data) {
        console.log("Received full runtime:", data);

        // Ensure the runtime is for the correct laser
        if (data.laser === laserId && Array.isArray(data.runtime)) {
            resetRuntime();  // Clear the previous runtime data
            // Update the log with the entire runtime
            data.runtime.forEach(addOrUpdateLogEntry);  // Add each event in the runtime

            // Get the most recent entry in the runtime (last entry in the array)
            const mostRecentStatus = data.runtime[data.runtime.length - 1];
            // Update the laser box color with the most recent status
            updateLaserBox(mostRecentStatus);

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

    return socket;
}

// Function to update the visual status of the laser box based on the most recent status
function updateLaserBox(data) {
    const laserBox = document.getElementById(data.laser);
    if (laserBox) {
        laserBox.className = `box ${data.status}`;  // Update box color based on status
    } else {
        console.error(`No element found with ID: ${data.laser}`);
    }
}

// Function to reset the log table and part-specific data
function resetRuntime() {
    const logDataTable = document.getElementById('logDataTable').getElementsByTagName('tbody')[0];
    logDataTable.innerHTML = '';  // Clear all rows

    // Clear part file, tech data, and total part count display
    document.getElementById('partFile').innerText = '';
    document.getElementById('techData').innerText = '';
    document.getElementById('totalPartCount').innerText = '';
    document.getElementById('avgCuttingTime').innerText = '';
    document.getElementById('avgIdleTime').innerText = '';
}

// Function to add or update a log entry
function addOrUpdateLogEntry(data) {
    const logDataTable = document.getElementById('logDataTable').getElementsByTagName('tbody')[0];
    const status = data.status.charAt(0).toUpperCase() + data.status.slice(1);
    const startTime = data.start_time ? new Date(data.start_time).toLocaleString() : new Date().toLocaleString();
    const endTime = data.end_time !== 'Ongoing' ? new Date(data.end_time).toLocaleString() : 'Ongoing';
    const partCount = data.session_part_count || 0;
    const totalTime = data.total_time || 'N/A';
    const details = data.details || 'N/A'

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

    // Check if a row with the same status and start time already exists
    const existingRow = Array.from(logDataTable.rows).find(row => {
        return row.cells[0].innerText === status && row.cells[1].innerText === startTime;
    });

    if (existingRow) {
        // Update the existing row with the new end time and part count
        existingRow.cells[2].innerText = endTime;
        existingRow.cells[3].innerText = totalTime;
        existingRow.cells[4].innerText = partCount;
    } else {
        // Create a new row if it doesn't exist
        const row = logDataTable.insertRow(0);
        row.insertCell(0).innerHTML = status;
        row.insertCell(1).innerHTML = startTime;
        row.insertCell(2).innerHTML = endTime;
        row.insertCell(3).innerHTML = totalTime;
        row.insertCell(4).innerHTML = partCount;
        row.insertCell(5).innerHTML = details;
    }

    // Optionally, remove the "No data available yet" row if it exists
    const noDataRow = logDataTable.querySelector('tr td[colspan="5"]');
    if (noDataRow) {
        noDataRow.remove();
    }
}