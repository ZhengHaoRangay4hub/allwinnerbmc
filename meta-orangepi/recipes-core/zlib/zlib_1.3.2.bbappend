# zlib.net intermittently returns corrupted archives on hosted runners.
# Use the upstream maintainer's GitHub release for the identical tarball.
SRC_URI = "https://github.com/madler/zlib/releases/download/v${PV}/${BP}.tar.gz \
           file://run-ptest \
           "
SRC_URI[sha256sum] = "bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16"
