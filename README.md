# Install

This program requires [Python](https://www.python.org/) 3.2+. For music
playback, it uses the program [`mpv`](https://mpv.io/), which can be installed
on OS X by using the following [Homebrew](http://brew.sh/) command

```
$ brew install python3 mpv
```

### NOTE

Only \*nix systems are supported at the moment.


# Config

The program expects your music to be in a directory given by the environment
variable `MUSPLAY_MUSIC`. Playlists will be searched for in
`$MUSPLAY_PLAYLISTS` or, if that is missing, in `$MUSPLAY_MUSIC/Playlists`.


# Usage

Throw the folder somewhere and run

```
$ python3 musplay --help
```


# Search functionality

If you only want to use the program to search for tracks, use the `-n` flag as
in

```
$ python3 musplay -n '@Trash80'
```

or run the `search.py` directly as in

```
$ python3 musplay/search.py '@Trash80'
```
