# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
import six
from functools import wraps
from uuid import uuid1
from django.utils.translation import ugettext as _
from django.conf import settings


class Valid(object):
    def __init__(self, method, **kwargs):
        self.method = method
        self.status = 400
        self.msg = None
        self.kwargs = kwargs
        self.perm_403 = kwargs.pop('perm_403', 403)

    def __str__(self):
        return '<Valid: %s>' % self.method

    def __repr__(self):
        return '<Valid: %s>' % self.method

    def __call__(self, *args, **kwargs):
        return getattr(self, self.method)(*args, **kwargs)


class MethodProxy(object):
    kwargs = {}

    def __init__(self, valid_class=None):
        self.valid_class = valid_class

    def __call__(self, *args, **kwargs):
        self.kwargs = kwargs
        return self

    def __getattr__(self, key):
        return self.valid_class(key, **self.kwargs)


V = MethodProxy()


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
            type='integer', required=item.get('required', True))
        item.setdefault('required', required)
        item.setdefault('type', type_by_name(item['name']))
        description = item.get('description') or item.get(
            'msg') or 'description'
        msg = getattr(item['method'], 'msg',
                      item.get('msg') or item.get('description') or
                      'msg')  # method maybe V
        if type(description) in {list, tuple}:
            description = list2mk(
                description, title=['value',
                                    'description'])  # 支持list转化为markdown表格的形式
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
        # if getattr(func, 'paginate', False):  # 如果方法需要分页 则加上分页参数
        # itemset.extend(pager)
        # 不把_doc_generator 放在wrapper里的原因是， _doc_generater只会在项目启动的时候被调用

        swagger = _doc_generater(itemset, func)

        def wrapper(cls, request, *args, **kwargs):
            paramap = dict(kwargs)
            data = request.GET
            if request.data:  # {'data': {'asd':'efg'}}   前端传的这种形式,只有data一个key
                if len(request.data) == 1 and 'data' in request.data:
                    data = request.data.get('data')
                else:
                    data = request.data
            paramap.update({x: y for x, y in data.items()})
            result = cls.result_class()
            for item in itemset:
                name, v, required, msg, replace = [
                    item[x]
                    for x in ['name', 'method', 'required', 'msg', 'replace']
                ]
                value = None  # 参数不存在时， value置为None, 与''区别, 如设置推广组的投放期时, 若传start_date='', 则把adgroup的start_date置空
                para = paramap.get(name)
                if required and not para:
                    result.error(name, _(u'required'))
                if para is not None:
                    if para:
                        try:
                            value = v(para)
                        except Exception:
                            if settings.DEBUG:
                                from traceback import print_exc
                                print('----')
                                print_exc()
                        if v.status == 403:
                            return result.perm(name, v.msg or
                                               msg)(status=v.status)
                        if not value:
                            result.error(name, v.msg or msg)
                    name = replace or name
                    kwargs.update({
                        name: value or para
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
                perm = method(request, kwargs)
                if not perm:
                    return cls.result_class().perm(reason=reason)(status=403)
            return func(cls, request, *args, **kwargs)

        return wrapper

    return decorator


def _make(index, data, length):
    if index == 0:
        return ''.join([join(data, length), '\n', join(((x * '-') for x in length), length)])
    return join(data, length)


def join(data, length):  # 填充空格
    try:
        row = '|'.join([
            ''.join([x, (length[index] - len(x)) * ' '])
            for index, x in enumerate(data)
        ])
    except UnicodeDecodeError:
        print('UnicodeDecodeError!!!')
        return ''

    return ''.join(['|', row, '|'])


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
