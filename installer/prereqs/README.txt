Optional prerequisite installers for Windows Setup
=================================================

Drop these files in this folder before running:

- vc_redist.x64.exe
  Microsoft Visual C++ Redistributable (x64)

- Tailscale-setup.exe
  Tailscale Windows installer (optional)

The installer will silently install each prerequisite only when needed:
- VC++ runtime installs if not already present
- Tailscale installs if not already present

If these files are not present, setup still builds and installs the app,
but prerequisite installation is skipped.
