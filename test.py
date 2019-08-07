import os
import time
from datetime import datetime

directory = os.getcwd()
time_now1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
time_now2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(directory)
print(os.path.join(os.getcwd(), 'check_result'))
print(time_now1)
print(time_now2)
print(datetime.date())