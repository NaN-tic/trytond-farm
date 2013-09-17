#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from sql import Flavor
from sql.functions import Function


class GenerateSeries(Function):
    __slots__ = ('start', 'stop', 'step')
    _function = 'GENERATE_SERIES'

    def __init__(self, start, stop, step=None):
        self.start = start
        self.stop = stop
        self.step = step

    def __str__(self):
        flavor = Flavor.get()
        Mapping = flavor.function_mapping.get(self.__class__)
        if Mapping:
            return str(Mapping(self.start, self.stop, self.step))
        param = flavor.param

        def format(arg):
            if isinstance(arg, basestring):
                return param
            else:
                return str(arg)
        if self.step:
            return self._function + '(%s, %s, %s)' % (self.start, self.stop,
                self.step)
        return self._function + '(%s, %s)' % (self.start, self.stop)

    @property
    def params(self):
        Mapping = Flavor.get().function_mapping.get(self.__class__)
        if Mapping:
            return Mapping(*self.args).params
        p = []
        for arg in (self.start, self.stop):  # , self.step):
            if arg is None:
                continue
            if isinstance(arg, basestring):
                p.append(arg)
            elif hasattr(arg, 'params'):
                p.extend(arg.params)
        return tuple(p)
