from shell import casDocumentCreate
from shell import cloudosDocumentCreate
from docx import Document
from tcpping import tcpping
import time, os

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


def Check(hostInfo, logfile):
    status = hostStatusCheck(hostInfo)
    document = Document()
    result = {"filename" : '', "content" : ''}
    for i in hostInfo:
        if i['role'] == 'cvm':
            logfile.addLog("####cas collectdata begin####")
            cas = casDocumentCreate.casCheck(i['ip'], i['httpUser'], i['httpPassword'], i['sshUser'], i['sshPassword'],logfile)
            logfile.addLog("cvm check document create")
            casDocumentCreate.cvmCheck(document, cas)
            logfile.addLog("cas cluster document creat")
            casDocumentCreate.clusterCheck(document, cas)
            logfile.addLog("cas cvk cluster document create")
            casDocumentCreate.cvkCheck(document, cas)
            logfile.addLog("cas vm check document create")
            casDocumentCreate.vmCheck(document, cas)
            logfile.addLog("cas cvm ha lb document crate")
            casDocumentCreate.cvmHaCheck(document, cas)
            del cas

        elif i['role'] == 'cloudos':
            logfile.addLog("####cloudos check#####")
            cloud = cloudosDocumentCreate.cloudosCheck(i['ip'], i['sshUser'], i['sshPassword'], i['httpUser'], i['httpPassword'], logfile)
            logfile.addLog("cloudos basic info document create")
            cloudosDocumentCreate.osBasicCheck(document, cloud)
            logfile.addLog("cloudos plat document create")
            cloudosDocumentCreate.osPlatCheck(document, cloud)
        result['content'] += i['role'] + '\t'

    filename = "巡检文档" + time.strftime("%Y%m%d%H%M", time.localtime())+".docx"
    path = os.getcwd() + "//check_result//" + filename
    document.save(path)
    result['filename'] = filename
    return result



# hostInfo = []
# cvm = {"ip":"192.168.2.5",'role':'cvm','sshUser':'root','sshPassword':'h3c.com!','httpUser':'admin','httpPassword':'admin', 'sshPort':22, 'httpPort':8080}
# hostInfo.append(cvm)
# print(hostInfo)
# Check(hostInfo)