import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Frame:
    def __init__(self, *, global_frame, scope, parent, interface):
        self.global_frame = global_frame
        self.scope = scope
        self.parent = parent
        self.interface = interface

        self.values = {
            l: None for l in self.scope.variables.locals().values()
        }

    def __getitem__(self, variable):
        if variable in self.values:
            return self.values[variable]
        elif self.parent:
            return self.parent[variable]
        else:
            raise KeyError

    def __setitem__(self, variable, value):
        if variable in self.values:
            self.values[variable] = value
        elif self.parent:
            self.parent[variable] = value
        else:
            raise KeyError

    def __str__(self):
        return str({
            variable.name: value
            for variable, value in self.values.items()
        })

    @contextmanager
    def child(self, scope):
        assert scope.parent == self.scope
        yield Frame(
            global_frame=self.global_frame if self.global_frame is not None else self,
            parent=self,
            scope=scope,
            interface=self.interface,
        )