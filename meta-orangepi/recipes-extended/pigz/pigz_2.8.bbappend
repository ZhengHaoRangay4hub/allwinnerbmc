# zlib.net intermittently returns a corrupted pigz archive on hosted runners.
# Use the official upstream GitHub tag for the same pigz release.
SRC_URI = "https://github.com/madler/pigz/archive/refs/tags/v${PV}.tar.gz"
SRC_URI[sha256sum] = "2f7f6a6986996d21cb8658535fff95f1c7107ddce22b5324f4b41890e2904706"
