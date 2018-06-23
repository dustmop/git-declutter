import argparse
import datetime
import hashlib
import os
import re
import shutil
import subprocess
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


def construct_realname_with_version(path):
  basename = path.basename
  match = re.match(r'^(.*)\.(\d+)$', basename)
  if match:
    realname = match.group(1)
    version = int(match.group(2))
    return realname, version
  else:
    return None, None


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


def build_file_list(inputs):
  result = []
  errors = []
  for i in inputs:
    if os.path.isfile(i):
      result.append(os.path.abspath(i))
    elif os.path.isdir(i):
      result += [os.path.abspath(os.path.join(i, p)) for p in os.listdir(i)]
    else:
      errors.append('Not found: "%s"' % i)
  if len(errors):
    raise RuntimeError(','.join(errors))
  return result


def get_file_metadata(file_list):
  result = []
  for f in file_list:
    basename = os.path.basename(f)
    dir = os.path.dirname(f)
    stat = os.stat(f)
    m = hashlib.sha256()
    m.update(open(f, 'rb').read())
    hash = m.hexdigest()[:8]
    dt = datetime.datetime.fromtimestamp(int(stat.st_mtime))
    result.append({'dir': dir, 'basename': basename, 'path': f, 'hash': hash,
                   'modified': dt.strftime('%Y-%m-%d %H:%M:%S'),
                   'mtime': int(stat.st_mtime), 'ctime': int(stat.st_ctime)})
  result.sort(key=lambda x:x['mtime'])
  return result


def parse_mapping_info(mapping_file):
  fp = open(mapping_file, 'r')
  content = fp.read()
  fp.close()
  #COLUMNS = [
  action_started = False
  mapping_info = []
  for line in content.split('\n'):
    if not line:
      continue
    if line == ('-' * 78):
      action_started = True
      continue
    if action_started:
      action, id, filename, sha256, timestamp, commit_msg = extract_fields(line)
      mapping_info.append([action, id, filename, sha256, timestamp, commit_msg])
  return mapping_info


def extract_fields(text):
  COLUMNS = [0, 7, 10, 34, 44, 65]
  action     = text[COLUMNS[0]: COLUMNS[1]].strip()
  id         = text[COLUMNS[1]: COLUMNS[2]].strip()
  filename   = text[COLUMNS[2]: COLUMNS[3]].strip()
  sha256     = text[COLUMNS[3]: COLUMNS[4]].strip()
  timestamp  = text[COLUMNS[4]: COLUMNS[5]].strip()
  commit_msg = text[COLUMNS[5]:].strip()
  return action, id, filename, sha256, timestamp, commit_msg


_g_count = 0
def new_id():
  global _g_count
  id = _g_count
  _g_count += 1
  return id


def analyze_and_create_mapping_file(inputs, output_dir):
  lock_file = os.path.abspath(os.path.join(output_dir, '.gitdeclutter.lock'))
  file_list = build_file_list(inputs)
  metadata = get_file_metadata(file_list)
  # TODO: Try and detect create vs modify vs delete, assign ids
  print('# Instructions: The actions below are listed by the order in which')
  print('# they occured. git-declutter tries its best to detect when a file')
  print('# was saved with a different file name (TODO: This isn\'t happening')
  print('# yet) versus created for the first time. For all items below,')
  print('# use the action `create` if a new file is being created, and use')
  print('# the action `modify` if a file is being modified, and change the')
  print('# id to match the id of the previously created or modified file.')
  print('# These actions will be used to build the new git repository.')
  print('# Also, enter the commit messages that will be used for each commit.')
  print('# Do not change any other fields.')
  print('#')
  print('# Save this text below to a file, then rerun git-declutter with')
  print('# the -m flag, providing the path to that saved file.')
  print('')
  print('Inputs: %s' % ' '.join(['"%s"' % m['path'] for m in metadata]))
  print('Output: %s' % lock_file)
  print('Body:')
  print('')
  print('ACTION ID FILENAME                SHA256    ' +
        'TIMESTAMP            COMMIT MESSAGE')
  print('-' * 78)
  for m in metadata:
    action = 'create'
    id = new_id()
    basename = m['basename']
    if len(basename) < 22:
      basename += ' ' * (22 - len(basename))
    elif len(basename) > 22:
      basename = basename[:14] + '...' + basename[-5:]
    commit_msg = 'Create new file'
    print('%s %s  %s  %s  %s  %s' % (action, id, basename,
                                     m['hash'], m['modified'], commit_msg))


def main_dispatch(inputs, output_dir, mapping_file, is_bare):
  if mapping_file is None:
    if os.path.exists(output_dir):
      raise RuntimeError('Output directory already exists: %s' % output_dir)
    analyze_and_create_mapping_file(inputs, output_dir)
  else:
    mapping_info = parse_mapping_info(mapping_file)
    raise RuntimeError('stop')


def run():
  p = argparse.ArgumentParser(description='Turn your mess of copied files into '
                              'a tidy git repository.')
  p.add_argument('-o', dest='output_dir',
                 help='Output git repository to create.', required=True)
  p.add_argument('-m', dest='mapping_file',
                 help='Use a file for describing the commits.')
  p.add_argument('--bare', dest='is_bare', action='store_true')
  p.add_argument('inputs', type=str, nargs='+',
                 help='Input directories or globs to process.')
  args = p.parse_args()
  main_dispatch(args.inputs, args.output_dir, args.mapping_file, args.is_bare)


if __name__ == '__main__':
  run()
