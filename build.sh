#!/usr/bin/env bash
set -euo pipefail

prefix="${IMAGE_PREFIX:-ghcr.io/mihneateodorstoica/jovykit}"
targets=(minimal base extended full)
default_python_versions=(3.9 3.10 3.11 3.12 3.13 3.14)
python_versions=()
requested=()
release=""
channels=()
tag_latest=false

usage() {
  cat <<EOF
usage: $0 [OPTIONS] [all|minimal|base|extended|full ...]

Options:
  -p, --python-version VERSION  Build VERSION as :LEVEL-python-VERSION. Repeat or use commas.
      --python VERSION          Alias for --python-version.
      --image IMAGE             Image repository. Default: ${prefix}
      --prefix PREFIX           Alias for --image.
      --release VERSION         Also tag :LEVEL-python-VERSION-VERSION.
      --channel CHANNEL         Also tag :LEVEL-CHANNEL-python-VERSION. Repeat for nightly, weekly, monthly.
      --latest                  Also tag :latest for minimal Python 3.14.
  -h, --help                    Show this help.

Default versions:
  minimal/base: 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
  extended/full: 3.11, 3.12, 3.13

Examples:
  $0 --python-version 3.13 minimal
  $0 --python 3.13 --python 3.14 minimal base
  $0 --python-version 3.11,3.12,3.13 all
  $0 --python 3.14 --release v8.1.0 --latest minimal
  $0 --python 3.11 --channel nightly base
EOF
}

add_python_versions() {
  local raw="$1"
  local version

  raw="${raw//,/ }"
  for version in ${raw}; do
    python_versions+=("${version}")
  done
}

add_channel() {
  case "$1" in
    nightly | weekly | monthly)
      channels+=("$1")
      ;;
    *)
      printf 'unknown channel: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
}

while (($#)); do
  case "$1" in
    -p | --python-version | --python)
      if [[ "$#" -lt 2 ]]; then
        printf 'missing value for %s\n' "$1" >&2
        exit 2
      fi
      add_python_versions "$2"
      shift 2
      ;;
    --python-version=* | --python=*)
      add_python_versions "${1#*=}"
      shift
      ;;
    --prefix | --image)
      if [[ "$#" -lt 2 ]]; then
        printf 'missing value for %s\n' "$1" >&2
        exit 2
      fi
      prefix="$2"
      shift 2
      ;;
    --prefix=* | --image=*)
      prefix="${1#*=}"
      shift
      ;;
    --release)
      if [[ "$#" -lt 2 ]]; then
        printf 'missing value for %s\n' "$1" >&2
        exit 2
      fi
      release="$2"
      shift 2
      ;;
    --release=*)
      release="${1#*=}"
      shift
      ;;
    --channel)
      if [[ "$#" -lt 2 ]]; then
        printf 'missing value for %s\n' "$1" >&2
        exit 2
      fi
      add_channel "$2"
      shift 2
      ;;
    --channel=*)
      add_channel "${1#*=}"
      shift
      ;;
    --latest)
      tag_latest=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    --)
      shift
      requested+=("$@")
      break
      ;;
    -*)
      printf 'unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
    *)
      requested+=("$1")
      shift
      ;;
  esac
done

if [[ "${#python_versions[@]}" -eq 0 ]]; then
  if [[ -n "${PYTHON_VERSIONS:-}" ]]; then
    add_python_versions "${PYTHON_VERSIONS}"
  elif [[ -n "${PYTHON_VERSION:-}" ]]; then
    add_python_versions "${PYTHON_VERSION}"
  else
    python_versions=("${default_python_versions[@]}")
  fi
fi

if [[ "${#requested[@]}" -eq 0 ]]; then
  requested=(all)
fi

selected=()
for image in "${requested[@]}"; do
  if [[ "${image}" == "all" ]]; then
    selected=("${targets[@]}")
    break
  fi
  case "${image}" in
    minimal | base | extended | full)
      selected+=("${image}")
      ;;
    *)
      printf 'unknown image: %s\n' "${image}" >&2
      usage >&2
      exit 2
      ;;
  esac
done

image_supports_python() {
  local image="$1"
  local version="$2"

  case "${image}:${version}" in
    minimal:3.9 | minimal:3.10 | minimal:3.11 | minimal:3.12 | minimal:3.13 | minimal:3.14)
      return 0
      ;;
    base:3.9 | base:3.10 | base:3.11 | base:3.12 | base:3.13 | base:3.14)
      return 0
      ;;
    extended:3.11 | extended:3.12 | extended:3.13)
      return 0
      ;;
    full:3.11 | full:3.12 | full:3.13)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

build_python_version() {
  local version="$1"
  local image
  local tags

  for image in "${selected[@]}"; do
    if ! image_supports_python "${image}" "${version}"; then
      printf 'skip %s Python %s (unsupported)\n' "${image}" "${version}" >&2
      continue
    fi
    tags=(-t "${prefix}:${image}-python-${version}")
    if [[ -n "${release}" ]]; then
      tags+=(-t "${prefix}:${image}-python-${version}-${release}")
    fi
    for channel in "${channels[@]}"; do
      tags+=(-t "${prefix}:${image}-${channel}-python-${version}")
    done
    if [[ "${tag_latest}" == true && "${image}" == "minimal" && "${version}" == "3.14" ]]; then
      tags+=(-t "${prefix}:latest")
    fi
    docker build \
      --build-arg "PYTHON_VERSION=${version}" \
      --target "${image}" \
      "${tags[@]}" \
      ./image
  done
}

if [[ "${#python_versions[@]}" -eq 1 ]]; then
  build_python_version "${python_versions[0]}"
  exit 0
fi

pids=()
pid_versions=()
for version in "${python_versions[@]}"; do
  build_python_version "${version}" &
  pids+=("$!")
  pid_versions+=("${version}")
done

status=0
for index in "${!pids[@]}"; do
  if ! wait "${pids[$index]}"; then
    printf 'build failed for Python %s\n' "${pid_versions[$index]}" >&2
    status=1
  fi
done

exit "${status}"
