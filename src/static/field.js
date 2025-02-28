// DOM Elements and state management
const form = document.getElementById('field-form');
const fileInput = document.getElementById('file-input');
const dropArea = document.querySelector('.file-drop-area');
const errorDiv = document.getElementById('error');
const ownershipResults = document.getElementById('ownership-results');
const advancedOptions = document.getElementById('advanced-options');
const leverageResults = document.getElementById('leverage-results');

// Theme toggle functionality
function setupThemeToggle() {
    document.querySelector('.theme-toggle').addEventListener('click', function() {
        document.body.classList.toggle('dark-mode');
        const icon = this.querySelector('i');
        icon.className = document.body.classList.contains('dark-mode') ? 'fas fa-sun' : 'fas fa-moon';
    });
}

// Radio button initialization
function initializeOptionButtons() {
    document.querySelectorAll('input[type="radio"]').forEach(radio => {
        if (radio.checked) {
            radio.closest('.option-button').classList.add('active');
        }
        
        radio.addEventListener('change', function() {
            const name = this.name;
            document.querySelectorAll(`input[name="${name}"]`).forEach(r => {
                r.closest('.option-button').classList.remove('active');
            });
            this.closest('.option-button').classList.add('active');
        });
    });
}

// File drop functionality
function setupFileDrop() {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    dropArea.addEventListener('click', () => fileInput.click());
    dropArea.addEventListener('drop', handleDrop, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function highlight() {
    dropArea.style.borderColor = 'var(--primary-color)';
    dropArea.style.backgroundColor = 'rgba(52, 152, 219, 0.05)';
}

function unhighlight() {
    dropArea.style.borderColor = '';
    dropArea.style.backgroundColor = '';
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    fileInput.files = files;
}

// Display ownership data in table
function displayOwnership(ownershipData) {
    const tbody = document.querySelector('#ownership-table tbody');
    tbody.innerHTML = '';

    // Sort by ownership percentage descending
    const sortedOwnership = Object.entries(ownershipData)
        .sort(([,a], [,b]) => b - a);

    sortedOwnership.forEach(([player, ownership]) => {
        const row = document.createElement('tr');
        
        const playerCell = document.createElement('td');
        playerCell.textContent = player;
        
        const ownershipCell = document.createElement('td');
        ownershipCell.className = 'percentage-cell';
        ownershipCell.textContent = `${ownership.toFixed(1)}%`;
        
        row.appendChild(playerCell);
        row.appendChild(ownershipCell);
        tbody.appendChild(row);
    });
}

// Form submission to process field
function setupFormSubmission() {
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const formData = new FormData();
        // Only require a file on the first submission
        const hasCachedFile = sessionStorage.getItem('hasProcessedFile') === 'true';

        if (!fileInput.files[0] && !hasCachedFile) {
            errorDiv.textContent = 'Please select a file';
            errorDiv.style.display = 'block';
            ownershipResults.style.display = 'none';
            advancedOptions.style.display = 'none';
            return;
        }

        if (fileInput.files[0]) {
            formData.append('file', fileInput.files[0]);
            // Reset the cached file flag when uploading a new file
            sessionStorage.removeItem('hasProcessedFile');
        }

        formData.append('sport', document.querySelector('input[name="sport"]:checked').value);
        formData.append('mode', document.querySelector('input[name="mode"]:checked').value.toLowerCase());

        try {
            const submitButton = form.querySelector('button');
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Processing...</span>';

            const response = await fetch('/analyze-field', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                // Mark that we have processed a file (for the session)
                sessionStorage.setItem('hasProcessedFile', 'true');

                displayOwnership(data.analysis);
                errorDiv.style.display = 'none';
                ownershipResults.style.display = 'block';
                
                // Show advanced options
                advancedOptions.style.display = 'block';
                
                // Scroll to results
                ownershipResults.scrollIntoView({ behavior: 'smooth' });
            } else {
                errorDiv.textContent = data.error;
                errorDiv.style.display = 'block';
                ownershipResults.style.display = 'none';
                advancedOptions.style.display = 'none';
            }
        } catch (error) {
            console.error("Error:", error);
            errorDiv.textContent = 'An error occurred while analyzing the file';
            errorDiv.style.display = 'block';
            ownershipResults.style.display = 'none';
            advancedOptions.style.display = 'none';
        } finally {
            const submitButton = form.querySelector('button');
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fas fa-chart-bar"></i><span>Process Field</span>';
        }
    });
}

// Handler functions for advanced options
function handleMaxEntriesRequest() {
    // Hide ownership results
    ownershipResults.style.display = 'none';

    // Hide text bars
    document.getElementById('contestant-input-div').style.display = 'none';
    document.getElementById('player-input-div').style.display = 'none';

    // Display loading
    this.disabled = true;
    this.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Processing...</span>';

    sendAnalysisRequest('/analyze-max-entries', {}, (data) => {
        const leverageContainer = document.getElementById('leverage-container');

        // Create max entries table
        let maxEntriesHTML = `
            <div class="results-table-wrapper">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>Contestant</th>
                            <th>Number of Entries</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        // Populate with data
        for (const item of data.entries) {
            maxEntriesHTML += `
                <tr>
                    <td>${item.contestant}</td>
                    <td class="count-cell">${item.entries}</td>
                </tr>
            `;
        }

        maxEntriesHTML += `
                    </tbody>
                </table>
            </div>
        `;

        leverageContainer.innerHTML = maxEntriesHTML;
        leverageResults.style.display = 'block';
        leverageResults.scrollIntoView({ behavior: 'smooth' });
        errorDiv.style.display = 'none';
    }, this);
}

function handleMMEOwnershipRequest() {
    // Hide ownership results
    ownershipResults.style.display = 'none';

    // Hide text bars
    document.getElementById('contestant-input-div').style.display = 'none';
    document.getElementById('player-input-div').style.display = 'block';

    // Display loading
    this.disabled = true;
    this.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Processing...</span>';

    const player = document.getElementById('player-input').value.trim();
    
    const requestData = {
        player: player
    };

    sendAnalysisRequest('/analyze-mme-ownership', requestData, (data) => {
        const leverageContainer = document.getElementById('leverage-container');

        // Create MME ownership table
        let mmeOwnershipHTML = `
            <div class="results-table-wrapper">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>Player</th>
                            <th>MME Ownership %</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        // Convert to array, sort by ownership percentage descending
        const sortedOwnership = Object.entries(data.mme_ownership)
            .sort(([, a], [, b]) => b - a);

        // Populate with data
        for (const [player, ownership] of sortedOwnership) {
            mmeOwnershipHTML += `
                <tr>
                    <td>${player}</td>
                    <td class="percentage-cell">${ownership.toFixed(1)}%</td>
                </tr>
            `;
        }

        mmeOwnershipHTML += `
                    </tbody>
                </table>
            </div>
        `;

        leverageContainer.innerHTML = mmeOwnershipHTML;
        leverageResults.style.display = 'block';
        leverageResults.scrollIntoView({ behavior: 'smooth' });
        errorDiv.style.display = 'none';
    }, this);
}

function handleDuplicatesRequest() {
    // Hide ownership results
    ownershipResults.style.display = 'none';

    // Hide text bars
    document.getElementById('contestant-input-div').style.display = 'none';
    document.getElementById('player-input-div').style.display = 'none';

    // Display loading
    this.disabled = true;
    this.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Processing...</span>';

    sendAnalysisRequest('/analyze-duplicates', {}, (data) => {
        const leverageContainer = document.getElementById('leverage-container');

        // Create duplicates table
        let duplicatesHTML = `
            <div class="results-table-wrapper">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>Lineup</th>
                            <th>Count</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        // Populate with data - account for the lineup being a string instead of an array
        for (const item of data.duplicates) {
            duplicatesHTML += `
                <tr>
                    <td>${item.lineup.replace(/-/g, ', ')}</td>
                    <td class="count-cell">${item.entries}</td>
                </tr>
            `;
        }

        duplicatesHTML += `
                    </tbody>
                </table>
            </div>
        `;

        leverageContainer.innerHTML = duplicatesHTML;
        leverageResults.style.display = 'block';
        leverageResults.scrollIntoView({ behavior: 'smooth' });
        errorDiv.style.display = 'none';
    }, this);
}

function handleLeverageRequest() {
    // Hide text bars
    document.getElementById('contestant-input-div').style.display = 'block';
    document.getElementById('player-input-div').style.display = 'block';

    const contestant = document.getElementById('contestant-input').value.trim();
    const player = document.getElementById('player-input').value.trim();

    if (!contestant) {
        errorDiv.textContent = 'Please enter a contestant name';
        errorDiv.style.display = 'block';
        leverageResults.style.display = 'none';
        return;
    }

    // Hide ownership results
    ownershipResults.style.display = 'none';

    // Display loading
    this.disabled = true;
    this.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Calculating...</span>';

    const requestData = {
        contestant: contestant,
        player: player
    };

    sendAnalysisRequest('/analyze-leverage', requestData, (data) => {
        const leverageContainer = document.getElementById('leverage-container');

        // Create leverage table
        let leverageHTML = `
            <div class="results-table-wrapper">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>Player</th>
                            <th>Leverage</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        // Populate with data using new array format
        for (const item of data.leverage) {
            // Determine if leverage is positive or negative for styling
            const leverageClass = item.leverage > 0 ? 'positive-leverage' : (item.leverage < 0 ? 'negative-leverage' : '');

            leverageHTML += `
                <tr>
                    <td>${item.player}</td>
                    <td class="percentage-cell ${leverageClass}">${item.leverage.toFixed(1)}%</td>
                </tr>
            `;
        }

        leverageHTML += `
                    </tbody>
                </table>
            </div>
        `;

        leverageContainer.innerHTML = leverageHTML;
        leverageResults.style.display = 'block';
        leverageResults.scrollIntoView({ behavior: 'smooth' });
        errorDiv.style.display = 'none';
    }, this);
}

function handleExportRequest() {
    try {
        // Hide text bars
        document.getElementById('contestant-input-div').style.display = 'none';
        document.getElementById('player-input-div').style.display = 'none';

        // Display loading
        this.disabled = true;
        this.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Exporting...</span>';

        // Client-side export using table data already available
        const table = document.getElementById('ownership-table');
        if (table) {
            let csv = [];
            csv.push(['Player', 'Ownership %']);

            const rows = table.querySelectorAll('tbody tr');
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                csv.push([cells[0].textContent, cells[1].textContent]);
            });

            const csvContent = 'data:text/csv;charset=utf-8,' +
                csv.map(row => row.join(',')).join('\n');

            const encodedUri = encodeURI(csvContent);
            const link = document.createElement('a');
            link.setAttribute('href', encodedUri);
            link.setAttribute('download', 'ownership_data.csv');
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    } catch (error) {
        console.error("Error:", error);
        errorDiv.textContent = 'Error exporting data';
        errorDiv.style.display = 'block';
    } finally {
        this.disabled = false;
        this.innerHTML = '<i class="fas fa-file-export"></i><span>Export Ownership</span>';
    }
}

function handleVisualizeRequest() {
    try {
        // Display loading
        this.disabled = true;
        this.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Visualizing...</span>';

        sendAnalysisRequest('/visualize-data', {}, (data) => {
            // Create a visualization container if it doesn't exist
            let visualContainer = document.getElementById('visualization-container');
            if (!visualContainer) {
                visualContainer = document.createElement('div');
                visualContainer.id = 'visualization-container';
                ownershipResults.appendChild(visualContainer);
            }

            // Create a simple bar chart using HTML/CSS
            let visualHTML = `
                <h3>Ownership Visualization</h3>
                <div class="chart-container" style="margin-top: 20px;">
            `;

            // Get top 15 players by ownership
            const topPlayers = Object.entries(data.visualization)
                .sort(([,a], [,b]) => b - a)
                .slice(0, 15);

            // Add bars for each player
            topPlayers.forEach(([player, ownership]) => {
                const widthPercent = Math.min(100, ownership * 2); // Scale for better visibility
                visualHTML += `
                    <div class="chart-bar" style="margin-bottom: 10px; display: flex; align-items: center;">
                        <div style="width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${player}</div>
                        <div style="flex-grow: 1;">
                            <div style="background-color: var(--primary-color); height: 20px; width: ${widthPercent}%; border-radius: 3px;"></div>
                        </div>
                        <div style="width: 50px; text-align: right;">${ownership.toFixed(1)}%</div>
                    </div>
                `;
            });

            visualHTML += `</div>`;
            visualContainer.innerHTML = visualHTML;

            // Scroll to the visualization
            visualContainer.scrollIntoView({ behavior: 'smooth' });
            errorDiv.style.display = 'none';
        }, this);
    } catch (error) {
        console.error("Error:", error);
        errorDiv.textContent = 'Error visualizing data';
        errorDiv.style.display = 'block';
    } finally {
        this.disabled = false;
        this.innerHTML = '<i class="fas fa-chart-pie"></i><span>Visualize Data</span>';
    }
}

// Helper function for sending analysis requests
async function sendAnalysisRequest(endpoint, additionalData, successCallback, buttonElement) {
    try {
        const formData = new FormData();
        
        // Only include the file if we don't have a cached version
        const hasCachedFile = sessionStorage.getItem('hasProcessedFile') === 'true';
        if (!hasCachedFile && fileInput.files[0]) {
            formData.append('file', fileInput.files[0]);
        }

        formData.append('sport', document.querySelector('input[name="sport"]:checked').value);
        formData.append('mode', document.querySelector('input[name="mode"]:checked').value.toLowerCase());
        
        // Add additional data from the parameter
        for (const [key, value] of Object.entries(additionalData)) {
            formData.append(key, value);
        }

        // Call API endpoint
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            successCallback(data);
        } else {
            console.error("API Error:", data.error);
            errorDiv.textContent = data.error;
            errorDiv.style.display = 'block';
            leverageResults.style.display = 'none';
        }
    } catch (error) {
        console.error("Error:", error);
        errorDiv.textContent = `Error making request to ${endpoint}`;
        errorDiv.style.display = 'block';
    } finally {
        // Reset button state
        if (buttonElement) {
            const originalHTML = {
                '/analyze-max-entries': '<i class="fas fa-chart-line"></i><span>Max Entries</span>',
                '/analyze-mme-ownership': '<i class="fas fa-percentage"></i><span>MME Ownership</span>',
                '/analyze-duplicates': '<i class="fas fa-clone"></i><span>Find Duplicates</span>',
                '/analyze-leverage': '<i class="fas fa-balance-scale"></i><span>Determine Leverage</span>',
                '/visualize-data': '<i class="fas fa-chart-pie"></i><span>Visualize Data</span>'
            };
            
            buttonElement.disabled = false;
            buttonElement.innerHTML = originalHTML[endpoint] || 'Submit';
        }
    }
}

// Initialize all event listeners when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Setup theme toggle
    setupThemeToggle();
    
    // Initialize option buttons (radio buttons)
    initializeOptionButtons();
    
    // Setup file drag and drop
    setupFileDrop();
    
    // Setup form submission
    setupFormSubmission();
    
    // Setup button handlers
    document.getElementById('max-entries-button').addEventListener('click', handleMaxEntriesRequest);
    document.getElementById('mme-ownership-button').addEventListener('click', handleMMEOwnershipRequest);
    document.getElementById('duplicates-button').addEventListener('click', handleDuplicatesRequest);
    document.getElementById('leverage-button').addEventListener('click', handleLeverageRequest);
    document.getElementById('export-button').addEventListener('click', handleExportRequest);
    document.getElementById('visualize-button').addEventListener('click', handleVisualizeRequest);
});