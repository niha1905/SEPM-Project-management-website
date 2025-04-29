"""
Script to fix datetime imports and usage in app.py
"""

def fix_datetime_imports():
    # Read the file
    with open('app.py', 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Replace the import statement
    content = content.replace(
        'import datetime', 
        'from datetime import datetime, timedelta, date  # Import specific components instead of the whole module'
    )
    
    # Replace all instances of datetime.datetime with datetime
    content = content.replace('datetime.datetime', 'datetime')
    
    # Write the changes back to the file
    with open('app.py', 'w', encoding='utf-8') as file:
        file.write(content)
    
    print("Successfully fixed datetime imports and usage in app.py")

if __name__ == "__main__":
    fix_datetime_imports()