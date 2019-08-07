from shell import casDocumentCreate
from shell import cloudosDocumentCreate
from docx import Document
import time
from tcpping import tcpping


def hostStatusCheck(hostInfo):
    error = str()
    for i in hostInfo:
        temp = str()
        #ssh端口检查
        if not tcpping(i['ip'], i['sshPort']):
            if not temp:
                temp = '\n主机'+i['ip']+'ssh端口连通异常'
            else:
                temp += 'ssh端口连通异常'
        if not tcpping(i['ip'], i['httpPort']):
            if not temp:
                temp = '\n主机'+i['ip']+'http端口连通异常'
            else:
                temp += 'ssh端口连通异常'
        error += temp
        del temp
    return error


def Check():
    a = "巡检完成"
    return a

# document = Document()
#
# cas = casDocumentCreate.casCheck('192.168.2.15', 'admin', 'admin', 'root', 'h3c.com!')
# casDocumentCreate.cvmCheck(document, cas)
# casDocumentCreate.clusterCheck(document, cas)
# casDocumentCreate.cvkCheck(document, cas)
# casDocumentCreate.vmCheck(document, cas)
# casDocumentCreate.cvmHaChech(document, cas)
#
# os = cloudosDocumentCreate.cloudosCheck('192.168.2.189', 'root', 'cloudos', 'admin', 'cloudos')
# cloudosDocumentCreate.osBasicCheck(document, os)
# cloudosDocumentCreate.osPlatCheck(document, os)
#
# file = time.time()
# document.save('test1.docx')
