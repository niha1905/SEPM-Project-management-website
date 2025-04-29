import sys
print("Python version:", sys.version)
print("Python path:", sys.path)

try:
    import datetime
    print("Successfully imported datetime")
except Exception as e:
    print("Error importing datetime:", e)

try:
    import numpy
    print("Successfully imported numpy")
except Exception as e:
    print("Error importing numpy:", e)

try:
    import pandas
    print("Successfully imported pandas")
except Exception as e:
    print("Error importing pandas:", e)