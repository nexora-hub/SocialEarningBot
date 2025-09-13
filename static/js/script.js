// ===== Toast Notification =====
function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3000);
}

// ===== Chart.js Setup =====
const ctx = document.getElementById('sysChart').getContext('2d');
const labels = [];
const cpuData = [];
const ramData = [];

const sysChart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: labels,
    datasets: [
      {
        label: 'CPU %',
        data: cpuData,
        borderColor: '#00ffff',
        backgroundColor: 'rgba(0,255,255,0.1)',
        tension: 0.4,
        fill: true
      },
      {
        label: 'RAM %',
        data: ramData,
        borderColor: '#ff00ff',
        backgroundColor: 'rgba(255,0,255,0.1)',
        tension: 0.4,
        fill: true
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 500,
      easing: 'easeOutQuart'
    },
    scales: {
      x: {
        ticks: { color: '#ccc' },
        grid: { color: 'rgba(255,255,255,0.05)' }
      },
      y: {
        min: 0,
        max: 100,
        ticks: { color: '#ccc', callback: v => v + '%' },
        grid: { color: 'rgba(255,255,255,0.05)' }
      }
    },
    plugins: {
      legend: {
        labels: { color: '#ccc' }
      }
    }
  }
});


// ===== Start & Stop Bot =====
function startBot() {
  fetch('/start', { method: 'GET' })
    .then(r => r.json())
    .then(data => showToast(data.message || "Bot started"))
    .catch(err => showToast(`Error: ${err}`));
}

function stopBot() {
  fetch('/shutdown', { method: 'GET' })
    .then(r => r.json())
    .then(data => showToast(data.message || "Bot stopped"))
    .catch(err => showToast(`Error: ${err}`));
}

// ===== Reset Task =====
function resetTasks() {
  fetch('/api/task/reset', { method: 'GET' })
    .then(r => r.json())
    .then(data => showToast(data.message || "Tasks reset"))
    .catch(err => showToast(`Error: ${err}`));
}

function StreamChartMetrics() {
  const source = new EventSource("/api/chart-metrics");
  source.onmessage = (event) => {
     try {
       const data = JSON.parse(event.data);
       const now = new Date().toLocaleTimeString();

       labels.push(now);

       cpuData.push(data.cpu_percent);
       ramData.push(data.ram_percent);

       if (labels.length > 12) {
           labels.shift();
           cpuData.shift();
           ramData.shift();
       }

       sysChart.update();

     } catch (err) {
         showToast('Failed to fetch Chart Metrics');
       }
  };
}


function StreamTextContent() {
  const source = new EventSource("/api/context-metrics");
  source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        document.getElementById('tasks').textContent = data.tasks_completed;

        document.getElementById('uptime').textContent = data.uptime || "--:--:--";

        document.getElementById('cpuExtra').textContent = data.cpu_usage;

        document.getElementById('ramExtra').textContent = data.ram_usage;

        document.getElementById('botStatus').textContent = data.status.toUpperCase();

        document.getElementById('botStatus').className = `status ${data.status}`;

        document.getElementById('PostedTasks').textContent = data.posted_task || "---";

      } catch (err) {
          showToast('Failed to fetch Content Metrics');
        }
  };
}


function StreamActivePlatform() {
  const source = new EventSource("/api/active-platform");
  source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const platformsContainer = document.getElementById('platforms');

        // 🔥 Render active platforms
        platformsContainer.innerHTML = ""; // reset

        if (data.active_platform && Array.isArray(data.active_platform) && data.active_platform.length > 0) {
            data.active_platform.forEach(p => {
                 const badge = document.createElement("span");
                 badge.className = "platform-badge";
                 badge.textContent = p;
                 platformsContainer.appendChild(badge);
            });
        } else if (typeof data.active_platform === "string" && data.active_platform.trim() !== "") {
             // If backend ever returns a single string instead of array
             const badge = document.createElement("span");
             badge.className = "platform-badge";
             badge.textContent = data.active_platform;
             platformsContainer.appendChild(badge);
        } else {
             platformsContainer.textContent = "None";
             platformsContainer.style.color = "#FF00FF";
        }

      } catch (err) {
          showToast('Failed to fetch Content Metrics');
      }
  };
}


// ===== Fetch Metrics & Update UI =====
async function fetchMetrics() {
  try {
    const res = await fetch('/api/chart-metrics');
    const data = await res.json();

    const platformsContainer = document.getElementById('platforms');

    // 🔥 Render active platforms
    platformsContainer.innerHTML = ""; // reset

    if (data.active_platform && Array.isArray(data.active_platform) && data.active_platform.length > 0) {
      data.active_platform.forEach(p => {
        const badge = document.createElement("span");
        badge.className = "platform-badge";
        badge.textContent = p;
        platformsContainer.appendChild(badge);
      });
    } else if (typeof data.active_platform === "string" && data.active_platform.trim() !== "") {
      // If backend ever returns a single string instead of array
      const badge = document.createElement("span");
      badge.className = "platform-badge";
      badge.textContent = data.active_platform;
      platformsContainer.appendChild(badge);
    } else {
      platformsContainer.textContent = "None";
      platformsContainer.style.color = "#FF00FF";
    }

  } catch (err) {
    showToast(`Failed to fetch metrics: ${err}`);
  }
}


StreamTextContent();
StreamChartMetrics();
StreamActivePlatform();

// ===== Auto Refresh =====
// setInterval(fetchMetrics, 3000);
// fetchMetrics();

