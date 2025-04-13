
let selectedTaskId = null; // Store dragged task ID
let normalizedTasks = [];   // Initialize normalizedTasks array to store tasks data
let formIsOpen = false;

function toggleTaskForm(status) {
    const formElement = document.getElementById('addTaskForm');
    const toggleButton = document.querySelector('.add-task-ico i');
    const statusInput = document.getElementById('taskStatus');
    const engagementId = document.getElementById('engagementId').value;

    if (formIsOpen) {
        formElement.style.display = 'none';
        toggleButton.textContent = 'add_circle_outline';
    } else {
        formElement.style.display = 'block';
        toggleButton.textContent = 'remove_circle_outline';
        
        if (status) {
            statusInput.value = status;
        }

        // Fetch team members for the engagement for task.html
        fetch(`/get_engagement_team_taskhtml?engagement_id=${engagementId}`)
            .then(response => response.json())
            .then(data => {
                const assignedToSelect = document.getElementById('assignedTo');
                assignedToSelect.innerHTML = ''; // Clear existing options

                if (data.success) {
                    data.team_members.forEach(member => {
                        const option = document.createElement('option');
                        option.value = member._id;
                        option.textContent = `${member.name}`;
                        assignedToSelect.appendChild(option);
                    });
                } else {
                    alert('Failed to fetch engagement team: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error fetching engagement team:', error);
            });
    }

    formIsOpen = !formIsOpen;
}

function showNotification(message) {
    const notificationElement = document.getElementById('notification');
    const notificationText = notificationElement.querySelector('.notification-text');
    
    notificationText.textContent = message || 'Task added successfully!';  // Set custom message if provided

    // Add the 'show' class to make the notification visible
    notificationElement.classList.add('show');

    // Automatically close the notification after 3 seconds
    setTimeout(() => {
        closeNotification();
    }, 3000);
}

function closeAddTaskModal() {
    const formElement = document.getElementById('addTaskForm');
    formElement.style.display = 'none';  // Hide the form modal
}



function submitAddTask() {
    const descriptionElement = document.getElementById('taskDescription');
    const assignedToElement = document.getElementById('assignedTo');
    const dueDateElement = document.getElementById('dueDate');
    const timeEstimateElement = document.getElementById('timeEstimate');
    const priorityElement = document.querySelector('input[name="priority"]:checked');
    const difficultyElement = document.getElementById('difficulty');

    if (!descriptionElement || !assignedToElement || !dueDateElement || !timeEstimateElement || !priorityElement || !difficultyElement) {
        console.error('One or more required fields are missing.');
        return;
    }

    const description = descriptionElement.value;
    const engagementId = document.getElementById('engagementId').value;  // Retrieve engagement ID
    const assignedTo = assignedToElement.value;
    const dueDate = dueDateElement.value;
    const timeEstimate = timeEstimateElement.value;
    const priority = priorityElement.value;
    const difficulty = difficultyElement.value;

    const taskData = {
        description: description,
        engagementId: engagementId,
        assignedTo: assignedTo,
        dueDate: dueDate,
        timeEstimate: timeEstimate,  // In hours
        priority: priority,
        difficulty: difficulty
    };

    fetch('/add_task', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(taskData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Task added successfully!');
            closeAddTaskModal();
            location.reload();
        } else {
            showNotification('Failed to add task: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Failed to add task: ' + error.message);
    });
}


// Load the form's HTML content dynamically
function loadTaskForm(formId) {
  const formElement = document.getElementById(formId);
  formElement.innerHTML = `
    <form class="add-card-form-true" onsubmit="handleTaskSubmit(event, '${formId}')">
      <div class="add-card-form__header">
        <div class="form__low-pr">
          <input class="form__checkbox" type="radio" name="priority" value="low" alt="Low Priority" />
          <label class="form__label">Low Priority</label>
        </div>
        <div class="form__med-pr">
          <input class="form__checkbox" type="radio" name="priority" value="med" alt="Med Priority" />
          <label class="form__label">Med Priority</label>
        </div>
        <div class="form__high-pr">
          <input class="form__checkbox" type="radio" name="priority" value="high" alt="High Priority" />
          <label class="form__label">High Priority</label>
        </div>
      </div>
      <textarea class="add-card-form__main" placeholder="Write your task"></textarea>
      <div class="add-card-form__footer">
        <input class="form-add-btn" type="submit" value="Add Task" />
      </div>
    </form>
  `;
}
function populateCards(tasks) {
    const categories = {
        'To Start': document.getElementById('toStartCards'),
        'In Progress': document.getElementById('inProgressCards'),
        'Review': document.getElementById('reviewCards'),
        'Completed': document.getElementById('completeCards')
    };

    // Clear existing tasks in each category
    Object.keys(categories).forEach(category => {
        if (categories[category]) {
            categories[category].innerHTML = '';
        }
    });

    tasks.forEach(task => {
        const categoryElement = categories[task.status];
        if (!categoryElement) {
            console.warn(`Category element for status ${task.status} not found.`);
            return; // Skip tasks with unmatched statuses
        }

        // Create task card
        const taskCard = document.createElement('div');
        taskCard.className = `card ${task.priority}-color`;
        taskCard.draggable = true;
        taskCard.ondragstart = () => handleDragStart(task._id);

        // Attach modal onclicks for specific statuses
        if (task.status === 'In Progress') {
            taskCard.onclick = () => openTimesheetModal(task._id, task.description, task.engagement_name);
        } else if (task.status === 'Review') {
            taskCard.onclick = () => openReviewModal(task._id, task.description, task.user, task.timeEstimate, task.actualTime);
        }
        
        // Construct the path to avatar
        const avatarPath = task.avatar ? `/static/images/${task.avatar}` : '/static/images/default-avatar.jpg';
        // Populate task card content
        taskCard.innerHTML = `
            <div class="card__header">
                <div class="card__header-priority">${task.priority}</div>
                <div class="card__header-clear" onclick="deleteTask('${task._id}')">
                    <i class="material-icons">clear</i>
                </div>
            </div>
            <div class="card__text">${task.description}</div>
            <div class="card__meta">
                <p><i class="material-icons">event</i> Due Date: ${task.formatted_dueDate || 'No Due Date'}</p>
                <p><i class="material-icons">access_time</i> Estimated Time: ${task.timeEstimate || 0} hours</p>
            </div>
            <div class="card__menu">
                <div class="card__menu-left">
                    <div class="comments-wrapper">
                        <div class="comments-ico"><i class="material-icons">comment</i></div>
                        <div class="comments-num">${task.comments || 0}</div>
                    </div>
                    <div class="attach-wrapper">
                        <div class="attach-ico"><i class="material-icons">attach_file</i></div>
                        <div class="attach-num">${task.attach || 0}</div>
                    </div>
                </div>
                <div class="card__menu-right">
                    <div class="img-avatar">
                        <img src="${avatarPath}" alt="${task.user || 'Unknown'}" />
                    </div>
                </div>
            </div>
        `;

        // Append task to the correct category
        categoryElement.appendChild(taskCard);
    });
}

// Handle drag start
function handleDragStart(taskId) {
    console.log(`Drag started for task ID: ${taskId}`);
    selectedTaskId = taskId;
}

// Handle drag over
function handleDragOver(event) {
    event.preventDefault();
}

// Handle drop
function handleDrop(event, newStatus) {
    event.preventDefault();
    console.log(`Dropping task ${selectedTaskId} to status ${newStatus}`);

    if (!selectedTaskId) {
        console.error('No task selected for drop.');
        return;
    }

    const task = normalizedTasks.find(task => task._id === selectedTaskId);
    if (task) {
        if (task.status === 'Review' && newStatus === 'Completed') {
            // If moving from "Review" to "Completed", open the Review Modal
            openReviewModal(task._id, task.description, task.user, task.timeEstimate, task.actualTime);
        } else {
            // Otherwise, update the task status directly
            task.status = newStatus;
            populateCards(normalizedTasks);
            saveTaskStatusToBackend(selectedTaskId, newStatus);
        }
    } else {
        console.error('Task not found in normalizedTasks:', selectedTaskId);
    }
    selectedTaskId = null;
}

// Save updated task status to the backend
function saveTaskStatusToBackend(taskId, newStatus) {
    console.log(`Updating backend for task ${taskId} with new status: ${newStatus}`);
    fetch('/update_task_status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ taskId: taskId, newStatus: newStatus })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            alert('Failed to update task status.');
        }
    })
    .catch(error => {
        console.error('Error updating task status:', error);
    });
}

// Delete Task
function deleteTask(taskId) {
  normalizedTasks = normalizedTasks.filter(task => task.id !== taskId);  // Remove task
  populateCards(normalizedTasks);  // Refresh view
  deleteTaskFromBackend(taskId); // Send delete request to backend
}

// Send delete request to the backend
function deleteTaskFromBackend(taskId) {
  fetch('/delete_task', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      taskId: taskId,
    }),
  })
  .then(response => response.json())
  .then(data => {
    if (!data.success) {
      alert('Failed to delete task.');
    }
  })
  .catch(error => {
    console.error('Error deleting task:', error);
  });
}

// Toggle visibility of cards within a section
function toggleCardsVisibility(element) {
  const cardsElement = element.closest('.card-wrapper').querySelector('.cards');
  const icon = element.querySelector('i');

  if (cardsElement.style.display === 'none' || !cardsElement.style.display) {
    cardsElement.style.display = 'block';
    icon.textContent = 'expand_more';
  } else {
    cardsElement.style.display = 'none';
    icon.textContent = 'chevron_right';
  }
}

// Generate a random ID for new tasks
function newId() {
  return Math.round(Math.random() * 36 ** 8).toString(36);
}
window.onload = function() {
    const engagementId = JSON.parse(document.getElementById('engagement-id').textContent);

    // Fetch tasks from the backend
    fetch(`/get_tasks_for_dragging?engagement_id=${engagementId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                console.log('Fetched tasks:', data.tasks);
                normalizedTasks = data.tasks; // Assign fetched tasks to normalizedTasks
                populateCards(normalizedTasks);
            } else {
                console.error('Failed to load tasks:', data.message);
            }
        })
        .catch(error => {
            console.error('Error fetching tasks:', error);
        });
};


// timeshet submit function
function openTimesheetModal(taskId, taskName, engagementName) {
    // Populate modal with task details
    document.getElementById('engagementName').value = engagementName;
    document.getElementById('taskName').value = taskName;
    document.getElementById('taskId').value = taskId;

    // Show the modal
    document.getElementById('timesheetModal').style.display = 'block';
}

function closeTimesheetModal() {
    document.getElementById('timesheetModal').style.display = 'none';
}

function submitTimesheet() {
    const taskId = document.getElementById('taskId').value;
    const timeCharge = parseFloat(document.getElementById('timeCharge').value);
    const date = document.getElementById('date').value;

    // Submit timesheet data via POST request
    fetch('/submit_timesheet', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            taskId: taskId,
            hours: timeCharge,
            date: date
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Timesheet submitted successfully.');
            closeTimesheetModal();
            location.reload(); // Reload the page or update the UI
        } else {
            alert('Failed to submit timesheet: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to submit timesheet: ' + error.message);
    });
}


function openReviewModal(taskId, taskName, preparerName, timeEstimate, actualTime) {
    // Populate modal with task details
    document.getElementById('review_taskName').value = taskName;
    document.getElementById('review_preparerName').value = preparerName;
    document.getElementById('review_timeEstimate').value = timeEstimate + " hours";
    document.getElementById('review_actualTime').value = actualTime + " hours";
    document.getElementById('taskId').value = taskId;

    // Show the modal
    document.getElementById('reviewModal').style.display = 'block';
}




function closeReviewModal() {
    document.getElementById('reviewModal').style.display = 'none';
}

function submitReview() {
    const taskId = document.getElementById('taskId').value;
    const accuracyMark = document.getElementById('accuracyMark').value;

    // Submit the review data via POST request
    fetch('/review_task', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            taskId: taskId,
            accuracyMark: accuracyMark
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Review submitted successfully.');
            closeReviewModal();
            location.reload(); // Reload the page or update the UI
        } else {
            alert('Failed to submit review: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to submit review: ' + error.message);
    });
}
