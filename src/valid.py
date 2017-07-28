import re
from .para import Valid as _Valid, MethodProxy
from ssrd.users.models import User, AuthorizeCode, Project, Invitation, Collect
from ssrd import const

__all__ = ("V")
ROLES = dict(const.ROLES)
STATUS = dict(const.STATUS)
ORDER_STATUS = dict(const.ORDER_STATUS)


class Valid(_Valid):
    def user(self, pk):
        self.msg = u"用户不存在或已停用"
        user = User.objects.get(id=pk)
        return user

    def authorizecode(self, pk):
        self.msg = u"用户不存在或已停用"
        ac = AuthorizeCode.objects.get(pk=pk)
        return ac

    def invitation(self, pk):
        self.msg = u"用户不存在或已停用"
        obj = Invitation.objects.get(pk=pk)
        return obj

    def project(self, pk):
        self.msg = '项目不存在'
        obj = Project.objects.get(pk=pk)
        return obj

    def collect(self, pk):
        self.msg = "收藏品不存在"
        obj = Collect.objects.get(pk=pk)
        return obj

    def role(self, value):
        self.msg = "错误的参数值：%s" % str(ROLES)
        return int(value) in ROLES

    def status(self, value):
        self.msg = "错误的参数值：%s" % str(STATUS)
        return int(value) in STATUS

    def order_status(self, value):
        self.msg = "错误的参数值：%s" % str(ORDER_STATUS)
        return int(value) in ORDER_STATUS

    def name(self, name, length=200):
        if not name:
            self.msg = (u"此处不能留空")
        if len(name) > length:
            self.msg = (u"名称长度不能超过200")
            return
        if not const.RE_NAME.match(name):
            self.msg = (u"名称不能包含特殊字符")
            return
        return name.strip()

    def email(self, email):
        if const.RE_EMAIL.match(email):
            return email.strip()

    def username(self, username):
        if const.RE_NAME(username):
            return username.strip()

    def password(self, password):
        if len(password) < 6:
            self.msg = "密码长度不能小于6位"
            return

    def file(self, obj):
        if not hasattr(obj, 'file'):
            self.msg = '必须为文件类型'
        return

    def num(self, num, n=1, bit=199, contain_0=True):
        re_str = r'[%s-9][0-9]{0,%s}$' % (n, bit)
        if re.match(re_str, num):
            if contain_0:
                return int(num)  # int(0) = 0， 但是布尔值还是False
            else:
                return int(num) or -1
        self.msg = "必须为数值类型"
        return


V = MethodProxy(Valid)
