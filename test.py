import os
import time
from datetime import datetime
import docx

# directory = os.getcwd()
# time_now1 = time.strftime("%Y%m%d%H%M%S", time.localtime())
# time_now2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# print(directory)
# print(os.path.join(os.getcwd(), 'check_result'))
# print(time_now1)
# print(time_now2)
# print(datetime.date())

filename = os.getcwd() + '\\check_result\\' + "巡检文档201908081510.docx"
# filename = os.getcwd()
print(filename)
os.remove(filename)
