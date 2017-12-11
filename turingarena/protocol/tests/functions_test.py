import pytest

from turingarena.protocol.model.exceptions import ProtocolError
from turingarena.protocol.module import ProtocolSource
from turingarena.protocol.tests.util import cpp_implementation


def test_function_no_arguments():
    with cpp_implementation(
            protocol_text="""
                interface function_no_arguments {
                    function function_no_arguments();
                    main {
                        call function_no_arguments();
                    }
                }
            """,
            source_text="""
                void function_no_arguments() {
                }
            """,
            protocol_name="turingarena.protocol.tests.function_no_arguments",
            interface_name="function_no_arguments",
    ) as impl:
        with impl.run() as p:
            p.function_no_arguments()


def test_function_with_arguments():
    with cpp_implementation(
            protocol_text="""
                interface function_with_arguments {
                    function function_with_arguments(int a, int b);
                    main {
                        var int a, b;
                        input a, b;
                        call function_with_arguments(a, b);
                    }
                }
            """,
            source_text="""
                #include <cassert>
                void function_with_arguments(int a, int b) {
                    assert(a == 1 && b == 2);
                }
            """,
            protocol_name="turingarena.protocol.tests.function_with_arguments",
            interface_name="function_with_arguments",
    ) as impl:
        with impl.run() as p:
            p.function_with_arguments(1, 2)


def test_function_return_value():
    with cpp_implementation(
            protocol_text="""
                interface function_return_value {
                    function function_return_value(int a) -> int;
                    main {
                        var int a, b;
                        input a;
                        call function_return_value(a) -> b;
                        output b;
                    }
                }
            """,
            source_text="""
                #include <cassert>
                int function_return_value(int a) {
                    assert(a == 1);
                    return 2;
                }
            """,
            protocol_name="turingarena.protocol.tests.function_return_value",
            interface_name="function_return_value",
    ) as impl:
        with impl.run() as p:
            assert p.function_return_value(1) == 2


def test_function_return_type_not_scalar():
    protocol_text = """
        interface function_return_type_not_scalar {
            function function_return_type_not_scalar() -> int[];
            main {}
        }
    """
    source = ProtocolSource(
        text=protocol_text,
        filename="<none>",
    )

    with pytest.raises(ProtocolError) as excinfo:
        source.compile()
    assert 'return type must be a scalar' in excinfo.value.get_user_message()
