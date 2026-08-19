#!/usr/bin/env bash
set -Eeuo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
version=$(sed -n "s/^Version:[[:space:]]*//p" "$repo_root/packaging/gnome-customizer.spec" | head -n1)
if [[ -z "$version" ]]; then
    echo "Could not read the RPM version" >&2
    exit 1
fi

for command_name in rpmbuild meson ninja; do
    command -v "$command_name" >/dev/null || {
        echo "Missing $command_name; Fedora needs rpm-build/meson/ninja-build, while Ubuntu/Debian needs rpm/meson/ninja-build" >&2
        exit 1
    }
done

rpm_root=${RPMBUILD_ROOT:-"$repo_root/.rpmbuild"}
source_dir="$rpm_root/SOURCES"
spec_dir="$rpm_root/SPECS"
mkdir -p "$source_dir" "$spec_dir"

archive="$source_dir/gnome-customizer-$version.tar.gz"
tar --transform="s,^,gnome-customizer-$version/," --exclude='./.git' --exclude='./build*' --exclude='./obj-*' --exclude='./stage*' \
    --exclude='./.rpmbuild' --exclude='./.rpmbuild-*' --exclude='./Screenshots' \
    --exclude='./verify.*' --exclude='./package-check.*' \
    -C "$repo_root" -czf "$archive" .
cp "$repo_root/packaging/gnome-customizer.spec" "$spec_dir/"

rpm_defines=(--define "_topdir $rpm_root")
if [[ -n "${RPM_CONFIGDIR:-}" ]]; then
    rpm_defines+=(--define "_rpmconfigdir $RPM_CONFIGDIR")
fi
rpmbuild "${rpm_defines[@]}" -ba "$spec_dir/gnome-customizer.spec"
echo "RPMs are in: $rpm_root/RPMS/noarch"
