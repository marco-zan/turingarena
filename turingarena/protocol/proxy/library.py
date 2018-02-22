from contextlib import contextmanager

from turingarena.protocol.driver.client import DriverClient, DriverClientEngine
from turingarena.protocol.module import ProtocolModule
from turingarena.sandbox.client import SandboxClient


class ProxiedAlgorithm:
    def __init__(self, *, algorithm_dir, protocol_name, interface_name):
        self.algorithm_dir = algorithm_dir
        self.protocol_name = protocol_name
        self.interface_name = interface_name

    @contextmanager
    def run(self, **global_variables):
        protocol_module = ProtocolModule(name=self.protocol_name)

        interface_signature = protocol_module.load_interface_signature(self.interface_name)

        sandbox = SandboxClient(algorithm_dir=self.algorithm_dir)
        with sandbox.run() as process:
            driver = DriverClient(
                protocol_name=self.protocol_name,
                interface_name=self.interface_name,
                process=process,
            )
            with driver.connect() as connection:
                engine = DriverClientEngine(
                    connection=connection,
                    interface_signature=interface_signature,
                )
                engine.begin_main(**global_variables)
                proxy = Proxy(engine=engine, interface_signature=interface_signature)
                yield process, proxy
                engine.end_main()


class Proxy:
    def __init__(self, engine, interface_signature):
        self._engine = engine
        self._interface_signature = interface_signature

    def __getattr__(self, item):
        try:
            self._interface_signature.functions[item]
        except KeyError:
            raise AttributeError

        def method(*args, **kwargs):
            return self._engine.call(item, args=args, callbacks_impl=kwargs)

        return method