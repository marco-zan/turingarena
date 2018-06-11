import collections
import logging
import numbers
from collections import namedtuple
from enum import IntEnum

from bidict import bidict

logger = logging.getLogger(__name__)


class DriverMessage:
    __slots__ = []

    def serialize_arguments(self):
        yield from []

    @staticmethod
    def deserialize_arguments():
        yield from []


def deserialize_request():
    cls = request_types[(yield)]
    return (yield from cls.deserialize_arguments())


def serialize_request(request):
    yield request_types.inv[type(request)]
    yield from request.serialize_arguments()


class MethodCall(DriverMessage, namedtuple("MethodCall", [
    "method_name", "parameters", "has_return_value", "accepted_callbacks"
])):
    __slots__ = []

    @staticmethod
    def deserialize_arguments():
        method_name = yield
        parameters_count = int((yield))
        parameters = [None] * parameters_count
        for i in range(parameters_count):
            parameters[i] = yield from deserialize_data()
        has_return_value = bool(int((yield)))
        callbacks_count = int((yield))
        accepted_callbacks = {}
        for _ in range(callbacks_count):
            callback_name = yield
            callback_parameters_count = int((yield))
            accepted_callbacks[callback_name] = callback_parameters_count

        return MethodCall(
            method_name=method_name,
            parameters=parameters,
            has_return_value=has_return_value,
            accepted_callbacks=accepted_callbacks,
        )

    def serialize_arguments(self):
        yield self.method_name
        yield len(self.parameters)
        for value in self.parameters:
            yield from serialize_data(value)
        yield int(self.has_return_value)
        yield len(self.accepted_callbacks)
        for name, parameters_count in self.accepted_callbacks.items():
            yield name
            yield parameters_count


class CallbackReturn(DriverMessage, namedtuple("CallbackReturn", [
    "return_value"
])):
    __slots__ = []

    @staticmethod
    def deserialize_arguments():
        has_return_value = bool(int((yield)))
        if has_return_value:
            return_value = int((yield))
        else:
            return_value = None
        return CallbackReturn(
            return_value=return_value,
        )

    def serialize_arguments(self):
        has_return_value = (self.return_value is not None)
        yield int(has_return_value)
        if has_return_value:
            yield int(self.return_value)


class Exit(DriverMessage):
    __slots__ = []

    @staticmethod
    def deserialize_arguments():
        yield from []
        return Exit()


request_types = bidict({
    "method_call": MethodCall,
    "callback_return": CallbackReturn,
    "exit": Exit,
})


class MetaType(IntEnum):
    SCALAR = 0
    ARRAY = 1


def get_meta_type(value):
    if isinstance(value, collections.Iterable):
        return MetaType.ARRAY
    if isinstance(value, numbers.Integral):
        return MetaType.SCALAR
    raise AssertionError(f"unsupported type for value: {value}")


def serialize_data(value):
    meta_type = get_meta_type(value)
    yield meta_type.value
    if meta_type is MetaType.ARRAY:
        items = list(value)
        yield len(items)
        for item in items:
            yield from serialize_data(item)
    elif meta_type == MetaType.SCALAR:
        yield int(value)
    else:
        raise AssertionError


def deserialize_data():
    meta_type = MetaType(int((yield)))
    if meta_type is MetaType.ARRAY:
        size = int((yield))
        value = [None] * size
        for i in range(size):
            value[i] = yield from deserialize_data()
    elif meta_type == MetaType.SCALAR:
        value = int((yield))
    else:
        raise AssertionError
    return value
