#!/usr/bin/env bash
# Run inside the initialized BitBake environment. Both stages share one budget.
set -Eeuo pipefail

stage=${1:?usage: ci-build-stage.sh boot|image}
: "${GITHUB_WORKSPACE:?}"
: "${GITHUB_ENV:?}"
: "${GITHUB_OUTPUT:?}"

case "$stage" in
  boot)
    # Include real boot environment tools and validate board helpers early.
    # Per-target tasks avoid pulling capture runtime dependencies into this gate.
    command=(bitbake u-boot-orangepi orangepi-boot-files
      orangepi-ms2130-capture:do_compile orangepi-gpio-control:do_install)
    log="$GITHUB_WORKSPACE/openbmc-boot.log"
    ;;
  image)
    # Keep unrelated tasks running through their sstate-producing steps after
    # a recipe fails, instead of discarding hours of finished do_compile work.
    command=(bitbake -k obmc-phosphor-image)
    log="$GITHUB_WORKSPACE/openbmc-bitbake.log"
    ;;
  *) echo "::error::Unknown build stage: $stage"; exit 2 ;;
esac

if [[ -z ${OPENBMC_BUILD_DEADLINE:-} ]]; then
  budget=${OPENBMC_BUILD_BUDGET_SECONDS:-18000}
  [[ $budget =~ ^[1-9][0-9]*$ ]] || { echo '::error::Invalid build budget'; exit 2; }
  OPENBMC_BUILD_DEADLINE=$(( $(date +%s) + budget ))
  echo "OPENBMC_BUILD_DEADLINE=$OPENBMC_BUILD_DEADLINE" >> "$GITHUB_ENV"
fi
remaining=$(( OPENBMC_BUILD_DEADLINE - $(date +%s) ))
if (( remaining <= 0 )); then
  echo 'checkpointed=true' >> "$GITHUB_OUTPUT"
  exit 0
fi

echo "Stage $stage: ${remaining}s remain in the shared build budget."
set +e
timeout --signal=TERM --kill-after=5m "${remaining}s" \
  "${command[@]}" 2>&1 | tee "$log"
pipeline_status=("${PIPESTATUS[@]}")
set -e
build_rc=${pipeline_status[0]}
if (( pipeline_status[1] != 0 )); then
  echo '::error::Could not save the BitBake log (check free disk space).'
  echo 'checkpointed=false' >> "$GITHUB_OUTPUT"
  exit 1
fi

if (( build_rc == 124 )) || \
   { (( build_rc == 137 || build_rc == 143 )) && \
     (( $(date +%s) >= OPENBMC_BUILD_DEADLINE )); }; then
  # A timeout must not conceal a recipe error already reported by BitBake -k.
  if grep -q '^ERROR:' "$log"; then
    echo '::error::A recipe failed before the build budget expired; repair it before resuming.'
    echo 'checkpointed=false' >> "$GITHUB_OUTPUT"
    exit 1
  fi
  echo 'checkpointed=true' >> "$GITHUB_OUTPUT"
  echo "Stage $stage reached the time budget; completed sstate will be saved."
  exit 0
fi

echo 'checkpointed=false' >> "$GITHUB_OUTPUT"
if (( build_rc != 0 )); then
  echo "::error::BitBake stage $stage failed with exit code $build_rc."
  exit "$build_rc"
fi

deploy="$GITHUB_WORKSPACE/yocto-tmp/deploy/images/orangepi-zero2"
if [[ $stage == boot ]]; then
  test -s "$deploy/u-boot-sunxi-with-spl.bin"
  test -s "$deploy/uboot.env"
  test -s "$deploy/orangepi-zero2-extlinux.conf"
else
  image=$(find "$deploy" -maxdepth 1 -type f -name '*.wic' -size +0c -print -quit)
  test -n "$image" || { echo '::error::BitBake completed without a TF-card image.'; exit 1; }
fi
