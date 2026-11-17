#!/usr/bin/env python3
"""Use existing docker-group membership without sudo or socket chmod."""
import grp
import os
from pathlib import Path
import pwd
import shlex
import sys

socket = Path("/var/run/docker.sock")
gid = socket.stat().st_gid
command = ["docker", *sys.argv[1:]]
if gid in {os.getgid(), *os.getgroups()}:
    os.execvp(command[0], command)
group = grp.getgrgid(gid)
user = pwd.getpwuid(os.getuid()).pw_name
if group.gr_name != "docker" or user not in group.gr_mem:
    raise SystemExit("Current account is not a member of the socket's docker group")
os.execvp("sg", ["sg", group.gr_name, "-c", shlex.join(command)])
