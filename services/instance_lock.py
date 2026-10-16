"""
Single-instance lock.

Prevents two copies of the app from running at once, which would put
two processes on the same SQLite file and double-log every action.

Implementation: QLocalServer. A named local socket is bound by the first
instance; subsequent instances try to connect to it and, if successful,
know an instance is already running.

The socket is released automatically when the process exits.

Usage in main.py:

    from services.instance_lock import SingleInstanceGuard
    guard = SingleInstanceGuard("AcademySystem")
    if not guard.acquire():
        # another instance is already running
        sys.exit(0)
    # ... rest of startup ...
"""

from qtpy.QtNetwork import QLocalServer, QLocalSocket
from qtpy.QtCore import QObject


class SingleInstanceGuard(QObject):
    """
    Owns a QLocalServer for the lifetime of the process.

    Call `acquire()` once at startup. If it returns False, another
    instance already owns the lock — exit immediately.

    Keep a reference to this object somewhere (e.g. assign it to a
    module-level variable in main.py) so Qt doesn't garbage-collect it
    and release the socket prematurely.
    """

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._server = None

    def acquire(self) -> bool:
        """
        Try to become the single instance.

        Returns True if we now own the lock (no other instance).
        Returns False if another instance already holds it.
        """
        # Step 1: is there an instance already listening?
        probe = QLocalSocket()
        probe.connectToServer(self._key)
        if probe.waitForConnected(200):
            # Connected → another instance owns the socket.
            probe.disconnectFromServer()
            return False

        # Step 2: no live instance. In case a previous run crashed and
        # left a stale socket, ask Qt to clean it up.
        QLocalServer.removeServer(self._key)

        # Step 3: bind our own server.
        server = QLocalServer(self)
        # Prevent other users on the same machine from opening our
        # socket. Only meaningful on Unix; harmless on Windows.
        try:
            server.setSocketOptions(
                QLocalServer.SocketOption.UserAccessOption
            )
        except Exception:
            pass

        if not server.listen(self._key):
            # Couldn't bind — most likely a permission or name collision.
            # Fail open (allow the app to run) rather than block a
            # legitimate startup, but log it.
            import logging
            logging.getLogger(__name__).warning(
                "instance_lock: could not bind %s: %s",
                self._key, server.errorString()
            )
            return True

        self._server = server
        return True