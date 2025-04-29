"""
Test script to diagnose numpy import issues
"""

print("Starting test...")

try:
    # First try importing datetime
    from datetime import datetime, timedelta
    print("Successfully imported datetime classes")
    
    # Now try importing numpy
    import numpy as np
    print("Successfully imported numpy")
    
    # Try matplotlib
    import matplotlib.pyplot as plt
    print("Successfully imported matplotlib")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("Test complete")