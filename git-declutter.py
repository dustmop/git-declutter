# usage: git-declutter -i files -o repo *.png

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import time


def mkdir_p(path):
  os.makedirs(path)


def execute(path, cmd, vars=None):
  pwd = os.getcwd()
  try:
    os.chdir(path)
    env = None
    if vars:
      env = os.environ.copy()
      for k, v in vars.items():
        env[k] = v
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env)
    output, err = p.communicate()
    return output.strip()
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


def construct_realname_with_version(path):
  basename = path.basename
  match = re.match(r'^(.*)\.(\d+)$', basename)
  if match:
    realname = match.group(1)
    version = int(match.group(2))
    return realname, version
  else:
    return None, None


class MessageProvider(object):
  def __init__(self, filename):
    self.filename = filename
    self.map = {}
    self.messages = []
    self.read()

  def read(self):
    if not self.filename:
      return
    fp = open(self.filename, 'r')
    contents = fp.read()
    fp.close()
    for line in contents.split('\n'):
      if not line:
        continue
      space_pos = line.find(' ')
      comment_pos = line.find('#')
      mtime = int(line[0:space_pos])
      txt = line[space_pos:comment_pos]
      self.messages.append([mtime, txt])
      self.map[mtime] = txt
    self.messages.reverse()

  def get(self, mtime):
    return self.map.get(mtime)


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


def copy_to_repo(src, dst, message, commits, is_dry_run):
  d = datetime.datetime.fromtimestamp(src.mtime)
  time_txt = d.strftime('%a %b %d %Y %H:%M:%S')
  time_txt = time_txt + time.strftime(' GMT%z (%Z)', time.gmtime())
  if not message:
    message = time_txt
  if is_dry_run:
    print('----------------------------------------')
    print('%s => %s' % (src.fullpath, dst.fullpath))
    print('cd %s && git add %s && time [%s]' % (dst.dir, dst.name, time_txt))
  else:
    shutil.copy2(src.fullpath, dst.fullpath)
    execute(dst.dir, ['git', 'add', dst.name])
    execute(dst.dir, ['git', 'commit', '--date="%s"' % time_txt, '-m', message],
            {'GIT_COMMITTER_DATE': time_txt})
    rev = execute(dst.dir, ['git', 'rev-parse', 'HEAD'])
    commits.append([src.mtime, time_txt, rev])


def declutter(input_dir, output_dir, glob, is_dry_run, create_file,
              message_file):
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
  msg_provider = MessageProvider(message_file)
  commits = []
  for t in track:
    target = Path.like(t, dir=output_dir, name=(t.realname + '.' + t.ext))
    copy_to_repo(t, target, msg_provider.get(t.mtime), commits, is_dry_run)
  commits.reverse()
  # Show commits.
  if create_file:
    fout = open(create_file, 'w')
    for mtime, time_txt, rev in commits:
      fout.write('%s %s # %s\n' % (mtime, time_txt, rev))
    fout.close()
    sys.stdout.write('Wrote temp commit messages to %s\n' % create_file)


def run():
  p = argparse.ArgumentParser(description='Turn a directory of poorly-named ' +
                              'files into a nice, organized git repository.')
  p.add_argument('-i', dest='input_dir',
                 help='Input directory of poorly-named files.', required=True)
  p.add_argument('-o', dest='output_dir',
                 help='Output git repository to create.', required=True)
  p.add_argument('-f', dest='force', action='store_true',
                 help='Force even if repository exists already.')
  p.add_argument('-d', dest='is_dry_run', action='store_true',
                 help='Dry run for adding files to a repo.')
  p.add_argument('-c', dest='create_file',
                 help=('Create a file based upon the new repo, to be edited ' +
                       'with commit messages.'))
  p.add_argument('-m', dest='message_file',
                 help='Use a file for commit messages.')
  p.add_argument('globs', type=str, nargs='+',
                 help='Globs of files to process.')
  args = p.parse_args()
  if not create_repo(args.output_dir):
    if not args.force:
      raise RuntimeError('Could not create repo')
  declutter(args.input_dir, args.output_dir, args.globs, args.is_dry_run,
            args.create_file, args.message_file)


if __name__ == '__main__':
  run()
