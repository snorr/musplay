# 4 December 2015
import argparse
import os
import re
import shlex
import subprocess
import sys


def error(*msg, code=1):
    print("error:", *msg, file=sys.stderr)
    exit(code)


extensions = {"mp3", "aac", "mka", "dts", "flac", "ogg", "m4a", "ac3", "opus", "wav"}
_re_ext = r'(' + r'|'.join(extensions) + r')'


def _patgen_title(query):
    query = r'[^/]*'.join(re.escape(p) for p in query.split())
    return query + r'[^/]*\.' + _re_ext + r'$'

def _patgen_album(query):
    query = r'[^/]*'.join(re.escape(p) for p in query.split())
    return query + r'[^/]*/.*\.' + _re_ext + r'$'

def _patgen_playlist(query):
    query = r'[^/]*'.join(re.escape(p) for p in query.split())
    return query + r'[^/]*\.txt$'

def _patgen_general(query):
    # all slashes must be explicit, but spaces still count as wildcard
    segs = (p.split() for p in query.split('/'))
    query = r'.*/.*'.join(r'[^/]*'.join(re.escape(p) for p in s) for s in segs)
    return query + r'.*\.' + _re_ext + r'$'


pattern_generators = {
    '@': _patgen_title,
    '@@': _patgen_album,
    '%':  _patgen_playlist,
    '$': _patgen_general,
}

sorted_patterns = list(pattern_generators.items())
sorted_patterns.sort(key=lambda pair: len(pair[0]), reverse=True)


loading_sentinent = object()


class Searcher:

    def __init__(self, *, music_dir=None, playlist_dir=None, debug=False, quiet=False):
        self.debug_flag = debug
        self.quiet = quiet

        if music_dir is None:
            music_dir = os.environ.get('MUSPLAY_MUSIC')
            if music_dir is None:
                error("missing environment variable MUSPLAY_MUSIC", code=2)

        if playlist_dir is None:
            playlist_dir = os.environ.get('MUSPLAY_PLAYLISTS')
            if playlist_dir is None:
                playlist_dir = os.path.join(music_dir, 'Playlists')
                if not os.path.exists(playlist_dir):
                    playlist_dir = music_dir
            elif not os.path.exists(playlist_dir):
                self.warn("MUSPLAY_PLAYLISTS folder doesn't exist {!r}".format(playlist_dir))

        self.music_dir = music_dir
        self.playlist_dir = playlist_dir
        self.loaded_playlists = {}
        self.paths = []

    def debug(self, *msg):
        if self.debug_flag:
            print("debug:", *msg, file=sys.stderr)

    def warn(self, *msg):
        if not self.quiet:
            print("warning:", *msg, file=sys.stderr)

    def call_searcher(self, pattern, folder):
        cmd = ['find', '-Ef', folder, '--', '-iregex', '.*' + pattern + '.*']
        self.debug(' '.join(shlex.quote(arg) for arg in cmd))
        result = subprocess.run(cmd, stdout=subprocess.PIPE)

        if result.returncode == 0:
            return result.stdout.decode('utf-8').strip().split('\n')
        else:
            return None

    def find_tracks(self, patterns):
        """Attempts to find the music tracks by the given patterns"""

        paths = []
        for pattern in patterns:
            if not pattern:
                continue

            # See if pattern matches one of the prefixes
            match = None
            for prefix, gen in sorted_patterns:
                if pattern.startswith(prefix):
                    match = (prefix, gen)
                    break
            if match:
                prefix, gen = match
                pat = gen(pattern[len(prefix):].lstrip())
                self.debug("match {} => {!r} ({!r})".format(prefix, pattern, pat))

                if prefix == '%':
                    # special playlist search
                    result = self.call_searcher(pat, self.playlist_dir)
                    if result:
                        res = []
                        for playlist in result:
                            res += self.parse_playlist(playlist)
                        result = res
                else:
                    result = self.call_searcher(pat, self.music_dir)

                if result:
                    paths += result
                else:
                    self.warn("no tracks found for pattern {!r}".format(pattern))
                continue

            # Otherwise it must be a simple path
            ext = os.path.splitext(pattern)[1]

            if ext == '.txt':
                pattern = os.path.join(self.playlist_dir, pattern)
                paths += self.parse_playlist(pattern)
                continue

            if ext[1:] in extensions:
                pattern = os.path.join(self.music_dir, pattern)
                paths.append(pattern)
                continue

            self.warn("ignoring unknown extension {!r} for pattern {!r}".format(ext, pattern))

        return paths

    def parse_playlist(self, playlist):
        playlist = os.path.realpath(playlist)

        cached = self.loaded_playlists.get(playlist)
        if cached is loading_sentinent:
            self.warn("recursive playlists are not supported")
            return []
        if cached:
            self.debug("using cache for {!r}".format(playlist))
            return self.loaded_playlists[playlist]
        self.loaded_playlists[playlist] = loading_sentinent

        self.debug("trying to parse {!r}".format(playlist))
        try:
            with open(playlist, 'r') as f:
                data = f.read()
        except IOError:
            self.warn("could not read playlist file {!r}".format(playlist))
            return []

        patterns = []
        for line in data.split('\n'):
            line = line.strip()
            if line.startswith('#'):
                continue
            patterns.append(line)

        if not patterns:
            self.warn("no patterns in playlist file: {!r}".format(playlist))

        paths = self.find_tracks(patterns)
        self.loaded_playlists[playlist] = paths
        return paths


description = """
Find music tracks by track and album titles.

environment variables:
  MUSPLAY_MUSIC         where to find music tracks (required)
  MUSPLAY_PLAYLISTS     where to find playlists
                        (default: $MUSPLAY_MUSIC/Playlists)
"""

epilog="""
pattern prefixes:
  @         search by track title (filename minus extension)
  @@        search by album title (directory name)
  %         search for playlists in the playlist directory (see above)
  $         search by the entire path to the file
  no prefix use pattern as a literal path to a file or playlist
"""


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(description=description, epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("pattern", nargs="+",
        help="the patterns to search with (see pattern prefixes below)")

    parser.add_argument("-d", "--debug", action="store_true", default=False,
        help="print extra information for debugging")

    parser.add_argument("-q", "--quiet", action="store_true", default=False,
        help="suppress non-fatal warnings")

    parser.add_argument("--exclude", metavar="pattern", nargs="+",
        help="exclude anything matched by the given patterns")

    parsed = parser.parse_args(args)

    searcher = Searcher(debug=parsed.debug, quiet=parsed.quiet)

    paths = searcher.find_tracks(parsed.pattern)

    if parsed.exclude:
        excluded = set(searcher.find_tracks(parsed.exclude))
        paths = (p for p in paths if not p in excluded)

    for path in paths:
        print(path)


if __name__ == '__main__':
    main()
