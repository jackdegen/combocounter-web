// DOM Elements
const form = document.getElementById('upload-form');
const fileInput = document.getElementById('file-input');
const fileInfo = document.querySelector('.file-info');
const errorDiv = document.getElementById('error');
const resultDiv = document.getElementById('result');
const sourceTypeInput = document.getElementById('source_type');
const tournamentInput = document.getElementById('tournament');
const percentsInput = document.getElementById('percents');
const isDkFileInput = document.getElementById('is_dk_file');
const themeToggle = document.querySelector('.theme-toggle');
const downloadButton = document.getElementById('download-results');


// Helper Functions
function showRecalculatingIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'recalculating-indicator';
    indicator.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Recalculating...';
    indicator.style.position = 'absolute';
    indicator.style.top = '10px';
    indicator.style.right = '10px';
    indicator.style.backgroundColor = 'var(--primary-color)';
    indicator.style.color = 'white';
    indicator.style.padding = '8px 12px';
    indicator.style.borderRadius = '4px';
    indicator.style.fontSize = '0.9rem';
    indicator.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
    indicator.style.zIndex = '10';

    // Remove any existing indicator
    const existingIndicator = document.getElementById('recalculating-indicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }

    resultDiv.appendChild(indicator);

    return indicator;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showError(message) {
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    resultDiv.style.display = 'none';

    // Scroll to error
    errorDiv.scrollIntoView({ behavior: 'smooth' });
}

function formatDate() {
    const today = new Date();

    // Convert to EST/EDT time
    const estOptions = { timeZone: 'America/New_York' };
    const estDateString = today.toLocaleString('en-US', estOptions);
    const estDate = new Date(estDateString);

    const dayOfWeek = estDate.getDay(); // 0 is Sunday, 1 is Monday, ..., 6 is Saturday
    const hours = estDate.getHours();

    // Logic for determining which date to return
    let targetDate = new Date(estDate);

    if (dayOfWeek === 0) {
        // Sunday - go back 2 days to Friday
        targetDate.setDate(estDate.getDate() - 2);
    } else if (dayOfWeek === 6) {
        // Saturday - go back 1 day to Friday
        targetDate.setDate(estDate.getDate() - 1);
    } else if (dayOfWeek === 1 && hours < 19) {
        // Monday before 7PM EST - go back 3 days to Friday
        targetDate.setDate(estDate.getDate() - 3);
    } else if (hours < 19) {
        // Weekday before 7PM EST - go back 1 day
        targetDate.setDate(estDate.getDate() - 1);
    }
    // else - it's after 7PM EST on a weekday, so keep the current date in targetDate

    // Format the date
    const mm = String(targetDate.getMonth() + 1).padStart(2, '0');
    const dd = String(targetDate.getDate()).padStart(2, '0');
    const yyyy = targetDate.getFullYear();
    return `${mm}-${dd}-${yyyy}`;
}

// Main Functions
function setupAutoRecalculation() {
    // Don't auto-recalculate if no results are displayed yet
    if (resultDiv.style.display !== 'block') return;

    // Get all form inputs that might trigger a recalculation
    const triggerElements = [
        ...document.querySelectorAll('input[type="radio"]'),
        document.getElementById('numResults'),
        document.getElementById('percents-toggle'),
        document.getElementById('dk-file-toggle')
    ];

    // Add event listeners to each element
    triggerElements.forEach(element => {
        element.addEventListener('change', () => {
            // Only auto-submit if results are already shown
            if (resultDiv.style.display === 'block') {
                handleFormSubmit(new Event('submit'));
            }
        });
    });
}

function handleFileSelect() {
    if (fileInput.files.length) {
        const file = fileInput.files[0];
        fileInfo.textContent = `Selected file: ${file.name} (${formatFileSize(file.size)})`;
    } else {
        fileInfo.textContent = '';
    }
}

async function loadAvailableFiles(tournament = null) {
    try {
        let url = '/available-files';
        if (tournament) {
            url += '/' + tournament;
        }

        const response = await fetch(url);
        const data = await response.json();

        const directorySelect = document.getElementById('directory-files');

        // Clear existing options except the first one
        directorySelect.options.length = 1;

        // Add new options
        if (data.files && data.files.length > 0) {
            data.files.forEach(file => {
                const option = document.createElement('option');
                option.value = file;
                option.textContent = file;
                if (tournament) {
                    option.dataset.tournament = tournament;
                }
                directorySelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error fetching available files:', error);
    }
}

function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');

    // Update icon
    const icon = themeToggle.querySelector('i');
    if (document.body.classList.contains('dark-mode')) {
        icon.className = 'fas fa-sun';
    } else {
        icon.className = 'fas fa-moon';
    }
}

async function handleFormSubmit(e) {
    e.preventDefault();

    const isAutoRecalculation = resultDiv.style.display === 'block';
    let recalculatingIndicator;

    if (isAutoRecalculation) {
        // Show lighter-weight indicator for auto-recalculation
        recalculatingIndicator = showRecalculatingIndicator();
    }

    const formData = new FormData(form);
    const sourceType = formData.get('source_type');

    // Validate file selection
    if (sourceType === 'upload' && !fileInput.files[0]) {
        showError('Please select a file to upload');
        return;
    } else if (sourceType === 'directory' && !formData.get('selected_file')) {
        showError('Please select a file from the directory');
        return;
    }

    try {
        // Show loading state for manual submissions
        if (!isAutoRecalculation) {
            const submitButton = form.querySelector('button[type="submit"]');
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Processing...</span>';
            submitButton.disabled = true;
        }

        const response = await fetch('/process', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        // Reset button state for manual submissions
        if (!isAutoRecalculation) {
            const submitButton = form.querySelector('button[type="submit"]');
            submitButton.innerHTML = '<i class="fas fa-chart-pie"></i><span>Analyze Data</span>';
            submitButton.disabled = false;
        } else if (recalculatingIndicator) {
            recalculatingIndicator.remove();
        }

        if (response.ok) {
            renderResults(data.result);
        } else {
            showError(data.error);
        }
    } catch (error) {
        // Reset UI states
        if (!isAutoRecalculation) {
            const submitButton = form.querySelector('button[type="submit"]');
            submitButton.innerHTML = '<i class="fas fa-chart-pie"></i><span>Analyze Data</span>';
            submitButton.disabled = false;
        } else if (recalculatingIndicator) {
            recalculatingIndicator.remove();
        }

        showError('An error occurred while processing the file.');
    }
}

function renderResults(resultData) {
    const tableContainer = document.getElementById('table-container');

    const table = document.createElement('table');
    table.className = 'results-table';

    const tbody = document.createElement('tbody');

    Object.entries(resultData).forEach(([key, value]) => {
        const row = document.createElement('tr');

        const th = document.createElement('th');
        th.textContent = key;
        row.appendChild(th);

        const td = document.createElement('td');
        if (typeof value === 'object' && value !== null) {
            td.textContent = JSON.stringify(value);
        } else {
            td.textContent = value;
        }
        row.appendChild(td);

        tbody.appendChild(row);
    });

    table.appendChild(tbody);

    tableContainer.innerHTML = '';
    tableContainer.appendChild(table);

    errorDiv.style.display = 'none';
    resultDiv.style.display = 'block';

    // Only scroll to results on initial submission, not on auto-recalculation
    const isAutoRecalculation = resultDiv.dataset.hasShownResults === 'true';
    if (!isAutoRecalculation) {
        resultDiv.scrollIntoView({ behavior: 'smooth' });
        resultDiv.dataset.hasShownResults = 'true';
    }

    // After results are displayed, set up auto-recalculation
    setupAutoRecalculation();
}

function downloadResults() {
    const table = document.querySelector('.results-table');
    if (!table) return;

    let csv = [];

    // Add headers
    csv.push(['Player/Combination', 'Count/Percentage']);

    // Add rows
    const rows = table.querySelectorAll('tr');
    rows.forEach(row => {
        const cells = row.querySelectorAll('th, td');
        const rowData = [];
        cells.forEach(cell => {
            rowData.push('"' + cell.textContent.replace(/"/g, '""') + '"');
        });
        csv.push(rowData.join(','));
    });

    // Create CSV content
    const csvContent = csv.join('\n');

    // Create download link
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'dfs_analysis_results.csv');
    link.style.display = 'none';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Setup Functions
function initializeOptionButtons() {
    // Set active class on radio button labels based on checked state
    document.querySelectorAll('input[type="radio"]').forEach(radio => {
        if (radio.checked) {
            radio.closest('.option-button').classList.add('active');
        }

        radio.addEventListener('change', function() {
            // Remove active class from all siblings
            const name = this.name;
            document.querySelectorAll(`input[name="${name}"]`).forEach(r => {
                r.closest('.option-button').classList.remove('active');
            });

            // Add active class to this option
            this.closest('.option-button').classList.add('active');
        });
    });
}

function setupEventListeners() {
    // Source type toggle
    document.querySelectorAll('.toggle-option[data-value]').forEach(option => {
        option.addEventListener('click', function() {
            const value = this.dataset.value;
            const parent = this.parentElement;

            // Get all sibling options
            const options = parent.querySelectorAll('.toggle-option');
            options.forEach(opt => opt.classList.remove('active'));

            // Activate this option
            this.classList.add('active');

            // If this is a source type toggle
            if (value === 'upload' || value === 'directory') {
                sourceTypeInput.value = value;
                document.getElementById('upload-section').classList.toggle('active', value === 'upload');
                document.getElementById('directory-section').classList.toggle('active', value === 'directory');
            }

            // If this is a tournament toggle
            if (value === 'genesis-invitational' || value === 'mexico-open' || value === 'cognizant-classic' || value === 'nba' || value === 'nfl') {
                tournamentInput.value = value;
                loadAvailableFiles(value);
            }
        });
    });

    // File input change
    fileInput.addEventListener('change', handleFileSelect);

    // Toggle switches
    document.getElementById('percents-toggle').addEventListener('change', function() {
        percentsInput.value = this.checked ? 'Yes' : 'No';
    });

    document.getElementById('dk-file-toggle').addEventListener('change', function() {
        isDkFileInput.value = this.checked ? 'Yes' : 'No';
    });

    // Theme toggle
    themeToggle.addEventListener('click', toggleDarkMode);

    // Form submission
    form.addEventListener('submit', handleFormSubmit);

    // Download results
    downloadButton.addEventListener('click', downloadResults);

    // File drop area
    const dropArea = document.querySelector('.file-drop-area');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    function highlight() {
        dropArea.classList.add('highlight');
    }

    function unhighlight() {
        dropArea.classList.remove('highlight');
    }

    dropArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length) {
            fileInput.files = files;
            handleFileSelect();
        }
    }
}

// Initialize the page
document.addEventListener('DOMContentLoaded', () => {
    // Get yesterday's date and update NBA option text
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const formattedDate = formatDate(yesterday);

    // Find the NBA toggle option and update its text
    const nbaOption = document.querySelector('.toggle-option[data-value="nba"] span');
    if (nbaOption) {
        nbaOption.textContent = `NBA (${formattedDate})`;
    }

    // Load files for the default tournament
    loadAvailableFiles(tournamentInput.value);

    // Set up event listeners
    setupEventListeners();

    // Initialize option buttons
    initializeOptionButtons();
});