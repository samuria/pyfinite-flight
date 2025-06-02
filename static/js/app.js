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
                socket.emit("set_aircraft_state", { state_name: "aircraft/0/systems/flaps/state", value: 1 });
                setFlapsStatus.textContent = 'Setting flaps...';
            } else {
                setFlapsStatus.textContent = 'Not connected.';
            }
        });
    }
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


// Make connectToDevice available globally
window.connectToDevice = connectToDevice;
window.closeStatesModal = closeStatesModal;