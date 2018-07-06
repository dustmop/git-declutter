# git-declutter

## Concept

Let's say you have a directory that's a mess of copies of a file.

![Finder window full of copies](https://raw.githubusercontent.com/dustmop/git-declutter/master/assets/01_finder.jpg)

Really though, what you'd like is a nice, neat directory with only the latest version, and any other copies stored away in the history of a tidy git repo. You can accomplish this by running git-declutter from the command-line, passing in your messy directory (git-declutter will *never* modify your existing files!), and the destination where you'd like to create a new repo:

`python git-declutter.py Docs -o new_repo`

![Command-line output of git-declutter](https://raw.githubusercontent.com/dustmop/git-declutter/master/assets/02_command-line.jpg)

Copy the output from git-declutter into a text file, fixing it up by specifying how you'd like your new repo to look. In this case, we want only a single file, so we start with "create 0", then all the rest of the actions will use "modify 0", to declare that they are modifying the same file (id 0).

![Text file containing mapping](https://raw.githubusercontent.com/dustmop/git-declutter/master/assets/03_changes-map.jpg)

Finally, run git-declutter again, passing it this saved map file:

`python git-declutter -m changes.map`

![History in the new git repo](https://raw.githubusercontent.com/dustmop/git-declutter/master/assets/04_git-repo.png)

How nice!

## How it works

git has facilities for writing commits with arbitrary timestamps, but the interface for doing so is awkward and hard to use. git-declutter is essentially a frontend to make this easier. It sorts the input files by modified timestamp, under the assumption that these modification times roughly represent a point in time when a commit would have been desired.

In the future, git-declutter may do more work to try and compare filenames and file contents to detect similar, in order to better guess file creation from file modification.

I hope you find this utility useful!

## Tips

git-declutter's "map" format is inspired by interactive rebase (`git rebase -i`). The allowed action names are `create`, `modify`, and `omit`.

The displayed filename is only for your benefit; it is ignored by git-declutter. The only fields that matter are the action, id, sha256 (uniquely identifies the file), timestamp (can be tweaked to your liking), and of course the commit message.

The list of input files are shown in timestamp order. If the files are of a format that is easily diffable (a text format), you can diff each pair in order to come up with useful commit messages for each step.
