# Project Management System

A Flask-based project management system that uses Excel as its database.

## Features

- User authentication (Admin and User roles)
- Project management
- Task tracking
- Meeting scheduling
- Team management
- Reports and analytics
- File uploads
- AI-powered chatbot assistance

## Setup Instructions

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with the following variables:
```
FLASK_SECRET_KEY=your-secret-key-here
GEMINI_API_KEY=your-gemini-api-key-here
```

4. Create required directories:
```bash
mkdir static
mkdir static/uploads
```

5. Run the application:
```bash
python app.py
```

## Database Structure

The application uses an Excel file (`project_management.xlsx`) with the following sheets:

- users: User information and authentication
- projects: Project details and status
- tasks: Task assignments and tracking
- meetings: Meeting schedules and participants
- timeline: Project progress updates
- settings: System configuration

## Default Admin Account

- Email: admin@admin.com
- Password: admin123

## User Registration

- Admin accounts: Use @admin.com email domain
- Regular users: Use @gmail.com email domain

## Security Features

- Password hashing
- Session management
- Role-based access control
- File upload restrictions
- Activity logging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 