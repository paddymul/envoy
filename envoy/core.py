# -*- coding: utf-8 -*-

"""
envoy.core
~~~~~~~~~~

This module provides envoy awesomeness.
"""

import os
import sys
import shlex
import signal
import subprocess
import threading
import pdb
import extproc
import time
import datetime
__version__ = '0.0.2'
__license__ = 'MIT'
__author__ = 'Kenneth Reitz'


def _terminate_process(process):
    if sys.platform == 'win32':
        import ctypes
        PROCESS_TERMINATE = 1
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, process.pid)
        ctypes.windll.kernel32.TerminateProcess(handle, -1)
        ctypes.windll.kernel32.CloseHandle(handle)
    else:
        os.kill(process.pid, signal.SIGTERM)

def _kill_process(process):
   if sys.platform == 'win32':
       _terminate_process(process)
   else:
       os.kill(process.pid, signal.SIGKILL)

def _is_alive(thread):
    if hasattr(thread, "is_alive"):
        return thread.is_alive()
    else:
        return thread.isAlive()

class Command(object):
    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None
        self.out = None
        self.err = None
        self.returncode = None
        self.data = None

    def run(self, data, timeout, kill_timeout, env):
        self.data = data
        environ = dict(os.environ)
        environ.update(env or {})
        after_communicate = ["First set"]
        def target():

            self.process = subprocess.Popen(self.cmd,
                universal_newlines=True,
                shell=False,
                env=environ,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            if sys.version_info[0] >= 3:
                self.out, self.err = self.process.communicate(
                    input = bytes(self.data, "UTF-8") if self.data else None
                )
            else:
                self.out, self.err = self.process.communicate(self.data)

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)
        if _is_alive(thread) :
            _terminate_process(self.process)
            thread.join(kill_timeout)
            if _is_alive(thread):
                _kill_process(self.process)
                thread.join()
        self.returncode = self.process.returncode
        return self.out, self.err


class ConnectedCommand(object):
    def __init__(self,
        process=None,
        std_in=None,
        std_out=None,
        std_err=None):

        self._process = process
        self.std_in = std_in
        self.std_out = std_out
        self.std_err = std_out
        self._status_code = None

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.kill()

    @property
    def status_code(self):
        """The status code of the process.
        If the code is None, assume that it's still running.
        """
        return self._status_code

    @property
    def pid(self):
        """The process' PID."""
        return self._process.pid

    def kill(self):
        """Kills the process."""
        return self._process.kill()

    def expect(self, bytes, stream=None):
        """Block until given bytes appear in the stream."""
        if stream is None:
            stream = self.std_out
        pass

    def send(self, str, end='\n'):
        """Sends a line to std_in."""
        return self._process.stdin.write(str+end)

    def block(self):
        """Blocks until command finishes. Returns Response instance."""
        self._status_code = self._process.wait()



class Response(object):
    """A command's response"""

    def __init__(self, process=None):
        super(Response, self).__init__()

        self._process = process
        self.command = None
        self.std_err = None
        self.std_out = None
        self.status_code = None
        self.history = []


    def __repr__(self):
        if len(self.command):
            return '<Response [{0}]>'.format(self.command[0])
        else:
            return '<Response>'

def wrap_extproc_Capture(capture_obj):
    r = Response()
    r.std_out = capture_obj.stdout.read()
    r.std_err = capture_obj.stderr.read()
    r.status_code = capture_obj.exit_status
    return r

def expand_args(command):
    """Parses command strings and returns a Popen-ready list."""

    # Prepare arguments.
    if isinstance(command, str):
        splitter = shlex.shlex(command)
        splitter.whitespace = '|'
        splitter.whitespace_split = True
        command = []

        while True:
            token = splitter.get_token()
            if token:
                command.append(token)
            else:
                break

        command = list(map(shlex.split, command))

    return command



def parse_to_commands(command):
    command = expand_args(command)
    history = []
    cmds = []
    for c in command:
        cmds.append(Command(c))
    return cmds


def run2(command, data=None, timeout=None, kill_timeout=None, env=None):
    history = []
    for cmd in parse_to_commands(command):

        if len(history):
            # due to broken pipe problems pass only first 10MB
            data = history[-1].std_out[0:10*1024]

        out, err = cmd.run(data, timeout, kill_timeout, env)

        r = Response(process=cmd)

        r.command = cmd.cmd
        r.std_out = out
        r.std_err = err
        r.status_code = cmd.returncode
        history.append(r)
    r = history.pop()
    r.history = history
    return r




def run_extproc(command, data=None, timeout=None, kill_timeout=0, env=None):
    ext_cmds = []
    for command_args in expand_args(command):
        cmd = extproc.Cmd(command_args, e=env)
        ext_cmds.append(cmd)
    if data:
        # the python fork decorator lets us express data in terms of
        # another function, much simpler than mucking about with files
        new_cmds = [extproc.make_echoer(data)]
        new_cmds.extend(ext_cmds)
        ext_cmds = new_cmds
    pi = extproc.Pipe(*ext_cmds, data=data, e=env)
    capture_obj = pi.capture(1,2, timeout=timeout, kill_timeout=kill_timeout)
    return wrap_extproc_Capture(capture_obj)

class ExtResponse(object):

    def __init__(self, pipe_obj):
        self.pipe_obj = pipe_obj

    @property
    def status_code(self):
        return self.pipe_obj.returncode

    @property
    def std_out(self):
        if self.status_code:
            return self.pipe_obj.fd_objs[1].read()

    @property
    def std_err(self):
        if self.status_code:
            return self.pipe_obj.fd_objs[2].read()

class ExtLiveCaptureWrap(object):
    def __init__(self, live_capture_obj):
        self.live_capture_obj = live_capture_obj

    @property
    def status_code(self):
        return self.live_capture_obj.returncode

    @property
    def std_out(self):
        return self.live_capture_obj.stdout

    @property
    def std_err(self):
        return self.live_capture_obj.stderr

def connect_extproc(command, data=None, env=None):
    """Spawns a new process from the given command."""

    ext_cmds = []
    for command_args in expand_args(command):
        cmd = extproc.Cmd(command_args, e=env)
        ext_cmds.append(cmd)
    if data:
        # the python fork decorator lets us express data in terms of
        # another function, much simpler than mucking about with files
        new_cmds = [extproc.make_echoer(data)]
        new_cmds.extend(ext_cmds)
        ext_cmds = new_cmds
    pi = extproc.Pipe(*ext_cmds, data=data, e=env)
    #capture_obj = pi.spawn()
    return ExtLiveCaptureWrap(pi.capture_spawn())


def run(command, data=None, timeout=None, kill_timeout=None, env=None):
    """Executes a given commmand and returns Response.

    Blocks until process is complete, or timeout is reached.
    """

    command = expand_args(command)
    history = []
    for c in command:

        if len(history):
            # due to broken pipe problems pass only first 10MB
            data = history[-1].std_out[0:10*1024]

        cmd = Command(c)
        out, err = cmd.run(data, timeout, kill_timeout, env)

        r = Response(process=cmd)

        r.command = c
        r.std_out = out
        r.std_err = err
        r.status_code = cmd.returncode

        history.append(r)

    r = history.pop()
    r.history = history

    return r


def connect(command, data=None, env=None):
    """Spawns a new process from the given command."""

    # TODO: support piped commands
    command_str = expand_args(command).pop()
    environ = dict(os.environ)
    environ.update(env or {})

    process = subprocess.Popen(command_str,
                               universal_newlines=True,
                               shell=False,
                               env=environ,
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               bufsize=0,
                               )

    return ConnectedCommand(process=process)
