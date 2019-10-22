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
        for i in json.loads(response.text)['projects']:
            if i['type'] == "SYSTEM":
                url = "http://" + self.ip + ":8000/os/compute/v1/v2/" + i['uuid'] + "/servers/detail"
                # response1 = requests.get(url, auth=HTTPBasicAuth(self.httpuser, self.httppassword))
                response1 = requests.get(url, cookies = cookies)
                serv = json.loads(response1.text)
                print(serv)
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

    @applog.logRun(logfile)
    def getImage2Pod(self):
        cmd = "/opt/bin/kubectl -s 127.0.0.1:8888 get pod | awk 'NR>1{print $1}'| while read line;do " \
              "/opt/bin/kubectl -s 127.0.0.1:8888 describe pod $line | grep Image: |awk -v var1=$line '" \
              "{print var1,$2}' | cut -d : -f 1;done"
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        stdin, stdout, stderr = ssh.exec_command(cmd)
        text = stdout.read().decode().strip()
        dic1 = {}
        for i in text.splitlines():
            dic1[i.split()[1]] = i.split()[0]
        ssh.close()
        return dic1

    @applog.logRun(logfile)
    def containerServiceCollect(self):
        servicedict = {
            "cloudos-openstack-glance": ["ftp-server.service","openstack-glance-api.service",
                                         "openstack-glance-registry.service"],
            "cloudos-neutron-server": ["neutron-server.service"],
            "cloudos-neutron-agent": ["h3c-agent.service"],
            "cloudos-openstack-ceilometer": ["openstack-ceilometer-api.service", "openstack-ceilometer-collector.service",
                                             "openstack-ceilometer-notification.service"],
            "cloudos-openstack-cinder": ["openstack-cinder-api.service", "openstack-cinder-scheduler.service"],
            "cloudos-openstack-compute": ["openstack-ceilometer-compute.service","openstack-cinder-volume.service",
                                          "openstack-neutron-cas-agent.service","openstack-nova-compute.service"],
            "cloudos-openstack-nova": ["openstack-nova-api.service", "openstack-nova-cert.service", "openstack-nova-conductor.service",
                                       "openstack-nova-consoleauth.service","openstack-nova-novncproxy.service","openstack-nova-scheduler.service"]
        }
        self.osInfo['serviceStatus'] = {}
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        podList = self.getImage2Pod()
        for i in servicedict.keys():
            pod = podList[i]
            self.osInfo['serviceStatus'][pod] = []
            for j in servicedict[i]:
                dic1 = {}
                dic1['name'] = j
                cmd ="/opt/bin/kubectl -s 127.0.0.1:8888 exec -it " + pod +" systemctl status " + j + " | grep Active | awk '{print $3}'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                sshout = stdout.read().decode().strip()
                if sshout != '':
                    status = re.findall(r'\((.*?)\)', sshout)[0]
                    # status = re.findall(r'\((.*?)\)', stdout.read().decode().strip())[0]
                else:
                    status = "running"
                if status == "running":
                    dic1['status'] = True
                else:
                    dic1['status'] = False
                self.osInfo['serviceStatus'][pod].append(dic1.copy())
        ssh.close()
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
                        if set1 == images.imagesv3Set:
                            i["images"] = set()
                        else:
                            i["images"] = images.imagesv3Set.difference(set1)
                    else:
                        if set1 == images.imagesv3Set - {'registry'}:
                            i["images"] = set()
                        else:
                            i["images"] = images.imagesv3Set.difference(set1)
                else:
                    print("docker Image check ssh is invalid")
        ssh.close()
        return