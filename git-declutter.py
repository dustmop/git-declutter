# usage: git-declutter files repo *.mse-set

import argparse
import os
import subprocess
import sys


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
  def __init__(self, dir, file):
    self.dir = dir
    self.name = file
    self.fullpath = os.path.join(self.dir, self.name)
    self.mtime = self.mod_time(self.fullpath)
    (basename, ext) = os.path.splitext(self.name)
    self.basename = basename
    self.ext = ext

  def mod_time(self, path):
    s = os.stat(path)
    return int(s.st_mtime)

  def __str__(self):
    return ('#<Path dir="%s" basename="%s" ext="%s" mtime=%s>' %
            (self.dir, self.basename, self.ext, self.mtime))


def declutter(input_dir, output_dir, glob):
  entities = os.listdir(input_dir)
  entities.sort()
  matches = []
  for ent in entities:
    if match_glob(ent, glob):
      matches.append(Path(input_dir, ent))
  matches.sort(key=lambda p:p.mtime)
  for path in matches:
    print path


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
  print('1 [%s]', args.input_dir)
  print('2 [%s]', args.output_dir)
  print('3 [%s]', args.globs)
  if not create_repo(args.output_dir):
    if not args.force:
      raise RuntimeError('Could not create repo')
  declutter(args.input_dir, args.output_dir, args.globs)


if __name__ == '__main__':
  run()
