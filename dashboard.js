// Function to establish a Socket connection and handle events for the dashboard
function connectSocket(serverUrl) {
    // Ensure the URL includes the correct namespace
    const socket = io.connect(serverUrl, { path: '/socket.io', transports: ['websocket', 'polling'] });

    socket.on('connect', function() {
        console.log("Connected to server for the dashboard");
        socket.emit('join', { 'laser_id': null });
    });

    // Listen for `runtime_message` event
    socket.on('runtime_message', function(data) {
        console.log("Received runtime update:", data);

        // Check if data contains runtime information and process the most recent status
        if (Array.isArray(data.runtime) && data.runtime.length > 0) {
            const mostRecentStatus = data.runtime[data.runtime.length - 1];
            updateLaserBox(mostRecentStatus);  // Update the dashboard with laser status
        } else if (data.status) {
            // If data directly contains status, update the laser box immediately
            updateLaserBox(data);
        } else {
            console.error("Invalid runtime data:", data);
        }
    });

    socket.on('disconnect', function() {
        console.log("Connection closed for dashboard");
    });

    return socket;
}

// Function to update the laser box on the dashboard
function updateLaserBox(data) {
    // Find the laser box element based on the laser ID
    const laserBox = document.getElementById(data.laser);
    if (laserBox) {
        // Update the box color based on the status
        laserBox.className = `box ${data.status}`;
    } else {
        console.error(`No element found with ID: ${data.laser}`);
    }
}

// Initialize the socket connection
connectSocket(window.location.origin);

