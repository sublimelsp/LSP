from os.path import abspath, dirname, join
import json


if __name__ == '__main__':
    file = abspath(join(dirname(__file__), '..', 'unittesting.json'))
    with open(file, 'w') as fp:
        config = {
            "deferred": True,
            "verbosity": 2,
            "capture_console": True,
            "failfast": True,
            "reload_package_on_testing": False,
            "start_coverage_after_reload": False,
            "show_reload_progress": False,
            "output": None,
            "generate_html_report": False
        }
        json.dump(config, fp, indent=4)
