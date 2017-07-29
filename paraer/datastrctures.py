# encoding: utf-8
from __future__ import unicode_literals


class Result(object):
    def __init__(self, dataset=None, serializer=None):
        self.errors = []
        self._error = self.errors.append
        self.serializer = serializer
        self.dataset = None
        self.msg = None

    def data(self, dataset):
        self.dataset = dataset
        return self

    def error(self, key, value, **kwargs):
        self._error(dict(kwargs, name=key, value=value))
        return self

    def perm(self, reason):
        self.msg = reason
        return self

    def __nonzero__(self):
        return not self.errors

    def response(self):
        raise NotImplementedError

    def __call__(self, status=200, serialize=False, **kwargs):
        return self.response(status=status, serialize=serialize, **kwargs)


class Valid(object):
    def __init__(self, method, **kwargs):
        self.method = method
        self.status = 200
        self.msg = None
        self.kwargs = kwargs

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
