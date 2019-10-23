from requests.auth import HTTPDigestAuth
import xmltodict
import requests
import paramiko
from multiprocessing import Pool
from shell import applog
import threadpool

logfile = applog.Applog()


THREADNUM = 4

class Cas3Data:
# 读取ip、username，password
    def __init__(self, ip, sshUser, sshPassword, httpUser, httpPassword):
        self.host = ip
        self.url = "http://" + ip + ":8080/cas/casrs/"
        self.httpUser = httpUser
        self.httpPassword = httpPassword
        self.casInfo = {}
        self.sshUser = sshUser
        self.sshPassword = sshPassword
        self.cookies = requests.get(self.url, auth=HTTPDigestAuth(self.httpUser, self.httpPassword)).cookies
        return

    # 获取cvm基础信息：版本信息、服务器版本、服务器规格、部署方式
    @applog.logRun(logfile)
    def cvmBasicCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy)
        ssh.connect(self.host, 22, self.sshUser, self.sshPassword)
        # 服务器硬件型号
        stdin, stdout, stderr = ssh.exec_command("dmidecode | grep -i product | awk 'NR==1{print $3,$4,$5 }'")
        if not stderr.read():
            self.casInfo['productVersion'] = stdout.read().decode()
        else:
            print(" product version error")
        # 服务规格
        stdin, stdout, stderr = ssh.exec_command(
            "lscpu | cut -d : -f 2 | awk 'NR==4 || NR==7{print $1}';free -g | awk 'NR==2{print $2}'")
        if not stderr.read():
            text = stdout.read().decode()
            a = text.splitlines()
            self.casInfo['deviceDmide'] = "cpu:" + a[0] + "*" + a[1] + "cores" + "\nMem:" + a[2] + 'G'
        else:
            print("device dmide error")

        # cas版本
        stdin, stdout, stderr = ssh.exec_command("cat /etc/cas_cvk-version | head -1")
        if not stderr.read():
            self.casInfo['casVersion'] = stdout.read().decode()
        else:
            print("cas version error")

        # 部署方式
        stdin, stdout, stderr = ssh.exec_command("crm status | grep Online | awk '{print NF-3}'")
        if not stderr.read():
            text = stdout.read().decode().splitlines()
            if not text or text[0] == '1':
                self.casInfo["installType"] = "单机部署"
            else:
                self.casInfo["installType"] = "集群部署"
        else:
            print("install type error")
        # 1020v版本：
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
    @applog.logRun(logfile)
    def clusterCollect(self):
        # response = requests.get(self.url + 'cluster/clusters/', auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
        response = requests.get(self.url + 'cluster/clusters/', cookies=self.cookies)
        contxt = response.text
        response.close()
        dict1 = xmltodict.parse(contxt)['list']['cluster']
        temp = []
        if isinstance(dict1, dict):
            temp.append(dict1)
        else:
            temp = dict1.copy()
        self.casInfo['clusterInfo'] = []
        tempInfo = {}
        for i in temp:
            # 获取集群的id,name,HA状态，cvk数量，LB状态
            tempInfo['id'] = i['id']
            tempInfo['name'] = i['name']
            tempInfo['enableHA'] = i['enableHA']
            tempInfo['cvkNum'] = (int)(i['childNum'])
            tempInfo['enableLB'] = i['enableLB']
            self.casInfo['clusterInfo'].append(tempInfo.copy())
        # 获取集群HA最小主机数量
        for i in self.casInfo['clusterInfo']:
            # response = requests.get(self.url + 'cluster/' + i['id'], auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
            response = requests.get(self.url + 'cluster/' + i['id'], cookies=self.cookies)
            contxt = response.text
            response.close()
            dict1 = xmltodict.parse(contxt)
            i['HaMinHost'] = dict1['cluster']['HaMinHost']
        del temp
        return

        ####################################################################
        # 获取主机ID、NAME、状态、虚拟机数量、cpu使用率、内存使用率            #
        ####################################################################
    @applog.logRun(logfile)
    def cvkBasicCollect(self):
        # 初始化cvk数据结构
        for i in self.casInfo['clusterInfo']:
            i['cvkInfo'] = []
            # response = requests.get(self.url + 'cluster/hosts?clusterId=' + i['id'],
            #                         auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
            response = requests.get(self.url + 'cluster/hosts?clusterId=' + i['id'], cookies=self.cookies)
            contxt = response.text
            response.close()
            dict1 = xmltodict.parse(contxt)['list']['host']
            temp1 = []
            if isinstance(dict1, dict):
                temp1.append(dict1)
            else:
                temp1 = dict1.copy()
            for j in temp1:
                temp2 = {}
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
    # 主机共享存储利用率/cas/casrs/host/id/{id}/storage#
    # 获取主机共享存储池信
    ##################################################
    @applog.logRun(logfile)
    def cvkSharepoolCollect(self):
        pool = threadpool.ThreadPool(THREADNUM)
        for i in self.casInfo['clusterInfo']:
            threadlist = threadpool.makeRequests(self.cvkSharepool, i['cvkInfo'])
            for k in threadlist:
                pool.putRequest(k)
        pool.wait()
        return

    def cvkSharepool(self, cvk):
        # response = requests.get(self.url + 'host/id/' + cvk['id'] + '/storage',
        #                         auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
        if cvk['status'] == '1':
            response = requests.get(self.url + 'host/id/' + cvk['id'] + '/storage', cookies=self.cookies)
            contxt1 = response.text
            response.close()
            dict1 = xmltodict.parse(contxt1)
            list1 = []
            dict2 = {}
            li = []
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
                        li.append(dict2.copy())
            del list1
            del dict2
            cvk['sharePool'] = li
        return


    ##############################################################
    # 获取CVK主机磁盘利用率
    # cas版本为V5.0 (E0530)时，api获取磁盘利用率信息不正确，cas软件bug
    ##############################################################
    @applog.logRun(logfile)
    def cvkDiskCollect(self):
        pool = threadpool.ThreadPool(THREADNUM)
        for i in self.casInfo['clusterInfo']:
            threadlist = threadpool.makeRequests(self.cvkDisk, i['cvkInfo'])
            for k in threadlist:
                pool.putRequest(k)
        pool.wait()
        return

    def cvkDisk(self, cvk):
        # response = requests.get(self.url + 'host/id/' + cvk['id'] + '/monitor',
        #                         auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
        if cvk['status'] == '1':
            response = requests.get(self.url + 'host/id/' + cvk['id'] + '/monitor', cookies=self.cookies)
            contxt1 = response.text
            response.close()
            dict2 = xmltodict.parse(contxt1)['host']
            li = []
            if 'disk' in dict2.keys():
                dict1 = xmltodict.parse(contxt1)['host']['disk']
                temp = []
                if isinstance(dict1, dict):
                    temp.append(dict1)
                else:
                    temp = dict1.copy()
                for h in temp:
                    temp1 = {}
                    temp1['name'] = h['device']
                    temp1['usage'] = (float)(h['usage'])
                    li.append(temp1.copy())
                    del temp1
                del temp
            cvk['diskRate'] = li
        return

        ##############################################################
        # 获取CVK主机虚拟交换机信息
        ##############################################################
    @applog.logRun(logfile)
    def cvkVswitchCollect(self):
        pool = threadpool.ThreadPool(THREADNUM)
        for i in self.casInfo['clusterInfo']:
            threadlist = threadpool.makeRequests(self.cvkVswitch, i['cvkInfo'])
            for k in threadlist:
                pool.putRequest(k)
        pool.wait()
        return

    def cvkVswitch(self, cvk):
        if cvk['status'] == '1':
            response = requests.get(self.url + 'host/id/' + cvk['id'] + '/vswitch', cookies=self.cookies)
            contxt1 = response.text
            response.close()
            dict2 = xmltodict.parse(contxt1)
            li = []
            if 'list' in dict2.keys():  # 3.0为list
                dict1 = dict2['list']
            else:
                return li
            temp = []
            if isinstance(dict1, dict):
                if isinstance(dict1['vSwitch'], dict):
                    temp.append(dict1['vSwitch'])
                else:
                    temp = dict1['vSwitch'].copy()
                for h in temp:
                    temp1 = {}
                    temp1['name'] = h['name']
                    temp1['status'] = h['status']
                    temp1['pnic'] = h['pnic']
                    li.append(temp1.copy())
                    del temp1
            del temp
            del dict1
            del dict2
            cvk['vswitch'] = li
        return


    ################################################################################
    # 获取cvk主机的存储池信息
    ################################################################################
    @applog.logRun(logfile)
    def cvkStorpoolCollect(self):
        pool = threadpool.ThreadPool(THREADNUM)
        for i in self.casInfo['clusterInfo']:
            threadlist = threadpool.makeRequests(self.cvkStorpool, i['cvkInfo'])
            for k in threadlist:
                pool.putRequest(k)
        pool.wait()
        return

    def cvkStorpool(self, cvk):
        # response = requests.get(self.url + 'storage/pool?hostId=' + cvk['id'],
        #                         auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
        if cvk['status'] == '1':
            response = requests.get(self.url + 'storage/pool?hostId=' + cvk['id'], cookies=self.cookies)
            contxt1 = response.text
            response.close()
            dict1 = xmltodict.parse(contxt1)['list']['storagePool']
            temp = []
            li = []
            if isinstance(dict1, dict):
                temp.append(dict1)
            else:
                temp = dict1.copy()
            for h in temp:
                temp1 = {}
                temp1['name'] = h['name']
                temp1['status'] = h['status']
                li.append(temp1.copy())
                del temp1
            del temp
            cvk['storagePool'] = li
        return


    # 获取cvk主机的网卡信息
    @applog.logRun(logfile)
    def cvkNetsworkCollect(self):
        pool = threadpool.ThreadPool(THREADNUM)
        for i in self.casInfo['clusterInfo']:
            threadlist = threadpool.makeRequests(self.cvkNetwork, i['cvkInfo'])
            for k in threadlist:
                pool.putRequest(k)
        pool.wait()
        return

    def cvkNetwork(self, cvk):
        if cvk['status'] == '1':
            li = []
            response = requests.get(self.url + 'host/id/' + cvk['id'], cookies=self.cookies)
            dict1 = xmltodict.parse(response.text)['host']
            response.close()
            if 'pNIC' in dict1.keys():
                dict2 = {}
                for i in dict1['pNIC']:
                    dict2['name'] = i['name']
                    dict2['status'] = i['status']
                    li.append(dict2.copy())
                del dict2
            cvk['network'] = li
        return


    # 获取虚拟机的id,name,虚拟机状态，castool状态，cpu利用率，内存利用率
    #SELECT ID,HOST_ID,STATUS,DOMAIN_NAME,CASTOOLS_STATUS FROM TBL_DOMAIN
    @applog.logRun(logfile)
    def vmBasicCollect(self):
        for i in self.casInfo['clusterInfo']:
            for j in i['cvkInfo']:
                if j['status'] == '1':
                    self.vmBasic(j)
        return

    def vmBasic(self, j):
        # response = requests.get(self.url + 'vm/vmList?hostId=' + j['id'],
        #                                  auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
        response = requests.get(self.url + 'vm/vmList?hostId=' + j['id'],  cookies=self.cookies)
        contxt = response.text
        response.close()
        j['vmInfo'] = []
        dict2 = xmltodict.parse(contxt)
        if isinstance(dict2['list'], dict) and 'domain' in dict2['list'].keys():
            dict1 = xmltodict.parse(contxt)['list']['domain']
            list1 = []
            if isinstance(dict1, dict):
                list1.append(dict1)
            else:
                list1 = dict1.copy()
            for k in list1:
                temp2 = {}
                temp2['id'] = k['id']
                temp2['name'] = k['title']
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
            del list1
        return

    # diskrate thread function
    # 2019/8/29
    def vmDiskRate(self, vm):
        li = []
        # response = requests.get(self.url + 'vm/id/' + vm['id'] + '/monitor',
        #                         auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
        response = requests.get(self.url + 'vm/id/' + vm['id'] + '/monitor', cookies=self.cookies)
        contxt1 = xmltodict.parse(response.text)
        response.close()
        list1 = []
        if isinstance(contxt1['domain'], dict) and 'partition' in contxt1['domain'].keys():
            if isinstance(contxt1['domain']['partition'], dict):
                list1.append(contxt1['domain']['partition'])
            else:
                list1 = (contxt1['domain']['partition']).copy()
                dict1 = {}
                for m in list1:
                    dict1['name'] = m['device']
                    dict1['usage'] = (float)(m['usage'])
                    li.append(dict1.copy())
        del list1
        vm['diskRate'] = li
        return

    @applog.logRun(logfile)
    def vmDiskRateCollect(self):
        #使用API读取信息
        # pool = threadpool.ThreadPool(THREADNUM)
        # li = []
        # for i in self.casInfo['clusterInfo']:
        #     for j in i['cvkInfo']:
        #         for k in j['vmInfo']:
        #             if k['status'] == 'running':
        #                 li.append(k)
        # for i in li:
        #     self.vmDiskRate(i)
        # threadlist = threadpool.makeRequests(self.vmDiskRate, li)
        # for h in threadlist:
        #     pool.putRequest(h)
        # pool.wait()

        #使用mysql读取信息
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.host, 22, self.sshUser, self.sshPassword)
        cmd1 = "mysql -uroot -p1q2w3e -N -Dvservice -e'select DOMAIN_ID,PARTITION_NAME,UTILIZATION from TBL_DOMAIN_PARTITION_DETAIL'"
        stdin, stdout, stderr = ssh.exec_command(cmd1)
        text = stdout.read().decode()
        ssh.close()
        diskdict = {}
        for i in text.splitlines():
            a = i.split()
            dict1 = {}
            if a[0] in diskdict.keys():
                dict1['name'] = a[1]
                dict1['usage'] = (float)(a[2])
                diskdict[a[0]].append(dict1)
            else:
                diskdict[a[0]] = []
                dict1['name'] = a[1]
                dict1['usage'] = (float)(a[2])
                diskdict[a[0]].append(dict1)
            del dict1
        for i in self.casInfo['clusterInfo']:
            for j in i['cvkInfo']:
                if j['status'] == '1':
                    for k in j['vmInfo']:
                        if k['status'] == 'running' and k['id'] in diskdict.keys():
                            k['diskRate'] = diskdict[k['id']]
                        else:
                            k['diskRate'] = []
        return

    ################
    # 2019/8/29
    # weifeng
    ##################

    # 根据虚拟机详细信息vmdetail，获取vm磁盘信息
    def vmDisk(self, vm, vmdetail):
        dict1 = {}
        li = []
        if 'domain' in vmdetail.keys():
            if 'storage' in vmdetail['domain'].keys():
                dict1 = vmdetail['domain']['storage']
                temp1 = []
                if isinstance(dict1, dict):
                    temp1.append(dict1)
                else:
                    temp1 = dict1.copy()
                for h in temp1:
                    temp2 = {}
                    if 'device' in h.keys() and h['device'] == 'disk':
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
                        li.append(temp2.copy())
                    del temp2
                del temp1
            del dict1
        return li

    #根据虚拟机详细信息vmdetail，获取vm网卡信息
    def vmNetwork(self, vm, vmdetail):
        dict1 = {}
        li = []
        if 'domain' in vmdetail.keys():
            if 'network' in vmdetail['domain'].keys():
                dict1 = vmdetail['domain']['network']
                temp1 = []
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
                        li.append(temp2.copy())
                    del temp2
                del temp1
            del dict1
        return li

    #虚拟机网卡和磁盘巡检回调函数
    def vmNetworkDisk(self, vm):
        # print("vmNetworkDisk Thread vm id:", vm['id'])
        # response = requests.get(self.url + 'vm/detail/' + vm['id'],
        #                         auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
        response = requests.get(self.url + 'vm/detail/' + vm['id'], cookies=self.cookies)
        contxt1 = xmltodict.parse(response.text)
        response.close()
        vm['vmNetwork'] = self.vmNetwork(vm, contxt1)
        vm['vmdisk'] = self.vmDisk(vm, contxt1)
        return

    # 虚拟机网卡巡检
    @applog.logRun(logfile)
    def vmNetworkDiskCollect(self):
        pool = threadpool.ThreadPool(THREADNUM)
        li = []
        for i in self.casInfo['clusterInfo']:
            for j in i['cvkInfo']:
                if j['status'] == '1':
                    for k in j['vmInfo']:
                        if k['status'] == 'running':
                            li.append(k)
        threadlist = threadpool.makeRequests(self.vmNetworkDisk, li)
        for h in threadlist:
            pool.putRequest(h)
        pool.wait()
        return

    # cvm双机热备信息
    @applog.logRun(logfile)
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

    # CVM备份策略是否开启
    # mysql -uroot -p1q2w3e -Dvservice -e'select STATE from TBL_BACKUP_CVM_STRATEGY;' | awk 'NR>1{print $0}'
    @applog.logRun(logfile)
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


    # 虚拟机备份策略
    @applog.logRun(logfile)
    def vmBackupPolicyCollect(self):
        # response = requests.get(self.url + 'backupStrategy/backupStrategyList',
        #                         auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
        response = requests.get(self.url + 'backupStrategy/backupStrategyList', cookies = self.cookies)
        contxt = response.text
        response.close()
        text = xmltodict.parse(contxt)['list']
        list1 = []
        # if not 'backupStrategy' in text:
        if not text:
            self.casInfo['vmBackPolicy'] = 'NONE'
        else:
            self.casInfo['vmBackPolicy'] = list()
            if isinstance(text['backupStrategy'], dict):
                list1.append(text['backupStrategy'])
            else:
                list1 = (text['backupStrategy']).copy()
            dict1 = {}
            for i in list1:
                dict1['name'] = i['name']
                dict1['state'] = i['state']
                self.casInfo['vmBackPolicy'].append(dict1)
            del dict1
        del list1, text
        return