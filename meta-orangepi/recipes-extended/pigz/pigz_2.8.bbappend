# zlib.net intermittently returns a corrupted pigz archive on hosted runners.
# Use the official upstream repository at the immutable v2.8 commit.  The
# git fetcher also avoids the unstable-archive QA check.
SRC_URI = "git://github.com/madler/pigz.git;protocol=https;branch=master"
SRCREV = "829eabb60cb4e6c42aff9d419bf6cf621dce76fd"
