from requests.auth import HTTPDigestAuth
import xmltodict, requests
from shell.Cas3Data import Cas3Data
from shell import applog

logfile = applog.Applog()

class Cas5Data(Cas3Data):

    def cvkVswitch(self, cvk):
        response = requests.get(self.url + '/host/id/' + cvk['id'] + '/vswitch',
                                auth=HTTPDigestAuth(self.httpUser, self.httpPassword))
        contxt1 = response.text
        response.close()
        dict2 = xmltodict.parse(contxt1)
        li = []
        if 'host' in dict2.keys():  # 5.0为host
            dict1 = dict2['host']
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
        return li