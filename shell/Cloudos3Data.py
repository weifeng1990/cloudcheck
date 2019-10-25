from requests.auth import HTTPBasicAuth
import json
import re
import requests
import paramiko
from shell.Cloudos2Data import Cloudos2Data
from shell import images, applog

logfile = applog.Applog()

class Cloudos3Data(Cloudos2Data):
    @applog.logRun(logfile)
    def imageCollect(self):
        self.osInfo["imagesStatus"] = []
        respond = requests.get("http://" + self.ip + ":8000/os/image/v1/v2/images",
                               auth=HTTPBasicAuth(self.httpuser, self.httppassword))
        if respond.text:
            tmp = json.loads(respond.text)
            if 'images' in tmp.keys():
                for i in tmp['images']:
                    dict1 = {}
                    dict1['name'] = i['name']
                    dict1['status'] = i['status']
                    self.osInfo["imagesStatus"].append(dict1.copy())
                    del dict1
        respond.close()
        return

    @applog.logRun(logfile)
    def vmCollect(self):
        self.osInfo['vmStatus'] = []
        response = requests.get("http://" + self.ip + ":8000/sys/identity/v2/projects",
                                auth=HTTPBasicAuth(self.httpuser, self.httppassword))
        cookies = response.cookies
        print(response.text)
        for i in json.loads(response.text)['projects']:
            print(i)
            if i['type'] == "SYSTEM":
                print(i['uuid'])
                url = "http://" + self.ip + ":8000/os/compute/v1/v2/" + i['uuid'] + "/servers/detail"
                # response1 = requests.get(url, auth=HTTPBasicAuth(self.httpuser, self.httppassword))
                response1 = requests.get(url, cookies = cookies)
                serv = json.loads(response1.text)
                response1.close()
                if 'servers' in serv.keys():
                    for j in serv['servers']:
                        dict1 = {}
                        dict1['name'] = j['name']
                        dict1['status'] = j['status']
                        self.osInfo['vmStatus'].append(dict1.copy())
                        del dict1
        response.close()
        return

    @applog.logRun(logfile)
    def vdiskCollect(self):
        response = requests.get("http://" + self.ip + ":8000/sys/identity/v2/projects",
                                auth=HTTPBasicAuth(self.httpuser, self.httppassword))
        self.osInfo['vDiskStatus'] = []
        cookies = response.cookies
        for i in json.loads(response.text)['projects']:
            if i['type'] == "SYSTEM":
                url = "http://" + self.ip + ":8000/os/storage/v1/v2/" + i['uuid'] + "/volumes/detail"
                # response1 = requests.get(url, auth=HTTPBasicAuth(self.httpuser, self.httppassword))
                response1 = requests.get(url, cookies=cookies)
                for j in json.loads(response1.text)['volumes']:
                    dict1 = {}
                    dict1['name'] = j['name']
                    dict1['status'] = j['status']
                    self.osInfo['vDiskStatus'].append(dict1.copy())
                    del dict1
                response1.close()
        response.close()
        return

    @applog.logRun(logfile)
    def listConfliction(self, li):
        li3 = []
        for i in range(len(li)):
            key = li[i]
            for j in range(i + 1, len(li)):
                if key == li[j] and li not in li3:
                    li3.append(key)
        return li3

    #获取冲突的计算节点
    @applog.logRun(logfile)
    def computeCollect(self):
        response = requests.get("http://" + self.ip + ":8000/os/compute/v1/h3cloudos/computenode",
                                auth=HTTPBasicAuth(self.httpuser, self.httppassword))
        li = json.loads(response.text)
        response.close()
        li2 = []
        dic = {}
        for i in self.listConfliction(li):
            dic['name'] = i['hostName']
            dic['ip'] = i['hostIp']
            dic['poolName'] = i['poolName']
            li2.append(dic.copy())
        self.osInfo['computeConfliction'] = li2.copy()
        del dic
        del li2
        return

    #检查容器镜像是否完整
    @applog.logRun(logfile)
    def dockerImageCheck(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            i['images'] = set()
            set1 = set()
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i['hostName'] + "\tdocker images | awk 'NR>1{print $1}' | grep -v gcr | grep -v\t" + self.osInfo['masterIP']
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    text = stdout.read().decode()
                    for j in text.splitlines():
                        set1.add(j)
                    # 当为v2版本使用v2的镜像集合进行对比
                    if i['hostName'] == self.osInfo['masterIP']:
                        if set1 != images.imagesv3Set:
                            i["images"] = images.imagesv3Set.difference(set1)
                    else:
                        if set1 != images.imagesv3Set - {'registry'}:
                            i["images"] = (images.imagesv3Set - {'registry'}).difference(set1)
                else:
                    print("docker Image check ssh is invalid")
        ssh.close()
        return