// Jenkins Dashboard JavaScript

// Configuration
const REFRESH_INTERVAL = 30; // seconds
let autoRefreshEnabled = true;
let refreshTimer = null;

// DOM Elements
const elements = {
  timestamp: document.getElementById("timestamp"),
  errorAlert: document.getElementById("error-alert"),
  errorMessage: document.getElementById("error-message"),
  runningBuilds: document.getElementById("running-builds"),
  noRunning: document.getElementById("no-running"),
  runningCount: document.getElementById("running-count"),
  queuedBuilds: document.getElementById("queued-builds"),
  noQueued: document.getElementById("no-queued"),
  queueCount: document.getElementById("queue-count"),
  queueTable: document.getElementById("queue-table"),
  refreshBtn: document.getElementById("refresh-btn"),
  autoRefreshToggle: document.getElementById("autoRefreshToggle"),
};

// Initialize the dashboard
function initDashboard() {
  console.log("Initializing dashboard...");

  // Check if all required elements exist
  for (const [key, element] of Object.entries(elements)) {
    if (!element) {
      console.error(`Missing element: ${key}`);
    }
  }

  // Add event listeners
  elements.refreshBtn.addEventListener("click", fetchDashboardData);
  elements.autoRefreshToggle.addEventListener("change", toggleAutoRefresh);

  // Initial data fetch
  fetchDashboardData();

  // Set up auto-refresh
  startAutoRefresh();

  console.log("Dashboard initialized");
}

// Toggle auto-refresh
function toggleAutoRefresh() {
  autoRefreshEnabled = elements.autoRefreshToggle.checked;
  console.log(`Auto-refresh ${autoRefreshEnabled ? "enabled" : "disabled"}`);

  if (autoRefreshEnabled) {
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }
}

// Start auto-refresh timer
function startAutoRefresh() {
  console.log("Starting auto-refresh timer");

  if (refreshTimer) {
    clearInterval(refreshTimer);
  }

  if (autoRefreshEnabled) {
    // Use arrow function to preserve context
    refreshTimer = setInterval(() => {
      console.log("Auto-refresh triggered");
      fetchDashboardData();
    }, REFRESH_INTERVAL * 1000);

    console.log(`Auto-refresh will occur every ${REFRESH_INTERVAL} seconds`);
  }
}

// Stop auto-refresh timer
function stopAutoRefresh() {
  console.log("Stopping auto-refresh timer");

  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

// Fetch dashboard data from API
function fetchDashboardData() {
  console.log("Fetching dashboard data...");

  // Show loading state
  elements.refreshBtn.disabled = true;
  elements.refreshBtn.innerHTML =
    '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Refreshing...';

  // Add cache-busting query parameter
  const timestamp = new Date().getTime();
  const url = `/api/dashboard?_=${timestamp}`;

  console.log(`Requesting from: ${url}`);

  fetch(url, {
    // Add cache control options
    cache: "no-store",
    headers: {
      Pragma: "no-cache",
      "Cache-Control": "no-cache",
    },
  })
    .then((response) => {
      console.log("API response status:", response.status);
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      console.log("Dashboard data received:", data);

      // Check if data has expected structure
      if (!data) {
        console.error("No data received from API");
        throw new Error("No data received from API");
      }

      console.log("Running builds:", data.running_builds);
      console.log("Queued builds:", data.queued_builds);

      updateDashboard(data);

      // Reset button state
      elements.refreshBtn.disabled = false;
      elements.refreshBtn.innerHTML =
        '<i class="bi bi-arrow-clockwise"></i> Refresh Now';
    })
    .catch((error) => {
      console.error("Error fetching dashboard data:", error);

      // Show error message
      elements.errorMessage.textContent = error.message;
      elements.errorAlert.style.display = "block";

      // Reset button state
      elements.refreshBtn.disabled = false;
      elements.refreshBtn.innerHTML =
        '<i class="bi bi-arrow-clockwise"></i> Refresh Now';
    });
}

// Update dashboard with new data
function updateDashboard(data) {
  console.log("Updating dashboard with new data");

  // Update timestamp
  elements.timestamp.textContent = data.timestamp;

  // Handle error if present
  if (data.error) {
    console.error("Dashboard error:", data.error);
    elements.errorMessage.textContent = data.error;
    elements.errorAlert.style.display = "block";
  } else {
    elements.errorAlert.style.display = "none";
  }

  // Update running builds
  updateRunningBuilds(data.running_builds);

  // Update queued builds
  updateQueuedBuilds(data.queued_builds);

  console.log("Dashboard update complete");
}

// Update running builds section
function updateRunningBuilds(builds) {
  console.log(`Updating running builds UI... (${builds.length} builds)`);

  // Update count badge
  elements.runningCount.textContent = builds.length;

  // Clear existing content
  elements.runningBuilds.innerHTML = "";

  // Show/hide empty state message
  if (builds.length === 0) {
    console.log("No running builds to display");
    elements.noRunning.style.display = "block";
    return;
  } else {
    elements.noRunning.style.display = "none";
  }

  // Create build cards
  builds.forEach((build, index) => {
    console.log(`Creating card for build ${index}:`, build);

    const card = document.createElement("div");
    card.className = "card build-card";

    // Determine progress bar color
    let progressClass = "bg-primary";
    if (build.progress >= 90) {
      progressClass = "bg-success";
    } else if (build.progress >= 75) {
      progressClass = "bg-info";
    } else if (build.progress <= 10) {
      progressClass = "bg-danger";
    }

    // Determine if build is overdue
    const isOverdue = build.remaining === "Overdue";
    const remainingClass = isOverdue ? "overdue" : "";

    // Build the card content
    card.innerHTML = `
        <div class="card-body">
            <div class="build-header">
                <h5 class="card-title">
                    <a href="${build.url}" target="_blank" class="build-link">
                        ${build.job_name || "Unknown Job"}
                    </a>
                </h5>
                <span class="badge bg-success">Running</span>
            </div>
            <p class="card-text">
                ${build.build_display || `#${build.build_number || "Unknown"}`}
            </p>
            <div class="build-info">
                <p class="card-text">
                    <small>
                        Estimated duration: ${
                          build.estimated_duration || "Unknown"
                        } |
                        <span class="${remainingClass}">Remaining: ${
      build.remaining || "Unknown"
    }</span>
                    </small>
                </p>
            </div>
            <div class="progress build-progress">
                <div class="progress-bar ${progressClass}" role="progressbar"
                     style="width: ${build.progress || 0}%;"
                     aria-valuenow="${
                       build.progress || 0
                     }" aria-valuemin="0" aria-valuemax="100">
                    ${build.progress || 0}%
                </div>
            </div>
        </div>
    `;

    elements.runningBuilds.appendChild(card);
  });

  console.log("Running builds UI updated");
}

// Update queued builds section
function updateQueuedBuilds(builds) {
  console.log(`Updating queued builds UI... (${builds.length} builds)`);

  // Update count badge
  elements.queueCount.textContent = builds.length;

  // Clear existing content
  elements.queuedBuilds.innerHTML = "";

  // Show/hide empty state message and table
  if (builds.length === 0) {
    console.log("No queued builds to display");
    elements.noQueued.style.display = "block";
    elements.queueTable.style.display = "none";
    return;
  } else {
    elements.noQueued.style.display = "none";
    elements.queueTable.style.display = "table";
  }

  // Create table rows
  builds.forEach((build, index) => {
    console.log(`Creating row for queued build ${index}:`, build);

    const row = document.createElement("tr");

    // Build the row content
    row.innerHTML = `
            <td>${build.job_name || "Unknown"}</td>
            <td>${build.waiting_time || "Unknown"}</td>
            <td>${build.why || "Unknown reason"}</td>
        `;

    elements.queuedBuilds.appendChild(row);
  });

  console.log("Queued builds UI updated");
}

// Initialize the dashboard when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM loaded, initializing dashboard");
  initDashboard();
});

// Handle page visibility changes to pause/resume auto-refresh
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    console.log("Page became visible, resuming auto-refresh");
    // Page is visible, fetch latest data and restart auto-refresh
    if (autoRefreshEnabled) {
      fetchDashboardData();
      startAutoRefresh();
    }
  } else {
    console.log("Page hidden, pausing auto-refresh");
    // Page is hidden, pause auto-refresh to save resources
    stopAutoRefresh();
  }
});

// Log that the script has loaded
console.log("Dashboard script loaded");
