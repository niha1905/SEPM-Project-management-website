import os
from datetime import datetime, timedelta, date  # Import specific components instead of the whole module
import json
import random  # Importing random module
import uuid
import re
import io
import base64
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_file, abort
from jinja2.exceptions import TemplateNotFound
from werkzeug.utils import secure_filename
import requests
from bs4 import BeautifulSoup
import PyPDF2
import matplotlib.pyplot as plt

# Import Google Generative AI
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from config import GEMINI_API_KEY

# Import pandas last to avoid conflicts
import pandas as pd


# Check for Gemini API key
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it before running the application.")

# Flask App Initialization
app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_secret_key_here")
db_file = "database.xlsx"

# Add template filters
@app.template_filter('format_number')
def format_number(value):
    """Format a number with commas as thousands separators"""
    try:
        return "{:,.2f}".format(float(value))
    except (ValueError, TypeError):
        return value

# Define sheets schema globally
sheets = {
    "users": {
        "columns": ["id", "email", "password", "name", "role", "skills", "created_at", "last_login", "is_active", "department", "supervisor_id", "permissions"],
        "dtypes": {
            "id": str,
            "email": str,
            "password": str,
            "name": str,
            "role": str,
            "skills": str,
            "created_at": str,
            "last_login": str,
            "is_active": bool,
            "department": str,
            "supervisor_id": str,
            "permissions": str
        }
    },
    "projects": {
    "columns": ["id", "name", "description", "client_requirements", "team_members", "start_date", "end_date", "due_date", "status", "progress", "created_at", "updated_at", "manager_id", "budget", "priority"],
    "dtypes": {
        "id": str,
        "name": str,
        "description": str,
        "client_requirements": str,
        "team_members": str,
        "start_date": str,
        "end_date": str,
        "due_date": str,  # NEW FIELD
        "status": str,
        "progress": float,
        "created_at": str,
        "updated_at": str,
        "manager_id": str,
        "budget": float,
        "priority": str
    }
}
,
    "tasks": {
        "columns": ["id", "project_id", "title", "description", "assigned_to", "status", "priority", "due_date", "created_at", "updated_at", "progress", "estimated_hours", "actual_hours", "required_skills"],
        "dtypes": {
            "id": str,
            "project_id": str,
            "title": str,
            "description": str,
            "assigned_to": str,
            "status": str,
            "priority": str,
            "due_date": str,
            "created_at": str,
            "updated_at": str,
            "progress": float,
            "estimated_hours": float,
            "actual_hours": float,
            "required_skills": str
        }
    },
    "notifications": {
        "columns": ["id", "user_id", "title", "message", "type", "created_at", "read", "action_url"],
        "dtypes": {
            "id": str,
            "user_id": str,
            "title": str,
            "message": str,
            "type": str,
            "created_at": str,
            "read": bool,
            "action_url": str
        }
    },
    "meetings": {
        "columns": ["id", "project_id", "title", "description", "date", "time", "duration", "location", "organizer_id", "participants", "status", "created_at", "updated_at", "agenda"],
        "dtypes": {
            "id": str,
            "project_id": str,
            "title": str,
            "description": str,
            "date": str,
            "time": str,
            "duration": str,
            "location": str,
            "organizer_id": str,
            "participants": str,
            "status": str,
            "created_at": str,
            "updated_at": str,
            "agenda": str
        }
    },
    "user_permissions": {
        "columns": ["id", "user_id", "permission", "granted_by", "granted_at"],
        "dtypes": {
            "id": str,
            "user_id": str,
            "permission": str,
            "granted_by": str,
            "granted_at": str
        }
    },
    "project_access": {
        "columns": ["id", "user_id", "project_id", "role", "granted_by", "granted_at"],
        "dtypes": {
            "id": str,
            "user_id": str,
            "project_id": str,
            "role": str,
            "granted_by": str,
            "granted_at": str
        }
    },
    "budget_analysis": {
        "columns": ["id", "project_id", "total_budget", "allocated_budget", "remaining_budget", "analysis_date", "created_at", "recommendations", "risk_assessment", "original_breakdown"],
        "dtypes": {
            "id": str,
            "project_id": str,
            "total_budget": float,
            "allocated_budget": float,
            "remaining_budget": float,
            "analysis_date": str,
            "created_at": str,
            "recommendations": str,
            "risk_assessment": str,
            "original_breakdown": str
        }
    },
    "conversations": {
        "columns": ["id", "project_id", "user_id", "message", "created_at", "updated_at", "is_read"],
        "dtypes": {
            "id": str,
            "project_id": str,
            "user_id": str,
            "message": str,
            "created_at": str,
            "updated_at": str,
            "is_read": bool
        }
    }
}

# Add context processor for user data
@app.context_processor
def inject_user():
    if 'user' in session:
        return {'current_user': load_user_data(session['user'])}
    return {'current_user': None}

# Initialize Gemini API
genai.configure(api_key=GEMINI_API_KEY)  # Use the API key from config
model = genai.GenerativeModel('gemini-1.5-flash')

def initialize_db():
    try:
        if not os.path.exists(db_file):
            print("Database file not found. Creating new database...")
            with pd.ExcelWriter(db_file, engine='openpyxl', mode='w') as writer:
                for sheet_name, sheet_info in sheets.items():
                    print(f"Creating sheet: {sheet_name}")
                    df = pd.DataFrame(columns=sheet_info["columns"])
                    for col, dtype in sheet_info["dtypes"].items():
                        if col in df.columns:  # Only set type for columns that exist
                            df[col] = df[col].astype(dtype)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            print("Database initialized successfully.")
        else:
            # Check if all required sheets exist and have the correct columns
            try:
                existing_sheets = pd.read_excel(db_file, sheet_name=None)
                for sheet_name, sheet_info in sheets.items():
                    if sheet_name not in existing_sheets:
                        print(f"Sheet {sheet_name} missing. Creating it...")
                        df = pd.DataFrame(columns=sheet_info["columns"])
                        for col, dtype in sheet_info["dtypes"].items():
                            if col in df.columns:
                                df[col] = df[col].astype(dtype)
                        
                        # Add the new sheet to the Excel file
                        existing_sheets[sheet_name] = df
                        
                        # Save all sheets back
                        with pd.ExcelWriter(db_file, engine='openpyxl', mode='w') as writer:
                            for s_name, s_data in existing_sheets.items():
                                s_data.to_excel(writer, sheet_name=s_name, index=False)
            except Exception as e:
                print(f"Error checking existing sheets: {str(e)}")
    except Exception as e:
        print(f"Error initializing DB: {e}")
        import traceback
        traceback.print_exc()


# Load Data with Error Handling
def load_data(sheet_name):
    try:
        if not os.path.exists(db_file):
            print(f"Database file not found: {db_file}")
            return pd.DataFrame()
            
        # Get sheet info for proper data types
        sheet_info = sheets.get(sheet_name)
        if not sheet_info:
            print(f"Sheet {sheet_name} not found in schema")
            return pd.DataFrame()
            
        df = pd.read_excel(db_file, sheet_name=sheet_name)
        
        # Convert columns to proper data types
        for col, dtype in sheet_info["dtypes"].items():
            if col in df.columns:
                try:
                    if dtype == bool:
                        df[col] = df[col].fillna(False).astype(bool)
                    elif dtype == float:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                    else:
                        df[col] = df[col].fillna('').astype(str)
                except Exception as e:
                    print(f"Error converting column {col} to {dtype}: {str(e)}")
                    df[col] = None
            
        return df
    except Exception as e:
        print(f"Error loading data from sheet {sheet_name}: {str(e)}")
        return pd.DataFrame()

def save_data(sheet_name, df):
    try:
        print(f"Saving data to sheet: {sheet_name}, DataFrame shape: {df.shape}")
        
        # Ensure the dataframe has the correct columns
        if sheet_name in sheets and "columns" in sheets[sheet_name]:
            expected_columns = sheets[sheet_name]["columns"]
            missing_columns = [col for col in expected_columns if col not in df.columns]
            
            if missing_columns:
                print(f"Warning: Missing columns in {sheet_name}: {missing_columns}")
                for col in missing_columns:
                    df[col] = None
            
            # Ensure columns are in the correct order
            df = df[expected_columns]
        
        # Load all sheets
        try:
            existing_sheets = pd.read_excel(db_file, sheet_name=None)
            print(f"Loaded existing sheets: {list(existing_sheets.keys())}")
        except Exception as e:
            print(f"Error loading existing sheets: {str(e)}")
            existing_sheets = {}
        
        # Replace target sheet
        existing_sheets[sheet_name] = df
        
        # Save all sheets back
        try:
            with pd.ExcelWriter(db_file, engine='openpyxl', mode='w') as writer:
                for sheet, data in existing_sheets.items():
                    print(f"Writing sheet: {sheet}, shape: {data.shape}")
                    data.to_excel(writer, sheet_name=sheet, index=False)
            
            print(f"Successfully saved data to {sheet_name}")
            return True
        except Exception as e:
            print(f"Error writing to Excel file: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"Error saving data to sheet {sheet_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# Function to check and repair database structure
def check_and_repair_db():
    try:
        print("Checking database structure...")
        if not os.path.exists(db_file):
            print("Database file not found. Initializing...")
            initialize_db()
            return
            
        # Check if all required sheets exist with correct columns
        existing_sheets = pd.read_excel(db_file, sheet_name=None)
        print(f"Found sheets: {list(existing_sheets.keys())}")
        
        needs_save = False
        for sheet_name, sheet_info in sheets.items():
            if sheet_name not in existing_sheets:
                print(f"Sheet {sheet_name} is missing. Creating it...")
                df = pd.DataFrame(columns=sheet_info["columns"])
                existing_sheets[sheet_name] = df
                needs_save = True
            else:
                # Check if all required columns exist
                df = existing_sheets[sheet_name]
                missing_columns = [col for col in sheet_info["columns"] if col not in df.columns]
                if missing_columns:
                    print(f"Sheet {sheet_name} is missing columns: {missing_columns}")
                    for col in missing_columns:
                        df[col] = None
                    existing_sheets[sheet_name] = df
                    needs_save = True
        
        if needs_save:
            print("Saving repaired database...")
            with pd.ExcelWriter(db_file, engine='openpyxl', mode='w') as writer:
                for s_name, s_data in existing_sheets.items():
                    s_data.to_excel(writer, sheet_name=s_name, index=False)
            print("Database repaired successfully.")
    except Exception as e:
        print(f"Error checking/repairing database: {str(e)}")
        import traceback
        traceback.print_exc()

# Initialize the database
initialize_db()
# Check and repair database structure
check_and_repair_db()

# Load User Data with Error Handling
def load_user_data(email):
    try:
        users_df = load_data("users")
        if users_df.empty:
            return None
            
        user = users_df[users_df['email'] == email]
        if not user.empty:
            user_data = user.to_dict(orient='records')[0]
            # Convert string representations to proper types
            if isinstance(user_data.get('permissions'), str):
                try:
                    user_data['permissions'] = eval(user_data['permissions'])
                except:
                    user_data['permissions'] = ['basic_access']
            if isinstance(user_data.get('skills'), str):
                user_data['skills'] = [skill.strip() for skill in user_data['skills'].split(',') if skill.strip()]
            return user_data
        return None
    except Exception as e:
        print(f"Error loading user data: {str(e)}")
        return None

# Save User Data with Error Handling
def save_user_data(email, user_data):
    try:
        users_df = load_data("users")
        if users_df.empty:
            users_df = pd.DataFrame(columns=sheets["users"]["columns"])
        
        # Convert lists to strings for storage
        if isinstance(user_data.get('permissions'), list):
            user_data['permissions'] = str(user_data['permissions'])
        if isinstance(user_data.get('skills'), list):
            user_data['skills'] = ','.join(user_data['skills'])
        
        # Create a new row with the user data
        new_user = pd.DataFrame([user_data])
        
        # Update or create user
        if email in users_df['email'].values:
            users_df.loc[users_df['email'] == email] = new_user.iloc[0]
        else:
            users_df = pd.concat([users_df, new_user], ignore_index=True)
        
        return save_data("users", users_df)
    except Exception as e:
        print(f"Error saving user data: {str(e)}")
        return False

# Load Projects Data with Error Handling
def load_projects():
    try:
        projects_df = load_data("projects")
        if projects_df.empty:
            return []
            
        projects = projects_df.to_dict(orient='records')
        for project in projects:
            # Convert string representations to proper types
            if isinstance(project.get('team_members'), str):
                project['team_members'] = [member.strip() for member in project['team_members'].split(',') if member.strip()]
            if isinstance(project.get('budget'), str):
                try:
                    project['budget'] = float(project['budget'])
                except:
                    project['budget'] = 0.0
            if isinstance(project.get('progress'), str):
                try:
                    project['progress'] = float(project['progress'])
                except:
                    project['progress'] = 0.0
            projects_df['due_date'] = projects_df['due_date'].fillna('')
        
        return projects
    except Exception as e:
        print(f"Error loading projects data: {str(e)}")
        return []

# Load Tasks Data with Error Handling
def load_tasks():
    try:
        tasks_df = load_data("tasks")
        if tasks_df.empty:
            return []
        
        # Load projects to get project names
        projects_df = load_data("projects")
        
        tasks = tasks_df.to_dict(orient='records')
        for task in tasks:
            # Convert string representations to proper types
            if isinstance(task.get('required_skills'), str):
                task['required_skills'] = [skill.strip() for skill in task['required_skills'].split(',') if skill.strip()]
            if isinstance(task.get('progress'), str):
                try:
                    task['progress'] = float(task['progress'])
                except:
                    task['progress'] = 0.0
            
            # Add project name to task
            if task.get('project_id') and not projects_df.empty:
                project = projects_df[projects_df['id'] == task['project_id']]
                if not project.empty:
                    task['project_name'] = project['name'].iloc[0]
            
            # Add status color
            task['status_color'] = {
                'Completed': 'success',
                'In Progress': 'primary',
                'To Do': 'warning',
                'On Hold': 'info',
                'Pending': 'secondary'
            }.get(task.get('status', ''), 'secondary')
            
            # Add priority color
            task['priority_color'] = {
                'High': 'danger',
                'Medium': 'warning',
                'Low': 'info'
            }.get(task.get('priority', ''), 'secondary')
            
        return tasks
    except Exception as e:
        print(f"Error loading tasks data: {str(e)}")
        return []

# Load Meetings Data with Error Handling
def load_meetings():
    try:
        print("Loading meetings data...")
        meetings_df = load_data("meetings")
        if meetings_df.empty:
            print("No meetings found in database")
            return []
            
        # Convert date strings to proper format if needed
        if 'date' in meetings_df.columns:
            meetings_df['date'] = meetings_df['date'].apply(
                lambda x: x if isinstance(x, str) else str(x) if x is not None else ''
            )
            
        # Convert time strings to proper format if needed
        if 'time' in meetings_df.columns:
            meetings_df['time'] = meetings_df['time'].apply(
                lambda x: x if isinstance(x, str) else str(x) if x is not None else ''
            )
            
        # Ensure participants is a string
        if 'participants' in meetings_df.columns:
            meetings_df['participants'] = meetings_df['participants'].apply(
                lambda x: x if isinstance(x, str) else ','.join(x) if isinstance(x, list) else ''
            )
            
        meetings_list = meetings_df.to_dict(orient='records')
        print(f"Loaded {len(meetings_list)} meetings")
        return meetings_list
    except Exception as e:
        print(f"Error loading meetings data: {str(e)}")
        import traceback
        traceback.print_exc()
        return []  # Return empty list on error

# Load Users Data with Error Handling
def load_users():
    try:
        users_df = load_data("users")
        if users_df.empty:
            return []
        return users_df.to_dict(orient='records')
    except Exception as e:
        print(f"Error loading users data: {str(e)}")
        return []

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@app.route('/index')
def index():
    if 'user' in session:
        return redirect(url_for('my_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Load users data
            users_df = load_data("users")
            if users_df.empty:
                flash('No users found. Please register first.', 'error')
                return redirect(url_for('register'))
            
            # Check if required columns exist
            required_columns = ['email', 'password', 'role', 'name']
            missing_columns = [col for col in required_columns if col not in users_df.columns]
            if missing_columns:
                print(f"Missing columns in users table: {missing_columns}")
                # Initialize missing columns
                for col in missing_columns:
                    users_df[col] = None
                save_data("users", users_df)
            
            # Find user
            user = users_df[(users_df['email'] == email) & (users_df['password'] == password)]
            
            if not user.empty:
                user_data = user.to_dict(orient='records')[0]
                
                # Update last login
                users_df.loc[users_df['email'] == email, 'last_login'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Update role to admin if srmist email
                if 'srmist' in email.lower() and user_data.get('role') != 'admin':
                    users_df.loc[users_df['email'] == email, 'role'] = 'admin'
                    users_df.loc[users_df['email'] == email, 'permissions'] = str(['basic_access', 'admin_access'])
                
                save_data("users", users_df)
                
                # Set session data
                session['user'] = email
                session['role'] = 'admin' if 'srmist' in email.lower() else user_data.get('role', 'user')
                session['user_id'] = user_data.get('id')
                session['permissions'] = ['basic_access', 'admin_access'] if 'srmist' in email.lower() else user_data.get('permissions', ['basic_access'])
                
                # Redirect based on role
                if 'srmist' in email.lower() or user_data.get('role') == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('my_dashboard'))
            else:
                flash('Invalid email or password', 'error')
                print(f"Login failed: Invalid credentials for email {email}.")

                return redirect(url_for('login'))
                
        except Exception as e:
            print(f"Error during login: {str(e)}")
            flash('An error occurred during login. Please try again.', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            name = request.form.get('name')
            skills = request.form.get('skills', '')
            department = request.form.get('department', '')
            
            
            # Validate required fields
            if not all([email, password, name]):
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('register'))
            
            # Set role based on email domain
            role = 'admin' if 'srmist' in email.lower() else 'user'
            
            # Load users data
            users_df = load_data("users")
            if users_df.empty:
                users_df = pd.DataFrame(columns=sheets["users"]["columns"])
            
            # Check if email already exists
            print(f"Checking if email {email} is already registered.")
            if not users_df[users_df['email'] == email].empty:
                flash('Email already registered', 'error')
                print(f"Registration failed: Email {email} is already registered.")
                return redirect(url_for('register'))
            
            # Create new user
            print(f"Creating new user: {email}")
            new_user = {
                'id': str(uuid.uuid4()),
                'email': email,
                'password': password,
                'name': name,
                'role': role,
                'skills': skills,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'last_login': None,
                'is_active': True,
                'department': department,
                'supervisor_id': None,
                'permissions': str(['basic_access', 'admin_access'] if role == 'admin' else ['basic_access'])
            }
            
            # Save the new user
            if save_user_data(email, new_user):
                flash('Registration successful! Please login.', 'success')
                print(f"User {email} registered successfully.")
                return redirect(url_for('login'))
            else:
                flash('Failed to save user data. Please try again.', 'error')
                return redirect(url_for('register'))
            
        except Exception as e:
            print(f"Error during registration: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Admin Routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    
    # Check if user is admin
    if not user_data or user_data.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('my_dashboard'))
    
    # Load all data
    projects = load_projects()
    tasks = load_tasks()
    users = load_users()
    meetings = load_meetings()
    
    # Calculate statistics
    total_projects = len(projects)
    active_projects = len([p for p in projects if p.get('status') == 'In Progress'])
    completed_projects = len([p for p in projects if p.get('status') == 'Completed'])
    total_users = len(users)
    active_users = len([u for u in users if u.get('is_active') == True])
    
    stats = {
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'total_users': total_users,
        'active_users': active_users,
        'active_projects_percentage': round((active_projects / total_projects * 100) if total_projects > 0 else 0, 1),
        'completed_projects_percentage': round((completed_projects / total_projects * 100) if total_projects > 0 else 0, 1),
        'active_users_percentage': round((active_users / total_users * 100) if total_users > 0 else 0, 1)
    }
    
    return render_template('admin_dashboard.html', 
                         user=user_data,
                         projects=projects,
                         tasks=tasks,
                         users=users,
                         meetings=meetings,
                         stats=stats,random=random)

@app.route('/team')
@login_required
def team():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if user_data.get('role') != 'admin':
        return redirect(url_for('my_dashboard'))
    users = load_users()
    return render_template('team_management.html', users=users)

@app.route('/projects')
@login_required
def projects():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if user_data and user_data.get('role') != 'admin':  
        return redirect(url_for('my_projects'))
    
    # Load projects data
    projects = load_projects()
    tasks = load_tasks()
    users = load_users()
    
    # Calculate project statistics
    total_projects = len(projects)
    active_projects = len([p for p in projects if p.get('status') == 'In Progress'])
    completed_projects = len([p for p in projects if p.get('status') == 'Completed'])
    on_hold_projects = len([p for p in projects if p.get('status') == 'On Hold'])
    not_started_projects = len([p for p in projects if p.get('status') == 'Not Started'])
    
    # Calculate task statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.get('status') == 'Completed'])
    
    # Calculate team member statistics
    total_members = len(users)
    active_members = len([u for u in users if u.get('is_active') == True])
    
    # Calculate percentages
    stats = {
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'total_projects': total_projects,
        'on_hold_projects': on_hold_projects,
        'not_started_projects': not_started_projects,
        'active_projects_percentage': round((active_projects / total_projects * 100) if total_projects > 0 else 0, 1),
        'completed_projects_percentage': round((completed_projects / total_projects * 100) if total_projects > 0 else 0, 1),
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'completed_tasks_percentage': round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1),
        'team_members': total_members,
        'active_members': active_members,
        'active_members_percentage': round((active_members / total_members * 100) if total_members > 0 else 0, 1)
    }
    
    # Calculate average progress
    total_progress = sum(float(p.get('progress', 0)) for p in projects)
    stats['average_progress'] = round(total_progress / total_projects, 1) if total_projects > 0 else 0
    
    return render_template('projects.html', projects=projects, stats=stats, users=users)

@app.route('/create_project', methods=['GET', 'POST'])
@login_required
def create_project():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        client_requirements = request.form.get('client_requirements')
        budget = request.form.get('budget')
        team_members = request.form.get('team_members', '')
        status = request.form.get('status', 'Not Started')
        due_date = request.form.get('due_date')  # NEW FIELD
        
        projects_df = load_data("projects")
        
        new_project = pd.DataFrame({
            'id': [str(len(projects_df) + 1)],
            'name': [name],
            'description': [description],
            'client_requirements': [client_requirements],
            'team_members': [team_members],
        'start_date': [datetime.now().strftime('%Y-%m-%d')],
        'end_date': [''],
        'due_date': [due_date],
        'status': [status],
        'progress': [0.0],
        'created_at': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        'updated_at': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        'manager_id': [session.get('user_id')],
        'budget': [float(budget) if budget else 0.0],
        'priority': ['Medium']
    })
    
        projects_df = pd.concat([projects_df, new_project], ignore_index=True)
        save_data("projects", projects_df)
        
        flash('Project created successfully!', 'success')
        return redirect(url_for('projects'))

        
    return render_template('create_project.html')

@app.route('/edit_project/<project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if user_data.get('role') != 'admin':
        return redirect(url_for('my_projects'))
    
    # Load projects data
    projects_df = load_data("projects")
    project = projects_df[projects_df['id'] == project_id]
    
    if project.empty:
        flash('Project not found', 'error')
        return redirect(url_for('projects'))
    
    if request.method == 'POST':
        # Update project data
        projects_df.loc[projects_df['id'] == project_id, 'name'] = request.form.get('name')
        projects_df.loc[projects_df['id'] == project_id, 'description'] = request.form.get('description')
        projects_df.loc[projects_df['id'] == project_id, 'client_requirements'] = request.form.get('client_requirements')
        projects_df.loc[projects_df['id'] == project_id, 'budget'] = request.form.get('budget')
        projects_df.loc[projects_df['id'] == project_id, 'team_members'] = request.form.get('team_members')
        projects_df.loc[projects_df['id'] == project_id, 'status'] = request.form.get('status')
        
        # Save changes
        save_data("projects", projects_df)
        
        flash('Project updated successfully!', 'success')
        return redirect(url_for('project_details', project_id=project_id))
    
    # GET request - show edit form
    project_data = project.to_dict('records')[0]
    return render_template('edit_project.html', project=project_data)

@app.route('/project/<project_id>')
@login_required
def project_details(project_id):
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    
    # Load project data
    projects_df = load_data("projects")
    project = projects_df[projects_df['id'] == project_id]
    
    if project.empty:
        flash('Project not found', 'error')
        return redirect(url_for('projects'))
    
    project_data = project.iloc[0].to_dict()
    
    # For non-admin users, check if they have access to this project
    if user_data.get('role') != 'admin':
        team_members = project_data.get('team_members', '')
        if isinstance(team_members, str):
            team_members = [member.strip() for member in team_members.split(',') if member.strip()]
        elif not isinstance(team_members, list):
            team_members = []
            
        if user_data['id'] not in team_members and project_data.get('manager_id') != user_data['id']:
            flash('Access denied. You do not have permission to view this project.', 'error')
            return redirect(url_for('my_projects'))
    
    # Load tasks for this project
    tasks_df = load_data("tasks")
    project_tasks = tasks_df[tasks_df['project_id'] == project_id]
    
    # For non-admin users, only show their assigned tasks
    if user_data.get('role') != 'admin':
        project_tasks = project_tasks[project_tasks['assigned_to'] == user_data['id']]
    
    # Convert tasks to list of dictionaries
    tasks = []
    for _, task in project_tasks.iterrows():
        task_dict = task.to_dict()
        
        # Add status and priority colors
        task_dict['status_color'] = {
            'Completed': 'success',
            'In Progress': 'primary',
            'To Do': 'warning',
            'On Hold': 'info'
        }.get(task_dict['status'], 'secondary')
        
        task_dict['priority_color'] = {
            'High': 'danger',
            'Medium': 'warning',
            'Low': 'info'
        }.get(task_dict['priority'], 'secondary')
        
        # Format the date
        due_date = task_dict.get('due_date', '')
        if due_date:
            try:
                # If it's already a datetime object
                if hasattr(due_date, 'strftime'):
                    task_dict['due_date'] = due_date
                else:
                    # If it's a string, convert to datetime
                    task_dict['due_date'] = datetime.datetime.strptime(due_date, '%Y-%m-%d')
            except:
                task_dict['due_date'] = due_date  # Keep as string if conversion fails
        
        tasks.append(task_dict)
    
    # Calculate project statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t['status'] == 'Completed'])
    in_progress_tasks = len([t for t in tasks if t['status'] == 'In Progress'])
    pending_tasks = len([t for t in tasks if t['status'] == 'To Do'])
    
    # Calculate project progress
    if total_tasks > 0:
        project_data['progress'] = round((completed_tasks / total_tasks) * 100, 1)
    else:
        project_data['progress'] = 0
    
    # Add task statistics to project data
    project_data['total_tasks'] = total_tasks
    project_data['completed_tasks'] = completed_tasks
    project_data['in_progress_tasks'] = in_progress_tasks
    project_data['pending_tasks'] = pending_tasks
    
    return render_template('project_details.html', 
                         project=project_data,
                         tasks=tasks,
                         user=user_data)

@app.route('/my_tasks')
@login_required
def my_tasks():
    """Display tasks assigned to the current user"""
    user_id = session.get('user_id')
    if not user_id:
        flash('User not found', 'error')
        return redirect(url_for('login'))
    
    # Load tasks, projects, and users
    tasks_df = load_data("tasks")
    projects_df = load_data("projects")
    
    # Filter tasks assigned to the current user
    user_tasks = tasks_df[tasks_df['assigned_to'] == user_id]
    
    # Process tasks to include required information
    processed_tasks = []
    for _, task in user_tasks.iterrows():
        task_data = task.to_dict()
        
        # Get project info
        project_id = task_data.get('project_id')
        if project_id:
            project = projects_df[projects_df['id'] == project_id]
            if not project.empty:
                project_data = project.iloc[0].to_dict()
                task_data['project_name'] = project_data.get('name', 'Unknown Project')
                task_data['project_progress'] = project_data.get('progress', 0)
            else:
                task_data['project_name'] = 'Unknown Project'
                task_data['project_progress'] = 0
        else:
            task_data['project_name'] = 'Unknown Project'
            task_data['project_progress'] = 0
        
        # Add status and priority colors
        task_data['status_color'] = {
            'Completed': 'success',
            'In Progress': 'primary',
            'To Do': 'warning',
            'On Hold': 'info'
        }.get(task_data.get('status'), 'secondary')
        
        task_data['priority_color'] = {
            'High': 'danger',
            'Medium': 'warning',
            'Low': 'info'
        }.get(task_data.get('priority'), 'secondary')
        
        processed_tasks.append(task_data)
    
    return render_template('my_tasks.html', 
                         tasks=processed_tasks,
                         projects=projects_df.to_dict('records') if not projects_df.empty else [])

@app.route('/tasks')
@login_required
def tasks():
    if session.get('role') != 'admin':
        return redirect(url_for('my_tasks'))

    # Load tasks, projects, and users
    tasks = load_tasks()
    projects = load_projects()
    users = load_users()

    # Convert projects and users into dictionaries for quick lookup
    project_dict = {project['id']: project['name'] for project in projects}
    user_dict = {user['id']: user['name'] for user in users}

    # Process each task
    processed_tasks = []
    for task in tasks:
        task_data = task.copy()
        task_data['project'] = {'name': project_dict.get(task.get('project_id'), 'Unknown Project')}
        task_data['assignee'] = {'name': user_dict.get(task.get('assigned_to'), 'Unassigned')}
        
        # Format the date
        due_date = task.get('due_date', '')
        if due_date:
            try:
                # If it's already a datetime object
                if hasattr(due_date, 'strftime'):
                    task_data['due_date'] = due_date
                else:
                    # If it's a string, convert to datetime
                    task_data['due_date'] = datetime.datetime.strptime(due_date, '%Y-%m-%d')
            except:
                task_data['due_date'] = due_date  # Keep as string if conversion fails
        
        # Add status and priority colors
        task_data['status_color'] = {
            'Completed': 'success',
            'In Progress': 'primary',
            'To Do': 'warning',
            'On Hold': 'info'
        }.get(task_data.get('status'), 'secondary')
        
        task_data['priority_color'] = {
            'High': 'danger',
            'Medium': 'warning',
            'Low': 'info'
        }.get(task_data.get('priority'), 'secondary')
        
        # Calculate skill match if task has an assignee
        if task_data.get('assigned_to'):
            assignee = next((u for u in users if u['id'] == task_data['assigned_to']), None)
            if assignee:
                # Handle assignee skills
                assignee_skills = assignee.get('skills', '')
                if isinstance(assignee_skills, (int, float)):
                    assignee_skills = str(assignee_skills)
                if isinstance(assignee_skills, str):
                    assignee_skills = [skill.strip() for skill in assignee_skills.split(',') if skill.strip()]
                elif not isinstance(assignee_skills, list):
                    assignee_skills = []
                
                # Handle required skills
                required_skills = task.get('required_skills', '')
                if isinstance(required_skills, (int, float)):
                    required_skills = str(required_skills)
                if isinstance(required_skills, str):
                    required_skills = [skill.strip() for skill in required_skills.split(',') if skill.strip()]
                elif not isinstance(required_skills, list):
                    required_skills = []
                
                # Calculate skill match
                if required_skills and assignee_skills:
                    matching_skills = set(required_skills) & set(assignee_skills)
                    task_data['skill_match_percentage'] = round((len(matching_skills) / len(required_skills)) * 100, 1)
                    task_data['matching_skills'] = list(matching_skills)
                else:
                    task_data['skill_match_percentage'] = 0
                    task_data['matching_skills'] = []
        
        processed_tasks.append(task_data)

    return render_template('tasks.html', tasks=processed_tasks, projects=projects, users=users)

@app.route('/my_tasks')
@login_required
def my_tasks():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    
    # Load tasks and projects data
    tasks_df = load_data("tasks")
    projects_df = load_data("projects")
    
    # Filter tasks for current user
    if user_data.get('role') == 'admin':
        user_tasks = tasks_df
    else:
        user_tasks = tasks_df[tasks_df['assigned_to'] == user_data['id']]  # Use user_id instead of email
    
    # Convert tasks to list of dictionaries with project info
    tasks = []
    for _, task in user_tasks.iterrows():
        task_dict = task.to_dict()
        
        # Get project info
        project = projects_df[projects_df['id'] == task['project_id']]
        if not project.empty:
            project_data = project.iloc[0].to_dict()
            task_dict['project_name'] = project_data['name']
            task_dict['project_progress'] = project_data.get('progress', 0)
        else:
            task_dict['project_name'] = 'Unknown Project'
            task_dict['project_progress'] = 0
            
        # Add status and priority colors
        task_dict['status_color'] = {
            'Completed': 'success',
            'In Progress': 'primary',
            'To Do': 'warning',
            'On Hold': 'info'
        }.get(task_dict['status'], 'secondary')
        
        task_dict['priority_color'] = {
            'High': 'danger',
            'Medium': 'warning',
            'Low': 'info'
        }.get(task_dict['priority'], 'secondary')
        
        # Format the date
        due_date = task_dict.get('due_date', '')
        if due_date:
            try:
                # If it's already a datetime object
                if hasattr(due_date, 'strftime'):
                    task_dict['due_date'] = due_date
                else:
                    # If it's a string, convert to datetime
                    task_dict['due_date'] = datetime.datetime.strptime(due_date, '%Y-%m-%d')
            except:
                task_dict['due_date'] = due_date  # Keep as string if conversion fails
        
        tasks.append(task_dict)
    
    return render_template('my_tasks.html', user=user_data, tasks=tasks, projects=projects_df.to_dict('records'))

@app.route('/meetings')
@login_required
def meetings():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    
    # Load meetings data
    meetings_df = load_data("meetings")
    projects_df = load_data("projects")
    users_df = load_data("users")
    
    print(f"Meetings data loaded. Shape: {meetings_df.shape}")
    
    # Convert meetings to list of dictionaries with project and user info
    meetings = []
    
    # Check if meetings dataframe is empty
    if meetings_df.empty:
        print("No meetings found in database")
        return render_template('meetings.html', 
                             meetings=[], 
                             projects=projects_df.to_dict('records'),
                             users=users_df.to_dict('records'))
    
    for _, meeting in meetings_df.iterrows():
        meeting_dict = meeting.to_dict()
        print(f"Processing meeting: {meeting_dict.get('title', 'Untitled')}")
        
        # Get project info
        project = projects_df[projects_df['id'] == meeting['project_id']]
        if not project.empty:
            project_data = project.iloc[0].to_dict()
            
            # For non-admin users, check if they're part of the project or the meeting
            if user_data.get('role') != 'admin':
                # Check if user is a participant in the meeting
                is_participant = False
                
                # Check if user is the organizer
                if meeting.get('organizer_id') == user_data['id']:
                    is_participant = True
                
                # Check if user is in participants list
                if not is_participant and 'participants' in meeting:
                    participants = meeting['participants']
                    if isinstance(participants, str) and participants.strip():
                        participant_ids = [p.strip() for p in participants.split(',') if p.strip()]
                        if user_data['id'] in participant_ids:
                            is_participant = True
                    elif isinstance(participants, list) and user_data['id'] in participants:
                        is_participant = True
                
                # Check if user is in project team
                if not is_participant:
                    team_members = project_data.get('team_members', '')
                    if isinstance(team_members, str):
                        team_members = [member.strip() for member in team_members.split(',') if member.strip()]
                    elif not isinstance(team_members, list):
                        team_members = []
                    
                    if user_data['id'] in team_members or project_data.get('manager_id') == user_data['id']:
                        is_participant = True
                
                # Skip this meeting if user is not a participant
                if not is_participant:
                    continue
            
            meeting_dict['project'] = project_data
            meeting_dict['project_name'] = project_data['name']
        else:
            meeting_dict['project'] = {'name': 'Unknown Project'}
            meeting_dict['project_name'] = 'Unknown Project'
            
        # Get organizer info
        organizer = users_df[users_df['id'] == meeting['organizer_id']]
        if not organizer.empty:
            meeting_dict['organizer'] = organizer.iloc[0].to_dict()
        else:
            meeting_dict['organizer'] = {'name': 'Unknown User'}
            
        # Get participants info
        if 'participants' in meeting_dict:
            if isinstance(meeting_dict['participants'], str) and meeting_dict['participants'].strip():
                participant_ids = [p.strip() for p in meeting_dict['participants'].split(',') if p.strip()]
                participants = []
                for pid in participant_ids:
                    participant = users_df[users_df['id'] == pid]
                    if not participant.empty:
                        participants.append(participant.iloc[0].to_dict())
                meeting_dict['participant_details'] = participants
            elif isinstance(meeting_dict['participants'], list):
                participants = []
                for pid in meeting_dict['participants']:
                    participant = users_df[users_df['id'] == pid]
                    if not participant.empty:
                        participants.append(participant.iloc[0].to_dict())
                meeting_dict['participant_details'] = participants
            else:
                meeting_dict['participant_details'] = []
        else:
            meeting_dict['participant_details'] = []
            meeting_dict['participants'] = ''
            
        # Ensure all required fields are present
        meeting_dict['title'] = meeting_dict.get('title', 'Untitled Meeting')
        meeting_dict['duration'] = meeting_dict.get('duration', '60') + ' minutes'
        meeting_dict['meeting_date'] = meeting_dict.get('date', '')
        meeting_dict['meeting_time'] = meeting_dict.get('time', '')
        meeting_dict['agenda'] = meeting_dict.get('agenda', 'No agenda set')
        meeting_dict['status'] = meeting_dict.get('status', 'Scheduled')
        
        # Add status color
        status_colors = {
            'Scheduled': 'primary',
            'In Progress': 'success',
            'Completed': 'info',
            'Cancelled': 'danger'
        }
        meeting_dict['status_color'] = status_colors.get(meeting_dict['status'], 'secondary')
        
        meetings.append(meeting_dict)
    
    return render_template('meetings.html', 
                         meetings=meetings, 
                         projects=projects_df.to_dict('records'),
                         users=users_df.to_dict('records'))

@app.route('/my_meetings')
@login_required
def my_meetings():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    
    # Load meetings data
    meetings_df = load_data("meetings")
    projects_df = load_data("projects")
    users_df = load_data("users")
    
    # Filter meetings for current user
    user_meetings = []
    for _, meeting in meetings_df.iterrows():
        # Check if user is organizer or participant
        is_participant = False
        if meeting['organizer_id'] == user_data['id']:
            is_participant = True
        elif isinstance(meeting.get('participants'), str) and meeting.get('participants').strip():
            if user_data['id'] in [p.strip() for p in meeting['participants'].split(',') if p.strip()]:
                is_participant = True
        elif isinstance(meeting.get('participants'), list):
            if user_data['id'] in meeting.get('participants'):
                is_participant = True
                
        if is_participant:
            meeting_dict = meeting.to_dict()
            
            # Get project info
            project = projects_df[projects_df['id'] == meeting['project_id']]
            if not project.empty:
                project_data = project.iloc[0].to_dict()
                # We don't need to filter by project team membership here
                # since we already filtered by meeting participation
                meeting_dict['project_name'] = project_data.get('name', 'Unknown Project')
                
                meeting_dict['project'] = project_data
            else:
                meeting_dict['project'] = {'name': 'Unknown Project'}
                
            # Get organizer info
            organizer = users_df[users_df['id'] == meeting['organizer_id']]
            if not organizer.empty:
                meeting_dict['organizer'] = organizer.iloc[0].to_dict()
            else:
                meeting_dict['organizer'] = {'name': 'Unknown User'}
                
            # Ensure all required fields are present
            meeting_dict['title'] = meeting_dict.get('title', 'Untitled Meeting')
            meeting_dict['duration'] = meeting_dict.get('duration', '60') + ' minutes'
            meeting_dict['meeting_date'] = meeting_dict.get('date', '')
            meeting_dict['meeting_time'] = meeting_dict.get('time', '')
            meeting_dict['agenda'] = meeting_dict.get('agenda', 'No agenda set')
            meeting_dict['status'] = meeting_dict.get('status', 'Scheduled')
            
            # Add status color
            status_colors = {
                'Scheduled': 'primary',
                'In Progress': 'success',
                'Completed': 'info',
                'Cancelled': 'danger'
            }
            meeting_dict['status_color'] = status_colors.get(meeting_dict['status'], 'secondary')
            
            user_meetings.append(meeting_dict)
    
    # Load users for the template
    return render_template('user_meetings.html', 
                         meetings=user_meetings,
                         projects=projects_df.to_dict('records'),
                         users=users_df.to_dict('records'))

@app.route('/team_management')
@login_required
def team_management():
    if session.get('role') != 'admin':
        return redirect(url_for('my_dashboard'))
    users = load_users()
    return render_template('team_management.html', users=users)

@app.route('/reports')
@login_required
def reports():
    if session.get('role') != 'admin':
        return redirect(url_for('my_dashboard'))
    projects = load_projects()
    tasks = load_tasks()
    return render_template('reports.html', projects=projects, tasks=tasks)

# User Routes
@app.route('/my_dashboard')
@login_required
def my_dashboard():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    
    # Load all data
    projects_df = load_data("projects")
    tasks_df = load_data("tasks")
    meetings_df = load_data("meetings")
    
    # Get all projects for the user
    user_projects = []
    for _, project in projects_df.iterrows():
        project_dict = project.to_dict()
        
        # Add status color
        status_colors = {
            'Not Started': 'secondary',
            'In Progress': 'primary',
            'On Hold': 'warning',
            'Completed': 'success'
        }
        project_dict['status_color'] = status_colors.get(project_dict.get('status', 'Not Started'), 'secondary')
        
        # Get tasks for this project assigned to the user
        project_tasks = tasks_df[
            (tasks_df['project_id'] == project_dict['id']) & 
            (tasks_df['assigned_to'] == user_data['id'])
        ]
        
        # Calculate task statistics
        total_tasks = len(project_tasks)
        completed_tasks = len(project_tasks[project_tasks['status'] == 'Completed'])
        
        project_dict['total_tasks'] = total_tasks
        project_dict['completed_tasks'] = completed_tasks
        project_dict['progress'] = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        user_projects.append(project_dict)
    
    # Get user's tasks using the enhanced load_tasks function
    all_tasks = load_tasks()
    user_tasks = [task for task in all_tasks if task.get('assigned_to') == user_data['id']]
    
    # Get user's meetings
    user_meetings = []
    for _, meeting in meetings_df.iterrows():
        participants = meeting.get('participants', '')
        if isinstance(participants, str):
            participants = [p.strip() for p in participants.split(',') if p.strip()]
        elif not isinstance(participants, list):
            participants = []
        
        if user_data['id'] in participants or meeting.get('organizer_id') == user_data['id']:
            meeting_dict = meeting.to_dict()
            meeting_dict['status_color'] = {
                'Scheduled': 'primary',
                'In Progress': 'success',
                'Completed': 'info',
                'Cancelled': 'danger'
            }.get(meeting_dict.get('status'), 'secondary')
            user_meetings.append(meeting_dict)
    
    # Calculate overall statistics
    stats = {
        'total_projects': len(user_projects),
        'active_projects': len([p for p in user_projects if p['status'] == 'In Progress']),
        'total_tasks': len(user_tasks),
        'completed_tasks': len([t for t in user_tasks if t['status'] == 'Completed']),
        'upcoming_meetings': len([m for m in user_meetings if m['status'] == 'Scheduled']),
        'project_progress': sum(p['progress'] for p in user_projects) / len(user_projects) if user_projects else 0
    }
    
    return render_template('user_dashboard.html', 
                         user=user_data, 
                         projects=user_projects, 
                         tasks=user_tasks, 
                         meetings=user_meetings,
                         stats=stats)

@app.route('/my_projects')
@login_required
def my_projects():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    
    # Load projects and tasks data
    projects_df = load_data("projects")
    tasks_df = load_data("tasks")
    
    # If user is admin, show all projects
    if user_data.get('role') == 'admin':
        user_projects = projects_df.to_dict('records')
    else:
        # For regular users, show all projects
        user_projects = []
        for _, project in projects_df.iterrows():
            project_dict = project.to_dict()
            
            # Add status color
            status_colors = {
                'Not Started': 'secondary',
                'In Progress': 'primary',
                'On Hold': 'warning',
                'Completed': 'success'
            }
            project_dict['status_color'] = status_colors.get(project_dict.get('status', 'Not Started'), 'secondary')
            
            # Add priority color
            priority_colors = {
                'High': 'danger',
                'Medium': 'warning',
                'Low': 'info'
            }
            project_dict['priority_color'] = priority_colors.get(project_dict.get('priority', 'Medium'), 'warning')
            
            # Get tasks for this project assigned to the user
            project_tasks = tasks_df[
                (tasks_df['project_id'] == project_dict['id']) & 
                (tasks_df['assigned_to'] == user_data['id'])
            ]
            
            # Convert tasks to list of dictionaries with status colors
            tasks = []
            for _, task in project_tasks.iterrows():
                task_dict = task.to_dict()
                task_dict['status_color'] = status_colors.get(task_dict.get('status', 'Not Started'), 'secondary')
                task_dict['priority_color'] = priority_colors.get(task_dict.get('priority', 'Medium'), 'warning')
                tasks.append(task_dict)
            
            project_dict['tasks'] = tasks
            project_dict['total_tasks'] = len(tasks)
            project_dict['completed_tasks'] = len([t for t in tasks if t['status'] == 'Completed'])
            project_dict['progress'] = (project_dict['completed_tasks'] / project_dict['total_tasks'] * 100) if project_dict['total_tasks'] > 0 else 0
            
            user_projects.append(project_dict)
    
    return render_template('my_projects.html', user=user_data, projects=user_projects)

@app.route('/my_timeline')
@login_required
def my_timeline():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    projects = load_projects()
    tasks = load_tasks()
    meetings = load_meetings()
    user_activities = []
    
    for project in projects:
        # Convert team_members to list if it's a string or float
        team_members = project.get('team_members', '')
        if isinstance(team_members, str):
            team_members = [member.strip() for member in team_members.split(',') if member.strip()]
        elif isinstance(team_members, float):
            team_members = []
        elif not isinstance(team_members, list):
            team_members = []
            
        if user_email in team_members:
            user_activities.append({
                'type': 'project',
                'title': project['name'],
                'date': project.get('start_date', ''),
                'status': project.get('status', 'Not Started')
            })
            
    for task in tasks:
        if task.get('assigned_to') == user_email:
            user_activities.append({
                'type': 'task',
                'title': task.get('task_name', ''),
                'date': task.get('due_date', ''),
                'status': task.get('status', 'Not Started')
            })
            
    for meeting in meetings:
        # Convert participants to list if it's a string or float
        participants = meeting.get('participants', '')
        if isinstance(participants, str):
            participants = [p.strip() for p in participants.split(',') if p.strip()]
        elif isinstance(participants, float):
            participants = []
        elif not isinstance(participants, list):
            participants = []
            
        if user_email in participants:
            user_activities.append({
                'type': 'meeting',
                'title': meeting.get('title', ''),
                'date': meeting.get('date', ''),
                'status': 'scheduled'
            })
            
    return render_template('user_timeline.html', user=user_data, activities=user_activities)

@app.route('/chatbot')
@login_required
def chatbot():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    
    # Get user's skills and current projects
    user_skills = user_data.get('skills', '') if user_data else ''
    projects = load_projects()
    tasks = load_tasks()
    user_projects = []
    user_tasks = []
    
    # Get user's projects and tasks
    for project in projects:
        team_members = project.get('team_members', '')
        if isinstance(team_members, str):
            team_members = [member.strip() for member in team_members.split(',') if member.strip()]
        elif isinstance(team_members, float):
            team_members = []
        elif not isinstance(team_members, list):
            team_members = []
            
        if user_email in team_members:
            user_projects.append(project)
            # Get tasks for this project
            project_tasks = [t for t in tasks if t.get('project_id') == project['id']]
            user_tasks.extend(project_tasks)
    
    # Calculate task statistics
    total_tasks = len(user_tasks)
    completed_tasks = len([t for t in user_tasks if t.get('status') == 'Completed'])
    in_progress_tasks = len([t for t in user_tasks if t.get('status') == 'In Progress'])
    pending_tasks = len([t for t in user_tasks if t.get('status') == 'To Do'])
    
    # Calculate project statistics
    total_projects = len(user_projects)
    active_projects = len([p for p in user_projects if p.get('status') == 'In Progress'])
    completed_projects = len([p for p in user_projects if p.get('status') == 'Completed'])
    
    # Prepare context for Gemini API
    context = {
        'user_skills': user_skills,
        'user_projects': user_projects,
        'user_tasks': user_tasks,
        'all_projects': projects,
        'user_role': user_data.get('role', 'user') if user_data else 'user',
        'user_department': user_data.get('department', '') if user_data else '',
        'task_stats': {
            'total': total_tasks,
            'completed': completed_tasks,
            'in_progress': in_progress_tasks,
            'pending': pending_tasks,
            'completion_rate': round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
        },
        'project_stats': {
            'total': total_projects,
            'active': active_projects,
            'completed': completed_projects,
            'completion_rate': round((completed_projects / total_projects * 100) if total_projects > 0 else 0, 1)
        }
    }
    
    return render_template('chatbot.html', user=user_data, context=context)

@app.route('/chatbot/query', methods=['POST'])
@login_required
def chatbot_query():
    user_query = request.json.get('query')
    if not user_query:
        return jsonify({'error': 'No query provided'}), 400
    
    try:
        # Get user context
        user_email = session.get('user')
        user_data = load_user_data(user_email)
        user_skills = user_data.get('skills', '') if user_data else ''
        user_role = user_data.get('role', 'user') if user_data else 'user'
        user_department = user_data.get('department', '') if user_data else ''

        # Get user's projects and tasks
        projects = load_projects()
        tasks = load_tasks()
        user_projects = []
        user_tasks = []
        
        for project in projects:
            team_members = project.get('team_members', '')
            if isinstance(team_members, str):
                team_members = [member.strip() for member in team_members.split(',') if member.strip()]
            if user_email in team_members:
                user_projects.append(project)
                project_tasks = [t for t in tasks if t.get('project_id') == project['id']]
                user_tasks.extend(project_tasks)

        # Calculate task statistics
        total_tasks = len(user_tasks)
        completed_tasks = len([t for t in user_tasks if t.get('status') == 'Completed'])
        in_progress_tasks = len([t for t in user_tasks if t.get('status') == 'In Progress'])
        pending_tasks = len([t for t in user_tasks if t.get('status') == 'To Do'])

        # Prepare a more detailed prompt
        prompt = f"""
        As an AI project management assistant, help with the following query: "{user_query}"
        
        User Context:
        - Role: {user_role}
        - Department: {user_department}
        - Skills: {user_skills}
        - Number of Active Projects: {len(user_projects)}

        Current Projects:
        {[{'name': p['name'], 'status': p['status'], 'progress': p['progress']} for p in user_projects]}

        Task Statistics:
        - Total Tasks: {total_tasks}
        - Completed: {completed_tasks}
        - In Progress: {in_progress_tasks}
        - Pending: {pending_tasks}
        - Completion Rate: {round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)}%
        
        Consider:
        1. User's role and permissions
        2. Project management best practices
        3. User's skills and experience
        4. Current project status and progress
        5. Task completion rates and workload
        6. Industry guidelines
        7. Team collaboration aspects
        8. Time management and prioritization

        Provide:
        1. A clear, actionable answer
        2. Relevant examples or references
        3. Next steps or recommendations
        4. Any potential risks or considerations
        5. Specific task or project suggestions based on user's skills
        6. Time management tips if relevant
        7. Team collaboration suggestions if applicable
        """

        # Generate response using Gemini
        response = model.generate_content(prompt)
        
        if response and hasattr(response, 'text'):
            # Format the response for better readability
            answer = response.text.replace('\n', '<br>')
            
            # Save the conversation
            conversations_df = load_data("conversations")
            new_conversation = pd.DataFrame({
                'id': [str(uuid.uuid4())],
                'project_id': [None],  # Can be updated if query is project-specific
                'user_id': [user_email],
                'message': [user_query],
                'created_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                'updated_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                'is_read': [True]
            })
            
            if conversations_df.empty:
                conversations_df = pd.DataFrame(columns=sheets["conversations"]["columns"])
            
            conversations_df = pd.concat([conversations_df, new_conversation], ignore_index=True)
            save_data("conversations", conversations_df)
            
            return jsonify({'answer': answer})
        else:
            return jsonify({'error': 'Failed to generate response'}), 500
            
    except Exception as e:
        print(f"Chatbot error: {e}")
        return jsonify({'error': 'Chatbot service is down'}), 500

# Common Routes
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    
    if request.method == 'POST':
        try:
            # Handle resume upload
            if 'resume' in request.files:
                file = request.files['resume']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{user_email}_{file.filename}")
                    if not os.path.exists(UPLOAD_FOLDER):
                        os.makedirs(UPLOAD_FOLDER)
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    
                    # Extract skills from resume
                    extracted_skills = extract_skills_from_pdf(file_path)
                    
                    # Update user data with resume path and extracted skills
                    users_df = load_data("users")
                    users_df.loc[users_df['email'] == user_email, 'resume_path'] = file_path
                    
                    # Combine extracted skills with manually entered skills
                    manual_skills = [skill.strip() for skill in request.form.get('skills', '').split(',') if skill.strip()]
                    all_skills = list(set(extracted_skills + manual_skills))
                    users_df.loc[users_df['email'] == user_email, 'skills'] = ','.join(all_skills)
                    
                    save_data("users", users_df)
                    flash('Resume uploaded and skills extracted successfully!', 'success')
                else:
                    flash('Invalid file type. Please upload a PDF file.', 'error')
            
            # Handle other profile updates
            users_df = load_data("users")
            users_df.loc[users_df['email'] == user_email, 'name'] = request.form.get('name')
            users_df.loc[users_df['email'] == user_email, 'department'] = request.form.get('department')
            
            # Handle password change
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if current_password and new_password and confirm_password:
                if current_password == user_data['password']:
                    if new_password == confirm_password:
                        users_df.loc[users_df['email'] == user_email, 'password'] = new_password
                        flash('Password updated successfully!', 'success')
                    else:
                        flash('New passwords do not match.', 'error')
                else:
                    flash('Current password is incorrect.', 'error')
            
            save_data("users", users_df)
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            print(f"Error updating profile: {str(e)}")
            flash('An error occurred while updating your profile.', 'error')
            return redirect(url_for('profile'))
    
    return render_template('profile.html', user=user_data)

@app.route('/download_resume')
@login_required
def download_resume():
    user_id = request.args.get('user_id')
    
    if user_id:
        # Load users data
        users_df = load_data("users")
        user_row = users_df[users_df['id'] == user_id]
        
        if user_row.empty:
            flash('User not found.', 'error')
            return redirect(url_for('profile'))
            
        user_data = user_row.iloc[0].to_dict()
    else:
        # Default to current user
        user_email = session.get('user')
        user_data = load_user_data(user_email)
    
    if not user_data or 'resume_path' not in user_data or not user_data['resume_path']:
        flash('No resume found.', 'error')
        return redirect(url_for('profile'))
    
    try:
        return send_file(
            user_data['resume_path'],
            as_attachment=True,
            download_name=os.path.basename(user_data['resume_path'])
        )
    except Exception as e:
        print(f"Error downloading resume: {str(e)}")
        flash('Error downloading resume.', 'error')
        return redirect(url_for('profile'))

@app.route('/settings')
@login_required
def settings():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if not user_data:
        flash('User not found', 'error')
        return redirect(url_for('login'))
        
    # Default settings
    default_settings = {
        'site_name': 'Project Management System',
        'admin_email': user_email,
        'timezone': 'UTC',
        'date_format': 'MM/DD/YYYY',
        'session_timeout': 30,
        'max_login_attempts': 5,
        'password_expiry': 90,
        'min_password_length': 8,
        'require_2fa': False,
        'email_task_updates': True,
        'email_project_updates': True,
        'email_meeting_reminders': True,
        'in_app_task_updates': True,
        'in_app_project_updates': True,
        'in_app_meeting_reminders': True,
        'google_calendar': False,
        'outlook_calendar': False,
        'google_drive': False,
        'dropbox': False,
        'slack': False,
        'teams': False
    }
    
    return render_template('settings.html', user=user_data, settings=default_settings)

@app.route('/users')
@login_required
def users():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if user_data.get('role') != 'admin':
        return redirect(url_for('my_dashboard'))
    users = load_users()
    return render_template('users.html', users=users)

@app.route('/delete_user/<email>', methods=['POST'])
@login_required
def delete_user(email):
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if user_data.get('role') != 'admin':
        return redirect(url_for('my_dashboard'))
        
    # Load users
    users_df = load_data("users")
    
    # Remove the user
    users_df = users_df[users_df['email'] != email]
    save_data("users", users_df)
    
    flash('User deleted successfully!', 'success')
    return redirect(url_for('users'))

@app.route('/edit_user/<email>', methods=['GET', 'POST'])
@login_required
def edit_user(email):
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if user_data.get('role') != 'admin':
        return redirect(url_for('my_dashboard'))
        
    # Load users
    users_df = load_data("users")
    user_to_edit = users_df[users_df['email'] == email]
    
    if user_to_edit.empty:
        flash('User not found', 'error')
        return redirect(url_for('team_management'))
        
    if request.method == 'POST':
        # Update user data
        users_df.loc[users_df['email'] == email, 'name'] = request.form.get('name')
        users_df.loc[users_df['email'] == email, 'role'] = request.form.get('role')
        users_df.loc[users_df['email'] == email, 'skills'] = request.form.get('skills')
        
        # Save changes
        save_data("users", users_df)
        
        flash('User updated successfully!', 'success')
        return redirect(url_for('team_management'))
        
    return render_template('edit_user.html', user=user_to_edit.iloc[0].to_dict())

@app.route('/create_task', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        try:
            # Get form data
            title = request.form.get('title')
            description = request.form.get('description')
            project_id = request.form.get('project_id')
            assigned_to = request.form.get('assigned_to')
            due_date = request.form.get('due_date')
            priority = request.form.get('priority', 'Medium')
            estimated_hours = float(request.form.get('estimated_hours', 0) or 0)
            required_skills = request.form.get('required_skills', '')
            
            # Debug information
            print(f"Creating task with: title={title}, project_id={project_id}, assigned_to={assigned_to}, due_date={due_date}")
            
            # Validate required fields
            if not all([title, project_id, assigned_to, due_date]):
                missing_fields = []
                if not title: missing_fields.append("Title")
                if not project_id: missing_fields.append("Project")
                if not assigned_to: missing_fields.append("Assignee")
                if not due_date: missing_fields.append("Due Date")
                
                flash(f'Please fill in all required fields: {", ".join(missing_fields)}', 'error')
                return redirect(url_for('create_task'))
            
            # Get assignee's skills
            users_df = load_data("users")
            assignee = users_df[users_df['id'] == assigned_to]
            if not assignee.empty:
                assignee_skills = assignee['skills'].iloc[0]
                if isinstance(assignee_skills, str):
                    assignee_skills = [skill.strip().lower() for skill in assignee_skills.split(',') if skill.strip()]
                else:
                    assignee_skills = []
            else:
                assignee_skills = []
            
            # Convert required skills to list
            required_skills_list = [skill.strip().lower() for skill in required_skills.split(',') if skill.strip()]
            
            # Calculate skill match percentage
            if required_skills_list and assignee_skills:
                matching_skills = set(required_skills_list) & set(assignee_skills)
                skill_match_percentage = (len(matching_skills) / len(required_skills_list)) * 100
                
                # If skill match is low, find better matches
                if skill_match_percentage < 50:
                    better_matches = []
                    for _, user in users_df.iterrows():
                        if user['id'] != assigned_to:
                            user_skills = user['skills']
                            if isinstance(user_skills, str):
                                user_skills = [skill.strip().lower() for skill in user_skills.split(',') if skill.strip()]
                            else:
                                user_skills = []
                            
                            user_matching_skills = set(required_skills_list) & set(user_skills)
                            user_skill_match = (len(user_matching_skills) / len(required_skills_list)) * 100
                            
                            if user_skill_match > skill_match_percentage:
                                better_matches.append({
                                    'user_id': user['id'],
                                    'name': user['name'],
                                    'match_percentage': user_skill_match,
                                    'matching_skills': list(user_matching_skills),
                                    'missing_skills': list(set(required_skills_list) - set(user_skills))
                                })
                    
                    # Sort better matches by match percentage
                    better_matches.sort(key=lambda x: x['match_percentage'], reverse=True)
                    
                    # Store recommendations in session for display
                    session['task_recommendations'] = {
                        'current_match': {
                            'percentage': skill_match_percentage,
                            'matching_skills': list(matching_skills),
                            'missing_skills': list(set(required_skills_list) - set(assignee_skills))
                        },
                        'better_matches': better_matches[:3]  # Top 3 matches
                    }
                    
                    # Create notifications for better matches
                    if better_matches:
                        notifications_df = load_data("notifications")
                        for match in better_matches[:3]:  # Top 3 matches
                            new_notification = pd.DataFrame({
                                'id': [str(uuid.uuid4())],
                                'user_id': [session.get('user_id')],  # Notify task creator
                                'title': ['Better Task Assignment Available'],
                                'message': [f'User {match["name"]} has a better skill match ({match["match_percentage"]:.1f}%) for task "{title}". Matching skills: {", ".join(match["matching_skills"])}'],
                                'type': ['task_recommendation'],
                                'created_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                                'read': [False],
                                'action_url': [f'/edit_task/{title}']
                            })
                            notifications_df = pd.concat([notifications_df, new_notification], ignore_index=True)
                        save_data("notifications", notifications_df)
            
            # Create new task
            tasks_df = load_data("tasks")
            
            # Generate a unique ID for the task
            task_id = str(uuid.uuid4())
            print(f"Generated task ID: {task_id}")
            
            # Create the new task DataFrame
            new_task = pd.DataFrame({
                'id': [task_id],
                'project_id': [project_id],
                'title': [title],
                'description': [description],
                'assigned_to': [assigned_to],
                'status': ['To Do'],
                'priority': [priority],
                'due_date': [due_date],
                'created_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                'updated_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                'progress': [0.0],
                'estimated_hours': [estimated_hours],
                'actual_hours': [0.0],
                'required_skills': [required_skills]
            })
            
            print(f"New task data: {new_task.to_dict('records')}")
            
            # Add to DataFrame
            try:
                tasks_df = pd.concat([tasks_df, new_task], ignore_index=True)
                print(f"Task added to DataFrame, now saving...")
                save_data("tasks", tasks_df)
                print(f"Task saved successfully")
            except Exception as e:
                print(f"Error saving task: {str(e)}")
                raise
            
            # Create notification for assigned user
            notifications_df = load_data("notifications")
            new_notification = pd.DataFrame({
                'id': [str(uuid.uuid4())],
                'user_id': [assigned_to],
                'title': ['New Task Assigned'],
                'message': [f'You have been assigned a new task: {title}'],
                'type': ['task_assignment'],
                'created_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                'read': [False],
                'action_url': [f'/task_details/{new_task["id"].iloc[0]}']
            })
            notifications_df = pd.concat([notifications_df, new_notification], ignore_index=True)
            save_data("notifications", notifications_df)
            
            flash('Task created successfully!', 'success')
            return redirect(url_for('tasks'))
            
        except Exception as e:
            print(f"Error creating task: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Failed to create task: {str(e)}', 'error')
            return redirect(url_for('create_task'))
    
    # GET request - show create task form
    projects = load_projects()
    users = load_users()
    
    # Get any stored recommendations
    recommendations = session.pop('task_recommendations', None)
    
    return render_template('create_task.html', 
                         projects=projects, 
                         users=users,
                         recommendations=recommendations)

@app.route('/notifications')
@login_required
def notifications():
    """Display user's notifications"""
    user_id = session.get('user_id')
    notifications_df = load_data("notifications")
    
    # Filter notifications for current user and sort by created_at
    user_notifications = notifications_df[
        notifications_df['user_id'] == user_id
    ].sort_values('created_at', ascending=False).to_dict('records')
    
    return render_template('notifications.html', notifications=user_notifications)

@app.route('/notifications/<notification_id>')
@login_required
def view_notification(notification_id):
    """View a specific notification"""
    user_id = session.get('user_id')
    notifications_df = load_data("notifications")
    
    # Find the notification
    notification = notifications_df[
        (notifications_df['id'] == notification_id) & 
        (notifications_df['user_id'] == user_id)
    ]
    
    if notification.empty:
        abort(404)
    
    # Mark as read
    notifications_df.loc[
        (notifications_df['id'] == notification_id) & 
        (notifications_df['user_id'] == user_id),
        'read'
    ] = True
    
    save_data("notifications", notifications_df)
    
    return render_template('view_notification.html', 
                         notification=notification.to_dict('records')[0])

@app.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    user_id = session.get('user_id')
    notifications_df = load_data("notifications")
    
    # Mark all user's notifications as read
    notifications_df.loc[
        (notifications_df['user_id'] == user_id) & 
        (notifications_df['read'] == False),
        'read'
    ] = True
    
    save_data("notifications", notifications_df)
    return jsonify({'success': True})

@app.route('/notifications/delete/<notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """Delete a notification"""
    user_id = session.get('user_id')
    notifications_df = load_data("notifications")
    
    # Delete the notification
    notifications_df = notifications_df[
        ~((notifications_df['id'] == notification_id) & 
          (notifications_df['user_id'] == user_id))
    ]
    
    save_data("notifications", notifications_df)
    return jsonify({'success': True})

def save_notification(notification_data):
    """Save a notification to the database"""
    try:
        notifications_df = load_data("notifications")
        new_notification = pd.DataFrame([notification_data])
        notifications_df = pd.concat([notifications_df, new_notification], ignore_index=True)
        save_data("notifications", notifications_df)
        return True
    except Exception as e:
        print(f"Error saving notification: {str(e)}")
        return False

def create_notification(user_id, title, message, notification_type='info', 
                       related_id=None, related_type=None, priority='normal', 
                       action_url=None):
    """Helper function to create a notification"""
    try:
        notification_data = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'title': title,
            'message': message,
            'type': notification_type,
            'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'read': False,
            'related_id': related_id,
            'related_type': related_type,
            'priority': priority,
            'action_url': action_url
        }
        
        return save_notification(notification_data)
    except Exception as e:
        print(f"Error creating notification: {str(e)}")
        return False

# Admin Routes
@app.route('/admin/user_permissions/<user_id>', methods=['GET'])
@login_required
def get_user_permissions(user_id):
    """Get user permissions"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    users_df = load_data("users")
    user = users_df[users_df['id'] == user_id]
    
    if user.empty:
        return jsonify({'error': 'User not found'}), 404
        
    permissions = user['permissions'].iloc[0]
    if isinstance(permissions, str):
        permissions = eval(permissions)
        
    return jsonify({'permissions': permissions})

@app.route('/admin/user_permissions/<user_id>', methods=['POST'])
@login_required
def update_user_permissions(user_id):
    """Update user permissions"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    users_df = load_data("users")
    user = users_df[users_df['id'] == user_id]
    
    if user.empty:
        return jsonify({'error': 'User not found'}), 404
        
    # Get new permissions from form
    new_permissions = request.form.getlist('permissions')
    
    # Update user permissions
    users_df.loc[users_df['id'] == user_id, 'permissions'] = str(new_permissions)
    save_data("users", users_df)
    
    # Log permission changes
    permissions_df = load_data("user_permissions")
    for permission in new_permissions:
        new_permission = pd.DataFrame({
            'id': [str(uuid.uuid4())],
            'user_id': [user_id],
            'permission': [permission],
            'granted_by': [session.get('user_id')],
            'granted_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            'expires_at': [None]
        })
        permissions_df = pd.concat([permissions_df, new_permission], ignore_index=True)
    save_data("user_permissions", permissions_df)
    
    return jsonify({'success': True})

@app.route('/admin/project_access/<project_id>', methods=['GET'])
@login_required
def get_project_access(project_id):
    """Get project access settings"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    project_access_df = load_data("project_access")
    project_access = project_access_df[
        project_access_df['project_id'] == project_id
    ].to_dict('records')
    
    return jsonify({'access': project_access})

@app.route('/admin/project_access/<project_id>', methods=['POST'])
@login_required
def update_project_access(project_id):
    """Update project access settings"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    project_access_df = load_data("project_access")
    user_id = request.form.get('user_id')
    access_level = request.form.get('access_level')
    
    # Update or create project access
    if user_id and access_level:
        grant_project_access(user_id, project_id, access_level, session.get('user_id'))
    
    return jsonify({'success': True})

@app.route('/admin/revoke_project_access/<project_id>/<user_id>', methods=['POST'])
@login_required
def revoke_project_access_route(project_id, user_id):
    """Revoke project access for a user"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    revoke_project_access(user_id, project_id)
    return jsonify({'success': True})

@app.route('/admin/budget_management', methods=['GET', 'POST'])
@login_required
def budget_management():
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if user_data.get('role') != 'admin':
        return redirect(url_for('my_dashboard'))
    
    if request.method == 'POST':
        try:
            # Get form data
            project_id = request.form.get('project_id')
            total_budget = float(request.form.get('total_budget', 0))
            budget_breakdown = request.form.get('budget_breakdown', '')
            
            # Load projects data
            projects_df = load_data("projects")
            if projects_df.empty:
                flash('No projects found', 'error')
                return redirect(url_for('budget_management'))
            
            # Update project budget
            projects_df.loc[projects_df['id'] == project_id, 'budget'] = total_budget
            save_data("projects", projects_df)
            
            # Redirect to the new AI budget recommendations page
            flash('Budget updated successfully! Generating AI recommendations...', 'success')
            return redirect(url_for('ai_budget_recommendations_page', project_id=project_id))
            
        except Exception as e:
            print(f"Error in budget management: {str(e)}")
            flash('Failed to process budget update', 'error')
            return redirect(url_for('budget_management'))
    
    # GET request - show budget management page
    projects = load_projects()
    budget_analysis_df = load_data("budget_analysis")
    budget_analysis = budget_analysis_df.to_dict('records') if not budget_analysis_df.empty else []
    
    return render_template('budget_management.html', 
                         projects=projects,
                         budget_analysis=budget_analysis)

@app.route('/admin/budget_analysis/<project_id>')
@login_required
def budget_analysis(project_id):
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if user_data.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Load project data
    projects = load_projects()
    if not projects:
        flash('Project not found', 'error')
        return redirect(url_for('budget_management'))
        
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        flash('Project not found', 'error')
        return redirect(url_for('budget_management'))
    
    # Load budget analysis data
    budget_analysis_df = load_data("budget_analysis")
    if budget_analysis_df.empty:
        analysis = []
    else:
        analysis = budget_analysis_df[budget_analysis_df['project_id'] == project_id].to_dict('records')
    
    return render_template('budget_analysis.html', project=project, analysis=analysis)

@app.route('/admin/ai_budget_recommendations/')
@login_required
def ai_budget_recommendations_index():
    """Redirect to budget management page"""
    return redirect(url_for('budget_management'))

@app.route('/ai_budget_recommendations/<project_id>')
@login_required
def ai_budget_recommendations_redirect(project_id):
    """Redirect to the admin budget recommendations page"""
    return redirect(url_for('ai_budget_recommendations_page', project_id=project_id))

@app.route('/admin/ai_budget_recommendations/<project_id>')
@login_required
def ai_budget_recommendations_page(project_id):
    """Page to display and generate AI budget recommendations"""
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    if user_data.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Load project data
    projects = load_projects()
    if not projects:
        flash('Project not found', 'error')
        return redirect(url_for('budget_management'))
        
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        flash('Project not found', 'error')
        return redirect(url_for('budget_management'))
    
    # Load existing budget analysis data
    budget_analysis_df = load_data("budget_analysis")
    if budget_analysis_df.empty:
        analysis = []
    else:
        analysis = budget_analysis_df[budget_analysis_df['project_id'] == project_id].to_dict('records')
        # Sort by date (newest first)
        analysis.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Get project team size
    team_size = 0
    if 'team_members' in project:
        if isinstance(project['team_members'], str):
            team_members = [m.strip() for m in project['team_members'].split(',') if m.strip()]
            team_size = len(team_members)
        elif isinstance(project['team_members'], list):
            team_size = len(project['team_members'])
    
    # Calculate project duration if start and end dates are available
    duration_months = 6  # Default
    if 'start_date' in project and project['start_date'] and 'end_date' in project and project['end_date']:
        try:
            start_date = datetime.datetime.strptime(project['start_date'], '%Y-%m-%d')
            end_date = datetime.datetime.strptime(project['end_date'], '%Y-%m-%d')
            duration_days = (end_date - start_date).days
            duration_months = max(1, round(duration_days / 30))
        except:
            duration_months = 6
    
    return render_template('ai_budget_recommendations.html', 
                         project=project, 
                         analysis=analysis,
                         team_size=team_size,
                         duration_months=duration_months)

@app.route('/api/budget/ai_recommendations', methods=['POST'])
@login_required
def api_budget_recommendations():
    """Generate AI-powered budget recommendations using Gemini API"""
    try:
        # Check if user is admin
        user_email = session.get('user')
        user_data = load_user_data(user_email)
        if user_data.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
            
        # Get request data
        data = request.get_json()
        project_id = data.get('project_id')
        total_budget = float(data.get('total_budget', 0))
        project_type = data.get('project_type', 'Software Development')
        team_size = int(data.get('team_size', 5))
        duration_months = int(data.get('duration_months', 6))
        complexity = data.get('complexity', 'Medium')
        current_breakdown = data.get('current_breakdown', '')
        
        # Validate inputs
        if not project_id or total_budget <= 0:
            return jsonify({'error': 'Invalid project data provided'}), 400
            
        # Load project data for additional context
        projects_df = load_data("projects")
        if not projects_df.empty:
            project = projects_df[projects_df['id'] == project_id]
            if not project.empty:
                project_data = project.iloc[0].to_dict()
                project_name = project_data.get('name', 'Unnamed Project')
                project_description = project_data.get('description', '')
                project_status = project_data.get('status', 'Not Started')
            else:
                project_name = 'Unnamed Project'
                project_description = ''
                project_status = 'Not Started'
        else:
            project_name = 'Unnamed Project'
            project_description = ''
            project_status = 'Not Started'
            
        # Create a detailed prompt for Gemini API
        prompt = f"""
        As an AI budget optimization expert, analyze and provide detailed budget recommendations for the following software project:
        
        PROJECT DETAILS:
        - Project ID: {project_id}
        - Project Name: {project_name}
        - Description: {project_description}
        - Status: {project_status}
        - Total Budget: ${total_budget:,.2f}
        - Project Type: {project_type}
        - Team Size: {team_size} members
        - Duration: {duration_months} months
        - Complexity: {complexity}
        
        CURRENT BUDGET BREAKDOWN (if available):
        {current_breakdown}
        
        PROVIDE A COMPREHENSIVE BUDGET ANALYSIS INCLUDING:
        
        1. OPTIMIZED BUDGET ALLOCATION:
           - Detailed breakdown by category (Development, Design, QA, Project Management, Infrastructure, etc.)
           - Specific dollar amounts and percentages for each category
           - Monthly burn rate recommendations
        
        2. JUSTIFICATION FOR ALLOCATIONS:
           - Explain the reasoning behind each allocation
           - Industry benchmarks and standards for similar projects
           - How the allocations align with project goals
        
        3. RISK ASSESSMENT:
           - Identify potential budget risks
           - Quantify potential impact (High/Medium/Low)
           - Recommended contingency reserves
        
        4. COST OPTIMIZATION STRATEGIES:
           - Specific actionable recommendations to maximize budget efficiency
           - Areas where costs can be reduced without compromising quality
           - Resource allocation optimization
        
        5. BUDGET MONITORING PLAN:
           - Key metrics to track
           - Recommended review frequency
           - Early warning indicators for budget issues
        
        Format your response in a clear, structured manner with headings and bullet points.
        """
        
        # Call Gemini API with enhanced safety settings
        try:
            print("Sending enhanced budget analysis request to Gemini API...")
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            generation_config = {
                "temperature": 0.2,  # Lower temperature for more focused, deterministic output
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,  # Allow for detailed response
            }
            
            response = model.generate_content(
                prompt,
                safety_settings=safety_settings,
                generation_config=generation_config
            )
            
            # Process the response
            if hasattr(response, 'text'):
                recommendations = response.text
                print(f"Received detailed budget recommendations from Gemini API")
                
                # Save the analysis to the database
                budget_analysis = {
                    'id': str(uuid.uuid4()),
                    'project_id': project_id,
                    'total_budget': total_budget,
                    'allocated_budget': 0.0,
                    'remaining_budget': total_budget,
                    'analysis_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'recommendations': recommendations,
                    'risk_assessment': 'AI-generated assessment',
                    'original_breakdown': current_breakdown
                }
                
                # Save to database
                budget_df = load_data("budget_analysis")
                if budget_df.empty:
                    budget_df = pd.DataFrame(columns=sheets["budget_analysis"]["columns"])
                
                budget_df = pd.concat([budget_df, pd.DataFrame([budget_analysis])], ignore_index=True)
                save_data("budget_analysis", budget_df)
                
                # Extract key sections for the response
                sections = {}
                current_section = None
                section_content = []
                
                for line in recommendations.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Check if this is a section header
                    if any(header in line.upper() for header in ['BUDGET ALLOCATION', 'JUSTIFICATION', 'RISK ASSESSMENT', 'COST OPTIMIZATION', 'MONITORING']):
                        # Save previous section if it exists
                        if current_section and section_content:
                            sections[current_section] = '\n'.join(section_content)
                            section_content = []
                        
                        # Set new section
                        current_section = line
                    else:
                        # Add content to current section
                        if current_section:
                            section_content.append(line)
                
                # Save the last section
                if current_section and section_content:
                    sections[current_section] = '\n'.join(section_content)
                
                return jsonify({
                    'success': True,
                    'analysis_id': budget_analysis['id'],
                    'recommendations': recommendations,
                    'sections': sections,
                    'summary': {
                        'total_budget': total_budget,
                        'project_name': project_name,
                        'analysis_date': budget_analysis['analysis_date']
                    }
                })
            else:
                raise Exception("No text attribute in Gemini API response")
                
        except Exception as e:
            print(f"Error with Gemini API budget recommendations: {str(e)}")
            
            # Create fallback recommendations based on project parameters
            dev_percent = 0.4
            design_percent = 0.15
            qa_percent = 0.2
            pm_percent = 0.15
            infra_percent = 0.05
            contingency = 0.05
            
            # Adjust percentages based on complexity
            if complexity.lower() == 'high':
                dev_percent = 0.45
                qa_percent = 0.25
                contingency = 0.1
                design_percent = 0.1
                pm_percent = 0.1
            elif complexity.lower() == 'low':
                dev_percent = 0.35
                qa_percent = 0.15
                design_percent = 0.2
                pm_percent = 0.2
                contingency = 0.05
                infra_percent = 0.05
                
            # Calculate monthly burn rate
            monthly_burn = total_budget / duration_months if duration_months > 0 else total_budget
                
            fallback_recommendations = f"""
            # OPTIMIZED BUDGET ALLOCATION
            
            ## Overall Allocation
            - Development: {dev_percent*100:.1f}% (${total_budget * dev_percent:,.2f})
            - Design: {design_percent*100:.1f}% (${total_budget * design_percent:,.2f})
            - Quality Assurance: {qa_percent*100:.1f}% (${total_budget * qa_percent:,.2f})
            - Project Management: {pm_percent*100:.1f}% (${total_budget * pm_percent:,.2f})
            - Infrastructure: {infra_percent*100:.1f}% (${total_budget * infra_percent:,.2f})
            - Contingency: {contingency*100:.1f}% (${total_budget * contingency:,.2f})
            
            ## Monthly Burn Rate
            - Recommended monthly budget: ${monthly_burn:,.2f}
            
            # JUSTIFICATION FOR ALLOCATIONS
            
            - Development allocation is based on standard industry practices for {complexity} complexity projects
            - QA allocation ensures proper testing for a {team_size}-person team
            - Project Management costs are scaled appropriately for a {duration_months}-month project
            - Contingency fund is set at {contingency*100:.1f}% to mitigate potential risks
            
            # RISK ASSESSMENT
            
            - Schedule overruns: Medium risk
            - Scope creep: High risk
            - Technical challenges: Medium risk
            - Resource availability: Low risk
            
            # COST OPTIMIZATION STRATEGIES
            
            - Consider phased implementation to spread costs
            - Leverage open-source tools where possible
            - Implement regular budget reviews
            - Optimize team composition based on project phases
            
            # BUDGET MONITORING PLAN
            
            - Track actual vs. planned expenditure weekly
            - Review burn rate bi-weekly
            - Conduct formal budget review monthly
            - Monitor contingency fund usage carefully
            """
            
            # Save the fallback analysis to the database
            fallback_analysis = {
                'id': str(uuid.uuid4()),
                'project_id': project_id,
                'total_budget': total_budget,
                'allocated_budget': 0.0,
                'remaining_budget': total_budget,
                'analysis_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'recommendations': fallback_recommendations,
                'risk_assessment': 'System-generated assessment (fallback)',
                'original_breakdown': current_breakdown
            }
            
            # Save to database
            budget_df = load_data("budget_analysis")
            if budget_df.empty:
                budget_df = pd.DataFrame(columns=sheets["budget_analysis"]["columns"])
            
            budget_df = pd.concat([budget_df, pd.DataFrame([fallback_analysis])], ignore_index=True)
            save_data("budget_analysis", budget_df)
            
            # Extract sections for the response
            sections = {
                "OPTIMIZED BUDGET ALLOCATION": "\n".join(fallback_recommendations.split("# OPTIMIZED BUDGET ALLOCATION")[1].split("# JUSTIFICATION")[0].strip().split("\n")[1:]),
                "JUSTIFICATION FOR ALLOCATIONS": "\n".join(fallback_recommendations.split("# JUSTIFICATION FOR ALLOCATIONS")[1].split("# RISK ASSESSMENT")[0].strip().split("\n")[1:]),
                "RISK ASSESSMENT": "\n".join(fallback_recommendations.split("# RISK ASSESSMENT")[1].split("# COST OPTIMIZATION")[0].strip().split("\n")[1:]),
                "COST OPTIMIZATION STRATEGIES": "\n".join(fallback_recommendations.split("# COST OPTIMIZATION STRATEGIES")[1].split("# BUDGET MONITORING")[0].strip().split("\n")[1:]),
                "BUDGET MONITORING PLAN": "\n".join(fallback_recommendations.split("# BUDGET MONITORING PLAN")[1].strip().split("\n")[1:])
            }
            
            return jsonify({
                'success': True,
                'analysis_id': fallback_analysis['id'],
                'recommendations': fallback_recommendations,
                'sections': sections,
                'summary': {
                    'total_budget': total_budget,
                    'project_name': project_name,
                    'analysis_date': fallback_analysis['analysis_date']
                },
                'note': 'Generated using fallback system due to AI service unavailability'
            })
            
    except Exception as e:
        print(f"Error in AI budget recommendations: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Failed to generate budget recommendations',
            'message': str(e)
        }), 500

@app.route('/analyze_task', methods=['POST'])
@login_required
def analyze_task():
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        
        if not title or not description:
            return jsonify({'success': False, 'message': 'Title and description are required'})
        
        # Load users data
        users_df = load_data("users")
        if users_df.empty:
            return jsonify({'success': False, 'message': 'No users found'})
        
        # Extract skills from task description using Gemini API
        skill_prompt = f"""
        Extract the required technical skills from this task description. Focus on:
        1. Programming languages
        2. Frameworks and tools
        3. Technologies and platforms
        4. Industry-specific skills

        Task Title: {title}
        Description: {description}

        Return only the skills as a comma-separated list.
        """
        
        try:
            # Add safety settings for Gemini API
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            skill_response = model.generate_content(
                skill_prompt,
                safety_settings=safety_settings
            )
            
            if not skill_response or not hasattr(skill_response, 'text'):
                print("Error: No response from Gemini API")
                return jsonify({'success': False, 'message': 'Failed to extract skills from task'})
            
            required_skills = [skill.strip().lower() for skill in skill_response.text.split(',') if skill.strip()]
            if not required_skills:
                print("Error: No skills extracted from Gemini API response")
                return jsonify({'success': False, 'message': 'No skills could be extracted from the task'})
                
        except Exception as e:
            print(f"Error calling Gemini API: {str(e)}")
            # Provide fallback skills extraction
            print("Using fallback skills extraction")
            # Extract common programming terms from description
            common_skills = ["python", "javascript", "java", "c#", "react", "angular", "vue", 
                            "node.js", "flask", "django", "database", "sql", "nosql", "aws", 
                            "azure", "devops", "docker", "kubernetes", "git", "agile"]
            required_skills = [skill for skill in common_skills if skill.lower() in description.lower()]
            if not required_skills:
                required_skills = ["programming", "development"]
                
            print(f"Fallback skills extracted: {required_skills}")
            # Continue with the extracted skills instead of returning an error
        
        # Find best matching user
        best_match = None
        best_match_percentage = 0
        best_matching_skills = []
        all_matches = []
        
        for _, user in users_df.iterrows():
            user_skills = user['skills']
            if isinstance(user_skills, str):
                user_skills = [skill.strip().lower() for skill in user_skills.split(',') if skill.strip()]
            elif not isinstance(user_skills, list):
                user_skills = []
            
            # Calculate skill match
            matching_skills = set(required_skills) & set(user_skills)
            match_percentage = (len(matching_skills) / len(required_skills)) * 100 if required_skills else 0
            
            match_info = {
                'user_id': user['id'],
                'name': user['name'],
                'match_percentage': round(match_percentage, 1),
                'matching_skills': list(matching_skills),
                'missing_skills': list(set(required_skills) - set(user_skills))
            }
            
            all_matches.append(match_info)
            
            if match_percentage > best_match_percentage:
                best_match_percentage = match_percentage
                best_match = user
                best_matching_skills = list(matching_skills)
        
        # Sort all matches by percentage
        all_matches.sort(key=lambda x: x['match_percentage'], reverse=True)
        
        if best_match:
            return jsonify({
                'success': True,
                'recommended_user': {
                    'id': best_match['id'],
                    'name': best_match['name']
                },
                'match_percentage': round(best_match_percentage, 1),
                'matching_skills': best_matching_skills,
                'all_matches': all_matches[:5],  # Return top 5 matches
                'required_skills': required_skills  # Return the extracted skills
            })
        else:
            return jsonify({'success': False, 'message': 'No suitable match found'})
            
    except Exception as e:
        print(f"Error in analyze_task: {str(e)}")
        return jsonify({'success': False, 'message': 'Internal server error'})

# Error Handler
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', 
                         error_code=404,
                         error="Page not found",
                         message="The page you are looking for does not exist.",
                         now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', 
                         error_code=500,
                         error="Internal server error",
                         message="Something went wrong on our end. Please try again later.",
                         now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')), 500

# Add these constants after the existing configuration
UPLOAD_FOLDER = 'uploads/resumes'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max file size

# Add these functions before the routes
def grant_project_access(user_id, project_id, access_level, granted_by):
    """Grant project access to a user."""
    try:
        project_access_df = load_data("project_access")
        new_access = pd.DataFrame({
            'id': [str(uuid.uuid4())],
            'user_id': [user_id],
            'project_id': [project_id],
            'role': [access_level],
            'granted_by': [granted_by],
            'granted_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        })
        project_access_df = pd.concat([project_access_df, new_access], ignore_index=True)
        save_data("project_access", project_access_df)
        return True
    except Exception as e:
        print(f"Error granting project access: {str(e)}")
        return False

def revoke_project_access(user_id, project_id):
    """Revoke project access from a user."""
    try:
        project_access_df = load_data("project_access")
        # Remove all access entries for this user and project
        project_access_df = project_access_df[
            ~((project_access_df['user_id'] == user_id) & 
              (project_access_df['project_id'] == project_id))
        ]
        save_data("project_access", project_access_df)
        return True
    except Exception as e:
        print(f"Error revoking project access: {str(e)}")
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_skills_from_pdf(pdf_file):
    try:
        # Read PDF file
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()

        # Common technical skills to look for
        common_skills = {
            'programming': ['python', 'java', 'javascript', 'c++', 'c#', 'php', 'ruby', 'swift', 'kotlin', 'go', 'rust'],
            'web': ['html', 'css', 'react', 'angular', 'vue', 'node.js', 'django', 'flask', 'spring', 'laravel'],
            'database': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'oracle', 'sqlite'],
            'tools': ['git', 'docker', 'kubernetes', 'jenkins', 'jira', 'confluence', 'slack'],
            'cloud': ['aws', 'azure', 'gcp', 'heroku', 'digitalocean'],
            'ai_ml': ['tensorflow', 'pytorch', 'scikit-learn', 'numpy', 'pandas', 'machine learning', 'deep learning'],
            'mobile': ['android', 'ios', 'react native', 'flutter', 'xamarin'],
            'design': ['figma', 'adobe xd', 'sketch', 'ui/ux', 'wireframing'],
            'testing': ['selenium', 'junit', 'pytest', 'cypress', 'jenkins'],
            'devops': ['ci/cd', 'terraform', 'ansible', 'puppet', 'chef']
        }

        # Extract skills from text
        found_skills = set()
        text = text.lower()
        
        for category, skills in common_skills.items():
            for skill in skills:
                if skill.lower() in text:
                    found_skills.add(skill)

        # Use Gemini API to extract additional skills
        prompt = f"""
        Extract technical skills from the following resume text. Focus on:
        1. Programming languages
        2. Frameworks and tools
        3. Technologies and platforms
        4. Industry-specific skills
        5. Soft skills

        Resume text:
        {text[:2000]}  # Limit text length for API

        Return only the skills as a comma-separated list.
        """

        try:
            response = model.generate_content(prompt)
            if response and hasattr(response, 'text'):
                additional_skills = [skill.strip() for skill in response.text.split(',') if skill.strip()]
                found_skills.update(additional_skills)
        except Exception as e:
            print(f"Error extracting skills with Gemini API: {str(e)}")

        return list(found_skills)
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return []

@app.route('/task/<task_id>')
@login_required
def view_task(task_id):
    # Load tasks and projects data
    tasks_df = load_data("tasks")
    projects_df = load_data("projects")
    users_df = load_data("users")
    
    # Get task data
    task = tasks_df[tasks_df['id'] == task_id]
    if task.empty:
        flash('Task not found', 'error')
        return redirect(url_for('tasks'))
    
    task_data = task.iloc[0].to_dict()
    
    # Get project info
    project = projects_df[projects_df['id'] == task_data['project_id']]
    if not project.empty:
        task_data['project'] = project.iloc[0].to_dict()
    else:
        task_data['project'] = {'name': 'Unknown Project'}
    
    # Get assignee info
    assignee = users_df[users_df['id'] == task_data['assigned_to']]
    if not assignee.empty:
        task_data['assignee'] = assignee.iloc[0].to_dict()
    else:
        task_data['assignee'] = {'name': 'Unassigned'}
    
    # Format the date
    due_date = task_data.get('due_date', '')
    if due_date:
        try:
            # If it's already a datetime object
            if hasattr(due_date, 'strftime'):
                task_data['due_date'] = due_date
            else:
                # If it's a string, convert to datetime
                task_data['due_date'] = datetime.datetime.strptime(due_date, '%Y-%m-%d')
        except:
            task_data['due_date'] = due_date  # Keep as string if conversion fails
    
    # Add status and priority colors
    task_data['status_color'] = {
        'Completed': 'success',
        'In Progress': 'primary',
        'To Do': 'warning',
        'On Hold': 'info'
    }.get(task_data.get('status'), 'secondary')
    
    task_data['priority_color'] = {
        'High': 'danger',
        'Medium': 'warning',
        'Low': 'info'
    }.get(task_data.get('priority'), 'secondary')
    
    # Handle required skills
    required_skills = task_data.get('required_skills', '')
    if isinstance(required_skills, (int, float)):
        required_skills = str(required_skills)
    elif not isinstance(required_skills, str):
        required_skills = ''
    task_data['required_skills'] = required_skills
    
    # Calculate skill match if task has an assignee
    if task_data.get('assigned_to'):
        assignee = next((u for u in users_df.to_dict('records') if u['id'] == task_data['assigned_to']), None)
        if assignee:
            # Handle assignee skills
            assignee_skills = assignee.get('skills', '')
            if isinstance(assignee_skills, (int, float)):
                assignee_skills = str(assignee_skills)
            if isinstance(assignee_skills, str):
                assignee_skills = [skill.strip() for skill in assignee_skills.split(',') if skill.strip()]
            elif not isinstance(assignee_skills, list):
                assignee_skills = []
            
            # Handle required skills
            required_skills_list = [skill.strip() for skill in required_skills.split(',') if skill.strip()]
            
            # Calculate skill match
            if required_skills_list and assignee_skills:
                matching_skills = set(required_skills_list) & set(assignee_skills)
                task_data['skill_match_percentage'] = round((len(matching_skills) / len(required_skills_list)) * 100, 1)
                task_data['matching_skills'] = list(matching_skills)
            else:
                task_data['skill_match_percentage'] = 0
                task_data['matching_skills'] = []
    
    return render_template('view_task.html', task=task_data)

@app.route('/task/<task_id>/status', methods=['PUT'])
@login_required
def update_task_status(task_id):
    try:
        # Get request data
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({'success': False, 'message': 'Status is required'})
        
        # Load tasks data
        tasks_df = load_data("tasks")
        
        # Check if task exists
        if task_id not in tasks_df['id'].values:
            return jsonify({'success': False, 'message': 'Task not found'})
        
        # Get user data
        user_email = session.get('user')
        user_data = load_user_data(user_email)
        
        # For non-admin users, check if they are assigned to the task
        if user_data.get('role') != 'admin':
            task = tasks_df[tasks_df['id'] == task_id].iloc[0]
            
            # Check if user is assigned to the task
            if task['assigned_to'] != user_data['id']:
                return jsonify({'success': False, 'message': 'You do not have permission to update this task'})
        
        # Update task status
        tasks_df.loc[tasks_df['id'] == task_id, 'status'] = new_status
        
        # If status is Completed, update progress to 100%
        if new_status == 'Completed':
            tasks_df.loc[tasks_df['id'] == task_id, 'progress'] = 100.0
        elif new_status == 'In Progress':
            tasks_df.loc[tasks_df['id'] == task_id, 'progress'] = 50.0
        elif new_status == 'To Do':
            tasks_df.loc[tasks_df['id'] == task_id, 'progress'] = 0.0
        
        # Update the updated_at timestamp
        tasks_df.loc[tasks_df['id'] == task_id, 'updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save updated data
        save_data("tasks", tasks_df)
        
        return jsonify({'success': True, 'message': 'Task status updated successfully'})
    
    except Exception as e:
        print(f"Error updating task status: {str(e)}")
        return jsonify({'success': False, 'message': f'Error updating task status: {str(e)}'})

@app.route('/task/<task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    try:
        # Load tasks data
        tasks_df = load_data("tasks")
        
        # Check if task exists
        if task_id not in tasks_df['id'].values:
            return jsonify({'success': False, 'message': 'Task not found'})
        
        # Get user data
        user_email = session.get('user')
        user_data = load_user_data(user_email)
        
        # For non-admin users, check if they are assigned to the task or are the project manager
        if user_data.get('role') != 'admin':
            task = tasks_df[tasks_df['id'] == task_id].iloc[0]
            
            # Check if user is assigned to the task
            if task['assigned_to'] != user_data['id']:
                # Check if user is the project manager
                projects_df = load_data("projects")
                project = projects_df[projects_df['id'] == task['project_id']]
                
                if project.empty or project.iloc[0]['manager_id'] != user_data['id']:
                    return jsonify({'success': False, 'message': 'You do not have permission to delete this task'})
        
        # Delete the task
        tasks_df = tasks_df[tasks_df['id'] != task_id]
        
        # Save updated data
        save_data("tasks", tasks_df)
        
        return jsonify({'success': True, 'message': 'Task deleted successfully'})
    
    except Exception as e:
        print(f"Error deleting task: {str(e)}")
        return jsonify({'success': False, 'message': f'Error deleting task: {str(e)}'})

@app.route('/task/<task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    user_email = session.get('user')
    user_data = load_user_data(user_email)
    
    # Load tasks, projects, and users data
    tasks_df = load_data("tasks")
    projects_df = load_data("projects")
    users_df = load_data("users")
    
    # Get task data
    task = tasks_df[tasks_df['id'] == task_id]
    if task.empty:
        flash('Task not found', 'error')
        return redirect(url_for('tasks'))
    
    task_data = task.iloc[0].to_dict()
    
    # Get project info
    project = projects_df[projects_df['id'] == task_data['project_id']]
    if project.empty:
        flash('Project not found', 'error')
        return redirect(url_for('tasks'))
    
    project_data = project.iloc[0].to_dict()
    
    # For non-admin users, check if they have access to this task
    if user_data.get('role') != 'admin':
        if task_data['assigned_to'] != user_data['id']:
            flash('Access denied. You do not have permission to edit this task.', 'error')
            return redirect(url_for('my_tasks'))
    
    if request.method == 'POST':
        try:
            # Update task data
            tasks_df.loc[tasks_df['id'] == task_id, 'title'] = request.form.get('title')
            tasks_df.loc[tasks_df['id'] == task_id, 'description'] = request.form.get('description')
            tasks_df.loc[tasks_df['id'] == task_id, 'assigned_to'] = request.form.get('assigned_to')
            tasks_df.loc[tasks_df['id'] == task_id, 'status'] = request.form.get('status')
            tasks_df.loc[tasks_df['id'] == task_id, 'priority'] = request.form.get('priority')
            tasks_df.loc[tasks_df['id'] == task_id, 'due_date'] = request.form.get('due_date')
            tasks_df.loc[tasks_df['id'] == task_id, 'progress'] = float(request.form.get('progress', 0))
            tasks_df.loc[tasks_df['id'] == task_id, 'estimated_hours'] = float(request.form.get('estimated_hours', 0))
            tasks_df.loc[tasks_df['id'] == task_id, 'actual_hours'] = float(request.form.get('actual_hours', 0))
            tasks_df.loc[tasks_df['id'] == task_id, 'required_skills'] = request.form.get('required_skills', '')
            tasks_df.loc[tasks_df['id'] == task_id, 'updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Save changes
            save_data("tasks", tasks_df)
            
            # Create notification for assigned user if changed
            if task_data['assigned_to'] != request.form.get('assigned_to'):
                new_assignee = request.form.get('assigned_to')
                notifications_df = load_data("notifications")
                new_notification = pd.DataFrame({
                    'id': [str(uuid.uuid4())],
                    'user_id': [new_assignee],
                    'title': ['Task Reassigned'],
                    'message': [f'You have been assigned the task: {request.form.get("title")}'],
                    'type': ['task_assignment'],
                    'created_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                    'read': [False],
                    'action_url': [f'/task/{task_id}']
                })
                notifications_df = pd.concat([notifications_df, new_notification], ignore_index=True)
                save_data("notifications", notifications_df)
            
            flash('Task updated successfully!', 'success')
            return redirect(url_for('view_task', task_id=task_id))
            
        except Exception as e:
            print(f"Error updating task: {str(e)}")
            flash('Failed to update task', 'error')
            return redirect(url_for('edit_task', task_id=task_id))
    
    # GET request - show edit form
    return render_template('edit_task.html', 
                         task=task_data,
                         project=project_data,
                         users=users_df.to_dict('records'))

@app.route('/create_meeting', methods=['POST'])
@login_required
def create_meeting():
    try:
        print("Creating meeting with form data")
        
        # Get user data
        user_email = session.get('user')
        user_data = load_user_data(user_email)
        
        # Get form data
        title = request.form.get('title')
        project_id = request.form.get('project_id')
        date = request.form.get('date')
        time = request.form.get('time')
        duration = request.form.get('duration')
        location = request.form.get('location', '')
        participants = request.form.getlist('participants')
        agenda = request.form.get('agenda', '')
        description = request.form.get('description', '')
        
        # Validate required fields
        if not all([title, project_id, date, time, duration, participants]):
            flash('All required fields must be filled out', 'error')
            return redirect(url_for('meetings'))
        
        # Convert participants list to comma-separated string
        participants_str = ','.join(participants)
        
        # Load meetings data
        meetings_df = load_data("meetings")
        if meetings_df.empty:
            print("Creating new meetings dataframe")
            # Ensure the meetings schema is defined
            if "meetings" not in sheets:
                print("Adding meetings schema to sheets dictionary")
                sheets["meetings"] = {
                    "columns": ["id", "project_id", "title", "description", "date", "time", "duration", "location", "organizer_id", "participants", "status", "created_at", "updated_at", "agenda"],
                    "dtypes": {
                        "id": str,
                        "project_id": str,
                        "title": str,
                        "description": str,
                        "date": str,
                        "time": str,
                        "duration": str,
                        "location": str,
                        "organizer_id": str,
                        "participants": str,
                        "status": str,
                        "created_at": str,
                        "updated_at": str,
                        "agenda": str
                    }
                }
            meetings_df = pd.DataFrame(columns=sheets["meetings"]["columns"])
        
        # Create new meeting
        meeting_id = str(uuid.uuid4())
        new_meeting = {
            'id': meeting_id,
            'project_id': project_id,
            'title': title,
            'description': description,
            'date': date,
            'time': time,
            'duration': duration,
            'location': location,
            'organizer_id': user_data['id'],
            'participants': participants_str,
            'status': 'Scheduled',
            'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'agenda': agenda
        }
        
        print(f"New meeting data: {new_meeting}")
        
        # Add to dataframe
        try:
            # Create a new DataFrame with the meeting data
            new_meeting_df = pd.DataFrame([new_meeting])
            
            # Ensure all required columns are present
            for col in sheets["meetings"]["columns"]:
                if col not in new_meeting_df.columns:
                    new_meeting_df[col] = None
            
            # Concatenate with existing data
            meetings_df = pd.concat([meetings_df, new_meeting_df], ignore_index=True)
            
            # Save to database
            print(f"Attempting to save meeting data. DataFrame shape: {meetings_df.shape}")
            result = save_data("meetings", meetings_df)
            print(f"Save result: {result}")
            if not result:
                flash('Failed to save meeting data', 'error')
                return redirect(url_for('meetings'))
                
            print(f"Meeting saved successfully with ID: {meeting_id}")
            
            flash('Meeting created successfully!', 'success')
            return redirect(url_for('meetings'))
            
        except Exception as e:
            print(f"Error saving meeting to dataframe: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Error saving meeting: {str(e)}', 'error')
            return redirect(url_for('meetings'))
        
    except Exception as e:
        print(f"Error creating meeting: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Failed to create meeting: {str(e)}', 'error')
        return redirect(url_for('meetings'))

@app.route('/api/meetings/<meeting_id>', methods=['PUT'])
@login_required
def update_meeting(meeting_id):
    try:
        data = request.get_json()
        user_email = session.get('user')
        user_data = load_user_data(user_email)
        
        # Load meetings data
        meetings_df = load_data("meetings")
        if meetings_df.empty:
            return jsonify({'success': False, 'message': 'Meeting not found'})
        
        # Find meeting
        meeting_mask = meetings_df['id'] == meeting_id
        if not any(meeting_mask):
            return jsonify({'success': False, 'message': 'Meeting not found'})
        
        meeting = meetings_df[meeting_mask].iloc[0]
        
        # Check if user is organizer
        if meeting['organizer_id'] != user_data['id'] and user_data.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'Unauthorized to update this meeting'})
        
        # Update meeting
        update_data = {
            'title': data.get('title', meeting['title']),
            'description': data.get('description', meeting['description']),
            'date': data.get('date', meeting['date']),
            'time': data.get('time', meeting['time']),
            'duration': data.get('duration', meeting['duration']),
            'location': data.get('location', meeting['location']),
            'participants': data.get('participants', meeting['participants']),
            'status': data.get('status', meeting['status']),
            'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'agenda': data.get('agenda', meeting['agenda'])
        }
        
        for key, value in update_data.items():
            meetings_df.loc[meeting_mask, key] = value
        
        save_data("meetings", meetings_df)
        
        return jsonify({'success': True, 'message': 'Meeting updated successfully'})
        
    except Exception as e:
        print(f"Error updating meeting: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to update meeting'})

@app.route('/api/meetings/<meeting_id>', methods=['DELETE'])
@login_required
def delete_meeting(meeting_id):
    try:
        user_email = session.get('user')
        user_data = load_user_data(user_email)
        
        # Load meetings data
        meetings_df = load_data("meetings")
        if meetings_df.empty:
            return jsonify({'success': False, 'message': 'Meeting not found'})
        
        # Find meeting
        meeting_mask = meetings_df['id'] == meeting_id
        if not any(meeting_mask):
            return jsonify({'success': False, 'message': 'Meeting not found'})
        
        meeting = meetings_df[meeting_mask].iloc[0]
        
        # Check if user is organizer
        if meeting['organizer_id'] != user_data['id'] and user_data.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'Unauthorized to delete this meeting'})
        
        # Delete meeting
        meetings_df = meetings_df[~meeting_mask]
        save_data("meetings", meetings_df)
        
        return jsonify({'success': True, 'message': 'Meeting deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting meeting: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to delete meeting'})

@app.route('/ai_recommendations')
@login_required
def ai_recommendations():
    """
    General AI recommendation page that provides access to all AI features
    in the application.
    """
    # Get current user
    user_email = session.get('user')
    user_data = load_user_data(user_email) if user_email else None
    
    # Load necessary data
    projects_df = load_data("projects")
    tasks_df = load_data("tasks")
    users_df = load_data("users")
    
    # Prepare data for the template
    recommendation_types = [
        {
            'id': 'task_assignment',
            'title': 'Task Assignment Recommendations',
            'description': 'Get AI recommendations for assigning tasks to team members based on skills and availability.',
            'icon': 'fa-tasks',
            'url': url_for('ai_task_recommendations')
        },
        {
            'id': 'budget',
            'title': 'Budget Recommendations',
            'description': 'Get AI recommendations for budget allocation and optimization.',
            'icon': 'fa-money-bill',
            'url': '#',  # This will be handled via AJAX
            'projects': projects_df.to_dict('records') if not projects_df.empty else []
        },
        {
            'id': 'task_analysis',
            'title': 'Task Analysis',
            'description': 'Analyze task descriptions to extract required skills and estimate complexity.',
            'icon': 'fa-chart-line',
            'url': url_for('ai_task_analysis')
        }
    ]
    
    # Project management recommendations
    pm_recommendations = [
        {
            'id': 'resource_allocation',
            'title': 'Resource Allocation',
            'description': 'Get AI recommendations for optimal resource allocation across projects.',
            'icon': 'fa-people-arrows',
            'button_text': 'Optimize Resources',
            'button_class': 'btn-success',
            'url': url_for('ai_resource_allocation')
        },
        {
            'id': 'risk_assessment',
            'title': 'Risk Assessment',
            'description': 'Identify potential risks in your projects and get mitigation strategies.',
            'icon': 'fa-exclamation-triangle',
            'button_text': 'Assess Risks',
            'button_class': 'btn-warning',
            'url': url_for('ai_risk_assessment')
        },
        {
            'id': 'timeline_optimization',
            'title': 'Timeline Optimization',
            'description': 'Optimize project timelines based on task dependencies and resource availability.',
            'icon': 'fa-calendar-check',
            'button_text': 'Optimize Timeline',
            'button_class': 'btn-info',
            'url': url_for('ai_timeline_optimization')
        }
    ]
    
    # Quick actions
    quick_actions = [
        {
            'id': 'generate_report',
            'title': 'Generate Project Report',
            'icon': 'fa-file-alt',
            'button_class': 'btn-primary'
        },
        {
            'id': 'team_performance',
            'title': 'Team Performance Analysis',
            'icon': 'fa-chart-bar',
            'button_class': 'btn-success'
        },
        {
            'id': 'meeting_summary',
            'title': 'Generate Meeting Summary',
            'icon': 'fa-clipboard-list',
            'button_class': 'btn-info'
        },
        {
            'id': 'skill_gap',
            'title': 'Team Skill Gap Analysis',
            'icon': 'fa-user-graduate',
            'button_class': 'btn-warning'
        }
    ]
    
    return render_template('ai_recommendations.html', 
                          recommendation_types=recommendation_types,
                          pm_recommendations=pm_recommendations,
                          quick_actions=quick_actions,
                          user=user_data)

@app.route('/ai_task_recommendations')
@login_required
def ai_task_recommendations():
    # Load necessary data
    tasks_df = load_data("tasks")
    users_df = load_data("users")
    projects_df = load_data("projects")
    
    if tasks_df.empty or users_df.empty:
        flash('No tasks or users found', 'error')
        return redirect(url_for('dashboard'))
    
    # Process tasks to include required information
    processed_tasks = []
    for _, task in tasks_df.iterrows():
        task_data = task.to_dict()
        
        # Get project info
        project_id = task_data.get('project_id')
        if project_id:
            project = projects_df[projects_df['id'] == project_id]
            if not project.empty:
                task_data['project'] = project.iloc[0].to_dict()
            else:
                task_data['project'] = {'name': 'Unknown Project'}
        else:
            task_data['project'] = {'name': 'Unknown Project'}
        
        # Get required skills
        required_skills = task_data.get('required_skills', '')
        if isinstance(required_skills, str):
            required_skills_list = [skill.strip().lower() for skill in required_skills.split(',') if skill.strip()]
        else:
            required_skills_list = []
        
        task_data['required_skills_list'] = required_skills_list
        
        # Find best matches for this task
        best_matches = []
        for _, user in users_df.iterrows():
            user_skills = user.get('skills', '')
            if isinstance(user_skills, str):
                user_skills_list = [skill.strip().lower() for skill in user_skills.split(',') if skill.strip()]
            else:
                user_skills_list = []
            
            # Skip if no skills to match
            if not required_skills_list or not user_skills_list:
                continue
            
            # Calculate match
            matching_skills = set(required_skills_list) & set(user_skills_list)
            match_percentage = round((len(matching_skills) / len(required_skills_list)) * 100, 1)
            
            # Add to best matches
            best_matches.append({
                'user_id': user['id'],
                'name': user['name'],
                'match_percentage': match_percentage,
                'matching_skills': list(matching_skills),
                'missing_skills': list(set(required_skills_list) - set(user_skills_list)),
                'resume_path': user.get('resume_path', '')
            })
        
        # Sort by match percentage
        best_matches.sort(key=lambda x: x['match_percentage'], reverse=True)
        task_data['best_matches'] = best_matches[:5]  # Top 5 matches
        
        processed_tasks.append(task_data)
    
    # Sort tasks by those with highest skill matches first
    processed_tasks.sort(key=lambda x: max([m['match_percentage'] for m in x['best_matches']]) if x['best_matches'] else 0, reverse=True)
    
    return render_template('ai_task_recommendations.html', tasks=processed_tasks)

# AI Recommendation API Routes
@app.route('/api/resource_allocation', methods=['POST'])
@login_required
def api_resource_allocation():
    """API endpoint for resource allocation recommendations using Gemini API"""
    try:
        # Get request data
        data = request.get_json() or {}
        use_gemini = data.get('use_gemini', True)  # Default to True to ensure Gemini API is used
        
        # Get project data
        projects_df = load_data("projects")
        users_df = load_data("users")
        tasks_df = load_data("tasks")
        
        if projects_df.empty or users_df.empty:
            return jsonify({'success': False, 'message': 'No projects or users found'})
        
        # Prepare data for Gemini API
        project_data = []
        for _, project in projects_df.iterrows():
            project_dict = project.to_dict()
            project_tasks = tasks_df[tasks_df['project_id'] == project_dict['id']]
            
            # Get assigned users for this project
            assigned_users = []
            for _, task in project_tasks.iterrows():
                if task.get('assigned_to') and task.get('assigned_to') not in [u['id'] for u in assigned_users]:
                    user = users_df[users_df['id'] == task['assigned_to']]
                    if not user.empty:
                        assigned_users.append({
                            'id': user.iloc[0]['id'],
                            'name': user.iloc[0]['name'],
                            'skills': user.iloc[0].get('skills', '').split(',') if isinstance(user.iloc[0].get('skills', ''), str) else []
                        })
            
            project_data.append({
                'id': project_dict['id'],
                'name': project_dict['name'],
                'description': project_dict.get('description', ''),
                'start_date': str(project_dict.get('start_date', '')),
                'end_date': str(project_dict.get('end_date', '')),
                'status': project_dict.get('status', ''),
                'assigned_users': assigned_users,
                'tasks_count': len(project_tasks)
            })
        
        # Create prompt for Gemini API
        prompt = f"""
        As an AI project management assistant, analyze the following project data and provide resource allocation recommendations.
        
        Project Data:
        {json.dumps(project_data, indent=2)}
        
        Please provide:
        1. Resource utilization analysis for each project
        2. Recommendations for optimal resource allocation
        3. Specific actions to improve team efficiency
        4. Potential resource conflicts and how to resolve them
        
        Format your response as a JSON object with the following structure:
        {{
            "current_utilization": {{
                "overview": "Brief overview of current resource utilization",
                "projects": [
                    {{
                        "project_id": "project_id",
                        "utilization_percentage": 65,
                        "issues": ["issue1", "issue2"]
                    }}
                ]
            }},
            "recommendations": [
                "recommendation1",
                "recommendation2"
            ],
            "efficiency_actions": [
                "action1",
                "action2"
            ],
            "resource_conflicts": [
                {{
                    "description": "Conflict description",
                    "resolution": "Proposed resolution"
                }}
            ]
        }}
        """
        
        # Add safety settings for Gemini API
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Call Gemini API
        response = model.generate_content(
            prompt,
            safety_settings=safety_settings
        )
        
        if not response or not hasattr(response, 'text'):
            return jsonify({'success': False, 'message': 'Failed to generate resource allocation recommendations'})
        
        # Parse the response
        try:
            result = json.loads(response.text)
            return jsonify({
                'success': True,
                'data': result
            })
        except json.JSONDecodeError:
            # If the response is not valid JSON, return it as text
            return jsonify({
                'success': True,
                'data': {
                    'current_utilization': {
                        'overview': 'Analysis of current resource utilization',
                        'projects': []
                    },
                    'recommendations': response.text.split('\n'),
                    'efficiency_actions': [],
                    'resource_conflicts': []
                }
            })
            
    except Exception as e:
        print(f"Error in resource allocation API: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/risk_assessment', methods=['POST'])
@login_required
def api_risk_assessment():
    """API endpoint for project risk assessment using Gemini API"""
    try:
        # Get project data
        projects_df = load_data("projects")
        tasks_df = load_data("tasks")
        
        if projects_df.empty:
            return jsonify({'success': False, 'message': 'No projects found'})
        
        # Get project ID from request or use the first project
        data = request.get_json() or {}
        project_id = data.get('project_id')
        
        if project_id:
            project = projects_df[projects_df['id'] == project_id]
            if project.empty:
                return jsonify({'success': False, 'message': 'Project not found'})
            project = project.iloc[0].to_dict()
        else:
            # Use the first active project
            active_projects = projects_df[projects_df['status'] == 'active']
            if active_projects.empty:
                project = projects_df.iloc[0].to_dict()
            else:
                project = active_projects.iloc[0].to_dict()
        
        # Get tasks for this project
        project_tasks = tasks_df[tasks_df['project_id'] == project['id']].to_dict('records')
        
        # Create prompt for Gemini API
        prompt = f"""
        As an AI risk assessment specialist, analyze the following project data and provide a comprehensive risk assessment.
        
        Project:
        {json.dumps(project, indent=2)}
        
        Project Tasks:
        {json.dumps(project_tasks, indent=2)}
        
        Please provide:
        1. Overall risk level for the project (High, Medium, or Low)
        2. Identification of high-risk items with detailed analysis
        3. Medium-risk items with brief analysis
        4. Low-risk items (just list them)
        5. Specific mitigation strategies for each high and medium risk
        
        Format your response as a JSON object with the following structure:
        {{
            "project_name": "{project['name']}",
            "overall_risk_level": "Medium",
            "risk_summary": "Brief summary of overall project risk",
            "high_risk_items": [
                {{
                    "title": "Risk title",
                    "description": "Detailed description",
                    "impact": "High/Medium/Low",
                    "probability": "High/Medium/Low",
                    "mitigation": "Specific mitigation strategy"
                }}
            ],
            "medium_risk_items": [
                {{
                    "title": "Risk title",
                    "description": "Brief description",
                    "mitigation": "Mitigation strategy"
                }}
            ],
            "low_risk_items": [
                "Risk 1",
                "Risk 2"
            ]
        }}
        """
        
        # Add safety settings for Gemini API
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Call Gemini API
        response = model.generate_content(
            prompt,
            safety_settings=safety_settings
        )
        
        if not response or not hasattr(response, 'text'):
            return jsonify({'success': False, 'message': 'Failed to generate risk assessment'})
        
        # Parse the response
        try:
            result = json.loads(response.text)
            return jsonify({
                'success': True,
                'data': result
            })
        except json.JSONDecodeError:
            # If the response is not valid JSON, return it as text
            return jsonify({
                'success': True,
                'data': {
                    'project_name': project['name'],
                    'overall_risk_level': 'Medium',
                    'risk_summary': 'Risk assessment completed',
                    'high_risk_items': [],
                    'medium_risk_items': [],
                    'low_risk_items': [],
                    'raw_response': response.text
                }
            })
            
    except Exception as e:
        print(f"Error in risk assessment API: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/timeline_optimization', methods=['POST'])
@login_required
def api_timeline_optimization():
    """API endpoint for project timeline optimization using Gemini API"""
    try:
        # Get project data
        projects_df = load_data("projects")
        tasks_df = load_data("tasks")
        
        if projects_df.empty:
            return jsonify({'success': False, 'message': 'No projects found'})
        
        # Get project ID from request or use the first project
        data = request.get_json() or {}
        project_id = data.get('project_id')
        
        if project_id:
            project = projects_df[projects_df['id'] == project_id]
            if project.empty:
                return jsonify({'success': False, 'message': 'Project not found'})
            project = project.iloc[0].to_dict()
        else:
            # Use the first active project
            active_projects = projects_df[projects_df['status'] == 'active']
            if active_projects.empty:
                project = projects_df.iloc[0].to_dict()
            else:
                project = active_projects.iloc[0].to_dict()
        
        # Get tasks for this project
        project_tasks = tasks_df[tasks_df['project_id'] == project['id']].to_dict('records')
        
        # Create prompt for Gemini API
        prompt = f"""
        As an AI project timeline optimization specialist, analyze the following project data and provide recommendations for optimizing the timeline.
        
        Project:
        {json.dumps(project, indent=2)}
        
        Project Tasks:
        {json.dumps(project_tasks, indent=2)}
        
        Please provide:
        1. Analysis of the current timeline
        2. Identification of critical path tasks
        3. Specific recommendations for timeline optimization
        4. Potential time savings
        5. Implementation plan for the optimized timeline
        
        Format your response as a JSON object with the following structure:
        {{
            "project_name": "{project['name']}",
            "current_timeline": {{
                "duration_weeks": 12,
                "critical_path_tasks": ["Task 1", "Task 3", "Task 5"],
                "bottlenecks": ["Bottleneck 1", "Bottleneck 2"]
            }},
            "optimized_timeline": {{
                "duration_weeks": 10,
                "time_savings_percentage": 16.7,
                "critical_path_tasks": ["Task 1", "Task 5"]
            }},
            "optimization_recommendations": [
                "Recommendation 1",
                "Recommendation 2"
            ],
            "implementation_plan": [
                "Step 1",
                "Step 2"
            ]
        }}
        """
        
        # Add safety settings for Gemini API
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Call Gemini API
        response = model.generate_content(
            prompt,
            safety_settings=safety_settings
        )
        
        if not response or not hasattr(response, 'text'):
            return jsonify({'success': False, 'message': 'Failed to generate timeline optimization'})
        
        # Parse the response
        try:
            result = json.loads(response.text)
            return jsonify({
                'success': True,
                'data': result
            })
        except json.JSONDecodeError:
            # If the response is not valid JSON, return it as text
            return jsonify({
                'success': True,
                'data': {
                    'project_name': project['name'],
                    'current_timeline': {
                        'duration_weeks': 12,
                        'critical_path_tasks': [],
                        'bottlenecks': []
                    },
                    'optimized_timeline': {
                        'duration_weeks': 10,
                        'time_savings_percentage': 16.7,
                        'critical_path_tasks': []
                    },
                    'optimization_recommendations': response.text.split('\n'),
                    'implementation_plan': []
                }
            })
            
    except Exception as e:
        print(f"Error in timeline optimization API: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/quick_action', methods=['POST'])
@login_required
def api_quick_action():
    """API endpoint for quick actions using Gemini API"""
    try:
        data = request.get_json()
        if not data or 'action_id' not in data:
            return jsonify({'success': False, 'message': 'Action ID is required'})
        
        action_id = data['action_id']
        use_gemini = data.get('use_gemini', True)  # Default to True to ensure Gemini API is used
        
        # Load necessary data
        projects_df = load_data("projects")
        tasks_df = load_data("tasks")
        users_df = load_data("users")
        meetings_df = load_data("meetings")
        
        # Create prompt based on action type
        if action_id == 'generate_report':
            # Get project ID from request or use the first project
            project_id = data.get('project_id')
            
            if project_id:
                project = projects_df[projects_df['id'] == project_id]
                if project.empty:
                    return jsonify({'success': False, 'message': 'Project not found'})
                project = project.iloc[0].to_dict()
            else:
                # Use the first active project
                active_projects = projects_df[projects_df['status'] == 'active']
                if active_projects.empty:
                    project = projects_df.iloc[0].to_dict()
                else:
                    project = active_projects.iloc[0].to_dict()
            
            # Get tasks for this project
            project_tasks = tasks_df[tasks_df['project_id'] == project['id']].to_dict('records')
            
            prompt = f"""
            Generate a comprehensive project report for the following project:
            
            Project:
            {json.dumps(project, indent=2)}
            
            Project Tasks:
            {json.dumps(project_tasks, indent=2)}
            
            Please include:
            1. Executive Summary
            2. Project Status Overview
            3. Key Accomplishments
            4. Challenges and Risks
            5. Next Steps
            6. Resource Allocation
            7. Timeline Analysis
            
            Format your response as a JSON object with the following structure:
            {{
                "title": "Project Report: {project['name']}",
                "date": "{datetime.datetime.now().strftime('%Y-%m-%d')}",
                "sections": [
                    {{
                        "heading": "Executive Summary",
                        "content": "Summary text here..."
                    }},
                    {{
                        "heading": "Project Status Overview",
                        "content": "Status text here..."
                    }},
                    // Additional sections
                ]
            }}
            """
            
        elif action_id == 'team_performance':
            # Get team performance data
            prompt = f"""
            Analyze the following team data and provide a performance analysis:
            
            Users:
            {json.dumps(users_df.to_dict('records'), indent=2)}
            
            Tasks:
            {json.dumps(tasks_df.to_dict('records'), indent=2)}
            
            Please provide:
            1. Overall team performance assessment
            2. Individual performance highlights
            3. Areas for improvement
            4. Recommendations for enhancing team productivity
            
            Format your response as a JSON object with the following structure:
            {{
                "title": "Team Performance Analysis",
                "date": "{datetime.datetime.now().strftime('%Y-%m-%d')}",
                "overall_assessment": "Assessment text here...",
                "individual_highlights": [
                    {{
                        "name": "User Name",
                        "strengths": ["Strength 1", "Strength 2"],
                        "areas_for_improvement": ["Area 1", "Area 2"]
                    }}
                ],
                "team_improvement_areas": ["Area 1", "Area 2"],
                "recommendations": ["Recommendation 1", "Recommendation 2"]
            }}
            """
            
        elif action_id == 'meeting_summary':
            # Get meeting ID from request or use the most recent meeting
            meeting_id = data.get('meeting_id')
            
            if meeting_id:
                meeting = meetings_df[meetings_df['id'] == meeting_id]
                if meeting.empty:
                    return jsonify({'success': False, 'message': 'Meeting not found'})
                meeting = meeting.iloc[0].to_dict()
            else:
                # Use the most recent meeting
                if meetings_df.empty:
                    return jsonify({'success': False, 'message': 'No meetings found'})
                meetings_df = meetings_df.sort_values(by='date', ascending=False)
                meeting = meetings_df.iloc[0].to_dict()
            
            prompt = f"""
            Generate a comprehensive meeting summary for the following meeting:
            
            Meeting:
            {json.dumps(meeting, indent=2)}
            
            Please include:
            1. Meeting Overview
            2. Key Discussion Points
            3. Decisions Made
            4. Action Items
            5. Next Steps
            
            Format your response as a JSON object with the following structure:
            {{
                "title": "Meeting Summary: {meeting.get('title', 'Team Meeting')}",
                "date": "{meeting.get('date', datetime.datetime.now().strftime('%Y-%m-%d'))}",
                "overview": "Overview text here...",
                "key_points": ["Point 1", "Point 2"],
                "decisions": ["Decision 1", "Decision 2"],
                "action_items": [
                    {{
                        "description": "Action item description",
                        "assigned_to": "Person name",
                        "due_date": "YYYY-MM-DD"
                    }}
                ],
                "next_steps": ["Step 1", "Step 2"]
            }}
            """
            
        elif action_id == 'skill_gap':
            prompt = f"""
            Analyze the following team skills and project requirements to identify skill gaps:
            
            Users and their skills:
            {json.dumps(users_df.to_dict('records'), indent=2)}
            
            Projects:
            {json.dumps(projects_df.to_dict('records'), indent=2)}
            
            Tasks:
            {json.dumps(tasks_df.to_dict('records'), indent=2)}
            
            Please provide:
            1. Team skill coverage assessment
            2. Identification of skill gaps
            3. Recommendations for addressing skill gaps
            4. Training and development suggestions
            
            Format your response as a JSON object with the following structure:
            {{
                "title": "Team Skill Gap Analysis",
                "date": "{datetime.datetime.now().strftime('%Y-%m-%d')}",
                "skill_coverage": {{
                    "percentage": 75,
                    "strong_skills": ["Skill 1", "Skill 2"],
                    "adequate_skills": ["Skill 3", "Skill 4"],
                    "gap_skills": ["Skill 5", "Skill 6"]
                }},
                "recommendations": [
                    {{
                        "skill": "Skill name",
                        "recommendation": "Recommendation text",
                        "priority": "High/Medium/Low"
                    }}
                ],
                "training_suggestions": [
                    {{
                        "skill": "Skill name",
                        "training_type": "Course/Workshop/Mentoring",
                        "description": "Description text"
                    }}
                ]
            }}
            """
        else:
            return jsonify({'success': False, 'message': 'Invalid action ID'})
        
        # Add safety settings for Gemini API
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Call Gemini API
        response = model.generate_content(
            prompt,
            safety_settings=safety_settings
        )
        
        if not response or not hasattr(response, 'text'):
            return jsonify({'success': False, 'message': f'Failed to generate {action_id} results'})
        
        # Parse the response
        try:
            result = json.loads(response.text)
            return jsonify({
                'success': True,
                'action_id': action_id,
                'data': result
            })
        except json.JSONDecodeError:
            # If the response is not valid JSON, return it as text
            return jsonify({
                'success': True,
                'action_id': action_id,
                'data': {
                    'title': f"{action_id.replace('_', ' ').title()} Results",
                    'date': datetime.datetime.now().strftime('%Y-%m-%d'),
                    'content': response.text
                }
            })
            
    except Exception as e:
        print(f"Error in quick action API: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# This route has been removed to avoid duplication with api_budget_recommendations
# @app.route('/api/budget/ai_recommendations', methods=['POST'])
# @login_required
def generate_budget_recommendations_unused():
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        project_type = data.get('project_type')
        team_size = data.get('team_size')
        duration_months = data.get('duration_months')
        complexity = data.get('complexity')
        total_budget = data.get('total_budget')
        current_breakdown = data.get('current_breakdown', '')
        
        # Get project details if project_id is provided
        project_name = "Unknown Project"
        project_description = ""
        if project_id:
            projects_df = load_data("projects")
            project = projects_df[projects_df['id'] == project_id]
            if not project.empty:
                project_name = project.iloc[0]['name']
                project_description = project.iloc[0]['description']
                if 'budget' in project.columns and not pd.isna(project.iloc[0]['budget']):
                    total_budget = project.iloc[0]['budget']
        
        prompt = f"""
        You are an expert project financial planner.
        Based on the following project details, generate an optimized budget recommendation:
        
        - Project Name: {project_name}
        - Project Description: {project_description}
        - Project Type: {project_type}
        - Team Size: {team_size} members
        - Duration: {duration_months} months
        - Project Complexity: {complexity}
        - Total Budget: ${total_budget}
        - Current Budget Breakdown (if any): {current_breakdown}
        
        Please suggest a detailed budget split (percentages or dollar amounts) across major categories like Development, Testing, Project Management, Infrastructure, Miscellaneous.
        Include specific recommendations for optimizing the budget allocation.
        """
        response = model.generate_content(prompt)
        content = response.text if hasattr(response, 'text') else str(response)
        return jsonify({"success": True, "data": {"recommendations": content, "project_name": project_name}})
    except Exception as e:
        print(f"Error generating budget recommendations: {str(e)}")
        return jsonify({"success": False, "message": f"Failed to generate recommendations: {str(e)}"})

# AI Budget Recommendations Page
# This route is commented out as it's a duplicate of /admin/ai_budget_recommendations/<project_id>
# Redirecting to the admin route for consistency
@app.route('/ai_budget_recommendations/<project_id>')
@login_required
def ai_budget_recommendations(project_id):
    """
    Redirect to the admin route for AI budget recommendations
    """
    return redirect(url_for('ai_budget_recommendations_page', project_id=project_id))

# Route 2: Task Analysis
@app.route('/api/task_analysis', methods=['POST'])
@login_required
def generate_task_analysis():
    try:
        data = request.get_json()
        task_title = data.get('task_title')
        task_description = data.get('task_description')
        prompt = f"""
        You are an expert project task analyzer.
        Analyze the following task and suggest:
        - Required skills
        - Estimated effort (in hours)
        - Possible risks
        - Improvement tips.
        Task Title: {task_title}
        Task Description: {task_description}
        
        Format your response with clear headings for each section:
        
        ## Required Skills
        - List skills here
        
        ## Estimated Effort
        - Provide hours estimate and justification
        
        ## Potential Risks
        - List risks here
        
        ## Improvement Tips
        - List tips here
        """
        
        # Add safety settings for Gemini API
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        response = model.generate_content(
            prompt,
            safety_settings=safety_settings
        )
        
        content = response.text if hasattr(response, 'text') else str(response)
        return jsonify({"status": "success", "analysis": content})
    except Exception as e:
        print(f"Error generating task analysis: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to generate task analysis"}), 500

@app.route('/api/refine_results', methods=['POST'])
@login_required
def refine_results():
    """API endpoint to refine AI-generated results based on user feedback"""
    try:
        data = request.get_json()
        title = data.get('title', '')
        content = data.get('content', '')
        refinement_prompt = data.get('refinement_prompt', '')
        
        if not refinement_prompt:
            return jsonify({'success': False, 'message': 'Refinement prompt is required'}), 400
        
        # Create a prompt for Gemini API
        prompt = f"""
        You are an AI assistant helping to refine and improve project management recommendations.
        
        Original recommendation title: {title}
        
        Original content:
        {content}
        
        User has requested the following refinement:
        "{refinement_prompt}"
        
        Please provide an improved and refined version of the original content that addresses the user's refinement request.
        Maintain the same overall structure and format as the original content (including HTML formatting),
        but enhance it according to the user's request.
        
        Return ONLY the refined HTML content that should replace the original content.
        """
        
        # Add safety settings for Gemini API
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Call Gemini API
        response = model.generate_content(
            prompt,
            safety_settings=safety_settings
        )
        
        if not response or not hasattr(response, 'text'):
            return jsonify({'success': False, 'message': 'Failed to refine results'}), 500
        
        # Return the refined content
        return jsonify({
            'success': True,
            'refined_content': response.text
        })
        
    except Exception as e:
        print(f"Error refining results: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/share_results', methods=['POST'])
@login_required
def share_results():
    """API endpoint to share AI-generated results with other users"""
    try:
        data = request.get_json()
        title = data.get('title', '')
        content = data.get('content', '')
        recipients = data.get('recipients', [])
        
        if not recipients:
            return jsonify({'success': False, 'message': 'Recipients are required'}), 400
        
        # In a real implementation, this would send emails or create notifications
        # For now, we'll just create notifications in the database
        
        user_email = session.get('user')
        user_data = load_user_data(user_email)
        
        notifications_df = load_data("notifications")
        if notifications_df.empty:
            notifications_df = pd.DataFrame(columns=sheets["notifications"]["columns"])
        
        # Create a notification for each recipient
        for recipient in recipients:
            # Check if recipient exists
            users_df = load_data("users")
            recipient_user = users_df[users_df['email'] == recipient]
            
            if recipient_user.empty:
                continue  # Skip if recipient doesn't exist
            
            recipient_id = recipient_user.iloc[0]['id']
            
            new_notification = pd.DataFrame({
                'id': [str(uuid.uuid4())],
                'user_id': [recipient_id],
                'title': ['Shared AI Recommendation'],
                'message': [f"{user_data.get('name', 'A user')} shared '{title}' with you"],
                'type': ['shared_recommendation'],
                'created_at': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                'read': [False],
                'action_url': ['/ai_recommendations']
            })
            
            notifications_df = pd.concat([notifications_df, new_notification], ignore_index=True)
        
        # Save notifications
        save_data("notifications", notifications_df)
        
        return jsonify({
            'success': True,
            'message': f'Results shared with {len(recipients)} recipients'
        })
        
    except Exception as e:
        print(f"Error sharing results: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/ai_task_analysis')
@login_required
def ai_task_analysis():
    """
    AI Task Analysis page for analyzing task descriptions to extract required skills
    and estimate complexity.
    """
    return render_template('ai_task_analysis.html')

@app.route('/ai_resource_allocation')
@login_required
def ai_resource_allocation():
    """
    AI Resource Allocation page for optimizing resource allocation across projects.
    """
    # Get current user
    user_email = session.get('user')
    user_data = load_user_data(user_email) if user_email else None
    
    # Load necessary data
    projects_df = load_data("projects")
    users_df = load_data("users")
    
    return render_template('ai_resource_allocation.html', 
                          user=user_data,
                          projects=projects_df.to_dict('records') if not projects_df.empty else [],
                          users=users_df.to_dict('records') if not users_df.empty else [])

@app.route('/ai_risk_assessment')
@login_required
def ai_risk_assessment():
    """
    AI Risk Assessment page for identifying potential risks in projects and getting
    mitigation strategies.
    """
    # Get current user
    user_email = session.get('user')
    user_data = load_user_data(user_email) if user_email else None
    
    # Load necessary data
    projects_df = load_data("projects")
    
    return render_template('ai_risk_assessment.html', 
                          user=user_data,
                          projects=projects_df.to_dict('records') if not projects_df.empty else [])

@app.route('/ai_timeline_optimization')
@login_required
def ai_timeline_optimization():
    """
    AI Timeline Optimization page for optimizing project timelines based on task
    dependencies and resource availability.
    """
    # Get current user
    user_email = session.get('user')
    user_data = load_user_data(user_email) if user_email else None
    
    # Load necessary data
    projects_df = load_data("projects")
    tasks_df = load_data("tasks")
    
    return render_template('ai_timeline_optimization.html', 
                          user=user_data,
                          projects=projects_df.to_dict('records') if not projects_df.empty else [],
                          tasks=tasks_df.to_dict('records') if not tasks_df.empty else [])

@app.route('/api/save_recommendations', methods=['POST'])
@login_required
def save_recommendations():
    """API endpoint to save AI-generated recommendations"""
    try:
        data = request.get_json()
        title = data.get('title', '')
        content = data.get('content', '')
        date = data.get('date', datetime.now().isoformat())
        
        # In a real implementation, this would save to a database
        # For now, we'll just return success
        
        return jsonify({
            'status': 'success',
            'message': 'Recommendations saved successfully'
        })
        
    except Exception as e:
        print(f"Error saving recommendations: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 500

@app.route('/api/feedback', methods=['POST'])
@login_required
def submit_feedback():
    """API endpoint to submit user feedback about AI recommendations"""
    try:
        data = request.get_json()
        feedback_type = data.get('feedback_type', 'general')
        feedback_text = data.get('feedback_text', '')
        
        if not feedback_text:
            return jsonify({'status': 'error', 'message': 'Feedback text is required'}), 400
        
        # In a real implementation, this would save to a database
        # For now, we'll just log it
        print(f"Received feedback - Type: {feedback_type}, Text: {feedback_text}")
        
        # Create a notification for the admin
        try:
            notifications_df = load_data("notifications")
            if notifications_df.empty:
                notifications_df = pd.DataFrame(columns=sheets["notifications"]["columns"])
            
            # Find admin users
            users_df = load_data("users")
            admin_users = users_df[users_df['role'] == 'admin']
            
            if not admin_users.empty:
                for _, admin in admin_users.iterrows():
                    new_notification = pd.DataFrame({
                        'id': [str(uuid.uuid4())],
                        'user_id': [admin['id']],
                        'title': ['New AI Recommendation Feedback'],
                        'message': [f"New {feedback_type} feedback: {feedback_text[:50]}..."],
                        'type': ['feedback'],
                        'created_at': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                        'read': [False],
                        'action_url': ['/ai_recommendations']
                    })
                    
                    notifications_df = pd.concat([notifications_df, new_notification], ignore_index=True)
                
                # Save notifications
                save_data("notifications", notifications_df)
        except Exception as e:
            print(f"Error creating notification for feedback: {str(e)}")
        
        return jsonify({
            'status': 'success',
            'message': 'Feedback submitted successfully'
        })
        
    except Exception as e:
        print(f"Error submitting feedback: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 500

# Route 4: Export Results
@app.route('/api/export_results', methods=['POST'])
@login_required
def export_results():
    try:
        data = request.get_json()
        export_type = data.get('export_type', 'pdf')
        content = data.get('content', '')
        title = data.get('title', 'AI Recommendations')
        
        # In a real implementation, this would generate the appropriate file
        # For now, we'll just return success
        
        return jsonify({"status": "success", "message": f"Results exported as {export_type.upper()}"})
    except Exception as e:
        print(f"Error exporting results: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to export results"}), 500

# Route for AI Task Analysis is already defined above

# Route for AI Resource Allocation is already defined above

# Route for AI Risk Assessment is already defined above

# Route for AI Timeline Optimization is already defined above

# Dynamic AI route handler for routes like /ai_timeline, /ai_risk, etc.
@app.route('/ai_<rec_id>')
@login_required
def ai_dynamic_route(rec_id):
    """
    Dynamic route handler for AI recommendation pages.
    This handles routes like /ai_timeline, /ai_risk, etc. that are referenced in the templates.
    
    Args:
        rec_id: The recommendation ID/type (e.g., 'timeline', 'risk')
    """
    # Template file should be named like ai_timeline.html, ai_risk.html, etc.
    template_path = f'ai_{rec_id}.html'
    try:
        return render_template(template_path)
    except TemplateNotFound:
        flash(f"No template found for recommendation type: {rec_id}", 'error')
        return redirect(url_for('admin_dashboard' if session.get('role') == 'admin' else 'my_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
