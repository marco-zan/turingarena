from turingarena_impl.cli import docopt_cli, init_logger
from turingarena_impl.config import install_cli, uninstall_cli
from turingarena_impl.interface.cli import generate_template_cli, generate_skeleton_cli, validate_interface_cli
from turingarena_impl.problem.cli import evaluate_cli
from turingarena_impl.pythonsite import configure_python_site_cli
from turingarena_impl.tests.cli import test_cli
from turingarena_impl.web.serve import serve_cli


@docopt_cli
def main(args):
    """TuringArena command line interface.

    Usage:
      turingarena [options] <cmd> [<args>]...
      turingarena --help-commands

    Options:
      --log-level=<level>  Set logging level.
      --help-commands  Show list of available commands.
    """
    init_logger(args)

    commands = {
        "evaluate": evaluate_cli,
        "template": generate_template_cli,
        "skeleton": generate_skeleton_cli,
        "validate": validate_interface_cli,
        "serve": serve_cli,
        "test": test_cli,
        "install": install_cli,
        "uninstall": uninstall_cli,
        "pythonsite": configure_python_site_cli,
    }

    if args["--help-commands"]:
        print("Avaliable commands:")
        print()
        for c, cli in commands.items():
            doc = cli.__doc__.splitlines(keepends=False)[0]
            print(f"{c:20} {doc}")
        print()
        print("For further help: turingarena <command> -h")
        return

    argv2 = args["<args>"]
    commands[args["<cmd>"]](argv2)


if __name__ == '__main__':
    main()
