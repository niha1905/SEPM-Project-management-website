/**
 * AI Recommendations functionality for the project management system
 */

document.addEventListener('DOMContentLoaded', function() {
    // Budget Recommendations
    const budgetRecommendationBtn = document.getElementById('btn-budget');
    if (budgetRecommendationBtn) {
        budgetRecommendationBtn.addEventListener('click', function() {
            const projectSelect = document.getElementById('project-select-budget');
            const projectId = projectSelect ? projectSelect.value : '';
            
            if (!projectId) {
                alert('Please select a project first');
                return;
            }
            
            // Show loading state
            document.getElementById('results-title').textContent = 'Budget Recommendations';
            document.getElementById('results-content').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Generating budget recommendations...</p></div>';
            document.getElementById('recommendation-results').style.display = 'block';
            document.getElementById('generation-date').textContent = new Date().toLocaleString();
            
            // Get project data
            fetch('/api/budget/ai_recommendations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    project_id: projectId,
                    project_type: 'Software Development', // Default value
                    team_size: 5, // Default value
                    duration_months: 6, // Default value
                    complexity: 'Medium', // Default value
                    total_budget: 100000, // Default value
                    current_breakdown: '' // Default value
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to generate budget recommendations');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Format the recommendations
                    const recommendations = data.recommendations;
                    document.getElementById('results-content').innerHTML = `
                        <div class="mb-4">
                            <h5>Budget Recommendations</h5>
                            <div class="recommendations-text">
                                ${recommendations.replace(/\n/g, '<br>')}
                            </div>
                        </div>
                    `;
                } else {
                    document.getElementById('results-content').innerHTML = `
                        <div class="alert alert-danger">
                            Error generating recommendations: ${data.message || 'Unknown error'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('results-content').innerHTML = `
                    <div class="alert alert-danger">
                        Error generating recommendations. Please try again.
                    </div>
                `;
            });
        });
    }
    
    // Task Analysis
    const taskAnalysisBtn = document.getElementById('btn-task_analysis');
    if (taskAnalysisBtn) {
        taskAnalysisBtn.addEventListener('click', function() {
            const taskTitle = document.getElementById('task-title').value;
            const taskDescription = document.getElementById('task-description').value;
            
            if (!taskTitle || !taskDescription) {
                alert('Please enter both task title and description');
                return;
            }
            
            // Show loading state in modal
            document.getElementById('taskAnalysisResults').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Analyzing task...</p></div>';
            
            // Show the modal
            const taskModal = new bootstrap.Modal(document.getElementById('taskAnalysisModal'));
            taskModal.show();
            
            // Get task analysis
            fetch('/api/task_analysis', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    task_title: taskTitle,
                    task_description: taskDescription
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to analyze task');
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    // Format the analysis
                    const analysis = data.analysis;
                    document.getElementById('taskAnalysisResults').innerHTML = `
                        <div class="mb-4">
                            <h5>Task Analysis Results</h5>
                            <div class="analysis-text">
                                ${analysis.replace(/\n/g, '<br>')}
                            </div>
                        </div>
                    `;
                } else {
                    document.getElementById('taskAnalysisResults').innerHTML = `
                        <div class="alert alert-danger">
                            Error analyzing task: ${data.message || 'Unknown error'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('taskAnalysisResults').innerHTML = `
                    <div class="alert alert-danger">
                        Error analyzing task. Please try again.
                    </div>
                `;
            });
        });
    }
    
    // Resource Allocation
    const resourceAllocationBtn = document.getElementById('btn-resource_allocation');
    if (resourceAllocationBtn) {
        resourceAllocationBtn.addEventListener('click', function() {
            // Show loading state
            document.getElementById('results-title').textContent = 'Resource Allocation Recommendations';
            document.getElementById('results-content').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Generating resource allocation recommendations...</p></div>';
            document.getElementById('recommendation-results').style.display = 'block';
            document.getElementById('generation-date').textContent = new Date().toLocaleString();
            
            // Get resource allocation recommendations
            fetch('/api/resource_allocation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    use_gemini: true
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to generate resource allocation recommendations');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Format the recommendations
                    const result = data.data;
                    let html = `
                        <div class="mb-4">
                            <h5>Current Resource Utilization</h5>
                            <div class="card">
                                <div class="card-body">
                                    <p>${result.current_utilization.overview}</p>
                                    
                                    <h6>Project Utilization</h6>
                                    <div class="table-responsive">
                                        <table class="table table-bordered">
                                            <thead>
                                                <tr>
                                                    <th>Project</th>
                                                    <th>Utilization</th>
                                                    <th>Issues</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                    `;
                    
                    if (result.current_utilization.projects && result.current_utilization.projects.length > 0) {
                        result.current_utilization.projects.forEach(project => {
                            html += `
                                <tr>
                                    <td>${project.project_id}</td>
                                    <td>
                                        <div class="progress">
                                            <div class="progress-bar" role="progressbar" style="width: ${project.utilization_percentage}%;" aria-valuenow="${project.utilization_percentage}" aria-valuemin="0" aria-valuemax="100">${project.utilization_percentage}%</div>
                                        </div>
                                    </td>
                                    <td>
                                        <ul class="mb-0">
                                            ${project.issues.map(issue => `<li>${issue}</li>`).join('')}
                                        </ul>
                                    </td>
                                </tr>
                            `;
                        });
                    } else {
                        html += `<tr><td colspan="3" class="text-center">No project data available</td></tr>`;
                    }
                    
                    html += `
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <h5>Recommendations</h5>
                            <div class="card">
                                <div class="card-body">
                                    <ul>
                                        ${result.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                                    </ul>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <h5>Efficiency Actions</h5>
                            <div class="card">
                                <div class="card-body">
                                    <ul>
                                        ${result.efficiency_actions.map(action => `<li>${action}</li>`).join('')}
                                    </ul>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <h5>Resource Conflicts</h5>
                            <div class="card">
                                <div class="card-body">
                    `;
                    
                    if (result.resource_conflicts && result.resource_conflicts.length > 0) {
                        html += `<div class="accordion" id="conflictsAccordion">`;
                        result.resource_conflicts.forEach((conflict, index) => {
                            html += `
                                <div class="accordion-item">
                                    <h2 class="accordion-header" id="conflict-heading-${index}">
                                        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#conflict-collapse-${index}" aria-expanded="false" aria-controls="conflict-collapse-${index}">
                                            ${conflict.description}
                                        </button>
                                    </h2>
                                    <div id="conflict-collapse-${index}" class="accordion-collapse collapse" aria-labelledby="conflict-heading-${index}" data-bs-parent="#conflictsAccordion">
                                        <div class="accordion-body">
                                            <strong>Resolution:</strong> ${conflict.resolution}
                                        </div>
                                    </div>
                                </div>
                            `;
                        });
                        html += `</div>`;
                    } else {
                        html += `<p class="text-center">No resource conflicts identified</p>`;
                    }
                    
                    html += `
                                </div>
                            </div>
                        </div>
                    `;
                    
                    document.getElementById('results-content').innerHTML = html;
                } else {
                    document.getElementById('results-content').innerHTML = `
                        <div class="alert alert-danger">
                            Error generating recommendations: ${data.message || 'Unknown error'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('results-content').innerHTML = `
                    <div class="alert alert-danger">
                        Error generating recommendations. Please try again.
                    </div>
                `;
            });
        });
    }
    
    // Risk Assessment
    const riskAssessmentBtn = document.getElementById('btn-risk_assessment');
    if (riskAssessmentBtn) {
        riskAssessmentBtn.addEventListener('click', function() {
            // Show loading state
            document.getElementById('results-title').textContent = 'Risk Assessment';
            document.getElementById('results-content').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Generating risk assessment...</p></div>';
            document.getElementById('recommendation-results').style.display = 'block';
            document.getElementById('generation-date').textContent = new Date().toLocaleString();
            
            // Get risk assessment
            fetch('/api/risk_assessment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to generate risk assessment');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Format the risk assessment
                    const result = data.data;
                    let html = `
                        <div class="mb-4">
                            <h5>Project: ${result.project_name}</h5>
                            <div class="alert alert-info">
                                <p><strong>Risk Score:</strong> ${result.risk_score}/10</p>
                                <p>${result.summary}</p>
                            </div>
                        </div>
                    `;
                    
                    // High Risk Items
                    if (result.high_risk_items && result.high_risk_items.length > 0) {
                        html += `
                            <div class="mb-4">
                                <h5>High Risk Items</h5>
                                <div class="list-group mb-3">
                                    ${result.high_risk_items.map(risk => `
                                        <div class="list-group-item list-group-item-danger">
                                            <div class="d-flex justify-content-between align-items-center">
                                                <h6 class="mb-0">${risk.title}</h6>
                                                <div>
                                                    <span class="badge bg-danger me-1">Impact: ${risk.impact}</span>
                                                    <span class="badge bg-warning text-dark">Probability: ${risk.probability}</span>
                                                </div>
                                            </div>
                                            <p class="mb-1">${risk.description}</p>
                                            <strong>Mitigation:</strong> ${risk.mitigation}
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `;
                    }
                    
                    // Medium Risk Items
                    if (result.medium_risk_items && result.medium_risk_items.length > 0) {
                        html += `
                            <div class="mb-4">
                                <h5>Medium Risk Items</h5>
                                <div class="list-group mb-3">
                                    ${result.medium_risk_items.map(risk => `
                                        <div class="list-group-item list-group-item-warning">
                                            <div class="d-flex justify-content-between align-items-center">
                                                <h6 class="mb-0">${risk.title}</h6>
                                                <span class="badge bg-warning text-dark">Medium</span>
                                            </div>
                                            <p class="mb-1">${risk.description}</p>
                                            <strong>Mitigation:</strong> ${risk.mitigation}
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `;
                    }
                    
                    // Low Risk Items
                    if (result.low_risk_items && result.low_risk_items.length > 0) {
                        html += `
                            <div class="mb-4">
                                <h5>Low Risk Items</h5>
                                <div class="card">
                                    <div class="card-body">
                                        <ul>
                                            ${result.low_risk_items.map(risk => `<li>${risk}</li>`).join('')}
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                    
                    // Recommendations
                    if (result.recommendations && result.recommendations.length > 0) {
                        html += `
                            <div class="mb-4">
                                <h5>Recommendations</h5>
                                <div class="card">
                                    <div class="card-body">
                                        <ol>
                                            ${result.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                                        </ol>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                    
                    document.getElementById('results-content').innerHTML = html;
                } else {
                    document.getElementById('results-content').innerHTML = `
                        <div class="alert alert-danger">
                            Error generating risk assessment: ${data.message || 'Unknown error'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('results-content').innerHTML = `
                    <div class="alert alert-danger">
                        Error generating risk assessment. Please try again.
                    </div>
                `;
            });
        });
    }
    
    // Timeline Optimization
    const timelineOptimizationBtn = document.getElementById('btn-timeline_optimization');
    if (timelineOptimizationBtn) {
        timelineOptimizationBtn.addEventListener('click', function() {
            // Show loading state
            document.getElementById('results-title').textContent = 'Timeline Optimization';
            document.getElementById('results-content').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Generating timeline optimization...</p></div>';
            document.getElementById('recommendation-results').style.display = 'block';
            document.getElementById('generation-date').textContent = new Date().toLocaleString();
            
            // Get timeline optimization
            fetch('/api/timeline_optimization', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to generate timeline optimization');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Format the timeline optimization
                    const result = data.data;
                    
                    // Calculate time savings
                    const currentDuration = result.current_timeline.duration_weeks;
                    const optimizedDuration = result.optimized_timeline.duration_weeks;
                    const timeSavings = currentDuration - optimizedDuration;
                    const savingsPercentage = Math.round((timeSavings / currentDuration) * 100);
                    
                    let html = `
                        <div class="mb-4">
                            <h5>Project: ${result.project_name}</h5>
                            <div class="alert alert-success">
                                <p><strong>Time Savings:</strong> ${timeSavings} weeks (${savingsPercentage}%)</p>
                                <p>Current Duration: ${currentDuration} weeks → Optimized Duration: ${optimizedDuration} weeks</p>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <h5>Timeline Comparison</h5>
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-header">Current Timeline</div>
                                        <div class="card-body">
                                            <p><strong>Project Duration:</strong> ${result.current_timeline.duration_weeks} weeks</p>
                                            <p><strong>Critical Path Tasks:</strong> ${result.current_timeline.critical_path_tasks.length}</p>
                                            <p><strong>Bottlenecks:</strong></p>
                                            <ul>
                                                ${result.current_timeline.bottlenecks.map(bottleneck => `<li>${bottleneck}</li>`).join('')}
                                            </ul>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-header">Optimized Timeline</div>
                                        <div class="card-body">
                                            <p><strong>Project Duration:</strong> ${result.optimized_timeline.duration_weeks} weeks</p>
                                            <p><strong>Time Savings:</strong> ${timeSavings} weeks (${savingsPercentage}%)</p>
                                            <p><strong>Critical Path Tasks:</strong> ${result.optimized_timeline.critical_path_tasks.length}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <h5>Optimization Recommendations</h5>
                            <div class="card">
                                <div class="card-body">
                                    <ol>
                                        ${result.optimization_recommendations.map(rec => `<li>${rec}</li>`).join('')}
                                    </ol>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <h5>Implementation Plan</h5>
                            <div class="card">
                                <div class="card-body">
                                    <ol>
                                        ${result.implementation_plan.map(step => `<li>${step}</li>`).join('')}
                                    </ol>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    document.getElementById('results-content').innerHTML = html;
                } else {
                    document.getElementById('results-content').innerHTML = `
                        <div class="alert alert-danger">
                            Error generating timeline optimization: ${data.message || 'Unknown error'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('results-content').innerHTML = `
                    <div class="alert alert-danger">
                        Error generating timeline optimization. Please try again.
                    </div>
                `;
            });
        });
    }
    
    // Quick Actions
    const quickActionButtons = document.querySelectorAll('[id^="quick-"]');
    quickActionButtons.forEach(button => {
        button.addEventListener('click', function() {
            const actionId = button.id.replace('quick-', '');
            const url = button.getAttribute('data-url');
            
            // If the button has a URL, redirect to it
            if (url) {
                window.location.href = url;
                return;
            }
            
            // Show loading state
            document.getElementById('results-title').textContent = `${button.textContent.trim()} Results`;
            document.getElementById('results-content').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Generating results...</p></div>';
            document.getElementById('recommendation-results').style.display = 'block';
            document.getElementById('generation-date').textContent = new Date().toLocaleString();
            
            // Call the quick action API
            fetch('/api/quick_action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    action_id: actionId
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to generate results');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Format the results based on action type
                    const result = data.data;
                    let html = '';
                    
                    if (actionId === 'generate_report') {
                        html = `
                            <div class="mb-4">
                                <h5>${result.title}</h5>
                                <p class="text-muted">Generated on ${result.date}</p>
                            </div>
                        `;
                        
                        // Add each section
                        result.sections.forEach(section => {
                            html += `
                                <div class="mb-4">
                                    <h5>${section.heading}</h5>
                                    <div class="card">
                                        <div class="card-body">
                                            ${section.content.replace(/\n/g, '<br>')}
                                        </div>
                                    </div>
                                </div>
                            `;
                        });
                    } else if (actionId === 'team_performance') {
                        html = `
                            <div class="mb-4">
                                <h5>${result.title}</h5>
                                <p class="text-muted">Generated on ${result.date}</p>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Overall Assessment</h5>
                                <div class="card">
                                    <div class="card-body">
                                        ${result.overall_assessment.replace(/\n/g, '<br>')}
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Individual Performance Highlights</h5>
                                <div class="row">
                                    ${result.individual_highlights.map(person => `
                                        <div class="col-md-6 mb-3">
                                            <div class="card">
                                                <div class="card-header">${person.name}</div>
                                                <div class="card-body">
                                                    <h6>Strengths:</h6>
                                                    <ul>
                                                        ${person.strengths.map(strength => `<li>${strength}</li>`).join('')}
                                                    </ul>
                                                    <h6>Areas for Improvement:</h6>
                                                    <ul>
                                                        ${person.areas_for_improvement.map(area => `<li>${area}</li>`).join('')}
                                                    </ul>
                                                </div>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Team Improvement Areas</h5>
                                <div class="card">
                                    <div class="card-body">
                                        <ul>
                                            ${result.team_improvement_areas.map(area => `<li>${area}</li>`).join('')}
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Recommendations</h5>
                                <div class="card">
                                    <div class="card-body">
                                        <ol>
                                            ${result.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                                        </ol>
                                    </div>
                                </div>
                            </div>
                        `;
                    } else if (actionId === 'meeting_summary') {
                        html = `
                            <div class="mb-4">
                                <h5>${result.title}</h5>
                                <p class="text-muted">Meeting Date: ${result.date}</p>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Overview</h5>
                                <div class="card">
                                    <div class="card-body">
                                        ${result.overview.replace(/\n/g, '<br>')}
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Key Discussion Points</h5>
                                <div class="card">
                                    <div class="card-body">
                                        <ul>
                                            ${result.key_points.map(point => `<li>${point}</li>`).join('')}
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Decisions Made</h5>
                                <div class="card">
                                    <div class="card-body">
                                        <ul>
                                            ${result.decisions.map(decision => `<li>${decision}</li>`).join('')}
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Action Items</h5>
                                <div class="list-group">
                                    ${result.action_items.map(item => `
                                        <div class="list-group-item">
                                            <div class="d-flex justify-content-between align-items-center">
                                                <h6 class="mb-0">${item.description}</h6>
                                                <span class="badge bg-primary">${item.due_date || 'No due date'}</span>
                                            </div>
                                            <p class="mb-0"><strong>Assigned to:</strong> ${item.assigned_to || 'Unassigned'}</p>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Next Steps</h5>
                                <div class="card">
                                    <div class="card-body">
                                        <ol>
                                            ${result.next_steps.map(step => `<li>${step}</li>`).join('')}
                                        </ol>
                                    </div>
                                </div>
                            </div>
                        `;
                    } else if (actionId === 'skill_gap') {
                        html = `
                            <div class="mb-4">
                                <h5>${result.title}</h5>
                                <p class="text-muted">Generated on ${result.date}</p>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Skill Coverage Overview</h5>
                                <div class="card">
                                    <div class="card-body">
                                        <div class="progress mb-3">
                                            <div class="progress-bar" role="progressbar" style="width: ${result.skill_coverage.percentage}%;" aria-valuenow="${result.skill_coverage.percentage}" aria-valuemin="0" aria-valuemax="100">${result.skill_coverage.percentage}% Coverage</div>
                                        </div>
                                        
                                        <div class="row">
                                            <div class="col-md-4">
                                                <h6 class="text-success">Strong Skills</h6>
                                                <ul>
                                                    ${result.skill_coverage.strong_skills.map(skill => `<li>${skill}</li>`).join('')}
                                                </ul>
                                            </div>
                                            <div class="col-md-4">
                                                <h6 class="text-warning">Adequate Skills</h6>
                                                <ul>
                                                    ${result.skill_coverage.adequate_skills.map(skill => `<li>${skill}</li>`).join('')}
                                                </ul>
                                            </div>
                                            <div class="col-md-4">
                                                <h6 class="text-danger">Gap Skills</h6>
                                                <ul>
                                                    ${result.skill_coverage.gap_skills.map(skill => `<li>${skill}</li>`).join('')}
                                                </ul>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Recommendations</h5>
                                <div class="table-responsive">
                                    <table class="table table-bordered">
                                        <thead>
                                            <tr>
                                                <th>Skill</th>
                                                <th>Recommendation</th>
                                                <th>Priority</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${result.recommendations.map(rec => `
                                                <tr>
                                                    <td>${rec.skill}</td>
                                                    <td>${rec.recommendation}</td>
                                                    <td>
                                                        <span class="badge ${rec.priority === 'High' ? 'bg-danger' : rec.priority === 'Medium' ? 'bg-warning text-dark' : 'bg-info text-dark'}">
                                                            ${rec.priority}
                                                        </span>
                                                    </td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Training Suggestions</h5>
                                <div class="row">
                                    ${result.training_suggestions.map(training => `
                                        <div class="col-md-4 mb-3">
                                            <div class="card">
                                                <div class="card-header">${training.skill}</div>
                                                <div class="card-body">
                                                    <h6>${training.training_type}</h6>
                                                    <p>${training.description}</p>
                                                </div>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `;
                    } else {
                        html = `
                            <div class="alert alert-info">
                                <h5>Results Generated</h5>
                                <p>${JSON.stringify(result)}</p>
                            </div>
                        `;
                    }
                    
                    document.getElementById('results-content').innerHTML = html;
                } else {
                    document.getElementById('results-content').innerHTML = `
                        <div class="alert alert-danger">
                            Error generating results: ${data.message || 'Unknown error'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('results-content').innerHTML = `
                    <div class="alert alert-danger">
                        Error generating results. Please try again.
                    </div>
                `;
            });
        });
    });

    // Save Results
    const saveResultsBtn = document.getElementById('save-results');
    if (saveResultsBtn) {
        saveResultsBtn.addEventListener('click', function() {
            const title = document.getElementById('results-title').textContent;
            const content = document.getElementById('results-content').innerHTML;
            
            fetch('/api/save_recommendations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: title,
                    content: content,
                    date: new Date().toISOString()
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to save recommendations');
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    alert('Recommendations saved successfully!');
                } else {
                    alert('Error saving recommendations: ' + (data.message || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error saving recommendations. Please try again.');
            });
        });
    }
    
    // Close Results
    const closeResultsBtn = document.getElementById('close-results');
    if (closeResultsBtn) {
        closeResultsBtn.addEventListener('click', function() {
            document.getElementById('recommendation-results').style.display = 'none';
        });
    }
    
    // Feedback Modal
    const feedbackBtn = document.getElementById('btn-feedback');
    if (feedbackBtn) {
        feedbackBtn.addEventListener('click', function() {
            const feedbackModal = new bootstrap.Modal(document.getElementById('feedbackModal'));
            feedbackModal.show();
        });
    }
    
    // Submit Feedback
    const feedbackForm = document.getElementById('feedbackForm');
    if (feedbackForm) {
        feedbackForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const feedbackType = document.getElementById('feedbackType').value;
            const feedbackText = document.getElementById('feedbackText').value;
            
            if (!feedbackText) {
                alert('Please enter your feedback');
                return;
            }
            
            fetch('/api/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    feedback_type: feedbackType,
                    feedback_text: feedbackText
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to submit feedback');
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    alert('Thank you for your feedback!');
                    // Close the modal
                    bootstrap.Modal.getInstance(document.getElementById('feedbackModal')).hide();
                    // Clear the form
                    document.getElementById('feedbackText').value = '';
                } else {
                    alert('Error submitting feedback: ' + (data.message || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error submitting feedback. Please try again.');
            });
        });
    }
    
    // Help Modal
    const helpBtn = document.getElementById('btn-help');
    if (helpBtn) {
        helpBtn.addEventListener('click', function() {
            const helpModal = new bootstrap.Modal(document.getElementById('helpModal'));
            helpModal.show();
        });
    }
    
    // Refine Results
    const refineResultsBtn = document.getElementById('btn-refine');
    if (refineResultsBtn) {
        refineResultsBtn.addEventListener('click', function() {
            const currentTitle = document.getElementById('results-title').textContent;
            const currentContent = document.getElementById('results-content').innerHTML;
            
            // Show a prompt to get user input for refinement
            const refinementPrompt = prompt('What aspects would you like to refine or improve?');
            if (!refinementPrompt) {
                return; // User cancelled
            }
            
            // Show loading state
            document.getElementById('results-content').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Refining results...</p></div>';
            
            // Call the API to refine results
            fetch('/api/refine_results', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: currentTitle,
                    content: currentContent,
                    refinement_prompt: refinementPrompt
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to refine results');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Update the results with refined content
                    document.getElementById('results-content').innerHTML = data.refined_content;
                    // Update the generation date
                    document.getElementById('generation-date').textContent = new Date().toLocaleString();
                } else {
                    document.getElementById('results-content').innerHTML = currentContent;
                    alert('Error refining results: ' + (data.message || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('results-content').innerHTML = currentContent;
                alert('Error refining results. Please try again.');
            });
        });
    }
    
    // Share Results
    const shareResultsBtn = document.getElementById('btn-share');
    if (shareResultsBtn) {
        shareResultsBtn.addEventListener('click', function() {
            const title = document.getElementById('results-title').textContent;
            const recipients = prompt('Enter email addresses to share with (comma-separated):');
            if (!recipients) {
                return; // User cancelled
            }
            
            fetch('/api/share_results', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: title,
                    content: document.getElementById('results-content').innerHTML,
                    recipients: recipients.split(',').map(email => email.trim())
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to share results');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    alert('Results shared successfully!');
                } else {
                    alert('Error sharing results: ' + (data.message || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error sharing results. Please try again.');
            });
        });
    }
    
    // Export Results
    const exportPdfBtn = document.getElementById('export-pdf');
    const exportExcelBtn = document.getElementById('export-excel');
    const exportWordBtn = document.getElementById('export-word');
    
    // Function to handle export
    const handleExport = (exportType) => {
        const title = document.getElementById('results-title').textContent;
        const content = document.getElementById('results-content').innerHTML;
        
        fetch('/api/export_results', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title: title,
                content: content,
                export_type: exportType
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to export as ${exportType.toUpperCase()}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                alert(data.message || `Results exported as ${exportType.toUpperCase()}`);
            } else {
                alert('Error exporting results: ' + (data.message || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error exporting results. Please try again.');
        });
    };
    
    // Add event listeners for export buttons
    if (exportPdfBtn) {
        exportPdfBtn.addEventListener('click', function(e) {
            e.preventDefault();
            handleExport('pdf');
        });
    }
    
    if (exportExcelBtn) {
        exportExcelBtn.addEventListener('click', function(e) {
            e.preventDefault();
            handleExport('excel');
        });
    }
    
    if (exportWordBtn) {
        exportWordBtn.addEventListener('click', function(e) {
            e.preventDefault();
            handleExport('word');
        });
    }
    
    // Settings button
    const settingsBtn = document.getElementById('btn-settings');
    if (settingsBtn) {
        settingsBtn.addEventListener('click', function() {
            const settingsModal = new bootstrap.Modal(document.getElementById('settingsModal'));
            settingsModal.show();
        });
    }
    
    // Handle all recommendation buttons with data-url attribute
    const recommendationButtons = document.querySelectorAll('button[data-url]');
    recommendationButtons.forEach(button => {
        button.addEventListener('click', function() {
            const url = this.getAttribute('data-url');
            if (url) {
                window.location.href = url;
            }
        });
    });
});