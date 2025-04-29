import os


# Flask configuration
SECRET_KEY = 1234
UPLOAD_FOLDER = 'static/uploads'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Excel database configuration
DB_FILE = 'project_management.xlsx'

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'images': {'png', 'jpg', 'jpeg', 'gif'},
    'documents': {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt'}
}

# Excel sheet names
SHEETS = {
    'users': 'users',
    'projects': 'projects',
    'tasks': 'tasks',
    'meetings': 'meetings',
    'timeline': 'timeline',
    'settings': 'settings',
    'notifications': 'notifications'
}

# Excel column definitions
COLUMNS = {
    'users': [
        'id', 'name', 'email', 'password', 'role', 'avatar', 
        'phone', 'linkedin', 'created_at', 'last_login', 'skills'
    ],
    'projects': [
        'id', 'name', 'description', 'start_date', 'end_date',
        'status', 'budget', 'progress', 'team_members', 'tech_stack'
    ],
    'tasks': [
        'id', 'project_id', 'name', 'description', 'assignee_id',
        'status', 'priority', 'start_date', 'due_date', 'budget_used',
        'required_skills', 'completed_at'
    ],
    'meetings': [
        'id', 'project_id', 'title', 'description', 'meeting_date',
        'duration', 'participants', 'created_at'
    ],
    'timeline': [
        'id', 'project_id', 'date', 'progress_update',
        'budget_update', 'files'
    ],
    'settings': [
        'id', 'site_name', 'admin_email', 'session_timeout',
        'max_file_size', 'allowed_file_types', 'notification_enabled'
    ],
    'notifications': [
        'id', 'user_id', 'title', 'message', 'type',
        'timestamp', 'read'
    ]
}

AIRTABLE_BASE_ID = 'appHoXSknaYRWvtBE'
AIRTABLE_TABLE_NAME = 'Projects'
AIRTABLE_TASKS_TABLE = "Tasks"
AIRTABLE_API_KEY = 'patK17VUNIZftj0OD1e2b16a1bf420e90be7c67ac630d250974734613f92cddc954ee135e40d509d4'
GEMINI_API_KEY = 'AIzaSyDUisDr1CSI78QRulZWrbXiJEScyx4Nxqc'
