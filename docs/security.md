# Security model

The GTK process runs as the logged-in user. Desktop GSettings need no elevation. Shell rendering occurs inside the packaged, focused companion using only its own schema. GDM writes cross a system D-Bus boundary.

The helper has explicit methods and no command execution, shell, environment, script, or arbitrary-path method. It validates schemas, keys, exact Python types, colors, image magic, sizes, resource contents, and monitor XML shape. Subprocesses use fixed absolute executables and argv arrays. Files use atomic replacement and fixed owned paths.

PolicyKit authorization is checked against the calling D-Bus process with user interaction allowed. Resource activation happens only after compilation and `gresource list` validation. Previous alternatives and monitor state are captured once. Restore cannot reset the user's entire GNOME profile.

If the GDM dconf profile did not exist, the helper records that it created the exact standard profile. Restore/purge removes it only while its contents are still unchanged; a subsequently edited profile is preserved. Multiline strings are escaped before dconf keyfile generation, and transaction rollback snapshots the profile, managed settings, assets, resource, alternatives state, and monitor state.
