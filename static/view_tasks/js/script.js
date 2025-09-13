async function fetchTasks() {
  try {
    const res = await fetch("/api/task/list");
    const data = await res.json();
    const container = document.getElementById("task-list");
    container.innerHTML = "";

    const tasks = data.message;
    const ids = Object.keys(tasks);

    if (ids.length === 0) {
      container.innerHTML = "<p>No active tasks.</p>";
      return;
    }

    ids.reverse().forEach(id => {
      const task = tasks[id];
      const div = document.createElement("div");
      div.className = "task-card";
      div.innerHTML = `

        <div class="task-id">Task ID: ${id}</div>

        <div class="task-field">
          <span class="task-label">File:</span>
          <span class="task-value boolean">${task.proof}</span>
        </div>

        <div class="task-field">
          <span class="task-label">Type:</span>
          <span class="task-value">${task.type}</span>
        </div>

        <div class="task-field">
          <span class="task-label">Status:</span>
          <span class="task-value boolean">${task.status}</span>
        </div>

        <div class="task-field">
          <span class="task-label">User-ID:</span>
          <span class="task-value">${task.user}</span>
        </div>

        <div class="task-field">
          <span class="task-label">Submiting:</span>
          <span class="task-value boolean">${task.submiting}</span>
        </div>

        <div class="message-text">${task.message}</div>
      `;
      container.appendChild(div);
    });
  } catch (err) {
    console.error("Error fetching tasks:", err);
  }
}

fetchTasks();
setInterval(fetchTasks, 5000);
