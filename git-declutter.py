# usage: git-declutter files repo *.mse-set

import argparse
import datetime
import os
import re
import subprocess
import sys
import time


def mkdir_p(path):
  os.makedirs(path)


def execute(path, cmd):
  pwd = os.getcwd()
  try:
    os.chdir(path)
    status = subprocess.call(' '.join(cmd), shell=True)
  finally:
    os.chdir(pwd)


def create_repo(path):
  if os.path.isdir(path):
    return False
  mkdir_p(path)
  execute(path, ['git', 'init'])
  return True


def match_glob(path, globs):
  for g in globs:
    if g.startswith('*.'):
      ext = g[2:]
      return path.endswith('.' + ext)
  return False


class Path(object):
  def __init__(self, dir, name):
    self.dir = dir
    self.name = name
    self.realname = None
    self.version = None
    self.init()

  def init(self):
    self.fullpath = os.path.join(self.dir, self.name)
    self.mtime = self.mod_time(self.fullpath)
    (basename, ext) = os.path.splitext(self.name)
    self.basename = basename
    self.ext = ext[1:]

  def mod_time(self, path):
    try:
      s = os.stat(path)
      return int(s.st_mtime)
    except OSError:
      return 0

  @staticmethod
  def like(other, realname=None, version=None, dir=None, name=None):
    make = Path(other.dir, other.name)
    if dir:
      make.dir = dir
    if name:
      make.name = name
    if realname:
      make.realname = realname
    if version:
      make.version = version
    make.init()
    return make

  def __str__(self):
    items = []
    items.append('dir="%s"' % self.dir)
    items.append('basename="%s"' % self.basename)
    items.append('ext="%s"' % self.ext)
    if not self.mtime is None:
      items.append('mtime=%s' % self.mtime)
    if not self.realname is None:
      items.append('realname="%s"' % self.realname)
    if not self.version is None:
      items.append('version=%s' % self.version)
    return '#<Path %s>' % (' '.join(items))


def construct_realname_with_version(path):
  basename = path.basename
  match = re.match(r'^(.*)\.(\d+)$', basename)
  if match:
    realname = match.group(1)
    version = int(match.group(2))
    return realname, version
  else:
    return None, None


def copy_to_repo(src, dst):
  d = datetime.datetime.fromtimestamp(src.mtime)
  #                 Sun Jul 12 2015 21:01:27 GMT-0400 (EDT)
  time_text = d.strftime('%a %b %d %Y %H:%M:%S')
  time_text = time_text + time.strftime(' GMT%z (%Z)', time.gmtime())
  print('----------------------------------------')
  print('%s => %s' % (src.fullpath, dst.fullpath))
  print('cd %s && git add %s && time [%s]' % (dst.dir, dst.name, time_text))
  #shutil.copy2(src.fullpath, dst.fullpath)


def declutter(input_dir, output_dir, glob):
  # List input directory, and sort it (by name).
  entities = os.listdir(input_dir)
  entities.sort()
  # Find files matching the glob, and sort by modification time.
  matches = []
  for ent in entities:
    if match_glob(ent, glob):
      matches.append(Path(input_dir, ent))
  matches.sort(key=lambda p:p.mtime)
  # Get version numbers from names, separate into tracked and untracked files.
  track = []
  untrack = []
  for path in matches:
    (realname, version) = construct_realname_with_version(path)
    if realname:
      track.append(Path.like(path, realname=realname, version=version))
    else:
      untrack.append(path)
  # Check that versions are monotomically increasing.
  collection = {}
  for t in track:
    if not t.realname in collection:
      if t.version != 1:
        raise RuntimeError('File "%s" is version %d, expected 1' %
                           (t.realname, t.version))
      collection[t.realname] = (t.version, t)
    else:
      prev = collection[t.realname][0]
      if t.version != prev + 1:
        raise RuntimeError('File "%s" is version %d, expected %d' %
                           (t.realname, t.version, prev + 1))
      collection[t.realname] = (t.version, t)
  # Display.
  for realname, val in collection.items():
    (version, path) = val
    sys.stdout.write('"%s.%s" @ %d\n' % (realname, path.ext, version))
  if untrack:
    sys.stdout.write('Untracked:\n')
    for u in untrack:
      sys.stdout.write('%s\n' % u)
  # Prompt?
  sys.stdout.write('Okay? [y/n]: ')
  answer = sys.stdin.readline().strip()
  if answer != 'y':
    return
  # Execute.
  for t in track:
    target = Path.like(t, dir=output_dir, name=(t.realname + '.' + t.ext))
    copy_to_repo(t, target)


def run():
  p = argparse.ArgumentParser(description='Turn a directory of poorly-named ' +
                              'files into a nice, organized git repository.')
  p.add_argument('-i', dest='input_dir',
                 help='Input directory of poorly-named files.', required=True)
  p.add_argument('-o', dest='output_dir',
                 help='Output git repository to create.', required=True)
  p.add_argument('-f', dest='force', action='store_true',
                 help='Force even if repository exists already.')
  p.add_argument('globs', type=str, nargs='+',
                 help='Globs of files to process.')
  args = p.parse_args()
  # Make sure output_dir doesn' exist yet. Create it.
  # step 1:
  # list intput_dir + glob
  # sort it
  # for each, match the glob
  #   add to file-set
  #   split off version
  #   make sure versions are in order
  # display changes (file-set, each change)
  # show untracked files
  # add to git
  if not create_repo(args.output_dir):
    if not args.force:
      raise RuntimeError('Could not create repo')
  declutter(args.input_dir, args.output_dir, args.globs)


if __name__ == '__main__':
  run()
