/**
 * Task management functions for the project management system
 */

/**
 * Edit a task by fetching its details and populating the edit form
 * @param {string} taskId - The ID of the task to edit
 */
function editTask(taskId) {
    // Redirect to the edit task page
    window.location.href = `/task/${taskId}/edit`;
}

/**
 * Delete a task after confirmation
 * @param {string} taskId - The ID of the task to delete
 */
function deleteTask(taskId) {
    if (confirm('Are you sure you want to delete this task?')) {
        fetch(`/task/${taskId}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to delete task');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error deleting task: ' + (data.message || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error deleting task. Please try again.');
        });
    }
}

// Initialize tooltips for skill match progress bars
document.addEventListener('DOMContentLoaded', function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});