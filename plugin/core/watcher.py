import os
import subprocess
import json
import threading
import socket
import time
# import shutils
from .protocol import Notification
from .url import filename_to_uri, uri_to_filename
from .logging import debug


def process_watchers(lsp_watchers):
    root = ""
    globs = []
    for watcher in lsp_watchers:
        uri = watcher["globPattern"]
        file_path = uri_to_filename(uri)
        globs.append(file_path)
        if root:
            root = os.path.commonprefix([root, file_path])
        else:
            root = file_path
    root_path = os.path.dirname(root)
    return globs, root_path

def build_glob_matches(root_path, globs):
    root_path_prefix_len = len(root_path)+1
    globmatches = []
    for glob in globs:
        if "{" in glob:
            rel_glob = glob[root_path_prefix_len:]

            open_pos = rel_glob.index("{")
            close_pos = rel_glob.index("}")
            options = rel_glob[open_pos+1:close_pos].split(",")
            debug("found OR values", options)
            for option in options:
                globmatches.append(["match", rel_glob[:open_pos] + option + rel_glob[close_pos+1:], "wholename"])

        else:
            globmatches.append(["match", glob[root_path_prefix_len:], "wholename"])
    return globmatches


def make_watch(registration_options):
    globs, root_path = process_watchers(registration_options["watchers"])   
    debug("registering watch for root:" + root_path)

    globmatches = build_glob_matches(root_path, globs)
    globmatches.insert(0, "anyof")
    subscribe_options = {
        'expression': globmatches
        # 'fields': ["name"]
    }

    subscribe_options["since"] = int(time.time())

    return root_path, subscribe_options


class WatchConfig:

    def __init__(self, registration_id, session, root_path, subscribe_options):
        self.registration_id = registration_id
        self.subscription_id = session.config.name + "_" + registration_id
        self.session = session
        self.root_path = root_path
        self.subscribe_options = subscribe_options


def make_subscription_request(watch_config):
    return json.dumps(["subscribe", watch_config.root_path, watch_config.subscription_id, watch_config.subscribe_options]) + "\n"

def make_unsubscribe_request(watch_config):
    return json.dumps(["unsubscribe", watch_config.root_path, watch_config.subscription_id]) + "\n"


class Watcher:

    queued_watches = list()
    running_watches = dict()
    kill_watches = list()
    thread = None

    @classmethod
    def is_available(cls):
        return True
        # return shutils.which("watchman")

    @classmethod
    def unregister(cls, id):
        cls.kill_watches.append(cls.running_watches.pop(id))

    @classmethod
    def unregister_all(cls):
        for id in cls.running_watches:
            cls.unregister(id)

    @classmethod
    def start_watchman(cls):
        thread = threading.Thread(target=cls.run_watchman_session)
        thread.start()

    @classmethod
    def queue_watch(cls, watch):
        pass

    @classmethod
    def register(cls, id, options, session):
        if cls.thread is None:
            cls.start_watchman()

        root_path, subscribe_options = make_watch(options)
        cls.queued_watches.append(WatchConfig(id, session, root_path, subscribe_options))
       
        # watcher = Watcher(root_path, options, session)
        # push to session.

    @classmethod
    def run_watchman_session(cls):

        def handle_files_update(update_obj):
            subscription = update_obj["subscription"]
            watch_config = cls.running_watches[subscription]

            events = []
            for file in update_obj["files"]:
                full_path = os.path.join(watch_config.root_path, file["name"])
                debug("watchman notification:", full_path)
                # type 1,2,3 = created, changed, deleted
                # todo: completely disregards requested WatchKind
                change_type = 1
                if not file["new"]:
                    change_type = 2 if file["exists"] else 4
                events.append({"uri": filename_to_uri(full_path), "type": change_type})

            watch_config.session.send_notification(Notification.didChangeWatchedFiles({"changes": events}))

        debug("watchman thread started")

        # get watchman socket name
        command = ["watchman", "get-sockname"]
        output = subprocess.check_output(command)
        output_obj = json.loads(output.decode())
        sockname = output_obj["sockname"]

        debug("connecting to", sockname)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(sockname)
            debug("connected")

            while True:
                # subscribe
                if len(cls.queued_watches) > 0:
                    watch_config = cls.queued_watches.pop()
                    debug("creating subscription", watch_config.subscription_id, watch_config.root_path)
                    request = make_subscription_request(watch_config)
                    debug(request)
                    s.sendall(request.encode())

                    cls.running_watches[watch_config.subscription_id] = watch_config

                # unsubscribe
                if len(cls.kill_watches) > 0:
                    watch_config = cls.kill_watches.pop()
                    request = make_unsubscribe_request(watch_config)
                    debug(request)
                    s.sendall(request.encode())

                # response
                debug("waiting for response")
                output = s.recv(1024)
                if not output:
                    break
                else:
                    debug("watchman sent ", output.decode())
                    update_obj = json.loads(output.decode())

                    if "files" in update_obj:
                        handle_files_update(update_obj)

            debug("watchman thread ended")
