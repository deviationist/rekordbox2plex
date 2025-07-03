import frida
import textwrap
from pathlib import Path
from typing import Any, Dict, Union
import time
import psutil

class KeyExtractor:
    """Extracts the Rekordbox database key using code injection.

    This method works by injecting code into the Rekordbox process and intercepting the
    call to unlock the database. Works for any Rekordbox version.
    """

    # fmt: off
    SCRIPT = textwrap.dedent("""
    var sqlite3_key = Module.findExportByName(null, 'sqlite3_key');

    Interceptor.attach(sqlite3_key, {
        onEnter: function(args) {
            var size = args[2].toInt32();
            var key = args[1].readUtf8String(size);
            send('sqlite3_key: ' + key);
        }
    });
    """)
    # fmt: on

    def __init__(self, rekordbox_executable: Union[str, Path]):
        self.executable = str(rekordbox_executable)
        self.key = ""

    def on_message(self, message: Dict[str, Any], data: Any) -> None:
        payload = message["payload"]
        if payload.startswith("sqlite3_key"):
            self.key = payload.split(": ")[1]

    def run(self) -> str:
        pid = self.get_rekordbox_pid()
        if pid:
            raise RuntimeError(
                "Rekordbox is running. Please close Rekordbox before running the `KeyExtractor`."
            )
        # Spawn Rekordbox process and attach to it
        pid = frida.spawn(self.executable)
        frida.resume(pid)
        session = frida.attach(pid)
        script = session.create_script(self.SCRIPT)
        script.on("message", self.on_message)
        script.load()
        # Wait for key to be extracted
        while not self.key:
            time.sleep(0.1)
        # Kill Rekordbox process
        frida.kill(pid)

        return self.key

    def get_rekordbox_pid(self, raise_exec: bool = False) -> int:
        """Returns the process ID of the Rekordbox application.

        Parameters
        ----------
        raise_exec : bool, optional
            Raise an exception if the Rekordbox process can not be found.

        Returns
        -------
        pid : int
            The ID of the Rekordbox process if it exists, otherwise zero.

        Raises
        ------
        RuntimeError: If ``raise_exec=True``, raises a runtime error if the Rekordbox
            application is not running.

        Examples
        --------
        >>> get_rekordbox_pid()
        12345
        """
        return self.get_process_id("rekordbox", raise_exec)

    def get_process_id(self, name: str, raise_exec: bool = False) -> int:
        """Returns the ID of a process if it exists.

        Parameters
        ----------
        name : str
            The name of the process, for example 'rekordbox'.
        raise_exec : bool, optional
            Raise an exception if the process can not be found.

        Returns
        -------
        pid : int
            The ID of the process if it exists, otherwise zero.

        Raises
        ------
        RuntimeError: If ``raise_exec=True``, raises a runtime error if the application
            is not running.

        Examples
        --------
        >>> get_process_id("rekordbox")
        12345

        >>> get_process_id("rekordboxAgent")
        23456
        """
        for proc in psutil.process_iter():
            try:
                proc_name = os.path.splitext(proc.name())[0]  # needed on Windows (.exe)
                if proc_name == name:
                    pid: int = proc.pid
                    return pid
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
        if raise_exec:
            raise RuntimeError("No process with name 'rekordbox' found!")
        return 0
