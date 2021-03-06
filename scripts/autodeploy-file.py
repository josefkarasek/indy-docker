#!/usr/bin/python
#
# Copyright (C) 2015 John Casey (jdcasey@commonjava.org)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import os
import sys
import hashlib
import re
import shutil
from optparse import (OptionParser,BadOptionError,AmbiguousOptionError)

WATCH=os.path.join(os.environ.get("HOME"), "indy-watched")
DEV=os.path.join(os.environ.get("HOME"), "indy-dev")
NAME='indy'
IMAGE='buildchimp/indy'

INDY_BINARY_RE = re.compile('indy-launcher-.+-launcher.tar.gz')

def run(cmd, fail=True):
  print cmd
  ret = os.system(cmd)
  if fail and ret != 0:
    print "%s (failed with code: %s)" % (cmd, ret)
    sys.exit(ret)

def parse():
  usage = """%prog [options] <init-script> [init-options]"""
  parser = OptionParser(usage=usage)
  parser.disable_interspersed_args()
  
  parser.add_option('-w', '--watchdir', help='Directory to watch for updated files')
  parser.add_option('-d', '--devdir', help='Directory to copy Indy tarballs to for deployment')
  parser.add_option('-i', '--image', help='The image to use when deploying (default: builchimp/indy)')
  parser.add_option('-n', '--name', help='The container name under which to deploy Indy volume container (default: indy)')
  parser.add_option('-s', '--service', help='The systemd service to manage when redeploying (default: indy-server)')
  parser.add_option('-N', '--noservice', action='store_true', help='Do not try to restart a systemd service')
  
  opts, args = parser.parse_args()
  
  init_cmd = " ".join(args)
  
  return (opts, init_cmd)

def deploy(watch_file, watchdir, devdir, opts, init_cmd):
  print "Deploying: %s" % watch_file
  
  print "Clearing deployments directory: %s" % devdir
  for file in os.listdir(devdir):
    os.remove(os.path.join(devdir, file))
  
  print "Moving deployment %s from: %s to: %s" % (watch_file, watchdir, devdir)
  shutil.move(os.path.join(watchdir, watch_file), os.path.join(devdir, watch_file))
  
  name = opts.name or NAME
  image = opts.image or IMAGE
  
  if opts.noservice is not True and opts.service and os.path.exists("/bin/systemctl"):
    print "Stopping service: %s" % opts.service
    run("systemctl stop %s" % opts.service)
  
  print "Shutting down existing docker container"
  run("docker stop %s" % name, fail=False)
  run("docker rm %s" % name, fail=False)
  run("docker pull %s" % image, fail=False)
  
  print "Running init command: %s" % init_cmd
  run(init_cmd)
  
  if opts.noservice is not True and opts.service and os.path.exists("/bin/systemctl"):
    print "Starting service: %s" % opts.service
    run("systemctl start %s" % opts.service)


def do(opts, init_cmd):
  watch = opts.watchdir or WATCH
  dev = opts.devdir or DEV
  
  files = os.listdir(watch)
  watch_file = None
  if len(files) > 0:
    files.sort(key=lambda x: os.stat(os.path.join(watch, x)).st_mtime, reverse=True)
    for file in files:
      if INDY_BINARY_RE.match(file):
        watch_file = file
        break
  
  if watch_file is None:
    print "No deployable file found in: %s" % watch
    sys.exit(0)
  
  dev_file=None
  files = os.listdir(dev)
  if len(files) > 0:
    files.sort(key=lambda x: os.stat(os.path.join(dev, x)).st_mtime, reverse=True)
    for file in files:
      if INDY_BINARY_RE.match(file):
        dev_file = file
        break
  
  do_deploy=True
  if dev_file is not None:
    watch_sha = hashlib.sha256(open(os.path.join(watch, watch_file), 'rb').read()).hexdigest()
    dev_sha = hashlib.sha256(open(os.path.join(dev, dev_file), 'rb').read()).hexdigest()
    if watch_sha == dev_sha:
      do_deploy = False
  
  if do_deploy:
    deploy( watch_file, watch, dev, opts, init_cmd )
  else:
    print "Nothing has changed; nothing to deploy"
    sys.exit(0)

if __name__ == '__main__':
    (opts, init_cmd) = parse()
    do(opts, init_cmd)
