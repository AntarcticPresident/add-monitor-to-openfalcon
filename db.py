# -*- coding: utf-8 -*-

from __future__ import unicode_literals 
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST
 
from Node.models import node,PresetFalcon
from django.utils import timezone

import re, os
import logging.config
from func import *

import urllib3, chardet
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

falcon_url = "10.18.216.190:8080"
falcon_headers = {"Apitoken": "{\"name\":\"root\",\"sig\":\"8d5a94155f3f11e98877befb8bbf7522\"}", }


# init log set
logpath = os.path.join(os.getcwd(), 'addnode/log.conf')
logging.config.fileConfig(logpath)
logger = logging.getLogger('addnode')


def test(request):
    test1 = list(node.objects.all().values())
    print test1
    print request.POST.get('ip').strip()
    return JsonResponse("<p>%s</p>" %test1)


# route api
def addnode(request):
    info = {'status': 'success', 'error_metric': [], 'all_metric': [], 'new_metric': []}

    # 请求是否POST, 前面的装饰器已经能够限定方法了
    if request.method == 'POST':
        ip = request.POST.get('ip').strip()
    else:
        #logging.error('request\'s method error!')
        return JsonResponse({"status": "failed", "errormsg": "请求非法！"})

    ip = request.POST.get('ip').strip()
    # 是否合法IP
    if not re.compile('^(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|[1-9])\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.'
                      '(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)$').match(ip):
        return JsonResponse({"status": "failed", "errormsg": "IP格式错误！"})

    try:
    	node_info = node.objects.get(node_ip=ip)
    except:
	return JsonResponse({"status": "failed", "errormsg": "该主机(%s)不存在！" % ip})

    endpoint = ip+'_'+node_info.hostname
    tpl_name = ip
    grp_name = ip
    # 判断template是否存在,并根据结果添加监控项
    tpl_id = get_template(tpl_name, falcon_url, falcon_headers)
    if tpl_id is None:
        tpl_id = creat_new_template(tpl_name, falcon_url, falcon_headers)
        info = add_new_action(tpl_id, falcon_url, falcon_headers, info, True, ip)
    else:
        info = add_new_action(tpl_id, falcon_url, falcon_headers, info, False, ip)

    # 判断主机组是否存在
    grp_id = get_hostgroups(grp_name, falcon_url, falcon_headers)
    # check hostgroup not exist
    if grp_id is None:
        falcon_api = "http://" + falcon_url + "/api/v1/hostgroup"
        create_hostgroup = requests.post(falcon_api, data={"Name": grp_name}, headers=falcon_headers)
        grp_id = json.loads(create_hostgroup.content)["id"]

    # add host to hostgroup
    data = {"Hosts": [endpoint], "HostGroupID": grp_id}
    requests.post('http://' + falcon_url + '/api/v1/hostgroup/host',data=data, headers=falcon_headers)
                  #data={"Hosts": [endpoint], "HostGroupID": grp_id}, headers=falcon_headers)
    
    # 区分docker和物理机,绑定不同的plugin.先删除,再重新绑定
    res = requests.get("http://" + falcon_url + "/api/v1/hostgroup/%s/plugins" %grp_id, headers=falcon_headers)
    for i in eval(res.content):
        plugin_id = dict(i)['id']
        res = requests.delete("http://" + falcon_url + "/api/v1/plugin/%s" %plugin_id, headers=falcon_headers)
    if node_info.docker_flag == 1:
        res =requests.post("http://" + falcon_url + "/api/v1/plugin", data={"GrpId":grp_id,"DirPaht":"sys"}, headers=falcon_headers)
        res =requests.post("http://" + falcon_url + "/api/v1/plugin", data={"GrpId":grp_id,"DirPaht":"docker"}, headers=falcon_headers)
    else:
        res =requests.post("http://" + falcon_url + "/api/v1/plugin", data={"GrpId":grp_id,"DirPaht":"sys"}, headers=falcon_headers)
        res =requests.post("http://" + falcon_url + "/api/v1/plugin", data={"GrpId":grp_id,"DirPaht":"physicals"}, headers=falcon_headers)
        res =requests.post("http://" + falcon_url + "/api/v1/plugin", data={"GrpId":grp_id,"DirPaht":"jucloud/conntrack"}, headers=falcon_headers)
        res =requests.post("http://" + falcon_url + "/api/v1/plugin", data={"GrpId":grp_id,"DirPaht":"jucloud/dockerhang"}, headers=falcon_headers)
        res =requests.post("http://" + falcon_url + "/api/v1/plugin", data={"GrpId":grp_id,"DirPaht":"jucloud/logclean"}, headers=falcon_headers)

    # 绑定主机组和模板
    requests.post('http://' + falcon_url + '/api/v1/hostgroup/template', data={"TplID": tpl_id, "GrpID": grp_id},
                  headers=falcon_headers)

    # 添加默认监控值
    json_headers = {"Apitoken": "{\"name\":\"root\",\"sig\":\"8d5a94155f3f11e98877befb8bbf7522\"}"}
    data = {"Tags":"","Step":60,"ObjType":"host","Obj":"%s" %endpoint,"Name":"%s" %endpoint,"Mock":-1,"Metric":"agent.alive","DsType":"GAUGE"}
    res = requests.post('http://' + falcon_url + '/api/v1/nodata', data=data, headers=json_headers)

    # 添加成功，修改数据库参数
    if len(info['error_metric']) != 0:
        info['status'] = 'failed'
    else:
        info['status'] = 'success'
        # 如果告警添加成功，更新为已监控
        node.objects.filter(node_ip=ip).update(monitor_flag=1, metric=info['all_metric'], template_id=tpl_id, modified_time=timezone.now())
    return JsonResponse(info)


# route api
def update_value(request):
    info = {'status': 'success', 'error_metric': [], 'all_metric': [], 'new_metric': []}

    # 请求是否POST, 前面的装饰器已经能够限定方法了
    if request.method == 'POST':
        ip = request.POST.get('ip').strip()
    else:
        #logging.error('request\'s method error!')
        return JsonResponse({"status": "failed", "errormsg": "请求非法！"})

    ip_list = eval(request.POST.get('ip').strip())
    update_metric = request.POST.get('metric').strip()
    for ip in ip_list:
        # 是否合法IP
        if not re.compile('^(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|[1-9])\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.'
                          '(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)$').match(ip):
            return JsonResponse({"status": "failed", "errormsg": "IP格式错误！"})

        try:
            node_info = node.objects.get(node_ip=ip)
        except:
            return JsonResponse({"status": "failed", "errormsg": "该主机(%s)不存在！" % ip})    

        tpl_name = ip
        tpl_id = get_template(tpl_name, falcon_url, falcon_headers)
        res = requests.get("http://" + falcon_url + "/api/v1/template/%s" %tpl_id, headers=falcon_headers)
        result = eval(res.content)
	new_dic = {"RightValue":0,"MaxStep":0,"ID":0,"Metric":0,"Func":0,"Op":0,"Tags":0,"run_begin":0,"Note":0,"Priority":0,"TplID":0,"run_end":0}
	# 这个stratges是openfalcon代码里面拼错了,只能这样了
        for strategy in result['stratges']:
            if update_metric == strategy['metric']:
		# 这个地方需要前端增加一个传参，需要把模块的名字也传上来，不然presetfalcon表会出现重复
		note = PresetFalcon.objects.get(metric=update_metric,module='node').note
                data = {
		    "TplId": tpl_id,
                    "Tags": strategy['tags'],
                    "RunEnd": "",
                    "RunBegin": "",
                    "RightValue": request.POST.get('value'),
                    "Priority": strategy['priority'],
                    "Op": strategy['op'],
                    "Note": note,
                    "Metric": strategy['metric'],
                    "MaxStep": strategy['max_step'],
                    "Func": strategy['func'],
                    "ID": strategy['id']
		}
#   new_dic['RightValue'] = request.POST.get('value')
#		new_dic['MaxStep'] = str(strategy['max_step'])
#		new_dic['ID'] = str(strategy['id'])
#		new_dic['Metric'] = strategy['metric']
#		new_dic['Func'] = strategy['func']
#		new_dic['Op'] = strategy['op']
#		new_dic['Tags'] = strategy['tags']
#		new_dic['run_begin'] = strategy['run_begin']
#		new_dic['Note'] = strategy['note']
#		new_dic['Priority'] = str(strategy['priority'])
#		new_dic['TplID'] = str(strategy['tpl_id'])
#		new_dic['run_end'] = strategy['run_end']
#		data = str(new_dic).replace("u'", "'")
		res = requests.put("http://" + falcon_url + "/api/v1/strategy", headers=falcon_headers, data=data)
		if 'updated' in res.content:
		    return JsonResponse({"status":"success"})
		break
    return JsonResponse({"status":"failed"})
