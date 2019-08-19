from requests.auth import HTTPDigestAuth
from requests.auth import HTTPBasicAuth
import json, re, math, xmltodict, requests, paramiko

# 获取cas版本：cat /etc/cas_cvk-version | awk 'NR==1{print $1}'
# 服务器的型号： dmidecode | grep -i product | awk 'NR==1{print $3,$4,$5 }'
# 服务器规格：lscpu | cut -d : -f 2 | awk 'NR==4 || NR==7{print $1}';free -g | awk 'NR==2{print $2}'
# 集群节点数：crm status | grep Online | awk '{print NF-3}'
# S1020v版本：ovs-vsctl -V | grep -i version | awk '{print $4}'


class casCollect:
    # 读取ip、username，password
    def __init__(self, ip, username, password, sshUser, sshPassword):
        self.host = ip
        self.url = "http://" + ip + ":8080/cas/casrs/"
        self.httpAuth = HTTPDigestAuth(username, password)
        self.casInfo = dict()
        self.sshUser = sshUser
        self.sshPassword = sshPassword
        return

    # 获取cvm基础信息：版本信息、服务器版本、服务器规格、部署方式
    def cvmBasicCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy)
        print("ssh连接##########", self.host, self.sshUser, self.sshPassword)
        ssh.connect(self.host, 22, self.sshUser, self.sshPassword)
        #服务器硬件型号
        stdin, stdout, stderr = ssh.exec_command("dmidecode | grep -i product | awk 'NR==1{print $3,$4,$5 }'")
        if not stderr.read():
            self.casInfo['productVersion'] = stdout.read().decode()
        else:
            print(" product version error")
        #服务规格
        stdin, stdout, stderr = ssh.exec_command("lscpu | cut -d : -f 2 | awk 'NR==4 || NR==7{print $1}';free -g | awk 'NR==2{print $2}'")
        if not stderr.read():
            text = stdout.read().decode()
            a = text.splitlines()
            self.casInfo['deviceDmide'] = "cpu:" + a[0]+"*"+a[1]+"cores"+"\nMem:"+a[2]+'G'
        else:
            print("device dmide error")

        # cas版本
        stdin, stdout, stderr = ssh.exec_command("cat /etc/cas_cvk-version | awk 'NR==1{print $1}'")
        if not stderr.read():
            self.casInfo['casVersion'] = stdout.read().decode()
        else:
            print("cas version error")

        #部署方式
        stdin, stdout, stderr = ssh.exec_command("crm status | grep Online | awk '{print NF-3}'")
        if not stderr.read():
            text = stdout.read().decode()
            if text == '1':
                self.casInfo["installType"] = "单机部署"
            else :
                self.casInfo["installType"] = "集群部署"
        else:
            print("install type error")
        #1020v版本：
        stdin, stdout, stderr = ssh.exec_command("ovs-vsctl -V | awk 'NR==1{print $0}'")
        if not stderr.read():
            self.casInfo['ovsVersion'] = stdout.read().decode()
        else:
            print("ovs version error")
        # license 信息
        self.casInfo['licenseInfo'] = 'NONE'
        ssh.close()
        return


    #####################################################
    # time:2019.4.28                                    #
    # function：集群巡检功能      author：wf             #
    #####################################################
    def clusterCollect(self):
        response = requests.get(self.url + 'cluster/clusters/', auth=self.httpAuth)
        contxt = response.text
        response.close()
        dict1 = xmltodict.parse(contxt)['list']['cluster']
        temp = list()
        if isinstance(dict1, dict):
            temp.append(dict1)
        else:
            temp = dict1.copy()
        self.casInfo['clusterInfo'] = list()
        tempInfo = dict()
        for i in temp:
            # 获取集群的id,name,HA状态，cvk数量，LB状态
            tempInfo['id'] = i['id']
            tempInfo['name'] = i['name']
            tempInfo['enableHA'] = i['enableHA']
            tempInfo['cvkNum'] = (int)(i['childNum'])
            tempInfo['enableLB'] = i['enableSLB']
            self.casInfo['clusterInfo'].append(tempInfo.copy())
        # 获取集群HA最小主机数量
        for i in self.casInfo['clusterInfo']:
            response = requests.get(self.url + 'cluster/' + i['id'], auth=self.httpAuth)
            contxt = response.text
            response.close()
            dict1 = xmltodict.parse(contxt)
            i['HaMinHost'] = dict1['cluster']['HaMinHost']
        del temp
        return

        ####################################################################
        # 获取主机ID、NAME、状态、虚拟机数量、cpu使用率、内存使用率            #
        ####################################################################
    def cvkBasicCollect(self):
        # 初始化cvk数据结构
        for i in self.casInfo['clusterInfo']:
            i['cvkInfo'] = list()
            response = requests.get(self.url + 'cluster/hosts?clusterId=' + i['id'], auth=self.httpAuth)
            contxt = response.text
            response.close()
            dict1 = xmltodict.parse(contxt)['list']['host']
            temp1 = list()
            if isinstance(dict1, dict):
                temp1.append(dict1)
            else:
                temp1 = dict1.copy()
            for j in temp1:
                temp2 = dict()
                temp2['id'] = j['id']
                temp2['name'] = j['name']
                temp2['status'] = j['status']
                temp2['ip'] = j['ip']
                temp2['vmNum'] = j['vmNum']
                temp2['cpuRate'] = (float)(j['cpuRate'])
                temp2['memRate'] = (float)(j['memRate'])
                i['cvkInfo'].append(temp2.copy())
                del temp2
            del temp1
        return


    ##################################################
    #主机共享存储利用率/cas/casrs/host/id/{id}/storage#
    #获取主机共享存储池信
    ##################################################
    def cvkSharepoolCollect(self):
        for i in self.casInfo['clusterInfo']:
            for k in i['cvkInfo']:
                response = requests.get(self.url + 'host/id/' + k['id'] + '/storage', auth=self.httpAuth)
                contxt1 = response.text
                response.close()
                dict1 = xmltodict.parse(contxt1)
                list1 = list()
                dict2 = dict()
                k['sharePool'] = list()
                if isinstance(dict1['list'], dict):
                    if 'storagePool' in dict1['list']:
                        if isinstance(dict1['list']['storagePool'], dict):
                            list1.append(dict1['list']['storagePool'])
                        else:
                            list1 = dict1['list']['storagePool']
                        for j in list1:
                            dict2['name'] = j['name']
                            dict2['rate'] = 1 - (float)(j['freeSize']) / (float)(j['totalSize'])
                            dict2['path'] = j['path']
                            k['sharePool'].append(dict2.copy())
                            # print(k['name'], j['name'],dict2['rate'])
                del list1
                del dict2
        return

    ##############################################################
    # 获取CVK主机磁盘利用率
    # cas版本为V5.0 (E0530)时，api获取磁盘利用率信息不正确，cas软件bug
    ##############################################################
    def cvkDiskCollect(self):
        for i in self.casInfo['clusterInfo']:
            for k in i['cvkInfo']:
                response = requests.get(self.url + 'host/id/' + k['id'] + '/monitor', auth=self.httpAuth)
                contxt1 = response.text
                response.close()
                k['diskRate'] = list()
                dict1 = xmltodict.parse(contxt1)['host']['disk']
                temp = list()
                if isinstance(dict1, dict):
                    temp.append(dict1)
                else:
                    temp = dict1.copy()
                for h in temp:
                    temp1 = dict()
                    temp1['name'] = h['device']
                    temp1['usage'] = (float)(h['usage'])
                    k['diskRate'].append(temp1.copy())
                    del temp1
                del temp
        return


        ##############################################################
        # 获取CVK主机虚拟交换机信息
        ##############################################################
    def cvkVswitchCollect(self):
        for i in self.casInfo['clusterInfo']:
            for k in i['cvkInfo']:
                response = requests.get(self.url + '/host/id/' + k['id'] + '/vswitch', auth=self.httpAuth)
                contxt1 = response.text
                response.close()
                k['vswitch'] = list()
                dict1 = xmltodict.parse(contxt1)['list']
                temp = list()
                if isinstance(dict1, dict):
                    if isinstance(dict1['vSwitch'], dict):
                        temp.append(dict1['vSwitch'])
                    else:
                        temp = dict1['vSwitch'].copy()
                        for h in temp:
                            temp1 = dict()
                            temp1['name'] = h['name']
                            temp1['status'] = h['status']
                            temp1['pnic'] = h['pnic']
                            k['vswitch'].append(temp1.copy())
                            del temp1
                del temp
                del dict1
        return

    ################################################################################
    # 获取cvk主机的存储池信息
    ################################################################################
    def cvkStorpoolCollect(self):
        for i in self.casInfo['clusterInfo']:
            for k in i['cvkInfo']:
                response = requests.get(self.url + 'storage/pool?hostId=' + k['id'], auth=self.httpAuth)
                contxt1 = response.text
                response.close()
                k['storagePool'] = list()
                dict1 = xmltodict.parse(contxt1)['list']['storagePool']
                temp = list()
                if isinstance(dict1, dict):
                    temp.append(dict1)
                else:
                    temp = dict1.copy()
                for h in temp:
                    temp1 = dict()
                    temp1['name'] = h['name']
                    temp1['status'] = h['status']
                    k['storagePool'].append(temp1.copy())
                    del temp1
                del temp
        return

    # 获取cvk主机的网卡信息
    def cvkNetsworkCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.host, 22, self.sshUser, self.sshPassword, look_for_keys=False, allow_agent=False)
        for i in self.casInfo['clusterInfo']:
            for k in i['cvkInfo']:
                cmd = "ssh  " + k[
                    'ip'] + " ifconfig -a | grep eth | awk '{print $1}' | while read line;do ethtool $line | grep -e eth -e Duplex -e Speed -e Link;done"
                k['network'] = list()
                stdin, stdout, stderr = ssh.exec_command(cmd)
                temp2 = dict()
                if not stderr.read():
                    temp1 = stdout.read().decode()
                    j = 0
                    for h in temp1.split():
                        if h == "(255)":
                            continue
                        if not (j - 2) % 10:
                            temp2['name'] = h.split(':')[0]
                        elif not (j - 4) % 10:
                            temp2['speed'] = h.split('M')[0]
                        elif not (j - 6) % 10:
                            temp2['duplex'] = h
                        elif not (j - 9) % 10:
                            temp2['status'] = h
                        if j > 0 and (j % 10 == 0):
                            k['network'].append(temp2.copy())
                        j += 1
                    del temp1
                else:
                    print(stderr.read().decode())
                del temp2
        ssh.close()
        return

    # 获取虚拟机的id,name,虚拟机状态，castool状态，cpu利用率，内存利用率
    def vmBasicCollect(self):
        for i in self.casInfo['clusterInfo']:
            for j in i['cvkInfo']:
                j['vmInfo'] = list()
                response = requests.get(self.url + 'vm/vmList?hostId=' + j['id'], auth=self.httpAuth)
                contxt = response.text
                response.close()
                dict2 = xmltodict.parse(contxt)
                if isinstance(dict2['list'], dict):
                    if 'domain' in dict2['list']:
                        dict1 = xmltodict.parse(contxt)['list']['domain']
                    else:
                        continue
                else:
                    continue
                temp1 = list()
                if isinstance(dict1, dict):
                    temp1.append(dict1)
                else:
                    temp1 = dict1.copy()
                for k in temp1:
                    temp2 = dict()
                    temp2['id'] = k['id']
                    temp2['name'] = k['name']
                    temp2['status'] = k['vmStatus']
                    if temp2['status'] == 'running':
                        if 'castoolsStatus' in k.keys():
                            temp2['castoolsStatus'] = k['castoolsStatus']
                        else:
                            temp2['castoolsStatus'] = '0'
                        temp2['cpuReate'] = (float)(k['cpuRate'])
                        temp2['memRate'] = (float)(k['memRate'])
                    j['vmInfo'].append(temp2.copy())
                    del temp2
                del temp1
        return


    #虚拟机磁盘分区利用率
    def vmDiskRateCollect(self):
        for i in self.casInfo['clusterInfo']:
            for j in i['cvkInfo']:
                for k in j['vmInfo']:
                    if k['status'] == 'running':
                        k['diskRate'] = list()
                        response = requests.get(self.url + 'vm/id/' + k['id']+'/monitor', auth=self.httpAuth)
                        contxt1 = xmltodict.parse(response.text)
                        response.close()
                        list1 = list()
                        if isinstance(contxt1['domain'], dict) and 'partition' in contxt1['domain'].keys():
                            if isinstance(contxt1['domain']['partition'], dict):
                                list1.append(contxt1['domain']['partition'])
                            else:
                                list1 = (contxt1['domain']['partition']).copy()
                            dict1 = dict()
                            for m in list1:
                                dict1['name'] = m['device']
                                dict1['usage'] = (float)(m['usage'])
                                k['diskRate'].append(dict1.copy())
                        del list1
        return


    # 虚拟机磁盘信息
    def vmDiskCollect(self):
        for i in self.casInfo['clusterInfo']:
            for j in i['cvkInfo']:
                for k in j['vmInfo']:
                    if k['status'] == 'running':
                        k['vmdisk'] = list()
                        response = requests.get(self.url + 'vm/detail/' + k['id'], auth=self.httpAuth)
                        contxt1 = xmltodict.parse(response.text)
                        response.close()
                        dict2 = dict()
                        dict1 = dict()
                        if 'domain' in contxt1.keys():
                            if 'storage' in contxt1['domain'].keys():
                                dict1 = contxt1['domain']['storage']
                            if 'network' in contxt1['domain'].keys():
                                dict2 = contxt1['domain']['network']
                        else:
                            continue
                        temp1 = list()
                        if isinstance(dict1, dict):
                            temp1.append(dict1)
                        else:
                            temp1 = dict1.copy()
                        for h in temp1:
                            temp2 = dict()
                            if h['device'] == 'disk':
                                temp2['name'] = h['deviceName']
                                if 'format' in h.keys():
                                    temp2['format'] = h['format']
                                else:
                                    temp2['format'] = 'NULL'
                                if 'cacheType' in h.keys():
                                    temp2['cacheType'] = h['cacheType']
                                else:
                                    temp2['cacheType'] = 'NULL'
                                if 'path' in h.keys():
                                    temp2['path'] = h['path']
                                else:
                                    temp2['path'] = 'NULL'
                                k['vmdisk'].append(temp2.copy())
                            del temp2
                        del temp1
                        del dict1
                        del dict2
        return

    # 虚拟机网卡巡检
    def vmNetworkCollect(self):
        for i in self.casInfo['clusterInfo']:
            for j in i['cvkInfo']:
                for k in j['vmInfo']:
                    if k['status'] == 'running':
                        k['vmNetwork'] = list()
                        response = requests.get(self.url + 'vm/detail/' + k['id'], auth=self.httpAuth)
                        contxt1 = xmltodict.parse(response.text)
                        response.close()
                        dict1 = dict()
                        if 'domain' in contxt1.keys():
                            if 'network' in contxt1['domain'].keys():
                                dict1 = contxt1['domain']['network']
                        else:
                            continue
                        temp1 = list()
                        if isinstance(dict1, dict):
                            temp1.append(dict1)
                        else:
                            temp1 = dict1.copy()
                        for h in temp1:
                            temp2 = dict()
                            if h:
                                temp2['name'] = h['vsName']
                                temp2['mode'] = h['deviceModel']
                                temp2['KernelAccelerated'] = h['isKernelAccelerated']
                                k['vmNetwork'].append(temp2.copy())
                                del temp2
                        del temp1
                        del dict1
        return

    # cvm双机热备信息
    def cvmHACollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.host, 22, self.sshUser, self.sshPassword, look_for_keys=False, allow_agent=False)
        stdin, stdout, stderr = ssh.exec_command("crm status | grep OFFLINE")
        if not stderr.read():
            a = stdout.read().decode()
            if not a:
                self.casInfo['HA'] = True
            else:
                self.casInfo['HA'] = False
        return

    #CVM备份策略是否开启
    # mysql -uroot -p1q2w3e -Dvservice -e'select STATE from TBL_BACKUP_CVM_STRATEGY;' | awk 'NR>1{print $0}'
    def cvmBackupEnbleCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.host, 22, self.sshUser, self.sshPassword, look_for_keys=False, allow_agent=False)
        stdin, stdout, stderr = ssh.exec_command(
            "mysql -uroot -p1q2w3e@4R -Dvservice -e'select STATE from TBL_BACKUP_CVM_STRATEGY;' | awk 'NR>1{print $0}'")
        a = stdout.read().decode()
        if not a:
            self.casInfo['BackupEnable'] = False
        else:
            self.casInfo['BackupEnable'] = True
        return

    #虚拟机备份策略
    def vmBackupPolicyCollect(self):
        response = requests.get(self.url + 'backupStrategy/backupStrategyList', auth=self.httpAuth)
        contxt =response.text
        response.close()
        text = xmltodict.parse(contxt)['list']
        list1 = list()
        if not 'backupStrategy' in text:
            self.casInfo['vmBackPolicy'] = 'NONE'
        else:
            self.casInfo['vmBackPolicy'] = list()
            if isinstance(text['backupStrategy'], dict):
                list1.append(text['backupStrategy'])
            else:
                list1 = (text['backupStrategy']).copy()
            dict1 = dict()
            for i in list1:
                dict1['name'] = i['name']
                dict1['state'] = i['state']
                self.casInfo['vmBackPolicy'].append(dict1)
            del dict1
        del list1, text
        return

class cloudosCollect:
    def __init__(self, ip, sshuser, sshpassword, httpuser, httppassword):
        self.ip = ip
        self.sshuser = sshuser
        self.sshpassword = sshpassword
        self.httpuser = httpuser
        self.httppassword = httppassword
        # self.token = self.getToken(ip, httpuser, httppassword)
        self.auth = HTTPBasicAuth(httpuser, httppassword)
        self.osInfo = dict()
        return


    # 获取Token
    def getToken(self, ip, username, password):
        data = {"auth": {"identity": {"methods": ["password"], "password": {"user": {
            "name": "", "password": "", "domain": {"id": "default"}}}}, "scope": {"project": {
            "name": "admin", "domain": {"id": "default"}}}}}

        #3.0 body字段
        # data = {
        #     "identity": {
        #         "method": "password",
        #         "user": {
        #             "name": "admin",
        #             "password": "admin"
        #         }
        #     }
        # }
        # cloudos 3.0 url：
        # url = "http://" + ip + ":8000/sys/identity/v2/tokens"

        data['auth']['identity']['password']['user']['name'] = username
        data['auth']['identity']['password']['user']['password'] = password
        print(username,password)
        print(json.dumps(data))
        headers = {'content-type': 'application/json', 'Accept': 'application/json', 'X-Auth-Token': ''}
        url = "http://" + ip + ":9000/v3/auth/tokens"
        respond = requests.post(url, json.dumps(data), headers=headers)
        token = respond.headers['X-Subject-Token']
        respond.close()
        return token

    #获取cloudos服务器硬件信息和软件版本
    def cloudosBasicCellect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        #服务器型号
        stdin, stdout, stderr = ssh.exec_command("dmidecode | grep -i product | awk '{print $0}' | cut -d : -f 2")
        if not stderr.read():
            self.osInfo['productVersion'] = stdout.read().decode()

        #服务器规格
        stdin, stdout, stderr = ssh.exec_command("lscpu | cut -d : -f 2 | awk 'NR==4 || NR==7{print $1}';free -g | awk 'NR==2{print $2}'")
        if not stderr.read():
            text = stdout.read().decode()
            str1 = text.splitlines()
            self.osInfo['deviceDmide'] = "cpu:" + str1[0] + "*" + str1[1] + "cores" + "\nMem:" + str1[2] + 'G'

        #cloudos版本
        stdin, stdout, stderr = ssh.exec_command('cat /opt/matrix/version.json')
        if not stderr.read():
            text = stdout.read().decode()
            for i in json.loads(text)['unit']:
                if i['name'] == 'cloudos-openstack':
                    self.osInfo['version'] = i['ver']
        ssh.close()
        return

    # 发现Node节点设备、并查询状态
    def NodeCollect(self):
        self.osInfo["nodeInfo"] = list()
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        stdin, stdout, stderr = ssh.exec_command(
            "/opt/bin/kubectl -s 127.0.0.1:8888 get nodes | awk 'NR>1{print $1,$2}'")
        if not stderr.read():
            line = stdout.readline()
            while line:
                dict1 = dict()
                dict1['hostName'] = line.split()[0]
                dict1['status'] = line.split()[1]
                self.osInfo['nodeInfo'].append(dict1)
                line = stdout.readline()
        else:
            print(stderr.read())
        ssh.close()
        return

    #发现主节点
    def findMaster(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        self.osInfo['masterIP'] = "NONE"
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i["hostName"] + "\tsystemctl status deploy-manager | grep Active | awk '{print $3}' | sed -e 's/(//g' | sed -e 's/)//g'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                text = stdout.read().decode().strip()
                if text == 'running':
                    self.osInfo['masterIP'] = i["hostName"]
        return

    #查看磁盘分区空间分配是否合规
    #规格：centos-root>201G,centos-swap>33.8G,centos-metadata>5.3G,centos-data>296G
    def diskCapacity(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                i['diskCapacity'] = list()
                cmd = "ssh\t" + i["hostName"] + "\tfdisk -l | grep /dev/mapper/centos | awk '{print $2,$5/1000/1000/1000}' | sed -e 's/://g' | sed -e 's/\/dev\/mapper\///g'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                text = stdout.read().decode()
                lines = text.splitlines()
                for j in lines:
                    dict1 = dict()
                    dict1['name'] = j.split()[0]
                    dict1['capacity'] = (float)(j.split()[1])
                    i['diskCapacity'].append(dict1.copy())
                    del dict1
        return

    # 查询磁盘利用率，磁盘利用率大于0.8属于不正常
    def diskRateCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            i['diskRate'] =list()
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i["hostName"] + "\tdf -h | grep -v tmp | cut -d % -f 1 | awk 'NR>1{print $1,$5/100}'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    line = stdout.readline()
                    temp = dict()
                    while line:
                        temp['name'] = line.split()[0]
                        temp['rate'] = (float)(line.split()[1])
                        line = stdout.readline()
                        i['diskRate'].append(temp.copy())
                    del temp
                else:
                    print(stderr.read())
        ssh.close()
        return

    # 查询内存利用率,利用率大于0.8属于不正常
    def memRateCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i["hostName"] + "\tfree | grep Mem | awk '{print $3/$2}'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    i['memRate'] = float(stdout.read().decode())
                else:
                    print(stderr.read())
        ssh.close()
        return

    #查询cpu利用率,利用率大于0.8属于不正常
    def cpuRateCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i["hostName"] + "\t vmstat | awk 'NR>2{print (100-$15)/100}'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    i['cpuRate'] = float(stdout.read().decode())
                else:
                    print(stderr.read())
        ssh.close()
        return

    # 容器状态检查，正常容器状态为Running
    def ctainrStateCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        stdin, stdout, stderr = ssh.exec_command("/opt/bin/kubectl -s 127.0.0.1:8888 get pod | awk 'NR>1{print $1,$3}'")
        self.osInfo['ctainrState'] = list()
        if not stderr.read():
            line = stdout.readline()
            while line:
                dict1 = dict()
                dict1['name'] = line.split()[0]
                dict1['status'] = line.split()[1]
                self.osInfo['ctainrState'].append(dict1.copy())
                line = stdout.readline()
                del dict1
        else:
            print(stderr.read())
        ssh.close()
        return

    # 查看共享磁盘是否存在是否正常断开,当状态为True时，表示正常断开无异常；
    # 当状态为False时，表示断开异常
    def shareStorErrorCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        stdin, stdout, stderr = ssh.exec_command("cat /var/log/messages | grep EXT4 | grep error")
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i["hostName"] + "\tcat /var/log/messages | grep EXT4 | grep error"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    if not stdout.read():
                        i["shareStorError"] = True
                    else:
                        i["shareStorError"] = False
                else:
                    print(stderr.read())
        ssh.close()
        return

    # 检查容器分布是否均匀
    #当状态为False表示为分布不均，当状态为True是表示分布均匀
    def ctainrLBCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        cmd = "/opt/bin/kubectl -s 127.0.0.1:8888 get node | awk 'NR>1{print$1}' | while read line;do echo $line $(/opt/bin/kubectl -s 127.0.0.1:8888 get pod -o wide | grep $line | wc -l);done"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        li = list()
        if not stderr.read():
            line = stdout.readline()
            while line:
                dict1 = dict()
                dict1['NodeName'] = line.split()[0]
                dict1['ctainrNum'] = int(line.split()[1])
                li.append(dict1.copy())
                line = stdout.readline()
                del dict1
            sum = 0
            length = len(li)
            for i in li:
                sum += i['ctainrNum']  # 容器总数
            sum2 = 0
            for j in li:
                sum2 += math.pow(sum / length - j['ctainrNum'], 2)  # 求容器分布的方差
            if sum2 / length > 9:  # 方差大于9时则分布不均
                self.osInfo['ctainrLB'] = False
            else:
                self.osInfo['ctainrLB'] = True
        else:
            print(stderr.read())
        ssh.close()
        return

    #检查容器镜像是否完整
    def dockerImageCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                i['images'] = set()
                cmd = "ssh\t" + i['hostName'] + "\tdocker images | awk 'NR>1{print $1}' | grep -v gcr | grep -v\t" + self.ip
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    text = stdout.read().decode()
                    for j in text.splitlines():
                        i['images'].add(j)
        ssh.close()
        return

    #检查ntp时间是否一致
    def nodeNtpTimeCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            cmd = "ssh\t" + i['hostName'] + "\tntpdate -q\t"+ self.osInfo["masterIP"] +"\t| awk 'NR==1{print $6}' | cut -d - -f 2 | cut -d , -f 1"
            sdtin, stdout, stderr = ssh.exec_command(cmd)
            i['ntpOffset'] = (float)(stdout.read())
        ssh.close()
        return

    # 检查openstack-compute和openstack内的关键服务是否正常
    def ctainrServiceCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        self.osInfo['serviceStatus'] = dict()
        cmd = "/opt/bin/kubectl -s 127.0.0.1:8888 get pod | awk 'NR>1{print $1}'| while read line;do " \
              "/opt/bin/kubectl -s 127.0.0.1:8888 describe pod $line | grep Image: |awk -v var1=$line '" \
              "{print var1,$2}' | cut -d : -f 1;done"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        line = stdout.read().decode()
        # cloudos-openstack内的服务列表
        serviceList1 = {'ftp-server', 'h3c-agent', 'httpd', 'mongod', 'neutron-server', 'openstack-nova-consoleauth',
                        'openstack-ceilometer-api', 'openstack-ceilometer-collector',
                        'openstack-ceilometer-notification',
                        'openstack-cinder-api', 'openstack-cinder-scheduler', 'openstack-glance-api',
                        'openstack-nova-conductor',
                        'openstack-glance-registry', 'openstack-nova-api', 'openstack-nova-cert',
                        'openstack-nova-novncproxy',
                        'openstack-nova-scheduler'}

        # cloudos-openstack-compute内的服务列表
        serviceList2 = {'openstack-ceilometer-compute', 'openstack-cinder-volume', 'openstack-neutron-cas-agent',
                        'openstack-nova-compute'}

        line = line.strip()  # 去空白
        for j in line.splitlines():
            # 对容器cloudos-openstack内的服务进行检查
            if j.split()[1] == 'cloudos-openstack':
                self.osInfo['serviceStatus']['cloudos-openstack'] = list()
                for i in serviceList1:
                    dict1 = dict()
                    dict1['name'] = i
                    cmd = "/opt/bin/kubectl -s 127.0.0.1:8888 exec " \
                          "-it\t" + j.split()[0] + "\tsystemctl status\t" + i + "| grep Active | awk '{print $3}'"
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                    status = re.findall(r'\((.*?)\)', stdout.read().decode())[0]
                    if status == 'running':
                        dict1['status'] = True
                    else:
                        dict1['status'] = False
                    self.osInfo['serviceStatus']['cloudos-openstack'].append(dict1.copy())
                    del dict1

            # 对容器cloudos-openstack-compute内的服务进行检查
            elif j.split()[1] == 'cloudos-openstack-compute':
                self.osInfo['serviceStatus']['cloudos-openstack-compute'] = list()
                for i in serviceList2:
                    dict1 = dict()
                    dict1['name'] = i
                    cmd = "/opt/bin/kubectl -s 127.0.0.1:8888 exec -it\t" + j.split()[
                        0] + "\tsystemctl status\t" + i + "| grep Active | awk '{print $3}'"
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                    status = re.findall(r'\((.*?)\)', stdout.read().decode())[0]
                    if status == "running":
                        dict1['status'] = True
                    else:
                        dict1['status'] = False
                    self.osInfo['serviceStatus']['cloudos-openstack-compute'].append(dict1.copy())
                    del dict1
        ssh.close()
        return

    # 检查云主机镜像是否正常
    def imageCollect(self):
        self.osInfo["imagesStatus"] = list()
        respond = requests.get("http://" + self.ip + ":9000/v3/images", auth=self.auth)
        print(respond.text)
        if respond.text:
            tmp = json.loads(respond.text)
            if 'image' in tmp:
                for i in tmp['images']:
                    dict1 = dict()
                    dict1['name'] = i['name']
                    dict1['status'] = i['status']
                    self.osInfo["imagesStatus"].append(dict1.copy())
                    del dict1
        respond.close()
        return

    # "status": "ACTIVE"
    # "name": "new-server-test"
    def vmCollect(self):
        self.osInfo['vmStatus'] = list()
        # headers = {'content-type': 'application/json', 'Accept': 'application/json', 'X-Auth-Token': ''}
        # headers['X-Auth-Token'] = self.token
        response = requests.get("http://" + self.ip + ":9000/v3/projects", auth=self.auth)
        for i in json.loads(response.text)['projects']:
            if 'cloud' in i.keys() and i['cloud'] is True:     # if后的逻辑运算从左到右
                url = "http://" + self.ip + ":9000/v2/" + i['id'] + "/servers/detail"
                response1 = requests.get(url, auth=self.auth)
                for j in json.loads(response1.text)['servers']:
                    dict1 = dict()
                    dict1['name'] = j['name']
                    dict1['status'] = j['status']
                    self.osInfo['vmStatus'].append(dict1.copy())
                    del dict1
                response1.close()
        response.close()
        return

    # 'status': 'available'
    def vdiskCollect(self):
        self.osInfo['vDiskStatus'] = list()
        response = requests.get("http://" + self.ip + ":9000/v3/projects", auth=self.auth)
        for i in json.loads(response.text)['projects']:
            if 'cloud' in i.keys() and i['cloud'] is True:  # if后的逻辑运算从左到右
                url = "http://" + self.ip + ":9000/v2/" + i['id'] + "/volumes/detail"
                response1 = requests.get(url, auth=self.auth)
                for j in json.loads(response1.text)['volumes']:
                    dict1 = dict()
                    dict1['name'] = j['name']
                    dict1['status'] = j['status']
                    self.osInfo['vDiskStatus'].append(dict1.copy())
                    del dict1
                response1.close()
        response.close()
        return


