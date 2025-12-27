import multiprocessing
import sys

import customtkinter as ctk

from src.ui.app import iFakeGPSApp
from src.utils.logger import logger


def main():
    """Main entry point."""
    try:
        app = iFakeGPSApp()
        app.mainloop()
    except Exception as e:
        logger.critical(f"Application crashed: {e}", exc_info=True)
        # Show error in UI if possible, otherwise just exit
        try:
            import tkinter.messagebox

            tkinter.messagebox.showerror("Critical Error", f"Application crashed:\n{e}")
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    # Fix for multiprocessing support in frozen applications
    multiprocessing.freeze_support()

    # Handle internal wrapper execution for frozen app (pymobiledevice3 CLI)
    # This allows us to run internal commands like 'tunneld' or 'mounter' from the single exe
    if len(sys.argv) > 1 and sys.argv[1].startswith("--internal-"):
        try:
            cmd = sys.argv[1]
            if cmd == "--internal-pmd3":
                # Generic pymobiledevice3 CLI wrapper
                # Usage: exe --internal-pmd3 [args...] -> pymobiledevice3 [args...]
                from pymobiledevice3.__main__ import cli

                # Shift args: remove exe path and internal flag
                # sys.argv becomes ['pymobiledevice3', arg2, arg3...]
                sys.argv = ["pymobiledevice3"] + sys.argv[2:]
                cli()

            elif cmd == "--internal-tunneld":
                # Legacy support for specific tunneld flag
                from pymobiledevice3.__main__ import cli

                sys.argv = ["pymobiledevice3", "remote", "tunneld"]
                cli()

        except Exception as e:
            # Log errors to stderr so they appear in console if attached
            print(f"Failed to run internal command: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
        sys.exit(0)

    main()
