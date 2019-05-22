# -*- coding: utf-8 -*-

import requests, json
from Node.models import node,PresetFalcon


# 根据模板名称获取模板id
def get_template(tpl_name, falcon_url, falcon_headers):
    falcon_url = "http://" + falcon_url + "/api/v1/template"
    templates = requests.get(falcon_url, headers=falcon_headers)
    for template in json.loads(templates.content)['templates']:
        if template['template']['tpl_name'] == tpl_name:
            return template['template']['id']
    return None


# 为模板创建告警接收组
def create_action(tpl_id, falcon_url, falcon_headers):
    action_data = {
        "URL": "",
        "UIC": "ops,mailgroup",
        "TplId": tpl_id,
        "Callback": 0,
        "BeforeCallbackSMS": 0,
        "BeforeCallbackMail": 0,
        "AfterCallbackMail": 0,
        "AfterCallbackSMS": 0
    }
    falcon_url = "http://" + falcon_url + "/api/v1/template/action"
    requests.post(falcon_url, data=action_data, headers=falcon_headers)
    return True


# 创建新的模板
def creat_new_template(endpoint, falcon_url, falcon_headers):
    falcon_api = "http://" + falcon_url + "/api/v1/template"
    # create template
    requests.post(falcon_api, data={"parent_id": 0, "Name": endpoint}, headers=falcon_headers)
    tpl_id = get_template(endpoint, falcon_url, falcon_headers)
    # create action to template
    create_action(tpl_id, falcon_url, falcon_headers)
    return tpl_id


# 添加监控项
def add_new_action(tpl_id, falcon_url, falcon_headers, info, isEmpty, ip):
    if isEmpty is True:
        metric_list = PresetFalcon.objects.filter(module='node').values()
        for strategy in metric_list:
	    add_strategy_FLAG = add_strategy(strategy, tpl_id, falcon_url, falcon_headers)
            if not add_strategy_FLAG:
                info['error_metric'].append(str(strategy['metric'] + '/' + strategy['tags']).rstrip('/').encode('utf-8'))
	    else:
		info['new_metric'].append(str(strategy['metric'] + '/' + strategy['tags']).rstrip('/').encode('utf-8'))
	info['all_metric'] = info['new_metric']
    else:
        strategy_list = PresetFalcon.objects.filter(module='node').values()
        current_metric = node.objects.get(node_ip=ip).metric
	
	if current_metric == None or current_metric == '[]' or current_metric == '':
	    add_new_action(tpl_id, falcon_url, falcon_headers, info, True, ip)
	else:
	    for i in range(len(strategy_list)):
		info['new_metric'].append(strategy_list[i]['metric'].encode('utf-8'))
		info['all_metric'].append(strategy_list[i]['metric'].encode('utf-8'))
	        if strategy_list[i]['metric'] not in current_metric:
	    	    if not add_strategy(strategy_list[i], tpl_id, falcon_url, falcon_headers):
	    	        info['error_metric'].append(str(strategy_list[i]['metric'] + '/' + strategy_list[i]['tags']).rstrip('/'))
			info['all_metric'].remove(strategy_list[i]['metric'])
		else:
		    info['new_metric'].remove(strategy_list[i]['metric'])
	    for i in range(len(eval(current_metric))):
		if eval(current_metric)[i] not in str(list(strategy_list)):
		    del_strategy(eval(current_metric)[i], tpl_id, falcon_url, falcon_headers)

    return info


# 添加告警策略
def add_strategy(strategy, tpl_id, falcon_url, falcon_headers):
    strategy_data = {
        "TplId": tpl_id,
        "Tags": strategy['tags'],
        "RunEnd": "",
        "RunBegin": "",
        "RightValue": strategy['right_value'],
        "Priority": strategy['priority'],
        "Op": strategy['op'],
        "Note": strategy['note'],
        "Metric": strategy['metric'],
        "MaxStep": strategy['max_step'],
        "Func": strategy['func']
    }
    falcon_url = 'http://' + falcon_url + '/api/v1/strategy'
    add_strategy_response = requests.post(falcon_url, data=strategy_data, headers=falcon_headers)
    if add_strategy_response.status_code == 200:
        # get template id (ready done ...)
        return True
    else:
        return False


# 根据主机组名称获取主机组id
def get_hostgroups(grp_name, falcon_url, falcon_headers):
    falcon_url = "http://" + falcon_url + "/api/v1/hostgroup"
    hostgroups = requests.get(falcon_url, headers=falcon_headers)
    for hostgroup in json.loads(hostgroups.content):
        if hostgroup["grp_name"] == grp_name:
            return hostgroup["id"]
    return None


#删除告警策略，
def del_strategy(metrics,tpl_id,falcon_url,falcon_headers):
    failed_del_metrics = []
    del_strategy_url = 'http://'+falcon_url + '/api/v1/strategy/'
    stratges = get_stratges_from_template(tpl_id,falcon_url,falcon_headers)
    if stratges is not None:
        for strategy in stratges:
            if strategy['metric'] == metrics:
                re=requests.delete(del_strategy_url + str(strategy['id']),headers=falcon_headers)
                if re.status_code != 200:
                    failed_del_metrics.append(strategy['metric'])

    return failed_del_metrics


#从模板中获取监控策略
def get_stratges_from_template(tpl_id,falcon_url,falcon_headers):
    get_template_info_url = 'http://'+falcon_url + '/api/v1/template/' + str(tpl_id)
    template_info = requests.get(get_template_info_url,headers=falcon_headers)
    if template_info.status_code != 200:
        return None
    stratges = json.loads(template_info.content)['stratges']
    return stratges


# 添加nodata
def add_nodata(falcon_url, falcon_headers, endpoint):
    body = {
        "id": 1,
        "name": endpoint,
        "obj": endpoint,
        "obj_type": "host",
        "metric": "agent.alive",
        "tags": "",
        "dstype": "GAUGE",
        "step": 60,
        "mock": -1,
        "creator": "root"
    }
    add_nodata_url = 'http://'+falcon_url+'/api/v1/nodata/'
    res = requests.post(add_nodata_url, data=body, headers=falcon_headers)
    if 'updated' in res.contentreturn:
	return JsonResponse({"status":"success"})
    else:
	return JsonResponse({"status":"failed"}) 

