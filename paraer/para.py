# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
import six
from functools import wraps
from uuid import uuid1
from django.utils.module_loading import import_string

from .datastrctures import Valid


def _doc_generater(itemset, func):
    func_name = func.__name__
    locationmap = {
        'get': 'query',
        'list': 'query',
        'retrieve': 'query',
        'update': 'formData',
        'create': 'formData',
        'post': 'formData'
    }
    location = locationmap.get(func_name, 'querystring')

    def defaulter(item):
        """设置默认参数"""

        def type_by_name(name):
            if name.endswith('id'):
                return 'integer'
            if any(x in name for x in ['date', 'start', 'end']):
                return 'date'
            return 'string'

        item.setdefault('in', location)
        required = item['in'] == 'path'
        item.setdefault('method', lambda x: x)
        item['name'] == 'pk' and item.update(
            name='id', type='integer', required=item.get('required', True))
        item.setdefault('required', required)
        item.setdefault('type', type_by_name(item['name']))
        description = item.get('description') or item.get(
            'msg') or 'description'
        msg = getattr(item['method'], 'msg',
                      item.get('msg') or item.get('description')
                      or 'msg')  # method maybe V
        if type(description) in {list, tuple}:
            description = list2mk(
                description, title=['value',
                                    'description'])  # 支持list转化为markdown表格的形式
        elif isinstance(description, dict):
            description = parse_description(
                description, title={'value':
                                    'description'})  # 支持dict转化为markdown表格的形式

        item['description'] = description
        item.setdefault('msg', msg)
        item.setdefault('replace', None)
        method = item['method']
        if not isinstance(method, Valid):  # replace lambda as Valid
            name = str(uuid1()).split('-')[0]
            v = Valid(name)
            setattr(v, name, method)
            item['method'] = v
        return item

    try:
        doc = func.__doc__.decode('utf8')
    except:
        doc = func.__doc__
    title = doc and doc.strip('\n').strip() or func.__name__

    parameters = [defaulter(x) for x in itemset]
    swagger = dict(title=title, parameters=parameters)
    return swagger


def default_data_method(request):
    return request.GET or request.data


def para_ok_or_400(itemset):
    """
    验证参数值, 参数不对则返回400, 若参数正确则返回验证后的值, 并且根据itemset中的值，来生成func的__doc__
    name: 需要校验的参数名称
    method: 校验方法, 校验成功时， 则返回校验方法后的校验值
    required: 是否可以为空
    msg: 校验失败返回的错误消息
    replace: 校验正确后返回的值对应的key
    description: 对参数的描述
    in: path, querystring, formData
    type: 参数类型(string, integer), 可以根据参数名称来确定, user_id(int), start_date(date), string
    """

    def decorator(func):
        from django.conf import settings
        swagger = _doc_generater(itemset, func)
        data_method = default_data_method
        if getattr(settings, 'PARAER_DATA_METHOD', ''):
            data_method = import_string(settings.PARAER_DATA_METHOD)  # 获取data的方法

        def wrapper(cls, request, *args, **kwargs):
            paramap = dict(kwargs)
            paramap.setdefault(
                'id', kwargs.get('pk', None)
            )  # Serializer fields中生成的为id 这个key， 但是django解析url中为 pk这个pk，为了不在文档中生成id 和pk这两个field， 所以都统一用id这个key， 那么在itemset中也写id这个key
            data = data_method(request)
            paramap.update({x: y for x, y in data.items()})
            result = cls.result_class()  # 继承与Result类
            for item in itemset:
                name, v, required, msg, replace = [
                    item[x]
                    for x in ['name', 'method', 'required', 'msg', 'replace']
                ]
                value = None  # 与 '' 区别
                para = paramap.get(name)
                if required and para in (None,
                                         ''):  # 如果是post方法并且传参是json的话，para可能为0
                    result.error(name, 'required')
                if para is not None:
                    if para:
                        try:
                            value = v(para)
                        except Exception:
                            if settings.DEBUG:
                                from traceback import print_exc
                                print_exc()
                        msg = v.msg or msg
                        if v.status == 403:  # 权限错误时直接返回错误
                            return result.perm(name, msg)(status=v.status)
                        if value is None or value is False:
                            result.error(name, msg)
                    if value is True:  # 当v返回的value为True时，取request中的值
                        value = para
                    kwargs.update({
                        replace or name: value
                    })  # method 返回了非布尔值则更新kwargs
            if not result:
                return result(status=400)
            return func(cls, request, *args, **kwargs)

        wrapper.__swagger__ = swagger
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


def perm_ok_or_403(itemset):
    """验证参数值, 参数不对则返回400, 若参数正确则返回验证后的值"""

    def decorator(func):
        @wraps(func)
        def wrapper(cls, request, *args, **kwargs):
            for item in itemset:
                before, method, reason = item.get('before'), item[
                    'method'], item['reason']
                before and before(request, kwargs)
                try:
                    perm = method(request, kwargs)
                except Exception:
                    perm = None
                    if settings.DEBUG:
                        from  traceback import print_exc
                        print_exc()
                if not perm:
                    return cls.result_class().perm(reason=reason)(status=403)
            return func(cls, request, *args, **kwargs)

        return wrapper

    return decorator


def _make(index, data, length):
    if index == 0:
        return ''.join([
            join(data, length), '\n',
            join(((x * '-') for x in length), length)
        ])
    return join(data, length)


def join(data, length):  # 填充空格
    try:
        row = (''.join((x, (length[index] - len(x)) * ' '))
               for index, x in enumerate(data))
        row = '|'.join(row)
    except UnicodeDecodeError:
        print('UnicodeDecodeError!!!')
        print(data)
        return ''
    return ''.join(('|', row, '|'))


def list2mk(dataset, title=None):
    if not dataset:
        return ''
    txt = ''  # 支持这种形式 ["description", [()]]
    if isinstance(dataset[0], six.string_types):
        txt = dataset[0]
        dataset = dataset[1:]
        dataset = [(str(x[0]), str(x[1])) for x in dataset]  # 为了把数字转为字符串
    dataset = list(dataset)  # just shallow copy
    title and dataset.insert(0, title)
    length = [len(x) for x in dataset[0]]  # assert title is [str, str]
    mk = '\n'.join(
        _make(index, data, length) for index, data in enumerate(dataset))
    if txt:
        mk = '\n'.join((txt, '', mk))
    return mk


def parse_description(dataset, title):
    dataset = {
        isinstance(x, int) and str(x) or x: y
        for x, y in dataset.items()
    }  # 吧数字转为字符串
    if isinstance(dataset, list):
        return ''
    txt = dataset.pop('description', '')
    length = [max(map(len, x)) for x in [dataset, dataset.values()]]  # 取出最大长度

    blank = join(((x * '-') for x in length), length)
    title = list(title.items())[0]
    title = '\n'.join((join(title, length), blank))
    mk = '\n'.join(join(data, length) for data in dataset.items())
    mk = '\n'.join((title, mk))
    if txt:
        mk = '\n'.join((txt, '\n', mk))
    return mk
