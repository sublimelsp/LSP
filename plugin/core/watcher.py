import os
from subprocess import Popen, PIPE, STDOUT
import subprocess
import json
import threading
import socket
import time
from .protocol import Notification

class Watcher:

    def __init__(self, root_path, options, session):
        self.process = None
        self.root_path = root_path
        self.options = options
        self.session = session

    @classmethod
    def register(cls, id, options, session):
        watchers = options["watchers"]
        root = ""
        globs = []
        for watcher in watchers:
            uri = watcher["globPattern"]
            file_path = uri.replace("file://", "")
            globs.append(file_path)
            if root:
                root = os.path.commonprefix([root, file_path])
            else:
                root = file_path
        root_path = os.path.dirname(root)
        print("registering watch for root:" + root_path)

        root_path_prefix_len = len(root_path)+1
        globmatches = []
        for glob in globs:
            if "{" in glob:
                rel_glob = glob[root_path_prefix_len:]

                open_pos = rel_glob.index("{")
                close_pos = rel_glob.index("}")
                options = rel_glob[open_pos+1:close_pos].split(",")
                print("found OR values", options)
                for option in options:
                    globmatches.append(["match", rel_glob[:open_pos] + option + rel_glob[close_pos+1:], "wholename"])

            else:
                globmatches.append(["match", glob[root_path_prefix_len:], "wholename"])

        globmatches.insert(0, "anyof")
        options = {
            'expression': globmatches,
            'fields': ["name"]
        }
        
        watcher = Watcher(root_path, options, session)
        thread = threading.Thread(target=watcher.run)
        thread.start()

    def run(self):
        print("thread started")

        command = ["watchman", "get-sockname"]

        output = subprocess.check_output(command)
        output_obj = json.loads(output.decode())
        print(output.decode())
        sockname = output_obj["sockname"]
        print("connecting to", sockname)
        self.options["since"] = int(time.time())
        # {"since": int(time.time()), "expression": ["match", "*.sbt"]}

        args = ["subscribe", self.root_path, "subname_lsp", self.options]
        request = json.dumps(args) + "\n"
        print(request)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(sockname)
            print("connected, sending")
            s.sendall(request.encode())
            print("sent, receiving")
            while True:
                output = s.recv(1024)
                if not output:
                    break
                else:
                    print(output.decode())
                    update_obj = json.loads(output.decode())
                    if "files" in update_obj:
                        events = []
                        for file in update_obj["files"]:
                            full_path = os.path.join(self.root_path, file)
                            print(full_path)
                            # type 1,2,3 = created, changed, deleted
                            events.append({"uri": "file://" + full_path, "type": 2})

                        self.session.send_notification(Notification.didChangeWatchedFiles({"changes": events}))
