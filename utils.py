import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import json
from config import GEMINI_API_KEY
import google.generativeai as genai

# Initialize Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def scrape_development_resources(query):
    """Scrape development resources from various sources"""
    resources = []
    
    # GitHub search
    github_url = f"https://github.com/search?q={query}&type=repositories"
    try:
        response = requests.get(github_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        repos = soup.find_all('div', class_='repo-list-item')
        for repo in repos[:5]:
            title = repo.find('a', class_='v-align-middle').text
            description = repo.find('p', class_='col-9').text.strip()
            resources.append({
                'source': 'GitHub',
                'title': title,
                'description': description,
                'url': f"https://github.com{repo.find('a', class_='v-align-middle')['href']}"
            })
    except Exception as e:
        print(f"Error scraping GitHub: {str(e)}")
    
    # Stack Overflow search
    stack_url = f"https://stackoverflow.com/search?q={query}"
    try:
        response = requests.get(stack_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        questions = soup.find_all('div', class_='question-summary')
        for question in questions[:5]:
            title = question.find('a', class_='question-hyperlink').text
            description = question.find('div', class_='excerpt').text.strip()
            resources.append({
                'source': 'Stack Overflow',
                'title': title,
                'description': description,
                'url': f"https://stackoverflow.com{question.find('a', class_='question-hyperlink')['href']}"
            })
    except Exception as e:
        print(f"Error scraping Stack Overflow: {str(e)}")
    
    return resources

def get_development_recommendations(project_type, tech_stack):
    """Get AI-powered development recommendations"""
    prompt = f"""
    Based on the project type: {project_type}
    And tech stack: {tech_stack}
    
    Please provide recommendations for:
    1. Best practices
    2. Architecture patterns
    3. Security considerations
    4. Performance optimization
    5. Testing strategies
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error getting AI recommendations: {str(e)}")
        return "Unable to generate recommendations at this time."

def match_skills_to_tasks(team_members, tasks):
    """Match team members to tasks based on skills"""
    matches = []
    
    for task in tasks:
        best_match = None
        best_score = 0
        
        for member in team_members:
            # Calculate skill match score
            score = calculate_skill_match(member['skills'], task['required_skills'])
            if score > best_score:
                best_score = score
                best_match = member
        
        if best_match:
            matches.append({
                'task_id': task['id'],
                'member_id': best_match['id'],
                'match_score': best_score
            })
    
    return matches

def calculate_skill_match(member_skills, required_skills):
    """Calculate skill match score between member and task"""
    if not member_skills or not required_skills:
        return 0
    
    member_skills = set(member_skills.lower().split(','))
    required_skills = set(required_skills.lower().split(','))
    
    if not required_skills:
        return 0
    
    matching_skills = member_skills.intersection(required_skills)
    return len(matching_skills) / len(required_skills)

def send_notification(user_id, title, message, notification_type='info'):
    """Send notification to user"""
    notification = {
        'id': datetime.now().timestamp(),
        'user_id': user_id,
        'title': title,
        'message': message,
        'type': notification_type,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'read': False
    }
    
    # Save notification to Excel
    from database import db
    db.add_record('notifications', notification)
    return notification

def check_project_milestones(project_id):
    """Check project milestones and send notifications"""
    from database import db
    from models import Project, Task, Notification
    
    project = Project.get_by_id(project_id)
    if not project:
        return
    
    # Check upcoming deadlines
    tasks = db.get_records('tasks', {'project_id': project_id})
    for task in tasks:
        if task['status'] != 'Completed':
            due_date = datetime.strptime(task['due_date'], '%Y-%m-%d')
            days_until_due = (due_date - datetime.now()).days
            
            if days_until_due <= 3 and days_until_due > 0:
                send_notification(
                    task['assignee_id'],
                    'Upcoming Task Deadline',
                    f"Task '{task['name']}' is due in {days_until_due} days",
                    'warning'
                )
            elif days_until_due <= 0:
                send_notification(
                    task['assignee_id'],
                    'Task Overdue',
                    f"Task '{task['name']}' is overdue",
                    'danger'
                )
    
    # Check project progress
    progress = project.calculate_progress()
    if progress >= 25 and progress < 50:
        send_notification(
            project.team_members[0],  # Project manager
            'Project Progress Update',
            f"Project '{project.name}' has reached {progress}% completion",
            'info'
        )
    
    # Check milestones
    milestones = project.get_milestones()
    for milestone in milestones:
        due_date = datetime.strptime(milestone['due_date'], '%Y-%m-%d')
        days_until_due = (due_date - datetime.now()).days
        
        if days_until_due <= 7 and days_until_due > 0:
            send_notification(
                project.team_members[0],
                'Upcoming Milestone',
                f"Milestone '{milestone['title']}' is due in {days_until_due} days",
                'warning'
            )
        elif days_until_due <= 0 and milestone['status'] == 'Pending':
            send_notification(
                project.team_members[0],
                'Milestone Overdue',
                f"Milestone '{milestone['title']}' is overdue",
                'danger'
            )
            # Update milestone status
            db.update_record('timeline', milestone['id'], {'status': 'Overdue'})

def check_skill_gaps(project_id):
    """Check for skill gaps in project team"""
    from database import db
    from models import Project, Task
    
    project = Project.get_by_id(project_id)
    if not project:
        return
    
    tasks = db.get_records('tasks', {'project_id': project_id})
    team_members = [db.get_record('users', member_id) for member_id in project.team_members.split(',')]
    
    skill_gaps = []
    for task in tasks:
        if task['status'] != 'Completed':
            required_skills = task.get('required_skills', '').split(',')
            assigned_member = next((member for member in team_members if str(member['id']) == str(task['assignee_id'])), None)
            
            if assigned_member:
                member_skills = assigned_member.get('skills', '').split(',')
                missing_skills = [skill for skill in required_skills if skill not in member_skills]
                
                if missing_skills:
                    skill_gaps.append({
                        'task_name': task['name'],
                        'member_name': assigned_member['name'],
                        'missing_skills': missing_skills
                    })
    
    if skill_gaps:
        send_notification(
            project.team_members[0],
            'Skill Gaps Detected',
            f"Found {len(skill_gaps)} tasks with skill gaps. Check project details for more information.",
            'warning'
        )
    
    return skill_gaps

def check_tech_stack_compatibility(project_id):
    """Check tech stack compatibility and send recommendations"""
    from database import db
    from models import Project
    
    project = Project.get_by_id(project_id)
    if not project:
        return
    
    recommendations = get_development_recommendations(project.name, ','.join(project.tech_stack))
    
    if recommendations:
        send_notification(
            project.team_members[0],
            'Tech Stack Recommendations',
            'New recommendations available for your project\'s tech stack. Check project details for more information.',
            'info'
        )
    
    return recommendations 