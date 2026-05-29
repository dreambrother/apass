import platform
import subprocess


def copy(text: str) -> None:
    system = platform.system()
    if system == "Darwin":
        subprocess.run("pbcopy", input=text, text=True)
    elif system == "Linux":
        subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True)
    elif system == "Windows":
        subprocess.run("clip", input=text, text=True, shell=True)
