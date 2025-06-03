// Infinite Flight Connect Web Interface
const socket = io();

// State management
let isConnected = false;
let currentDevices = [];
let currentConnection = null;

// DOM elements
const discoverBtn = document.getElementById('discoverBtn');
const disconnectBtn = document.getElementById('disconnectBtn');
const connectionStatus = document.getElementById('connectionStatus');
const discoveryStatus = document.getElementById('discoveryStatus');
const deviceList = document.getElementById('deviceList');
const discoverySection = document.querySelector('.discovery-section');
const connectionSection = document.getElementById('connectionSection');
const categoriesSection = document.getElementById('categoriesSection');
const locationSection = document.getElementById('locationSection');
const loadingOverlay = document.getElementById('loadingOverlay');
const loadingText = document.getElementById('loadingText');
const setFlapsBtn = document.getElementById('setFlapsBtn');
const setFlapsStatus = document.getElementById('setFlapsStatus');

// Flight Planner DOM elements
const flightPlannerSection = document.getElementById('flightPlannerSection');
const fpBearing = document.getElementById('fpBearing');
const fpDesiredTrack = document.getElementById('fpDesiredTrack');
const fpDistanceToDestination = document.getElementById('fpDistanceToDestination');
const fpDistanceToNext = document.getElementById('fpDistanceToNext');
const fpEtaToDestination = document.getElementById('fpEtaToDestination');
const fpEtaToNext = document.getElementById('fpEtaToNext');
const fpEteToDestination = document.getElementById('fpEteToDestination');
const fpEteToNext = document.getElementById('fpEteToNext');
const fpTrack = document.getElementById('fpTrack');
const fpWaypointName = document.getElementById('fpWaypointName');
const fpIcao = document.getElementById('fpIcao');
const fpNextWaypointLatitude = document.getElementById('fpNextWaypointLatitude');
const fpNextWaypointLongitude = document.getElementById('fpNextWaypointLongitude');
const fpXTrackErrorDistance = document.getElementById('fpXTrackErrorDistance');
const fpXTrackErrorAngle = document.getElementById('fpXTrackErrorAngle');
const fpTotalDistance = document.getElementById('fpTotalDistance');
const fpNextWaypointIndex = document.getElementById('fpNextWaypointIndex');
const fpWaypointsList = document.getElementById('fpWaypointsList');
// const getFlightPlanBtn = document.getElementById('getFlightPlanBtn'); // Manual button removed

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    setupSocketListeners();
    checkConnectionStatus();
});

// Event Listeners
function setupEventListeners() {
    discoverBtn.addEventListener('click', startDiscovery);
    disconnectBtn.addEventListener('click', disconnectFromDevice);
    if (setFlapsBtn) { // Check if the button exists (it's in a conditional section)
        setFlapsBtn.addEventListener('click', () => {
            if (isConnected) {
                console.log("Emitting set_aircraft_state for flaps");
                socket.emit("set_aircraft_state", { state_name: "aircraft/0/systems/flaps/state", value: 2 });
                setFlapsStatus.textContent = 'Setting flaps...';
            } else {
                setFlapsStatus.textContent = 'Not connected.';
            }
        });
    }
    // if (getFlightPlanBtn) { // Manual button removed
    //     getFlightPlanBtn.addEventListener('click', () => {
    //         if (isConnected) {
    //             console.log("Emitting get_flight_plan_manually");
    //             socket.emit("get_flight_plan_manually");
    //         } else {
    //             // Optionally, provide feedback if not connected
    //             alert("Not connected to Infinite Flight. Cannot fetch flight plan.");
    //         }
    //     });
    // }
}

// Socket Event Listeners
function setupSocketListeners() {
    socket.on('connected', (data) => {
        console.log('Connected to server:', data);
    });

    socket.on('discovery_started', (data) => {
        showDiscoveryStatus(data.message, 'scanning');
        deviceList.innerHTML = '';
        currentDevices = [];
    });

    socket.on('device_found', (device) => {
        console.log('Device found:', device);
        currentDevices.push(device);
        addDeviceToList(device);
    });

    socket.on('discovery_complete', (data) => {
        showDiscoveryStatus(data.message, 'complete');
        if (data.count === 0) {
            showNoDevicesFound();
        }
        hideLoading();
        discoverBtn.disabled = false;
    });

    socket.on('discovery_error', (data) => {
        showDiscoveryStatus(`Error: ${data.error}`, 'error');
        hideLoading();
        discoverBtn.disabled = false;
    });

    socket.on('connection_status', (data) => {
        handleConnectionStatus(data);
    });

    socket.on('manifest_loaded', (data) => {
        updateConnectionInfo(data);
        displayCategories(data.categories);
    });

    socket.on('category_states', (data) => {
        const statesLoading = document.getElementById('statesLoading');
        const statesList = document.getElementById('statesList');

        statesLoading.style.display = 'none';
        statesList.style.display = 'block';

        if (data.states && data.states.length > 0) {
            statesList.innerHTML = `
                <div style="margin-bottom: 16px; color: #8892b0;">
                    Showing ${data.count} states for ${data.category}
                </div>
            `;

            data.states.forEach(state => {
                const stateItem = document.createElement('div');
                stateItem.className = 'state-item';

                const valueClass = state.value === 'N/A' ? 'na' : '';

                stateItem.innerHTML = `
                    <div class="state-name">${state.displayName}</div>
                    <div class="state-type">${state.type}</div>
                    <div class="state-value ${valueClass}">${state.value}</div>
                `;

                statesList.appendChild(stateItem);
            });
        } else {
            statesList.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #8892b0;">
                    No states found for this category
                </div>
            `;
        }
    });

    socket.on('category_states_error', (data) => {
        const statesLoading = document.getElementById('statesLoading');
        const statesList = document.getElementById('statesList');

        statesLoading.style.display = 'none';
        statesList.style.display = 'block';
        statesList.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #ff4444;">
                Error loading states: ${data.error}
            </div>
        `;
    });

    socket.on('location_update', (data) => {
        updateLocationDisplay(data);
    });

    socket.on('set_state_response', (data) => {
        console.log('Set state response:', data);
        if (setFlapsStatus) {
            if (data.success) {
                setFlapsStatus.textContent = `State ${data.state_name} set to ${data.value}.`;
            } else {
                setFlapsStatus.textContent = `Error setting state: ${data.error}`;
            }
            // Clear status after a few seconds
            setTimeout(() => {
                setFlapsStatus.textContent = '';
            }, 5000);
        }
    });

    socket.on('flight_plan_update', (data) => {
        updateFlightPlanDisplay(data);
    });
}

// Discovery Functions
function startDiscovery() {
    // The overlay is removed; status is shown by showDiscoveryStatus via discovery_started event
    discoverBtn.disabled = true;
    socket.emit('start_discovery');
    // The hideLoading() and discoverBtn.disabled = false will be handled
    // by discovery_complete or discovery_error events (though hideLoading is less critical now for this flow).
}

function showDiscoveryStatus(message, type = 'info') {
    discoveryStatus.textContent = message;
    discoveryStatus.className = `discovery-status ${type}`;
}

function addDeviceToList(device) {
    const deviceCard = createDeviceCard(device);
    deviceList.appendChild(deviceCard);
}

function createDeviceCard(device) {
    const card = document.createElement('div');
    card.className = 'device-card';

    const stateClass = device.state.toLowerCase().replace(' ', '-');

    card.innerHTML = `
        <div class="device-header">
            <div class="device-name">${device.deviceName}</div>
            <div class="device-state ${stateClass}">${device.state}</div>
        </div>
        <div class="device-info">
            <div class="device-info-item">
                <label>IP Address:</label>
                <span>${device.preferredIp}</span>
            </div>
            <div class="device-info-item">
                <label>Port:</label>
                <span>${device.port}</span>
            </div>
            <div class="device-info-item">
                <label>Version:</label>
                <span>${device.version}</span>
            </div>
        </div>
        <button class="btn btn-primary connect-btn" onclick="connectToDevice('${device.preferredIp}', ${device.port})">
            <span class="btn-icon">🔌</span>
            Connect
        </button>
    `;

    return card;
}

function showNoDevicesFound() {
    deviceList.innerHTML = `
        <div style="text-align: center; padding: 40px; color: #8892b0;">
            <p>No devices found</p>
            <p style="margin-top: 10px; font-size: 0.9rem;">
                Make sure Infinite Flight is running with Connect API enabled
                and both devices are on the same network.
            </p>
        </div>
    `;
}

// Connection Functions
function connectToDevice(host, port) {
    showLoading(`Connecting to ${host}:${port}...`);
    const device = currentDevices.find(d => d.preferredIp === host && d.port === port);
    if (device) {
        currentConnection = { host, port, aircraft: device.aircraft, livery: device.livery };
    } else {
        currentConnection = { host, port, aircraft: 'N/A', livery: 'N/A' }; // Fallback
    }
    socket.emit('connect_to_device', { host, port });
}

function disconnectFromDevice() {
    if (confirm('Are you sure you want to disconnect?')) {
        socket.emit('disconnect_from_device');
    }
}

function checkConnectionStatus() {
    socket.emit('get_connection_status');
}

function handleConnectionStatus(data) {
    hideLoading();

    const statusIndicator = connectionStatus.querySelector('.status-indicator');
    const statusText = connectionStatus.querySelector('.status-text');

    switch (data.status) {
        case 'connecting':
            statusIndicator.className = 'status-indicator connecting';
            statusText.textContent = 'Connecting...';
            break;

        case 'connected':
            isConnected = true;
            statusIndicator.className = 'status-indicator connected';
            statusText.textContent = 'Connected';
            connectionSection.style.display = 'block';
            locationSection.style.display = 'block';
            flightPlannerSection.style.display = 'block'; // Show flight planner
            discoverySection.style.display = 'none'; // Hide discovery section when connected

            if (data.host && data.port) {
                document.getElementById('connectedHost').textContent = data.host;
                document.getElementById('connectedPort').textContent = data.port;
            }

            if (currentConnection && currentConnection.aircraft !== undefined) {
                document.getElementById('aircraftValue').textContent = currentConnection.aircraft;
            }
            if (currentConnection && currentConnection.livery !== undefined) {
                document.getElementById('liveryValue').textContent = currentConnection.livery;
            }

            if (data.availableStates !== undefined) {
                document.getElementById('availableStates').textContent = data.availableStates;
            }

            showDiscoveryStatus(data.message || 'Connected to Infinite Flight', 'success');
            break;

        case 'disconnected':
            isConnected = false;
            statusIndicator.className = 'status-indicator disconnected';
            statusText.textContent = 'Not Connected';
            connectionSection.style.display = 'none';
            categoriesSection.style.display = 'none';
            locationSection.style.display = 'none';
            flightPlannerSection.style.display = 'none'; // Hide flight planner
            discoverySection.style.display = 'block'; // Show discovery section when disconnected
            showDiscoveryStatus(data.message || 'Disconnected', 'info');
            break;

        case 'failed':
        case 'error':
            isConnected = false;
            statusIndicator.className = 'status-indicator disconnected';
            statusText.textContent = 'Connection Failed';
            connectionSection.style.display = 'none';
            categoriesSection.style.display = 'none';
            locationSection.style.display = 'none';
            flightPlannerSection.style.display = 'none'; // Hide flight planner
            discoverySection.style.display = 'block'; // Show discovery section on connection failed/error
            showDiscoveryStatus(data.message || 'Connection error', 'error');
            break;
    }
}

function updateConnectionInfo(data) {
    if (data.stateCount !== undefined) {
        document.getElementById('availableStates').textContent = data.stateCount;
    }
}

function displayCategories(categories) {
    if (!categories || Object.keys(categories).length === 0) return;

    categoriesSection.style.display = 'block';
    const categoriesList = document.getElementById('categoriesList');
    categoriesList.innerHTML = '';

    for (const [category, count] of Object.entries(categories)) {
        const categoryItem = document.createElement('div');
        categoryItem.className = 'category-item';
        categoryItem.onclick = () => showCategoryStates(category);
        categoryItem.innerHTML = `
            <span class="category-name">${category}</span>
            <span class="category-count">${count} states</span>
        `;
        categoriesList.appendChild(categoryItem);
    }
}

// Category States Modal
function showCategoryStates(category) {
    const modal = document.getElementById('statesModal');
    const modalTitle = document.getElementById('modalTitle');
    const statesLoading = document.getElementById('statesLoading');
    const statesList = document.getElementById('statesList');

    // Show modal with loading state
    modal.style.display = 'flex';
    modalTitle.textContent = `${category.toUpperCase()} States`;
    statesLoading.style.display = 'flex';
    statesList.style.display = 'none';
    statesList.innerHTML = '';

    // Request states for this category
    socket.emit('get_category_states', { category });
}

function closeStatesModal() {
    const modal = document.getElementById('statesModal');
    modal.style.display = 'none';
}

// Close modal when clicking outside
document.getElementById('statesModal').addEventListener('click', (e) => {
    if (e.target.id === 'statesModal') {
        closeStatesModal();
    }
});

// Utility Functions
function showLoading(text = 'Loading...') {
    loadingText.textContent = text;
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

// Location Updates
function updateLocationDisplay(data) {
    // Update each location value
    if (data.latitude !== undefined) {
        document.getElementById('latitudeValue').textContent = data.latitude;
    }
    if (data.longitude !== undefined) {
        document.getElementById('longitudeValue').textContent = data.longitude;
    }
    if (data.altitude_msl !== undefined) {
        document.getElementById('altitudeMslValue').textContent = data.altitude_msl;
    }
    if (data.altitude_agl !== undefined) {
        document.getElementById('altitudeAglValue').textContent = data.altitude_agl;
    }
    if (data.heading !== undefined) {
        document.getElementById('headingValue').textContent = data.heading;
    }
    if (data.speed !== undefined) {
        document.getElementById('speedValue').textContent = data.speed;
    }

    // Flash the update indicator
    const updateDot = document.querySelector('.update-dot');
    updateDot.style.animation = 'none';
    setTimeout(() => {
        updateDot.style.animation = 'pulse 2s infinite';
    }, 10);
}

// Flight Plan Display
function updateFlightPlanDisplay(rawData) {
    let data;
    if (typeof rawData === 'string') {
        try {
            data = JSON.parse(rawData);
        } catch (e) {
            console.error("Error parsing flight plan JSON:", e);
            fpBearing.textContent = '-';
            fpDesiredTrack.textContent = '-';
            fpDistanceToDestination.textContent = '-';
            fpDistanceToNext.textContent = '-';
            fpEtaToDestination.textContent = '-';
            fpEtaToNext.textContent = '-';
            fpEteToDestination.textContent = '-';
            fpEteToNext.textContent = '-';
            fpTrack.textContent = '-';
            fpWaypointName.textContent = '-';
            fpIcao.textContent = '-';
            fpNextWaypointLatitude.textContent = '-';
            fpNextWaypointLongitude.textContent = '-';
            fpXTrackErrorDistance.textContent = '-';
            fpXTrackErrorAngle.textContent = '-';
            fpTotalDistance.textContent = '-';
            fpNextWaypointIndex.textContent = '-';
            fpWaypointsList.innerHTML = `<li style="color: #ff4444; font-weight: bold;">Error: Invalid flight plan data format.</li>`;
            if (flightPlannerSection.style.display === 'none' && isConnected) {
                flightPlannerSection.style.display = 'block';
            }
            return;
        }
    } else {
        data = rawData; // Assume it's already an object (e.g. if backend changes or for testing)
    }

    if (!data) {
        // Clear all fields if data is null or undefined after potential parsing
        fpBearing.textContent = '-';
        fpDesiredTrack.textContent = '-';
        fpDistanceToDestination.textContent = '-';
        fpDistanceToNext.textContent = '-';
        fpEtaToDestination.textContent = '-';
        fpEtaToNext.textContent = '-';
        fpEteToDestination.textContent = '-';
        fpEteToNext.textContent = '-';
        fpTrack.textContent = '-';
        fpWaypointName.textContent = '-';
        fpIcao.textContent = '-';
        fpNextWaypointLatitude.textContent = '-';
        fpNextWaypointLongitude.textContent = '-';
        fpXTrackErrorDistance.textContent = '-';
        fpXTrackErrorAngle.textContent = '-';
        fpTotalDistance.textContent = '-';
        fpNextWaypointIndex.textContent = '-';
        fpWaypointsList.innerHTML = '<li>Error: No data received.</li>';
        if (flightPlannerSection.style.display === 'none' && isConnected) {
            flightPlannerSection.style.display = 'block';
        }
        return;
    }

    // Check for an error message from the backend
    if (data.error) {
        console.error("Flight plan error:", data.error);
        // Clear all fields
        fpBearing.textContent = '-';
        fpDesiredTrack.textContent = '-';
        fpDistanceToDestination.textContent = '-';
        fpDistanceToNext.textContent = '-';
        fpEtaToDestination.textContent = '-';
        fpEtaToNext.textContent = '-';
        fpEteToDestination.textContent = '-';
        fpEteToNext.textContent = '-';
        fpTrack.textContent = '-';
        fpWaypointName.textContent = '-';
        fpIcao.textContent = '-';
        fpNextWaypointLatitude.textContent = '-';
        fpNextWaypointLongitude.textContent = '-';
        fpXTrackErrorDistance.textContent = '-';
        fpXTrackErrorAngle.textContent = '-';
        fpTotalDistance.textContent = '-';
        fpNextWaypointIndex.textContent = '-';
        // Display the error in the waypoints list area
        fpWaypointsList.innerHTML = `<li style="color: #ff4444; font-weight: bold;">Error: ${data.error}</li>`;
        // Ensure the section is visible to show the error
        if (flightPlannerSection.style.display === 'none' && isConnected) {
            flightPlannerSection.style.display = 'block';
        }
        return;
    }

    // Check if the data object is not a valid flight plan (e.g., empty object from backend)
    // by checking for a key field like 'bearing'.
    if (typeof data.bearing === 'undefined') {
        console.warn("Received flight plan data object without expected fields (e.g., bearing). Assuming no active flight plan.");
        // Clear all fields
        fpBearing.textContent = '-';
        fpDesiredTrack.textContent = '-';
        fpDistanceToDestination.textContent = '-';
        fpDistanceToNext.textContent = '-';
        fpEtaToDestination.textContent = '-';
        fpEtaToNext.textContent = '-';
        fpEteToDestination.textContent = '-';
        fpEteToNext.textContent = '-';
        fpTrack.textContent = '-';
        fpWaypointName.textContent = '-';
        fpIcao.textContent = '-';
        fpNextWaypointLatitude.textContent = '-';
        fpNextWaypointLongitude.textContent = '-';
        fpXTrackErrorDistance.textContent = '-';
        fpXTrackErrorAngle.textContent = '-';
        fpTotalDistance.textContent = '-';
        fpNextWaypointIndex.textContent = '-';
        fpWaypointsList.innerHTML = '<li>No active flight plan data found.</li>';
        // Ensure the section is visible to show this message
        if (flightPlannerSection.style.display === 'none' && isConnected) {
            flightPlannerSection.style.display = 'block';
        }
        return;
    }

    // If no error and data structure seems valid, proceed to populate the data
    fpBearing.textContent = data.bearing !== null ? data.bearing.toFixed(2) : '-';
    fpDesiredTrack.textContent = data.desiredTrack !== null ? data.desiredTrack.toFixed(2) : '-';
    fpDistanceToDestination.textContent = data.distanceToDestination !== null ? data.distanceToDestination.toFixed(2) + ' nm' : '-';
    fpDistanceToNext.textContent = data.distanceToNext !== null ? data.distanceToNext.toFixed(2) + ' nm' : '-';

    // ETA specific handling
    // If ETE is Infinity or NaN, or ETA is 0 or a very large number, display N/A for ETA.
    if (data.eteToDestination === "Infinity" || data.etaToDestination === 0 || (typeof data.etaToDestination === 'number' && data.etaToDestination > 10 ** 14)) {
        fpEtaToDestination.textContent = 'N/A';
    } else {
        fpEtaToDestination.textContent = data.etaToDestination ?? '-';
    }

    if (data.eteToNext === "NaN" || data.etaToNext === 0 || (typeof data.etaToNext === 'number' && data.etaToNext > 10 ** 14)) {
        fpEtaToNext.textContent = 'N/A';
    } else {
        fpEtaToNext.textContent = data.etaToNext ?? '-';
    }

    fpEteToDestination.textContent = data.eteToDestination ?? '-';
    fpEteToNext.textContent = data.eteToNext ?? '-';
    fpTrack.textContent = data.track !== null ? data.track.toFixed(2) : '-';
    fpWaypointName.textContent = data.waypointName ?? '-';
    fpIcao.textContent = data.icao ?? '-';
    fpNextWaypointLatitude.textContent = data.nextWaypointLatitude !== null ? data.nextWaypointLatitude.toFixed(5) : '-';
    fpNextWaypointLongitude.textContent = data.nextWaypointLongitude !== null ? data.nextWaypointLongitude.toFixed(5) : '-';
    fpXTrackErrorDistance.textContent = data.xTrackErrorDistance !== null ? data.xTrackErrorDistance.toFixed(2) + ' nm' : '-';
    fpXTrackErrorAngle.textContent = data.xTrackErrorAngle !== null ? (data.xTrackErrorAngle * 180 / Math.PI).toFixed(2) + '°' : '-'; // Convert radians to degrees
    fpTotalDistance.textContent = data.totalDistance !== null ? data.totalDistance.toFixed(2) + ' nm' : '-';
    fpNextWaypointIndex.textContent = data.nextWaypointIndex ?? '-';

    if (data.detailedInfo && data.detailedInfo.flightPlanItems) {
        fpWaypointsList.innerHTML = ''; // Clear previous waypoints
        data.detailedInfo.flightPlanItems.forEach(item => {
            const li = document.createElement('li');
            li.textContent = `${item.name} (Type: ${item.type})`;
            if (item.children && item.children.length > 0) {
                const ul = document.createElement('ul');
                item.children.forEach(child => {
                    const childLi = document.createElement('li');
                    childLi.textContent = `${child.identifier} (Alt: ${child.altitude === -1 ? 'N/A' : child.altitude + 'ft'})`;
                    ul.appendChild(childLi);
                });
                li.appendChild(ul);
            }
            fpWaypointsList.appendChild(li);
        });
    } else {
        fpWaypointsList.innerHTML = '<li>No detailed waypoint data available.</li>';
    }
    // Show the section if it was hidden and we have data
    if (flightPlannerSection.style.display === 'none' && isConnected) {
        flightPlannerSection.style.display = 'block';
    }
}


// Make connectToDevice available globally
window.connectToDevice = connectToDevice;
window.closeStatesModal = closeStatesModal;