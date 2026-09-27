"""PyInstaller entrypoint. Keep package imports intact in frozen Windows builds."""
from forgecast.server import main


if __name__ == '__main__':
    main()
