from shell import casDocumentCreate
from shell import cloudosDocumentCreate
from shell.CollectData import casCollect
from shell.CollectData import cloudosCollect
from docx import Document
from tcpping import tcpping
import time
import os

def hostStatusCheck(hostInfo):
    error = str()
    for i in hostInfo:
        temp = str()
        #ssh端口检查
        if not tcpping(i['ip'], i['sshPort'], 2):
            print("ssh port invalid")
            if not temp:
                temp = '<br/>主机'+i['ip']+'&nbspssh端口连通异常'
            else:
                temp += ',ssh端口连通异常'
        if not tcpping(i['ip'], i['httpPort'], 2):
            print("http port invalid")
            if not temp:
                temp = '<br/>主机'+i['ip']+'&nbsphttp端口连通异常'
            else:
                temp += ',http端口连通异常'
        error += temp
        del temp
    return error


def Check(hostInfo):
    status = hostStatusCheck(hostInfo)
    document = Document()
    result = {"filename" : '', "content" : ''}
    for i in hostInfo:
        if i['role'] == 'cvm':
            print("巡检项：", i['check_item'])
            casInfo = casCollect(i['ip'], i['sshUser'], i['sshPassword'], i['httpUser'], i['httpPassword'], i['check_item'])
            casDocumentCreate.cvmCheck(document, casInfo)
            casDocumentCreate.clusterCheck(document, casInfo)
            casDocumentCreate.cvkCheck(document, casInfo)
            if i['check_item'] == 1:
                casDocumentCreate.vmCheck(document, casInfo)
            casDocumentCreate.cvmHaCheck(document, casInfo)

        elif i['role'] == 'cloudos':
            osInfo = cloudosCollect(i['ip'], i['sshUser'], i['sshPassword'], i['httpUser'], i['httpPassword'])
            cloudosDocumentCreate.osBasicCheck(document, osInfo)
            cloudosDocumentCreate.osPlatCheck(document, osInfo)
        result['content'] += i['role'] + '\t'

    filename = "巡检文档" + time.strftime("%Y%m%d%H%M", time.localtime())+".docx"
    path = os.getcwd() + "//check_result//" + filename
    document.save(path)
    result['filename'] = filename
    return result